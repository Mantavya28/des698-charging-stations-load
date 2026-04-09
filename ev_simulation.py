"""
Event-Driven EV Charging Load Simulation Engine
================================================
Full discrete-event simulation with:
  - EV objects with SoC state
  - Station utility-based routing (M/G/c/K queues)
  - Dynamic power taper for fast chargers (CC-CV approximation)
  - Home charging as a separate load stream
  - heapq-based priority event queue
  - Grid load time series output

Mathematical Model
------------------
  Arrivals    : Poisson(λ(t)) — time-varying rate
  Station flo : utility = -β1·distance - β2·E[wait]
  Fast power  : P(soc) = P_max            if soc ≤ 0.5
                        P_max·(1 - α·(soc-0.5))  otherwise
  Slow power  : constant P_slow
  Grid load   : L(t) = Σ P_i(soc_i, t)
"""

import heapq
import math
import numpy as np
import pandas as pd
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple


# ── Constants ────────────────────────────────────────────────────────────────
DT_MINUTES   = 2          # UPDATE_SOC granularity (minutes)
DT_HOURS     = DT_MINUTES / 60.0
ALPHA_TAPER  = 1.6        # fast charger taper coefficient
BETA1        = 0.02       # distance penalty in utility
BETA2        = 0.05       # wait-time penalty in utility
MAX_WAIT_MIN = 10.0       # threshold: EV leaves if expected wait > this
DELTA_SWITCH = 5.0        # minutes after queuing to reconsider station

# ── Event type constants ──────────────────────────────────────────────────────
ARRIVAL         = "ARRIVAL"
QUEUE_DECISION  = "QUEUE_DECISION"
START_CHARGING  = "START_CHARGING"
UPDATE_SOC      = "UPDATE_SOC"
END_CHARGING    = "END_CHARGING"
SWITCH_STATION  = "SWITCH_STATION"


# ── Data Structures ───────────────────────────────────────────────────────────

@dataclass
class EV:
    ev_id: int
    arrival_time: float          # minutes from sim start
    soc: float                   # current state of charge [0,1]
    target_soc: float = 0.8
    battery_kwh: float = 30.0    # default battery capacity
    assigned_station: int = -1   # station index
    status: str = "en_route"     # en_route / waiting / charging / done / left
    charger_idx: int = -1        # which charger slot is in use


@dataclass
class Charger:
    charger_id: int
    charger_type: str            # "fast" or "slow"
    power_max_kw: float
    occupied: bool = False
    ev_id: Optional[int] = None  # currently charging EV


@dataclass
class Station:
    station_id: int
    chargers: List[Charger]
    queue: List[int] = field(default_factory=list)   # list of ev_ids
    location: Tuple[float, float] = (0.0, 0.0)       # (lat, lon) or (x,y)


# ── Helper functions ──────────────────────────────────────────────────────────

def sample_soc(rng: np.random.Generator) -> float:
    """Incoming battery SOC: Beta distribution centred near 0.25."""
    return float(np.clip(rng.beta(2, 5), 0.05, 0.75))


def sample_interarrival_time(lam_per_min: float, rng: np.random.Generator) -> float:
    """Exponential inter-arrival: Poisson stream with rate λ (per minute)."""
    if lam_per_min <= 0:
        return 1e9
    return float(rng.exponential(1.0 / lam_per_min))


def energy_required(ev: EV) -> float:
    """kWh needed to reach target SoC."""
    return ev.battery_kwh * max(0.0, ev.target_soc - ev.soc)


def charging_power_fast(soc: float, p_max: float) -> float:
    """CC-CV taper: constant until 50%, then linearly de-rated."""
    if soc <= 0.5:
        return p_max
    return p_max * max(0.0, 1.0 - ALPHA_TAPER * (soc - 0.5))


def charging_time_fast(ev: EV, p_max: float) -> float:
    """
    Numerical integration (trapezoidal) from ev.soc → ev.target_soc.
    Returns duration in minutes.
    """
    n_steps = 200
    soc_arr = np.linspace(ev.soc, ev.target_soc, n_steps)
    powers  = np.array([charging_power_fast(s, p_max) for s in soc_arr])
    # dt/dsoc = battery_kwh / power  → total_time = integral(battery_kwh/P ds)
    d_soc   = (ev.target_soc - ev.soc) / (n_steps - 1)
    inv_pwr = np.where(powers > 0, 1.0 / powers, 0.0)
    hours   = float(np.trapz(inv_pwr, dx=d_soc) * ev.battery_kwh)
    return hours * 60.0   # → minutes


