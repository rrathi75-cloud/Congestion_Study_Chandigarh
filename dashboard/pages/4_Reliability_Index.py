"""Page 4 — Reliability Index.

Brief output #4: how unpredictable a commute is. Buffer Time Index (FHWA
standard) is the headline; Coefficient of Variation is the cross-check.
"""

from __future__ import annotations

import streamlit as st

from data import cached_observations, cached_quality_report, data_signature
from insights import reliability_translation
from metrics import (
    bti as compute_bti, cv as compute_cv, peak_observations, ranking_table,
    weekday_observations,
)
from ui import (
    apply_page_chrome, audit_context_caption, callout,
    chart_evidence_caption, page_header,
)
from viz import reliability_chart

st.set_page_config(page_title="Reliability Index", page_icon="⏱️", layout="wide")


sig = data_signature()
df = cached_observations(sig)
ranking = ranking_table(df)
quality = cached_quality_report(sig)
stats = quality["stats"]

apply_page_chrome(df, ranking, stats)

page_header(
    title="Reliability Index",
    subtitle=("Brief output #4 — how much extra time must a commuter budget "
              "to arrive on time? Headline metric is the FHWA Buffer Time Index."),
    eyebrow="Page 4",
)

if df.empty:
    st.warning("No observations yet.")
    st.stop()

wk_peak = peak_observations(weekday_observations(df))
bti_df = compute_bti(df)

callout(reliability_translation(bti_df), kind="insight",
        title="What reliability says about commute planning")

# ---------------------------------------------------------------------------
# BTI — headline
# ---------------------------------------------------------------------------
st.subheader("Buffer Time Index (BTI) — FHWA standard")
st.markdown(
    "**BTI = (p95 peak duration − median peak duration) ÷ median peak duration.** "
    "A BTI of 0.30 means a commuter must budget 30% extra time to arrive on time "
    "95 days out of 100. Source: US Federal Highway Administration's Mobility "
    "Monitoring Program."
)
st.plotly_chart(reliability_chart(bti_df, metric="bti"), use_container_width=True)

chart_evidence_caption(
    slb="<i>Travel-time reliability</i> (FHWA Mobility Monitoring Program); complements <i>Time Delay in Traffic</i>",
    adm="Audit Design Matrix · Objective 3, Sub-Objective 3.3 — predictability of commute as a service-level criterion",
)

st.divider()

# ---------------------------------------------------------------------------
# CV — collapsed cross-check
# ---------------------------------------------------------------------------
with st.expander("Cross-check — Coefficient of Variation (CV)"):
    st.markdown(
        "**CV = σ(peak duration) ÷ μ(peak duration).** A simpler, distribution-shape-"
        "agnostic measure of trip-time variability. Reported alongside BTI so two "
        "different statistical lenses converge on the same conclusion."
    )
    cv_df = compute_cv(df)
    st.plotly_chart(reliability_chart(cv_df, metric="cv"), use_container_width=True)

# ---------------------------------------------------------------------------
# Reliability table
# ---------------------------------------------------------------------------
with st.expander("Reliability table — per corridor, per direction"):
    cv_df = compute_cv(df)
    table = bti_df.merge(
        cv_df[["corridor_id", "direction", "cv", "mu_peak_s", "sigma_peak_s"]],
        on=["corridor_id", "direction"], how="left",
    )
    table["bti"] = table["bti"].round(3)
    table["cv"] = table["cv"].round(3)
    table["median_peak_min"] = (table["median_peak_s"] / 60.0).round(2)
    table["p95_peak_min"] = (table["p95_peak_s"] / 60.0).round(2)
    display = table[[
        "corridor_id", "corridor_name", "direction",
        "median_peak_min", "p95_peak_min", "bti", "cv", "n",
    ]]
    st.dataframe(display, use_container_width=True, hide_index=True)

audit_context_caption()
