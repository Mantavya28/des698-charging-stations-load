import numpy as np
import pandas as pd
from datetime import datetime, timedelta

np.random.seed(42)

n_stations = 40
days = 14
freq = "15min"
city_center_lat = 28.6139
city_center_lon = 77.2090

station_ids = [f"S{i:03d}" for i in range(1, n_stations + 1)]

lats = city_center_lat + np.random.normal(0, 0.05, n_stations)
lons = city_center_lon + np.random.normal(0, 0.05, n_stations)
chargers = np.random.randint(2, 8, n_stations)
bays = chargers + np.random.randint(1, 4, n_stations)
inventory_caps = chargers * np.random.randint(3, 6, n_stations)

stations_df = pd.DataFrame({
    "station_id": station_ids,
    "lat": lats,
    "lon": lons,
    "chargers": chargers,
    "bays": bays,
    "inventory_cap": inventory_caps
})

start_time = datetime(2025, 1, 1, 0, 0)
timestamps = pd.date_range(start_time, periods=int((24*60/15)*days), freq=freq)

demand_rows = []
for sid in station_ids:
    base_rate = np.random.uniform(0.5, 2.5)
    peak_multiplier = np.random.uniform(1.5, 2.5)
    for t in timestamps:
        hour = t.hour
        if 8 <= hour <= 11 or 17 <= hour <= 21:
            lam = base_rate * peak_multiplier
        else:
            lam = base_rate
        # Generate arrivals (ensure non-negative)
        arrivals = np.random.poisson(lam)
        demand_rows.append([sid, t, arrivals])

demand_df = pd.DataFrame(demand_rows, columns=["station_id", "datetime", "arrivals"])

coords = stations_df[["lat", "lon"]].values
topology_rows = []
for i in range(n_stations):
    for j in range(i+1, n_stations):
        lat1, lon1 = coords[i]
        lat2, lon2 = coords[j]
        
        # Haversine-like approximation or simple Euclidean * 111km
        dist = np.sqrt((lat1 - lat2)**2 + (lon1 - lon2)**2) * 111
        
        topology_rows.append([station_ids[i], station_ids[j], dist])
        topology_rows.append([station_ids[j], station_ids[i], dist])

topology_df = pd.DataFrame(topology_rows, columns=["from_station", "to_station", "distance_km"])

stations_df.to_csv("stations.csv", index=False)
demand_df.to_csv("demand.csv", index=False)
topology_df.to_csv("topology.csv", index=False)

print("Generated files:")
print("stations.csv")
print("demand.csv")
print("topology.csv")
