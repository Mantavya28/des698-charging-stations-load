"""
SimPy Battery Simulation Module (Timer-Based)
==============================================
Simulates battery states (charged, depleted, charging) per minute for each station.

Key Parameters:
- Charging time: 0% to 100% = 180 minutes
- Depleted batteries arrive at 15% SOC (need 153 min to reach 100%)
- Timer t = time remaining to full charge
- Emergency interrupt: Pull batteries at 90%+ (t <= 18 min) when no charged batteries available

Conservation: b_total = b_charging + b_charged + b_depleted
"""

import simpy
import pandas as pd
import numpy as np
import json
from pathlib import Path
from collections import defaultdict



# Helper function for path resolution
def get_data_path(filename):
    """Get absolute path to data file, compatible with Streamlit Cloud."""
    base_dir = Path(__file__).parent
    return str(base_dir / filename)

def load_stations_from_csv(filename='stations_jsons.csv'):
    """Load stations from CSV file."""
    try:
        path = get_data_path(filename)
        df = pd.read_csv(path)
        # Ensure correct types
        return df.to_dict('records')
    except Exception as e:
        print(f"Error loading {filename}: {e}")
        return []


class Battery:
    """Represents a single battery with timer-based charging state."""
    def __init__(self, battery_id, initial_soc=100.0):
        self.id = battery_id
        self.soc = initial_soc  # State of Charge (0-100%)
        
        # Timer: minutes remaining to 100% charge
        # 0% -> 100% = 180 min, so timer = (100 - soc) * 1.8
        self.timer = self._calculate_timer(initial_soc)
        
        # State: 'charged', 'charging', 'depleted'
        if initial_soc >= 100.0:
            self.state = 'charged'
            self.timer = 0
        elif self.timer > 0:
            self.state = 'charging'
        else:
            self.state = 'depleted'
    
    def _calculate_timer(self, soc):
        """Calculate timer (minutes to full charge) from SOC."""
        # 0% -> 100% takes 180 minutes
        # Timer = (100 - SOC) * 1.8
        return max(0, (100.0 - soc) * 1.8)
    
    def get_soc_from_timer(self):
        """Calculate current SOC from timer."""
        # SOC = 100 - (timer / 1.8)
        return max(0, 100.0 - (self.timer / 1.8))
    
    def __repr__(self):
        return f"Battery({self.id}, t={self.timer:.0f}min, {self.state})"


