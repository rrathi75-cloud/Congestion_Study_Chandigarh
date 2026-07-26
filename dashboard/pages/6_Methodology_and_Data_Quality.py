"""Page 6 — Methodology & Data Quality.

This is the audit-defensibility page for senior reviewer review. Seven sections:
  1. Formulas (rendered as LaTeX)
  2. Coverage matrix (corridor × date)
  3. FAIL log (with the 56 bootstrap fails surfaced transparently)
  4. Distance drift table (defends against "did Google measure the same path?")
  5. Reproducibility signature (MD5 hashes + pinned versions)
  6. Triangulation hooks (Citizen Survey, JPV, peer-city placeholders)


Non-negotiable for the 101-city Mobility Audit Best-Practice framing.
"""

from __future__ import annotations

import platform
import sys

import pandas as pd
import plotly
import streamlit as st

from data import (
    AUDIT_WINDOW_END, AUDIT_WINDOW_START, cached_observations,
    cached_quality_report, data_signature,
)
from metrics import (
    ACTIVE_HOURS, PEAK_PRESETS, SHORT_CORRIDOR_IDS, active_peak_hours,
    active_peak_preset, peak_observations, ranking_table, weekday_observations,
)
from ui import apply_page_chrome, audit_context_caption, page_header
from viz import coverage_heatmap, cr_cdf_chart

st.set_page_config(page_title="Methodology & Data Quality", page_icon="📐", layout="wide")


sig = data_signature()
df = cached_observations(sig)
rep = cached_quality_report(sig)
stats = rep["stats"]
ranking = ranking_table(df)

apply_page_chrome(df, ranking, stats)

page_header(
    title="Methodology & Data Quality",
    subtitle=("The audit-defensibility page. Formulas, coverage, failure log, "
              "distance drift, and a reproducibility signature."),
    eyebrow="Page 6",
)

# ---------------------------------------------------------------------------
# 1. Formulas
# ---------------------------------------------------------------------------
st.header("1. Formulas")

st.markdown("**Instant Congestion Ratio** — already stored in the CSV as `congestion_ratio`:")
st.latex(r"\text{CR}_{i,t} = \frac{\text{duration\_traffic\_s}_{i,t}}{\text{duration\_freeflow\_s}_{i,t}}")
st.caption(
    "Excluded if `api_status != \"OK\"`, `duration_freeflow_s ≤ 0`, or either field is null. "
    "`duration_traffic_s` is Google's live travel time given current traffic; "
    "`duration_freeflow_s` is Google's `staticDuration` — the model's estimate of "
    "the same route with no congestion."
)

st.markdown("**Hourly Median Congestion Ratio** (median, not mean — defends against single-batch spikes):")
st.latex(r"\text{CR}^{h}_{i,d} = \mathrm{median}_{t \in \text{hour } h}\bigl(\text{CR}_{i,t}\bigr)")

st.markdown("**Peak-Hour Congestion Index (PHCI)** — the headline ranking metric:")
st.latex(
    r"\text{PHCI}_i = \max\bigl(\mathrm{median}(\text{CR}_{i,d,h}) : "
    r"h \in \{8,9,10,17,18,19\},\ d \in \text{weekdays}\bigr)"
)
st.caption("Both directions of a corridor are aggregated by taking the max — represents the peak-hour high in the peak direction.")

st.markdown("**All-Day Congestion Index (ADCI)** — mean of hourly medians over active hours 06-22:")
st.latex(r"\text{ADCI}_i = \mathrm{mean}_{h \in [6, 22]}\bigl(\text{CR}^{h}_{i}\bigr)")

st.markdown("**Buffer Time Index (BTI)** — FHWA Mobility Monitoring Program standard:")
st.latex(
    r"\text{BTI}_i = \frac{p_{95}(\text{duration\_traffic}_{i,\text{peak}}) - "
    r"\mathrm{median}(\text{duration\_traffic}_{i,\text{peak}})}"
    r"{\mathrm{median}(\text{duration\_traffic}_{i,\text{peak}})}"
)
st.caption("Interpretation: BTI=0.30 means \"budget 30% extra time to arrive on time 95 days out of 100\".")

st.markdown("**Coefficient of Variation (CV)** — cross-check on BTI:")
st.latex(
    r"\text{CV}_i = \frac{\sigma(\text{duration\_traffic}_{i,\text{peak}})}"
    r"{\mu(\text{duration\_traffic}_{i,\text{peak}})}"
)

