import copy

class LightweightStation:
    """
    Minimal station representation for the hill climbing simulation.
    Captures the snapshot state at 17:00.
    """
    def __init__(self, name, charged_count, charging_timers, hourly_demand, depleted_count=0):
        self.name = name
        self.b_charged = charged_count
        self.b_charging_timers = charging_timers # List of remaining minutes for each battery
        self.hourly_demand = hourly_demand # dict {hour_idx: count}
        self.b_depleted = depleted_count
    
    def deepcopy(self):
        return LightweightStation(
            self.name, 
            self.b_charged, 
            copy.deepcopy(self.b_charging_timers), 
            copy.deepcopy(self.hourly_demand),
            self.b_depleted
        )

def simulate_hour_wait(stations_snapshot, start_hour_idx=17):
    total_wait = 0

    for name, s in stations_snapshot.items():

        # 1. Count available batteries
        fully_charged = s.b_charged
        charging_90_plus = sum(
            1 for t in s.b_charging_timers if t <= 18
        )

        available = fully_charged + charging_90_plus

        # 2. Hourly demand
        demand = s.hourly_demand.get(start_hour_idx, 0)

        # 3. If enough batteries, no wait
        if available >= demand:
            continue

        # 4. Shortage case
        shortfall = demand - available

        # Batteries below 90% (not emergency-eligible yet)
        batteries_below_90 = [
            t for t in s.b_charging_timers if t > 18
        ]

        if batteries_below_90:
            nearest_timer = min(batteries_below_90)
            wait_per_customer = max(0, nearest_timer - 18)

        else:
            if getattr(s, "b_depleted", 0) > 0:
                wait_per_customer = 135
            else:
                wait_per_customer = 0

        station_wait = shortfall * wait_per_customer
        total_wait += station_wait

    return total_wait/36

def optimize_rebalancing(stations_snapshot, demand_map, start_hour=17):
    """
    Hill Climbing optimization to move CHARGED batteries between stations.
    
    Args:
        stations_snapshot: Dict {name: {'charged': int, 'charging': [timers], 'depleted': int}}
        demand_map: Dict {name: {hour: count}}
    
    Returns:
        tuple: (best_allocation_changes, final_wait, shuffled_count, iterations, moves)
    """
    # 1. Convert to Lightweight objects
    sim_stations = {}
    for name, state in stations_snapshot.items():
        sim_stations[name] = LightweightStation(
            name,
            state['charged'],
            state['charging'],
            demand_map.get(name, {}),
            state.get('depleted', 0)
        )
    
    # 2. Initial State
    current_allocation = {name: s.b_charged for name, s in sim_stations.items()}
    best_allocation = current_allocation.copy()
    
    base_wait = simulate_hour_wait(sim_stations, start_hour)
    best_wait = base_wait
    
    # 3. Hill Climbing
    improved = True
    iteration = 0
    total_moves = 0
    
    max_iterations = 100
    
    while improved and iteration < max_iterations:
        improved = False
        iteration += 1
        
        providers = [p for p in sim_stations.keys() if sim_stations[p].b_charged > 0]
        receivers = list(sim_stations.keys())
        
        local_best_wait = best_wait
        local_best_move = None
        
        for p in providers:
            for r in receivers:
                if p == r: continue
                
                # Try Move p -> r
                sim_stations[p].b_charged -= 1
                sim_stations[r].b_charged += 1
                
                wait = simulate_hour_wait(sim_stations, start_hour)
                
                # Revert
                sim_stations[p].b_charged += 1
                sim_stations[r].b_charged -= 1
                
                if wait < local_best_wait:
                    local_best_wait = wait
                    local_best_move = (p, r)
        
        if local_best_move:
            p, r = local_best_move
            # Commit the move locally
            sim_stations[p].b_charged -= 1
            sim_stations[r].b_charged += 1
            
            best_allocation[p] -= 1
            best_allocation[r] += 1
            
            best_wait = local_best_wait
            improved = True
            total_moves += 1
            
    # Calculate Results
    shuffled_batteries = 0
    changes = {}
    
    for name, count in current_allocation.items():
        diff = best_allocation[name] - count
        changes[name] = diff
        shuffled_batteries += abs(diff)
        
    shuffled_batteries = shuffled_batteries // 2 # One move involves 2 stations count change, but is 1 battery
    
    return {
        'initial_wait': base_wait,
        'final_wait': best_wait,
        'shuffled_count': shuffled_batteries,
        'changes': changes,
        'iterations': iteration,
        'moves': total_moves
    }
