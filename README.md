# HackSmart Digital Twin Dashboard

A comprehensive Streamlit-based digital twin simulation platform for battery swap station networks. This tool allows operations planners to test "what-if" scenarios before deploying changes in the real network.

## 🎯 Features

### Dashboard Home
- **Real-time Network Overview**: View all swap stations on an interactive Delhi map
- **Live KPI Monitoring**: Track key performance indicators including:
  - Average wait time
  - Lost swaps per hour
  - Idle inventory
  - Charger utilization
  - Operational cost
  - City throughput
- **Station Details**: Click on any station to view detailed metrics and configuration

### Scenario Builder
- **Demand Changes**:
  - City-wide demand multiplier
  - Station-specific overrides
  - Time-window surge events
  
- **Infrastructure Changes**:
  - Add new swap stations
  - Modify existing stations (increase/decrease chargers)
  - Disable stations for maintenance scenarios
  
- **Policy Configuration**:
  - Fixed threshold replenishment
  - Scheduled refill
  - Predictive refill
  - Inter-station balancing

### Results Analysis
- **KPI Comparison**: Side-by-side baseline vs scenario comparison
- **Confidence Intervals**: 95% CI for predictions
- **Time Series Visualizations**: Track metrics over simulation horizon
- **Cost-Benefit Analysis**: Financial impact assessment with ROI calculations
- **Interactive Maps**: Visualize network changes and station status

## 📦 Installation

### Prerequisites
- Python 3.8 or higher
- pip package manager

### Setup

1. **Clone or download the project files**

2. **Install required dependencies**:
```bash
pip install -r requirements.txt
```

Required packages:
- streamlit
- folium
- streamlit-folium
- plotly
- pandas
- numpy
- matplotlib
- scipy
- fpdf
- Pillow

3. **Run the application**:
```bash
streamlit run app.py
```

The dashboard will open automatically in your default web browser at `http://localhost:8501`

## 🚀 Usage Guide

### Step 1: Explore Baseline Network
1. Start at the **Dashboard Home**
2. Review current network KPIs
3. Click on station markers to view detailed information
4. Identify bottlenecks and underutilized stations

### Step 2: Create a Scenario
1. Navigate to **Scenario Builder**
2. Configure your intervention:
   - **Demand Tab**: Adjust demand patterns (e.g., +20% city-wide, concert event surge)
   - **Infrastructure Tab**: Add stations or modify existing ones
   - **Policy Tab**: Select replenishment strategy
3. Review the scenario summary
4. Click **Run Simulation**

### Step 3: Analyze Results
1. The system will automatically switch to **Results Analysis**
2. Review KPI comparison table
3. Check confidence intervals for reliability
4. Examine time series charts for temporal patterns
5. Assess cost-benefit analysis for financial viability
6. View updated network map with changes highlighted

### Step 4: Iterate
1. Return to Scenario Builder to test alternative interventions
2. Compare up to 2 scenarios simultaneously
3. Export results as PDF report (coming soon)

## 📊 Mathematical Models

The simulation engine implements the following mathematical models from the problem statement:

### Wait Time (M/M/c Queue)
```
W_q,i(t) = (c_i * ρ_i(t))^c_i * ρ_i(t) / (c_i! * (1 - ρ_i(t))^2 * λ_i(t)) * P_0,i(t)
```

### Lost Swaps
```
LostSwaps_i(t) = λ_i(t) * P_K,i(t)
```

### Idle Inventory
```
IdleInventory_i(t) = c_i - λ_i(t) / μ_i
```

### Utilization
```
Utilization_i(t) = ρ_i(t) = λ_i(t) / (c_i * μ_i)
```

### Operational Cost
```
Cost_i(t) = α*c_i + β*λ_i(t)*W_q,i(t) + γ*LostSwaps_i(t)
```

### City Throughput
```
CityThroughput(t) = Σ_i min(λ_i(t), c_i*μ_i)
```

## ⚙️ Configuration

