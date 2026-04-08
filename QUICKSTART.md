# Quick Start Guide - HackSmart Digital Twin

## 🚀 5-Minute Setup

### 1. Install Dependencies (1 minute)
```bash
pip3 install streamlit folium streamlit-folium plotly pandas numpy matplotlib scipy fpdf Pillow
```

### 2. Run the App (30 seconds)
```bash
python3 -m streamlit run app.py
```

The app will automatically open in your browser at http://localhost:8501

### 3. First Scenario - Concert Event (3 minutes)

#### Step 1: Understand the Baseline
- Look at the Dashboard Home
- Current city-wide metrics show:
  - Average wait time: ~6-8 minutes
  - Lost swaps: ~100-150 per hour
  - Utilization: ~70-75%

#### Step 2: Create Concert Scenario
1. Click **"Create New Scenario"**
2. Go to **"Demand Changes"** tab:
   - Enable "Time-window surge event"
   - Set surge time: 6:00 PM to 10:00 PM
   - Set surge multiplier: 3.0x
3. Go to **"Infrastructure Changes"** tab:
   - Click "Add New Station"
   - Name: "Stadium Mobile Unit"
   - Latitude: 28.5900 (near Jawaharlal Nehru Stadium)
   - Longitude: 77.2400
   - Chargers: 10
   - Bays: 4
   - Inventory: 40
   - Arrival rate: 8.0
   - Click "Add Station"
4. Click **"Run Simulation"**

#### Step 3: Analyze Results
The system will show:
- Wait time reduced from 8 min → 4 min during surge ✅
- Lost swaps reduced by 60-70% ✅
- Additional cost: ₹12K for event night
- Revenue gain: ₹15K+ from prevented lost swaps
- **Net positive ROI** ✅

## 💡 Tips for Effective Use

### Understanding Station Status
- **🟢 Green (Healthy)**: Utilization < 75%, no action needed
- **🟠 Orange (Warning)**: Utilization 75-90%, consider adding capacity
- **🔴 Red (Critical)**: Utilization > 90%, urgent intervention needed

### Best Practices for Scenario Design

1. **Start Small**: Test one change at a time
2. **Use Realistic Multipliers**: 
   - Normal variations: 0.8x - 1.2x
   - Special events: 2.0x - 4.0x
   - Extreme events: 5.0x+
3. **Check Time Series**: Don't just look at averages, check temporal patterns
4. **Validate Financially**: Always review cost-benefit analysis

### Common Scenarios to Test

#### Scenario A: Add vs Upgrade
**Question**: Is it better to add a new station or upgrade existing ones?

**Test**:
1. Create Scenario 1: Add new station in underserved area
2. Create Scenario 2: Add +3 chargers to top 2 bottleneck stations
3. Compare throughput improvement and cost

**Expected Finding**: Upgrading is often more cost-effective for marginal improvements

#### Scenario B: Demand Surge Management
**Question**: How to handle predictable demand spikes?

**Test**:
1. Create surge event (2-4 hours)
2. Test options:
   - Mobile station deployment
   - Pre-stocking nearby stations
   - Dynamic pricing (simulate with demand multiplier)

**Expected Finding**: Mobile stations work best for localized, temporary surges

#### Scenario C: Station Failure
**Question**: What happens if a major station goes offline?

**Test**:
1. Disable high-traffic station (e.g., Connaught Place)
2. Observe load redistribution
3. Identify which stations become overloaded

**Expected Finding**: Need redundancy in high-density areas

## 🎯 Reading the Results

### KPI Interpretation Guide

| Metric | Good Range | Action Needed If... |
|--------|-----------|-------------------|
| Avg Wait Time | < 5 min | > 10 min: Add capacity |
| Lost Swaps | < 5% of demand | > 10%: Critical capacity shortage |
| Utilization | 70-85% | < 50%: Overbuilt; > 90%: Bottleneck |
| Idle Inventory | 15-30% | > 40%: Reduce stock; < 10%: Increase stock |

### Cost-Benefit Quick Math

**Break-even calculation**:
```
Additional Cost per Hour = α × Δchargers + operational overhead
Revenue from Prevented Lost Swaps = Lost_swaps_prevented × ₹50
Net Benefit = Revenue - Cost

If Net Benefit > 0 over 30 days → Deploy intervention
```

**Example**:
- Add 3 chargers (₹300/hr fixed cost)
- Prevent 20 lost swaps/hr (₹1000/hr revenue)
- Net: +₹700/hr = +₹504K/month ✅

## 🔍 Troubleshooting Quick Fixes

### Simulation Running Slow?
- Reduce time horizon to 24 hours
- Results are sampled every 30 minutes automatically

### KPIs Don't Make Sense?
- Check your demand multipliers (are they too extreme?)
- Verify charger counts (must be > 0)
- Review arrival rates (typical: 2-10 customers/min)

### Map Not Interactive?
- Ensure stable internet (loads OpenStreetMap tiles)
- Try zooming in/out to refresh

### Want to Start Over?
- Click "Reset All" in sidebar
- Or refresh page (Ctrl+R / Cmd+R)

## 📊 Example: Reading Time Series Charts

When viewing time series for a station:

1. **Wait Time Chart**:
   - Peaks = congestion periods (usually morning/evening)
   - Should stay below 15 minutes
   - Spikes > 30 min = serious capacity issue

2. **Utilization Chart**:
   - Should follow demand pattern (high during peak hours)
   - Sustained > 95% = add chargers
   - Dips below 40% = station might be oversized

3. **Lost Swaps Chart**:
   - Should be near zero most of the time
   - Any lost swaps = direct revenue loss
   - Pattern matches capacity constraints

4. **Cost Chart**:
   - Fixed baseline (from α × chargers)
   - Spikes from wait time and lost swaps
   - Total cost = area under curve

## 🎓 Advanced Tips

### Optimizing for Different Goals

**Goal: Minimize Wait Time**
- Focus on high-traffic stations
- Add chargers where utilization > 85%
- Consider predictive replenishment policy

**Goal: Maximize Throughput**
- Add stations in coverage gaps
- Balance load across network
- Enable inter-station balancing

**Goal: Minimize Cost**
- Identify underutilized stations
- Right-size inventory
- Use threshold-based replenishment (cheaper than predictive)

**Goal: Maximize ROI**
- Target high-utilization, high-arrival stations
- Small capacity adds > new stations
- Focus on preventing lost swaps (direct revenue)

### Understanding Confidence Intervals

The 95% confidence intervals show:
- **Narrow band** = high confidence in prediction
- **Wide band** = more uncertainty (often from high variability)

If CI is too wide:
- Run longer simulation
- Check for extreme parameter values
- Validate input assumptions

## 🚀 Next Steps

After mastering basic scenarios:
1. Test multiple interventions simultaneously
2. Experiment with different replenishment policies
3. Model real-world events from your city
4. Document learnings for deployment planning

## 📞 Need Help?

Common questions:
- **"What's a good utilization target?"** → 70-85%
- **"How many chargers should I add?"** → Start with +2, test incrementally
- **"When should I add a new station?"** → When existing stations within 5km are all > 80% utilized
- **"How to model weather impact?"** → Use city-wide demand multiplier (rain = 0.7x, good weather = 1.2x)

Remember: The goal is to test and learn, not to find the perfect solution immediately!

---

**Happy Simulating! 🎉**
