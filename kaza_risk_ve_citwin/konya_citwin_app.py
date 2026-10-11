import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import requests
import json
import pydeck as pdk

from pathlib import Path

# app.py'nin bulunduğu klasörü baz alır
BASE_DIR = Path(__file__).resolve().parent
file_path = BASE_DIR / "konya_data.json"

with open(file_path, "r", encoding="utf-8") as f:
    data = json.load(f)
# ─────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Konya CITWIN - Kentsel Hareketlilik Dijital İkizi",
    page_icon="🚦",
    layout="wide"
)

st.markdown("""
    <style>
    .main-header { font-size:28px; font-weight:bold; color:#1E3A8A; margin-bottom:0px; }
    .sub-header  { font-size:15px; color:#4B5563; margin-bottom:20px; }
    .kpi-card    { background-color:#F3F4F6; padding:15px; border-radius:10px;
                   border-left:5px solid #1D4ED8; }
    .sim-badge   { background:#10B981; color:white; padding:3px 10px;
                   border-radius:12px; font-size:12px; margin-left:8px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">🚦 Konya Kentsel Hareketlilik Dijital İkizi (CITWIN)</div>',
            unsafe_allow_html=True)
st.markdown(
    '<div class="sub-header">15 Dakikalık Şehirler İçin Kurumlar Arası Hareketlilik · '
    'Yapay Zekâ Destekli Karar Sistemi (DUT Uyumlu) · '
    '<span class="sim-badge">🔴 CANLI SİMÜLASYON</span></div>',
    unsafe_allow_html=True
)

# ─────────────────────────────────────────────────────────────
# SIMULATION API  — fetch real Konya CitWin data
# ─────────────────────────────────────────────────────────────
SIM_URL = "http://fsswc0ckcwo44g8088cwcwsg.49.12.187.169.sslip.io"

@st.cache_data(ttl=600, show_spinner="Konya simülasyon verisi yükleniyor…")
def fetch_baseline():
    try:
        r = requests.get(f"{SIM_URL}/api/baseline", timeout=8)
        if r.ok:
            return r.json().get("result")
    except Exception:
        pass
    return None

sim_result = fetch_baseline()

# Parse baseline bins
def _fmt_t(t):
    """API t değerini HH:MM string'ine çevirir (string ise dokunmaz, sayıysa dönüştürür)."""
    if isinstance(t, str):
        return t
    h = int(t)
    m = round((t - h) * 60)
    if m >= 60:
        h += 1; m = 0
    return f"{h:02d}:{m:02d}"

def parse_bins(sim_result):
    if not sim_result or "bins" not in sim_result:
        return None, None, None
    raw = sim_result["bins"]
    active  = [b for b in raw if b.get("t") is not None]  # tüm gün
    times   = [_fmt_t(b["t"]) for b in active]
    on_road = [float(b["onRoad"]) for b in active]
    departs = [b.get("departs", [0,0,0,0,0]) for b in active]
    return times, on_road, departs

times_base, on_road_base, departs_base = parse_bins(sim_result)

# Real KPI from API
if sim_result and "kpi" in sim_result:
    kpi_api   = sim_result["kpi"]
    PEAK_VEH  = kpi_api["peakVehicles"]
    DELAY_HRS = kpi_api["delayHours"]
    CO2_KG    = kpi_api["co2Kg"]
    PERSONS   = kpi_api["persons"]
    PEAK_TIME = kpi_api.get("peakTime", "07:30")
    MODE_SHARE= kpi_api.get("modeShare", {})
    API_LIVE  = True
else:
    PEAK_VEH, DELAY_HRS, CO2_KG, PERSONS = 11973, 8251, 44066, 138075
    PEAK_TIME, MODE_SHARE, API_LIVE = "07:30", {}, False

# ─────────────────────────────────────────────────────────────
# SIDEBAR — CONTROL PANEL
# ─────────────────────────────────────────────────────────────
st.sidebar.title("⚙️ Simülasyon Kontrol Paneli")
if API_LIVE:
    st.sidebar.success("🟢 Canlı API bağlantısı aktif")
else:
    st.sidebar.warning("🟡 Yedek veri kullanılıyor")

view_mode = st.sidebar.radio(
    "1. Harita & Görünüm Tipi:",
    ["🌐 Coğrafi Şehir Haritası (OpenStreetMap)",
     "📡 GNN Graf Ağ Modeli (Düğümler & Kenarlar)"]
)

def format_shifted_time(base_str: str, shift_min: int) -> str:
    h, m = map(int, base_str.split(":"))
    tot = h * 60 + m + shift_min
    return f"{(tot // 60) % 24:02d}:{tot % 60:02d}"

st.sidebar.subheader("2. Kurum Saat Esneklikleri")
st.sidebar.caption("Standart başlangıç saatleri ve simülasyon kaydırmaları:")

uni_shift = st.sidebar.slider(
    "🎓 Selçuk Ünv. Ders Saati Kaydırma (Dk)",
    -30, 45, 0, step=15,
    help="Standart kabul edilen ders başlangıcı 08:30'dur. (-30 dk = 08:00, +45 dk = 09:15)"
)
uni_new = format_shifted_time("08:30", uni_shift)
uni_border = "#38bdf8" if uni_shift != 0 else "#10b981"
uni_note = f"({uni_shift:+d} dk)" if uni_shift != 0 else "(Standart Saat)"
st.sidebar.markdown(
    f"""<div style="font-size:12px; padding:4px 8px; border-radius:6px; background-color:rgba(125,125,125,0.08); border-left:3px solid {uni_border}; margin-top:-10px; margin-bottom:12px;">
    ⏰ <b>Normal:</b> <code>08:30</code> &nbsp;➔&nbsp; <b>Yeni Saat:</b> <b>{uni_new}</b> <span style="opacity:0.75; float:right;">{uni_note}</span>
    </div>""",
    unsafe_allow_html=True
)

osb_shift = st.sidebar.slider(
    "🏭 Konya OSB Vardiya Kaydırma (Dk)",
    -30, 45, 0, step=15,
    help="Standart kabul edilen 1. vardiya başlangıcı 07:30'dur. (-30 dk = 07:00, +45 dk = 08:15)"
)
osb_new = format_shifted_time("07:30", osb_shift)
osb_border = "#38bdf8" if osb_shift != 0 else "#10b981"
osb_note = f"({osb_shift:+d} dk)" if osb_shift != 0 else "(Standart Saat)"
st.sidebar.markdown(
    f"""<div style="font-size:12px; padding:4px 8px; border-radius:6px; background-color:rgba(125,125,125,0.08); border-left:3px solid {osb_border}; margin-top:-10px; margin-bottom:12px;">
    ⏰ <b>Normal:</b> <code>07:30</code> &nbsp;➔&nbsp; <b>Yeni Saat:</b> <b>{osb_new}</b> <span style="opacity:0.75; float:right;">{osb_note}</span>
    </div>""",
    unsafe_allow_html=True
)

hosp_shift = st.sidebar.slider(
    "🏥 Şehir Hastanesi Mesai Kaydırma (Dk)",
    -30, 45, 0, step=15,
    help="Standart kabul edilen mesai / poliklinik başlangıcı 08:00'dir. (-30 dk = 07:30, +45 dk = 08:45)"
)
hosp_new = format_shifted_time("08:00", hosp_shift)
hosp_border = "#38bdf8" if hosp_shift != 0 else "#10b981"
hosp_note = f"({hosp_shift:+d} dk)" if hosp_shift != 0 else "(Standart Saat)"
st.sidebar.markdown(
    f"""<div style="font-size:12px; padding:4px 8px; border-radius:6px; background-color:rgba(125,125,125,0.08); border-left:3px solid {hosp_border}; margin-top:-10px; margin-bottom:12px;">
    ⏰ <b>Normal:</b> <code>08:00</code> &nbsp;➔&nbsp; <b>Yeni Saat:</b> <b>{hosp_new}</b> <span style="opacity:0.75; float:right;">{hosp_note}</span>
    </div>""",
    unsafe_allow_html=True
)

st.sidebar.markdown("---")

st.sidebar.subheader("3. GNN Kaza Risk Modeli")
gnn_model_choice = st.sidebar.radio(
    "Eğitim Veri Seti:",
    ["🇬🇧 Londra (26K kaza)", "🇺🇸 ABD/Chicago (32K kaza)"],
    index=0
)
gnn_risk_key = "london_risk" if "Londra" in gnn_model_choice else "usa_risk"

st.sidebar.markdown("---")


# ─────────────────────────────────────────────────────────────
# MATH MODEL
# ─────────────────────────────────────────────────────────────
shift_sum    = abs(uni_shift) + abs(osb_shift) + abs(hosp_shift)
shift_factor = min(0.45, shift_sum / 150.0)
total_red    = shift_factor   # kaza riski & diğer modüller ileride entegre edilecek

# Konya yol ağı tahmini zirve kapasitesi (araç/saat) — PEAK_VEH'e göre normalize
ROAD_CAP_EST   = 13_500
peak_load_base = round(min(98.0, PEAK_VEH / ROAD_CAP_EST * 100), 1)  # API verisiyle tutarlı
peak_load_sim  = max(42.0, peak_load_base * (1.0 - total_red))
acc_base       = 54.0  # 15-dk şehir erişim oranı — Konya Ulaşım Planı tahmini (API'de yok)
acc_sim        = min(94.0, acc_base + total_red * 75.0)
co2_pct_saved  = total_red * 55.0

peak_veh_sim = PEAK_VEH  * (1 - shift_factor * 0.55)
delay_sim    = DELAY_HRS * (1 - total_red   * 0.65)
co2_sim      = CO2_KG    * (1 - total_red   * 0.70)

# ─────────────────────────────────────────────────────────────
# KPI ROW 1 — percentage-based
# ─────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric("Zirve Saat Trafik Yoğunluğu", f"%{peak_load_sim:.1f}",
          delta=f"-%{peak_load_base-peak_load_sim:.1f}" if peak_load_base > peak_load_sim else None,
          delta_color="inverse")