def charging_time_slow(ev: EV, power_kw: float) -> float:
    """Constant power: returns duration in minutes."""
    e = energy_required(ev)
    if power_kw <= 0:
        return 1e9
    return (e / power_kw) * 60.0    # → minutes


def expected_wait_time(station: Station) -> float:
    """
    Simplified: queue length / (free chargers × avg service rate).
    Returns estimated wait in minutes.
    """
    n_free = sum(1 for c in station.chargers if not c.occupied)
    avg_rate = 1.0 / 30.0  # ~30 min avg service
    if n_free > 0:
        return 0.0
    q_len = len(station.queue)
    n_chargers = max(1, len(station.chargers))
    return q_len / (n_chargers * avg_rate)


def station_utility(ev: EV, station: Station, ev_location=(0.0, 0.0)) -> float:
    """Higher is better station. Distance in arbitrary grid units."""
    dist = math.dist(ev_location, station.location)
    wait = expected_wait_time(station)
    return -BETA1 * dist - BETA2 * wait


# ── Core Simulation Class ─────────────────────────────────────────────────────

class EVChargingSimulation:
    """
    Full event-driven EV charging load simulation.

    Parameters
    ----------
    demand_curve_per_min : array of shape (T,) — arrival rate λ(t) per minute
    stations_cfg         : list of dicts, each with keys:
                             id, location, chargers (list of {type, power_kw})
    battery_kwh          : default battery size (kWh)
    home_charge_kwh      : average home-charging energy per EV (kWh)
    home_power_kw        : home charger power (kW)
    n_home_evs           : number of home-charging EVs in the evening
    random_seed          : reproducibility
    """

    def __init__(
        self,
        demand_curve_per_min: np.ndarray,
        stations_cfg: List[Dict],
        battery_kwh: float = 30.0,
        home_charge_kwh: float = 8.0,
        home_power_kw: float = 3.3,
        n_home_evs: int = 0,
        random_seed: int = 42,
    ):
        self.T_end = len(demand_curve_per_min)  # minutes
        self.lambda_t = demand_curve_per_min
        self.battery_kwh = battery_kwh
        self.home_charge_kwh = home_charge_kwh
        self.home_power_kw = home_power_kw
        self.n_home_evs = n_home_evs
        self.rng = np.random.default_rng(random_seed)

        # Build station objects
        self.stations: List[Station] = []
        for cfg in stations_cfg:
            chargers = [
                Charger(
                    charger_id=i,
                    charger_type=c["type"],
                    power_max_kw=c["power_kw"],
                )
                for i, c in enumerate(cfg["chargers"])
            ]
            self.stations.append(
                Station(
                    station_id=cfg["id"],
                    chargers=chargers,
                    location=tuple(cfg.get("location", (0.0, 0.0))),
                )
            )

        # EV registry
        self.evs: Dict[int, EV] = {}
        self._ev_counter = 0

        # Priority event queue: (time, event_type, payload_dict)
        self._event_queue: List[Tuple[float, str, dict]] = []

        # Load time series: list of (time_min, total_kw)
        self.load_time_series: List[Tuple[float, float]] = []

        # Summary counters
        self.total_served  = 0
        self.total_dropped = 0
        self.total_arrived = 0

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _push(self, time: float, etype: str, payload: dict):
        heapq.heappush(self._event_queue, (time, etype, payload))

    def _pop(self) -> Tuple[float, str, dict]:
        return heapq.heappop(self._event_queue)

    def _new_ev(self, arrival_time: float) -> EV:
        ev = EV(
            ev_id=self._ev_counter,
            arrival_time=arrival_time,
            soc=sample_soc(self.rng),
            battery_kwh=self.battery_kwh,
        )
        self.evs[self._ev_counter] = ev
        self._ev_counter += 1
        return ev

    def _get_lambda(self, t_min: float) -> float:
        idx = min(int(t_min), self.T_end - 1)
        return float(self.lambda_t[idx])

    def _free_charger(self, station: Station) -> Optional[Charger]:
        for c in station.chargers:
            if not c.occupied:
                return c
        return None

    def _charger_for_ev(self, station: Station, ev_id: int) -> Optional[Charger]:
        for c in station.chargers:
            if c.ev_id == ev_id:
                return c
        return None

    # ── Event Handlers ────────────────────────────────────────────────────────

    def _handle_arrival(self, time: float, payload: dict):
        ev = self._new_ev(time)
        self.total_arrived += 1

        # Rank stations by utility (EV location assumed at (0,0) for simplicity)
        ranked = sorted(
            self.stations,
            key=lambda s: station_utility(ev, s),
            reverse=True,   # higher utility = better
        )
        ev.assigned_station = ranked[0].station_id
        self._push(time, QUEUE_DECISION, {"ev_id": ev.ev_id})

        # Schedule next arrival
        lam = self._get_lambda(time)
        next_t = time + sample_interarrival_time(lam, self.rng)
        if next_t < self.T_end:
            self._push(next_t, ARRIVAL, {})

    def _handle_queue_decision(self, time: float, payload: dict):
        ev_id = payload["ev_id"]
        ev = self.evs.get(ev_id)
        if ev is None or ev.status in ("done", "left", "charging"):
            return

        station = self.stations[ev.assigned_station]
        wait = expected_wait_time(station)

        if wait > MAX_WAIT_MIN:
            ev.status = "left"
            self.total_dropped += 1
            return

        charger = self._free_charger(station)
        if charger is not None:
            self._push(time, START_CHARGING, {"ev_id": ev_id})
        else:
            if ev.ev_id not in station.queue:
                station.queue.append(ev.ev_id)
            ev.status = "waiting"
            switch_t = time + DELTA_SWITCH
            if switch_t < self.T_end:
                self._push(switch_t, SWITCH_STATION, {"ev_id": ev_id})

    def _handle_start_charging(self, time: float, payload: dict):
        ev_id = payload["ev_id"]
        ev = self.evs.get(ev_id)
        if ev is None or ev.status in ("done", "left"):
            return

        station = self.stations[ev.assigned_station]

        # Remove from queue if present
        if ev_id in station.queue:
            station.queue.remove(ev_id)

        charger = self._free_charger(station)
        if charger is None:
            # No free charger — re-queue
            if ev_id not in station.queue:
                station.queue.append(ev_id)
            ev.status = "waiting"
            return

        charger.occupied = True
        charger.ev_id = ev_id
        ev.charger_idx = charger.charger_id
        ev.status = "charging"

        if charger.charger_type == "fast":
            duration = charging_time_fast(ev, charger.power_max_kw)
        else:
            duration = charging_time_slow(ev, charger.power_max_kw)

        end_t = time + duration
        if end_t > self.T_end:
            end_t = self.T_end

        self._push(end_t, END_CHARGING, {"ev_id": ev_id})

        # SOC update loop
        upd_t = time + DT_MINUTES
        if upd_t < end_t:
            self._push(upd_t, UPDATE_SOC, {"ev_id": ev_id})

    def _handle_update_soc(self, time: float, payload: dict):
        ev_id = payload["ev_id"]
        ev = self.evs.get(ev_id)
        if ev is None or ev.status != "charging":
            return

        station = self.stations[ev.assigned_station]
        charger = self._charger_for_ev(station, ev_id)
        if charger is None:
            return

        if charger.charger_type == "fast":
            power = charging_power_fast(ev.soc, charger.power_max_kw)
        else:
            power = charger.power_max_kw

        delta_soc = (power * DT_HOURS) / ev.battery_kwh
        ev.soc = min(ev.soc + delta_soc, ev.target_soc)

        if ev.soc < ev.target_soc - 0.001:
            next_upd = time + DT_MINUTES
            if next_upd < self.T_end:
                self._push(next_upd, UPDATE_SOC, {"ev_id": ev_id})

    def _handle_end_charging(self, time: float, payload: dict):
        ev_id = payload["ev_id"]
        ev = self.evs.get(ev_id)
        if ev is None:
            return

        station = self.stations[ev.assigned_station]
        charger = self._charger_for_ev(station, ev_id)

        if charger:
            charger.occupied = False
            charger.ev_id = None

        ev.status = "done"
        ev.soc = ev.target_soc
        self.total_served += 1

        # Pull next EV from queue
        if station.queue:
            next_ev_id = station.queue.pop(0)
            self._push(time, START_CHARGING, {"ev_id": next_ev_id})

    def _handle_switch_station(self, time: float, payload: dict):
        ev_id = payload["ev_id"]
        ev = self.evs.get(ev_id)
        if ev is None or ev.status != "waiting":
            return

        current_st_id = ev.assigned_station
        best = max(
            self.stations,
            key=lambda s: station_utility(ev, s),
        )

        if best.station_id != current_st_id:
            old_st = self.stations[current_st_id]
            if ev_id in old_st.queue:
                old_st.queue.remove(ev_id)
            ev.assigned_station = best.station_id
            self._push(time, QUEUE_DECISION, {"ev_id": ev_id})

    # ── Grid Load Snapshot ────────────────────────────────────────────────────

    def _update_grid_load(self, time: float):
        total = 0.0
        for station in self.stations:
            for charger in station.chargers:
                if charger.occupied and charger.ev_id is not None:
                    ev = self.evs.get(charger.ev_id)
                    if ev is None:
                        continue
                    if charger.charger_type == "fast":
                        total += charging_power_fast(ev.soc, charger.power_max_kw)
                    else:
                        total += charger.power_max_kw
        self.load_time_series.append((time, total))

    # ── Home Charging ─────────────────────────────────────────────────────────

    def _compute_home_load(self) -> np.ndarray:
        """
        Evening home-charging stream — NOT through queue.
        Uniformly distributed start times 18:00–22:00 (minutes 1080–1320).
        Returns per-minute load array of length T_end.
        """
        home_load = np.zeros(self.T_end)
        if self.n_home_evs <= 0 or self.T_end < 60:
            return home_load

        start_window_min = min(int(0.75 * self.T_end), self.T_end - 1)
        end_window_min   = min(int(0.92 * self.T_end), self.T_end - 1)

        for _ in range(self.n_home_evs):
            t_start = int(self.rng.integers(start_window_min, end_window_min + 1))
            duration_min = int(
                math.ceil((self.home_charge_kwh / self.home_power_kw) * 60)
            )
            t_end = min(t_start + duration_min, self.T_end)
            home_load[t_start:t_end] += self.home_power_kw

        return home_load

    # ── Run ───────────────────────────────────────────────────────────────────

    def run(self) -> Dict:
        """
        Execute the full simulation. Returns results dict.
        """
        # Seed first arrival
        lam0 = self._get_lambda(0)
        t0   = sample_interarrival_time(lam0, self.rng)
        if t0 < self.T_end:
            self._push(t0, ARRIVAL, {})

        prev_load_t = 0.0

        while self._event_queue:
            time, etype, payload = self._pop()

            if time >= self.T_end:
                break

            # Record load snapshot since last event
            if time > prev_load_t:
                self._update_grid_load(time)
                prev_load_t = time

            if   etype == ARRIVAL:        self._handle_arrival(time, payload)
            elif etype == QUEUE_DECISION: self._handle_queue_decision(time, payload)
            elif etype == START_CHARGING: self._handle_start_charging(time, payload)
            elif etype == UPDATE_SOC:     self._handle_update_soc(time, payload)
            elif etype == END_CHARGING:   self._handle_end_charging(time, payload)
            elif etype == SWITCH_STATION: self._handle_switch_station(time, payload)

        # ── Build minute-resolution load arrays ───────────────────────────
        station_load = self._resample_load(self.load_time_series)
        home_load    = self._compute_home_load()
        total_load   = station_load + home_load

        # ── Aggregate to 15-min slots (96 per day) ────────────────────────
        slot_load = self._to_15min(total_load)

        # ── Metrics ───────────────────────────────────────────────────────
        dt_hr = 1.0 / 60.0
        total_kwh    = float(np.sum(total_load) * dt_hr)
        peak_kw      = float(np.max(total_load)) if total_load.any() else 0.0
        avg_kw       = float(np.mean(total_load))
        load_factor  = (avg_kw / peak_kw) if peak_kw > 0 else 0.0

        installed_kw = sum(
            c.power_max_kw
            for s in self.stations
            for c in s.chargers
        )
        utilization_pct = (avg_kw / installed_kw * 100) if installed_kw > 0 else 0.0

        return {
            "load_curve":          slot_load.tolist(),
            "load_curve_min":      total_load.tolist(),
            "home_load_min":       home_load.tolist(),
            "station_load_min":    station_load.tolist(),
            "total_kwh":           round(total_kwh, 1),
            "peak_kw":             round(peak_kw, 1),
            "avg_kw":              round(avg_kw, 1),
            "load_factor":         round(load_factor, 4),
            "utilization_pct":     round(utilization_pct, 1),
            "total_arrived":       self.total_arrived,
            "total_served":        self.total_served,
            "total_dropped":       self.total_dropped,
            "installed_kw":        round(installed_kw, 1),
        }

    def _resample_load(self, raw: List[Tuple[float, float]]) -> np.ndarray:
        """
        Forward-fill event-time load snapshots → uniform per-minute array.
        """
        arr = np.zeros(self.T_end)
        if not raw:
            return arr
        raw_sorted = sorted(raw, key=lambda x: x[0])
        prev_t, prev_kw = 0, 0.0
        for t, kw in raw_sorted:
            t_idx = int(t)
            p_idx = int(prev_t)
            if t_idx > p_idx:
                arr[p_idx:min(t_idx, self.T_end)] = prev_kw
            prev_t, prev_kw = t, kw
        # fill tail
        arr[int(prev_t):] = prev_kw
        return arr

    def _to_15min(self, minute_arr: np.ndarray) -> np.ndarray:
        """Average per-minute array into 15-minute slots."""
        n_slots = self.T_end // 15
        out = np.zeros(n_slots)
        for i in range(n_slots):
            out[i] = np.mean(minute_arr[i * 15:(i + 1) * 15])
        return out


