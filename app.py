import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

from simulation import load_demand_curve, generate_simulation_curve
from ev_simulation import run_ev_simulation

# ── PAGE CONFIG ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="EV Charging Load Engine",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=EV');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.stApp { background: #F1F5F9; }

.block-container {
    padding-top: 2rem !important;
    max-width: 1280px;
}

/* ── Sidebar ─────────────────────────────── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #04142B 0%, #0A2240 100%);
    border-right: 1px solid rgba(255,255,255,0.07);
}
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] div,
[data-testid="stSidebar"] label {
    color: #CBD5E1 !important;
}
[data-testid="stSidebar"] .stSlider [data-testid="stTickBar"],
[data-testid="stSidebar"] .stSlider .rc-slider-track { background: #2563EB !important; }

/* ── Cards ───────────────────────────────── */
.kpi-card {
    background: white;
    border-radius: 18px;
    padding: 22px 20px 18px;
    border: 1px solid #E2E8F0;
    box-shadow: 0 2px 10px rgba(0,0,0,0.05);
    text-align: center;
    min-height: 160px;
    display: flex;
    flex-direction: column;
    justify-content: center;
}
.kpi-label {
    font-size: 0.68rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.09em;
    color: #94A3B8;
    margin-bottom: 6px;
}
.kpi-value {
    font-size: 2.1rem;
    font-weight: 800;
    line-height: 1.05;
    margin: 0;
}
.kpi-unit {
    font-size: 0.78rem;
    color: #94A3B8;
    margin-top: 3px;
}
.blue   { color: #1D4ED8; }
.green  { color: #047857; }
.orange { color: #B45309; }
.purple { color: #6D28D9; }
.red    { color: #B91C1C; }
.teal   { color: #0F766E; }

/* ── Section headers ─────────────────────── */
.sec-head {
    font-size: 1rem;
    font-weight: 700;
    color: #0F172A;
    margin: 0 0 2px;
}
.sec-sub {
    font-size: 0.79rem;
    color: #64748B;
    margin-bottom: 14px;
}

/* ── Parameter summary box ───────────────── */
.param-box {
    background: rgba(255,255,255,0.06);
    border-radius: 12px;
    padding: 14px 16px;
    border: 1px solid rgba(255,255,255,0.10);
    margin-top: 6px;
}
.param-box p {
    margin: 4px 0;
    font-size: 0.78rem;
    color: #94A3B8 !important;
}
.param-box strong { color: #E2E8F0 !important; }

/* ── Minimal chart card ──────────────────── */
.chart-card {
    background: white;
    border-radius: 18px;
    padding: 20px 20px 10px;
    border: 1px solid #E2E8F0;
    box-shadow: 0 2px 10px rgba(0,0,0,0.05);
}

/* ── Info banner ─────────────────────────── */
.info-banner {
    background: #EFF6FF;
    border: 1px solid #BFDBFE;
    border-radius: 14px;
    padding: 16px 22px;
    color: #1E40AF;
    font-size: 0.85rem;
    text-align: center;
    margin-top: 12px;
}

/* ── Engine badge ────────────────────────── */
.engine-badge {
    display: inline-block;
    background: linear-gradient(135deg, #1D4ED8, #7C3AED);
    color: white;
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    padding: 3px 10px;
    border-radius: 20px;
    text-transform: uppercase;
    margin-bottom: 18px;
}
</style>
""", unsafe_allow_html=True)


# ── LOAD DEMAND CURVE ─────────────────────────────────────────────────────────
@st.cache_data
def get_base_curve() -> np.ndarray:
    return load_demand_curve()


BASE_CURVE = get_base_curve()


# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚡ Load Engine")
    st.caption("City-Level EV Charging Simulation")
    st.markdown("---")

    st.markdown("### 🚗 EV Population")
    N_EV = st.number_input("Total EVs in City", min_value=1000, max_value=10_000_000, value=100_000, step=10_000)
    f_charge = st.slider("% EVs Charging Daily", 0.1, 0.6, 0.3)
    st.markdown("**⏱️ Daily Charging Pattern**")
    peak_ratio = st.slider("Morning / Evening Peak Ratio", 0.1, 10.0, 1.0, step=0.1)
    
    shaped_curve = generate_simulation_curve(peak_ratio, 1.0)
    
    N_daily = N_EV * f_charge
    curve_normalized = shaped_curve / shaped_curve.sum()
    DYNAMIC_CURVE = curve_normalized * N_daily

    st.markdown("**🏬 Network Configuration**")
    num_stations = st.slider("Number of stations", 1, 100, 8)
    
    use_iea_constraints = st.checkbox("Apply India (STEPS 2030) Infra Constraints", value=True)
    if use_iea_constraints:
        total_chargers = N_EV / 7
        total_power = 3 * N_EV
        st.info(f"IEA Policy: {int(total_chargers):,} chargers, {int(total_power):,} kW cap.")
    else:
        total_chargers = st.number_input("Total Public Chargers", min_value=1, value=int(N_EV / 7))
        total_power = st.number_input("Total Charger Power (kW)", min_value=1.0, value=float(3 * N_EV))

    st.markdown("**⚡ Public Charging**")
    fast_share = st.slider("Fast Charging Share", 0.0, 1.0, 0.4)
    p_fast = st.number_input("Fast Charger Power (kW)", value=60.0)
    p_slow = st.number_input("Slow Charger Power (kW)", value=7.4)

    N_fast = int(total_chargers * fast_share)
    N_slow = int(total_chargers * (1 - fast_share))
    n_fast = max(0, int(N_fast / num_stations))
    n_slow = max(0, int(N_slow / num_stations))

    avg_fast_time = 30  # minutes
    avg_slow_time = 240 # minutes
    fast_capacity = N_fast * (15 / avg_fast_time)
    slow_capacity = N_slow * (15 / avg_slow_time)
    capacity_per_slot = fast_capacity + slow_capacity

    st.markdown("**🔋 Vehicle Specs**")
    battery_kwh  = st.slider("Battery capacity (kWh)", 10.0, 100.0, 30.0, step=1.0, format="%.0f kWh")

    st.markdown("**🏠 Home Charging**")
    home_share = st.slider("Home Charging Share", 0.0, 1.0, 0.6)
    n_home_evs = int(N_daily * home_share)
    home_power = st.slider("Home charger power (kW)", 1.5, 22.0, 3.3, step=0.1, format="%.1f kW")

    st.markdown("<br>", unsafe_allow_html=True)
    run_btn = st.button("▶  Run Simulation", use_container_width=True, type="primary")


# ── HEADER ────────────────────────────────────────────────────────────────────
st.markdown("""
<h1 style="font-size:1.85rem;font-weight:800;color:#0F172A;margin:0 0 4px;">
  ⚡ City-Level EV Charging – Load Engine
</h1>
<p style="color:#64748B;font-size:0.88rem;margin:0 0 8px;">
  Event-driven discrete simulation &nbsp;·&nbsp; Dynamic SoC-based power &nbsp;·&nbsp;
  Station utility routing &nbsp;·&nbsp; Home charging integration
</p>
<span class="engine-badge">🔬 Event-Driven · M/G/c/K · heapq priority queue</span>
""", unsafe_allow_html=True)


# ── DEMAND CURVE PREVIEW ──────────────────────────────────────────────────────
st.markdown('<div class="sec-head">📈 City Demand Profile vs Capacity</div>', unsafe_allow_html=True)
peak = DYNAMIC_CURVE.max()
st.markdown(
    f'<div class="sec-sub">Derived from EV population and charging behavior &nbsp;·&nbsp; '
    f'Derived Peak = {int(peak)} EVs / 15 min<br>'
    f'Service Capacity = {int(capacity_per_slot)} EVs / slot</div>',
    unsafe_allow_html=True,
)

with st.container():
    fig_d, ax_d = plt.subplots(figsize=(12, 3.6))
    fig_d.patch.set_facecolor("white")
    ax_d.set_facecolor("#F8FAFC")

    slots    = np.arange(96)

    ax_d.plot(slots, DYNAMIC_CURVE, color="#2563EB", linewidth=2.0, label="Charging Demand (EVs / 15 min)")

    ax_d.set_xlim(0, 95)
    ax_d.set_ylim(0)
    ax_d.set_xticks([0, 16, 32, 48, 64, 80, 95])
    ax_d.set_xticklabels(["00:00", "04:00", "08:00", "12:00",
                           "16:00", "20:00", "23:45"], fontsize=8)
    ax_d.set_ylabel("EVs / 15 min", fontsize=8)
    ax_d.spines[["top", "right"]].set_visible(False)
    ax_d.tick_params(labelsize=8)
    ax_d.grid(axis="y", alpha=0.25, linewidth=0.6)
    ax_d.legend(fontsize=8, framealpha=0)

    plt.tight_layout(pad=0.5)
    st.pyplot(fig_d, use_container_width=True)
    plt.close(fig_d)

st.divider()


# ── RUN + RESULTS ─────────────────────────────────────────────────────────────
if "results" not in st.session_state:
    st.session_state.results = None

if run_btn:
    with st.spinner("Running event-driven simulation…"):
        norm_curve = DYNAMIC_CURVE / (np.max(DYNAMIC_CURVE) if np.max(DYNAMIC_CURVE) > 0 else 1)
        st.session_state.results = run_ev_simulation(
            max_demand=int(np.max(DYNAMIC_CURVE)),
            demand_curve=norm_curve,
            num_stations=num_stations,
            n_fast=n_fast,
            p_fast=p_fast,
            n_slow=n_slow,
            p_slow=p_slow,
            battery_kwh=battery_kwh,
            n_home_evs=n_home_evs,
            home_power_kw=home_power,
        )


if st.session_state.results:
    r    = st.session_state.results
    load = np.array(r["load_curve"])
    slots = np.arange(len(load))

    # ── KPI CARDS ─────────────────────────────────────────────────────────
    st.markdown('<div class="sec-head">📊 Grid Load Metrics</div>', unsafe_allow_html=True)
    c1, c2, c3, c4, c5, c6 = st.columns(6)

    overload = DYNAMIC_CURVE > capacity_per_slot
    overload_fraction = overload.sum() / len(DYNAMIC_CURVE)
    utilization = DYNAMIC_CURVE.mean() / capacity_per_slot if capacity_per_slot > 0 else 0

    for col, label, value, unit, cls in [
        (c1, "Derived Peak",  f"{int(peak):,}",                "EVs/15min",  "blue"),
        (c2, "Avg Util",      f"{utilization:.2f}",           "ratio",      "orange"),
        (c3, "Overload Time", f"{overload_fraction * 100:.1f}", "% slots",    "red"),
        (c4, "Peak Load",     f"{r['peak_kw']:,.0f}",          "kW",         "purple"),
        (c5, "Cumul. Demand", f"{r['total_arrived']:,}",       "EVs",        "green"),
        (c6, "Dropped",       f"{r['total_dropped_pct']:.1f}", "%",          "teal"),
    ]:
        with col:
            st.markdown(f"""
<div class="kpi-card">
  <div class="kpi-label">{label}</div>
  <div class="kpi-value {cls}">{value}</div>
  <div class="kpi-unit">{unit}</div>
</div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── LOAD CURVES (SEPARATE) ───────────────────────────────────────────
    st.markdown('<div class="sec-head">⚡ Station Charging Load (kW)</div>', unsafe_allow_html=True)
    
    home_min    = np.array(r.get("home_load_min", [0] * 1440))
    station_min = np.array(r.get("station_load_min", [0] * 1440))
    n_slots     = len(load)
    xticks      = [0, 16, 32, 48, 64, 80, n_slots - 1]

    home_15    = np.array([np.mean(home_min[i*15:(i+1)*15]) for i in range(n_slots)])
    station_15 = np.array([np.mean(station_min[i*15:(i+1)*15]) for i in range(n_slots)])

    fig1, ax1 = plt.subplots(figsize=(12, 3.2))
    fig1.patch.set_facecolor("white")
    ax1.set_facecolor("#F8FAFC")
    ax1.fill_between(slots, station_15, color="#2563EB", alpha=0.7)
    ax1.plot(slots, station_15, color="#1E40AF", linewidth=1.5)
    
    ax1.axhline(r["peak_kw"], color="#EF4444", linewidth=1.1, linestyle="--", alpha=0.4, label="Total Peak")
    
    ax1.set_xlim(0, n_slots - 1)
    ax1.set_ylim(0, max(station_15.max()*1.1, 10))
    ax1.set_xticks(xticks)
    ax1.set_xticklabels(["00:00", "04:00", "08:00", "12:00", "16:00", "20:00", "23:45"], fontsize=8)
    ax1.set_ylabel("kW", fontsize=8)
    ax1.spines[["top", "right"]].set_visible(False)
    ax1.grid(axis="y", alpha=0.2)
    plt.tight_layout(pad=0.5)
    st.pyplot(fig1, use_container_width=True)
    plt.close(fig1)

    st.markdown('<div class="sec-head">🏠 Home Charging Load (kW)</div>', unsafe_allow_html=True)
    
    fig2, ax2 = plt.subplots(figsize=(12, 3.2))
    fig2.patch.set_facecolor("white")
    ax2.set_facecolor("#F8FAFC")
    ax2.fill_between(slots, home_15, color="#F59E0B", alpha=0.7)
    ax2.plot(slots, home_15, color="#B45309", linewidth=1.5)
    ax2.set_xlim(0, n_slots - 1)
    ax2.set_ylim(0, max(home_15.max()*1.1, 10))
    ax2.set_xticks(xticks)
    ax2.set_xticklabels(["00:00", "04:00", "08:00", "12:00", "16:00", "20:00", "23:45"], fontsize=8)
    ax2.set_ylabel("kW", fontsize=8)
    ax2.spines[["top", "right"]].set_visible(False)
    ax2.grid(axis="y", alpha=0.2)
    plt.tight_layout(pad=0.5)
    st.pyplot(fig2, use_container_width=True)
    plt.close(fig2)

    # ── SECONDARY METRICS ──────────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="sec-head">🔧 Simulation Summary</div>', unsafe_allow_html=True)

    col_a, col_b, col_c = st.columns(3)

    with col_a:
        st.markdown("**EV & Battery Parameters**")
        st.markdown(f"""
| Parameter | Value |
|---|---|
| Battery capacity | **{battery_kwh:.0f} kWh** |
| Target SoC | **80%** |
| Energy per charge | **{r['e_battery_kwh']} kWh** |
| Fast charge (avg) | **{r['fast_charge_min']:.0f} min** |
| Slow charge (avg) | **{r['slow_charge_min']:.0f} min** |
""")

    with col_b:
        st.markdown("**Network & Queue**")
        st.markdown(f"""
| Parameter | Value |
|---|---|
| Stations | **{num_stations}** |
| Fast chargers / st | **{n_fast}** |
| Slow chargers / st | **{n_slow}** |
| Installed capacity | **{r['installed_kw']:,.0f} kW** |
| Max wait threshold | **10 min** |
""")

    with col_c:
        st.markdown("**EV Flow**")
        st.markdown(f"""
| Metric | Value |
|---|---|
| Total arrivals | **{r['total_arrived']:,}** |
| EVs served | **{r['total_served']:,}** |
| EVs dropped | **{r['total_dropped']:,}** |
| Drop rate | **{r['total_dropped_pct']:.1f}%** |
| Home-charging EVs | **{n_home_evs}** |
""")

else:
    st.markdown("""
<div class="info-banner">
  👈 &nbsp; Configure inputs in the sidebar and click <strong>▶ Run Simulation</strong>
  to generate the grid load curve.
</div>
""", unsafe_allow_html=True)