st.subheader("Peak window — policy-anchored, sidebar-switchable")
_am_active, _pm_active, _ = active_peak_hours()
_active_key = active_peak_preset()
_active_preset_meta = PEAK_PRESETS.get(_active_key, {})
st.markdown(
    f"- **AM peak (active)**: {sorted(_am_active)[0]:02d}:00–"
    f"{sorted(_am_active)[-1] + 1:02d}:00 IST.  \n"
    f"- **PM peak (active)**: {sorted(_pm_active)[0]:02d}:00–"
    f"{sorted(_pm_active)[-1] + 1:02d}:00 IST.  \n"
    f"- **Active hours** (for ADCI): {ACTIVE_HOURS[0]:02d}:00–"
    f"{ACTIVE_HOURS[-1] + 1:02d}:00 IST.  \n\n"
    f"Active preset: **{_active_preset_meta.get('label', _active_key)}** — "
    f"{_active_preset_meta.get('long', '')}  \n\n"
    "The window is **policy-anchored, not detected from the data** — with 2–14 days of "
    "observations, data-driven peak detection is unstable and invites the \"you fit the "
    "window to make the numbers look bad\" objection. Switch presets in the sidebar to "
    "re-run every page on the alternate band."
)

st.markdown("**Same numbers under both peak-window definitions** — sensitivity check:")
_wk_df = weekday_observations(df)

def _stats_under(am_h, pm_h):
    peak = tuple(am_h) + tuple(pm_h)
    sub = _wk_df[_wk_df["hour"].astype(int).isin(peak)]
    if sub.empty:
        return {"median_cr": None, "p95_cr": None, "n": 0}
    return {
        "median_cr": float(sub["congestion_ratio"].median()),
        "p95_cr": float(sub["congestion_ratio"].quantile(0.95)),
        "n": int(len(sub)),
    }

_compare_rows = []
for k, meta in PEAK_PRESETS.items():
    s = _stats_under(meta["am"], meta["pm"])
    _compare_rows.append({
        "Preset": meta["label"]
                  + (" (active)" if k == _active_key else ""),
        "AM band": f"{meta['am'][0]:02d}:00–{meta['am'][-1] + 1:02d}:00",
        "PM band": f"{meta['pm'][0]:02d}:00–{meta['pm'][-1] + 1:02d}:00",
        "Network median CR": (f"{s['median_cr']:.3f}" if s['median_cr'] is not None else "—"),
        "Network p95 CR":    (f"{s['p95_cr']:.3f}"    if s['p95_cr']    is not None else "—"),
        "Peak observations (n)": s["n"],
    })
st.dataframe(pd.DataFrame(_compare_rows), use_container_width=True, hide_index=True)
st.caption(
    "Reading: both presets see the same underlying observations; the table shows the "
    "network-wide weekday median and 95th-percentile Congestion Ratio that result from "
    "applying each band. A small gap between the two rows is the audit-defensibility "
    "result — the dashboard's ranking is not artefact of the peak-window choice."
)

st.subheader("Sample-size sufficiency thresholds")
st.markdown(
    "Each metric and chart self-gates by observation count: **Locked** (insufficient), "
    "**Preliminary** (usable with `n` quoted), **Stable** (audit-defensible). "
    "Thresholds live in `dashboard/metrics.py:GATING` and are visible on every page."
)

