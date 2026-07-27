"""
Shared Plotly figure factories for the chandigarh congestion dashboard.

Every chart on every page goes through this module so the dashboard,
the Excel exporter, and the PNG export produce visually identical
artefacts. Colour scales and annotations are not parameterised — the
design choices on the heatmap (white=1.0 anchor, red=2.0+) are part
of the audit's visual language and must stay consistent.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import pydeck as pdk

# ---------------------------------------------------------------------------
# Chandigarh Plotly template — Modern-SaaS visual language used on every chart.
# Inter font (loaded via UI CSS), soft slate gridlines, plenty of margin.
# ---------------------------------------------------------------------------

CHANDIGARH_TEMPLATE = go.layout.Template(
    layout=go.Layout(
        font=dict(
            family="Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
            color="#0F172A",
            size=12,
        ),
        title=dict(font=dict(size=15, color="#0F172A"), x=0.0, xanchor="left"),
        plot_bgcolor="#FFFFFF",
        paper_bgcolor="#FFFFFF",
        xaxis=dict(
            gridcolor="#E2E8F0",
            linecolor="#CBD5E1",
            tickfont=dict(color="#475569", size=11),
            title=dict(font=dict(color="#334155", size=12)),
            zerolinecolor="#E2E8F0",
        ),
        yaxis=dict(
            gridcolor="#E2E8F0",
            linecolor="#CBD5E1",
            tickfont=dict(color="#475569", size=11),
            title=dict(font=dict(color="#334155", size=12)),
            zerolinecolor="#E2E8F0",
        ),
        legend=dict(
            font=dict(color="#334155", size=11),
            bgcolor="rgba(255,255,255,0.9)",
            bordercolor="#E2E8F0",
            borderwidth=0,
        ),
        margin=dict(l=60, r=40, t=60, b=40),
        colorway=["#4F46E5", "#F59E0B", "#10B981", "#EF4444", "#06B6D4", "#8B5CF6"],
    )
)


# ---------------------------------------------------------------------------
# The Chandigarh Congestion Heatmap colour scale — manual, not a Plotly default.
# Anchored so that white = free-flow boundary (1.0). Faster-than-free-flow
# values render blue (sanity-check region). Above 1.0 escalates orange→red.
# ---------------------------------------------------------------------------

HEATMAP_COLORSCALE = [
    [0.00, "#3b82f6"],   # 0.8  — faster than free-flow (blue)
    [0.118, "#93c5fd"],  # 1.0  — free-flow boundary, white
    [0.118, "#ffffff"],
    [0.265, "#fcd34d"],  # 1.25 — pale orange
    [0.412, "#f97316"],  # 1.5  — orange
    [0.706, "#dc2626"],  # 2.0  — red
    [1.00, "#7f1d1d"],   # 2.5+ — dark red
]
HEATMAP_ZMIN = 0.8
HEATMAP_ZMAX = 2.5
HEATMAP_ZMID = 1.0


def _empty_figure(message: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        xref="paper", yref="paper", x=0.5, y=0.5,
        showarrow=False,
        font=dict(size=14, color="#6b7280"),
    )
    fig.update_layout(
        template=CHANDIGARH_TEMPLATE,
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        plot_bgcolor="white", paper_bgcolor="white",
        margin=dict(l=20, r=20, t=40, b=20),
    )
    return fig


def hourly_heatmap(
    hourly_median: pd.DataFrame,
    corridor_order: list[str],
    title: str,
    subtitle: str,
    weekday_or_weekend: str = "Weekday",
    hours: range = range(6, 23),
) -> go.Figure:
    """Render the corridor × hour heatmap for one panel (Weekday OR Weekend).

    `hourly_median` columns: corridor_id, corridor_name, direction, hour,
                             weekday_or_weekend, median_cr, n
    `corridor_order` is a list of corridor_id strings, top-down on Y axis
                     (highest PHCI first). Both directions of each corridor
                     are collapsed to the per-corridor median of medians for
                     display purposes — the per-direction view lives on page 3.
    """
    sub = hourly_median[hourly_median["weekday_or_weekend"] == weekday_or_weekend].copy()
    if sub.empty:
        return _empty_figure(f"No {weekday_or_weekend.lower()} observations yet.")

    # Collapse both directions: per (corridor, hour) take median of direction medians.
    collapsed = (
        sub.groupby(["corridor_id", "corridor_name", "hour"])
        .agg(median_cr=("median_cr", "median"), n=("n", "sum"))
        .reset_index()
    )

    hour_list = list(hours)
    pivot_val = collapsed.pivot(index="corridor_id", columns="hour", values="median_cr")
    pivot_n = collapsed.pivot(index="corridor_id", columns="hour", values="n")
    name_map = dict(zip(collapsed["corridor_id"], collapsed["corridor_name"]))

    # Reindex Y by the requested PHCI-sorted order, X by full hour range.
    pivot_val = pivot_val.reindex(index=corridor_order, columns=hour_list)
    pivot_n = pivot_n.reindex(index=corridor_order, columns=hour_list).fillna(0)

    y_labels = [
        f"{cid}. {name_map.get(cid, cid)[:50]}" for cid in corridor_order
    ]

    text = pivot_val.round(2).astype(object)
    text = text.where(pivot_n >= 3, "")
    text = text.where(pivot_n > 0, "")
    text_n = pivot_n.astype(int).astype(str).where(
        (pivot_n > 0) & (pivot_n < 3), ""
    )
    text_combined = text.where(text != "", "n=" + text_n).where(pivot_n > 0, "")

    hover = (
        "Corridor: %{customdata[1]}<br>"
        "Hour: %{x}:00<br>"
        "Median CR: %{z:.3f}<br>"
        "n = %{customdata[0]}<extra></extra>"
    )

    customdata = []
    for cid in corridor_order:
        row = []
        for h in hour_list:
            n_val = int(pivot_n.loc[cid, h]) if cid in pivot_n.index else 0
            row.append([n_val, name_map.get(cid, cid)])
        customdata.append(row)

    fig = go.Figure(
        data=go.Heatmap(
            z=pivot_val.values,
            x=[f"{h:02d}" for h in hour_list],
            y=y_labels,
            colorscale=HEATMAP_COLORSCALE,
            zmin=HEATMAP_ZMIN, zmax=HEATMAP_ZMAX, zmid=HEATMAP_ZMID,
            text=text_combined.values,
            texttemplate="%{text}",
            textfont=dict(size=9),
            hovertemplate=hover,
            customdata=customdata,
            colorbar=dict(
                title="Median CR",
                tickvals=[0.8, 1.0, 1.25, 1.5, 2.0, 2.5],
                tickformat=".2f",
            ),
        )
    )

    # Faint amber bands shade the active peak windows — auto-tracking the
    # sidebar's peak-window preset so the bands always show what the rest of
    # the page is computing on. The x-axis is numeric, so cells centred on
    # integer hours span ±0.5; bands run from first-0.5 to last+0.5.
    from metrics import active_peak_hours
    _am_active, _pm_active, _ = active_peak_hours()
    for hrs in (_am_active, _pm_active):
        if not hrs:
            continue
        first_peak_hr, last_peak_hr = hrs[0], hrs[-1]
        if first_peak_hr in hour_list and last_peak_hr in hour_list:
            fig.add_vrect(
                x0=first_peak_hr - 0.5,
                x1=last_peak_hr + 0.5,
                fillcolor="#F59E0B", opacity=0.12,
                layer="below", line_width=0,
            )

    fig.update_layout(
        template=CHANDIGARH_TEMPLATE,
        title=dict(text=f"<b>{title}</b><br><span style='font-size:11px;color:#64748B'>{subtitle}</span>",
                   x=0.0, xanchor="left"),
        xaxis_title="Hour of day (IST)",
        # Highest PHCI at top; force every corridor name to render — without
        # tickmode=array Plotly auto-thins ticks when the chart is dense.
        yaxis=dict(
            autorange="reversed",
            tickmode="array",
            tickvals=y_labels,
            ticktext=y_labels,
            tickfont=dict(size=11),
            automargin=True,
        ),
        plot_bgcolor="white", paper_bgcolor="white",
        margin=dict(l=260, r=40, t=80, b=40),
        # No height cap. 22px per corridor row keeps the heatmap cells square
        # enough to be readable on the 17-hour x-axis.
        height=max(420, 22 * len(corridor_order) + 140),
    )
    return fig


def ranking_bar(ranking: pd.DataFrame, metric: str = "phci",
                title: str = "Peak-Hour Congestion Index — 38 corridors",
                max_name_len: int = 55) -> go.Figure:
    """Horizontal bar chart of corridors ranked by PHCI (or any chosen metric).

    Bars coloured on the same scale as the heatmap so the visual language
    is consistent. Short corridors (sensitive to signal-cycle noise) are
    hatched and asterisked.

    `max_name_len` controls how aggressively corridor names are truncated.
    The full-page chart packs 38 rows and uses the default 55; the compact
    Executive-Summary version passes a larger value since it only shows the
    top 6 and has more vertical breathing room.
    """
    if ranking.empty:
        return _empty_figure("Awaiting data.")

    df = ranking.copy().sort_values(metric, ascending=True).reset_index(drop=True)
    labels = [
        f"{r.corridor_id}. {r.corridor_name[:max_name_len]}"
        + (" *" if r.is_short_corridor else "")
        for r in df.itertuples()
    ]

    fig = go.Figure(
        data=go.Bar(
            x=df[metric],
            y=labels,
            orientation="h",
            marker=dict(
                color=df[metric],
                colorscale=HEATMAP_COLORSCALE,
                cmin=HEATMAP_ZMIN, cmax=HEATMAP_ZMAX, cmid=HEATMAP_ZMID,
                line=dict(color="#374151", width=0.5),
                showscale=False,
            ),
            text=[f"{v:.2f}" for v in df[metric]],
            textposition="outside",
            textfont=dict(size=12, color="#0F172A"),
            cliponaxis=False,
            hovertemplate=(
                "Corridor: %{y}<br>"
                f"{metric.upper()}: %{{x:.3f}}<br>"
                "<extra></extra>"
            ),
        )
    )
    fig.add_vline(x=1.0, line=dict(color="#475569", width=1, dash="dash"),
                  annotation_text="Free-flow (1.0)", annotation_position="top")

    # Outside text labels need room past the longest bar. The default Plotly
    # auto-range adds only ~5% padding past the max value, which clips the
    # text for whichever bar reaches the right edge of the plot area. Force
    # explicit headroom and also disable cliponaxis (above) as a safety net
    # for the chart's narrow Executive-Summary layout.
    max_val = float(df[metric].max())
    x_upper = max(max_val * 1.18, 1.3)

    fig.update_layout(
        template=CHANDIGARH_TEMPLATE,
        title=dict(text=f"<b>{title}</b>", x=0.0, xanchor="left"),
        xaxis=dict(range=[0, x_upper], title=metric.upper()),
        yaxis_title="",
        plot_bgcolor="white", paper_bgcolor="white",
        margin=dict(l=300, r=80, t=60, b=40),
        # No height cap — Plotly silently thins y-tick labels when bars exceed
        # the available height. 22px per row gives every label room to render.
        height=max(420, 22 * len(df) + 120),
        yaxis=dict(
            tickmode="array",
            tickvals=labels,
            ticktext=labels,
            tickfont=dict(size=11),
            automargin=True,
        ),
    )
    return fig


def direction_asymmetry_chart(asymmetry: pd.DataFrame, peak_label: str) -> go.Figure:
    """Paired horizontal bars per corridor: A_to_B vs B_to_A for one peak window."""
    sub = asymmetry[asymmetry["peak"] == peak_label].copy()
    if sub.empty:
        return _empty_figure(f"No {peak_label} data yet.")
    sub = sub.sort_values("asymmetry_pct", ascending=True)
    labels = [f"{r.corridor_id}. {r.corridor_name[:45]}" for r in sub.itertuples()]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=sub["median_cr_A_to_B"], y=labels, orientation="h",
        name="A → B", marker=dict(color="#2563eb"),
        hovertemplate="%{y}<br>A→B median CR: %{x:.3f}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=sub["median_cr_B_to_A"], y=labels, orientation="h",
        name="B → A", marker=dict(color="#dc2626"),
        hovertemplate="%{y}<br>B→A median CR: %{x:.3f}<extra></extra>",
    ))
    fig.add_vline(x=1.0, line=dict(color="#475569", width=1, dash="dash"))
    fig.update_layout(
        template=CHANDIGARH_TEMPLATE,
        barmode="group",
        title=dict(text=f"<b>Direction asymmetry — {peak_label}</b>",
                   x=0.0, xanchor="left"),
        xaxis_title="Median Congestion Ratio",
        plot_bgcolor="white", paper_bgcolor="white",
        margin=dict(l=280, r=40, t=60, b=40),
        # No height cap — see reliability_chart for rationale. With grouped
        # bars each corridor needs ~26px to keep both bars readable.
        height=max(420, 26 * len(sub) + 120),
        yaxis=dict(
            tickmode="array",
            tickvals=labels,
            ticktext=labels,
            tickfont=dict(size=11),
            automargin=True,
        ),
        legend=dict(orientation="h", y=-0.05),
    )
    return fig


def reliability_chart(bti_df: pd.DataFrame, metric: str = "bti") -> go.Figure:
    """BTI or CV per corridor-direction, horizontal bar.

    Adds a plain-English predictability label as text annotation.
    """
    if bti_df.empty:
        return _empty_figure("Awaiting data.")
    df = bti_df.copy().dropna(subset=[metric])
    df = df.sort_values(metric, ascending=True)
    _DIR = {"A_to_B": "A→B", "B_to_A": "B→A"}
    labels = [f"{r.corridor_id} ({_DIR.get(r.direction, r.direction)}) — {r.corridor_name[:40]}"
              for r in df.itertuples()]

    def english_label(v: float) -> str:
        if metric == "bti":
            if v < 0.15: return "Reliable"
            if v < 0.30: return "Mostly reliable"
            if v < 0.50: return "Unpredictable"
            return "Highly unpredictable"
        else:
            if v < 0.10: return "Stable"
            if v < 0.20: return "Variable"
            if v < 0.35: return "Volatile"
            return "Highly volatile"

    text = [f"{v:.2f} — {english_label(v)}" for v in df[metric]]

    cmax_val = max(0.5, float(df[metric].fillna(0).max() or 0.0))
    # The longest English label is "Highly unpredictable" (~26 chars including
    # leading "<value> — "). With textposition="outside", Plotly places that
    # text just past the bar end in axis coordinates; if the xaxis range
    # auto-fits to max value, the longest bar's outside text gets clipped at
    # the plot edge. Force enough headroom past the longest bar — 60% of cmax
    # — so the text always renders in full.
    x_upper = max(cmax_val * 1.6, 0.85)
    fig = go.Figure(go.Bar(
        x=df[metric], y=labels, orientation="h",
        marker=dict(color=df[metric], colorscale="Reds",
                    cmin=0, cmax=cmax_val,
                    showscale=False),
        text=text, textposition="outside",
        cliponaxis=False,
        hovertemplate="%{y}<br>" + metric.upper() + ": %{x:.3f}<extra></extra>",
    ))
    label_text = "Buffer Time Index (FHWA)" if metric == "bti" else "Coefficient of Variation"
    fig.update_layout(
        template=CHANDIGARH_TEMPLATE,
        title=dict(text=f"<b>{label_text} — peak window</b>", x=0.0, xanchor="left"),
        xaxis=dict(range=[0, x_upper], title=metric.upper()),
        plot_bgcolor="white", paper_bgcolor="white",
        margin=dict(l=340, r=80, t=60, b=40),
        # No height cap: with 56 corridor-direction rows Plotly will otherwise
        # auto-thin the y-tick labels and silently hide every other corridor
        # name. 22px per row + an explicit tickmode guarantees every label
        # renders.
        height=max(420, 22 * len(df) + 120),
        yaxis=dict(
            tickmode="array",
            tickvals=labels,
            ticktext=labels,
            tickfont=dict(size=11),
            automargin=True,
        ),
    )
    return fig


def coverage_heatmap(coverage: pd.DataFrame) -> go.Figure:
    """Corridor × date observation count, with cells coloured red/amber/green."""
    if coverage.empty:
        return _empty_figure("No coverage data.")
    pivot = coverage.pivot(index="corridor_id", columns="date", values="n_obs").fillna(0)
    fig = go.Figure(go.Heatmap(
        z=pivot.values,
        x=pivot.columns.tolist(),
        y=pivot.index.tolist(),
        colorscale=[
            [0.0, "#dc2626"],
            [0.5, "#fcd34d"],
            [1.0, "#16a34a"],
        ],
        # Full day = 48 batches × 2 directions = 96 observations per
        # (corridor, date) cell. Earlier zmax=48 was wrong and saturated every
        # complete day at the top of the ramp.
        zmin=0, zmax=96,
        text=pivot.values.astype(int),
        texttemplate="%{text}",
        textfont=dict(size=10),
        colorbar=dict(title="n obs/day"),
    ))
    fig.update_layout(
        template=CHANDIGARH_TEMPLATE,
        title=dict(text="<b>Observation Coverage — corridor × date</b>",
                   x=0.0, xanchor="left"),
        xaxis_title="Date",
        yaxis_title="Corridor ID",
        plot_bgcolor="white", paper_bgcolor="white",
        margin=dict(l=80, r=40, t=60, b=40),
        height=min(720, max(420, 16 * len(pivot) + 100)),
    )
    return fig


def cr_cdf_chart(cr_values: pd.Series) -> go.Figure:
    """CDF of all CR values — Methodology page sanity check."""
    s = cr_values.dropna().sort_values().reset_index(drop=True)
    if s.empty:
        return _empty_figure("No CR observations.")
    y = (s.rank(method="first") / len(s)).values
    fig = go.Figure(go.Scatter(x=s.values, y=y, mode="lines",
                               line=dict(color="#4F46E5", width=2)))
    fig.add_vline(x=1.0, line=dict(color="#EF4444", width=1, dash="dash"),
                  annotation_text="Free-flow (1.0)", annotation_position="top right")
    fig.update_layout(
        template=CHANDIGARH_TEMPLATE,
        title=dict(text="<b>Empirical CDF of Congestion Ratio</b>", x=0.0, xanchor="left"),
        xaxis_title="Congestion Ratio",
        yaxis_title="Cumulative share of observations",
        plot_bgcolor="white", paper_bgcolor="white",
        margin=dict(l=60, r=40, t=60, b=40),
        height=380,
    )
    return fig


# ---------------------------------------------------------------------------
# Executive-summary helpers: a compact ranking bar, a network-hourly line,
# and a small pydeck mini-map of the worst N corridors.
# ---------------------------------------------------------------------------

PROJECT_DIR = Path(__file__).resolve().parent.parent
POLYLINES_FILE = PROJECT_DIR / "corridor_polylines.json"


def compact_ranking_bar(ranking: pd.DataFrame, top_n: int = 6) -> go.Figure:
    """A short, executive-summary version of `ranking_bar` — top N corridors only.

    Only six rows fit in this chart, so we can afford taller rows, a longer
    left margin for full corridor names, and more right padding so the
    outside-text values render without clipping in the narrow half-column
    layout.
    """
    if ranking.empty:
        return _empty_figure("Awaiting data.")
    top = ranking.head(top_n).copy()
    fig = ranking_bar(
        top, metric="phci",
        title=f"Top {len(top)} corridors by Peak-Hour Congestion Index",
        max_name_len=80,
    )
    fig.update_layout(height=360, margin=dict(l=300, r=90, t=55, b=40))
    return fig


def network_hourly_line(df: pd.DataFrame) -> go.Figure:
    """Network-wide median Congestion Ratio by hour of day, weekday vs weekend."""
    if df.empty:
        return _empty_figure("No observations yet.")
    sub = df[df["hour"].astype(int).between(6, 22)].copy()
    sub["hour_int"] = sub["hour"].astype(int)
    grouped = (
        sub.groupby(["weekday_or_weekend", "hour_int"])
        .agg(median_cr=("congestion_ratio", "median"),
             n=("congestion_ratio", "size"))
        .reset_index()
    )
    fig = go.Figure()
    palette = {"Weekday": "#4F46E5", "Weekend": "#F59E0B"}
    for label in ("Weekday", "Weekend"):
        s = grouped[grouped["weekday_or_weekend"] == label].sort_values("hour_int")
        if s.empty:
            continue
        fig.add_trace(go.Scatter(
            x=s["hour_int"],
            y=s["median_cr"],
            mode="lines+markers",
            name=label,
            line=dict(color=palette[label], width=2.5),
            marker=dict(size=6, color=palette[label]),
            hovertemplate=f"{label}<br>%{{x}}:00 — CR %{{y:.2f}}<extra></extra>",
        ))
    fig.add_hline(y=1.0, line=dict(color="#94A3B8", width=1, dash="dash"),
                  annotation_text="Free-flow", annotation_position="bottom right",
                  annotation_font_color="#64748B")
    from metrics import active_peak_hours
    _am_active, _pm_active, _ = active_peak_hours()
    _edges = set()
    if _am_active:
        _edges.update([_am_active[0], _am_active[-1] + 1])
    if _pm_active:
        _edges.update([_pm_active[0], _pm_active[-1] + 1])
    for hr in sorted(_edges):
        fig.add_vline(x=hr, line=dict(color="#CBD5E1", width=1, dash="dot"))
    fig.update_layout(
        template=CHANDIGARH_TEMPLATE,
        title=dict(text="<b>When does congestion peak? — network median by hour</b>",
                   x=0.0, xanchor="left"),
        xaxis_title="Hour of day (IST)",
        yaxis_title="Median Congestion Ratio",
        xaxis=dict(tickmode="linear", tick0=6, dtick=2),
        height=320,
        margin=dict(l=60, r=30, t=50, b=40),
        legend=dict(orientation="h", y=1.08, x=1, xanchor="right"),
    )
    return fig


def _phci_to_rgb(v: float) -> list[int]:
    """Map a PHCI value to an RGB triplet on the same scale as the heatmap.

    Single source of truth for corridor-line color across the full map (page 5)
    and the executive-summary mini-map.
    """
    if pd.isna(v):
        return [156, 163, 175]
    if v < 1.0:
        return [59, 130, 246]
    if v < 1.25:
        return [252, 211, 77]
    if v < 1.5:
        return [249, 115, 22]
    if v < 2.0:
        return [220, 38, 38]
    return [127, 29, 29]


def _load_polylines() -> dict:
    if not POLYLINES_FILE.exists():
        return {}
    try:
        return json.loads(POLYLINES_FILE.read_text())
    except json.JSONDecodeError:
        return {}


def build_corridor_geometry(df: pd.DataFrame, ranking: pd.DataFrame) -> pd.DataFrame:
    """Build the per-corridor geometry frame used by both the full map and the mini-map.

    Joins corridor endpoints + ranking metrics, attaches OSRM polyline coords if
    available (else straight-line fallback), and adds rendering columns.
    """
    polylines = _load_polylines()
    geom = (
        df[["corridor_id", "corridor_name", "origin_lat", "origin_lng",
            "dest_lat", "dest_lng", "est_distance_km"]]
        .drop_duplicates(subset=["corridor_id"])
        .reset_index(drop=True)
    )
    geom = geom.dropna(subset=["corridor_id", "origin_lat", "origin_lng", "dest_lat", "dest_lng"]).copy()
    cols = ["corridor_id", "phci", "adci", "bti", "phci_hour"]
    cols = [c for c in cols if c in ranking.columns] or ["corridor_id"]
    display = geom.merge(ranking[cols], on="corridor_id", how="left")
    if "phci" in display.columns:
        display["phci"] = display["phci"].fillna(1.0)
    else:
        display["phci"] = 1.0
    if "rank" in ranking.columns:
        display = display.merge(ranking[["corridor_id", "rank"]], on="corridor_id", how="left")
    else:
        display["rank"] = pd.Series(range(1, len(display) + 1))

    def _coords(row):
        key = f"{row['corridor_id']}__A_to_B"
        entry = polylines.get(key)
        if entry and entry.get("coords"):
            return entry["coords"]
        return [[row["origin_lng"], row["origin_lat"]],
                [row["dest_lng"], row["dest_lat"]]]

    display["coords"] = display.apply(_coords, axis=1)
    display["color_rgb"] = display["phci"].apply(_phci_to_rgb)
    display["color_r"] = display["color_rgb"].apply(lambda c: c[0])
    display["color_g"] = display["color_rgb"].apply(lambda c: c[1])
    display["color_b"] = display["color_rgb"].apply(lambda c: c[2])
    display["phci_label"] = display["phci"].round(3).astype(str)
    display["n_path_points"] = display["coords"].apply(len)
    return display


def mini_map(display: pd.DataFrame, top_n: int = 5,
             show_labels: bool = False) -> pdk.Deck:
    """Compact pydeck map showing the top N most-congested corridors with context.

    All 38 corridors are drawn faintly so the geographic context is preserved;
    the top N are emphasised with full opacity, thicker lines, and a small
    rank badge at the line's midpoint.

    `show_labels=False` (default) renders rank-only badges; pair with an
    adjacent text list for the corridor names. `show_labels=True` writes the
    full corridor name on the map (legacy, can crowd the canvas).
    """
    if display.empty:
        return pdk.Deck(layers=[], initial_view_state=pdk.ViewState(
            longitude=76.77, latitude=30.733, zoom=11.5,
        ))
    df = display.copy()
    df["is_top"] = df["rank"] <= top_n
    # Rank-graded width: rank 1 thickest, descending. Faded grey for the rest.
    df["line_alpha"] = df["is_top"].map({True: 245, False: 50}).astype(int)
    df["line_width"] = df.apply(
        lambda r: max(11 - int(r["rank"]), 6) if r["is_top"] else 2.5,
        axis=1,
    )

    path_layer = pdk.Layer(
        "PathLayer",
        data=df,
        get_path="coords",
        get_color=["color_r", "color_g", "color_b", "line_alpha"],
        get_width="line_width",
        width_min_pixels=2,
        width_max_pixels=14,
        pickable=True,
        cap_rounded=True,
        joint_rounded=True,
    )

    layers = [path_layer]
    # Only opt-in legacy mode draws text on the map. Default keeps the canvas
    # clean — the ranked list beside the map carries the labels.
    if show_labels:
        label_df = df[df["is_top"]].copy()
        label_df["label_text"] = label_df.apply(
            lambda r: f"{int(r['rank'])}. {r['corridor_name'][:28]}", axis=1
        )
        label_df["mid_lng"] = label_df["coords"].apply(
            lambda c: c[len(c) // 2][0] if c else 0
        )
        label_df["mid_lat"] = label_df["coords"].apply(
            lambda c: c[len(c) // 2][1] if c else 0
        )
        layers.append(pdk.Layer(
            "TextLayer",
            data=label_df,
            get_position=["mid_lng", "mid_lat"],
            get_text="label_text",
            get_size=12,
            get_color=[15, 23, 42, 230],
            get_alignment_baseline="'center'",
            background=True,
            get_background_color=[255, 255, 255, 220],
            get_border_color=[226, 232, 240, 255],
            get_border_width=1,
        ))

    tooltip = {
        "html": "<b>★ Rank {rank} — {corridor_name}</b><br/>PHCI: {phci_label}",
        "style": {"backgroundColor": "white", "color": "#0F172A",
                  "fontSize": "12px", "padding": "8px",
                  "border": "1px solid #E2E8F0", "borderRadius": "6px"},
    }
    return pdk.Deck(
        layers=layers,
        initial_view_state=pdk.ViewState(
            longitude=76.77, latitude=30.733, zoom=11.5, pitch=0, bearing=0,
        ),
        map_style="light_no_labels",
        tooltip=tooltip,
    )
