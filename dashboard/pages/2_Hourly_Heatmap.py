"""Page 2 — Hourly Heatmap.

Brief output #2: corridor × hour heatmap that reveals peak windows and
their spreading. Weekday panel renders today; weekend panel is gated until
weekend data arrives (first Sat: 2026-05-16).
"""

from __future__ import annotations

import streamlit as st

from data import cached_observations, cached_quality_report, data_signature
from insights import heatmap_patterns
from metrics import (
    GATING, gating_state, hourly_median_cr, ranking_table, weekend_observations,
)
from ui import (
    apply_page_chrome, audit_context_caption, callout, chart_evidence_caption,
    heatmap_color_legend, page_header,
)
from viz import hourly_heatmap

st.set_page_config(page_title="Hourly Heatmap", page_icon="🌡️", layout="wide")


sig = data_signature()
df = cached_observations(sig)
ranking = ranking_table(df)
quality = cached_quality_report(sig)
stats = quality["stats"]

apply_page_chrome(df, ranking, stats)

from metrics import active_peak_hours as _active_peak_hours_for_header
_am_h, _pm_h, _ = _active_peak_hours_for_header()
_am_h_label = f"{_am_h[0]:02d}–{_am_h[-1] + 1:02d}" if _am_h else "—"
_pm_h_label = f"{_pm_h[0]:02d}–{_pm_h[-1] + 1:02d}" if _pm_h else "—"
page_header(
    title="Hourly Congestion Heatmap",
    subtitle=("Brief output #2 — corridor × hour grid of median Congestion Ratio. "
              f"Shaded bands mark the active peak windows ({_am_h_label} AM, "
              f"{_pm_h_label} PM IST) — toggle the preset in the sidebar."),
    eyebrow="Page 2",
)

if df.empty:
    st.warning("No observations yet.")
    st.stop()

corridor_order = ranking["corridor_id"].tolist() if not ranking.empty else []
hm = hourly_median_cr(df)

# ---------------------------------------------------------------------------
# Inline color legend (was previously only on the User Guide)
# ---------------------------------------------------------------------------
heatmap_color_legend()

# ---------------------------------------------------------------------------
# Weekday panel
# ---------------------------------------------------------------------------
st.subheader("Weekday")

wk_panel = hm[hm["weekday_or_weekend"] == "Weekday"]
if wk_panel.empty:
    st.error("No weekday observations yet.")
else:
    n_days_weekday = df[df["weekday_or_weekend"] == "Weekday"]["date"].nunique()
    fig = hourly_heatmap(
        hm, corridor_order,
        title="Median Congestion Ratio — Weekday",
        subtitle=f"{n_days_weekday} weekday(s) of data. Source: Google Routes API v2, 30-min polling.",
        weekday_or_weekend="Weekday",
    )
    st.plotly_chart(fig, use_container_width=True)

chart_evidence_caption(
    slb="<i>Traffic Congestion at Peak</i> &amp; <i>Time Delay in Traffic</i> — hour-resolved",
    adm="Audit Design Matrix · Objective 3, Sub-Objective 3.1 — peak-band identification and spread",
)

callout(heatmap_patterns(df), kind="insight",
        title="Patterns to notice in this heatmap")

st.divider()

# ---------------------------------------------------------------------------
# Weekend / Holiday panel — gated until first weekend day arrives
# ---------------------------------------------------------------------------
st.subheader("Weekend / Holiday")

wkend_days = weekend_observations(df)["date"].nunique()
threshold_w = GATING["heatmap_weekend"]

if wkend_days < threshold_w.min_n:
    st.info(
        "Weekend heatmap unlocks once the first weekend day of observations is "
        "collected. First Saturday in the audit window: **2026-05-16**."
    )
elif wkend_days < threshold_w.stable_n:
    fig = hourly_heatmap(
        hm, corridor_order,
        title="Median Congestion Ratio — Weekend (preliminary)",
        subtitle=f"{wkend_days} weekend day(s) of data.",
        weekday_or_weekend="Weekend",
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    fig = hourly_heatmap(
        hm, corridor_order,
        title="Median Congestion Ratio — Weekend",
        subtitle=f"{wkend_days} weekend days of data.",
        weekday_or_weekend="Weekend",
    )
    st.plotly_chart(fig, use_container_width=True)

audit_context_caption(
    "Y-axis sorted by Peak-Hour Congestion Index (highest PHCI at top). "
    "Methodology and full per-cell counts on Page 6."
)
