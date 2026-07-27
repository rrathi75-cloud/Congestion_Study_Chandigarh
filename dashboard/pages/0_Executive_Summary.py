"""Executive Summary — the landing page.

A one-screen story for senior reviewers: top 3 findings in plain English,
headline KPIs, a mini-map of the most-congested corridors, and jump-links
into the detail pages.
"""

from __future__ import annotations

import pandas as pd
import pydeck as pdk
import streamlit as st

from data import (
    AUDIT_WINDOW_END, AUDIT_WINDOW_START, cached_observations,
    cached_quality_report, data_signature,
)
from metrics import (
    bti as compute_bti,
    direction_asymmetry,
    minutes_lost_table,
    ranking_table,
    slb_indicators,
)
from viz import (
    build_corridor_geometry,
    compact_ranking_bar,
    mini_map,
    network_hourly_line,
)
from insights import top_findings_html
from ui import (
    KPI, SLBIndicator, apply_page_chrome, audit_context_caption, callout,
    headline_findings, kpi_row, page_header, slb_indicator_strip,
)
try:
    from ui import top_rank_list
except ImportError:
    # Defensive: if the deployed ui.py is from a partial cache, fall back to a
    # plain dataframe so the page still renders the rank info.
    def top_rank_list(ranking, top_n=5, title="Top corridors", footer=""):
        st.markdown(f"**{title}**")
        if ranking is not None and len(ranking) > 0:
            st.dataframe(
                ranking.head(top_n)[["rank", "corridor_name", "phci"]],
                use_container_width=True, hide_index=True,
            )
        if footer:
            st.caption(footer)


st.set_page_config(
    page_title="Executive Summary — Chandigarh Mobility Audit",
    page_icon="🚦",
    layout="wide",
    initial_sidebar_state="expanded",
)


sig = data_signature()
df = cached_observations(sig)
ranking = ranking_table(df)
quality = cached_quality_report(sig)
stats = quality["stats"]

apply_page_chrome(df, ranking, stats)

# ---------------------------------------------------------------------------
# Hero
# ---------------------------------------------------------------------------
page_header(
    title="Chandigarh Mobility Congestion Index",
    subtitle=(
        f"Live evidence base for the audit of urban mobility in Chandigarh · "
        f"{AUDIT_WINDOW_START.date()} → {AUDIT_WINDOW_END.date()} · "
        "25 critical corridors · 30-minute polling via Google Routes API v2."
    ),
    eyebrow="Executive Summary",
)

if df.empty:
    st.warning("No observations yet. The dashboard will populate as the cron collector runs.")
    st.stop()

# ---------------------------------------------------------------------------
# Per-corridor distance lookup — used in the hero strip and the KPI sublabels
# below to give the reader physical context for delay/ratio numbers.
# ---------------------------------------------------------------------------
_dist_by_corridor = (
    df.dropna(subset=["est_distance_km"])
    .drop_duplicates("corridor_id")
    .set_index("corridor_id")["est_distance_km"]
    .to_dict()
)


def _dist_str(corridor_id, prefix: str = " · ") -> str:
    d = _dist_by_corridor.get(str(corridor_id))
    return f"{prefix}{d:.1f} km corridor" if d else ""


ml = minutes_lost_table(df)
bti_df = compute_bti(df)

worst = ranking.iloc[0] if not ranking.empty else None
longest_delay = ml.iloc[0] if not ml.empty else None
most_unreliable = (
    bti_df.dropna(subset=["bti"]).iloc[0]
    if (not bti_df.empty and bti_df["bti"].notna().any()) else None
)

# ---------------------------------------------------------------------------
# Headline findings — two hero cards at the top of the page.
# Card 1: the highest sustained peak — what every weekday peak hour looks like.
# Card 2: the highest single observation — the most-congested 30-min window in
#         the audit dataset.
# Acronyms PHCI / CR are expanded in full here so every subsequent shorthand
# on the page has already been introduced. Each card carries an intensity
# bar (1.0× free-flow → 3.0×+) so the magnitude is readable at a glance.
# ---------------------------------------------------------------------------
_hero_cards: list[dict] = []

if worst is not None:
    pct_over = (float(worst["phci"]) - 1.0) * 100
    dir_pretty = {"A_to_B": "A→B", "B_to_A": "B→A"}.get(
        str(worst["phci_direction"]), str(worst["phci_direction"]))
    _hero_cards.append({
        "eyebrow": "Highest sustained peak congestion · weekday pattern",
        "value": f"+{pct_over:.0f}% over free-flow",
        "ratio": float(worst["phci"]),
        "where": str(worst["corridor_name"]),
        "when": (f"Peaks at {int(worst['phci_hour']):02d}:00 IST · "
                 f"direction {dir_pretty}"),
        "detail": (f"<b>Peak-Hour Congestion Index (PHCI) "
                   f"{float(worst['phci']):.2f}</b> · weekday peak-hour median "
                   f"across {int(worst['n_peak']):,} observations"
                   f"{_dist_str(worst['corridor_id'])}"),
        "accent": "indigo",
    })

