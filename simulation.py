"""
City-Level EV Battery EV Charging Load Engine
================================================
Demand  →  Queue  →  Charging  →  Load (kW) + Energy (kWh)

Mathematical Model
------------------
  Demand  : N_i(t) ~ Poisson(λ_city(t) · w_i),  w_i = 1/M (equal station weights)
  Queue   : M/M/c/K per station  (c = chargers, K = queue_mult · c)
  Charging: E_battery = 0.8 · E_max,  T_charge = E_battery / P_charger
  Load    : L(t) = N_active(t) · P_charger
  Energy  : E_total = Σ L(t) · Δt,  Δt = 0.25 hr
"""

import math
import numpy as np
import pandas as pd
from pathlib import Path


def get_data_path(filename: str) -> str:
    return str(Path(__file__).parent / filename)


def load_demand_curve() -> np.ndarray:
    """
    Load a typical 24-hour normalized demand profile from full_dataset.csv.
    Aggregates over all days by hour, then upsamples to 96 × 15-min slots
    via linear interpolation. Returns array of shape (96,) in [0, 1].
    """
    try:
        df = pd.read_csv(get_data_path("full_dataset.csv"))
        hourly = df.groupby("hour")["normalized_demand"].mean().sort_index().values  # 24 values

        # Upsample 24 hourly → 96 quarter-hourly via linear interpolation
        x_hr = np.arange(24) + 0.5             # hour midpoints
        x_qt = np.linspace(0, 24, 96, endpoint=False) + 0.125  # quarter-hour midpoints
        curve = np.interp(x_qt, x_hr, hourly)
        return curve / curve.max()

    except Exception:
        # Fallback: synthetic dual-peak curve (morning + evening)
        t = np.linspace(0, 24, 96, endpoint=False)
        curve = (
            0.25
            + 0.55 * np.exp(-((t - 8.5) ** 2) / 3)
            + 0.75 * np.exp(-((t - 18.5) ** 2) / 2.5)
        )
        return curve / curve.max()


def generate_simulation_curve(morning_peak: float, evening_peak: float) -> np.ndarray:
    """
    Generates a demand curve (EVs per 15-min slot) by scaling the historic
    profile to hit non-normalized absolute morning and evening peaks.
    
    Morning window: 05:00 - 14:00 (slots 20 - 56)
    Evening window: 14:00 - 05:00 (slots 56 - 20)
    """
    base_curve = load_demand_curve()
    
    # 1. Identify current peak indices in normalized curve
    # Values represent mid-points of typical rush hours
    # slot 34 = 08:30, slot 74 = 18:30
    current_m_peak = np.max(base_curve[20:56])
    current_e_peak = np.max(base_curve[56:88])
    
    # 2. Create scaling mask
    # We use a sigmoid-like transition at 2 PM (slot 56) to smoothly switch 
    # between morning and evening scaling factors
    t = np.arange(96)
    transition = 1 / (1 + np.exp(-0.5 * (t - 56)))
    
    m_scale = morning_peak / current_m_peak if current_m_peak > 0 else 0
    e_scale = evening_peak / current_e_peak if current_e_peak > 0 else 0
    
    scales = m_scale * (1 - transition) + e_scale * transition
    
    return base_curve * scales