### Model Parameters (Adjustable in Sidebar)

- **α (Alpha)**: Fixed cost coefficient (default: ₹1000/hour)
- **β (Beta)**: Wait time cost coefficient (default: ₹50/minute)
- **γ (Gamma)**: Lost swap cost coefficient (default: ₹200/swap)

### Time Horizon
- Configurable from 1 hour to 168 hours (1 week)
- Simulation runs at minute-level granularity

### Station Parameters
Each station has:
- **Chargers (c_i)**: Number of charging units
- **Bays**: Number of swap bays
- **Inventory Capacity**: Maximum batteries
- **Arrival Rate (λ_i)**: Customers per minute
- **Service Rate (μ_i)**: Swaps per charger per minute (default: 0.5)

## 🗺️ Delhi Network

The system includes 8 pre-configured stations across Delhi:
1. Connaught Place Hub
2. Karol Bagh Station
3. Nehru Place Center
4. Dwarka Express
5. Rohini Junction
6. Lajpat Nagar Point
7. Saket Mall Station
8. Mayur Vihar Hub

## 📈 Example Scenarios

### Scenario 1: Concert Event
- **Intervention**: Add mobile station near venue + 300% demand surge
- **Expected Impact**: -68% wait time, -83% lost swaps
- **ROI**: Positive net impact

### Scenario 2: Network Expansion
- **Intervention**: Add 2 new stations in underserved areas
- **Expected Impact**: +25% throughput, -40% city-wide lost swaps
- **Cost**: Additional ₹2L/month operational cost

### Scenario 3: Charger Optimization
- **Intervention**: +2 chargers at top 3 bottleneck stations
- **Expected Impact**: -30% wait time at those stations
- **ROI**: High (lower marginal cost than new station)

## 🎨 UI Theme

The dashboard follows BatterySmart's brand identity:
- **Primary Colors**: Blue (#0066CC) and Green (#00CC66)
- **Light Theme**: Clean, professional interface
- **Status Indicators**:
  - 🟢 Green: Healthy (utilization < 75%)
  - 🟠 Orange: Warning (utilization 75-90%)
  - 🔴 Red: Critical (utilization > 90%)

## 🔧 Technical Architecture

```
┌─────────────────────────────────────┐
│  Streamlit Frontend                 │
│  - Interactive Dashboard            │
│  - Folium Maps                      │
│  - Plotly Visualizations            │
└─────────────┬───────────────────────┘
              │
┌─────────────▼───────────────────────┐
│  Simulation Engine (Python)         │
│  - Discrete-event simulation        │
│  - Queueing theory models           │
│  - KPI calculations                 │
└─────────────┬───────────────────────┘
              │
┌─────────────▼───────────────────────┐
│  Session State (In-memory)          │
│  - Station configurations           │
│  - Simulation results               │
│  - Scenario definitions             │
└─────────────────────────────────────┘
```

## 📝 Future Enhancements

- [ ] PDF report export functionality
- [ ] Multi-scenario comparison (>2 scenarios)
- [ ] Historical data import from CSV
- [ ] Machine learning-based demand forecasting
- [ ] Real-time data integration via API
- [ ] User authentication and saved scenarios
- [ ] Collaborative scenario sharing
- [ ] Advanced optimization algorithms
- [ ] 3D visualization with Pydeck
- [ ] Mobile-responsive design

## 🐛 Troubleshooting

### Common Issues

**Issue**: Map not displaying
- **Solution**: Ensure internet connection for OpenStreetMap tiles

**Issue**: Simulation takes too long
- **Solution**: Reduce time horizon or increase time step

**Issue**: Memory error on long simulations
- **Solution**: Results are sampled every 30 minutes; adjust for longer horizons

## 📄 License

This project is part of the HackSmart challenge solution.

## 👥 Contributors

Digital Twin Development Team

## 📞 Support

For issues or questions, please refer to the HackSmart documentation.

---

**Built with** ❤️ **using Streamlit, Folium, and Plotly**
