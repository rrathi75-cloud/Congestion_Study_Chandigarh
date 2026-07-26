"""User Guide — long-form reference for plain-English explanations.

Sidebar carries the brief glossary on every page; this page is the deeper
manual for first-time readers and reviewers who want every short-form
explained and every page described.
"""

from __future__ import annotations

import streamlit as st

from data import cached_observations, cached_quality_report, data_signature
from metrics import ranking_table
from ui import apply_page_chrome, audit_context_caption, callout, page_header

st.set_page_config(page_title="User Guide", page_icon="📖", layout="wide")


sig = data_signature()
df = cached_observations(sig)
ranking = ranking_table(df)
quality = cached_quality_report(sig)
stats = quality["stats"]

apply_page_chrome(df, ranking, stats)

page_header(
    title="User Guide",
    subtitle=("Plain-English reference: what every metric means and how to read each "
              "page. Read this first if you are new to the dashboard."),
    eyebrow="Reference",
)

# ---------------------------------------------------------------------------
# What this dashboard is
# ---------------------------------------------------------------------------
st.header("What this dashboard is")
st.markdown(
    f"""
This is a measurement tool for the **audit of urban mobility in Chandigarh**. It
does one job: for 25 important roads of Chandigarh, it asks Google Maps every 30
minutes how long the drive currently takes, compares that to how long the
drive *would* take with zero traffic, and stores the answer.

So far we have **{stats.total_observations:,} measurements across
{stats.days_covered} day(s)** in the 14-day audit window. From these, the
dashboard produces ranked lists, heatmaps, and a map that show **which roads of
Chandigarh are congested, when, and by how much** — replacing "Bailey Road feels
congested" with "Bailey Road takes 11 minutes at 6 AM and 36 minutes at
6:30 PM, every weekday."
    """
)

# ---------------------------------------------------------------------------
# The one number everything is built on
# ---------------------------------------------------------------------------
st.header("The one number everything is built on")
st.subheader("Congestion Ratio (CR)")
st.markdown(
    """
**CR = (drive time right now) ÷ (drive time with no traffic).**

- **CR = 1.0** → free-flow.
- **CR = 1.5** → 50% longer than free-flow. A 20-min drive now takes 30 min.
- **CR = 2.0** → twice as long as free-flow.
- **CR = 0.9** → faster than Google's free-flow estimate (real, off-peak; not hidden).

We collect one CR per road, per direction, every 30 minutes (48 CRs per day).
Every other number on this dashboard is a summary of many CRs.
    """
)
callout(
    "<b>Why a ratio and not minutes?</b> Different roads are different lengths. "
    "A 60-second delay on a 1 km road is a disaster; the same 60 seconds on a "
    "10 km road is normal. The Congestion Ratio compares each road to its own "
    "free-flow baseline, so all 25 roads can be compared on the same scale.",
    kind="neutral",
    title="Method note",
)

# ---------------------------------------------------------------------------
# How to read each page
# ---------------------------------------------------------------------------
st.header("How to read each page")

with st.expander("Executive Summary (landing page)", expanded=False):
    st.markdown(
        "One-screen story for senior auditors and govt officials: top 3 findings "
        "in plain English, headline KPI tiles, a mini-map of the most-congested "
        "corridors, and links into the detail pages. Start here every visit."
    )

with st.expander("Page 1 — Congestion Index Ranking"):
    st.markdown(
        """
**Headline metric — PHCI (Peak-Hour Congestion Index):** per corridor, the
weekday median CR at the peak hour and the peak direction.

| PHCI | Plain-English |
|---|---|
| < 1.10 | Essentially free-flow even at peak |
| 1.10 – 1.25 | Mild peak-hour congestion |
| 1.25 – 1.50 | Noticeable congestion |
| 1.50 – 2.00 | Heavy peak congestion |
| > 2.00 | Very heavy — peak drive is more than twice free-flow |

**Secondary metric — ADCI (All-Day Congestion Index):** mean of hourly median
CRs across 06:00–21:59. A road can have high PHCI but low ADCI (only bad at
peak) or moderate PHCI with high ADCI (sustained congestion across the day).

**Cross-check — peak minutes lost per trip.** A short corridor can show CR 2.0
but only ~60 sec of real delay. A long corridor can show CR 1.3 but 5+ min of
real delay. Use the minutes-lost table before recommending interventions for
short corridors.
        """
    )

with st.expander("Page 2 — Hourly Heatmap"):
    st.markdown(
        """
Rows are corridors (highest PHCI at top), columns are hours of day (06–22 IST),
cell colour = median CR.

| Colour | Meaning |
|---|---|
| White | Free-flow (~1.0) |
| Pale orange | Mild (1.10 – 1.25) |
| Orange | Noticeable (1.25 – 1.50) |
| Red | Heavy (1.50 – 2.00) |
| Dark red | Very heavy (> 2.00) |
| Blue | Faster than free-flow (rare; off-peak) |

**Patterns to look for:**
- Wide red bands → sustained all-day congestion → capacity issue.
- Two distinct red blocks (AM + PM) → directional commuter flow → consider
  one-way / contra-flow.
- Late-evening red (after 20:00) → after-office market traffic.

Dashed vertical lines mark the active peak windows. Default is UT govt
office hours (08–11 / 17–20); toggle the sidebar preset to switch to the
MoUD/NUTP SLB standard (06–10 / 16–20) and the bands move with you.
        """
    )

