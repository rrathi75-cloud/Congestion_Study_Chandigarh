"""Page 1 — Congestion Index Ranking.

Brief output #1: a highest- to lowest-PHCI ranking of 25 corridors with
peak-hour ratios, plus the secondary "absolute minutes lost" ranking that
contextualises short-corridor ratios.
"""

from __future__ import annotations

import streamlit as st

from data import cached_observations, cached_quality_report, data_signature
from insights import ranking_callout
from metrics import (
    bti as compute_bti,
    minutes_lost_table,
    ranking_table,
    SHORT_CORRIDOR_IDS,
)
from ui import (
    KPI, apply_page_chrome, audit_context_caption, callout,
    chart_evidence_caption, kpi_row, page_header,
)
from viz import ranking_bar

st.set_page_config(page_title="Congestion Index Ranking", page_icon="📊", layout="wide")


sig = data_signature()
df = cached_observations(sig)
ranking = ranking_table(df)
quality = cached_quality_report(sig)
stats = quality["stats"]

apply_page_chrome(df, ranking, stats)

page_header(
    title="Congestion Index Ranking",
    subtitle="Brief output #1 — 25 corridors of Chandigarh, most-congested first.",
    eyebrow="Page 1",
)

if ranking.empty:
    st.warning("No observations yet. The dashboard will populate as the cron collector runs.")
    st.stop()

# ---------------------------------------------------------------------------
# KPI strip
# ---------------------------------------------------------------------------
ml = minutes_lost_table(df)
bti_df = compute_bti(df)

worst_phci = ranking.iloc[0]
worst_adci = ranking.sort_values("adci", ascending=False).iloc[0]
worst_bti = bti_df.dropna(subset=["bti"]).iloc[0] if not bti_df.empty else None
longest_delay = ml.iloc[0] if not ml.empty else None

kpi_row([
    KPI(
        label="Highest PHCI",
        value=f"{float(worst_phci['phci']):.2f}",
        sublabel=str(worst_phci["corridor_name"]),
        accent="rose",
    ),
    KPI(
        label="Highest all-day index (ADCI)",
        value=f"{float(worst_adci['adci']):.2f}",
        sublabel=str(worst_adci["corridor_name"]),
        accent="amber",
    ),
    KPI(
        label="Lowest reliability",
        value=(f"BTI {float(worst_bti['bti']):.2f}" if worst_bti is not None else "—"),
        sublabel=(str(worst_bti["corridor_name"]) if worst_bti is not None else "Locked"),
        accent="violet",
    ),
    KPI(
        label="Largest peak delay",
        value=(f"{float(longest_delay['minutes_lost']):.1f} min" if longest_delay is not None else "—"),
        sublabel=(str(longest_delay["corridor_name"]) if longest_delay is not None else "—"),
        accent="cyan",
    ),
])

# ---------------------------------------------------------------------------
# Primary chart
# ---------------------------------------------------------------------------
st.subheader("Peak-Hour Congestion Index (PHCI)")
st.markdown(
    "Per corridor: the weekday median Congestion Ratio at the peak hour, taken on "
    "the peak direction. A PHCI of 1.50 means the peak-hour median trip took "
    "50% longer than free-flow."
)
st.plotly_chart(ranking_bar(ranking), use_container_width=True)

chart_evidence_caption(
    slb="<i>Traffic Congestion at Peak</i> — corridor-level ranking",
    adm="Audit Design Matrix · Objective 3 (Traffic &amp; Congestion Management), Sub-Objective 3.1",
)

callout(ranking_callout(ranking), kind="insight",
        title="What this ranking says")

# ---------------------------------------------------------------------------
# Cross-check — minutes lost (above the giant table for short-corridor context)
# ---------------------------------------------------------------------------
st.subheader("Cross-check — real minutes lost per peak trip")
st.caption(
    "Same data, different lens. Read this for short corridors (< 1.5 km) where a "
    "high CR is only seconds in absolute terms, and for long corridors where a "
    "modest CR can still mean many minutes lost."
)
ml_disp = ml.copy()
ml_disp.insert(0, "rank", ml_disp.index + 1)
st.dataframe(ml_disp, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Full ranking table — collapsed by default to keep visual focus on the chart
# ---------------------------------------------------------------------------
with st.expander("Full ranking table — all metrics, sortable"):
    display = ranking[[
        "rank", "corridor_id", "corridor_name", "phci", "phci_hour", "phci_direction",
        "adci", "bti", "cv", "n_peak", "is_short_corridor",
    ]].copy()
    display["phci"] = display["phci"].round(3)
    display["adci"] = display["adci"].round(3)
    display["bti"] = display["bti"].round(3)
    display["cv"] = display["cv"].round(3)
    display = display.rename(columns={
        "phci": "PHCI", "phci_hour": "Peak hour", "phci_direction": "Peak dir",
        "adci": "ADCI (06-22)", "bti": "BTI (peak)", "cv": "CV (peak)",
        "n_peak": "n peak obs", "is_short_corridor": "Short corridor *",
    })
    st.dataframe(display, use_container_width=True, hide_index=True)
    if any(ranking["is_short_corridor"]):
        short = ", ".join(sorted(SHORT_CORRIDOR_IDS))
        st.caption(
            f"\\* Short corridors ({short}) are < 1.5 km. Their CR is sensitive "
            "to one signal cycle; cross-check with the minutes-lost table above."
        )

audit_context_caption()