if not df.empty:
    _idx_max = df["congestion_ratio"].idxmax()
    _w = df.loc[_idx_max]
    _traffic_min = float(_w["duration_traffic_s"]) / 60.0
    _free_min = float(_w["duration_freeflow_s"]) / 60.0
    _hero_cards.append({
        "eyebrow": "Highest single observation in the audit window",
        "value": f"{float(_w['congestion_ratio']):.1f}× free-flow time",
        "ratio": float(_w["congestion_ratio"]),
        "where": str(_w["corridor_name"]),
        "when": (f"{_w['day_of_week']} {_w['date']} at "
                 f"{str(_w['time'])[:5]} IST"),
        "detail": (f"<b>Congestion Ratio (CR) {float(_w['congestion_ratio']):.2f}</b> · "
                   f"traffic-aware travel time {_traffic_min:.1f} min vs. "
                   f"free-flow {_free_min:.1f} min"
                   f"{_dist_str(_w['corridor_id'])}"),
        "accent": "amber",
    })

if _hero_cards:
    headline_findings(_hero_cards)

# ---------------------------------------------------------------------------
# KPI strip — six cards
# ---------------------------------------------------------------------------
kpi_row([
    KPI(
        label="Highest peak-hour congestion",
        value=(f"PHCI {float(worst['phci']):.2f} @ "
               f"{int(worst['phci_hour']):02d}:00" if worst is not None else "—"),
        sublabel=(
            f"{worst['corridor_name']}{_dist_str(worst['corridor_id'])}"
            if worst is not None else "Locked"
        ),
        accent="rose",
    ),
    KPI(
        label="Largest peak delay",
        value=(f"{float(longest_delay['minutes_lost']):.1f} min/trip"
               if longest_delay is not None else "—"),
        sublabel=(
            f"{longest_delay['corridor_name']}"
            f"{_dist_str(longest_delay['corridor_id'])}"
            if longest_delay is not None else "Awaiting data"
        ),
        accent="amber",
    ),
    KPI(
        label="Lowest reliability (Buffer Time Index)",
        value=(f"BTI {float(most_unreliable['bti']):.2f}"
               if most_unreliable is not None else "—"),
        sublabel=(str(most_unreliable["corridor_name"])
                  if most_unreliable is not None else "Locked"),
        accent="violet",
    ),
    KPI(
        label="Days observed",
        value=f"{stats.days_covered} / 14",
        sublabel="of the 14-day audit window",
        accent="indigo",
    ),
    KPI(
        label="Corridor coverage",
        value=f"{stats.corridors_covered} / 25",
        sublabel="critical corridors active",
        accent="emerald",
    ),
    KPI(
        label="Observations",
        value=f"{stats.total_observations:,}",
        sublabel=f"FAIL rate {stats.fail_pct:.2f}%",
        accent="cyan",
    ),
])

# ---------------------------------------------------------------------------
# SLB-indicator strip — MoUD / NUTP framework alignment
# ---------------------------------------------------------------------------
_slb = slb_indicators(df)
_tcp = _slb.get("traffic_congestion_at_peak", {})
_tdt = _slb.get("time_delay_in_traffic", {})
_pcr = _slb.get("pct_congested_roads", {})


def _slb_detail(d: dict) -> str:
    n = d.get("n_per_corr_min", 0)
    if not n:
        return ""
    return f"min n={n}/corridor in MoUD peak"


def _slb_value(d: dict, formatter) -> str:
    if d.get("state") == "Locked":
        return "—"
    try:
        return formatter(d)
    except (KeyError, TypeError, ValueError):
        return "—"


def _tcp_reality(d: dict) -> str:
    cr = d.get("peak_hour_max_cr")
    pct = d.get("peak_hour_max_pct_over_freeflow")
    name = d.get("peak_hour_max_corridor", "")
    hour = d.get("peak_hour_max_hour", -1)
    if cr is None or cr != cr:
        return ""
    hour_txt = f" @ {hour:02d}:00" if isinstance(hour, int) and hour >= 0 else ""
    return (
        f"Worst corridor at its peak hour: +{pct:.0f}% over free-flow "
        f"(CR {cr:.2f})"
        + (f" — {name}{hour_txt}" if name else "")
    )


def _tdt_reality(d: dict) -> str:
    worst = d.get("peak_hour_max_min_per_km")
    name = d.get("peak_hour_max_corridor", "")
    if worst is None or worst != worst:
        return ""
    return (
        f"Worst corridor at its peak hour: {worst:.2f} min/km lost"
        + (f" — {name}" if name else "")
    )


def _pcr_reality(d: dict) -> str:
    n_hard = d.get("n_peak_hour_above_threshold")
    pct_hard = d.get("pct_peak_hour_above_threshold")
    n_soft = d.get("n_peak_hour_above_soft")
    pct_soft = d.get("pct_peak_hour_above_soft")
    n_corr = d.get("n_corridors")
    if None in (n_hard, pct_hard, n_soft, pct_soft, n_corr):
        return ""
    return (
        f"At each corridor's actual peak hour: "
        f"{pct_hard:.0f}% ({n_hard}/{n_corr}) cross ≥ 1.5×, "
        f"{pct_soft:.0f}% ({n_soft}/{n_corr}) cross ≥ 1.25× (≥ 25% slower)"
    )