# ── Public factory / convenience function ────────────────────────────────────

def build_stations_cfg(
    num_stations: int,
    chargers_per_station: int,
    charger_power_kw: float,
    charger_type: str = "fast",
) -> List[Dict]:
    """Generate a uniform station configuration for the UI."""
    cfg = []
    for i in range(num_stations):
        angle = 2 * math.pi * i / max(num_stations, 1)
        cfg.append({
            "id": i,
            "location": (math.cos(angle), math.sin(angle)),
            "chargers": [
                {"type": charger_type, "power_kw": charger_power_kw}
                for _ in range(chargers_per_station)
            ],
        })
    return cfg


def run_ev_simulation(
    max_demand: int,
    demand_curve: np.ndarray,
    num_stations: int,
    chargers_per_station: int,
    charger_power_kw: float,
    battery_kwh: float,
    charger_type: str = "fast",
    n_home_evs: int = 0,
    home_power_kw: float = 3.3,
    random_seed: int = 42,
) -> Dict:
    """
    High-level entrypoint matching the original run_simulation() signature
    so app.py can swap in with minimal changes.

    demand_curve : normalized shape (96,) — 15-min slots
    Returns      : same keys as original, plus ev-level metrics
    """
    # expand 96-slot curve → per-minute λ(t)
    lam_per_slot = demand_curve * max_demand        # arrivals per 15-min slot
    lam_per_min  = lam_per_slot / 15.0             # arrivals per minute
    # upsample 96 slots → 1440 minutes
    lam_per_min_full = np.repeat(lam_per_min, 15)  # (1440,)

    stations_cfg = build_stations_cfg(
        num_stations, chargers_per_station, charger_power_kw, charger_type
    )

    sim = EVChargingSimulation(
        demand_curve_per_min=lam_per_min_full,
        stations_cfg=stations_cfg,
        battery_kwh=battery_kwh,
        n_home_evs=n_home_evs,
        home_power_kw=home_power_kw,
        random_seed=random_seed,
    )

    results = sim.run()

    # backward-compat fields
    results["e_battery_kwh"]      = round(battery_kwh * 0.8, 2)
    results["charge_duration_min"] = round(charging_time_fast(
        EV(0, 0.0, 0.2, battery_kwh=battery_kwh), charger_power_kw
    ), 1) if charger_type == "fast" else round(
        charging_time_slow(EV(0, 0.0, 0.2, battery_kwh=battery_kwh), charger_power_kw), 1
    )
    results["total_dropped_pct"] = round(
        100 * results["total_dropped"] / max(1, results["total_arrived"]), 1
    )

    return results
