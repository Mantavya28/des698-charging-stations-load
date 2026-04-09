# EV Charging Load Engine: Methodology & Technical Summary

## 1. Executive Summary
The **EV Charging Load Engine** is a high-fidelity, discrete-event simulation (DES) platform designed to estimate grid load profiles for city-wide electric vehicle (EV) populations. Unlike static models, this engine converts **EV Stock** (total vehicles) into **Dynamic Flow** (charging events) and integrates physical infrastructure constraints to identify periods of capacity overload and grid stress.

---

## 2. Demand Modeling (Stock-to-Flow)
The simulation uses a bottom-up methodology to generate charging demand:

### 2.1 Daily Charging Pool
The total number of daily charging events ($N_{daily}$) is derived from the total EV population ($N_{EV}$) and a daily charging frequency factor ($f_{charge}$):
$$N_{daily} = N_{EV} \times f_{charge}$$

### 2.2 Temporal Distribution
A normalized 24-hour demand profile ($B(t)$), derived from historical charging datasets, defines the probability of an EV arrival at any given time. Users can adjust the **Morning/Evening Peak Ratio** to shift the weight between commute-driven morning peaks and evening residential peaks.
The final 15-minute arrival rate $\lambda(t)$ is:
$$\lambda(t) = \text{Normalize}(B_{shaped}(t)) \times N_{daily}$$

### 2.3 Sectoral Split (Public vs. Home)
EVs are partitioned between **Public** and **Home** charging based on a user-defined share. 
- **Public Charging:** Routed through a discrete-event queue at charging stations.
- **Home Charging:** Added as a background load stream, typically following an evening peak distribution.

---

## 3. Infrastructure & Capacity Calibration
The dashboard evaluates whether the existing infrastructure can sustain the demand.

### 3.1 Policy-Aligned Constraints (IEA STEPS 2030)
The engine includes a calibration layer based on the **IEA India STEPS 2030** scenario:
- **Charger Density:** 1 Public Charger for every 7 EVs.
- **Power Density:** 3 kW of public charging capacity per EV.

### 3.2 Service Capacity Metrics
**Service Capacity** is defined as the maximum number of EVs the public network can serve in a 15-minute slot:
$$C_{slot} = N_{fast} \times \left(\frac{15}{T_{fast}}\right) + N_{slow} \times \left(\frac{15}{T_{slow}}\right)$$
*Where $T_{fast} \approx 30$ min and $T_{slow} \approx 240$ min.*

---

## 4. Simulation Engine (Discrete-Event)
The core backend is an event-driven simulation built on a `heapq`-based priority queue.

### 4.1 Event Handlers
The simulation processes five primary event types:
1.  **ARRIVAL:** An EV Enters the system.
2.  **QUEUE_DECISION:** EV selects a station based on distance and expected wait time (Utility Function).
3.  **START_CHARGING:** EV occupies a charger slot.
4.  **UPDATE_SOC:** Incremental state-of-charge tracking (includes power tapering for DC fast chargers).
5.  **END_CHARGING:** EV releases the charger; the next vehicle in the queue is pulled.

### 4.2 Queue Model
Stations operate as **M/G/c/K queues**:
- **M:** Poisson arrivals.
- **G:** General/Tapered service times.
- **c:** Number of parallel charger slots.
- **K:** Finite queue capacity; vehicles are "dropped" if expected wait time exceeds the maximum threshold (10 min).

---

## 5. Key Performance Indicators (KPIs)
- **Derived Peak:** The maximum instantaneous EV charging demand.
- **Average Utilization:** Ratio of mean demand to total service capacity ($< 1.0$ is optimal, $> 1.0$ indicates chronic shortage).
- **Overload Time (%):** Percentage of the day where the arrival rate exceeds the hardware service capacity.
- **Grid Load (kW):** The total instantaneous power draw from the grid, including the SoC-based power tapering for fast chargers.

---

## 6. Technical Stack
- **Dashboard:** Streamlit
- **Computations:** NumPy, Pandas
- **Visualization:** Matplotlib
- **Simulation:** Discrete Event (Python implementation)