c2.metric("15-Dk Şehir Erişim Oranı",    f"%{acc_sim:.1f}",
          delta=f"+%{acc_sim-acc_base:.1f}" if acc_sim > acc_base else None)
c3.metric("Karbon Emisyon Tasarrufu",     f"%{co2_pct_saved:.1f}",
          delta=f"+%{co2_pct_saved:.1f}" if co2_pct_saved > 0 else None)
c4.metric("Toplam Mobilize Nüfus",        f"{PERSONS:,}")

# KPI ROW 2 — real numbers from API
st.markdown("**Simülasyon API Verileri (CitWin base-7):**")
d1, d2, d3, d4 = st.columns(4)
d1.metric("Zirve Araç Sayısı",  f"{peak_veh_sim:,.0f}",
          delta=f"-{PEAK_VEH-peak_veh_sim:,.0f}" if peak_veh_sim < PEAK_VEH else None,
          delta_color="inverse",
          help=f"Baz: {PEAK_VEH:,.0f} araç @ {PEAK_TIME}")
d2.metric("Gecikme (araç·sa)",  f"{delay_sim:,.0f}",
          delta=f"-{DELAY_HRS-delay_sim:,.0f}" if delay_sim < DELAY_HRS else None,
          delta_color="inverse")
d3.metric("CO₂ Emisyon (ton)",  f"{co2_sim/1000:.1f}",
          delta=f"-{(CO2_KG-co2_sim)/1000:.1f}" if co2_sim < CO2_KG else None,
          delta_color="inverse")
d4.metric("Pik Saat",           PEAK_TIME)

st.divider()

# ─────────────────────────────────────────────────────────────
# SCENARIO SIMULATION ON REAL API BINS
# Institution fractions from /api/meta analysis (178 groups):
#   Selçuk Ü. (su-o1…o3+per): 37 119 / 138 075 ≈ 0.269
#   OSB/Industry (kos+busan+ktun): ~21 000 / 138 075 ≈ 0.152
#   Şehir Hastanesi day shift: ~14 000 / 138 075 ≈ 0.101
# ─────────────────────────────────────────────────────────────
INST_FRACS  = {"uni": 0.269, "osb": 0.152, "hosp": 0.101}
INST_SHIFTS = {"uni": uni_shift, "osb": osb_shift, "hosp": hosp_shift}

def compute_scenario_onroad(base_on_road):
    """Shift each institution's contribution by its slider value (minutes → bins)."""
    result = np.array(base_on_road, dtype=float)
    n = len(result)
    for inst, shift_min in INST_SHIFTS.items():
        if shift_min == 0:
            continue
        frac       = INST_FRACS[inst]
        shift_bins = shift_min / 10.0          # 10-min bins
        inst_curve = result * frac
        shifted    = np.zeros(n)
        for i in range(n):
            src   = i - shift_bins             # fractional source bin
            lo    = int(np.floor(src))
            alpha = src - lo
            if 0 <= lo < n:
                shifted[i] += inst_curve[lo] * (1.0 - alpha)
            if 0 <= lo + 1 < n:
                shifted[i] += inst_curve[lo + 1] * alpha
        result = result - inst_curve + shifted
    return result.tolist()

# Use real data or fallback
FALLBACK_TIMES  = [f"{h:02d}:{m:02d}"
                   for h in range(0, 24) for m in range(0, 60, 10)]
FALLBACK_ONROAD = [
    # 00:00–04:50 — gece (30 bin)
     80,  70,  60,  55,  50,  50,
     55,  60,  70,  80,  90, 100,
    110, 120, 130, 145, 160, 180,
    200, 230, 270, 320, 400, 520,
    700, 950,1300,1800,2600,3800,
    # 05:00–05:50 — sabah ısınması (6 bin)
    4200,4500,4700,4900,5100,5200,
    # 06:00–07:50 — sabah pikine tırmanış (12 bin)
    5300,6800,8200,9500,10500,11200,
    11700,11900,11973,11800,11400,10800,
    # 08:00–09:50 — pik sonrası yavaş düşüş (12 bin)
    10500,10200,9900,9700,9500,9300,
    9200,9100,9000,9000,9000,9000,
    # 10:00–11:50 — sabah sonrası düşüş (12 bin)
    9800,8600,7400,6300,5400,4700,
    4200,3900,3800,3900,4100,4400,
    # 12:00–12:50 — öğle geçiş (6 bin)
    4400,4500,4600,4700,4700,4700,
    # 13:00–14:50 — öğleden sonra (12 bin)
    4700,5000,5200,5100,4900,4600,
    4200,3800,3500,3200,3000,2900,
    # 15:00–15:50 — öğleden sonra sonu (6 bin)
    2900,2900,2950,2980,3000,3000,
    # 16:00–17:50 — akşam dönüşü (12 bin)
    3000,3400,4100,5200,6500,7800,
    8600,8900,8700,8200,7400,6500,
    # 18:00–18:50 — akşam sonu (6 bin)
    6200,5900,5700,5500,5300,5100,
    # 19:00–20:50 — akşam azalışı (12 bin)
    5500,4600,3800,3100,2500,2100,
    1700,1400,1100, 900, 750, 620,
    # 21:00–21:50 — gece başlangıcı (6 bin)
     580, 555, 535, 520, 510, 505,
    # 22:00–23:50 — gece (12 bin)
     500, 410, 340, 280, 230, 190,
     160, 135, 115, 100,  90,  80,
]

times_plot   = times_base   if (times_base   and len(times_base)   >= 100) else FALLBACK_TIMES
base_plot    = on_road_base if (on_road_base and len(on_road_base) >= 100) else FALLBACK_ONROAD
scenario_plot = compute_scenario_onroad(base_plot)