slb_items = [
    SLBIndicator(
        name="Traffic Congestion at Peak",
        value=_slb_value(
            _tcp,
            lambda d: f"+{d['pct_over_freeflow']:.0f}% over free-flow "
                      f"(CR {d['median_cr']:.2f})",
        ),
        definition=(
            "Network-wide weekday median Congestion Ratio in the MoUD "
            "peak window (06–10 / 16–20 IST). 1.00 = free-flow."
        ),
        state=_tcp.get("state", "Locked"),
        detail=_slb_detail(_tcp),
        reality_label="Corridor reality (peak hour, not 8-hour median)",
        reality_value=_tcp_reality(_tcp) if _tcp.get("state") != "Locked" else "",
    ),
    SLBIndicator(
        name="Time Delay in Traffic",
        value=_slb_value(
            _tdt,
            lambda d: f"{d['median_min_per_km']:.2f} min/km lost at peak",
        ),
        definition=(
            "Median extra travel time per kilometre in the MoUD peak "
            "window, taken across monitored corridors."
        ),
        state=_tdt.get("state", "Locked"),
        detail=_slb_detail(_tdt),
        reality_label="Corridor reality (peak hour, not 8-hour median)",
        reality_value=_tdt_reality(_tdt) if _tdt.get("state") != "Locked" else "",
    ),
    SLBIndicator(
        name="% Congested Roads",
        value=_slb_value(
            _pcr,
            lambda d: f"{d['pct']:.0f}% ({d['n_congested']}/{d['n_corridors']} corridors)",
        ),
        definition=(
            "Share of monitored corridors whose MoUD peak-window median "
            "Congestion Ratio is ≥ 1.5× (≥ 50% slower than free-flow)."
        ),
        state=_pcr.get("state", "Locked"),
        detail=_slb_detail(_pcr),
        reality_label="Corridor reality (peak hour, both thresholds)",
        reality_value=_pcr_reality(_pcr) if _pcr.get("state") != "Locked" else "",
    ),
]
slb_indicator_strip(slb_items)

# ---------------------------------------------------------------------------
# Top 3 findings
# ---------------------------------------------------------------------------
asym = direction_asymmetry(df)
findings_html = top_findings_html(df, ranking, asym, bti_df, ml)
callout(findings_html, kind="insight",
        title="Top 3 findings — what the data says today")

# ---------------------------------------------------------------------------
# Mini-map of top 5 worst corridors — paired with a colour-matched rank list
# ---------------------------------------------------------------------------
st.markdown("### Where peak-hour congestion is concentrated")
st.caption(
    "The five most-congested corridors are drawn in their PHCI colour — "
    "rank 1 is the thickest line, tapering down to rank 5. The remaining "
    "corridors are faded for geographic context. Hover any line for the "
    "corridor name and PHCI."
)
geom = build_corridor_geometry(df, ranking)
map_col, list_col = st.columns([2, 1], gap="medium")
with map_col:
    st.pydeck_chart(mini_map(geom, top_n=5), use_container_width=True, height=420)
with list_col:
    top_rank_list(
        ranking, top_n=5, title="Top 5 most-congested corridors",
        footer="Badge colour matches the line colour on the map. "
               "Hover any line for full statistics.",
    )

# ---------------------------------------------------------------------------
# Two compact charts
# ---------------------------------------------------------------------------
col_a, col_b = st.columns([1, 1], gap="large")
with col_a:
    st.markdown("#### Top corridors by PHCI")
    st.plotly_chart(compact_ranking_bar(ranking, top_n=6), use_container_width=True)
with col_b:
    st.markdown("#### When does congestion peak?")
    st.plotly_chart(network_hourly_line(df), use_container_width=True)

# ---------------------------------------------------------------------------
# Jump-to navigation
# ---------------------------------------------------------------------------
st.markdown("### Drill into the detail")
nav_cols = st.columns(3)
links = [
    ("pages/1_Congestion_Index_Ranking.py", "Full ranking", "📊"),
    ("pages/2_Hourly_Heatmap.py", "Hourly heatmap", "🌡️"),
    ("pages/3_Direction_Asymmetry.py", "Direction asymmetry", "↔️"),
    ("pages/4_Reliability_Index.py", "Reliability index", "⏱️"),
    ("pages/5_Corridor_Map.py", "Full interactive map", "🗺️"),
    ("pages/6_Methodology_and_Data_Quality.py", "Methodology & data quality", "📐"),
]
for i, (path, label, icon) in enumerate(links):
    with nav_cols[i % 3]:
        try:
            st.page_link(path, label=label, icon=icon)
        except KeyError:
            st.markdown(f"{icon} **{label}** &nbsp;`{path.split('/')[-1]}`",
                        unsafe_allow_html=True)

st.markdown("&nbsp;", unsafe_allow_html=True)
audit_context_caption(
    f"Last updated: {stats.last_timestamp} IST · "
    f"Reproducibility MD5: {stats.observations_md5[:12]}…"
)