with st.expander("Page 3 — Direction Asymmetry"):
    st.markdown(
        """
Per corridor, the AM and PM peak CR split into the two directions of travel.

**Why this matters:** symmetric congestion (both directions equally bad) →
capacity problem. Asymmetric congestion → flow problem; one-way regulation,
contra-flow lanes, or signal-cycle retiming can help.

**Asymmetry %** = |CR(A→B) − CR(B→A)| ÷ max of the two × 100. 0% = perfectly
symmetric; 40% = one direction much worse.
        """
    )

with st.expander("Page 4 — Reliability Index"):
    st.markdown(
        """
**Headline — BTI (Buffer Time Index, FHWA standard):**
*(p95 − median) ÷ median* of peak-window durations. A BTI of 0.30 means a
commuter must budget 30% extra time to be on-time 95 days out of 100.

| BTI | Plain-English |
|---|---|
| < 0.15 | Reliable |
| 0.15 – 0.30 | Mostly reliable |
| 0.30 – 0.50 | Unpredictable |
| > 0.50 | Highly unpredictable |

**Cross-check — CV (Coefficient of Variation):** σ ÷ μ of peak duration.
Distribution-shape-agnostic; less sensitive to small samples.
        """
    )

with st.expander("Page 5 — Corridor Map"):
    st.markdown(
        """
All 25 corridors drawn along their actual road geometry (OpenStreetMap
Routing Machine), coloured by PHCI. Hover any line for full statistics.
The top 3 most-congested corridors are emphasised.

**Audit nuance:** the displayed line follows OSRM's path. The CR numbers are
ratios from Google's own route choice per call — route-invariant, since both
numerator and denominator come from the same Google route.
        """
    )

with st.expander("Page 6 — Methodology & Data Quality"):
    st.markdown(
        "Reference for reviewers. Mathematical formulas, coverage matrix, "
        "FAIL log, distance-drift audit, reproducibility MD5. Open this page "
        "when a finding is challenged."
    )

with st.expander("Page 7 — Downloads"):
    st.markdown(
        "One-click downloads of the **10-sheet Excel annexure** (audit-report "
        "ready) and a **ZIP of all charts** at 300 DPI for embedding in the "
        "Word/PDF report."
    )

# ---------------------------------------------------------------------------
# Glossary
# ---------------------------------------------------------------------------
st.header("Glossary — every short form in one place")
st.markdown(
    """
| Short form | Full term | Plain-English meaning |
|---|---|---|
| **CR** | Congestion Ratio | (drive time now) ÷ (drive time with no traffic) |
| **PHCI** | Peak-Hour Congestion Index | Weekday median CR at the peak hour, taken on the peak direction |
| **ADCI** | All-Day Congestion Index | Mean CR across active hours (06:00–22:59) |
| **BTI** | Buffer Time Index | Extra time % to budget to be on-time 95 days out of 100 |
| **CV** | Coefficient of Variation | Day-to-day variability of peak drive times |
| **OD pair** | Origin-Destination pair | One direction of one corridor |
| **IST** | Indian Standard Time | UTC+5:30 |
| **API** | Application Programming Interface | The Google service we query |
| **MD5** | Message-Digest algorithm 5 | Short fingerprint of a file (reproducibility) |
| **p95** | 95th percentile | Value that 95% of measurements are below |
| **median** | — | Middle value when measurements are sorted |
| **n** | Sample size | Number of measurements behind a given number |
| **FHWA** | Federal Highway Administration (US) | The agency whose BTI definition we use |
| **JPV** | Joint Physical Verification | On-site inspection pillar of the audit |
| **OSRM** | OpenStreetMap Routing Machine | Free routing engine used for map line geometry |
| **DPI** | Dots Per Inch | Image resolution (300 DPI = print quality) |
    """
)

# ---------------------------------------------------------------------------
# Gating badges
# ---------------------------------------------------------------------------
st.header("Locked / Preliminary / Stable")
st.markdown(
    """
The sidebar shows a small pill for each metric:

- **Locked** — not enough data yet; the chart is hidden until more measurements arrive.
- **Preliminary** — enough data to compute, but small sample. Quote the number with its `n`.
- **Stable** — sample size has crossed the audit-defensibility threshold. Cite without caveat.

Pills update automatically as the collector adds measurements every 30 minutes.
By 26 May 2026 (end of the audit window) every metric should be Stable.
    """
)

audit_context_caption(
    "Open Methodology & Data Quality (Page 6) for the mathematical formulas "
    "and the full data-quality audit."
)