def run_simulation(
    max_demand: int,
    demand_curve: np.ndarray,
    num_stations: int,
    chargers_per_station: int,
    charger_power_kw: float,
    battery_kwh: float,
    queue_multiplier: int = 2,
    random_seed: int = 42,
) -> dict:
    """
    Discrete-event M/M/c/K charging load simulation at 15-min resolution.

    Parameters
    ----------
    max_demand            : Peak city-level EV arrivals per 15-min interval
    demand_curve          : Normalized shape array, 96 values in [0, 1]
    num_stations          : Number of EVping stations (M)
    chargers_per_station  : Chargers per station (c)
    charger_power_kw      : Power per charger in kW (P)
    battery_kwh           : Full battery capacity in kWh (E_max)
    queue_multiplier      : Queue capacity K = queue_multiplier × c
    random_seed           : RNG seed for reproducibility

    Returns
    -------
    dict with keys:
        load_curve         : list[float], 96 load values in kW
        total_kwh          : float, total daily energy consumed
        peak_kw            : float, maximum load
        avg_kw             : float, average load
        load_factor        : float, avg / peak
        utilization_pct    : float, avg load as % of installed capacity
        t_charge_hr        : float, charging time per battery (hours)
        charge_duration_min: float, charging time in minutes
        e_battery_kwh      : float, energy delivered per battery (kWh)
        total_served       : int, total batteries charged in the day
        total_dropped      : int, total arrivals dropped (queue full)
    """
    rng = np.random.default_rng(random_seed)

    # ── Derived charging parameters ──────────────────────────────────────────
    e_battery = 0.8 * battery_kwh                       # kWh  (80% SoC cutoff)
    t_charge_hr = e_battery / charger_power_kw           # hours
    t_charge_slots = t_charge_hr * 4                     # 15-min slots
    charge_duration = max(1, math.ceil(t_charge_slots))  # integer slots

    # ── Queue parameters ─────────────────────────────────────────────────────
    c = chargers_per_station
    K = queue_multiplier * c   # max queue depth per station
    w = 1.0 / num_stations     # equal demand weight across stations

    # ── City arrivals per 15-min slot ────────────────────────────────────────
    city_lambda = demand_curve * max_demand   # expected arrivals / slot

    # ── Station state ────────────────────────────────────────────────────────
    # 'chargers': list of finish_slots for batteries currently charging
    # 'queue'   : integer count of waiting batteries
    stations = [{"chargers": [], "queue": 0} for _ in range(num_stations)]

    load_curve_kw = np.zeros(96)
    total_served  = 0
    total_dropped = 0

    for t in range(96):

        # 1. Free chargers whose batteries have finished; pull from queue ─────
        for st in stations:
            st["chargers"] = [f for f in st["chargers"] if f > t]
            freed = c - len(st["chargers"])
            if freed > 0 and st["queue"] > 0:
                to_start = min(freed, st["queue"])
                st["queue"] -= to_start
                total_served += to_start
                for _ in range(to_start):
                    st["chargers"].append(t + charge_duration)

        # 2. Sample Poisson arrivals for this slot ────────────────────────────
        arrivals_per_station = rng.poisson(city_lambda[t] * w, num_stations)

        # 3. Route arrivals via M/M/c/K logic ─────────────────────────────────
        for i, n_arrivals in enumerate(arrivals_per_station):
            st = stations[i]
            for _ in range(int(n_arrivals)):
                if len(st["chargers"]) < c:
                    # Charger free → start immediately
                    st["chargers"].append(t + charge_duration)
                    total_served += 1
                elif st["queue"] < K:
                    # Join queue
                    st["queue"] += 1
                else:
                    # Queue full → drop
                    total_dropped += 1

        # 4. Snapshot load ─────────────────────────────────────────────────────
        active = sum(len(st["chargers"]) for st in stations)
        load_curve_kw[t] = active * charger_power_kw

    # ── Aggregate metrics ────────────────────────────────────────────────────
    total_kwh       = float(np.sum(load_curve_kw) * 0.25)
    peak_kw         = float(np.max(load_curve_kw))
    avg_kw          = float(np.mean(load_curve_kw))
    load_factor     = float(avg_kw / peak_kw) if peak_kw > 0 else 0.0
    max_cap_kw      = num_stations * c * charger_power_kw
    utilization_pct = float((avg_kw / max_cap_kw) * 100) if max_cap_kw > 0 else 0.0

    return {
        "load_curve":          load_curve_kw.tolist(),
        "total_kwh":           round(total_kwh, 1),
        "peak_kw":             round(peak_kw, 1),
        "avg_kw":              round(avg_kw, 1),
        "load_factor":         round(load_factor, 4),
        "utilization_pct":     round(utilization_pct, 1),
        "t_charge_hr":         round(t_charge_hr, 3),
        "charge_duration_min": round(t_charge_hr * 60, 1),
        "e_battery_kwh":       round(e_battery, 2),
        "total_served":        total_served,
        "total_dropped":       total_dropped,
    }