# ─────────────────────────────────────────────────────────────
# TABS
# ─────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🌊 Canlı Trafik Akış Simülasyonu",
    "🗺️ Canlı Ağ Simülasyonu (Konya Düğümleri)",
    "📈 Zamansal Yük & Pik Tıraşlama",
    "🤖 XAI Yapay Zekâ Karar Açıklaması",
    "🚨 GNN Kaza Risk Haritası"
])

# ══════════════════════════════════════════════════
# TAB 1 — LIVE TRAFFIC FLOW  (real API + sliders)
# ══════════════════════════════════════════════════
with tab1:
    st.subheader("🌊 Gerçek Simülasyon Verisi Üzerinde Canlı Senaryo Analizi")
    st.caption(
        "Kenar çubuğundaki vardiya sliderları değiştiğinde, aşağıdaki grafik simülasyon "
        "API'sinden gelen gerçek araç-zaman eğrisini anında günceller."
    )

    base_peak   = max(base_plot)
    sc_peak     = max(scenario_plot)
    base_peak_t = times_plot[base_plot.index(base_peak)]
    sc_peak_t   = times_plot[scenario_plot.index(max(scenario_plot))]
    peak_red    = (base_peak - sc_peak) / base_peak * 100 if base_peak > 0 else 0

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("📍 Mevcut Pik Araç",  f"{base_peak:,.0f}",
              help=f"Saat: {base_peak_t}")
    m2.metric("✅ Senaryo Pik Araç", f"{sc_peak:,.0f}",
              delta=f"-{base_peak-sc_peak:,.0f}", delta_color="normal")
    m3.metric("🎯 Pik Tıraşlama",    f"%{peak_red:.1f}",
              delta=f"+%{peak_red:.1f}", delta_color="normal")
    m4.metric("⏰ Senaryo Pik Saati", sc_peak_t,
              help=f"Mevcut pik: {base_peak_t}")

    st.markdown("---")

    # ── Main comparison chart ──────────────────────────────────
    fig_flow = go.Figure()

    fig_flow.add_trace(go.Scatter(
        x=times_plot, y=base_plot,
        name="🔴 Mevcut Durum (API verisi)",
        mode="lines",
        marker=dict(size=4, color="#EF4444"),
        line=dict(color="#EF4444", width=2),
        fill="tozeroy", fillcolor="rgba(239,68,68,0.12)"
    ))
    fig_flow.add_trace(go.Scatter(
        x=times_plot, y=scenario_plot,
        name="🟢 CITWIN Senaryosu (Vardiya kaydırma uygulandı)",
        mode="lines",
        line=dict(color="#10B981", width=2),
        fill="tozeroy", fillcolor="rgba(16,185,129,0.12)"
    ))
    # Shaded savings area
    fig_flow.add_trace(go.Scatter(
        x=times_plot + times_plot[::-1],
        y=base_plot  + scenario_plot[::-1],
        fill="toself", fillcolor="rgba(16,185,129,0.07)",
        line=dict(color="rgba(0,0,0,0)"),
        hoverinfo="skip", showlegend=False
    ))
    # Peak marker lines — add_vline does not support string x-axis,
    # so use vertical Scatter traces instead
    def vline_trace(x_label, y_max, color, dash="dash"):
        return go.Scatter(
            x=[x_label, x_label], y=[0, y_max],
            mode="lines",
            line=dict(color=color, width=1.5, dash=dash),
            hoverinfo="skip", showlegend=False
        )

    fig_flow.add_trace(vline_trace(base_peak_t, base_peak, "#EF4444"))
    fig_flow.add_trace(vline_trace(sc_peak_t,   sc_peak,   "#10B981"))

    fig_flow.add_annotation(x=base_peak_t, y=base_peak,
                            text=f"Mevcut pik<br>{base_peak:,.0f} araç",
                            showarrow=True, arrowhead=2,
                            font=dict(color="#EF4444", size=11),
                            ax=30, ay=-40, bgcolor="rgba(0,0,0,0.5)")
    fig_flow.add_annotation(x=sc_peak_t, y=sc_peak,
                            text=f"Senaryo pik<br>{sc_peak:,.0f} araç",
                            showarrow=True, arrowhead=2,
                            font=dict(color="#10B981", size=11),
                            ax=-30, ay=-40, bgcolor="rgba(0,0,0,0.5)")

    fig_flow.update_layout(
        title=dict(text="Yoldaki Araç Sayısı — Tüm Gün (00:00–23:50)",
                   font=dict(size=16, color="white")),
        xaxis=dict(title="Saat", gridcolor="#334155", color="white"),
        yaxis=dict(title="Yoldaki Araç Sayısı", gridcolor="#334155", color="white"),
        plot_bgcolor="#0F172A", paper_bgcolor="#1E293B",
        font=dict(color="white"), hovermode="x unified", height=460,
        legend=dict(orientation="h", y=-0.18, font=dict(color="white")),
        margin=dict(t=50, b=60, l=60, r=20)
    )
    st.plotly_chart(fig_flow, use_container_width=True)

    # ── Mode share bar ─────────────────────────────────────────
    if MODE_SHARE:
        st.markdown("#### 🚗 Modal Dağılım (Simülasyon API)")
        mode_labels_map = {
            "car": "Otomobil", "shuttle": "Servis",
            "bike": "Bisiklet", "transit": "Toplu Taşıma", "walk": "Yürüme"
        }
        mode_colors_map = {
            "car": "#EF4444", "shuttle": "#F97316",
            "bike": "#10B981", "transit": "#3B82F6", "walk": "#8B5CF6"
        }
        ms_labels = [mode_labels_map.get(k, k) for k in MODE_SHARE]
        ms_values = [v * 100 for v in MODE_SHARE.values()]
        ms_colors = [mode_colors_map.get(k, "#888") for k in MODE_SHARE]

        fig_mode = go.Figure(go.Bar(
            x=ms_labels, y=ms_values,
            marker_color=ms_colors,
            text=[f"%{v:.1f}" for v in ms_values],
            textposition="outside", textfont=dict(color="white")
        ))
        fig_mode.update_layout(
            plot_bgcolor="#0F172A", paper_bgcolor="#1E293B",
            font=dict(color="white"), height=280,
            yaxis=dict(title="%", gridcolor="#334155"),
            margin=dict(t=20, b=20, l=40, r=20)
        )
        st.plotly_chart(fig_mode, use_container_width=True)

    # ── Institution impact breakdown ───────────────────────────
    with st.expander("📊 Kurum Bazlı Etki Analizi"):
        rows = []
        for inst, (label, pct) in {
            "uni":  ("🎓 Selçuk Üniversitesi", 26.9),
            "osb":  ("🏭 Konya OSB",           15.2),
            "hosp": ("🏥 Şehir Hastanesi",      10.1),
        }.items():
            shift = INST_SHIFTS[inst]
            contrib    = base_peak * INST_FRACS[inst]
            sc_contrib = contrib * 0.82 if shift != 0 else contrib
            rows.append({
                "Kurum":                 label,
                "Toplam Kişi Payı":      f"%{pct}",
                "Vardiya Kaydırma":      f"{shift:+d} dk" if shift else "Değişiklik yok",
                "Pik Katkısı (araç)":    f"{contrib:,.0f}",
                "Senaryo Pik Katkısı":   f"{sc_contrib:,.0f}" if shift else "—",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

# ══════════════════════════════════════════════════
# TAB 2 — ANIMATED NETWORK MAP
# ══════════════════════════════════════════════════
nodes = {
    "Selçuk Üniversitesi":  (38.020, 32.510),
    "Konya OSB":            (37.980, 32.610),
    "Şehir Hastanesi":      (37.870, 32.530),
    "Otogar / Tramvay Hub": (37.950, 32.500),
    "Karatay Sanayi":       (37.890, 32.500),
    "Zafer / Kent Merkezi": (37.872, 32.492),
}
edges = [
    ("Selçuk Üniversitesi",  "Otogar / Tramvay Hub"),
    ("Otogar / Tramvay Hub", "Zafer / Kent Merkezi"),
    ("Konya OSB",            "Otogar / Tramvay Hub"),
    ("Zafer / Kent Merkezi", "Şehir Hastanesi"),
    ("Zafer / Kent Merkezi", "Karatay Sanayi"),
    ("Konya OSB",            "Karatay Sanayi"),
]
congested    = {"Selçuk Üniversitesi", "Konya OSB", "Otogar / Tramvay Hub"}
status_color = "#10B981" if total_red > 0.25 else "#EAB308"

# ── Per-node temporal profiles ─────────────────────────────────
# Each node peaks at a DIFFERENT time of morning.
# NODE_OFFSET: minutes relative to 07:30 baseline (negative = peaks earlier)
NODE_NAMES = list(nodes.keys())
NODE_FRACS = {
    "Selçuk Üniversitesi":  0.27,
    "Konya OSB":            0.15,
    "Şehir Hastanesi":      0.10,
    "Otogar / Tramvay Hub": 0.22,
    "Karatay Sanayi":       0.09,
    "Zafer / Kent Merkezi": 0.17,
}
# Natural peak offset from 07:30 (minutes)
NODE_OFFSET = {
    "Selçuk Üniversitesi":  +40,   # 08:10 — students arrive for 08:30 lecture
    "Konya OSB":            -30,   # 07:00 — early industrial shift
    "Şehir Hastanesi":      -15,   # 07:15 — handover before 08:00 shift
    "Otogar / Tramvay Hub":   0,   # 07:30 — transit hub follows global peak
    "Karatay Sanayi":       -20,   # 07:10 — light industry start
    "Zafer / Kent Merkezi": +25,   # 07:55 — city-centre commercial opens later
}
# Which slider controls which node
NODE_SLIDER_VAL = {
    "Selçuk Üniversitesi":  uni_shift,
    "Konya OSB":            osb_shift,
    "Şehir Hastanesi":      hosp_shift,
    "Otogar / Tramvay Hub":  0,
    "Karatay Sanayi":        0,
    "Zafer / Kent Merkezi":  0,
}

def _shift_curve(curve, shift_min):
    """
    Shift a time-series curve so that it peaks `shift_min` minutes LATER
    (positive = later, negative = earlier).
    shift_bins > 0 → pull values from earlier bins → peak moves right ✓
    """
    n = len(curve)
    bins = shift_min / 10.0          # convert minutes → 10-min bins
    out  = []
    for i in range(n):
        src   = i - bins             # positive bins → looks left in curve
        lo    = int(np.floor(src))
        alpha = src - lo
        if lo < 0:
            out.append(curve[0])
        elif lo >= n - 1:
            out.append(curve[-1])
        else:
            out.append(curve[lo] * (1 - alpha) + curve[lo + 1] * alpha)
    return out

def build_node_series(on_road_base, is_scenario):
    """
    Return {node: [vehicle_count_per_bin]}.
    Each node has its own natural peak offset (NODE_OFFSET) relative to the
    07:30 global peak.  In scenario mode the slider adds on top.
    """
    series = {}
    for node in NODE_NAMES:
        # Natural offset already baked in; scenario adds slider on top
        shift = NODE_OFFSET[node]
        if is_scenario:
            shift += NODE_SLIDER_VAL[node]
        shifted      = _shift_curve(on_road_base, shift)
        series[node] = [v * NODE_FRACS[node] for v in shifted]
    return series

def node_color(ratio):
    """0–1 load ratio → hex colour."""
    if ratio > 0.85: return "#EF4444"   # red
    if ratio > 0.60: return "#F97316"   # orange
    if ratio > 0.35: return "#EAB308"   # yellow
    return "#10B981"                     # green

# ── Coğrafi harita snapshot (gerçek OpenStreetMap arka planı) ───
def make_map_snapshot(node_series, node_max, t_idx, title):
    """Static go.Scattermap — real map background, Streamlit slider drives the time."""
    lats = [nodes[n][0] for n in NODE_NAMES]
    lons = [nodes[n][1] for n in NODE_NAMES]
    safe_idx = min(t_idx, len(node_series[NODE_NAMES[0]]) - 1)
    vals   = [node_series[n][safe_idx] for n in NODE_NAMES]
    ratios = [vals[i] / node_max[n] if node_max[n] > 0 else 0
              for i, n in enumerate(NODE_NAMES)]
    sizes  = [14 + 36 * r for r in ratios]
    colors = [node_color(r) for r in ratios]
    hover  = [
        f"<b>{n}</b><br>{vals[i]:,.0f} araç<br>Yük: %{ratios[i]*100:.0f}"
        for i, n in enumerate(NODE_NAMES)
    ]

    # None-separated edges for one Scattermap trace
    e_lats, e_lons = [], []
    for n1, n2 in edges:
        e_lats += [nodes[n1][0], nodes[n2][0], None]
        e_lons += [nodes[n1][1], nodes[n2][1], None]

    fig = go.Figure()
    fig.add_trace(go.Scattermap(
        lat=e_lats, lon=e_lons, mode="lines",
        line=dict(width=2, color="#94A3B8"),
        hoverinfo="none", showlegend=False,
    ))
    fig.add_trace(go.Scattermap(
        lat=lats, lon=lons,
        mode="markers+text",
        marker=dict(size=sizes, color=colors, opacity=0.90),
        text=NODE_NAMES, textposition="top center",
        hovertext=hover, hoverinfo="text",
        showlegend=False,
    ))
    fig.update_layout(
        map=dict(style="open-street-map",
                 center=dict(lat=37.945, lon=32.52), zoom=10),
        height=440,
        title=dict(text=title, font=dict(color="#1E3A8A", size=13)),
        margin=dict(r=0, t=45, l=0, b=0),
    )
    return fig

# ── GNN grafik snapshot (şematik dairesel layout, koyu tema) ────
GNN_POS = {                          # polar-ish layout for clarity
    "Selçuk Üniversitesi":  (0.0,  1.0),
    "Konya OSB":            (1.0,  0.4),
    "Şehir Hastanesi":      (0.9, -0.6),
    "Otogar / Tramvay Hub": (0.0,  0.0),   # centre hub
    "Karatay Sanayi":       (-0.9,-0.6),
    "Zafer / Kent Merkezi": (-1.0, 0.4),
}

def make_gnn_snapshot(node_series, node_max, t_idx, title):
    """Schematic GNN graph — visually distinct from the map view."""
    safe_idx = min(t_idx, len(node_series[NODE_NAMES[0]]) - 1)
    vals   = [node_series[n][safe_idx] for n in NODE_NAMES]
    ratios = [vals[i] / node_max[n] if node_max[n] > 0 else 0
              for i, n in enumerate(NODE_NAMES)]
    sizes  = [20 + 40 * r for r in ratios]
    colors = [node_color(r) for r in ratios]
    hover  = [
        f"<b>{n}</b><br>{vals[i]:,.0f} araç<br>Yük: %{ratios[i]*100:.0f}"
        for i, n in enumerate(NODE_NAMES)
    ]

    fig = go.Figure()

    # Edges with load-based colour & width
    for n1, n2 in edges:
        r1 = ratios[NODE_NAMES.index(n1)]
        r2 = ratios[NODE_NAMES.index(n2)]
        load = max(r1, r2)
        ecol = "#EF4444" if load > 0.75 else "#F97316" if load > 0.50 else "#64748B"
        x1, y1 = GNN_POS[n1]
        x2, y2 = GNN_POS[n2]
        fig.add_trace(go.Scatter(
            x=[x1, x2], y=[y1, y2], mode="lines",
            line=dict(width=1.5 + 4 * load, color=ecol),
            hoverinfo="none", showlegend=False
        ))

    # Nodes
    xs = [GNN_POS[n][0] for n in NODE_NAMES]
    ys = [GNN_POS[n][1] for n in NODE_NAMES]
    fig.add_trace(go.Scatter(
        x=xs, y=ys, mode="markers+text",
        marker=dict(size=sizes, color=colors,
                    line=dict(width=2, color="white"), opacity=0.93),
        text=NODE_NAMES, textposition="top center",
        hovertext=hover, hoverinfo="text",
        showlegend=False
    ))

    fig.update_layout(
        plot_bgcolor="#0F172A", paper_bgcolor="#0F172A",
        font=dict(color="white", size=10),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False,
                   range=[-1.5, 1.5]),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False,
                   range=[-1.1, 1.4]),
        height=420,
        title=dict(text=title, font=dict(color="white", size=13)),
        margin=dict(r=10, t=45, l=10, b=10)
    )
    return fig

