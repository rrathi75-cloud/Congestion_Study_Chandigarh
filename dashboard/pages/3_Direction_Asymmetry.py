"""Page 3 — Direction Asymmetry.

Brief output #3: inbound vs outbound congestion at AM and PM peak windows.
Useful for one-way regulation or signal-timing recommendations.
"""

from __future__ import annotations

import streamlit as st

from data import cached_observations, cached_quality_report, data_signature
from insights import asymmetry_implication
from metrics import (
    GATING, active_peak_hours, am_peak_observations, direction_asymmetry,
    gating_state, pm_peak_observations, ranking_table, weekday_observations,
)
from ui import (
    apply_page_chrome, audit_context_caption, callout,
    chart_evidence_caption, page_header,
)
from viz import direction_asymmetry_chart

st.set_page_config(page_title="Direction Asymmetry", page_icon="↔️", layout="wide")


sig = data_signature()
df = cached_observations(sig)
ranking = ranking_table(df)
quality = cached_quality_report(sig)
stats = quality["stats"]

apply_page_chrome(df, ranking, stats)

page_header(
    title="Direction Asymmetry",
    subtitle=("Brief output #3 — for each corridor, inbound (A→B) vs outbound (B→A) "
              "median congestion ratio at AM and PM peaks."),
    eyebrow="Page 3",
)

if df.empty:
    st.warning("No observations yet.")
    st.stop()

wk = weekday_observations(df)
am_obs = am_peak_observations(wk)
pm_obs = pm_peak_observations(wk)

threshold = GATING["direction_asymmetry"]
am_min = int(am_obs.groupby(["corridor_id", "direction"]).size().min()) if not am_obs.empty else 0
pm_min = int(pm_obs.groupby(["corridor_id", "direction"]).size().min()) if not pm_obs.empty else 0

state_am = gating_state(am_min, "direction_asymmetry")
state_pm = gating_state(pm_min, "direction_asymmetry")

asym = direction_asymmetry(df)

chart_evidence_caption(
    slb="<i>Traffic Congestion at Peak</i> — directional decomposition",
    adm="Audit Design Matrix · Objective 3, Sub-Objective 3.2 — peak-direction targeting (signal-timing, lane-reversal evidence)",
)

callout(asymmetry_implication(asym), kind="insight",
        title="What direction asymmetry says about intervention")

# ---------------------------------------------------------------------------
# AM peak
# ---------------------------------------------------------------------------
_am_hrs, _pm_hrs, _ = active_peak_hours()
_am_label = f"{_am_hrs[0]:02d}:00–{_am_hrs[-1] + 1:02d}:00" if _am_hrs else "—"
_pm_label = f"{_pm_hrs[0]:02d}:00–{_pm_hrs[-1] + 1:02d}:00" if _pm_hrs else "—"
st.subheader(f"AM peak ({_am_label} IST)")
if state_am != "Locked":
    st.plotly_chart(direction_asymmetry_chart(asym, "AM Peak"), use_container_width=True)
else:
    st.info("AM-peak asymmetry unlocks once each direction has more morning observations.")

st.divider()

# ---------------------------------------------------------------------------
# PM peak
# ---------------------------------------------------------------------------
st.subheader(f"PM peak ({_pm_label} IST)")
if state_pm != "Locked":
    st.plotly_chart(direction_asymmetry_chart(asym, "PM Peak"), use_container_width=True)
else:
    st.info("PM-peak asymmetry unlocks once each direction has more evening observations.")

st.divider()

# ---------------------------------------------------------------------------
# Full table — collapsed
# ---------------------------------------------------------------------------
with st.expander("Full asymmetry table"):
    display = asym.copy()
    for col in ("median_cr_A_to_B", "median_cr_B_to_A"):
        if col in display.columns:
            display[col] = display[col].round(3)
    display = display[[
        "peak", "corridor_id", "corridor_name",
        "median_cr_A_to_B", "median_cr_B_to_A", "asymmetry_pct",
        "n_A_to_B", "n_B_to_A",
    ]]
    st.dataframe(display, use_container_width=True, hide_index=True)

audit_context_caption()
