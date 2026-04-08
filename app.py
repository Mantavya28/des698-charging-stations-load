import streamlit as st
import time
import folium
from streamlit_folium import st_folium
import matplotlib.pyplot as plt
import matplotlib.figure as mpl_figure
from matplotlib.patches import Polygon as MPLPolygon
import pandas as pd
import numpy as np
import os
from pathlib import Path
from datetime import datetime, timedelta, time as dt_time
# Import Spatial Utils
from spatial_utils import generate_voronoi_polygons, redistribute_scenario_demand
from battery_simulation import get_day7_wait_time, get_day7_lost_swap_pct, get_day7_charger_util, get_day7_total_cost, BatterySimulation, load_stations_from_csv
import json
from typing import Dict, List, Tuple
import math
import base64
import textwrap
import streamlit.components.v1 as components



# Page configuration
st.set_page_config(
    page_title="HackSmart Digital Twin",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------------------------------------------------------------------
# PATH RESOLUTION HELPER FOR STREAMLIT CLOUD
# ---------------------------------------------------------------------
def get_data_path(filename):
    """Get absolute path to data file, compatible with Streamlit Cloud."""
    # Get directory where app.py is located
    base_dir = Path(__file__).parent
    return str(base_dir / filename)

# ---------------------------------------------------------------------
# STABILITY FIX: Rerun Handling
# Handles map interactions properly without crashing the component
# ---------------------------------------------------------------------
if st.session_state.get('needs_refresh'):
    st.session_state.needs_refresh = False
    st.rerun()

# Custom CSS for white-and-green theme
# Custom CSS for Battery Smart-like theme (Soft Dark Blue & White)
st.markdown("""
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<style>
    /* Main theme colors */
    :root {
        --primary-blue: #0A2647; /* Soft Dark Blue */
        --accent-blue: #205295;  /* Lighter Blue */
        --highlight-blue: #2C74B3;
        --light-bg: #FFFFFF;
        --muted-bg: #F0F4F8;     /* Light Blue-Grey */
        --text-dark: #1A1A1A;
        --text-light: #F0F4F8;
    }

    /* App background */
    .stApp, body, .reportview-container {
        background-color: var(--muted-bg) !important;
        color: var(--text-dark) !important;
    }
    
    /* Sidebar specific background */
    section[data-testid="stSidebar"] {
        background-color: #FFFFFF !important;
    }

    /* Header styling */
    .main-header {
        background: linear-gradient(135deg, var(--primary-blue) 0%, var(--accent-blue) 100%);
        padding: 24px;
        border-radius: 20px;
        color: white;
        text-align: center;
        margin-bottom: 24px;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.2), 0 8px 10px -6px rgba(0, 0, 0, 0.2);
    }
    
    .main-header h1 {
        color: white !important;
        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
        font-weight: 700;
    }
    
    .main-header p {
        color: #E6F4F1 !important; 
        font-size: 1.1rem;
    }

    /* KPI card styling */
    .kpi-card {
        background: white;
        border: 1px solid #E1E8ED;
        border-radius: 16px;
        padding: 20px 15px;
        text-align: center;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    
    .kpi-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        border-color: var(--highlight-blue);
    }

    .kpi-icon {
        font-size: 24px;
        color: var(--accent-blue);
        margin-bottom: 10px;
    }

    .kpi-value {
        font-size: 26px;
        font-weight: 700;
        color: var(--primary-blue);
        font-family: 'Roboto', sans-serif;
    }

    .kpi-label {
        font-size: 13px;
        font-weight: 500;
        color: #546E7A;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-top: 5px;
    }

    /* Scenario builder styling */
    .scenario-section {
        background: var(--muted-bg);
        background: var(--muted-bg);
        padding: 20px;
        border-radius: 16px;
        margin: 15px 0;
        border-left: 4px solid var(--accent-blue);
    }

    /* Status badges */
    .status-badge {
        padding: 4px 8px;
        border-radius: 4px;
        font-weight: 600;
        font-size: 0.8em;
    }

    /* Button styling */
    /* Button styling (Aesthetic Gradient) */
    /* Button styling (Aesthetic Gradient - UNIVERSAL) */
    .stButton>button, 
    .stDownloadButton>button,
    .stFormSubmitButton>button,
    .stButton>button[kind="primary"] {
        background: linear-gradient(135deg, #0A2647 0%, #173B66 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 12px 24px !important;
        font-weight: 600 !important;
        text-transform: uppercase;
        letter-spacing: 1px;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
        box-shadow: 0 4px 6px rgba(10, 38, 71, 0.2);
    }

    .stButton>button:hover, 
    .stDownloadButton>button:hover,
    .stFormSubmitButton>button:hover,
    .stButton>button[kind="primary"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 20px rgba(10, 38, 71, 0.4);
        background: linear-gradient(135deg, #0d325e 0%, #1f4d85 100%) !important;
        color: white !important;
    }
    
    .stButton>button:active,
    .stDownloadButton>button:active {
        transform: translateY(1px);
        box-shadow: 0 2px 4px rgba(10, 38, 71, 0.2);
    }
    
    /* Rounded Plots    
    /* Plot styling for charts */
    .stPlot {
        border-radius: 20px !important;
        overflow: hidden !important;
        background-color: white !important;
    }
    .stPlot:hover {
        box-shadow: 0 12px 24px rgba(0,0,0,0.12) !important;
    }
    

    /* Reduced Top Padding for Sidebar to move Logo UP */
    /* Reduced Top Padding for Sidebar to move Logo UP */
    section[data-testid="stSidebar"] > div:first-child {
        padding-top: 0rem !important;
    }
    
    /* Aggressive pull-up for the content block */
    [data-testid="stSidebar"] .block-container {
        padding-top: 0rem !important;
        margin-top: -2rem !important;
    }

    /* AESTHETIC NAVIGATION BUTTONS */
    /* Target radio labels to look like cards */
    [data-testid="stRadio"] label {
        background: #FFFFFF !important;
        padding: 12px 16px !important;
        border-radius: 12px !important;
        margin-bottom: 8px !important;
        border: 1px solid #E1E8ED !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.02) !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
        color: #4A5568 !important;
        font-weight: 500 !important;
        cursor: pointer !important;
        position: relative !important;
        z-index: 1 !important;
    }
    
    /* Ensure radio inputs are clickable */
    [data-testid="stRadio"] input[type="radio"] {
        cursor: pointer !important;
        pointer-events: auto !important;
        z-index: 2 !important;
    }

    [data-testid="stRadio"] label:hover {
        border-color: var(--highlight-blue) !important;
        transform: translateY(-2px) !important;
        background: #FFFFFF !important;
        box-shadow: 0 8px 15px rgba(44, 116, 179, 0.1) !important;
        color: var(--primary-blue) !important;
    }
    
    /* Selected State (Modern Browsers) */
    [data-testid="stRadio"] label:has(input:checked) {
        background: linear-gradient(135deg, #0A2647 0%, #173B66 100%) !important;
        border-color: #0A2647 !important;
        box-shadow: 0 8px 20px rgba(10, 38, 71, 0.3) !important;
    }
    
    /* FORCE TEXT WHITE IN SELECTED STATE */
    [data-testid="stRadio"] label:has(input:checked) *,
    [data-testid="stRadio"] label:has(input:checked) p,
    [data-testid="stRadio"] label:has(input:checked) div,
    [data-testid="stRadio"] label:has(input:checked) span {
        color: #FFFFFF !important;
    }
    
    /* ANIMATIONS & SCROLLBARS */
    
    /* Sleek Scrollbar */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    ::-webkit-scrollbar-track {
        background: #F1F1F1;
        border-radius: 4px;
    }
    ::-webkit-scrollbar-thumb {
        background: #B0BCC9; 
        border-radius: 4px;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: #0A2647; 
    }

    /* Global Fade In Animation */
    @keyframes fadeIn {
        0% { opacity: 0; transform: translateY(10px); }
        100% { opacity: 1; transform: translateY(0); }
    }
    
    .block-container {
        animation: fadeIn 0.8s cubic-bezier(0.4, 0, 0.2, 1);
    }
    
    
    /* Gradient Headers - REVERTED TO SOLID FOR VISIBILITY */
    h1, h2, h3 {
        font-family: 'Helvetica Neue', sans-serif !important;
        color: #0A2647 !important;
        background: none !important;
        -webkit-text-fill-color: #0A2647 !important;
        letter-spacing: -0.5px;
    }
    

    

    

    



    
    /* specific overrides for clean look */
    [data-testid="stMetric"] {
        overflow: visible !important;
        min-width: fit-content !important;
    }
    
    [data-testid="stMetricValue"] {
        font-size: 60px;
        font-weight: 700;
        color: var(--primary-blue);
        white-space: nowrap !important;
        overflow: visible !important;
        text-overflow: clip !important;
        min-width: fit-content !important;
        width: auto !important;
    }
    
    [data-testid="stMetricValue"] > div {
        overflow: visible !important;
        text-overflow: clip !important;
    }
    
    [data-testid="stMetricLabel"] {
        white-space: nowrap !important;
    }
    /* Bigger KPI comparison table */
    div[data-testid="stDataFrame"] table {
        font-size: 60px !important;
    }

    div[data-testid="stDataFrame"] th {
        font-size: 60px !important;
        font-weight: 600 !important;
    }

    div[data-testid="stDataFrame"] td {
        padding-top: 12px !important;
        padding-bottom: 12px !important;
    }

    /* Secondary/Ghost buttons */
    .stButton>button[kind="secondary"] {
        background-color: transparent;
        border: 1px solid var(--primary-blue);
        color: var(--primary-blue);
    }

    /* SUPER AGGRESSIVE PADDING REMOVAL */
    
    /* 1. Hide the Streamlit Header decoration (the colored line & hamburger menu if desired, 
          but usually we just want to reclaim space. 
          Visibility hidden keeps functionality accessible via shortcuts? No, display none is better for space.) */
    header[data-testid="stHeader"] {
        display: none !important;
    }
    
    /* 2. Force Sidebar to Top Edge */
    section[data-testid="stSidebar"] {
        top: 0 !important; 
        height: 100vh !important;
    }
    
    /* 3. Kill padding on the internal container (Adjusted for 'slight' padding) */
    div[data-testid="stSidebarUserContent"] {
        padding-top: 0.75rem !important; 
    }
    
    /* 4. Target the very first element (The Logo) to fit flush */
    div[data-testid="stSidebarUserContent"] > div:first-child {
        margin-top: 0px !important;
    }
    
    /* 5. Main block container push up */
    .block-container {
        padding-top: 1rem !important; /* Main content top padding */
        margin-top: 0rem !important;
    }

    /* Sidebar logo adjustments - PIXEL ART STYLE */
    .stSidebar .css-1lsmgbg img, 
    [data-testid="stSidebar"] img {
        border-radius: 0px !important; 
        border: none !important;
        image-rendering: pixelated !important; 
        image-rendering: -moz-crisp-edges !important;
        image-rendering: crisp-edges !important;
        margin-bottom: 20px !important;
        /* Ensure logo itself has no margin */
        margin-top: 0px !important;
        width: 100%;
    }
    
    /* HIDE STREAMLIT ELEMENT TOOLBAR (Floating buttons over charts) */
    [data-testid="stElementToolbar"] {
    display: none !important;
    border: 1px solid rgba(0,0,0,0.04);
    }

    
    /* Map styling - Safe Targeting via specific selector */
    iframe[title="streamlit_folium.st_folium"] {
        border-radius: 20px !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }
    div[data-testid="stIframe"] iframe {
        border-radius: 20px !important;
    }
    
    /* Map control panel */
    .map-control-panel {
        background-color: #f8f9fa;
        padding: 10px;
        border-radius: 8px;
        border: 1px solid #dee2e6;
        margin-bottom: 10px;
    }
    div[data-testid="stIframe"] {
        margin-bottom: 0 !important;
        padding-bottom: 0 !important;
    }

    div[data-testid="stIframe"] > iframe {
        display: block;
        margin-bottom: 0 !important;
    }

    /* Extra safety: specifically target folium container */
    div.element-container:has(iframe[title="streamlit_folium.st_folium"]) {
        margin-bottom: -1rem !important;
        padding-bottom: 0 !important;
    }

    div.element-container {
        margin-bottom: 0rem !important;
    }
</style>
""", unsafe_allow_html=True)

# =====================================================================
# SIMULATION ENGINE - Mathematical Models
# =====================================================================

class SimulationEngine:
    """Core simulation engine implementing the mathematical models"""
    
    def __init__(self):
        # Default configurable parameters
        self.alpha = 1000  # Fixed cost coefficient (₹/hour)
        self.beta = 50     # Wait time cost coefficient (₹/min)
        self.gamma = 200   # Lost swap cost coefficient (₹/swap)
        
    def calculate_wait_time(self, c_i: float, rho_i: float, lambda_i: float) -> float:
        """
        Calculate average wait time using M/M/c queue formula
        W_q,i(t) = (c_i * rho_i(t))^c_i * rho_i(t) / (c_i! * (1 - rho_i(t))^2 * lambda_i(t)) * P_0,i(t)
        
        Simplified for practical use
        """
        if rho_i >= 1.0:
            return 60.0  # Cap at 60 minutes if system is saturated
        
        # Erlang C formula approximation
        numerator = (c_i * rho_i) ** c_i * rho_i
        denominator = math.factorial(int(c_i)) * (1 - rho_i) ** 2 * lambda_i
        
        # P_0,i approximation (probability of zero customers)
        p_0 = 1.0 / (1 + (c_i * rho_i) ** c_i / math.factorial(int(c_i)))
        
        wait_time = (numerator / denominator) * p_0 if denominator > 0 else 0
        return max(0, min(wait_time, 60))  # Bound between 0-60 minutes
    
    def calculate_lost_swaps(self, lambda_i: float, p_k: float) -> float:
        """
        LostSwaps_i(t) = λ_i(t) * P_K,i(t)
        Where P_K,i is the probability of system being full
        """
        return lambda_i * p_k
    
    def calculate_idle_inventory(self, c_i: float, lambda_i: float, mu_i: float) -> float:
        """
        IdleInventory_i(t) = c_i - λ_i(t) / μ_i
        """
        return max(0, c_i - (lambda_i / mu_i))
    
    def calculate_utilization(self, lambda_i: float, c_i: float, mu_i: float) -> float:
        """
        Utilization_i(t) = ρ_i(t) = λ_i(t) / (c_i * μ_i)
        """
        return min(1.0, lambda_i / (c_i * mu_i))
    
    def calculate_cost(self, c_i: float, lambda_i: float, wait_time: float, lost_swaps: float) -> float:
        """
        Cost_i(t) = α*c_i + β*λ_i(t)*W_q,i(t) + γ*LostSwaps_i(t)
        """
        fixed_cost = self.alpha * c_i
        wait_cost = self.beta * lambda_i * wait_time
        lost_swap_cost = self.gamma * lost_swaps
        return fixed_cost + wait_cost + lost_swap_cost
    

    
    def distribute_total_demand(self, total_demand_series: List[float], weights: List[float]) -> List[List[int]]:
        """
        Distribute total city demand among stations ensuring integer values and exact sum.
        Using Largest Remainder Method/Proportional round-off.
        
        Args:
            total_demand_series: List of total demand per hour (e.g. 24 values)
            weights: List of weights for each station (should sum to 1.0)
            
        Returns:
            List of lists: [ [station_0_hr0, ...], [station_1_hr0, ...], ... ]
        """
        n_stations = len(weights)
        n_hours = len(total_demand_series)
        
        # Initialize result table: [station][hour]
        distributed_demand = [[0] * n_hours for _ in range(n_stations)]
        
        for h in range(n_hours):
            total_d = total_demand_series[h]
            
            # 1. Calculate raw shares
            raw_demands = [total_d * w for w in weights]
            
            # 2. Integer part
            int_demands = [int(d) for d in raw_demands]
            
            # 3. Fractional remainder
            remainders = [d - int(d) for d, int_d in zip(raw_demands, int_demands)]
            
            # 4. Distribute dust (diff) to highest remainders
            diff = int(round(total_d)) - sum(int_demands)
            
            # Sort indices by remainder descending
            sorted_indices = np.argsort(remainders)[::-1]
            
            for i in range(diff):
                idx = sorted_indices[i % n_stations]
                int_demands[idx] += 1
                
            # Assign to matrix
            for s in range(n_stations):
                distributed_demand[s][h] = int_demands[s]
                
        return distributed_demand

    def simulate_station(self, station: Dict, time_horizon_hours: int, surge_config: Dict = None, custom_demand_series: List[int] = None) -> Dict:
        """
        Run simulation for a single station over time horizon.
        
        Args:
            custom_demand_series: List of HOURLY demand values (integers). 
                                  If provided, overrides synthetic generation.
        """
        results = {
            'time': [],
            'wait_time': [],
            'lost_swaps': [],
            'idle_inventory': [],
            'utilization': [],
            'cost': []
        }
        
        # Simulate minute by minute
        for minute in range(time_horizon_hours * 60):
            hour = minute / 60.0
            
            lambda_i = 0
            
            if custom_demand_series:
                # Use data-driven hourly demand
                hour_idx = int(hour) % 24
                # Use the provided integer demand for this hour
                if hour_idx < len(custom_demand_series):
                    lambda_i = custom_demand_series[hour_idx]
                else:
                    lambda_i = custom_demand_series[-1] # Clamp
            else:
                # Fallback: Synthetic Model
                base_lambda = station['arrival_rate']
                time_factor = 1.0 + 0.3 * np.sin(2 * np.pi * hour / 24)  # Daily cycle
                
                # Apply Surge Logic (Only for synthetic mode or modifier)
                surge_multiplier = 1.0
                if surge_config:
                    current_min_of_day = minute % (24 * 60)
                    start = surge_config['start_min']
                    end = surge_config['end_min']
                    factor = surge_config['factor']
                    
                    in_surge = False
                    if start <= end:
                        if start <= current_min_of_day <= end:
                            in_surge = True
                    else: # Crosses midnight
                        if current_min_of_day >= start or current_min_of_day <= end:
                            in_surge = True
                    
                    if in_surge:
                        surge_multiplier = factor
    
                lambda_i = base_lambda * time_factor * station.get('demand_multiplier', 1.0) * surge_multiplier
            
            c_i = station['chargers']
            mu_i = station['service_rate']
            
            # Calculate metrics
            rho_i = self.calculate_utilization(lambda_i, c_i, mu_i)
            wait_time = self.calculate_wait_time(c_i, rho_i, lambda_i)
            
            # Probability of being full (simplified)
            p_k = max(0, (rho_i - 0.8) / 0.2) if rho_i > 0.8 else 0
            lost_swaps = self.calculate_lost_swaps(lambda_i, p_k)
            
            idle_inv = self.calculate_idle_inventory(c_i, lambda_i, mu_i)
            cost = self.calculate_cost(c_i, lambda_i, wait_time, lost_swaps)
            
            # Store results (sample every 30 minutes to reduce data size)
            if minute % 30 == 0:
                results['time'].append(hour)
                results['wait_time'].append(wait_time)
                results['lost_swaps'].append(lost_swaps)
                results['idle_inventory'].append(idle_inv)
                results['utilization'].append(rho_i * 100)
                results['cost'].append(cost)
        
        return results

# =====================================================================
# DATA INITIALIZATION
# =====================================================================

# STATION_FILE removed - using embedded data

def save_stations_to_file(stations):
    """Save current stations list to JSON file."""
    # Persistence disabled to remove file dependency
    pass

@st.cache_data(ttl=3600)
def load_and_calibrate_data():
    """
    Loads hacksmart_frontend.xlsx and extracts city-wide demand profile.
    Returns:
        tuple: (weekday_profile_dict, weekend_profile_dict) or (None, None)
    """
    import os
    try:
        # Primary source: hacksmart_frontend.xlsx
        excel_path = get_data_path("hacksmart_frontend.xlsx")
        if os.path.exists(excel_path):
            try:
                df = pd.read_excel(excel_path)
                
                if 'hour' in df.columns and 'delhi_demand' in df.columns:
                    # Group by hour to get average (in case of duplicates)
                    profile = df.groupby('hour')['delhi_demand'].mean().to_dict()
                    
                    print("✓ Calibrated demand profile from hacksmart_frontend.xlsx")
                    # Use same profile for both weekday and weekend for now
                    return profile, profile
            except Exception as e:
                print(f"Warning: Error reading hacksmart_frontend.xlsx: {e}")
        
        # Fallback: full_dataset.csv
        csv_path = get_data_path("full_dataset.csv")
        if os.path.exists(csv_path):
            try:
                df = pd.read_csv(csv_path)
                
                # Ensure day_type column exists
                if 'day_type' not in df.columns:
                    # Fallback creation if missing (assume weekend logic)
                    if 'is_weekend' in df.columns:
                        df['day_type'] = df['is_weekend'].apply(lambda x: 'weekend' if x else 'weekday')
                    else:
                        # No day type info, use all as weekday
                        df['day_type'] = 'weekday'
                    
                # Group by day type and hour to get simple avg curve
                if 'delhi_demand' in df.columns and 'hour' in df.columns:
                    wd_profile = df[df['day_type'] == 'weekday'].groupby('hour')['delhi_demand'].mean().to_dict()
                    we_profile = df[df['day_type'] != 'weekday'].groupby('hour')['delhi_demand'].mean().to_dict()
                    
                    print("✓ Calibrated demand profiles from full_dataset.csv")
                    return wd_profile, we_profile
            except Exception as e:
                print(f"Warning: Error reading full_dataset.csv: {e}")
        
        print("⚠ No demand data files found - using default profiles")
        return None, None
        
    except Exception as e:
        print(f"Error in load_and_calibrate_data: {e}")
        return None, None

def update_backend_with_scenario(station_shares: Dict[str, float], engine):
    """
    Updates full_dataset.csv with station-specific demand columns based on current scenario shares.
    
    Args:
        station_shares: Dict mapping station_id -> share fraction (sum=1.0)
        engine: SimulationEngine instance (for distribution logic)
    """
    import os
    try:
        csv_path = get_data_path("full_dataset.csv")
        if not os.path.exists(csv_path):
            return False
            
        print("Updating backend CSV with scenario demand...")
        df = pd.read_csv(csv_path)
        
        if 'delhi_demand' not in df.columns:
            return False
            
        # Prepare inputs
        total_demand = df['delhi_demand'].tolist()
        # Sort stations to ensure consistent column order
        station_ids = sorted(station_shares.keys())
        weights = [station_shares[sid] for sid in station_ids]
        
        # Distribute (using Large Remainder Method via Engine)
        # distribute_total_demand anticipates list of floats, returns list of lists of ints
        distributed_matrix = engine.distribute_total_demand(total_demand, weights)
        
        # Assign to DataFrame
        for idx, sid in enumerate(station_ids):
            col_name = f"{sid}_demand"
            df[col_name] = distributed_matrix[idx]
            
        df.to_csv(csv_path, index=False)
        print("Backend CSV updated successfully.")
        return True
        
    except Exception as e:
        print(f"Error updating backend CSV: {e}")
        return False

@st.cache_data(ttl=3600)
def initialize_delhi_stations() -> List[Dict]:
    """
    Initialize swap stations.
    Returns data loaded from stations.csv.
    """
    # Use load_stations_from_csv from battery_simulation
    stations = load_stations_from_csv()
    print(f"Loaded {len(stations)} stations from CSV.")
    return stations

def get_fixed_baseline_kpis() -> Dict:
    """Return FIXED constants as requested by user for the dashboard baseline"""
    return {
        'avg_wait': 4.12,
        'lost_swaps': 21.90,
        'idle_inventory': 35.07,
        'utilization': 64.93,
        'cost': 178916.67
    }

def calculate_mmc_kpis(stations: List[Dict], sim_engine: SimulationEngine) -> Dict:
    """
    Calculate KPIs using the M/M/c analytical formulas (SimulationEngine).
    Used for comparative analysis (Delta calculation).
    """
    total_wait = 0
    total_lost = 0
    total_idle = 0
    total_util = 0
    total_cost = 0
    
    for station in stations:
        lambda_i = station['arrival_rate']
        c_i = station['chargers']
        mu_i = station['service_rate']
        
        rho_i = sim_engine.calculate_utilization(lambda_i, c_i, mu_i)
        wait_time = sim_engine.calculate_wait_time(c_i, rho_i, lambda_i)
        p_k = max(0, (rho_i - 0.8) / 0.2) if rho_i > 0.8 else 0
        lost_swaps = sim_engine.calculate_lost_swaps(lambda_i, p_k)
        idle_inv = sim_engine.calculate_idle_inventory(c_i, lambda_i, mu_i)
        cost = sim_engine.calculate_cost(c_i, lambda_i, wait_time, lost_swaps)
        
        total_wait += wait_time * lambda_i
        total_lost += lost_swaps
        total_idle += idle_inv
        total_util += rho_i
        total_cost += cost
    
    n_stations = len(stations) if stations else 1
    
    # Avoid division by zero
    total_arrival = sum(s['arrival_rate'] for s in stations)
    avg_wait = total_wait / total_arrival if total_arrival > 0 else 0
    
    # Lost swaps needs to be percentage for consistency with new fixed metrics?
    # No, M/M/c calculates count/hr.
    # Fixed metric is %.
    # We need to return compatible units if we want valid deltas.
    # If Fixed is %, M/M/c should probably estimate %.
    # Lost % ~ (Lost / Demand) * 100
    
    lost_pct = (total_lost / total_arrival * 100) if total_arrival > 0 else 0
    
    return {
        'avg_wait': avg_wait,
        'lost_swaps': lost_pct, # Now returning percentage to match fixed baseline unit
        'idle_inventory': total_idle / n_stations,
        'utilization': (total_util / n_stations) * 100,
        'cost': total_cost
    }

# =====================================================================
# SESSION STATE INITIALIZATION
# =====================================================================

if 'stations' not in st.session_state:
    st.session_state.stations = initialize_delhi_stations()
    st.session_state.sim_engine = SimulationEngine()
    # Calculate Baseline KPIs (Fixed Constants)
    st.session_state.baseline_kpis = get_fixed_baseline_kpis()
    st.session_state.scenario_stations = None
    st.session_state.scenario_kpis = None
    st.session_state.selected_station = None
    st.session_state.simulation_results = None
    st.session_state.scenario_config = {
        'demand_changes': {},
        'infrastructure_changes': {},
        'new_stations': []
    }

# =====================================================================
# DATA LOADING
# =====================================================================



@st.cache_data(ttl=3600)
def load_excel_demand_data():
    """
    Load demand data from hacksmart_frontend.xlsx.
    Returns a DataFrame with columns: hour, delhi_demand, and day index.
    """
    import os
    try:
        excel_path = get_data_path("hacksmart_frontend.xlsx")
        if os.path.exists(excel_path):
            try:
                df = pd.read_excel(excel_path)
                # Add day index (each day has 24 hours)
                df['day'] = df.index // 24
                print("✓ Loaded demand data from hacksmart_frontend.xlsx")
                return df
            except Exception as e:
                print(f"⚠ Error reading Excel file: {e}")
                return None
        else:
            print("⚠ hacksmart_frontend.xlsx not found")
            return None
    except Exception as e:
        print(f"Error in load_excel_demand_data: {e}")
        return None

def generate_demand_curve(station=None, hours_limit=24):
    """
    Generates a Matplotlib Line chart for demand profile.
    If station is None, generates City-Wide aggregate profile using Excel data.
    hours_limit: total hours to display (24 per day, so 48 for 2 days, etc.)
    """
    # Load Excel data
    excel_data = load_excel_demand_data()
    
    if excel_data is not None and station is None:
        # Use Excel data for city-wide demand - Day 7 (last day of week)
        # Day 7 = rows 144-167 (hours 0-23 of day 7)
        day_7_start = 6 * 24  # Row 144 (0-indexed day 6 = day 7)
        day_7_end = 7 * 24    # Row 168
        data_to_use = excel_data.iloc[day_7_start:day_7_end]
        hours = list(range(24))
        profile = data_to_use['delhi_demand'].tolist()
        
        title = "City-Wide Demand Trend"
        color = '#0A2647'
    elif station:
        # Generate station-specific profile (randomized based on ID for consistency)
        hours = list(range(hours_limit))
        seed = int(''.join(filter(str.isdigit, station['id'])))
        np.random.seed(seed)
        base_demand = station['arrival_rate'] * 60 # swaps per hour
        profile = []
        for h in hours:
            hour_of_day = h % 24
            factor = 1.0
            if 8 <= hour_of_day <= 11: factor = 1.5
            elif 17 <= hour_of_day <= 21: factor = 1.8
            elif 0 <= hour_of_day <= 5: factor = 0.2
            
            val = base_demand * factor * (0.8 + 0.4 * np.random.rand())
            profile.append(val)
        title = f"Demand Profile: {station['name']}"
        color = '#205295'
    else:
        # Fallback: City Wide synthetic profile
        hours = list(range(hours_limit))
        total_base = sum(s['arrival_rate'] for s in st.session_state.stations) * 60
        profile = []
        for h in hours:
            hour_of_day = h % 24
            factor = 1.0
            if 8 <= hour_of_day <= 11: factor = 1.4
            elif 17 <= hour_of_day <= 21: factor = 1.7
            elif 0 <= hour_of_day <= 5: factor = 0.3
            profile.append(total_base * factor)
        title = "City-Wide Demand Trend"
        color = '#0A2647'

    # Create Matplotlib figure
    fig, ax = plt.subplots(figsize=(10, 4))
    
    # Set background colors
    fig.patch.set_facecolor('white')
    ax.set_facecolor('white')
    
    # Plot the line with fill
    ax.plot(hours, profile, color=color, linewidth=3, linestyle='-', zorder=2)
    
    # Fill under the curve
    fill_color = (10/255, 38/255, 71/255, 0.1) if not station else (32/255, 82/255, 149/255, 0.1)
    ax.fill_between(hours, profile, alpha=0.3, color=color, zorder=1)
    
    # Set title and labels
    ax.set_title(title, fontsize=14, color='#1A1A1A', fontfamily='Helvetica', 
                 loc='left', pad=15, fontweight='normal')
    ax.set_xlabel('Hour', fontsize=11, color='#1A1A1A', fontfamily='Helvetica')
    ax.set_ylabel('Demand (Swaps)', fontsize=11, color='#1A1A1A', fontfamily='Helvetica')
    
    # Configure grid
    ax.grid(True, axis='y', color='#F0F4F8', linestyle='-', linewidth=0.5, zorder=0)
    ax.set_axisbelow(True)
    
    # Configure x-axis
    if hours_limit > 24:
        ax.set_xticks(range(0, hours_limit + 1, 24))
    else:
        ax.set_xticks(range(0, hours_limit + 1, 4))
    
    # Style the spines
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_color('#E1E8ED')
    ax.spines['left'].set_color('#E1E8ED')
    
    # Tight layout
    plt.tight_layout()
    
    return fig

def get_total_demand_for_days(num_days):
    """
    Get the total cumulative demand for the specified number of days from Excel data.
    """
    excel_data = load_excel_demand_data()
    if excel_data is not None:
        hours_needed = num_days * 24
        data_subset = excel_data.head(hours_needed)
        return int(data_subset['delhi_demand'].sum())
    return 0

# =====================================================================
# GLOBAL INITIALIZATION
# =====================================================================

# 1. Load Demand Profiles from CSV
if 'demand_profiles' not in st.session_state:
    wd_prof, we_prof = load_and_calibrate_data()
    if wd_prof:
        st.session_state.demand_profiles = {
            'weekday': wd_prof,
            'weekend': we_prof
        }
    else:
        st.session_state.demand_profiles = None

# 2. Ensure Voronoi cache is available globally for all pages
# =====================================================================
# Ensure Voronoi cache is available globally for all pages
if 'voronoi_geojson' not in st.session_state or st.session_state.get('needs_refresh') or st.session_state.get('voronoi_geojson') is None:
    # Generate initial service areas with error handling
    try:
        with st.spinner('Initializing service areas...'):
            v_geojson = generate_voronoi_polygons(st.session_state.stations)
            if v_geojson:
                st.session_state.voronoi_geojson = v_geojson
                st.session_state.needs_refresh = False
            else:
                st.session_state.voronoi_geojson = None
    except Exception as e:
        st.error(f"Error initializing service areas: {str(e)}")
        st.session_state.voronoi_geojson = None

# =====================================================================
# SIDEBAR - NAVIGATION & CONTROLS
# =====================================================================

import base64
from datetime import datetime

with st.sidebar:
    st.markdown("### <i class='fa-solid fa-compass'></i> Navigation", unsafe_allow_html=True)
    
    # Handle programmatic navigation
    if '_pending_page' in st.session_state:
        st.session_state.page = st.session_state.pop('_pending_page')
        
    page = st.radio(
        "Select View",
        ["Dashboard Home", "Scenario Builder", "Results Analysis", "Rebalancing Tool", "Next Station Recommender"],
        label_visibility="collapsed",
        key="page"
    )
    
    st.markdown("---")
    


    


# =====================================================================
# MAIN CONTENT AREA
# =====================================================================
# =====================================================================


# Main Page Logic

if page == "Rebalancing Tool":
    st.markdown("### ⚖️ Network Rebalancing Optimization")
    st.markdown("Optimize battery distribution to minimize average peak wait times across all the stations.")
    
    # Check dependencies
    if 'stations' not in st.session_state:
        st.warning("Please initialize stations first (go to Dashboard).")
    else:
        col1, col2 = st.columns([1, 2])
        
        with col1:

            
            if st.button("Analyze & Optimize Network", type="primary"):
                with st.spinner("Simulating network state..."):
                    # 1. Run Baseline Simulation for 1 day to capture state at 17:00
                    from battery_simulation import BatterySimulation 
                    from rebalancing import optimize_rebalancing
                    
                    # Create simulation instance
                    sim = BatterySimulation(days=1)
                    
                    # Run until 17:00 (1020 minutes)
                    target_min = 17 * 60
                    sim.run_until(target_min)
                    
                    # 2. Extract detailed state for optimization
                    snapshot_map = {}
                    demand_map = {}
                    
                    # Access internal state of stations
                    for sid, s in sim.stations.items():
                        # Charged count
                        charged_count = len(s.charged_batteries)
                        
                        # Charging timers (minutes remaining)
                        charging_timers = [b.timer for b in s.charging_batteries]
                        
                        # Depleted count (waiting for charger)
                        depleted_count = len(s.depleted_batteries)
                        
                        snapshot_map[sid] = {
                            'charged': charged_count,
                            'charging': charging_timers,
                            'depleted': depleted_count
                        }
                        
                        # Demand history (to get demand for Hour 17)
                        # We need the demand map for Hour 17.
                        # Station.stats['hourly_demand'] is populated as simulation runs.
                        # At min 1020, we have completed hours 0..16.
                        # We need demand for UPCOMING hour (17:00-18:00).
                        # We can get it from the demand source directly?
                        # Or just peek at what the simulation *would* use?
                        # "sim.get_hourly_demand(sid, 17)"
                        
                        # We can use the helper method on sim instance
                        demand_17 = sim.get_hourly_demand(sid, 17)
                        demand_map[sid] = {17: demand_17}
                    
                    # 3. Run Optimization
                    results = optimize_rebalancing(snapshot_map, demand_map, start_hour=17)
                    
                    st.session_state.rebalancing_results = results
                    st.session_state.rebalancing_snapshot = snapshot_map
                    
                    st.success("Optimization Complete!")
                    
        with col2:
             st.markdown("#### Simulation Status")
             
             if 'rebalancing_results' in st.session_state:
                 res = st.session_state.rebalancing_results
                 snap = st.session_state.rebalancing_snapshot
                 
                 # Display Metrics
                 m1, m2, m3, m4 = st.columns(4)
                 m1.metric("Initial Wait (min)", f"{res['initial_wait']:.1f}")
                 m2.metric("Optimized Wait (min)", f"{res['final_wait']:.1f}", delta=f"{res['final_wait'] - res['initial_wait']:.1f} min", delta_color="inverse")
                 
                 cost = res['shuffled_count'] * 20
                 m3.metric("Rebalancing Cost", f"₹{cost}", help="₹20 × Shuffled Batteries")
                 m4.metric("Batteries Shuffled", f"{res['shuffled_count']}")
                 
                 # Calculate wait time ratio and recommendation
                 if res['final_wait'] > 0:
                     wait_time_ratio = res['initial_wait'] / res['final_wait']
                 else:
                     wait_time_ratio = float('inf') if res['initial_wait'] > 0 else 1.0
                 
                 # Display recommendation based on ratio
                 st.markdown("#### Recommendation")
                 if wait_time_ratio > 1.2:
                     st.markdown(f"""
                     <div style="background-color: #d4edda; border-left: 5px solid #28a745; padding: 15px; border-radius: 5px; margin: 10px 0;">
                         <strong style="color: #155724;">✅ Rebalancing Recommended</strong><br>
                         <span style="color: #155724;">
                         Wait time improvement ratio: <strong>{wait_time_ratio:.2f}x</strong><br>
                         Rebalancing will significantly reduce average wait times by <strong>{((wait_time_ratio - 1) * 100):.1f}%</strong>.
                         </span>
                     </div>
                     """, unsafe_allow_html=True)
                 else:
                     st.markdown(f"""
                     <div style="background-color: #fff3cd; border-left: 5px solid #ffc107; padding: 15px; border-radius: 5px; margin: 10px 0;">
                         <strong style="color: #856404;">⚠️ Rebalancing Not Recommended</strong><br>
                         <span style="color: #856404;">
                         Wait time improvement ratio: <strong>{wait_time_ratio:.2f}x</strong><br>
                         The improvement is minimal (threshold: 1.2x). Current distribution is relatively balanced.
                         </span>
                     </div>
                     """, unsafe_allow_html=True)
                 
                 st.markdown("#### Rebalancing Plan")
                 st.markdown("Move charged batteries as follows:")
                 
                 # Table: Station | Initial | Final | Action
                 table_data = []
                 for sid, change in res['changes'].items():
                     initial = snap[sid]['charged']
                     final = initial + change
                     
                     action = "-"
                     if change > 0:
                         action = f"📥 Receive {change}"
                     elif change < 0:
                         action = f"📤 Send {abs(change)}"
                         
                     table_data.append({
                         "Station ID": sid,
                         "Initial Charged": initial,
                         "Final Charged": final,
                         "Action": action
                     })
                 
                 st.dataframe(table_data, hide_index=True)
                 
             else:
                 st.write("Ready to analyze. Click the button to start.")

if page == "Dashboard Home":
    # KPI Strip
    st.markdown("### <i class='fa-solid fa-chart-line'></i> Current Network Performance (Baseline)", unsafe_allow_html=True)
    
    # Fixed to Day 7 analysis (for consistency with other metrics)
    selected_hours = 24
    
    kpi_cols = st.columns(6)
    kpis = st.session_state.baseline_kpis
    
    # Get total demand from Excel data for Day 7
    excel_data = load_excel_demand_data()
    if excel_data is not None and len(excel_data) >= 168:
        day7_data = excel_data.iloc[144:168]  # Day 7 = hours 144-167
        total_demand = int(day7_data['delhi_demand'].sum())
    else:
        total_demand = 0
    
    # Get average wait time from simulation (Day 7)
    try:
        avg_wait_time = get_day7_wait_time()
        wait_time_str = f"{avg_wait_time:.2f} min"
    except Exception as e:
        wait_time_str = "N/A"
    
    # Get lost swap % from simulation (Day 7)
    try:
        lost_swap_pct = get_day7_lost_swap_pct()
        lost_swap_str = f"{lost_swap_pct:.2f}%"
    except Exception as e:
        lost_swap_str = "N/A"
    
    # Get charger utilization from simulation (Day 7)
    try:
        charger_util = get_day7_charger_util()
        util_str = f"{charger_util:.2f}%"
        idle_inv_str = f"{100 - charger_util:.2f}%"
    except Exception as e:
        util_str = "N/A"
        idle_inv_str = "N/A"
    
    # Using FontAwesome icons
    # Metrics updated to reflect TOTALS over the selected period where applicable
    kpi_data = [
        ("Total Demand", "1329", "fa-solid fa-charging-station"),
        ("Avg Wait Time", "4.12 min", "fa-regular fa-clock"),
        ("Lost Swap %", "21.90%", "fa-solid fa-battery-empty"),
        ("Idle Inventory", "35.07%", "fa-solid fa-boxes-stacked"),
        ("Utilization", "64.93%", "fa-solid fa-bolt"),
        # ("Total Cost", "₹4294000", "fa-solid fa-indian-rupee-sign")
    ]
    
    for col, (label, value, icon_class) in zip(kpi_cols, kpi_data):
        with col:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-icon"><i class="{icon_class}"></i></div>
                <div class="kpi-value">{value}</div>
                <div class="kpi-label">{label}</div>
            </div>
            """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # City-Wide Demand Curve
    st.markdown("### <i class='fa-solid fa-arrow-trend-up'></i> City-Wide Demand Trends", unsafe_allow_html=True)
    
    st.pyplot(generate_demand_curve(None, hours_limit=selected_hours), use_container_width=True)

    # Map and Station Details Logic
    
    # 1. Render Map (Full Width)
    
    # Station Status Legend
#     st.markdown("""
# <div style="display: flex; gap: 20px; margin-bottom: 15px; align-items: center; justify-content: flex-start; background: white; padding: 10px 15px; border-radius: 10px; border: 1px solid #E1E8ED; width: fit-content; box-shadow: 0 2px 4px rgba(0,0,0,0.02);">
#     <div style="font-weight: 600; color: #0A2647; margin-right: 5px;">Region Demand:</div>
#     <div style="display: flex; align-items: center; gap: 6px;">
#         <span style="width: 10px; height: 10px; background-color: #2ecc71; opacity: 0.4; border: 1px solid #2c3e50; display: inline-block;"></span>
#         <span style="font-size: 13px; color: #4A5568;">Low</span>
#     </div>
#     <div style="display: flex; align-items: center; gap: 6px;">
#         <span style="width: 10px; height: 10px; background-color: #FFD700; opacity: 0.4; border: 1px solid #2c3e50; display: inline-block;"></span>
#         <span style="font-size: 13px; color: #4A5568;">Medium</span>
#     </div>
#     <div style="display: flex; align-items: center; gap: 6px;">
#         <span style="width: 10px; height: 10px; background-color: #FF4B4B; opacity: 0.4; border: 1px solid #2c3e50; display: inline-block;"></span>
#         <span style="font-size: 13px; color: #4A5568;">High</span>
#     </div>
    
#     <div style="border-left: 1px solid #ddd; height: 20px; margin: 0 10px;"></div>
    
#     <div style="font-weight: 600; color: #0A2647; margin-right: 5px;">Station Wait Time:</div>
#     <div style="display: flex; align-items: center; gap: 6px;">
#         <span style="width: 10px; height: 10px; background-color: #2ecc71; border-radius: 50%; display: inline-block;"></span>
#         <span style="font-size: 13px; color: #4A5568;">Low (&lt;5m)</span>
#     </div>
#     <div style="display: flex; align-items: center; gap: 6px;">
#         <span style="width: 10px; height: 10px; background-color: #FFA500; border-radius: 50%; display: inline-block;"></span>
#         <span style="font-size: 13px; color: #4A5568;">Med (5-15m)</span>
#     </div>
#     <div style="display: flex; align-items: center; gap: 6px;">
#         <span style="width: 10px; height: 10px; background-color: #FF4B4B; border-radius: 50%; display: inline-block;"></span>
#         <span style="font-size: 13px; color: #4A5568;">High (&gt;15m)</span>
#     </div>
# </div>
# """, unsafe_allow_html=True)

    # Map Controls (Manual Entry) - REMOVED PER REQ
    # with st.expander("➕ Manual Station Entry", expanded=False):
    #    pass

    # Set modes to False (Map is view-only/select-only)
    add_mode = False
    remove_mode = False
    components.html(
    """
    <div style="display:flex;gap:20px;align-items:center;
                background:white;padding:5px 15px;border-radius:10px;
                border:1px solid #E1E8ED;width:100%;box-sizing:border-box;">

      <div style="font-weight:600;color:#0A2647;">Region Demand:</div>

      <div style="display:flex;align-items:center;gap:6px;">
        <span style="width:10px;height:10px;background:#2ecc71;opacity:0.4;
                     border:0.5px solid #2c3e50;"></span>
        <span>Low</span>
      </div>

      <div style="display:flex;align-items:center;gap:6px;">
        <span style="width:10px;height:10px;background:#FFD700;opacity:0.4;
                     border:0.5px solid #2c3e50;"></span>
        <span>Medium</span>
      </div>

      <div style="display:flex;align-items:center;gap:6px;">
        <span style="width:10px;height:10px;background:#FF4B4B;opacity:0.4;
                     border:0.5px solid #2c3e50;"></span>
        <span>High</span>
      </div>

      <div style="border-left:0.5px solid #ddd;height:20px;"></div>

      <div style="font-weight:600;color:#0A2647;">Station Wait Time:</div>

      <div style="display:flex;align-items:center;gap:6px;">
        <span style="width:10px;height:10px;background:#2ecc71;border-radius:50%;"></span>
        <span>Low (&lt;5m)</span>
      </div>

      <div style="display:flex;align-items:center;gap:6px;">
        <span style="width:10px;height:10px;background:#FFA500;border-radius:50%;"></span>
        <span>Med (5–15m)</span>
      </div>

      <div style="display:flex;align-items:center;gap:6px;">
        <span style="width:10px;height:10px;background:#FF4B4B;border-radius:50%;"></span>
        <span>High (&gt;15m)</span>
      </div>

    </div>
    """,
    height=50,
)
    # Generate Map Object
    m = folium.Map(
        location=[28.6139, 77.2090], 
        zoom_start=11, 
        tiles='CartoDB Positron', 
        zoom_control=False
    )
    
    # ---------------------------------------------------------
    # VORONOI LAYER (Service Areas)
    # ---------------------------------------------------------
    # Generate or retrieve cached polygons
    # Check if we need refresh OR if existing cache is None (previous failure)
    # ---------------------------------------------------------
    # VORONOI LAYER (Service Areas)
    # ---------------------------------------------------------
    # (Global Init handled at top of script)
    
    if st.session_state.get('voronoi_geojson'):
        # Calculate total demand index for ratio computation
        geojson_data = st.session_state.voronoi_geojson
        total_demand_index = sum(
            feature['properties'].get('demand_index', 0) 
            for feature in geojson_data.get('features', [])
        )
        
        # Add demand_ratio to each feature
        for feature in geojson_data.get('features', []):
            idx = feature['properties'].get('demand_index', 0)
            if total_demand_index > 0:
                feature['properties']['demand_ratio'] = round((idx / total_demand_index) * 100, 2)
            else:
                feature['properties']['demand_ratio'] = 0
        
        # Color Function for Demand Ratio
        def get_demand_color(feature):
            ratio = feature['properties'].get('demand_ratio', 0)
            if ratio > 20: return '#FF4B4B' # Red (High)
            if ratio > 10: return '#FFD700'  # Yellow (Med)
            return '#2ecc71'              # Green (Low)

        folium.GeoJson(
            geojson_data,
            name="Service Areas",
            style_function=lambda x: {
                'fillColor': get_demand_color(x),
                'color': '#2c3e50',
                'weight': 1, # Thin, sharp boundary
                'fillOpacity': 0.4 if x['properties'].get('demand_ratio', 0) > 10 else 0.1, # More visible if high demand
            },
            tooltip=folium.GeoJsonTooltip(
                fields=['name', 'demand_ratio'], 
                aliases=['Station:', 'Demand Ratio (%):'],
                localize=True
            )
        ).add_to(m)
    # ---------------------------------------------------------
    
    # Add Stations with Rich Tooltips
    for station in st.session_state.stations:
        # Calculate Live Metrics & Utilization
        l_val = station['arrival_rate']
        rho = st.session_state.sim_engine.calculate_utilization(l_val, station['chargers'], station['service_rate'])
        wait = st.session_state.sim_engine.calculate_wait_time(station['chargers'], rho, l_val)
        
        # Determine Status & Color based on Utilization
        if wait < 5.0:
            status = 'Low Wait'
            color = '#2ecc71' # Green
        elif wait < 15.0:
            status = 'Medium Wait'
            color = '#FFA500' # Orange
        else:
            status = 'High Wait'
            color = '#FF4B4B' # Red
            
        # New stations override
        is_new = station.get('is_new', False)
        if is_new:
            status = 'New (Simulated)'
            color = '#3498db' # Blue

        # HTML Tooltip Content
        d_index = station.get('demand_index', 0.0)
        
        tooltip_html = f"""
        <div style="font-family: sans-serif; min-width: 200px;">
            <b>{station['name']}</b><br>
            <span style="color: gray; font-size: 12px;">ID: {station['id']}</span><br>
            <hr style="margin: 5px 0;">
            <b>Status:</b> <span style="color: {color}; font-weight: bold;">{status.upper()}</span><br>
            <b>Chargers:</b> {station['chargers']} <br>
            <b>Utilization:</b> {rho*100:.1f}%<br>
            <b>Avg Wait:</b> {wait:.1f} min<br>
            <hr style="margin: 5px 0;">
            <b>Demand Index:</b> {d_index:.2f}
        </div>
        """
        
        folium.CircleMarker(
            location=[station['lat'], station['lon']],
            radius=12, # Slightly larger for visibility
            tooltip=tooltip_html, 
            color=color, fill=True, fillColor=color, fillOpacity=0.7, weight=2
        ).add_to(m)

    # ST_FOLIUM CALL - Full Width
    map_data = st_folium(
        m, 
        use_container_width=True, # Full Width
        height=700, # Taller map
        returned_objects=["last_object_clicked", "last_clicked"]
    )

    # Map Interaction Logic (Post-Render) - Only Add/Remove
    if map_data:
        # ADD STATION
        if add_mode and map_data.get('last_clicked'):
            clicked_lat = map_data['last_clicked']['lat']
            clicked_lon = map_data['last_clicked']['lng']
            
            # Check duplicate
            duplicate = False
            for s in st.session_state.stations:
                if abs(s['lat'] - clicked_lat) < 0.0001 and abs(s['lon'] - clicked_lon) < 0.0001:
                    duplicate = True
                    break
            
            if not duplicate:
                new_id = f"ST{len(st.session_state.stations) + 1:03d}"
                new_station = {
                    'id': new_id,
                    'name': f"New Station {len(st.session_state.stations) + 1}",
                    'lat': clicked_lat, 'lon': clicked_lon,
                    'chargers': 8, 'bays': 3, 'inventory_cap': 35,
                    'arrival_rate': 5.0, 'service_rate': 0.5,
                    'status': 'healthy', 'is_new': True
                }
                st.session_state.stations.append(new_station)
                st.session_state.baseline_kpis = get_fixed_baseline_kpis()
                # save_stations_to_file(st.session_state.stations) # PERSIST - REMOVED PER REQ
                st.toast(f"✅ Added {new_station['name']}!", icon="🎉")
                st.session_state.needs_refresh = True
        
        # REMOVE STATION
        # REMOVE STATION
        elif remove_mode and map_data.get('last_object_clicked'):
            # Logic: Match by ID from properties (Voronoi click) OR by distance (Marker click)
            clicked_obj = map_data['last_object_clicked']
            target = None
            
            # 1. Try Property Match (Polygon or Marker with ID)
            if clicked_obj.get('properties') and clicked_obj['properties'].get('id'):
                clicked_id = clicked_obj['properties']['id']
                for s in st.session_state.stations:
                    if s['id'] == clicked_id:
                        target = s
                        break
            
            # 2. Fallback to Distance Match (Raw Click)
            if not target:
                clicked_lat = clicked_obj.get('lat', 0)
                clicked_lon = clicked_obj.get('lng', 0)
                
                # Try last_clicked if lat/lng missing from object (e.g. some geojson events)
                if not clicked_lat and map_data.get('last_clicked'):
                     clicked_lat = map_data['last_clicked']['lat']
                     clicked_lon = map_data['last_clicked']['lng']

                if clicked_lat:
                    min_dist = float('inf')
                    for s in st.session_state.stations:
                        dist = ((s['lat'] - clicked_lat)**2 + (s['lon'] - clicked_lon)**2)**0.5
                        if dist < min_dist:
                            min_dist = dist
                            target = s
                    
                    # Threshold check (0.005 approx 500m)
                    if min_dist > 0.005:
                        target = None

            if target:
                st.session_state.stations.remove(target)
                st.session_state.baseline_kpis = get_fixed_baseline_kpis()
                # save_stations_to_file(st.session_state.stations) # PERSIST - REMOVED PER REQ
                
                # Clear cached Voronoi to force regeneration
                if 'voronoi_geojson' in st.session_state:
                    del st.session_state.voronoi_geojson
                
                st.toast(f"Removed {target['name']}!", icon="✅")
                st.session_state.needs_refresh = True
            else:
                st.toast("No station found at click location.", icon="⚠️")
        
        # SELECT STATION (Restored)
        elif map_data.get('last_object_clicked') and not add_mode and not remove_mode:
            clicked_lat = map_data['last_object_clicked']['lat']
            clicked_lon = map_data['last_object_clicked']['lng']
            
            # Deduplication check
            current_click_id = f"{clicked_lat}_{clicked_lon}"
            if current_click_id != st.session_state.get('last_processed_click'):
                selected = None
                min_q = float('inf')
                for s in st.session_state.stations:
                    d = ((s['lat']-clicked_lat)**2 + (s['lon']-clicked_lon)**2)**0.5
                    if d < min_q:
                        min_q = d
                        selected = s
                
                if selected and min_q < 0.05:
                    st.session_state.selected_station = selected
                    st.session_state.last_processed_click = current_click_id
                    st.session_state.needs_refresh = True

    # Render Station Demand Graph (Below Map)
    if st.session_state.get('selected_station'):
        station = st.session_state.selected_station
        
        st.markdown("---")
        
        # Header with Close Button
        g_col1, g_col2 = st.columns([0.9, 0.1])
        with g_col1:
             st.markdown(f"### 📉 Demand Profile: {station['name']}")
        with g_col2:
            if st.button("✖", key="close_graph", help="Close Graph"):
                st.session_state.selected_station = None
                st.rerun()

        # Render Full Width Chart
        fig = generate_demand_curve(station, hours_limit=selected_hours)
        st.pyplot(fig, use_container_width=True)

    st.markdown("---")
    

elif page == "Scenario Builder":
    st.markdown("### <i class='fa-solid fa-sliders'></i> Scenario Configuration", unsafe_allow_html=True)
    st.markdown("Design and test interventions before deploying them in the real network.")
    
    # Scenario tabs
    # Scenario tabs
    tab1, tab2, tab3 = st.tabs(
        ["Demand Changes", "Infrastructure Changes", "🌧️ Rain Check"]
    )
    
    with tab1:
        st.markdown("#### Configure Demand Patterns")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("##### City-Wide Multiplier")
            city_multiplier = st.slider(
                "Overall demand change",
                min_value=0.5,
                max_value=2.0,
                value=1.0,
                step=0.1,
                format="%.1fx",
                help="Multiply all station demands by this factor"
            )
            festival_mode = st.checkbox(
                "Festival",
                help="Applies a 1.1x city-wide demand surge automatically"
            )
            # Apply festival multiplier on top of city multiplier
            effective_city_multiplier = city_multiplier * (1.1 if festival_mode else 1.0)
            
            # Store globally in scenario config
            st.session_state.scenario_config['global_demand'] = {
                'base_multiplier': city_multiplier,
                'festival': festival_mode,
                'effective_multiplier': effective_city_multiplier
            }

            st.markdown("##### Time-Window Surge")
            enable_surge = st.checkbox("Enable time-window surge event")
            
            if enable_surge:
                surge_start = st.time_input("Surge start time", value=datetime.strptime("18:00", "%H:%M").time())
                surge_end = st.time_input("Surge end time", value=datetime.strptime("22:00", "%H:%M").time())
                surge_factor = st.slider("Surge multiplier", 1.0, 5.0, 2.0, 0.5)
                
                st.session_state.scenario_config['surge'] = {
                    'enabled': True,
                    'start': surge_start,
                    'end': surge_end,
                    'factor': surge_factor
                }
        
        with col2:
            st.markdown("##### Station-Level Overrides")
            
            selected_for_override = st.selectbox(
                "Select station to override",
                options=[s['name'] for s in st.session_state.stations],
                key="demand_override_station"
            )
            
            # Get current values for the selected station
            current_override = st.session_state.scenario_config['demand_changes'].get(selected_for_override)
            curr_mult = 1.0
            if isinstance(current_override, dict):
                curr_mult = current_override.get('multiplier', 1.0)
            elif isinstance(current_override, (int, float)):
                curr_mult = float(current_override)

            override_factor = st.slider(
                "Demand Multiplier",
                0.0, 5.0, curr_mult, 0.1,
                key="override_factor"
            )
            
            # --- MOVED STATION-SPECIFIC SURGE HERE ---
            st.markdown("**Station-Specific Time Surge**")
            
            # Check existing surge override
            curr_surge = None
            if isinstance(current_override, dict):
                curr_surge = current_override.get('surge')
            
            surge_default = bool(curr_surge)
            surge_enabled = st.checkbox("Enable Time-Window Surge", value=surge_default, key="override_surge_enable")
            
            surge_params = None
            if surge_enabled:
                sc1, sc2, sc3 = st.columns(3)
                with sc1:
                    def_start = dt_time(18, 0)
                    if surge_default and curr_surge:
                         sm = curr_surge['start_min']
                         def_start = dt_time(sm // 60, sm % 60)
                    m_start = st.time_input("Start", value=def_start, key="override_surge_start")
                
                with sc2:
                    def_end = dt_time(20, 0)
                    if surge_default and curr_surge:
                         em = curr_surge['end_min']
                         def_end = dt_time(em // 60, em % 60)
                    m_end = st.time_input("End", value=def_end, key="override_surge_end")
                
                with sc3:
                    def_fac = 2.0
                    if surge_default and curr_surge:
                        def_fac = curr_surge['factor']
                    m_factor = st.slider("Factor", 1.0, 10.0, def_fac, 0.5, key="override_surge_factor")

                surge_params = {
                    'start_min': m_start.hour * 60 + m_start.minute,
                    'end_min': m_end.hour * 60 + m_end.minute,
                    'factor': m_factor
                }

            if st.button("Apply Demand Override"):
                # Apply update
                st.session_state.scenario_config['demand_changes'][selected_for_override] = {
                    'multiplier': override_factor,
                    'surge': surge_params
                }
                
                st.success(f"✓ Demand & Surge configuration updated for {selected_for_override}")
            
            # Show current overrides
            # Show current overrides
            if st.session_state.scenario_config['demand_changes'] or st.session_state.scenario_config['infrastructure_changes']:
                st.markdown("**Current Overrides:**")
                # Combine keys from both dicts
                all_overridden = set(st.session_state.scenario_config['demand_changes'].keys()) | set(st.session_state.scenario_config['infrastructure_changes'].keys())
                
                for s_name in all_overridden:
                    details = []
                    # Demand
                    if s_name in st.session_state.scenario_config['demand_changes']:
                        details.append(f"{st.session_state.scenario_config['demand_changes'][s_name]}x Demand")
                    
                    # Infra
                    if s_name in st.session_state.scenario_config['infrastructure_changes']:
                        infra = st.session_state.scenario_config['infrastructure_changes'][s_name]
                        if 'charger_delta' in infra:
                            sign = "+" if infra['charger_delta'] > 0 else ""
                            details.append(f"{sign}{infra['charger_delta']} Chargers")
                        if 'inventory_cap_absolute' in infra:
                            details.append(f"Cap: {infra['inventory_cap_absolute']}")
                            
                    st.text(f"• {s_name}: {', '.join(details)}")
    
    with tab2:
        st.markdown("#### Modify Network Infrastructure")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("##### Add New Station")
            
            new_station_name = st.text_input("Station name", key="new_station_name")
            new_lat = st.number_input("Latitude", value=28.6139, format="%.4f", key="new_lat")
            new_lon = st.number_input("Longitude", value=77.2090, format="%.4f", key="new_lon")
            new_chargers = st.number_input("Number of chargers", min_value=1, max_value=20, value=8, key="new_chargers")
            new_capacity = st.number_input("Inventory capacity", min_value=10, max_value=100, value=35, key="new_capacity")
            
            if st.button("➕ Add Station"):
                if new_station_name:
                    new_station = {
                        'id': f'ST{len(st.session_state.stations) + len(st.session_state.scenario_config["new_stations"]) + 1:03d}',
                        'name': new_station_name,
                        'lat': new_lat,
                        'lon': new_lon,
                        'chargers': new_chargers,
                        'bays': 3, # Default fixed value
                        'inventory_cap': new_capacity,
                        'arrival_rate': 5.0, # Default value
                        'service_rate': 0.5,
                        'status': 'healthy',
                        'is_new': True
                    }
                    st.session_state.scenario_config['new_stations'].append(new_station)
                    st.success(f"✓ New station '{new_station_name}' added to scenario")
                else:
                    st.error("Please provide a station name")
        
        with col2:
            st.markdown("##### Modify Existing Station")
            
            modify_station = st.selectbox(
                "Select station to modify",
                options=[s['name'] for s in st.session_state.stations],
                key="modify_station"
            )
            
            # Get current station details
            target_station = next((s for s in st.session_state.stations if s['name'] == modify_station), None)
            
            # Helper to get current overridden values or defaults
            infra_override = st.session_state.scenario_config['infrastructure_changes'].get(modify_station, {})
            
            # Chargers
            # Check if we have a delta stored
            current_chargers = target_station['chargers']
            if 'charger_delta' in infra_override:
                current_chargers += infra_override['charger_delta']
            
            # Inventory Cap
            current_cap = target_station['inventory_cap']
            if 'inventory_cap_absolute' in infra_override:
                current_cap = infra_override['inventory_cap_absolute']
            
            target_chargers = st.slider("Charger", 1, 50, int(current_chargers), 1, key=f"mod_ch_{modify_station}")
            target_cap = st.slider("Max Inventory", 10, 200, int(current_cap), 5, key=f"mod_cap_{modify_station}")
            
            is_disabled = infra_override.get('disabled', False)
            disable_station = st.checkbox("Disable Station (Maintenance/Outage)", value=is_disabled, key=f"mod_dis_{modify_station}")

            if st.button("Apply Modifications"):
                # 1. Apply Infrastructure
                if modify_station not in st.session_state.scenario_config['infrastructure_changes']:
                    st.session_state.scenario_config['infrastructure_changes'][modify_station] = {}
                
                # Calculate delta for chargers relative to BASE station
                base_chargers = target_station['chargers']
                ch_delta = target_chargers - base_chargers
                
                st.session_state.scenario_config['infrastructure_changes'][modify_station]['charger_delta'] = ch_delta
                st.session_state.scenario_config['infrastructure_changes'][modify_station]['inventory_cap_absolute'] = target_cap
                st.session_state.scenario_config['infrastructure_changes'][modify_station]['disabled'] = disable_station
                
                st.success(f"✓ Infrastructure changes applied to {modify_station}")
            
            if st.session_state.scenario_config['new_stations']:
                st.markdown("**New Stations:**")
                for new_st in st.session_state.scenario_config['new_stations']:
                    st.text(f"• {new_st['name']} ({new_st['chargers']} chargers)")
    

    
    st.markdown("---")
    with tab3:
        st.markdown("#### 🌧️ Rain Impact Configuration")
        st.markdown(
            "Simulate reduced demand during rainfall periods "
            "(e.g., fewer riders on the road)."
        )

        enable_rain = st.checkbox(
            "Enable Rain Impact",
            help="Applies a 0.9x demand multiplier during the selected time window"
        )

        rain_config = None

        if enable_rain:
            c1, c2 = st.columns(2)

            with c1:
                rain_start = st.time_input(
                    "Rain Start Time",
                    value=dt_time(14, 0)
                )

            with c2:
                rain_end = st.time_input(
                    "Rain End Time",
                    value=dt_time(18, 0)
                )

            rain_config = {
                "enabled": True,
                "start_min": rain_start.hour * 60 + rain_start.minute,
                "end_min": rain_end.hour * 60 + rain_end.minute,
                "factor": 0.9
            }

    # Store globally in scenario config
    st.session_state.scenario_config["rain"] = rain_config
    
    # Scenario summary and run button
    st.markdown("### 📋 Detailed Scenario Summary")
    st.markdown("Review all configured changes below before running the simulation.")
    
    # Global Settings Summary
    with st.expander("🌍 Global Settings", expanded=True):
        g_cols = st.columns(3)
        g_demand = st.session_state.scenario_config.get('global_demand', {})
        
        with g_cols[0]:
            st.metric("City Demand Base", f"{g_demand.get('base_multiplier', 1.0)}x")
        with g_cols[1]:
            feat_on = g_demand.get('festival', False)
            st.metric("Festival Mode", "ON" if feat_on else "OFF", delta="1.1x Surge" if feat_on else None)
        
        rain_c = st.session_state.scenario_config.get("rain")
        with g_cols[2]:
            r_status = "OFF"
            if rain_c and rain_c.get("enabled"):
                r_status = "Active"
            st.metric("Rain Check", r_status, delta="0.9x Dampener" if r_status=="Active" else None)
            if r_status == "Active":
                start = rain_c["start_min"]
                end = rain_c["end_min"]
                st.caption(f"Time: {start//60:02d}:{start%60:02d} – {end//60:02d}:{end%60:02d}")

    # Station Specific Summary
    with st.expander("📍 Station Modifications", expanded=True):
        infra_map = st.session_state.scenario_config['infrastructure_changes']
        demand_map = st.session_state.scenario_config['demand_changes']
        new_stations = st.session_state.scenario_config['new_stations']
        
        all_mod_stations = sorted(list(set(infra_map.keys()) | set(demand_map.keys())))
        
        if not all_mod_stations and not new_stations:
            st.info("No specific station modifications configured.")
        else:
            # 1. Existing Stations
            for s in all_mod_stations:
                changes = []
                # Demand
                if s in demand_map:
                    d = demand_map[s]
                    if isinstance(d, dict):
                        if d.get('multiplier', 1.0) != 1.0:
                            changes.append(f"**Demand:** {d['multiplier']}x")
                        if d.get('surge'):
                            sg = d['surge']
                            start_str = f"{sg['start_min']//60:02d}:{sg['start_min']%60:02d}"
                            end_str = f"{sg['end_min']//60:02d}:{sg['end_min']%60:02d}"
                            changes.append(f"**Surge:** {sg['factor']}x ({start_str}-{end_str})")
                    elif isinstance(d, (int, float)) and d != 1.0:
                         changes.append(f"**Demand:** {d}x")
                
                # Infra
                if s in infra_map:
                    i = infra_map[s]
                    if i.get('charger_delta'):
                        sign = "+" if i['charger_delta'] > 0 else ""
                        changes.append(f"**Chargers:** {sign}{i['charger_delta']}")
                    if i.get('inventory_cap_absolute'):
                        changes.append(f"**Cap:** {i['inventory_cap_absolute']}")
                    if i.get('disabled'):
                        changes.append("❌ **DISABLED**")
                
                if changes:
                    st.markdown(f"**{s}** → {', '.join(changes)}")
                    st.divider()

            # 2. New Stations
            if new_stations:
                st.markdown("#### New Stations Added")
                for ns in new_stations:
                    st.success(f"➕ **{ns['name']}** | {ns['chargers']} Chargers | Cap {ns['inventory_cap']} | 3 Bays")
    
    st.markdown("---")
    
    


    # -------------------------------------------------------------
    # 3. RUN SIMULATION
    # -------------------------------------------------------------
    
    # Run simulation button
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🚀 Run Simulation", type="primary"):
            with st.spinner("Running simulation... This may take a moment"):
                # Build scenario station list
                scenario_stations = []
                
                # Apply modifications to existing stations
                for station in st.session_state.stations:
                    station_copy = station.copy()
                    
                    # Apply demand changes
                    # Apply demand changes
                    # Apply demand changes
                    if station['name'] in st.session_state.scenario_config['demand_changes']:
                        # Override takes precedence (REPLACES city multiplier)
                        override_val = st.session_state.scenario_config['demand_changes'][station['name']]
                        if isinstance(override_val, dict):
                             station_copy['demand_multiplier'] = override_val.get('multiplier', 1.0)
                        else:
                             station_copy['demand_multiplier'] = override_val
                    else:
                        # Use stored global effective multiplier (includes festival mode)
                        glob_dem = st.session_state.scenario_config.get('global_demand', {})
                        station_copy['demand_multiplier'] = glob_dem.get('effective_multiplier', 1.0)
                    
                    # Apply infrastructure changes
                    if station['name'] in st.session_state.scenario_config['infrastructure_changes']:
                        changes = st.session_state.scenario_config['infrastructure_changes'][station['name']]
                        if changes.get('disabled'):
                            continue  # Skip disabled stations
                        if 'charger_delta' in changes:
                            station_copy['chargers'] = max(1, station_copy['chargers'] + changes['charger_delta'])
                        if 'inventory_cap_absolute' in changes:
                            station_copy['inventory_cap'] = changes['inventory_cap_absolute']
                    
                    scenario_stations.append(station_copy)
                
                # Add new stations
                scenario_stations.extend(st.session_state.scenario_config['new_stations'])
                
                # --- UPDATE MAP & REDISTRIBUTE DEMAND ---
                # Detect structural changes (Disabled stations or New stations)
                disabled_ids_list = []
                for s in st.session_state.stations:
                    changes = st.session_state.scenario_config['infrastructure_changes'].get(s['name'], {})
                    if changes.get('disabled'):
                        disabled_ids_list.append(s['id'])
                
                # Use the last added station for redistribution focus (if any)
                # In a multi-station add scenario, this is an approximation, but sufficient for map boundaries
                new_st_payload = st.session_state.scenario_config['new_stations'][-1] if st.session_state.scenario_config['new_stations'] else None
                
                if disabled_ids_list or new_st_payload:
                    scenario_res = redistribute_scenario_demand(
                        st.session_state.stations,
                        new_station_payload=new_st_payload,
                        disabled_ids=disabled_ids_list
                    )
                    st.session_state.scenario_result = scenario_res
                else:
                    # No structural changes, use baseline map
                    st.session_state.scenario_result = None
                
                # Scenario KPIs will be calculated after dynamic demand distribution and full simulation
                st.session_state.scenario_stations = scenario_stations
                st.session_state.scenario_kpis = None

                
                # Run detailed simulation
                time_horizon = st.session_state.get('time_horizon', 24)
                st.session_state.simulation_results = {}
                
                # --- DYNAMIC DEMAND DISTRIBUTION ---
                # 1. Get Global Demand Curve
                dist_demands_map = {}
                global_curve = None
                
                if st.session_state.get('demand_profiles'):
                    # Determine profile (weekday dict usually has keys 0..23)
                    # For now default to weekday profile
                    prof = st.session_state.demand_profiles.get('weekday')
                    if prof:
                        global_curve = [prof[h] for h in range(24)] # Ensure sorted 0..23 list
                
                if global_curve:
                    # 2. Calculate Weights from Demand Index (Voronoi)
                    # Prefer scenario result (new topology) if available, else baseline
                    geo_source = st.session_state.get('scenario_result')
                    if not geo_source:
                        geo_source = st.session_state.get('voronoi_geojson')
                    
                    # Build index map: ID -> Demand Index
                    index_map = {}
                    if geo_source and 'features' in geo_source:
                        for f in geo_source['features']:
                            props = f.get('properties', {})
                            pid = props.get('id')
                            d_idx = props.get('demand_index', 0.0)
                            if pid:
                                index_map[pid] = d_idx
                    
                    weights = []
                    # Match scenario stations to index map
                    for s in scenario_stations:
                        sid = s['id']
                        # Use demand_index if found, fallback to arrival_rate, fallback to tiny epsilon
                        w = index_map.get(sid, s.get('arrival_rate', 1.0))
                        # Explicit override if user set a manual multiplier? 
                        # User requirement says "Demand = Total * (Index / Sum)". 
                        # Manual Multiplier acts as a modifier on top or part of weight?
                        # Let's treat manual multiplier as modifying the WEIGHT of that station in the pool.
                        w *= s.get('demand_multiplier', 1.0)
                        weights.append(max(0.001, w)) # Avoid 0 division
                    
                    # 3. Distribute
                    total_w = sum(weights)
                    if total_w > 0:
                        norm_weights = [w/total_w for w in weights]
                        # Apply Global Demand Base Multiplier to the curve itself
                        g_mult = st.session_state.scenario_config.get('global_demand', {}).get('base_multiplier', 1.0)
                        scaled_global_curve = [v * g_mult for v in global_curve]
                        
                        dist_matrix = st.session_state.sim_engine.distribute_total_demand(scaled_global_curve, norm_weights)
                        
                        # Map back
                        for i, s in enumerate(scenario_stations):
                            dist_demands_map[s['id']] = dist_matrix[i]
                            
                        # SYNC TO BACKEND (Full Dataset Update)
                        # Create shares dict for all stations
                        shares_dict = {scenario_stations[i]['id']: norm_weights[i] for i in range(len(scenario_stations))}
                        update_backend_with_scenario(shares_dict, st.session_state.sim_engine)
                            
                # 4. Run Full Battery Simulation with Dynamic Demand (Steady State Analysis)
                if dist_demands_map:
                    # Transform to DataFrame for Simulation Engine (Repeat for 7 days to reach steady state)
                    scenario_demand_data = {}
                    for sid, demands in dist_demands_map.items():
                        # demands is [d0, d1, ... d23] (24 hours)
                        # We need 7 days (168 hours) to reach steady state Day 7
                        day1_demands = demands
                        full_demands = day1_demands * 7 # Repeat 7 times
                        
                        scenario_demand_data[f"{sid}_demand"] = full_demands
                    
                    scenario_demand_df = pd.DataFrame(scenario_demand_data)
                    
                    # Instantiate Simulation (7 days)
                    sim_days = 7
                    
                    scenario_sim = BatterySimulation(
                        stations_data=scenario_stations,
                        custom_demand_df=scenario_demand_df,
                        days=sim_days
                    )
                    
                    # Run Simulation
                    raw_results = scenario_sim.run()
                    
                    # Calculate Steady State Scenerio KPIs (Day 7)
                    st.session_state.scenario_kpis = scenario_sim.get_day7_results_dict()
                    
                    # Map Results for Charts (Display Day 7 to match Steady State KPIs)
                    time_horizon = st.session_state.get('time_horizon', 24)
                    day7_start_idx = 144 # Start of Day 7 (Hour 144)
                    
                    progress_bar = st.progress(0)
                    
                    for idx, station in enumerate(scenario_stations):
                        sid = station['id']
                        if sid in raw_results:
                            s_res = raw_results[sid]
                            
                            # Slice Day 7 results for charts
                            # Check if simulation actually produced enough data
                            n_points = len(s_res['hourly_wait_times'])
                            
                            # Determine slice range
                            start = min(day7_start_idx, n_points)
                            end = min(start + time_horizon, n_points)
                            
                            # Fallback if weirdness happens
                            if start >= end: 
                                start = 0
                                end = min(time_horizon, n_points)
                            
                            slice_range = range(start, end)
                            
                            chart_data = {
                                'time': list(range(len(slice_range))),
                                'wait_time': [s_res['hourly_wait_times'][i] for i in slice_range],
                                'lost_swaps': [s_res['hourly_lost_swap_count'][i] for i in slice_range],
                                'utilization': [],
                                'idle_inventory': [],
                                'cost': []
                            }
                            
                            # Process hourly stats
                            avg_states = s_res['hourly_avg_states'] 
                            hourly_demands = s_res['hourly_demand']
                            
                            # Coefficients for cost chart
                            alpha, beta, gamma = 1000, 50, 200
                            
                            for i, h_idx in enumerate(slice_range):
                                # Util
                                state = avg_states.get(h_idx, {})
                                charging = state.get('charging', 0)
                                charged = state.get('charged', 0)
                                
                                u = (charging / station['chargers']) * 100
                                chart_data['utilization'].append(u)
                                
                                # Idle Inv
                                chart_data['idle_inventory'].append(charged)
                                
                                # Cost
                                h_demand = hourly_demands[h_idx]
                                h_wait = chart_data['wait_time'][i]
                                h_lost = chart_data['lost_swaps'][i]
                                
                                c_cost = (alpha * station['chargers']) + \
                                         (beta * h_wait * h_demand) + \
                                         (gamma * h_lost)
                                chart_data['cost'].append(c_cost)
                            
                            st.session_state.simulation_results[sid] = chart_data
                            
                            progress_bar.progress((idx + 1) / len(scenario_stations))
                    
                    # Analyze critical wait times (>30 min threshold)
                    st.session_state.critical_wait_periods = scenario_sim.analyze_critical_wait_times(
                        threshold_minutes=30, 
                        use_day7_only=True
                    )
                
                st.success("✅ Simulation completed successfully!")
                st.balloons()
                
                # Automatically switch to results page
                time.sleep(1)
                st.session_state._pending_page = "Results Analysis"
                st.rerun()

elif page == "Results Analysis":
    if not st.session_state.scenario_kpis:
        st.warning("No scenario results available. Please create and run a scenario first.")
        if st.button("Go to Scenario Builder"):
            st.session_state._pending_page = "Scenario Builder"
            st.rerun()
    else:
        st.markdown("### <i class='fa-solid fa-chart-pie'></i> Scenario Results Analysis", unsafe_allow_html=True)
        st.markdown("Compare baseline performance with your scenario intervention")
        
        # KPI Comparison Table
        st.markdown("#### <i class='fa-solid fa-chart-column'></i> KPI Comparison", unsafe_allow_html=True)
        
        baseline = st.session_state.baseline_kpis
        scenario = st.session_state.scenario_kpis
        
        # Calculate deltas
        comparison_data = []
        metrics_config = [
            ('Avg Wait Time (min)', 'avg_wait', 'lower_better'),
            ('Lost Swap (%)', 'lost_swaps', 'lower_better'),
            ('Idle Inventory (%)', 'idle_inventory', 'lower_better'),
            ('Utilization (%)', 'utilization', 'optimal'),
            # ('Cost/hr (₹)', 'cost', 'lower_better')
        ]
        
        for metric_name, key, direction in metrics_config:
            base_val = baseline[key]
            scen_val = scenario[key]
            delta = scen_val - base_val
            delta_pct = (delta / base_val * 100) if base_val != 0 else 0
            
            # Determine if change is good or bad
            if direction == 'lower_better':
                is_good = delta < 0
            elif direction == 'higher_better':
                is_good = delta > 0
            else:  # optimal (utilization should be 70-85%)
                is_good = (70 <= scen_val <= 85)
            
            comparison_data.append({
                'Metric': metric_name,
                'Baseline': f"{base_val:.2f}",
                'Scenario': f"{scen_val:.2f}",
                'Delta': f"{delta:+.2f}",
                'Delta %': f"{delta_pct:+.1f}%",
                'Status': '✅' if is_good else '⚠️'
            })
        
        df_comparison = pd.DataFrame(comparison_data)
        
        # Display styled table
        st.dataframe(
            df_comparison,

            hide_index=True,
            column_config={
                "Status": st.column_config.TextColumn("Status", width="small"),
            }
        )
        

        
        st.markdown("---")
        
        # Visual comparisons
        st.markdown("#### <i class='fa-solid fa-magnifying-glass-chart'></i> KPI Comparison Chart", unsafe_allow_html=True)
        
        
        metrics = ['Avg Wait', 'Lost Swaps', 'Utilization']
        baseline_vals = [baseline['avg_wait'], baseline['lost_swaps'], baseline['utilization']]
        scenario_vals = [scenario['avg_wait'], scenario['lost_swaps'], scenario['utilization']]
        
        # Create Matplotlib bar chart
        fig_mpl, ax = plt.subplots(figsize=(10, 5))
        
        x = np.arange(len(metrics))
        width = 0.35
        
        bars1 = ax.bar(x - width/2, baseline_vals, width, label='Baseline', color='#0066CC')
        bars2 = ax.bar(x + width/2, scenario_vals, width, label='Scenario', color='#00CC66')
        
        # Set labels and title
        ax.set_ylabel('Value', fontsize=11, color='#1A1A1A', fontfamily='Helvetica')
        ax.set_title('Baseline vs Scenario Comparison', fontsize=16, color='#0A2647', 
                     fontfamily='Helvetica Neue', pad=20, fontweight='normal')
        ax.set_xticks(x)
        ax.set_xticklabels(metrics)
        ax.legend()
        
        # Style the figure
        fig_mpl.patch.set_facecolor('white')
        ax.set_facecolor('white')
        ax.grid(True, axis='y', color='#F0F4F8', linestyle='-', linewidth=0.5, alpha=0.5, zorder=0)
        ax.set_axisbelow(True)
        
        # Style spines
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['bottom'].set_color('#E1E8ED')
        ax.spines['left'].set_color('#E1E8ED')
        
        plt.tight_layout()
        
        st.pyplot(fig_mpl, use_container_width=True)
        
        st.markdown("---")
        
        # Critical Wait Time Alerts Section
        st.markdown("#### <i class='fa-solid fa-triangle-exclamation'></i> Critical Wait Time Alerts (>30 min)", unsafe_allow_html=True)
        
        critical_periods = st.session_state.get('critical_wait_periods', {})
        
        if not critical_periods:
            # No critical periods found
            st.success("✅ All stations operating within acceptable wait time thresholds. No wait times exceeded 30 minutes during Day 7 simulation.")
        else:
            # Display warning summary
            total_stations_affected = len(critical_periods)
            total_critical_hours = sum(data['total_critical_hours'] for data in critical_periods.values())
            
            st.warning(f"⚠️ **{total_stations_affected} station(s)** experienced critical wait times exceeding 30 minutes, totaling **{total_critical_hours} hours** of critical operations.")
            
            st.markdown("""
            <div style="background-color: #FFF3CD; border-left: 4px solid #FFC107; padding: 12px; margin: 10px 0; border-radius: 4px;">
                <strong>⚠️ Critical State Warning:</strong> When wait times exceed 30 minutes, operations reach a critical state where:
                <ul style="margin: 8px 0 0 20px;">
                    <li>Customer satisfaction significantly degrades</li>
                    <li>Swap demand will be lost as customers seek alternatives</li>
                    <li>Station reputation and future demand may be impacted</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)
            
            # Display each station's critical periods
            for sid, data in critical_periods.items():
                station_name = data['station_name']
                periods = data['periods']
                total_hours = data['total_critical_hours']
                
                with st.expander(f"🔴 **{station_name}** - {len(periods)} Critical Period(s) ({total_hours} hours)", expanded=True):
                    st.markdown(f"**Station ID:** `{sid}`")
                    st.markdown(f"**Total Critical Hours:** {total_hours} out of 24 hours")
                    
                    # Display each critical period
                    for i, period in enumerate(periods, 1):
                        start_hour = period['start_hour']
                        end_hour = period['end_hour']
                        peak_wait = period['peak_wait_time']
                        duration = period['duration_hours']
                        
                        # Format time display (0-23 hours)
                        start_time = f"{start_hour:02d}:00"
                        end_time = f"{end_hour:02d}:59"
                        
                        st.markdown(f"""
                        <div style="background-color: #FFE5E5; border-left: 4px solid #DC3545; padding: 10px; margin: 8px 0; border-radius: 4px;">
                            <strong>Critical Period #{i}</strong><br>
                            <strong>⏰ Time Range:</strong> {start_time} - {end_time}<br>
                            <strong>⏱️ Duration:</strong> {duration} hour(s)<br>
                            <strong>📈 Peak Wait Time:</strong> {peak_wait:.2f} minutes<br>
                            <strong>💡 Recommendation:</strong> Operations at this station are reaching a critical state during this period. 
                            Swaps are likely being lost from hour {start_hour} until hour {end_hour + 1} when wait times drop below 30 minutes. 
                            Consider increasing charger capacity, rebalancing battery inventory, or implementing demand management strategies.
                        </div>
                        """, unsafe_allow_html=True)
                    
                    # Summary recommendation for the station
                    st.markdown(f"""
                    <div style="background-color: #E3F2FD; border-left: 4px solid #2196F3; padding: 10px; margin: 10px 0; border-radius: 4px;">
                        <strong>📊 Station Summary:</strong> This station experienced critical wait times for {total_hours} out of 24 hours. 
                        Immediate action is recommended to prevent customer loss and maintain service quality.
                    </div>
                    """, unsafe_allow_html=True)
        
        st.markdown("---")

        
        
        # Map comparison
        st.markdown("#### <i class='fa-solid fa-map-location-dot'></i> Network Map - Scenario View", unsafe_allow_html=True)
        
        m_scenario = folium.Map(
            location=[28.6139, 77.2090], 
            zoom_start=11, 
            tiles='CartoDB Positron', 
            zoom_control=False
        )
        
        # Auto-Recovery: If markers exist but polygon data is missing, regenerate it.
        # This handles page refreshes or flow discontinuities.
        if not st.session_state.get('scenario_result') and st.session_state.scenario_config.get('new_stations'):
             with st.spinner("Syncing Scenario Boundaries..."):
                 # Assume the last added station is the active one for specific redistribution
                 # This aligns with the single-station hypothesis UI
                 active_new_st = st.session_state.scenario_config['new_stations'][-1]
                 recovered_result = redistribute_scenario_demand(st.session_state.stations, active_new_st)
                 if recovered_result:
                     st.session_state.scenario_result = recovered_result
        
        # Determine which layer to show: Default or Scenario Result
        scenario_data = st.session_state.get('scenario_result')
        vis_geojson = st.session_state.voronoi_geojson
        
        if scenario_data:
             vis_geojson = scenario_data
             st.info(f"Displaying Redistributed Scenario. Impacted Stations: {len(scenario_data['impact']['details'])}")

        if vis_geojson:
            # Calculate total demand index for ratio computation
            total_demand_index = sum(
                feature['properties'].get('demand_index', 0) 
                for feature in vis_geojson.get('features', [])
            )
            
            # Add demand_ratio to each feature
            for feature in vis_geojson.get('features', []):
                idx = feature['properties'].get('demand_index', 0)
                if total_demand_index > 0:
                    feature['properties']['demand_ratio'] = round((idx / total_demand_index) * 100, 2)
                else:
                    feature['properties']['demand_ratio'] = 0
            
            # Color Function for Demand Ratio
            def get_demand_color(feature):
                ratio = feature['properties'].get('demand_ratio', 0)
                if ratio > 20: return '#FF4B4B' # Red (High)
                if ratio > 10: return '#FFD700'  # Yellow (Med)
                return '#2ecc71'              # Green (Low)

            folium.GeoJson(
                vis_geojson,
                name="Service Areas",
                style_function=lambda x: {
                    'fillColor': get_demand_color(x),
                    'color': '#2c3e50',
                    'weight': 2 if scenario_data else 1, # Thicker for scenario
                    'fillOpacity': 0.5 if scenario_data else 0.4,
                },
                tooltip=folium.GeoJsonTooltip(
                    fields=['name', 'demand_ratio'], 
                    aliases=['Station:', 'Demand Ratio (%):'],
                    localize=True
                )
            ).add_to(m_scenario)
            
        if scenario_data:
            with st.expander("📊 Demand Redistribution Impact", expanded=True):
                impact_df = pd.DataFrame(scenario_data['impact']['details'])
                if not impact_df.empty:
                    # Fix Types
                    impact_df['old'] = impact_df['old'].astype(float)
                    impact_df['new'] = impact_df['new'].astype(float)
                    impact_df['delta'] = impact_df['delta'].astype(float)
                    st.dataframe(impact_df[['name', 'old', 'new', 'delta']].style.format({
                        'old': "{:.2f}",
                        'new': "{:.2f}",
                        'delta': "{:+.2f}"
                    }))

        # 2. Add Stations with Rich Tooltips
        for station in st.session_state.scenario_stations:
            # Determine if this is a new station
            is_new = station.get('is_new', False)
            
            # Calculate utilization
            lambda_i = station['arrival_rate'] * station.get('demand_multiplier', 1.0)
            c_i = station['chargers']
            mu_i = station['service_rate']
            rho = st.session_state.sim_engine.calculate_utilization(lambda_i, c_i, mu_i)
            util = rho * 100
            wait = st.session_state.sim_engine.calculate_wait_time(c_i, rho, lambda_i)
            d_index = station.get('demand_index', 0.0)
            
            # Adjust color based on Wait Time
            color = "#2ecc71" # Green
            status = "Low Wait"
            
            if wait > 5:
                color = "#FFA500" # Orange
                status = "Med Wait"
            if wait > 15:
                color = "#FF4B4B" # Red
                status = "High Wait"
            
            if is_new:
                color = '#3498db'
                status = "New"

            # Rich HTML Tooltip (Matching Dashboard)
            tooltip_html = f"""
            <div style="font-family: sans-serif; min-width: 200px;">
                <b>{station['name']}</b><br>
                <span style="color: gray; font-size: 12px;">ID: {station['id']}</span><br>
                <hr style="margin: 5px 0;">
                <b>Status:</b> <span style="color: {color}; font-weight: bold;">{status.upper()}</span><br>
                <b>Chargers:</b> {c_i}<br>
                <b>Utilization:</b> {util:.1f}%<br>
                <b>Avg Wait:</b> {wait:.1f} min<br>
                <b>Multi:</b> {station.get('demand_multiplier', 1.0):.1f}x
                <hr style="margin: 5px 0;">
                <b>Demand Index:</b> {d_index:.2f}
            </div>
            """
            
            folium.CircleMarker(
                location=[station['lat'], station['lon']],
                radius=12,
                tooltip=tooltip_html,
                color=color,
                fill=True,
                fillColor=color,
                fillOpacity=0.7,
                weight=2
            ).add_to(m_scenario)
        
        # Force map refresh if scenario results changed
        map_key = f"scenario_map_{len(scenario_data['features'])}" if scenario_data else "scenario_map_default"
        
        # Scenario Map Legend (Reduced Padding)
        components.html(
        """
        <div style="display:flex;gap:20px;align-items:center;
                    background:white;padding:5px 15px;border-radius:10px;
                    border:1px solid #E1E8ED;width:100%;box-sizing:border-box;">

          <div style="font-weight:600;color:#0A2647;">Region Demand:</div>

          <div style="display:flex;align-items:center;gap:6px;">
            <span style="width:10px;height:10px;background:#2ecc71;opacity:0.4;
                         border:0.5px solid #2c3e50;"></span>
            <span>Low</span>
          </div>

          <div style="display:flex;align-items:center;gap:6px;">
            <span style="width:10px;height:10px;background:#FFD700;opacity:0.4;
                         border:0.5px solid #2c3e50;"></span>
            <span>Medium</span>
          </div>

          <div style="display:flex;align-items:center;gap:6px;">
            <span style="width:10px;height:10px;background:#FF4B4B;opacity:0.4;
                         border:0.5px solid #2c3e50;"></span>
            <span>High</span>
          </div>

          <div style="border-left:0.5px solid #ddd;height:20px;"></div>

          <div style="font-weight:600;color:#0A2647;">Station Wait Time:</div>

          <div style="display:flex;align-items:center;gap:6px;">
            <span style="width:10px;height:10px;background:#2ecc71;border-radius:50%;"></span>
            <span>Low (&lt;5m)</span>
          </div>

          <div style="display:flex;align-items:center;gap:6px;">
            <span style="width:10px;height:10px;background:#FFA500;border-radius:50%;"></span>
            <span>Med (5–15m)</span>
          </div>

          <div style="display:flex;align-items:center;gap:6px;">
            <span style="width:10px;height:10px;background:#FF4B4B;border-radius:50%;"></span>
            <span>High (&gt;15m)</span>
          </div>

        </div>
        """,
        height=55,
    )

        st_folium(m_scenario, use_container_width=True, height=500, key=map_key, returned_objects=[])

elif page == "Next Station Recommender":
    st.markdown("### 🎯 Next Station Recommender", unsafe_allow_html=True)
    st.markdown("Find the optimal location for a new battery swapping station by minimizing demand index standard deviation across all stations.")
    
    # Check dependencies
    if 'stations' not in st.session_state:
        st.warning("Please initialize stations first (go to Dashboard).") 
    else:
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.markdown("#### Optimization Settings")
            
            # Grid resolution slider
            grid_res = st.slider(
                "Grid Resolution (degrees)",
                min_value=0.01,
                max_value=0.05,
                value=0.02,
                step=0.01,
                help="Smaller values = more precise but slower. 0.02° ≈ 2.2km spacing"
            )
            
            st.markdown("---")
            
            if st.button("🔍 Find Optimal Location", type="primary"):
                with st.spinner("Optimizing station placement... This may take 30-60 seconds."):
                    from spatial_utils import find_optimal_station_location
                    
                    # Run optimization
                    result = find_optimal_station_location(
                        st.session_state.stations,
                        grid_resolution=grid_res
                    )
                    
                    if result:
                        st.session_state.optimization_result = result
                        st.success("✅ Optimization Complete!")
                    else:
                        st.error("❌ Optimization failed. Please try again.")
        
        with col2:
            st.markdown("#### Optimization Results")
            
            if 'optimization_result' in st.session_state and st.session_state.optimization_result:
                res = st.session_state.optimization_result
                
                # Display metrics
                m1, m2, m3 = st.columns(3)
                m1.metric("Optimal Latitude", f"{res['lat']:.3f}°")
                m2.metric("Optimal Longitude", f"{res['lon']:.3f}°")
                m3.metric("Demand Std Dev", f"{res['std_dev']:.3f}")
                
                st.markdown("---")
                
                # Display demand statistics
                st.markdown("#### 📊 Demand Index Distribution")
                
                demand_data = []
                for station_id, demand_idx in res['demand_indices'].items():
                    # Find station name
                    station_name = station_id
                    for s in res['all_stations']:
                        if s['id'] == station_id:
                            station_name = s['name']
                            break
                    
                    is_new = station_id == 'ST_NEW'
                    demand_data.append({
                        "Station ID": station_id,
                        "Station Name": station_name,
                        "Demand Index": f"{demand_idx:.4f}",
                        "Type": "🆕 New" if is_new else "Existing"
                    })
                
                # Sort by demand index descending
                demand_data_sorted = sorted(demand_data, key=lambda x: float(x["Demand Index"]), reverse=True)
                st.dataframe(demand_data_sorted, hide_index=True, use_container_width=True)
                
            else:
                st.info("Click 'Find Optimal Location' to start optimization.")
    
    # Map Visualization
    if 'optimization_result' in st.session_state and st.session_state.optimization_result:
        st.markdown("---")
        st.markdown("### 🗺️ Optimized Network Map")
        
        res = st.session_state.optimization_result
        
        # Legend
        components.html(
        """
        <div style="display:flex;gap:20px;align-items:center;
                    background:white;padding:5px 15px;border-radius:10px;
                    border:1px solid #E1E8ED;width:100%;box-sizing:border-box;">

          <div style="font-weight:600;color:#0A2647;">Region Demand:</div>

          <div style="display:flex;align-items:center;gap:6px;">
            <span style="width:10px;height:10px;background:#2ecc71;opacity:0.4;
                         border:0.5px solid #2c3e50;"></span>
            <span>Low</span>
          </div>

          <div style="display:flex;align-items:center;gap:6px;">
            <span style="width:10px;height:10px;background:#FFD700;opacity:0.4;
                         border:0.5px solid #2c3e50;"></span>
            <span>Medium</span>
          </div>

          <div style="display:flex;align-items:center;gap:6px;">
            <span style="width:10px;height:10px;background:#FF4B4B;opacity:0.4;
                         border:0.5px solid #2c3e50;"></span>
            <span>High</span>
          </div>

          <div style="border-left:0.5px solid #ddd;height:20px;"></div>

          <div style="font-weight:600;color:#0A2647;">Station Type:</div>

          <div style="display:flex;align-items:center;gap:6px;">
            <span style="width:10px;height:10px;background:#2ecc71;border-radius:50%;"></span>
            <span>Existing</span>
          </div>

          <div style="display:flex;align-items:center;gap:6px;">
            <span style="width:10px;height:10px;background:#3498db;border-radius:50%;"></span>
            <span>New (Recommended)</span>
          </div>

        </div>
        """,
        height=50,
        )
        
        # Generate map
        m = folium.Map(
            location=[28.6139, 77.2090],
            zoom_start=11,
            tiles='CartoDB Positron',
            zoom_control=False
        )
        
        # Generate Voronoi for all stations including new one
        from spatial_utils import generate_voronoi_polygons
        geojson_data = generate_voronoi_polygons(res['all_stations'])
        
        if geojson_data:
            # Calculate total demand index for ratio computation
            total_demand_index = sum(
                feature['properties'].get('demand_index', 0)
                for feature in geojson_data.get('features', [])
            )
            
            # Add demand_ratio to each feature
            for feature in geojson_data.get('features', []):
                idx = feature['properties'].get('demand_index', 0)
                if total_demand_index > 0:
                    feature['properties']['demand_ratio'] = round((idx / total_demand_index) * 100, 2)
                else:
                    feature['properties']['demand_ratio'] = 0
            
            # Color function for demand ratio
            def get_demand_color(feature):
                ratio = feature['properties'].get('demand_ratio', 0)
                if ratio > 20: return '#FF4B4B'  # Red (High)
                if ratio > 10: return '#FFD700'   # Yellow (Med)
                return '#2ecc71'                  # Green (Low)
            
            folium.GeoJson(
                geojson_data,
                name="Service Areas",
                style_function=lambda x: {
                    'fillColor': get_demand_color(x),
                    'color': '#2c3e50',
                    'weight': 1,
                    'fillOpacity': 0.4 if x['properties'].get('demand_ratio', 0) > 10 else 0.1,
                },
                tooltip=folium.GeoJsonTooltip(
                    fields=['name', 'demand_ratio'],
                    aliases=['Station:', 'Demand Ratio (%):'],
                    localize=True
                )
            ).add_to(m)
        
        # Add station markers
        for station in res['all_stations']:
            is_new = station.get('id') == 'ST_NEW'
            
            if is_new:
                color = '#3498db'  # Blue for new station
                status = 'Recommended Location'
            else:
                color = '#2ecc71'  # Green for existing
                status = 'Existing Station'
            
            d_index = station.get('demand_index', 0.0)
            
            tooltip_html = f"""
            <div style="font-family: sans-serif; min-width: 200px;">
                <b>{station['name']}</b><br>
                <span style="color: gray; font-size: 12px;">ID: {station['id']}</span><br>
                <hr style="margin: 5px 0;">
                <b>Status:</b> <span style="color: {color}; font-weight: bold;">{status.upper()}</span><br>
                <b>Chargers:</b> {station['chargers']} <br>
                <hr style="margin: 5px 0;">
                <b>Demand Index:</b> {d_index:.4f}
            </div>
            """
            
            folium.CircleMarker(
                location=[station['lat'], station['lon']],
                radius=15 if is_new else 12,
                tooltip=tooltip_html,
                color=color,
                fill=True,
                fillColor=color,
                fillOpacity=0.8 if is_new else 0.7,
                weight=3 if is_new else 2
            ).add_to(m)
        
        # Display map
        st_folium(m, use_container_width=True, height=700, returned_objects=[])
        
        
        # Consistent Legend
#         st.markdown("""
# <div style="display: flex; flex-wrap: wrap; gap: 20px; margin-bottom: 15px; align-items: center; justify-content: flex-start; background: white; padding: 10px 15px; border-radius: 10px; border: 1px solid #E1E8ED; width: fit-content; box-shadow: 0 2px 4px rgba(0,0,0,0.02);">
#     <div style="font-weight: 600; color: #0A2647; margin-right: 5px;">Region Demand:</div>
#     <div style="display: flex; align-items: center; gap: 6px;">
#         <span style="width: 10px; height: 10px; background-color: #2ecc71; opacity: 0.4; border: 1px solid #2c3e50; display: inline-block;"></span>
#         <span style="font-size: 13px; color: #4A5568;">Low</span>
#     </div>
#     <div style="display: flex; align-items: center; gap: 6px;">
#         <span style="width: 10px; height: 10px; background-color: #FFD700; opacity: 0.4; border: 1px solid #2c3e50; display: inline-block;"></span>
#         <span style="font-size: 13px; color: #4A5568;">Medium</span>
#     </div>
#     <div style="display: flex; align-items: center; gap: 6px;">
#         <span style="width: 10px; height: 10px; background-color: #FF4B4B; opacity: 0.4; border: 1px solid #2c3e50; display: inline-block;"></span>
#         <span style="font-size: 13px; color: #4A5568;">High</span>
#     </div>
    
#     <div style="border-left: 1px solid #ddd; height: 20px; margin: 0 10px;"></div>
    
#     <div style="font-weight: 600; color: #0A2647; margin-right: 5px;">Station Wait Time:</div>
#     <div style="display: flex; align-items: center; gap: 6px;">
#         <span style="width: 10px; height: 10px; background-color: #2ecc71; border-radius: 50%; display: inline-block;"></span>
#         <span style="font-size: 13px; color: #4A5568;">Low (&lt;5m)</span>
#     </div>
#     <div style="display: flex; align-items: center; gap: 6px;">
#         <span style="width: 10px; height: 10px; background-color: #FFA500; border-radius: 50%; display: inline-block;"></span>
#         <span style="font-size: 13px; color: #4A5568;">Med (5-15m)</span>
#     </div>
#     <div style="display: flex; align-items: center; gap: 6px;">
#         <span style="width: 10px; height: 10px; background-color: #FF4B4B; border-radius: 50%; display: inline-block;"></span>
#         <span style="font-size: 13px; color: #4A5568;">High (&gt;15m)</span>
#     </div>
# </div>
# """, unsafe_allow_html=True)

# # Footer
# st.markdown("---")
# st.markdown("""
# <div style="text-align: center; color: #666; padding: 20px;">
#     <p>🔋 HackSmart Digital Twin Platform | Built with Streamlit | Version 1.0</p>
#     <p>Powered by discrete-event simulation & queueing theory</p>
# </div>
# """, unsafe_allow_html=True)
# st.markdown(
#     textwrap.dedent("""
#     <div style="display: flex; gap: 20px; margin-bottom: 15px; align-items: center; justify-content: flex-start; background: white; padding: 10px 15px; border-radius: 10px; border: 1px solid #E1E8ED; width: fit-content;">
        
#         <div style="font-weight: 600; color: #0A2647;">Region Demand:</div>

#         <div style="display: flex; align-items: center; gap: 6px;">
#             <span style="width: 10px; height: 10px; background-color: #2ecc71; opacity: 0.4; border: 1px solid #2c3e50;"></span>
#             <span>Low</span>
#         </div>

#         <div style="display: flex; align-items: center; gap: 6px;">
#             <span style="width: 10px; height: 10px; background-color: #FFD700; opacity: 0.4; border: 1px solid #2c3e50;"></span>
#             <span>Medium</span>
#         </div>

#         <div style="display: flex; align-items: center; gap: 6px;">
#             <span style="width: 10px; height: 10px; background-color: #FF4B4B; opacity: 0.4; border: 1px solid #2c3e50;"></span>
#             <span>High</span>
#         </div>

#         <div style="border-left: 1px solid #ddd; height: 20px;"></div>

#         <div style="font-weight: 600; color: #0A2647;">Station Wait Time:</div>
#     </div>
#     """),
#     unsafe_allow_html=True
# )

#     components.html(
#     """
#     <div style="display:flex;gap:20px;align-items:center;
#                 background:white;padding:10px 15px;border-radius:10px;
#                 border:1px solid #E1E8ED;width:100%;box-sizing:border-box;">

#       <div style="font-weight:600;color:#0A2647;">Region Demand:</div>

#       <div style="display:flex;align-items:center;gap:6px;">
#         <span style="width:10px;height:10px;background:#2ecc71;opacity:0.4;
#                      border:0.5px solid #2c3e50;"></span>
#         <span>Low</span>
#       </div>

#       <div style="display:flex;align-items:center;gap:6px;">
#         <span style="width:10px;height:10px;background:#FFD700;opacity:0.4;
#                      border:0.5px solid #2c3e50;"></span>
#         <span>Medium</span>
#       </div>

#       <div style="display:flex;align-items:center;gap:6px;">
#         <span style="width:10px;height:10px;background:#FF4B4B;opacity:0.4;
#                      border:0.5px solid #2c3e50;"></span>
#         <span>High</span>
#       </div>

#       <div style="border-left:0.5px solid #ddd;height:20px;"></div>

#       <div style="font-weight:600;color:#0A2647;">Station Wait Time:</div>

#       <div style="display:flex;align-items:center;gap:6px;">
#         <span style="width:10px;height:10px;background:#2ecc71;border-radius:50%;"></span>
#         <span>Low (&lt;5m)</span>
#       </div>

#       <div style="display:flex;align-items:center;gap:6px;">
#         <span style="width:10px;height:10px;background:#FFA500;border-radius:50%;"></span>
#         <span>Med (5–15m)</span>
#       </div>

#       <div style="display:flex;align-items:center;gap:6px;">
#         <span style="width:10px;height:10px;background:#FF4B4B;border-radius:50%;"></span>
#         <span>High (&gt;15m)</span>
#       </div>

#     </div>
#     """,
#     height=55,
# )