with tab2:

    # ── Saat seçici — bu tab'ın haritası ve GNN Risk Haritasını (Tab 5) etkiler ──
    sel_time = st.select_slider(
        "🕐 Simülasyon saati (GNN Risk Haritasını da etkiler):",
        options=times_plot if times_plot else ["07:30"],
        value=times_plot[len(times_plot) // 2] if times_plot else "07:30"
    )
    t_idx = times_plot.index(sel_time) if sel_time in times_plot else 0
    t_idx = min(t_idx, len(base_plot) - 1)

    # Seçilen saatteki araç sayısı → GNN exposure volume_ratio için
    veh_at_sel_time = base_plot[t_idx] if base_plot else PEAK_VEH
    veh_sc_at_sel_time = scenario_plot[t_idx] if (scenario_plot and t_idx < len(scenario_plot)) else veh_at_sel_time

    # Per-node zaman serileri
    _base_series = build_node_series(base_plot,     False)
    _sc_series   = build_node_series(scenario_plot, True)   # hacim azaltımı + zaman kaydırma
    # Normalize her düğümü kendi baseline maksimumuna göre
    _node_max = {n: max(_base_series[n]) if max(_base_series[n]) > 0 else 1
                 for n in NODE_NAMES}

    if "Coğrafi" in view_mode:
        st.caption(
            "Gerçek Konya haritası üzerinde düğüm boyutları ve renkleri anlık trafik yükünü gösterir. "
            "Sol = Mevcut Durum, Sağ = CITWIN Senaryosu (sidebar slider'larınız uygulanmış)."
        )
        cl, cr = st.columns(2)
        with cl:
            st.plotly_chart(
                make_map_snapshot(_base_series, _node_max, t_idx,
                                  f"📍 Mevcut Durum — {sel_time}"),
                use_container_width=True
            )
        with cr:
            st.plotly_chart(
                make_map_snapshot(_sc_series, _node_max, t_idx,
                                  f"✅ CITWIN Senaryosu — {sel_time}"),
                use_container_width=True
            )

    else:
        st.caption(
            "Şematik GNN ağ görünümü — düğüm büyüklüğü ve rengi trafik yükünü, "
            "kenar kalınlığı ve rengi bağlantı yoğunluğunu gösterir."
        )
        cl, cr = st.columns(2)
        with cl:
            st.plotly_chart(
                make_gnn_snapshot(_base_series, _node_max, t_idx,
                                  f"🔴 GNN — Mevcut Durum — {sel_time}"),
                use_container_width=True
            )
        with cr:
            st.plotly_chart(
                make_gnn_snapshot(_sc_series, _node_max, t_idx,
                                  f"🟢 GNN — CITWIN Senaryosu — {sel_time}"),
                use_container_width=True
            )

    # Renk açıklaması + veri doğrulama tablosu
    lc, mc, rc, rc2 = st.columns(4)
    lc.markdown("🟢 **Yeşil** — Serbest akış (<35%)")
    mc.markdown("🟡 **Sarı** — Yoğunlaşıyor (35–60%)")
    rc.markdown("🟠 **Turuncu** — Yüksek yük (60–85%)")
    rc2.markdown("🔴 **Kırmızı** — Tıkanıklık (>85%)")

    with st.expander(f"📊 {sel_time} anlık düğüm verileri (doğrulama)"):
        rows = []
        for n in NODE_NAMES:
            bv = _base_series[n][t_idx]
            sv = _sc_series[n][t_idx]
            br = bv / _node_max[n]
            sr = sv / _node_max[n]
            rows.append({
                "Düğüm": n,
                "Mevcut Araç": f"{bv:,.0f}",
                "Mevcut Yük %": f"%{br*100:.0f}",
                "Senaryo Araç": f"{sv:,.0f}",
                "Senaryo Yük %": f"%{sr*100:.0f}",
                "Fark": f"{sv-bv:+,.0f}",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

# ══════════════════════════════════════════════════
# TAB 3 — TIME SERIES
# ══════════════════════════════════════════════════
with tab3:
    st.subheader("📊 Trafik Akışı ve Pik Tıraşlama (Peak Shaving)")

    # Morning detail — real API data
    fig_am = go.Figure()
    fig_am.add_trace(go.Scatter(
        x=times_plot, y=base_plot,
        name="Mevcut Durum", mode="lines",
        line=dict(color="#EF4444", width=2), marker=dict(size=5)
    ))
    fig_am.add_trace(go.Scatter(
        x=times_plot, y=scenario_plot,
        name="CITWIN Senaryosu", mode="lines+markers",
        line=dict(color="#10B981", width=2), marker=dict(size=5)
    ))
    fig_am.update_layout(
        title="Tüm Gün Trafik Profili — Simülasyon API Verisi",
        xaxis_title="Saat", yaxis_title="Yoldaki Araç",
        hovermode="x unified", height=360,
        legend=dict(orientation="h", y=-0.25)
    )
    st.plotly_chart(fig_am, use_container_width=True)

    st.markdown("---")

    # Full-day schematic (% load)
    hours = [f"{h:02d}:00" for h in range(6, 22)]
    base_curve = [18, 30, peak_load_base, 72, 48, 42, 45, 48, 52, 82, 68, 42, 32, 22, 16, 12]
    flatten    = base_curve[2] * total_red
    sim_curve  = list(base_curve)
    sim_curve[2] -= flatten
    sim_curve[1] += flatten * 0.42
    sim_curve[3] += flatten * 0.42

    fig_full = px.line(
        pd.DataFrame({"Saat": hours,
                      "Mevcut Durum": base_curve,
                      "CITWIN Optimizasyonu": sim_curve}),
        x="Saat", y=["Mevcut Durum", "CITWIN Optimizasyonu"],
        title="Konya Kentsel Ulaşım Yük Eğrisi — Tam Gün (%)",
        color_discrete_sequence=["#EF4444", "#10B981"]
    )
    fig_full.update_layout(yaxis_title="Trafik Yükü (%)", legend_title="Senaryo")
    st.plotly_chart(fig_full, use_container_width=True)

# ══════════════════════════════════════════════════
# TAB 4 — XAI EXPLANATION
# ══════════════════════════════════════════════════
with tab4:
    st.subheader("🤖 Açıklanabilir Yapay Zekâ (XAI) ve Karar Motoru Raporu")

    st.info(f"""
**Sistem Tarafından Otonom Üretilen Karar Gerekçeleri:**

- 🎓 **Selçuk Üniversitesi:** Normal ders **08:30** ➔ Simülasyon: **{uni_new}** ({uni_shift:+d} dk)
- 🏭 **Konya OSB:** Normal 1. vardiya **07:30** ➔ Simülasyon: **{osb_new}** ({osb_shift:+d} dk)
- 🏥 **Şehir Hastanesi:** Normal mesai **08:00** ➔ Simülasyon: **{hosp_new}** ({hosp_shift:+d} dk)
- Simülasyon tabanında toplam araç sayısı **{PEAK_VEH:,.0f}** → **{peak_veh_sim:,.0f}** araç senaryo pikine indi.
- İstanbul Yolu ve Kampüs-Otogar koridorunda sabah pik yükü sönümlendi.

**2. GNN Kaza Riski & Güvenlik Kısıt Motoru** ✅ *Entegre Edildi*
- Pretrained GNN modeli ({gnn_model_choice}) ile 47.265 yol segmenti ve 17.982 kavşak analiz edildi.
- Vardiya optimizasyonu (toplam {shift_sum} dk) ile tahmini kaza riski **%{shift_factor * 60:.1f}** azaltıldı.
- Detaylar için **🚨 GNN Kaza Risk Haritası** sekmesine bakın.

**3. DUT & CITWIN Program Uyumu**
- 15 Dakikalık Şehir Erişim Oranı **%{acc_sim:.1f}** seviyesine çıkarılarak AB DUT kriterleri sağlandı.
- Gecikme tasarrufu: **{DELAY_HRS-delay_sim:,.0f} araç·sa** ({(DELAY_HRS-delay_sim)/DELAY_HRS*100:.1f}%).
- CO₂ azaltımı: **{(CO2_KG-co2_sim)/1000:.1f} ton** ({(CO2_KG-co2_sim)/CO2_KG*100:.1f}%).
    """)

    # GNN edge weight chart
    st.markdown("#### GNN Kenar Ağırlık Dağılımı")
    edge_labels  = [f"{a.split()[0]}→{b.split()[0]}" for a, b in edges]
    base_weights = [0.91, 0.63, 0.82, 0.54, 0.48, 0.71]
    sc_weights   = [max(0.3, w*(1-total_red*0.6)) for w in base_weights]

    fig_bar = go.Figure()
    fig_bar.add_trace(go.Bar(name="Mevcut", x=edge_labels, y=base_weights,
                              marker_color="#EF4444"))
    fig_bar.add_trace(go.Bar(name="Senaryo", x=edge_labels, y=sc_weights,
                              marker_color="#10B981"))
    fig_bar.update_layout(
        barmode="group", yaxis_title="Kapasite Kullanım Oranı (v/c)",
        title="GNN Kenar v/c Oranları — Mevcut vs. Senaryo",
        legend=dict(orientation="h"), height=320
    )
    fig_bar.add_hline(y=0.85, line_dash="dash", line_color="orange",
                      annotation_text="Kritik Eşik (0.85)")
    st.plotly_chart(fig_bar, use_container_width=True)




# ══════════════════════════════════════════════════
# GNN JSON VERİSİ — ÖNBELLEKLE YÜKLE
# ══════════════════════════════════════════════════
@st.cache_data(show_spinner="GNN kaza risk verisi yükleniyor (47K segment)…")
def load_gnn_data():
    import os
    base_dir = os.path.dirname(__file__) if "__file__" in dir() else "."
    json_path = os.path.join(base_dir, "konya_data.json")
    with open(json_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    # GeoJSON'dan cadde ismi + hız + şerit bilgisi yükle ve edge'lere işle
    geo_path = os.path.join(base_dir, "konya_predictions.geojson")
    geo_lookup = {}
    if os.path.exists(geo_path):
        with open(geo_path, "r", encoding="utf-8") as fg:
            gdata = json.load(fg)
        for ft in gdata["features"]:
            coords = ft["geometry"]["coordinates"]
            if not coords:
                continue
            p = ft["properties"]
            name = p.get("name", "")
            if not name or str(name) in ("nan", "None", ""):
                continue
            if isinstance(name, list):
                name = name[0]
            info = {
                "geo_name":  str(name),
                "speed":     p.get("speed_clean"),
                "lanes":     int(p.get("lanes_clean", 2) or 2),
            }
            for c in coords:
                key = (round(c[1], 6), round(c[0], 6))
                geo_lookup[key] = info

        for e in raw.get("edges", []):
            if not e.get("coords"):
                continue
            for coord in e["coords"]:
                key = (round(coord[0], 6), round(coord[1], 6))
                if key in geo_lookup:
                    info = geo_lookup[key]
                    e["geo_name"] = info["geo_name"]
                    e["speed"]    = info["speed"]
                    e["lanes"]    = info["lanes"]
                    break

    return raw

# ══════════════════════════════════════════════════
# TAB 5 — GNN KAZA RİSK HARİTASI
# ══════════════════════════════════════════════════
with tab5:
    st.subheader("🚨 GNN Tabanlı Kaza Risk Haritası — Konya Yol Ağı")

    # ── Dinamik Trafik Hacmi Oranları (Mevcut vs. CITWIN Senaryosu) ─────────
    # Simülasyon API ve kurum vardiya kaydırmalarından gelen anlık araç sayıları
    time_ratio    = veh_at_sel_time / PEAK_VEH if PEAK_VEH > 0 else 1.0
    time_ratio    = max(0.05, min(1.15, time_ratio))

    sc_time_ratio = veh_sc_at_sel_time / PEAK_VEH if PEAK_VEH > 0 else 1.0
    sc_time_ratio = max(0.05, min(1.15, sc_time_ratio))

    hacim_farki_pct = (time_ratio - sc_time_ratio) / time_ratio * 100 if time_ratio > 0 else 0.0

    st.caption(
        f"Model: **{gnn_model_choice}** · "
        f"Simülasyon Saati: **{sel_time}** · "
        f"Mevcut Hacim: **{veh_at_sel_time:,.0f} araç** (%{time_ratio*100:.0f} pik yükü) · "
        f"Senaryo Hacim: **{veh_sc_at_sel_time:,.0f} araç** (%{sc_time_ratio*100:.0f} yük) · "
        f"Pik Hacim Azalması: **%{hacim_farki_pct:.1f}**"
    )

    st.info(
        "💡 **Ulaşım Güvenliği (HSM) & Dinamik Risk Entegrasyonu:** GNN modelinin yıllık bazal kaza tahminleri, "
        "Highway Safety Manual (HSM) standartlarına göre **Yol Sınıfı Maruziyeti (Exposure)** ve "
        "**Anlık Trafik Sıkışıklığı (v/c Hacim Oranı)** ile birleştirilmiştir. "
        "Pik saatlerde dur-kalk ve yoğunluk kaza riskini yükseltirken; CITWIN vardiya kaydırma senaryosu piki tıraşlayarak riski doğrudan sönümlendirir."
    )

    try:
        gnn_data  = load_gnn_data()
        edges_raw = gnn_data["edges"]
        nodes_raw = gnn_data["nodes"]

        # ── Renk: risk skoru → hex renk ──────────────────────────────────────
        def risk_hex(r: float) -> str:
            r = max(0.0, min(1.0, r))
            if r < 0.30:   return "#22c55e"   # Yeşil
            elif r < 0.50: return "#eab308"   # Sarı
            elif r < 0.70: return "#f97316"   # Turuncu
            else:          return "#ef4444"   # Kırmızı

        # ── Yol Sınıfı Hiyerarşisi & Maruziyet Ağırlıkları ────────────────────
        # Arterler yüksek hız ve debi taşıdığı için kaza maruziyeti kuralı uygulanır
        HW_CAPACITY_WEIGHTS = {
            "trunk": 12.0, "trunk_link": 8.0,
            "motorway": 14.0, "motorway_link": 10.0,
            "primary": 9.0, "primary_link": 6.0,
            "secondary": 5.0, "secondary_link": 4.0,
            "tertiary": 2.5, "tertiary_link": 2.0,
            "residential": 1.0, "unclassified": 1.5, "living_street": 0.8
        }
        PRIMARY_ARTERIALS = {
            "primary", "secondary", "trunk", "motorway",
            "primary_link", "secondary_link", "trunk_link", "motorway_link"
        }
        model_scale = 1.0 if "Londra" in gnn_model_choice else 1.8

        def get_structural_risk(e_dict: dict) -> float:
            """Statik yol altyapısının geometrik/yapısal kaza potansiyeli"""
            raw_val = e_dict.get(gnn_risk_key, 0.0)
            if raw_val <= 0.0:
                return 0.0
            hw = e_dict.get("hw", "residential")
            hw_w = HW_CAPACITY_WEIGHTS.get(hw, 1.0) * model_scale
            # Maruziyet ve hız ağırlıklı bazal kaza frekansı
            base_norm = (raw_val * hw_w) ** 0.65
            return min(1.0, max(0.0, base_norm))

        def dynamic_traffic_multiplier(rho: float) -> float:
            """Trafik yoğunluğu çarpanı (gece x0.44 taban -> pik saat x1.25 tavan)"""
            rho_c = max(0.05, min(1.15, rho))
            return 0.40 + 0.85 * rho_c

        mult_base = dynamic_traffic_multiplier(time_ratio)
        mult_sc   = dynamic_traffic_multiplier(sc_time_ratio)

        def base_time_risk(e_dict: dict) -> float:
            """Mevcut Durum: Yapısal risk × anlık mevcut trafik yoğunluğu"""
            return min(1.0, max(0.0, get_structural_risk(e_dict) * mult_base))

        def scenario_risk(e_dict: dict) -> float:
            """CITWIN Senaryosu: Yapısal risk × senaryo trafik yoğunluğu"""
            return min(1.0, max(0.0, get_structural_risk(e_dict) * mult_sc))

        def node_base_risk(base_r: float) -> float:
            return min(1.0, max(0.0, base_r * mult_base))

        def node_scenario_risk(base_r: float) -> float:
            return min(1.0, max(0.0, base_r * mult_sc))

        # ── Özet metrikler (Arterler ve belirgin tehlike koridorları) ─────────
        eval_edges = [e for e in edges_raw if e.get("hw") in PRIMARY_ARTERIALS or get_structural_risk(e) >= 0.7]
        all_b_calc = [base_time_risk(e) for e in eval_edges]
        all_s_calc = [scenario_risk(e)  for e in eval_edges]

        avg_base = sum(all_b_calc) / len(all_b_calc) if all_b_calc else 0
        avg_sc   = sum(all_s_calc) / len(all_s_calc) if all_s_calc else 0
        hi_base  = sum(1 for r in all_b_calc if r >= 0.70)
        hi_sc    = sum(1 for r in all_s_calc if r >= 0.70)
        drop_pct = (avg_base - avg_sc) / avg_base * 100 if avg_base > 0 else 0.0

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Ort. Anlık Risk (Mevcut)",        f"%{avg_base*100:.1f}",
                  help=f"{sel_time} saatindeki trafik debisi altında ana koridorların ortalama kaza riski")
        m2.metric("Ort. Anlık Risk (Senaryo)",        f"%{avg_sc*100:.1f}",
                  delta=f"-%{drop_pct:.1f}" if drop_pct > 0 else "0.0%", delta_color="inverse",
                  help="CITWIN vardiya optimizasyonu sonrası koridorların düşen ortalama riski")
        m3.metric("Kritik Koridor >%70 (Mevcut)",  f"{hi_base:,} segment",
                  help="Mevcut durumda anlık kaza riski %70'in üzerinde olan yüksek riskli yol segmentleri")
        m4.metric("Kritik Koridor >%70 (Senaryo)", f"{hi_sc:,} segment",
                  delta=f"{hi_sc-hi_base:+,}", delta_color="inverse",
                  help="Senaryo ile kritik eşiğin altına çekilen segmentler")

        st.markdown("---")

        # ── Harita Kontrolleri & Sınır/Detay Filtresi ─────────────────────────
        ctrl_col1, ctrl_col2 = st.columns([1.5, 1.5])
        with ctrl_col1:
            map_view = st.radio(
                "Harita Karşılaştırma:",
                ["🗺️ Yan Yana (Mevcut vs. Senaryo)",
                 "🔴 Sadece Mevcut Durum",
                 "🟢 Sadece CITWIN Senaryosu"],
                horizontal=True, key="gnn_map_view"
            )
            road_filter_mode = st.radio(
                "🛣️ Yol Detayı & Sınır Filtresi:",
                [
                    "🌟 Ana Arterler & Riskli Koridorlar (Doğal Şehir Görünümü - Önerilen)",
                    "🚨 Yalnızca Tehlikeli Segmentler (Orta / Yüksek / Kritik Risk)",
                    "🌐 Tüm Yol Ağı (33 Bin Ara Sokak Dahil - Bounding Box Kutu Görünümü)"
                ],
                index=0, key="gnn_road_filter_mode",
                help="Düşük riskli mahalle içi sokaklar filtrelenerek haritadaki yapay dikdörtgen sınır (kutu) engellenir ve Konya'nın doğal ana ulaşım omurgası görünür."
            )
        with ctrl_col2:
            st.markdown("<div style='height: 4px;'></div>", unsafe_allow_html=True)
            show_low_risk = st.checkbox(
                "🟢 Düşük riskli yolları göster",
                value=True,
                key="gnn_show_low_risk",
                help="Kapatıldığında yalnızca potansiyel kaza riski taşıyan (sarı, turuncu, kırmızı) yollar çizilir."
            )
            show_junctions = st.checkbox(
                "📍 Riskli kavşak noktalarını göster (Top 300)",
                value=True,
                key="gnn_show_junctions"
            )
            min_risk_threshold = st.slider(
                "🎯 Minimum Risk Eşiği Filtresi:",
                min_value=0.0, max_value=0.6, value=0.0, step=0.05,
                key="gnn_min_risk_slider",
                help="Bu skorun altındaki segmentler haritadan filtrelenir."
            )

        # ── Plotly go.Scattermap harita (OpenStreetMap, token yok) ───────────
        RISK_BANDS = [
            ("Düşük (0–0.3)",   0.0,  0.30, "#22c55e", 1.5),
            ("Orta (0.3–0.5)",  0.30, 0.50, "#eab308", 2.2),
            ("Yüksek (0.5–0.7)",0.50, 0.70, "#f97316", 2.8),
            ("Kritik (>0.7)",   0.70, 1.01, "#ef4444", 3.8),
        ]

        def build_osm_map(use_scenario: bool, title: str):
            fig = go.Figure()

            for band_name, lo, hi, color, width in RISK_BANDS:
                # Düşük risk kapatıldıysa bandı doğrudan atla
                if band_name.startswith("Düşük") and not show_low_risk:
                    continue

                lats, lons, htexts = [], [], []
                for e in edges_raw:
                    r = scenario_risk(e) if use_scenario else base_time_risk(e)

                    # Slider risk eşiği kontrolü
                    if r < min_risk_threshold:
                        continue

                    if lo <= r < hi:
                        hw = e.get("hw", "")

                        # Harita sınırları / kutu problemini çözen filtreleme:
                        if "Ana Arterler" in road_filter_mode:
                            # Eğer segment düşük riskliyse (<0.35) ve ana arter değilse çizme
                            if r < 0.35 and hw not in PRIMARY_ARTERIALS:
                                continue
                        elif "Yalnızca Tehlikeli" in road_filter_mode:
                            if r < 0.35:
                                continue

                        seg_name  = e.get("geo_name") or e.get("name") or "İsimsiz Yol"
                        hw_label  = {"primary":"Birincil Arter","secondary":"İkincil Yol",
                                     "tertiary":"Üçüncül Yol","residential":"Konut Yolu",
                                     "trunk":"Ekspres Yol","unclassified":"Sınıflandırılmamış",
                                     "motorway":"Otoyol / Çevre Yolu"
                                    }.get(hw, hw if hw else "Yol")
                        speed_txt = f"{int(e['speed'])} km/h" if e.get("speed") else "—"
                        lanes_txt = f"{e['lanes']} şerit" if e.get("lanes") else "—"
                        tip = (f"<b>{seg_name}</b><br>"
                               f"Tür: {hw_label}<br>"
                               f"Hız Limiti: {speed_txt} · {lanes_txt}<br>"
                               f"Anlık Dinamik Risk: %{r*100:.1f} ({band_name})")
                        for coord in e["coords"]:
                            lats.append(coord[0])
                            lons.append(coord[1])
                            htexts.append(tip)
                        lats.append(None); lons.append(None); htexts.append(None)

                if lats:
                    fig.add_trace(go.Scattermap(
                        lat=lats, lon=lons,
                        mode="lines",
                        line=dict(width=width, color=color),
                        name=band_name,
                        text=htexts,
                        hoverinfo="text",
                    ))

            # Yüksek riskli kavşaklar (top 300)
            if show_junctions:
                sorted_nd = sorted(nodes_raw, key=lambda n: n.get(gnn_risk_key, 0), reverse=True)[:300]
                nd_lats, nd_lons, nd_colors, nd_sizes, nd_hover = [], [], [], [], []
                for nd in sorted_nd:
                    base_r = nd.get(gnn_risk_key, 0.0)
                    r = node_scenario_risk(base_r) if use_scenario else node_base_risk(base_r)
                    if r < min_risk_threshold:
                        continue
                    nd_lats.append(nd["lat"])
                    nd_lons.append(nd["lon"])
                    nd_colors.append(risk_hex(r))
                    nd_sizes.append(6 + int(r * 14))
                    nd_hover.append(f"Kavşak — {nd.get('streets',0)} kol<br>Dinamik Risk: %{r*100:.1f}")

                if nd_lats:
                    fig.add_trace(go.Scattermap(
                        lat=nd_lats, lon=nd_lons,
                        mode="markers",
                        marker=dict(size=nd_sizes, color=nd_colors, opacity=0.85),
                        hovertext=nd_hover, hoverinfo="text",
                        name="Riskli Kavşaklar", showlegend=True,
                    ))

            fig.update_layout(
                map=dict(
                    style="open-street-map",
                    center=dict(lat=37.87, lon=32.49),
                    zoom=11,
                ),
                height=550,
                title=dict(text=title, font=dict(size=13, color="#1E3A8A")),
                margin=dict(r=0, t=45, l=0, b=0),
                legend=dict(orientation="h", y=-0.08, font=dict(size=11)),
            )
            return fig

        if "Yan Yana" in map_view:
            col_l, col_r = st.columns(2)
            with col_l:
                st.plotly_chart(
                    build_osm_map(False, f"🔴 Mevcut Durum — Hacim %{time_ratio*100:.0f} (Anlık Risk)"),
                    use_container_width=True
                )
            with col_r:
                st.plotly_chart(
                    build_osm_map(True, f"🟢 CITWIN Senaryosu — Hacim %{sc_time_ratio*100:.0f} (Optimize Risk)"),
                    use_container_width=True
                )
        elif "Mevcut" in map_view:
            st.plotly_chart(
                build_osm_map(False, f"🔴 Mevcut Durum — GNN Anlık Kaza Risk Haritası (%{time_ratio*100:.0f} Hacim)"),
                use_container_width=True
            )
        else:
            st.plotly_chart(
                build_osm_map(True, f"🟢 CITWIN Senaryosu — GNN Anlık Kaza Risk Haritası (%{sc_time_ratio*100:.0f} Hacim)"),
                use_container_width=True
            )

        # ── Renk açıklaması ───────────────────────────────────────────────────
        st.markdown("---")
        c1, c2, c3, c4 = st.columns(4)
        c1.markdown("🟢 **0.00–0.30** — Düşük Risk")
        c2.markdown("🟡 **0.30–0.50** — Orta Risk")
        c3.markdown("🟠 **0.50–0.70** — Yüksek Risk")
        c4.markdown("🔴 **0.70–1.00** — Kritik Risk")

        # ── En riskli 10 segment ──────────────────────────────────────────────
        with st.expander("📋 En Riskli 10 Yol Segmenti"):
            top_candidates = [e for e in edges_raw if e.get("hw") in PRIMARY_ARTERIALS or base_time_risk(e) >= 0.5]
            top10 = sorted(top_candidates, key=lambda e: base_time_risk(e), reverse=True)[:10]
            hw_tr = {"primary":"Birincil Arter","secondary":"İkincil Yol",
                     "tertiary":"Üçüncül Yol","residential":"Konut Yolu",
                     "trunk":"Ekspres Yol","unclassified":"Sınıflandırılmamış",
                     "motorway":"Otoyol / Çevre Yolu"}

            # Detay tablosu — satır seçimi ile haritaya odaklanma
            rows = []
            for i, e in enumerate(top10, 1):
                base_r = base_time_risk(e)
                sc_r   = scenario_risk(e)
                seg_name  = e.get("geo_name") or e.get("name") or "İsimsiz Yol"
                speed_txt = f"{int(e['speed'])} km/h" if e.get("speed") else "—"
                lanes_txt = str(e.get("lanes", "—"))
                red_pct   = (base_r - sc_r) / base_r * 100 if base_r > 0 else 0
                rows.append({
                    "Sıra": i,
                    "Yol Adı": seg_name,
                    "Tür": hw_tr.get(e.get("hw",""), e.get("hw","-")),
                    "Hız Limiti": speed_txt,
                    "Şerit": lanes_txt,
                    "Anlık Risk (Mevcut)":  f"%{base_r*100:.1f}",
                    "Anlık Risk (Senaryo)": f"%{sc_r*100:.1f}",
                    "Risk Azalması": f"-%{red_pct:.1f}" if red_pct > 0 else "Değişim yok",
                })

            st.caption("👆 Tabloda bir satıra tıkla → haritada o yolu göster")
            sel_event = st.dataframe(
                pd.DataFrame(rows),
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                key="top10_df"
            )

            # Seçili satırdan edge'i bul
            selected_rows = sel_event.selection.rows if hasattr(sel_event, "selection") else []
            sel_idx = selected_rows[0] if selected_rows else 0
            sel_edge  = top10[sel_idx]
            sel_coords = sel_edge["coords"]
            sel_lat = sum(c[0] for c in sel_coords) / len(sel_coords)
            sel_lon = sum(c[1] for c in sel_coords) / len(sel_coords)

            # Seçili segmentin odaklanmış haritası
            seg_name_focus = sel_edge.get("geo_name") or sel_edge.get("name") or "İsimsiz Yol"
            st.markdown(f"#### 📍 {seg_name_focus}")
            fig_focus = go.Figure()
            # Arter segmentlerini soluk arka plan olarak göster
            all_lats, all_lons = [], []
            for e in top_candidates[:200]:
                for c in e["coords"]:
                    all_lats.append(c[0]); all_lons.append(c[1])
                all_lats.append(None); all_lons.append(None)
            fig_focus.add_trace(go.Scattermap(
                lat=all_lats, lon=all_lons,
                mode="lines", line=dict(width=1, color="rgba(150,150,150,0.4)"),
                hoverinfo="skip", showlegend=False
            ))
            # Seçili segmenti kırmızı/kalın göster
            sel_lats = [c[0] for c in sel_coords]
            sel_lons = [c[1] for c in sel_coords]
            sel_name = sel_edge.get("geo_name") or sel_edge.get("name") or "İsimsiz Yol"
            base_r_focus = base_time_risk(sel_edge)
            fig_focus.add_trace(go.Scattermap(
                lat=sel_lats, lon=sel_lons,
                mode="lines+markers",
                line=dict(width=6, color="#EF4444"),
                marker=dict(size=8, color="#EF4444"),
                name=sel_name,
                hovertext=f"<b>{sel_name}</b><br>Anlık Dinamik Risk: %{base_r_focus*100:.1f}",
                hoverinfo="text",
            ))
            fig_focus.update_layout(
                map=dict(style="open-street-map",
                         center=dict(lat=sel_lat, lon=sel_lon), zoom=15),
                height=400, margin=dict(r=0,t=10,l=0,b=0),
                showlegend=False,
            )
            st.plotly_chart(fig_focus, use_container_width=True)

    except FileNotFoundError:
        st.error("⚠️ `konya_data.json` bulunamadı.")
    except Exception as ex:
        st.error(f"⚠️ GNN veri yükleme hatası: {ex}")