class Station:
    """
    Represents a swap station with timer-based battery management.
    
    Uses timers instead of SOC for charging simulation:
    - Timer decrements by 1 each minute while charging
    - t <= 0: Battery is fully charged (100%)
    - t <= 18: Battery is at 90%+ (eligible for emergency interrupt)
    """
    def __init__(self, env, station_id, name, num_chargers, total_batteries):
        self.env = env
        self.station_id = station_id
        self.name = name
        self.num_chargers = num_chargers
        self.total_batteries = total_batteries
        
        # Timer thresholds
        self.FULL_CHARGE_TIMER = 0      # t <= 0 means 100%
        self.EMERGENCY_THRESHOLD = 18   # t <= 18 means 90%+
        
        # Timer for depleted batteries (15% SOC = 85% to charge = 153 min)
        self.DEPLETED_TIMER = int((100.0 - 15.0) * 1.8)  # 153 minutes
        
        # Battery pools
        self.charged_batteries = []      # Ready to swap (100% SOC, t=0)
        self.charging_batteries = []     # Currently charging (has timer)
        self.depleted_batteries = []     # Waiting for charger slot
        
        # Initialize all batteries as charged
        for i in range(total_batteries):
            battery = Battery(f"{station_id}_B{i:03d}", initial_soc=100.0)
            battery.state = 'charged'
            battery.timer = 0
            self.charged_batteries.append(battery)
        
        # Statistics tracking
        self.stats = {
            'hourly_demand': [],
            'hourly_satisfied': [],
            'hourly_lost': [],
            'hourly_emergency_used': [],  # Track emergency interrupts
            'hourly_wait_times': [],      # Wait time per hour
            'hourly_lost_swap_count': [], # Lost swap count per hour (new formula)
            'minute_snapshots': []
        }
        
        # Track emergency uses
        self.current_hour_emergency = 0
    
    def get_state_counts(self):
        """Return current battery state counts."""
        return {
            'charged': len(self.charged_batteries),
            'charging': len(self.charging_batteries),
            'depleted': len(self.depleted_batteries),
            'total': len(self.charged_batteries) + len(self.charging_batteries) + len(self.depleted_batteries)
        }
    
    def calculate_wait_time(self, demand):
        """
        Calculate wait time based on battery availability.
        
        Logic:
        1. Available = Fully Charged + Charging (SOC >= 90%, i.e. t <= 18)
        2. If Available >= Demand: Wait = 0
        3. If Short: Wait = Time for battery closest to 90% to reach 90%
        
        Returns: wait_time in minutes
        """
        # Count available batteries
        fully_charged = len(self.charged_batteries)
        charging_90_plus = sum(1 for b in self.charging_batteries if b.timer <= self.EMERGENCY_THRESHOLD)
        available = fully_charged + charging_90_plus
        
        if available >= demand:
            return 0
        
        # We're short - find battery closest to 90% (smallest timer > 18)
        batteries_below_90 = [b for b in self.charging_batteries if b.timer > self.EMERGENCY_THRESHOLD]
        
        if not batteries_below_90:
            # No batteries below 90% charging, check depleted pool
            if self.depleted_batteries:
                # Depleted batteries need full charging time to 90%
                # 90% = 10% remaining to charge = 18 min from 90% to 100%
                # So time to reach 90% from 15% = 153 - 18 = 135 min
                return 135
            return 0  # No batteries available at all
        
        # Sort by timer ascending (closest to 90% first)
        batteries_below_90.sort(key=lambda b: b.timer)
        
        # Wait time = time for closest battery to reach 90% (t <= 18)
        closest = batteries_below_90[0]
        wait_time = closest.timer - self.EMERGENCY_THRESHOLD
        
        return max(0, wait_time)
    
    def calculate_lost_swap(self, demand):
        """
        Calculate lost swaps based on new formula.
        
        Lost Swaps = max(0, (Demand - Supply) - Batteries_within_30min)
        Where:
        - Supply = b_charged (fully charged batteries)
        - Batteries_within_30min = batteries that can reach 90% within 30 minutes
          (i.e., timer <= 18 + 30 = 48 minutes)
        
        Returns: lost swap count
        """
        supply = len(self.charged_batteries)
        shortfall = demand - supply
        
        if shortfall <= 0:
            return 0
        
        # Batteries that can reach 90% within 30 mins
        # 90% means timer <= 18, so within 30 mins means current timer <= 18 + 30 = 48
        batteries_within_30min = sum(
            1 for b in self.charging_batteries 
            if b.timer <= self.EMERGENCY_THRESHOLD + 30
        )
        
        lost = shortfall - batteries_within_30min
        return max(0, lost)
    
    def process_swap_demand(self, demand):
        """
        Process swap demand at the start of hour.
        
        Priority:
        1. Use fully charged batteries (b_charged)
        2. If demand > b_charged and b_charged == 0, use emergency interrupt
        3. Any remaining demand is lost
        
        Returns: (satisfied, lost)
        """
        satisfied = 0
        lost = 0
        remaining_demand = demand
        self.current_hour_emergency = 0
        
        # Step 1: Satisfy from fully charged pool
        from_charged = min(remaining_demand, len(self.charged_batteries))
        for _ in range(from_charged):
            given_battery = self.charged_batteries.pop(0)
            # Battery comes back depleted at 15% SOC
            given_battery.soc = 15.0
            given_battery.timer = self.DEPLETED_TIMER
            given_battery.state = 'depleted'
            self.depleted_batteries.append(given_battery)
            satisfied += 1
            remaining_demand -= 1
        
        # Step 2: Emergency interrupt - only if demand still not met AND no charged batteries left
        if remaining_demand > 0 and len(self.charged_batteries) == 0:
            # Look for batteries at 90%+ (t <= 18)
            # Sort charging batteries by timer (lowest first = most charged)
            self.charging_batteries.sort(key=lambda b: b.timer)
            
            # Pull eligible batteries (t <= 18) to b_charged first
            still_charging = []
            for battery in self.charging_batteries:
                if battery.timer <= self.EMERGENCY_THRESHOLD:
                    # Move from charging → charged (plug out from charger)
                    battery.soc = battery.get_soc_from_timer()
                    battery.timer = 0
                    battery.state = 'charged'
                    self.charged_batteries.append(battery)
                    self.current_hour_emergency += 1
                else:
                    still_charging.append(battery)
            
            self.charging_batteries = still_charging
            
            # Now satisfy remaining demand from newly available charged batteries
            from_emergency = min(remaining_demand, len(self.charged_batteries))
            for _ in range(from_emergency):
                given_battery = self.charged_batteries.pop(0)
                # Battery comes back depleted at 15% SOC
                given_battery.soc = 15.0
                given_battery.timer = self.DEPLETED_TIMER
                given_battery.state = 'depleted'
                self.depleted_batteries.append(given_battery)
                satisfied += 1
                remaining_demand -= 1
        
        # Remaining demand is lost
        lost = remaining_demand
        
        # Record stats
        self.stats['hourly_demand'].append(demand)
        self.stats['hourly_satisfied'].append(satisfied)
        self.stats['hourly_lost'].append(lost)
        self.stats['hourly_emergency_used'].append(self.current_hour_emergency)
        
        # Calculate and record lost swap using new formula (before demand was served)
        # We need to calculate this based on initial state, so we add back satisfied
        initial_charged = len(self.charged_batteries) + satisfied
        initial_shortfall = demand - initial_charged
        if initial_shortfall > 0:
            # Count batteries that could reach 90% within 30 min at start of hour
            batteries_30min = sum(
                1 for b in self.charging_batteries 
                if b.timer <= self.EMERGENCY_THRESHOLD + 30
            )
            lost_swap_new = max(0, initial_shortfall - batteries_30min - self.current_hour_emergency)
        else:
            lost_swap_new = 0
        self.stats['hourly_lost_swap_count'].append(lost_swap_new)
        
        # Calculate and record wait time for this hour
        # Wait time is calculated AFTER serving demand to reflect system state
        wait_time = self.calculate_wait_time(1)  # Check for hypothetical next demand
        self.stats['hourly_wait_times'].append(wait_time)
        
        return satisfied, lost
    
    def charge_step(self):
        """
        Execute one minute of charging simulation using timers.
        
        1. Fill charger slots from depleted pool
        2. Decrement all charging timers by 1
        3. Move batteries with t <= 0 to charged pool
        """
        # 1. Fill charger slots from depleted pool
        while len(self.charging_batteries) < self.num_chargers and len(self.depleted_batteries) > 0:
            battery = self.depleted_batteries.pop(0)
            battery.state = 'charging'
            self.charging_batteries.append(battery)
        
        # 2. Decrement timers and check for completion
        still_charging = []
        for battery in self.charging_batteries:
            battery.timer -= 1  # Advance time by 1 minute
            
            if battery.timer <= self.FULL_CHARGE_TIMER:
                # Battery is fully charged
                battery.timer = 0
                battery.soc = 100.0
                battery.state = 'charged'
                self.charged_batteries.append(battery)
            else:
                battery.soc = battery.get_soc_from_timer()
                still_charging.append(battery)
        
        self.charging_batteries = still_charging
    
    def record_snapshot(self, minute):
        """Record current state for analysis."""
        state = self.get_state_counts()
        state['minute'] = minute
        state['hour'] = minute // 60
        
        # Calculate charger utilization: (B_charging / total_chargers) * 100
        state['charger_utilization'] = (len(self.charging_batteries) / self.num_chargers) * 100 if self.num_chargers > 0 else 0
        
        # Also track average timer of charging batteries
        if self.charging_batteries:
            state['avg_charging_timer'] = sum(b.timer for b in self.charging_batteries) / len(self.charging_batteries)
        else:
            state['avg_charging_timer'] = 0
            
        self.stats['minute_snapshots'].append(state)