st.subheader("Empirical CR distribution — sanity check")
st.markdown(
    "Values below 1.0 are real and not a bug: in deep off-peak, Google's live "
    "`duration` can be faster than its `staticDuration` model estimate. We do not "
    f"clamp. Empirical range in the current dataset: **{rep['cr_distribution'].min():.3f}** "
    f"to **{rep['cr_distribution'].max():.3f}**, median **{rep['cr_distribution'].median():.3f}**."
)
st.plotly_chart(cr_cdf_chart(rep["cr_distribution"]), use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# 2. Coverage matrix
# ---------------------------------------------------------------------------
st.header("2. Observation Coverage")
st.markdown(
    "Every cell counts the OK observations collected for a given corridor on a "
    "given date, summed across both directions. Full coverage is **48 batches/day "
    "× 2 directions = 96** (cron every 30 minutes; one row per corridor-direction "
    "per batch). Red ≲ 50, amber 50–80, green ≳ 90."
)
st.plotly_chart(coverage_heatmap(rep["coverage"]), use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# 3. FAIL log
# ---------------------------------------------------------------------------
st.header("3. Failed API calls — transparency log")
st.markdown(
    f"**{stats.fail_count}** failed Routes API calls in the audit window "
    f"({stats.fail_pct:.2f}% of all calls). All failures are surfaced here so reviewers "
    "can confirm no observation is silently hidden. The OK-only filter on every "
    "other page excludes these rows."
)
st.caption(
    "Note: 56 calls failed during a one-off manual test at 2026-05-12 20:47 IST "
    "— before the audit window opened — with the error `Timestamp must be set to "
    "a future time`. The bug (`datetime.now()` evaluated client-side instead of "
    "with a small future offset) was fixed in `collect_travel_times.py` before "
    "cron started. Those rows are excluded from every dashboard surface because "
    "they pre-date the audit window. They reflect the original 28-corridor set "
    "(28 × 2 directions = 56) and do not involve the corridors added on "
    "2026-05-20 (see Section 7 below)."
)

if stats.fail_count > 0:
    st.subheader("Failure summary")
    st.dataframe(rep["fail_summary"], use_container_width=True, hide_index=True)

    with st.expander("Raw FAIL rows"):
        fail_display = rep["fail_log"][[
            "timestamp_ist", "corridor_id", "corridor_name", "direction",
            "api_status", "error_msg",
        ]]
        st.dataframe(fail_display, use_container_width=True, hide_index=True)
else:
    st.success("No failed API calls inside the audit window.")

st.divider()

# ---------------------------------------------------------------------------
# 4. Distance drift
# ---------------------------------------------------------------------------
st.header("4. Distance drift — did Google measure the same path each time?")
st.markdown(
    "**Yes, ratios are route-invariant.** For each call, Google returns both "
    "`duration_traffic_s` and `duration_freeflow_s` for the *same chosen route*. "
    "The Congestion Ratio is therefore dimensionless and does not depend on which "
    "alternative path was selected on a given run. We report distance drift here "
    "so reviewers see we have audited the question explicitly."
)
st.markdown(
    "The table below shows, for each (corridor, direction): how many distinct "
    "`distance_m` values Google returned, the median distance, the share of "
    "calls returning a distance outside a ±5% band around that median "
    "(`pct_rows_outside_modal_5pct`), and the max-vs-min spread. "
    "**Re-route = True** flags pairs where the spread exceeds 25% of "
    "`est_distance_km` in `corridors.csv`. **High path variability = True** "
    "flags pairs where more than 30% of calls fall outside the ±5% modal band."
)

drift = rep["distance_drift"].copy()
drift["delta_pct_of_est"] = drift["delta_pct_of_est"].round(2)
display_cols = [
    "corridor_id", "direction",
    "median_distance_m", "distinct_distances",
    "pct_rows_outside_modal_5pct",
    "min_distance_m", "max_distance_m", "delta_m", "delta_pct_of_est",
    "reroute_flag", "high_path_variability_flag",
]
st.dataframe(drift[display_cols], use_container_width=True, hide_index=True)

if drift["reroute_flag"].any():
    n_flagged = int(drift["reroute_flag"].sum())
    st.caption(
        f"{n_flagged} (corridor, direction) pair(s) flagged for re-routing. "
        "The ratio-based metrics on every other page remain valid regardless."
    )

st.subheader("Highest path-variability corridors")
st.markdown(
    "On the (corridor, direction) pairs listed below, more than **30%** of "
    "calls returned a `distance_m` outside a ±5% band around that route's "
    "median distance for the audit window. The routing engine selected "
    "different physical paths on those calls between the named endpoints."
)
st.markdown(
    "The Congestion Ratio remains internally consistent for each row — "
    "`duration_traffic_s` and `duration_freeflow_s` come from the same API "
    "response and describe the same chosen route. Aggregated metrics for "
    "these corridors should be read as the typical travel experience between "
    "the named endpoints, not as a measurement of a single fixed road."
)

hv = drift[drift["high_path_variability_flag"]].copy()
if hv.empty:
    st.info("No (corridor, direction) pairs exceed the 30% threshold in the current data.")
else:
    name_lookup = (
        df[["corridor_id", "direction", "corridor_name"]]
        .drop_duplicates(["corridor_id", "direction"])
    )
    hv = hv.merge(name_lookup, on=["corridor_id", "direction"], how="left")
    hv_display = hv[[
        "corridor_id", "direction", "corridor_name",
        "median_distance_m", "pct_rows_outside_modal_5pct",
        "distinct_distances",
    ]].rename(columns={
        "pct_rows_outside_modal_5pct": "pct_outside_±5%_band",
    }).sort_values("pct_outside_±5%_band", ascending=False)
    st.dataframe(hv_display, use_container_width=True, hide_index=True)
    st.caption(
        f"{len(hv)} of {len(drift)} (corridor, direction) pairs meet the "
        "threshold. Threshold and ±5% band are documented in "
        "`dashboard/data.py:data_quality_report()`."
    )

st.divider()

# ---------------------------------------------------------------------------
# 5. Reproducibility signature
# ---------------------------------------------------------------------------
st.header("5. Reproducibility signature")
st.markdown(
    "Two reviewers on two laptops, running the same code against the same input "
    "files, should see **identical** MD5 hashes below. If hashes match and the "
    "versions below match, every number on every page matches by construction."
)

col1, col2 = st.columns(2)
with col1:
    st.markdown("**Input hashes (MD5 of sorted CSV serialisation):**")
    st.code(
        f"observations:  {stats.observations_md5}\n"
        f"corridors.csv: {stats.corridors_md5}",
        language="text",
    )
    st.markdown("**Data window:**")
    st.code(
        f"first observation: {stats.first_timestamp} IST\n"
        f"last observation:  {stats.last_timestamp} IST\n"
        f"days covered:      {stats.days_covered}\n"
        f"corridors:         {stats.corridors_covered}/25",
        language="text",
    )
with col2:
    st.markdown("**Software versions:**")
    st.code(
        f"python:    {sys.version.split()[0]}\n"
        f"platform:  {platform.platform()}\n"
        f"pandas:    {pd.__version__}\n"
        f"plotly:    {plotly.__version__}\n"
        f"streamlit: {st.__version__}",
        language="text",
    )
    st.markdown("**Audit collection window:**")
    try:
        start_text = f"{AUDIT_WINDOW_START.date()} 00:00 IST"
        end_text = f"{AUDIT_WINDOW_END.date()} 23:59 IST"
    except Exception:
        start_text = "n/a"
        end_text = "n/a"

    st.code(
        f"start: {start_text}\n"
        f"end:   {end_text}\n"
        f"polling: every 30 minutes\n"
        f"OD pairs: 50 (25 corridors × 2 directions) from 2026-07-27 15:30 IST;\n",
        language="text",
    )

st.markdown(
    "Short corridors (sensitive to single signal cycles): "
    + ", ".join(sorted(SHORT_CORRIDOR_IDS))
    + ". These are footnoted on the Ranking page and require higher `n` before "
    "their peak-hour cells render in the heatmap."
)

st.divider()

# ---------------------------------------------------------------------------
# 6. Triangulation hooks
# ---------------------------------------------------------------------------
st.header("6. Triangulation with the rest of the audit")
st.markdown(
    "The Chandigarh Mobility Audit has three pillars: the Citizen Survey, the Joint "
    "Physical Verification (JPV), and this Congestion Index Tool. The three are "
    "designed to triangulate. The tables below are placeholders for the cross-"
    "references that will be populated as the other two pillars complete — their "
    "presence here, even unfilled, demonstrates that this tool is designed for "
    "triangulation, not as a standalone artefact."
)

with st.expander("Citizen Survey alignment (placeholder)"):
    st.markdown(
        "For each corridor in the survey, compare the share of respondents who "
        "reported 'high congestion' against the corridor's PHCI. Alignment ⇒ "
        "the audit finding is doubly defensible. Divergence ⇒ probe further."
    )
    st.dataframe(
        pd.DataFrame({
            "corridor_id": [], "citizen_high_congestion_pct": [], "phci": [],
            "alignment": [],
        }),
        use_container_width=True,
    )

with st.expander("Joint Physical Verification photographs (placeholder)"):
    st.markdown(
        "Link JPV photograph IDs to corridor IDs so the audit report can pair "
        "ground-truth images with the quantitative finding for the same corridor."
    )
    st.dataframe(
        pd.DataFrame({"corridor_id": [], "jpv_photo_id": [], "observation_time": []}),
        use_container_width=True,
    )

with st.expander("Peer-city comparison (placeholder — 101-city programme)"):
    st.markdown(
        "When peer audit offices run this tool for their cities, the same metric "
        "definitions enable apples-to-apples comparison. Each peer city contributes "
        "its PHCI distribution and the top-ranked-corridor BTI."
    )
    st.dataframe(
        pd.DataFrame({
            "city": [], "median_PHCI": [], "p95_PHCI": [], "top_corridor_BTI": [],
        }),
        use_container_width=True,
    )

st.divider()


