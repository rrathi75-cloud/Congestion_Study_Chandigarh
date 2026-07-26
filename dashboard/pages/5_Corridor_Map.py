"""Page 5 — Corridor Map.

Brief output #5: an interactive map of Chandigarh with all 25 corridors colour-coded
by Peak-Hour Congestion Index. Designed as an audit-report-ready visual.

Each corridor is drawn along its actual road geometry, sourced from
`corridor_polylines.json` (built one-time via `tools/fetch_corridor_polylines.py`
using the free OpenStreetMap Routing Machine demo server). The polylines
are for DISPLAY ONLY — Congestion Ratio metrics are calculated on Google's
own route choice for each measurement, which is route-invariant (both
numerator and denominator come from the same Google route per call).
"""

from __future__ import annotations

import pydeck as pdk
import streamlit as st

from data import cached_observations, cached_quality_report, data_signature
from insights import map_narrative
from metrics import ranking_table
from ui import apply_page_chrome, audit_context_caption, callout, page_header
from viz import build_corridor_geometry

st.set_page_config(page_title="Corridor Map", page_icon="🗺️", layout="wide")


sig = data_signature()
df = cached_observations(sig)
ranking = ranking_table(df)
quality = cached_quality_report(sig)
stats = quality["stats"]

apply_page_chrome(df, ranking, stats)

page_header(
    title="Chandigarh — Corridor Congestion Map",
    subtitle=("Brief output #5 — all 25 corridors of Chandigarh, drawn along their actual "
              "road geometry and colour-coded by Peak-Hour Congestion Index. "
              "Suitable for inclusion in the audit report."),
    eyebrow="Page 5",
)

if df.empty:
    st.warning("No observations yet.")
    st.stop()

display = build_corridor_geometry(df, ranking)

callout(map_narrative(ranking, top_n=3), kind="insight",
        title="The 3 corridors that need first-priority attention")

# ---------------------------------------------------------------------------
# pydeck layers — full map (top 3 emphasised in tooltip and weight)
# ---------------------------------------------------------------------------
display["is_top3"] = display["rank"] <= 3
display["line_width"] = display["is_top3"].map({True: 8, False: 5}).astype(int)
display["line_alpha"] = display["is_top3"].map({True: 240, False: 200}).astype(int)
display["tooltip_prefix"] = display["is_top3"].map({True: "★ ", False: ""})

path_layer = pdk.Layer(
    "PathLayer",
    data=display,
    get_path="coords",
    get_color=["color_r", "color_g", "color_b", "line_alpha"],
    get_width="line_width",
    width_min_pixels=3,
    width_max_pixels=12,
    pickable=True,
    auto_highlight=True,
    cap_rounded=True,
    joint_rounded=True,
)

origin_layer = pdk.Layer(
    "ScatterplotLayer",
    data=display,
    get_position=["origin_lng", "origin_lat"],
    get_fill_color=[15, 23, 42, 200],
    get_radius=70,
    pickable=False,
)
dest_layer = pdk.Layer(
    "ScatterplotLayer",
    data=display,
    get_position=["dest_lng", "dest_lat"],
    get_fill_color=[15, 23, 42, 200],
    get_radius=70,
    pickable=False,
)

view_state = pdk.ViewState(
    longitude=76.78,
    latitude=30.73,
    zoom=11.2,
    pitch=0,
    bearing=0,
)

tooltip = {
    "html": "<b>{tooltip_prefix}Rank {rank} — {corridor_id}. {corridor_name}</b><br/>"
            "PHCI: {phci_label}<br/>"
            "Peak hour: {phci_hour}:00<br/>"
            "Est. distance: {est_distance_km} km",
    "style": {"backgroundColor": "white", "color": "#0F172A",
              "fontSize": "12px", "padding": "8px",
              "border": "1px solid #E2E8F0", "borderRadius": "6px"},
}

deck = pdk.Deck(
    layers=[path_layer, origin_layer, dest_layer],
    initial_view_state=view_state,
    map_style="light",
    tooltip=tooltip,
)

st.pydeck_chart(deck, use_container_width=True)

# ---------------------------------------------------------------------------
# Legend
# ---------------------------------------------------------------------------
st.markdown(
    "**Colour scale — Peak-Hour Congestion Index (PHCI):** "
    "<span style='background:#3b82f6;color:white;padding:2px 6px;border-radius:4px;'>&lt; 1.0</span> "
    "<span style='background:#fcd34d;color:black;padding:2px 6px;border-radius:4px;'>1.0–1.25</span> "
    "<span style='background:#f97316;color:white;padding:2px 6px;border-radius:4px;'>1.25–1.5</span> "
    "<span style='background:#dc2626;color:white;padding:2px 6px;border-radius:4px;'>1.5–2.0</span> "
    "<span style='background:#7f1d1d;color:white;padding:2px 6px;border-radius:4px;'>≥ 2.0</span> "
    "<span style='background:#9ca3af;color:white;padding:2px 6px;border-radius:4px;'>no data</span>",
    unsafe_allow_html=True,
)

st.subheader("Corridor summary")
table = display[[
    "rank", "corridor_id", "corridor_name", "est_distance_km",
    "phci", "phci_hour", "adci", "bti", "n_path_points",
]].copy()
table = table.sort_values("phci", ascending=False).reset_index(drop=True)
table["phci"] = table["phci"].round(3)
if "adci" in table.columns:
    table["adci"] = table["adci"].round(3)
if "bti" in table.columns:
    table["bti"] = table["bti"].round(3)
table = table.rename(columns={"n_path_points": "Road-path vertices"})
st.dataframe(table, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Methodology note — moved below the table to keep the map+legend the focus
# ---------------------------------------------------------------------------
with st.expander("What the lines on this map actually represent"):
    st.markdown(
        """
        Each corridor is drawn as a path following the **actual road geometry**
        between its two endpoints, sourced from the **OpenStreetMap Routing
        Machine (OSRM)**. The geometry is fetched once via
        `tools/fetch_corridor_polylines.py` and cached in
        `corridor_polylines.json` (committed to the repo for reproducibility).

        **Important nuance for audit-defensibility:** the OSRM path is for
        **display only**. The Congestion Ratio numbers themselves come from
        Google's live route choice for each 30-minute measurement, which can
        differ slightly between calls (see the *Distance Drift* table on the
        Methodology & Data Quality page). All metrics on this dashboard are
        **ratios** of Google's live-traffic time to Google's free-flow time
        on the *same call*, so they are route-invariant — Google can re-route
        without affecting the ratio's validity.

        In short: the map shows the canonical road being measured; the numbers
        on the dashboard reflect the actual traffic on whatever path Google
        chose at each measurement instant.
        """
    )

audit_context_caption(
    "Map tiles: CARTO Light. Geometry: OpenStreetMap Routing Machine (OSRM). "
    "Publication-quality PNG export available on the Downloads page."
)