class BatterySimulation:
    """
    Main simulation controller.
    Runs SimPy simulation across all stations using demand from dataset.
    """
    def __init__(self, demand_file='full_dataset.csv', days=7, stations_data=None, custom_demand_df=None):
        self.days = days
        self.total_minutes = days * 24 * 60  # Total simulation time in minutes
        
        # Load station config
        if stations_data is not None:
            self.station_configs = stations_data
        else:
            # Load from CSV
            self.station_configs = load_stations_from_csv()
        
        # Load demand data
        if custom_demand_df is not None:
            self.demand_df = custom_demand_df
        else:
            demand_path = get_data_path(demand_file)
            self.demand_df = pd.read_csv(demand_path)
        
        # Only use first N days (N*24 rows)
        self.demand_df = self.demand_df.head(days * 24)
        
        # Map station IDs to demand columns
        self.station_demand_cols = {}
        for s in self.station_configs:
            sid = s['id']
            col_name = f"{sid}_demand"
            if col_name in self.demand_df.columns:
                self.station_demand_cols[sid] = col_name
            else:
                self.station_demand_cols[sid] = None
        
        # SimPy environment
        self.env = simpy.Environment()
        
        # Create station objects
        self.stations = {}
        for s in self.station_configs:
            station = Station(
                env=self.env,
                station_id=s['id'],
                name=s['name'],
                num_chargers=s['chargers'],
                total_batteries=s['inventory_cap']
            )
            self.stations[s['id']] = station
        
        # Results storage
        self.results = {}
    
    def get_hourly_demand(self, station_id, hour_index):
        """Get demand for a station at a specific hour."""
        if hour_index >= len(self.demand_df):
            return 0
        
        col = self.station_demand_cols.get(station_id)
        if col and col in self.demand_df.columns:
            return int(self.demand_df.iloc[hour_index][col])
        else:
            total = self.demand_df.iloc[hour_index]['delhi_demand']
            n_stations = len(self.stations)
            return int(total / n_stations)
    

    
    def station_process(self, station):
        """
        SimPy process for a single station.
        Runs the per-minute simulation loop.
        """
        for minute in range(self.total_minutes):
            hour_index = minute // 60
            minute_in_hour = minute % 60
            
            # At the start of each hour (minute 0), process swap demand
            if minute_in_hour == 0:
                demand = self.get_hourly_demand(station.station_id, hour_index)
                station.process_swap_demand(demand)
            
            # Execute charging step (every minute)
            station.charge_step()
            
            # Record state snapshot (every minute)
            station.record_snapshot(minute)
            
            # Yield for 1 minute
            yield self.env.timeout(1)
    
    def start_processes(self):
        """Initialize station processes."""
        for station in self.stations.values():
            self.env.process(self.station_process(station))
            
    def run_until(self, minutes):
        """Run simulation until specific time (minutes)."""
        if not self.env._queue: 
             self.start_processes()
        
        self.env.run(until=minutes)

    def run(self):
        """Run the full simulation."""
        print(f"Starting SimPy Battery Simulation (Timer-Based)...")
        print(f"  Duration: {self.days} days ({self.total_minutes} minutes)")
        print(f"  Stations: {len(self.stations)}")
        print(f"  Emergency threshold: 90% (t <= 18 min)")
        
        # Start station processes
        self.start_processes()
        
        # Run simulation
        self.env.run(until=self.total_minutes)
        
        print("Simulation complete!")
        
        # Compile results
        self.compile_results()
        
        return self.results
    
    def compile_results(self):
        """Compile simulation results into structured format."""
        for sid, station in self.stations.items():
            snapshots_df = pd.DataFrame(station.stats['minute_snapshots'])
            
            hourly_stats = snapshots_df.groupby('hour').agg({
                'charged': 'mean',
                'charging': 'mean',
                'depleted': 'mean'
            }).round(2)
            
            total_emergency = sum(station.stats['hourly_emergency_used'])
            avg_wait_time = sum(station.stats['hourly_wait_times']) / max(1, len(station.stats['hourly_wait_times']))
            
            self.results[sid] = {
                'name': station.name,
                'total_batteries': station.total_batteries,
                'num_chargers': station.num_chargers,
                'total_demand': sum(station.stats['hourly_demand']),
                'total_satisfied': sum(station.stats['hourly_satisfied']),
                'total_lost': sum(station.stats['hourly_lost']),
                'total_emergency_used': total_emergency,
                'avg_wait_time': round(avg_wait_time, 2),
                'lost_percentage': (sum(station.stats['hourly_lost']) / max(1, sum(station.stats['hourly_demand']))) * 100,
                'hourly_demand': station.stats['hourly_demand'],
                'hourly_satisfied': station.stats['hourly_satisfied'],
                'hourly_lost': station.stats['hourly_lost'],
                'hourly_emergency_used': station.stats['hourly_emergency_used'],
                'hourly_wait_times': station.stats['hourly_wait_times'],
                'hourly_lost_swap_count': station.stats['hourly_lost_swap_count'],
                'minute_snapshots': snapshots_df.to_dict('records'),
                'hourly_avg_states': hourly_stats.to_dict('index')
            }
    
    def save_results(self, output_file='simulation_results.json'):
        """Save results to JSON file."""
        output = {}
        for sid, data in self.results.items():
            output[sid] = {
                'name': data['name'],
                'total_batteries': data['total_batteries'],
                'num_chargers': data['num_chargers'],
                'total_demand': data['total_demand'],
                'total_satisfied': data['total_satisfied'],
                'total_lost': data['total_lost'],
                'total_emergency_used': data['total_emergency_used'],
                'lost_percentage': round(data['lost_percentage'], 2),
                'hourly_demand': data['hourly_demand'],
                'hourly_satisfied': data['hourly_satisfied'],
                'hourly_lost': data['hourly_lost'],
                'hourly_emergency_used': data['hourly_emergency_used']
            }
        
        output_path = get_data_path(output_file)
        with open(output_path, 'w') as f:
            json.dump(output, f, indent=2)
        
        print(f"Results saved to {output_file}")
    
    def print_summary(self):
        """Print summary of simulation results."""
        print("\n" + "="*70)
        print("SIMULATION SUMMARY (TIMER-BASED WITH EMERGENCY INTERRUPT)")
        print("="*70)
        
        total_demand = 0
        total_satisfied = 0
        total_lost = 0
        total_emergency = 0
        
        for sid, data in self.results.items():
            print(f"\n{data['name']} ({sid}):")
            print(f"  Batteries: {data['total_batteries']}, Chargers: {data['num_chargers']}")
            print(f"  Total Demand: {data['total_demand']}")
            print(f"  Satisfied: {data['total_satisfied']} ({100*data['total_satisfied']/max(1,data['total_demand']):.1f}%)")
            print(f"  Lost: {data['total_lost']} ({data['lost_percentage']:.2f}%)")
            print(f"  Emergency Interrupts: {data['total_emergency_used']}")
            print(f"  Avg Wait Time: {data['avg_wait_time']:.2f} min")
            
            total_demand += data['total_demand']
            total_satisfied += data['total_satisfied']
            total_lost += data['total_lost']
            total_emergency += data['total_emergency_used']
        
        print("\n" + "-"*70)
        print("OVERALL TOTALS:")
        print(f"  Total Demand: {total_demand}")
        print(f"  Total Satisfied: {total_satisfied} ({100*total_satisfied/max(1,total_demand):.1f}%)")
        print(f"  Total Lost: {total_lost} ({100*total_lost/max(1,total_demand):.2f}%)")
        print(f"  Total Emergency Interrupts: {total_emergency}")
        print("="*70)
    
    def get_day7_avg_wait_time(self):
        """
        Get the average wait time for Day 7 (last day) across all stations.
        Calculation: sum of station Day7 averages / number of stations
        Returns the average in minutes.
        """
        station_day7_avgs = []
        for sid, data in self.results.items():
            # Day 7 = hours 144-167 (indices 144-167)
            if len(data['hourly_wait_times']) >= 168:
                day7_waits = data['hourly_wait_times'][144:168]
                station_avg = sum(day7_waits) / len(day7_waits) if day7_waits else 0
                station_day7_avgs.append(station_avg)
        
        if station_day7_avgs:
            # Average of station averages
            return round(sum(station_day7_avgs) / len(station_day7_avgs), 2)
        return 0.0
    
    def get_day7_lost_swap_percentage(self):
        """
        Get the total lost swap % for Day 7 (last day) across all stations.
        
        Formula: sum(lost_swap_count across all stations for Day 7) / 
                 sum(demand across all stations for Day 7) * 100
        
        Returns: lost swap percentage
        """
        total_lost_swap = 0
        total_demand = 0
        
        for sid, data in self.results.items():
            # Day 7 = hours 144-167 (indices 144-167)
            if len(data['hourly_lost_swap_count']) >= 168 and len(data['hourly_demand']) >= 168:
                day7_lost = data['hourly_lost_swap_count'][144:168]
                day7_demand = data['hourly_demand'][144:168]
                total_lost_swap += sum(day7_lost)
                total_demand += sum(day7_demand)
        
        if total_demand > 0:
            return round((total_lost_swap / total_demand) * 100, 2)
        return 0.0
    
    def get_day7_charger_utilization(self):
        """
        Get the average charger utilization for Day 7 (last day) across all stations.
        
        Formula: Average of (B_charging / total_chargers * 100) per minute for Day 7
        Then average across all stations.
        
        Returns: utilization percentage
        """
        station_day7_utils = []
        
        for sid, data in self.results.items():
            snapshots = data.get('minute_snapshots', [])
            
            # Day 7 minutes = 144*60 to 168*60 = 8640 to 10080
            day7_start_min = 144 * 60
            day7_end_min = 168 * 60
            
            day7_utils = [
                s['charger_utilization'] 
                for s in snapshots 
                if day7_start_min <= s['minute'] < day7_end_min and 'charger_utilization' in s
            ]
            
            if day7_utils:
                station_avg = sum(day7_utils) / len(day7_utils)
                station_day7_utils.append(station_avg)
        
        if station_day7_utils:
            return round(sum(station_day7_utils) / len(station_day7_utils), 2)
        return 0.0

    
    def get_day7_total_cost(self):
        """
        Calculate total cost per hour for Day 7 (last day) across all stations.
        
        Formula: Cost = (alpha * chargers) + (beta * wait_time_mins * demand) + (gamma * lost_swaps)
        But simplified for aggregated metrics:
        Cost/hr = (alpha * total_chargers) + 
                  (beta * total_day7_wait_mins / 24) + 
                  (gamma * total_day7_lost_swaps / 24)
                  
        Coefficients:
        alpha = 1000 (Fixed cost/hr/charger)
        beta = 50    (Wait cost/min)
        gamma = 200  (Lost swap cost/swap)
        
        Returns: average cost per hour (₹)
        """
        alpha = 1000
        beta = 50
        gamma = 200
        
        total_chargers = 0
        total_day7_wait_mins_accumulated = 0 # sum of (avg_wait_time * demand) for each hour
        total_day7_lost_swaps = 0
        
        for sid, data in self.results.items():
            total_chargers += data['num_chargers']
            
            if len(data['hourly_demand']) >= 168 and len(data['hourly_wait_times']) >= 168:
                # Day 7 = hours 144-167
                day7_demand = data['hourly_demand'][144:168]
                day7_wait = data['hourly_wait_times'][144:168]
                day7_lost = data['hourly_lost_swap_count'][144:168]
                
                # Calculate accumulated wait minutes (Wait * Demand) for each hour
                wait_mins = sum(w * d for w, d in zip(day7_wait, day7_demand))
                total_day7_wait_mins_accumulated += wait_mins
                
                total_day7_lost_swaps += sum(day7_lost)
        
        # Calculate hourly rates
        # Fixed cost is per hour already (alpha * chargers)
        fixed_cost = alpha * total_chargers
        
        # Variable costs need to be averaged over 24 hours
        wait_cost = (beta * total_day7_wait_mins_accumulated) / 24
        lost_cost = (gamma * total_day7_lost_swaps) / 24
        
        total_hourly_cost = fixed_cost + wait_cost + lost_cost
        return round(total_hourly_cost, 2)

    def get_day7_results_dict(self):
        """
        Get all Day 7 KPIs in a dictionary.
        Used for Scenario Analysis to ensure apples-to-apples comparison with baseline.
        """
        avg_wait = self.get_day7_avg_wait_time()
        
        # Lost Swap %
        # Formula: (Total Lost Day 7 / Total Demand Day 7) * 100
        total_lost_day7 = 0
        total_demand_day7 = 0
        for sid, data in self.results.items():
            if len(data['hourly_demand']) >= 168:
                total_demand_day7 += sum(data['hourly_demand'][144:168])
                total_lost_day7 += sum(data['hourly_lost_swap_count'][144:168])
        
        lost_pct = (total_lost_day7 / total_demand_day7 * 100) if total_demand_day7 > 0 else 0
        
        utilization = self.get_day7_charger_utilization()
        cost = self.get_day7_total_cost()
        idle_inv = 100 - utilization
        
        return {
            'avg_wait': round(avg_wait, 2),
            'lost_swaps': round(lost_pct, 2),
            'idle_inventory': round(idle_inv, 2),
            'utilization': round(utilization, 2),
            'cost': round(cost, 2)
        }


    def get_aggregated_kpis(self):
        """
        Calculate aggregated KPIs for the entire simulation duration.
        Returns a dictionary compatible with the dashboard requirements.
        """
        total_wait_mins = 0
        total_demand = 0
        total_lost_swaps = 0
        total_chargers = 0
        total_util_points = 0
        total_util_count = 0
        
        # Coefficients for cost
        alpha = 1000
        beta = 50
        gamma = 200
        
        hours_simulated = self.total_minutes / 60
        
        for sid, data in self.results.items():
            total_chargers += data['num_chargers']
            
            # Demand and Wait
            # hourly_wait_times is average wait per minute for that hour
            # We need weighted average by demand? Or just average?
            # Dashboard baseline uses "sum of averages / stations" or weighted?
            # Baseline uses get_day7_wait_time -> sum(station_avgs) / n_stations.
            # But specific station avg is sum(wait)/count.
            # Let's assume hourly_wait_times is true average.
            
            demands = data['hourly_demand']
            waits = data['hourly_wait_times']
            losts = data['hourly_lost_swap_count']
            
            # Limit to actual data length
            n = min(len(demands), len(waits), len(losts))
            
            # Total demand for this station
            st_demand = sum(demands[:n])
            total_demand += st_demand
            
            # Weighted wait time (Total wait minutes)
            # wait[h] is avg wait for hour h. Approximated as wait[h] * demand[h]
            st_wait_mins = sum(w * d for w, d in zip(waits[:n], demands[:n]))
            total_wait_mins += st_wait_mins
            
            # Total lost
            total_lost_swaps += sum(losts[:n])
            
            # Utilization (average % over time)
            # hourly_utilization or minute snapshots?
            # We have get_day7_charger_utilization logic.
            # Let's use minute_snapshots if possible, but results dict might not have it aggregated?
            # results has 'charger_utilization' maybe? 
            # save_results() puts 'hourly_wait_times', 'hourly_demand', 'hourly_lost_swap_count'.
            # It does NOT put hourly utilization in the results dict by default in compile_results().
            
            # Check compile_results:
            # hourly_stats = ...
            # self.results[sid] = { ... 'hourly_wait_times': ... }
            # It does not seem to export utilization series.
            # But the simulation instance has self.stations[sid].stats['minute_snapshots']
            
            # So we should access self.stations directly for utilization if possible, or update compile_results.
            # Since we are inside the class, we can access self.stations.
            
            station = self.stations[sid]
            snapshots = station.stats['minute_snapshots']
            
            # Average utilization for this station
            # Utilization = (charging / chargers) * 100
            
            # We want network average utilization?
            # Network Util = (Sum Charging / Sum Chargers) * 100
            # OR Average of Station Utilizations?
            # get_day7_charger_utilization does: Avg of (B_charging / total_chargers * 100) per minute, then Avg across stations.
            
            # Let's stick to network-wide average utilization.
            # But for "Avg of Station Utils" approach:
            
            # Let's calculate utilization from snapshots for the duration
            utils = [s['charger_utilization'] for s in snapshots]
            if utils:
                total_util_points += sum(utils)
                total_util_count += len(utils)

        # KPIs
        
        # 1. Avg Wait Time (Weighted by demand across network)
        # Baseline uses simple average of station averages, but weighted is more accurate for "System Wait".
        # Let's match Baseline: get_day7_avg_wait_time -> sum(st_avg) / N.
        # st_avg = sum(wait * demand) / sum(demand) for that station.
        
        # Let's calculate per-station avg wait, then average them.
        st_avg_waits = []
        for sid, data in self.results.items():
            demands = data['hourly_demand']
            waits = data['hourly_wait_times']
            n = min(len(demands), len(waits))
            if n > 0:
                st_d = sum(demands[:n])
                if st_d > 0:
                    st_w_mins = sum(w * d for w, d in zip(waits[:n], demands[:n]))
                    st_avg_waits.append(st_w_mins / st_d)
                else:
                    st_avg_waits.append(0)
        
        avg_wait = sum(st_avg_waits) / len(st_avg_waits) if st_avg_waits else 0
        
        # 2. Lost Swap %
        # Total Lost / Total Demand * 100
        lost_pct = (total_lost_swaps / total_demand * 100) if total_demand > 0 else 0
        
        # 3. Utilization
        # Avg of station utilizations?
        # Re-calculating properly
        st_utils = []
        for sid, station in self.stations.items():
            snapshots = station.stats['minute_snapshots']
            if snapshots:
                u = [s['charger_utilization'] for s in snapshots]
                st_utils.append(sum(u)/len(u))
        
        utilization = sum(st_utils) / len(st_utils) if st_utils else 0
        
        # 4. Idle Inventory
        idle_inventory = 100 - utilization
        
        # 5. Cost (Total for duration / hours)
        # Fixed: alpha * total_chargers * hours
        # Wait: beta * total_wait_mins
        # Lost: gamma * total_lost_swaps
        
        # Note: total_wait_mins calculated above was summing st_avg_waits, which is wrong for Cost.
        # Cost needs TOTAL wait minutes across system.
        
        # Re-sum total wait minutes
        grand_total_wait_mins = 0
        for sid, data in self.results.items():
            demands = data['hourly_demand']
            waits = data['hourly_wait_times']
            n = min(len(demands), len(waits))
            grand_total_wait_mins += sum(w * d for w, d in zip(waits[:n], demands[:n]))
            
        fixed_cost = alpha * total_chargers * hours_simulated
        wait_cost = beta * grand_total_wait_mins
        lost_cost = gamma * total_lost_swaps
        
        total_cost_abs = fixed_cost + wait_cost + lost_cost
        cost_per_hr = total_cost_abs / max(1, hours_simulated)
        
        return {
            'avg_wait': round(avg_wait, 2),
            'lost_swaps': round(lost_pct, 2),
            'idle_inventory': round(idle_inventory, 2),
            'utilization': round(utilization, 2),
            'cost': round(cost_per_hr, 2)
        }

    def analyze_critical_wait_times(self, threshold_minutes=30, use_day7_only=True):
        """
        Analyze wait times to identify critical periods where wait time exceeds threshold.
        
        Args:
            threshold_minutes: Wait time threshold in minutes (default: 30)
            use_day7_only: If True, analyze only Day 7 data (hours 144-167)
        
        Returns:
            dict: Map of station_id -> list of critical periods
                  Each period contains: {
                      'start_hour': int (0-23 for day hour),
                      'end_hour': int (0-23 for day hour),
                      'start_hour_absolute': int (absolute hour index),
                      'end_hour_absolute': int (absolute hour index),
                      'peak_wait_time': float,
                      'duration_hours': int
                  }
        """
        critical_periods = {}
        
        for sid, data in self.results.items():
            wait_times = data.get('hourly_wait_times', [])
            
            if not wait_times:
                continue
            
            # Determine analysis range
            if use_day7_only and len(wait_times) >= 168:
                # Day 7 = hours 144-167 (indices 144-167)
                start_idx = 144
                end_idx = 168
                analysis_range = wait_times[start_idx:end_idx]
                offset = start_idx
            else:
                # Use all available data
                analysis_range = wait_times
                offset = 0
            
            # Find critical periods (continuous sequences where wait > threshold)
            periods = []
            in_critical_period = False
            period_start = None
            period_peak = 0
            
            for i, wait_time in enumerate(analysis_range):
                absolute_hour = offset + i
                
                if wait_time > threshold_minutes:
                    if not in_critical_period:
                        # Start new critical period
                        in_critical_period = True
                        period_start = i
                        period_peak = wait_time
                    else:
                        # Continue critical period, update peak
                        period_peak = max(period_peak, wait_time)
                else:
                    if in_critical_period:
                        # End critical period
                        periods.append({
                            'start_hour': period_start,  # 0-23 for day
                            'end_hour': i - 1,  # 0-23 for day
                            'start_hour_absolute': offset + period_start,
                            'end_hour_absolute': offset + i - 1,
                            'peak_wait_time': round(period_peak, 2),
                            'duration_hours': i - period_start
                        })
                        in_critical_period = False
                        period_start = None
                        period_peak = 0
            
            # Handle case where critical period extends to end of analysis range
            if in_critical_period:
                periods.append({
                    'start_hour': period_start,
                    'end_hour': len(analysis_range) - 1,
                    'start_hour_absolute': offset + period_start,
                    'end_hour_absolute': offset + len(analysis_range) - 1,
                    'peak_wait_time': round(period_peak, 2),
                    'duration_hours': len(analysis_range) - period_start
                })
            
            if periods:
                critical_periods[sid] = {
                    'station_name': data.get('name', sid),
                    'periods': periods,
                    'total_critical_hours': sum(p['duration_hours'] for p in periods)
                }
        
        return critical_periods



