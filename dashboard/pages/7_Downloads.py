"""Page 7 — Downloads.

Maps to brief output #6: the multi-sheet Excel workbook intended as a direct
annexure to the audit report, plus a zip of all dashboard charts as
1600×1000 PNGs for embedding in the formal Word/PDF report.

Both artefacts are expensive to build (Excel ≈ 8 s for 40k rows; PNG zip
≈ 10 s for eight kaleido renders), so the page now:

  * Renders the UI immediately, without building anything on page load.
  * Builds each artefact only after its "Prepare" button is clicked.
  * Caches the built bytes against the dataset signature, so re-clicks
    inside the cache window are instant.
  * Persists the "prepared" flag in session_state, so the download button
    survives Streamlit's button-state rerun reset.
"""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from data import cached_observations, cached_quality_report, data_signature
from exports import build_excel_annexure, build_png_zip
from metrics import (
    bti as compute_bti, direction_asymmetry, hourly_median_cr, ranking_table,
)
from ui import apply_page_chrome, audit_context_caption, page_header
from viz import (
    coverage_heatmap, cr_cdf_chart, direction_asymmetry_chart, hourly_heatmap,
    ranking_bar, reliability_chart,
)

st.set_page_config(page_title="Downloads", page_icon="⬇️", layout="wide")


# ---------------------------------------------------------------------------
# Cached artefact builders. Keyed by the dataset signature so a fresh
# travel_log batch invalidates the cache automatically; re-clicks inside
# the cache window return the bytes from RAM instantly.
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600, show_spinner=False)
def _build_excel(sig: str) -> bytes:
    df = cached_observations(sig)
    rep = cached_quality_report(sig)
    return build_excel_annexure(df, rep)


@st.cache_data(ttl=3600, show_spinner=False)
def _build_png_zip(sig: str) -> bytes:
    df = cached_observations(sig)
    rep = cached_quality_report(sig)
    ranking = ranking_table(df)
    order = ranking["corridor_id"].tolist()
    hm = hourly_median_cr(df)
    figs = {
        "01_ranking_phci.png": ranking_bar(ranking),
        "02a_heatmap_weekday.png": hourly_heatmap(
            hm, order, "Median Congestion Ratio — Weekday",
            "Source: Google Routes API v2, 30-min polling.",
            weekday_or_weekend="Weekday",
        ),
        "02b_heatmap_weekend.png": hourly_heatmap(
            hm, order, "Median Congestion Ratio — Weekend",
            "Source: Google Routes API v2, 30-min polling.",
            weekday_or_weekend="Weekend",
        ),
        "03a_direction_asymmetry_am.png": direction_asymmetry_chart(
            direction_asymmetry(df), "AM Peak",
        ),
        "03b_direction_asymmetry_pm.png": direction_asymmetry_chart(
            direction_asymmetry(df), "PM Peak",
        ),
        "04a_reliability_bti.png": reliability_chart(compute_bti(df), "bti"),
        "06_coverage_matrix.png": coverage_heatmap(rep["coverage"]),
        "06b_cr_cdf.png": cr_cdf_chart(rep["cr_distribution"]),
    }
    return build_png_zip(figs)


sig = data_signature()
df = cached_observations(sig)
ranking = ranking_table(df)
rep = cached_quality_report(sig) if not df.empty else None
stats = rep["stats"] if rep is not None else None

if stats is not None:
    apply_page_chrome(df, ranking, stats)

page_header(
    title="Downloads",
    subtitle=("Audit-report-ready artefacts. The Excel workbook is the formal "
              "annexure; the PNG zip carries every chart at 1600×1000."),
    eyebrow="Page 7",
)

if df.empty:
    st.warning("No observations yet — exports unavailable.")
    st.stop()

stamp = datetime.now().strftime("%Y%m%d_%H%M")

# session_state flags survive button-click reruns, so the download_button
# below stays on screen between clicks.
_xlsx_flag = f"xlsx_ready::{sig}"
_zip_flag = f"png_ready::{sig}"

col1, col2 = st.columns(2)

with col1:
    st.subheader("Excel annexure (10 sheets)")
    st.markdown(
        "- **Cover** — audit metadata, MD5 hashes  \n"
        "- **Ranking** — PHCI / ADCI / BTI / CV per corridor  \n"
        "- **Hourly Medians** — raw of the heatmap  \n"
        "- **Direction Asymmetry** — AM/PM peak by direction  \n"
        "- **Reliability** — BTI + CV per corridor-direction  \n"
        "- **Coverage** — corridor × date, conditional-formatted  \n"
        "- **FAIL Log** — every failed API call with `error_msg`  \n"
        "- **Distance Drift** — re-route audit table  \n"
        "- **Methodology** — formulas, peak window, filters  \n"
        "- **Raw Observations** — full OK-filtered dataset"
    )

    if st.button("Prepare Excel workbook", use_container_width=True, key="xlsx_btn"):
        st.session_state[_xlsx_flag] = True

    if st.session_state.get(_xlsx_flag):
        with st.spinner("Building workbook…"):
            xlsx_bytes = _build_excel(sig)
        st.download_button(
            "⬇ Download Chandigarh_Congestion_Audit_Annexure.xlsx",
            data=xlsx_bytes,
            file_name=f"Chandigarh_Congestion_Audit_Annexure_{stamp}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key="xlsx_dl",
        )
        st.caption(
            f"Ready · {len(xlsx_bytes) / 1024:.0f} KB. Subsequent clicks reuse "
            "the cached build until the next data batch lands."
        )

with col2:
    st.subheader("Charts — PNG bundle")
    st.markdown(
        "Each dashboard chart at 1600 × 1000 px. Drop straight into the "
        "Word report annexure — at typical 6-inch column width that's "
        "≈ 267 DPI, well above print quality."
    )

    if st.button("Prepare PNG bundle", use_container_width=True, key="png_btn"):
        st.session_state[_zip_flag] = True

    if st.session_state.get(_zip_flag):
        with st.spinner("Rendering PNGs (kaleido)…"):
            png_zip = _build_png_zip(sig)
        st.download_button(
            "⬇ Download Chandigarh_Congestion_Charts.zip",
            data=png_zip,
            file_name=f"Chandigarh_Congestion_Charts_{stamp}.zip",
            mime="application/zip",
            use_container_width=True,
            key="png_dl",
        )
        st.caption(
            f"Ready · {len(png_zip) / 1024:.0f} KB. If any PNG file is "
            "replaced by a `.error.txt`, the kaleido package is not "
            "installed — run `pip install kaleido==0.2.1` and rebuild."
        )

st.divider()
audit_context_caption(
    "Both bundles are stamped with the build timestamp in the filename. The Excel "
    "cover sheet carries the observations MD5 — match against Page 6 to confirm "
    "provenance."
)
