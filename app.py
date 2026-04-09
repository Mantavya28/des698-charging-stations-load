import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

from simulation import load_demand_curve, generate_simulation_curve
from ev_simulation import run_ev_simulation

# ── PAGE CONFIG ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="EV Swap Load Engine",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

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

    st.markdown("**🏙️ City Demand Peaks**")
    m_peak = st.slider("Morning Peak (swaps/15 min)", 10, 500, 120, step=5,
                       help="Peak arrivals around 09:00")
    e_peak = st.slider("Evening Peak (swaps/15 min)", 10, 500, 150, step=5,
                       help="Peak arrivals around 18:30")

    DYNAMIC_CURVE = generate_simulation_curve(m_peak, e_peak)

    st.markdown("**🏬 Network Configuration**")
    num_stations = st.slider("Number of stations",   1, 20,  8)
    
    st.markdown("**⚡ Fast Chargers (DC)**")
    n_fast = st.slider("Fast chargers / station", 0, 20, 5)
    p_fast = st.slider("Fast charger power (kW)", 25.0, 150.0, 50.0, step=5.0)

    st.markdown("**🔌 Slow Chargers (AC)**")
    n_slow = st.slider("Slow chargers / station", 0, 20, 5)
    p_slow = st.slider("Slow charger power (kW)", 3.3, 22.0, 7.4, step=0.1)

    st.markdown("**🔋 Vehicle Specs**")
    battery_kwh  = st.slider("Battery capacity (kWh)", 10.0, 100.0, 30.0,
                              step=1.0, format="%.0f kWh")

    st.markdown("**🏠 Home Charging**")
    n_home_evs   = st.slider("Home-charging EVs (evening)", 0, 500, 50,
                              help="EVs charging at home 18:00–22:00")
    home_power   = st.slider("Home charger power (kW)", 1.5, 22.0, 3.3,
                              step=0.1, format="%.1f kW")

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
st.markdown('<div class="sec-head">📈 City Demand Profile</div>', unsafe_allow_html=True)
st.markdown(
    f'<div class="sec-sub">Typical 24-hour swap demand curve derived from historical data &nbsp;·&nbsp; '
    f'Expected Peak = {int(np.max(DYNAMIC_CURVE))} swaps / 15 min</div>',
    unsafe_allow_html=True,
)

with st.container():
    fig_d, ax_d = plt.subplots(figsize=(12, 2.4))
    fig_d.patch.set_facecolor("white")
    ax_d.set_facecolor("#F8FAFC")

    slots    = np.arange(96)
    max_val  = np.max(DYNAMIC_CURVE)

    ax_d.fill_between(slots, DYNAMIC_CURVE, alpha=0.12, color="#2563EB")
    ax_d.plot(slots, DYNAMIC_CURVE, color="#2563EB", linewidth=2.0)
    ax_d.axhline(max_val, color="#EF4444", linewidth=1.0, linestyle="--",
                 alpha=0.55, label=f"Peak = {max_val:.0f}")

    ax_d.set_xlim(0, 95)
    ax_d.set_ylim(0)
    ax_d.set_xticks([0, 16, 32, 48, 64, 80, 95])
    ax_d.set_xticklabels(["00:00", "04:00", "08:00", "12:00",
                           "16:00", "20:00", "23:45"], fontsize=8)
    ax_d.set_ylabel("Swaps / 15 min", fontsize=8)
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

    for col, label, value, unit, cls in [
        (c1, "Peak Load",     f"{r['peak_kw']:,.0f}",          "kW",         "blue"),
        (c2, "Cumulative Demand", f"{r['total_kwh']:,.0f}",         "kWh (Area)", "green"),
        (c3, "Load Factor",   f"{r['load_factor']:.2f}",        "avg / peak", "orange"),
        (c4, "Avg Load",      f"{r['avg_kw']:,.0f}",            "kW",         "purple"),
        (c5, "EVs Served",    f"{r['total_served']:,}",          "EVs",        "teal"),
        (c6, "Dropped",       f"{r['total_dropped_pct']:.1f}",  "%",          "red"),
    ]:
        with col:
            st.markdown(f"""
<div class="kpi-card">
  <div class="kpi-label">{label}</div>
  <div class="kpi-value {cls}">{value}</div>
  <div class="kpi-unit">{unit}</div>
</div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── LOAD CURVE ─────────────────────────────────────────────────────────
    st.markdown('<div class="sec-head">⚡ Grid Load Curve (kW)</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sec-sub">Station charging load + home charging &nbsp;·&nbsp; 15-min resolution</div>',
        unsafe_allow_html=True,
    )

    # Decompose station vs home load into 15-min slots
    home_min    = np.array(r.get("home_load_min", [0] * 1440))
    station_min = np.array(r.get("station_load_min", [0] * 1440))
    n_slots     = len(load)

    home_15    = np.array([np.mean(home_min[i*15:(i+1)*15]) for i in range(n_slots)])
    station_15 = np.array([np.mean(station_min[i*15:(i+1)*15]) for i in range(n_slots)])

    fig, ax = plt.subplots(figsize=(12, 3.6))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("#F8FAFC")

    ax.stackplot(slots, station_15, home_15,
                 labels=["Station charging (kW)", "Home charging (kW)"],
                 colors=["#2563EB", "#F59E0B"], alpha=0.75)

    ax.axhline(r["peak_kw"], color="#EF4444", linewidth=1.2, linestyle="--",
               alpha=0.75, label=f"Peak  {r['peak_kw']:,.0f} kW")
    ax.axhline(r["avg_kw"],  color="#10B981", linewidth=1.2, linestyle=":",
               alpha=0.85, label=f"Avg  {r['avg_kw']:,.0f} kW")

    max_cap = num_stations * (n_fast * p_fast + n_slow * p_slow)
    ax.axhline(max_cap, color="#94A3B8", linewidth=0.9, linestyle="-.",
               alpha=0.55, label=f"Installed capacity  {max_cap:,.0f} kW")

    xticks = [0, 16, 32, 48, 64, 80, n_slots - 1]
    ax.set_xlim(0, n_slots - 1)
    ax.set_ylim(0, max(max_cap * 1.05, r["peak_kw"] * 1.1, 1))
    ax.set_xticks(xticks)
    ax.set_xticklabels(["00:00", "04:00", "08:00", "12:00",
                         "16:00", "20:00", "23:45"], fontsize=9)
    ax.set_ylabel("Load (kW)", fontsize=9)
    ax.set_xlabel("Time of Day", fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(labelsize=9)
    ax.grid(axis="y", alpha=0.25, linewidth=0.6)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))
    ax.legend(fontsize=8, framealpha=0, ncol=2)

    plt.tight_layout(pad=0.6)
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)

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