def run_simulation(days=7, save_output=True):
    """
    Convenience function to run the simulation.
    
    Args:
        days: Number of days to simulate (max 7 from dataset)
        save_output: Whether to save results to JSON
    
    Returns:
        dict: Simulation results for all stations
    """
    sim = BatterySimulation(days=min(days, 7))
    results = sim.run()
    sim.print_summary()
    
    if save_output:
        sim.save_results()
    
    return results, sim


def get_day7_wait_time():
    """
    Run simulation and return Day 7 average wait time.
    Used by the dashboard to display wait time.
    """
    sim = BatterySimulation(days=7)
    sim.run()
    return sim.get_day7_avg_wait_time()


def get_day7_lost_swap_pct():
    """
    Run simulation and return Day 7 lost swap percentage.
    Used by the dashboard to display lost swap %.
    """
    sim = BatterySimulation(days=7)
    sim.run()
    return sim.get_day7_lost_swap_percentage()


def get_day7_charger_util():
    """
    Run simulation and return Day 7 charger utilization percentage.
    Used by the dashboard to display utilization.
    """
    sim = BatterySimulation(days=7)
    sim.run()
    return sim.get_day7_charger_utilization()




def get_day7_total_cost():
    """
    Run simulation and return Day 7 average cost per hour.
    Used by the dashboard to display cost.
    """
    sim = BatterySimulation(days=7)
    sim.run()
    return sim.get_day7_total_cost()


if __name__ == "__main__":
    # Run 7-day simulation
    results = run_simulation(days=7)
