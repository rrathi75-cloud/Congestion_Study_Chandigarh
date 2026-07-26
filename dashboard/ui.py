"""
Shared UI chrome for the chandigarh Mobility dashboard.

Single source of truth for the Modern-SaaS visual language: global CSS,
page header, KPI tiles, "so what" callouts, sidebar status pills, and the
sidebar glossary expander. Every page imports from this module and calls
`apply_page_chrome(...)` at the top so the look stays consistent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import streamlit as st

__all__ = [
    "KPI",
    "SLBIndicator",
    "ACCENT_COLORS",
    "apply_page_chrome",
    "audit_context_caption",
    "callout",
    "chart_evidence_caption",
    "headline_findings",
    "heatmap_color_legend",
    "inject_global_css",
    "kpi_row",
    "page_header",
    "render_sidebar",
    "sidebar_freshness_footer",
    "sidebar_glossary_expander",
    "sidebar_peak_window_control",
    "sidebar_status_pills",
    "slb_indicator_strip",
    "top_rank_list",
]


# ---------------------------------------------------------------------------
# Global CSS — injected once per page render. Streamlit re-runs the script
# top-to-bottom, so calling this from every page is fine.
# ---------------------------------------------------------------------------

_GLOBAL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"], [data-testid="stAppViewContainer"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}
h1, h2, h3, h4 { font-family: 'Inter', sans-serif !important; letter-spacing: -0.01em; }

/* Page header */
.chandigarh-hero {
    background: linear-gradient(135deg, #EEF2FF 0%, #F8FAFC 60%, #FFFFFF 100%);
    border: 1px solid #E2E8F0;
    border-radius: 16px;
    padding: 22px 26px;
    margin: 4px 0 18px 0;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}
.chandigarh-hero-title {
    font-size: 26px;
    font-weight: 700;
    color: #0F172A;
    margin: 0;
    letter-spacing: -0.02em;
    line-height: 1.2;
}
.chandigarh-hero-subtitle {
    font-size: 13.5px;
    color: #475569;
    margin-top: 6px;
    font-weight: 400;
    line-height: 1.5;
}
.chandigarh-hero-eyebrow {
    font-size: 11px;
    font-weight: 600;
    color: #4F46E5;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 6px;
}

/* KPI cards */
.chandigarh-kpi-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
    gap: 12px;
    margin: 4px 0 18px 0;
}
.chandigarh-card {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    padding: 14px 16px 12px 16px;
    box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
    position: relative;
    overflow: hidden;
}
.chandigarh-card::before {
    content: "";
    position: absolute;
    left: 0; top: 0; bottom: 0;
    width: 3px;
    background: var(--accent, #4F46E5);
}
.chandigarh-kpi-label {
    font-size: 10.5px;
    font-weight: 600;
    color: #64748B;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin: 0;
}
.chandigarh-kpi-value {
    font-size: 22px;
    font-weight: 700;
    color: #0F172A;
    margin: 4px 0 2px 0;
    line-height: 1.15;
    letter-spacing: -0.01em;
}
.chandigarh-kpi-sublabel {
    font-size: 11.5px;
    color: #64748B;
    margin: 0;
    line-height: 1.4;
}

/* Headline findings — hero strip on the Executive Summary */
.chandigarh-headline-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    margin: 6px 0 18px 0;
}
@media (max-width: 900px) {
    .chandigarh-headline-grid { grid-template-columns: 1fr; }
}
.chandigarh-headline-card {
    border-radius: 14px;
    padding: 22px 24px 18px 26px;
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-left: 5px solid var(--accent, #4F46E5);
    box-shadow: 0 2px 4px rgba(15, 23, 42, 0.04);
}
.chandigarh-headline-eyebrow {
    font-size: 10.5px;
    font-weight: 700;
    color: var(--accent, #4F46E5);
    text-transform: uppercase;
    letter-spacing: 0.09em;
    margin: 0 0 12px 0;
}
.chandigarh-headline-value {
    font-size: 32px;
    font-weight: 800;
    color: #0F172A;
    margin: 0 0 12px 0;
    line-height: 1.05;
    letter-spacing: -0.025em;
    font-variant-numeric: tabular-nums;
}
.chandigarh-headline-where {
    font-size: 14px;
    font-weight: 600;
    color: #1E293B;
    line-height: 1.35;
    margin: 0;
}
.chandigarh-headline-when {
    font-size: 12px;
    color: #475569;
    font-weight: 500;
    margin: 5px 0 0 0;
}
.chandigarh-headline-detail {
    font-size: 11.5px;
    color: #64748B;
    margin-top: 12px;
    padding-top: 10px;
    border-top: 1px solid #E2E8F0;
    line-height: 1.5;
}
/* Intensity scale — gives a magnitude reference for the big number */
.chandigarh-headline-scale {
    margin: 4px 0 14px 0;
}
.chandigarh-headline-scale-track {
    height: 7px;
    border-radius: 4px;
    position: relative;
    background: linear-gradient(to right,
        #93C5FD 0%, #FFFFFF 12%,
        #FCD34D 26%, #F97316 41%,
        #DC2626 70%, #7F1D1D 100%);
    border: 1px solid #E2E8F0;
}
.chandigarh-headline-scale-marker {
    position: absolute;
    top: -4px;
    width: 14px;
    height: 14px;
    border-radius: 50%;
    background: #0F172A;
    border: 2.5px solid #FFFFFF;
    box-shadow: 0 1px 3px rgba(15, 23, 42, 0.35);
    transform: translateX(-50%);
}
.chandigarh-headline-scale-ticks {
    display: flex;
    justify-content: space-between;
    font-size: 9.5px;
    color: #94A3B8;
    margin-top: 6px;
    font-weight: 600;
    letter-spacing: 0.04em;
}

/* Callouts */
.chandigarh-callout {
    border-radius: 12px;
    padding: 14px 18px;
    margin: 14px 0;
    border-left: 4px solid var(--accent, #4F46E5);
    background: var(--bg, #EEF2FF);
}
.chandigarh-callout-title {
    font-size: 12px;
    font-weight: 700;
    color: var(--accent, #4F46E5);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin: 0 0 6px 0;
}
.chandigarh-callout-body {
    font-size: 13.5px;
    color: #1E293B;
    line-height: 1.55;
    margin: 0;
}
.chandigarh-callout-body ul { margin: 6px 0 0 18px; padding: 0; }
.chandigarh-callout-body li { margin-bottom: 4px; }

/* Status pills (sidebar) */
.chandigarh-status-list { margin: 4px 0 12px 0; padding: 0; list-style: none; }
.chandigarh-status-row {
    display: flex; justify-content: space-between; align-items: center;
    padding: 6px 0;
    border-bottom: 1px dashed #E2E8F0;
    font-size: 12px;
}
.chandigarh-status-row:last-child { border-bottom: none; }
.chandigarh-status-label { color: #334155; font-weight: 500; }
.chandigarh-status-pill {
    display: inline-block;
    padding: 2px 9px;
    border-radius: 999px;
    font-size: 10.5px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}
.chandigarh-pill-locked     { background: #F1F5F9; color: #64748B; }
.chandigarh-pill-prelim     { background: #FEF3C7; color: #92400E; }
.chandigarh-pill-stable     { background: #D1FAE5; color: #065F46; }

/* Ranked-list (paired with mini-map) */
.chandigarh-ranklist {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    padding: 14px 16px;
    box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
}
.chandigarh-ranklist-title {
    font-size: 11px;
    font-weight: 700;
    color: #64748B;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin: 0 0 10px 0;
}
.chandigarh-ranklist-row {
    display: flex; align-items: center; gap: 10px;
    padding: 9px 0;
    border-bottom: 1px solid #F1F5F9;
}
.chandigarh-ranklist-row:last-child { border-bottom: none; }
.chandigarh-ranklist-badge {
    flex: 0 0 auto;
    width: 26px; height: 26px;
    border-radius: 999px;
    color: #FFFFFF;
    font-weight: 700;
    font-size: 13px;
    display: inline-flex; align-items: center; justify-content: center;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.15);
}
.chandigarh-ranklist-body { flex: 1 1 auto; min-width: 0; }
.chandigarh-ranklist-name {
    font-size: 13px;
    font-weight: 600;
    color: #0F172A;
    line-height: 1.3;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.chandigarh-ranklist-meta {
    font-size: 11px;
    color: #64748B;
    margin-top: 2px;
}
.chandigarh-ranklist-phci {
    flex: 0 0 auto;
    font-size: 13px;
    font-weight: 700;
    color: #0F172A;
    font-variant-numeric: tabular-nums;
}
.chandigarh-ranklist-foot {
    font-size: 10.5px;
    color: #94A3B8;
    margin: 8px 0 0 0;
    padding-top: 8px;
    border-top: 1px dashed #E2E8F0;
    line-height: 1.4;
}

/* SLB framework-alignment strip */
.chandigarh-slb-wrap {
    background: linear-gradient(135deg, #ECFDF5 0%, #F0FDFA 100%);
    border: 1px solid #A7F3D0;
    border-radius: 14px;
    padding: 16px 18px 14px 18px;
    margin: 8px 0 18px 0;
}
.chandigarh-slb-title {
    font-size: 11px;
    font-weight: 700;
    color: #0F766E;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin: 0 0 2px 0;
}
.chandigarh-slb-subtitle {
    font-size: 12px;
    color: #115E59;
    font-weight: 500;
    margin: 0 0 12px 0;
    line-height: 1.45;
}
.chandigarh-slb-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 12px;
}
.chandigarh-slb-card {
    background: #FFFFFF;
    border: 1px solid #D1FAE5;
    border-radius: 11px;
    padding: 12px 14px 12px 14px;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
    border-left: 3px solid #0F766E;
    display: flex;
    flex-direction: column;
    gap: 4px;
}
.chandigarh-slb-name {
    font-size: 10.5px;
    font-weight: 700;
    color: #0F766E;
    text-transform: uppercase;
    letter-spacing: 0.06em;
}
.chandigarh-slb-value {
    font-size: 22px;
    font-weight: 700;
    color: #0F172A;
    line-height: 1.15;
    letter-spacing: -0.01em;
    font-variant-numeric: tabular-nums;
}
.chandigarh-slb-def {
    font-size: 11.5px;
    color: #475569;
    line-height: 1.4;
    margin: 2px 0 0 0;
}
.chandigarh-slb-reality {
    display: flex;
    flex-direction: column;
    gap: 1px;
    padding: 6px 9px;
    margin: 4px 0 2px 0;
    background: #FFF7ED;
    border: 1px solid #FED7AA;
    border-left: 3px solid #C2410C;
    border-radius: 6px;
}
.chandigarh-slb-reality-label {
    font-size: 9.5px;
    font-weight: 700;
    color: #9A3412;
    text-transform: uppercase;
    letter-spacing: 0.07em;
}
.chandigarh-slb-reality-value {
    font-size: 13px;
    font-weight: 600;
    color: #7C2D12;
    line-height: 1.3;
    font-variant-numeric: tabular-nums;
}
.chandigarh-slb-meta {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 6px;
    padding-top: 8px;
    border-top: 1px dashed #E2E8F0;
    font-size: 10.5px;
    color: #64748B;
}

/* Chart-evidence caption — small "Evidences SLB-X / ADM Q-Y" tag under charts */
.chandigarh-evidence {
    display: inline-block;
    padding: 4px 10px;
    margin: -4px 0 12px 0;
    background: #F0FDFA;
    border: 1px solid #99F6E4;
    border-left: 3px solid #0F766E;
    border-radius: 6px;
    font-size: 11px;
    color: #115E59;
    font-weight: 500;
    line-height: 1.45;
}
.chandigarh-evidence b { color: #0F766E; font-weight: 700; }

/* Heatmap inline legend */
.chandigarh-legend {
    display: flex; flex-wrap: wrap; gap: 6px;
    align-items: center;
    margin: 6px 0 10px 0;
    font-size: 11.5px;
    color: #475569;
}
.chandigarh-legend-chip {
    display: inline-block;
    padding: 2px 9px;
    border-radius: 6px;
    font-weight: 600;
    border: 1px solid rgba(15, 23, 42, 0.08);
}

/* Audit context caption */
.chandigarh-context {
    font-size: 11.5px;
    color: #64748B;
    padding: 8px 12px;
    background: #F8FAFC;
    border-radius: 8px;
    margin: 8px 0 14px 0;
    border: 1px solid #E2E8F0;
}

/* Sidebar tweaks */
[data-testid="stSidebar"] { background: #F8FAFC; }
[data-testid="stSidebar"] .chandigarh-side-title {
    font-size: 14px; font-weight: 700; color: #0F172A; margin: 0;
    letter-spacing: -0.01em;
}
[data-testid="stSidebar"] .chandigarh-side-sub {
    font-size: 11px; color: #64748B; margin: 2px 0 12px 0;
}

/* Print */
@media print {
    [data-testid="stSidebar"], [data-testid="stToolbar"], [data-testid="stHeader"] {
        display: none !important;
    }
    .chandigarh-card, .chandigarh-callout, .chandigarh-hero {
        page-break-inside: avoid;
        box-shadow: none !important;
    }
    body { font-size: 11pt; }
    .stPlotlyChart, .stDeckGlJsonChart { page-break-inside: avoid; }
}
</style>
"""


def inject_global_css() -> None:
    """Inject the global stylesheet. Idempotent — safe to call from every page."""
    st.markdown(_GLOBAL_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------

def page_header(title: str, subtitle: str = "", eyebrow: str = "") -> None:
    """Render the standard page hero block."""
    parts = ['<div class="chandigarh-hero">']
    if eyebrow:
        parts.append(f'<div class="chandigarh-hero-eyebrow">{eyebrow}</div>')
    parts.append(f'<div class="chandigarh-hero-title">{title}</div>')
    if subtitle:
        parts.append(f'<div class="chandigarh-hero-subtitle">{subtitle}</div>')
    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# KPI cards
# ---------------------------------------------------------------------------

ACCENT_COLORS = {
    "indigo":  "#4F46E5",
    "amber":   "#F59E0B",
    "rose":    "#EF4444",
    "emerald": "#10B981",
    "cyan":    "#06B6D4",
    "violet":  "#8B5CF6",
    "slate":   "#64748B",
}


@dataclass
class KPI:
    label: str
    value: str
    sublabel: str = ""
    accent: str = "indigo"


def kpi_row(cards: Iterable[KPI | dict]) -> None:
    """Render a responsive grid of KPI cards.

    Accepts KPI dataclass instances or plain dicts with the same keys.
    """
    items = []
    for c in cards:
        if isinstance(c, dict):
            c = KPI(**c)
        accent = ACCENT_COLORS.get(c.accent, ACCENT_COLORS["indigo"])
        items.append(
            f'<div class="chandigarh-card" style="--accent:{accent};">'
            f'<div class="chandigarh-kpi-label">{c.label}</div>'
            f'<div class="chandigarh-kpi-value">{c.value}</div>'
            + (f'<div class="chandigarh-kpi-sublabel">{c.sublabel}</div>' if c.sublabel else "")
            + '</div>'
        )
    st.markdown(
        f'<div class="chandigarh-kpi-grid">{"".join(items)}</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Headline findings — hero strip used on the Executive Summary
# ---------------------------------------------------------------------------

_HEADLINE_PALETTE = {
    "indigo": "#4F46E5",
    "amber":  "#B45309",
    "slate":  "#475569",
    "teal":   "#0F766E",
}

_SCALE_MIN = 1.0   # free-flow
_SCALE_MAX = 3.0   # three-times free-flow — top of the heatmap colour scale


def _scale_block(ratio: float) -> str:
    """Render an intensity bar that shows where `ratio` sits between 1.0× and 3.0×.

    The track is the same colour gradient as the heatmap legend so readers can
    map a headline value back to the rest of the dashboard's visual language.
    """
    pct = (ratio - _SCALE_MIN) / (_SCALE_MAX - _SCALE_MIN)
    pct_clamped = max(0.0, min(1.0, pct)) * 100.0
    return (
        '<div class="chandigarh-headline-scale">'
        '<div class="chandigarh-headline-scale-track">'
        f'<div class="chandigarh-headline-scale-marker" style="left:{pct_clamped:.1f}%;"></div>'
        '</div>'
        '<div class="chandigarh-headline-scale-ticks">'
        '<span>1.0× free-flow</span>'
        '<span>2.0× heavy</span>'
        '<span>3.0×+</span>'
        '</div>'
        '</div>'
    )


def headline_findings(items: list[dict]) -> None:
    """Render a hero strip of headline findings on the Executive Summary.

    Each item supports the following keys:
      eyebrow  : small uppercase label above the big number
      value    : the big number itself, displayed at 32px
      where    : corridor / location line
      when     : time line
      detail   : footer detail (HTML allowed)
      ratio    : float — if provided, an intensity bar is drawn between the
                 value and the where/when block, with a marker at this ratio
                 on the 1.0×–3.0× free-flow scale.
      accent   : palette key — indigo / amber / slate / teal.
    """
    if not items:
        return
    cards = []
    for it in items:
        accent = _HEADLINE_PALETTE.get(it.get("accent", "indigo"),
                                       _HEADLINE_PALETTE["indigo"])
        parts = [
            f'<div class="chandigarh-headline-card" style="--accent:{accent};">',
        ]
        if it.get("eyebrow"):
            parts.append(f'<div class="chandigarh-headline-eyebrow">{it["eyebrow"]}</div>')
        if it.get("value"):
            parts.append(f'<div class="chandigarh-headline-value">{it["value"]}</div>')
        if it.get("ratio") is not None:
            parts.append(_scale_block(float(it["ratio"])))
        if it.get("where"):
            parts.append(f'<div class="chandigarh-headline-where">{it["where"]}</div>')
        if it.get("when"):
            parts.append(f'<div class="chandigarh-headline-when">{it["when"]}</div>')
        if it.get("detail"):
            parts.append(f'<div class="chandigarh-headline-detail">{it["detail"]}</div>')
        parts.append("</div>")
        cards.append("".join(parts))
    st.markdown(
        f'<div class="chandigarh-headline-grid">{"".join(cards)}</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Callout box
# ---------------------------------------------------------------------------

_CALLOUT_VARIANTS = {
    "insight": ("#4F46E5", "#EEF2FF"),
    "warning": ("#D97706", "#FEF3C7"),
    "good":    ("#059669", "#D1FAE5"),
    "neutral": ("#475569", "#F1F5F9"),
}


def callout(body: str, kind: str = "insight", title: str = "") -> None:
    """Render a "so what" callout box. `body` may contain Markdown/HTML."""
    accent, bg = _CALLOUT_VARIANTS.get(kind, _CALLOUT_VARIANTS["insight"])
    title_html = (
        f'<div class="chandigarh-callout-title" style="color:{accent};">{title}</div>'
        if title else ""
    )
    st.markdown(
        f'<div class="chandigarh-callout" style="--accent:{accent}; --bg:{bg};">'
        f'{title_html}'
        f'<div class="chandigarh-callout-body">{body}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Audit context caption — small footer used after charts
# ---------------------------------------------------------------------------

def audit_context_caption(extra: str = "") -> None:
    base = ("25 Chandigarh corridors · 27july–11 August 2026 · Google Routes API v2 (30-min polling). "
            "Data-driven evidence base for the Chandigarh Urban Mobility Audit.")
    text = f"{base} {extra}".strip()
    st.markdown(f'<div class="chandigarh-context">{text}</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Heatmap inline legend
# ---------------------------------------------------------------------------

def top_rank_list(ranking, top_n: int = 5, title: str = "Top corridors",
                  footer: str = "") -> None:
    """Color-matched ranked list designed to sit beside the mini-map.

    `ranking` must include columns: rank, corridor_name, phci, phci_hour
    (and optionally phci_direction). Badge colors mirror the PHCI colour
    scale used on the map, so a number in the list visually maps to a
    line on the map without any text labels on the map itself.
    """
    if ranking is None or len(ranking) == 0:
        return
    rows_html = []
    sub = ranking.head(top_n)
    for _, r in sub.iterrows():
        phci_v = float(r["phci"])
        rgb = _phci_rgb(phci_v)
        badge_bg = f"rgb({rgb[0]},{rgb[1]},{rgb[2]})"
        name = str(r["corridor_name"])
        meta_bits = []
        if "phci_hour" in r and r["phci_hour"] is not None:
            try:
                meta_bits.append(f"peaks at {int(r['phci_hour']):02d}:00")
            except (TypeError, ValueError):
                pass
        if "phci_direction" in r and r["phci_direction"]:
            dir_pretty = {"A_to_B": "A→B", "B_to_A": "B→A"}.get(
                str(r["phci_direction"]), str(r["phci_direction"]))
            meta_bits.append(dir_pretty)
        meta = " · ".join(meta_bits) or "&nbsp;"
        rows_html.append(
            f'<div class="chandigarh-ranklist-row">'
            f'<span class="chandigarh-ranklist-badge" style="background:{badge_bg};">'
            f'{int(r["rank"])}</span>'
            f'<div class="chandigarh-ranklist-body">'
            f'<div class="chandigarh-ranklist-name" title="{name}">{name}</div>'
            f'<div class="chandigarh-ranklist-meta">{meta}</div>'
            f'</div>'
            f'<span class="chandigarh-ranklist-phci">PHCI {phci_v:.2f}</span>'
            f'</div>'
        )
    foot_html = f'<div class="chandigarh-ranklist-foot">{footer}</div>' if footer else ""
    st.markdown(
        f'<div class="chandigarh-ranklist">'
        f'<div class="chandigarh-ranklist-title">{title}</div>'
        + "".join(rows_html) + foot_html + "</div>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# SLB-indicator strip — MoUD / NUTP Service Level Benchmark tile row
# ---------------------------------------------------------------------------

@dataclass
class SLBIndicator:
    """One tile in the SLB framework-alignment strip on the Executive Summary."""
    name: str               # eyebrow, e.g. "Traffic Congestion at Peak"
    value: str              # big number (the MoUD framework value)
    definition: str         # MoUD framing in one line
    state: str              # "Locked" | "Preliminary" | "Stable"
    detail: str = ""        # extra n=… info
    reality_label: str = "" # eyebrow on the corridor-reality contrast row
    reality_value: str = "" # the corridor-level reality the framework value hides


def slb_indicator_strip(items: list[SLBIndicator],
                        title: str = "MoUD Service Level Benchmarks — framework view vs. corridor reality",
                        subtitle: str = (
                            "MoUD/NUTP Service Level Benchmarks, computed on the "
                            "guideline peak window (06–10 / 16–20 weekday IST). "
                            "These are network-wide medians taken across all eight "
                            "peak hours and all 38 corridors, plus a 1.5× ‘congested’ "
                            "threshold — together they structurally dilute the "
                            "concentrated peak-hour congestion residents experience. "
                            "Beneath each framework value, the corridor-level reality "
                            "at the corridor’s own peak hour is shown."
                        )) -> None:
    """Render the SLB framework-alignment strip on the Executive Summary."""
    if not items:
        return
    pill_class = {
        "Locked":      "chandigarh-pill-locked",
        "Preliminary": "chandigarh-pill-prelim",
        "Stable":      "chandigarh-pill-stable",
    }
    cards = []
    for it in items:
        cls = pill_class.get(it.state, "chandigarh-pill-locked")
        meta = (
            f'<span class="chandigarh-status-pill {cls}">{it.state}</span>'
            + (f'<span>{it.detail}</span>' if it.detail else "")
        )
        reality_html = ""
        if it.reality_value:
            reality_html = (
                '<div class="chandigarh-slb-reality">'
                f'<span class="chandigarh-slb-reality-label">{it.reality_label or "Corridor reality"}</span>'
                f'<span class="chandigarh-slb-reality-value">{it.reality_value}</span>'
                '</div>'
            )
        cards.append(
            '<div class="chandigarh-slb-card">'
            f'<div class="chandigarh-slb-name">{it.name}</div>'
            f'<div class="chandigarh-slb-value">{it.value}</div>'
            f'{reality_html}'
            f'<div class="chandigarh-slb-def">{it.definition}</div>'
            f'<div class="chandigarh-slb-meta">{meta}</div>'
            '</div>'
        )
    st.markdown(
        f'<div class="chandigarh-slb-wrap">'
        f'<div class="chandigarh-slb-title">{title}</div>'
        f'<div class="chandigarh-slb-subtitle">{subtitle}</div>'
        f'<div class="chandigarh-slb-grid">{"".join(cards)}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def chart_evidence_caption(slb: str = "", adm: str = "", note: str = "") -> None:
    """Small "Evidences SLB-X · ADM Q-Y" caption to sit under a chart.

    Use under every primary chart on pages 1-4 to tie it back to the
    Draft Guidelines framework so a senior reviewer can tick coverage
    off without leaving the page.
    """
    bits = []
    if slb:
        bits.append(f"<b>SLB:</b> {slb}")
    if adm:
        bits.append(f"<b>ADM:</b> {adm}")
    if note:
        bits.append(note)
    if not bits:
        return
    st.markdown(
        f'<div class="chandigarh-evidence">Evidences &nbsp; '
        + " &nbsp;·&nbsp; ".join(bits) + "</div>",
        unsafe_allow_html=True,
    )


def _phci_rgb(v: float) -> tuple[int, int, int]:
    """Mirror viz._phci_to_rgb so badge colors match the map lines."""
    if v != v:  # NaN
        return (156, 163, 175)
    if v < 1.0:
        return (59, 130, 246)
    if v < 1.25:
        return (252, 211, 77)
    if v < 1.5:
        return (249, 115, 22)
    if v < 2.0:
        return (220, 38, 38)
    return (127, 29, 29)


def heatmap_color_legend() -> None:
    """The CR colour-scale legend used above the heatmap and the map."""
    chips = [
        ("&lt; 1.0 (faster)", "#3b82f6", "white"),
        ("1.0 free-flow",     "#FFFFFF", "#0F172A"),
        ("1.0–1.25",          "#fcd34d", "#0F172A"),
        ("1.25–1.5",          "#f97316", "white"),
        ("1.5–2.0",           "#dc2626", "white"),
        ("≥ 2.0",             "#7f1d1d", "white"),
    ]
    spans = "".join(
        f'<span class="chandigarh-legend-chip" style="background:{bg};color:{fg};">{label}</span>'
        for label, bg, fg in chips
    )
    st.markdown(
        f'<div class="chandigarh-legend"><span style="font-weight:600;color:#334155;">'
        f'Median Congestion Ratio:</span>{spans}</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Sidebar — global chrome on every page
# ---------------------------------------------------------------------------

def sidebar_status_pills(status_list: list[tuple[str, str, str]]) -> None:
    """Render the metric-readiness strip in the sidebar."""
    pill_class = {
        "Locked":      "chandigarh-pill-locked",
        "Preliminary": "chandigarh-pill-prelim",
        "Stable":      "chandigarh-pill-stable",
    }
    rows = []
    for label, state, _detail in status_list:
        cls = pill_class.get(state, "chandigarh-pill-locked")
        rows.append(
            f'<li class="chandigarh-status-row">'
            f'<span class="chandigarh-status-label">{label}</span>'
            f'<span class="chandigarh-status-pill {cls}">{state}</span>'
            f'</li>'
        )
    st.sidebar.markdown(
        '<div style="font-size:11px;font-weight:600;color:#64748B;'
        'text-transform:uppercase;letter-spacing:0.06em;margin:6px 0 2px 0;">'
        'Metric readiness</div>'
        f'<ul class="chandigarh-status-list">{"".join(rows)}</ul>',
        unsafe_allow_html=True,
    )


def sidebar_peak_window_control() -> None:
    """Sidebar widget — let the auditor switch the dashboard's peak window.

    Default is the UT govt office-hours band (08–11 / 17–20). The MoUD/NUTP
    Service Level Benchmark band (06–10 / 16–20) is the alternative. Switching
    re-runs every metric on the new window so a senior reviewer can verify
    the audit isn't sensitive to the band we picked.
    """
    from metrics import PEAK_PRESETS, DEFAULT_PEAK_PRESET, active_peak_hours

    st.sidebar.markdown(
        '<div style="font-size:11px;font-weight:600;color:#64748B;'
        'text-transform:uppercase;letter-spacing:0.06em;margin:14px 0 4px 0;">'
        'Peak-window definition</div>',
        unsafe_allow_html=True,
    )
    keys = list(PEAK_PRESETS.keys())
    if DEFAULT_PEAK_PRESET in keys:
        default_idx = keys.index(DEFAULT_PEAK_PRESET)
    else:
        default_idx = 0
    st.sidebar.radio(
        label="Peak-window preset",
        options=keys,
        format_func=lambda k: PEAK_PRESETS[k]["short"],
        index=default_idx,
        key="peak_preset",
        label_visibility="collapsed",
    )
    am, pm, _ = active_peak_hours()
    am_str = f"{am[0]:02d}:00–{am[-1] + 1:02d}:00"
    pm_str = f"{pm[0]:02d}:00–{pm[-1] + 1:02d}:00"
    st.sidebar.markdown(
        f'<div style="font-size:10.5px;color:#64748B;margin:-4px 0 4px 0;'
        f'line-height:1.4;">Active band · AM {am_str} · PM {pm_str} IST. '
        f'Every page recomputes on the chosen band.</div>',
        unsafe_allow_html=True,
    )


def sidebar_glossary_expander() -> None:
    """Collapsible 'How to read this dashboard' for every page."""
    with st.sidebar.expander("How to read this dashboard"):
        st.markdown(
            """
**Congestion Ratio (CR)** — live travel time ÷ free-flow travel time.
A CR of 1.50 means the trip took 50% longer than free-flow.

**PHCI** — Peak-Hour Congestion Index. Per corridor: the weekday median CR
at the peak hour and peak direction. Headline metric.

**ADCI** — All-Day Congestion Index. Mean of hourly median CRs across
06:00–22:59. Captures spread, not just peak.

**BTI** — Buffer Time Index (FHWA standard).
*(p95 − median) ÷ median* peak duration. A BTI of 0.30 means commuters
must budget 30% extra time to be on-time 95 days out of 100.

**CV** — Coefficient of Variation. σ ÷ μ of peak duration. Cross-check
on BTI; less sensitive to small samples.

**Peak windows** — set via the sidebar preset above.
Default = UT govt office hours (08–11 / 17–20).
Alternative = MoUD/NUTP SLB standard (06–10 / 16–20).

**Gating** — Locked = insufficient data; Preliminary = directional only,
quote with `n`; Stable = audit-defensible.
            """
        )


def sidebar_freshness_footer(stats) -> None:
    """Last timestamp + reproducibility hash in the sidebar footer."""
    st.sidebar.markdown(
        f'<div style="font-size:10.5px;color:#64748B;margin-top:14px;'
        f'padding-top:10px;border-top:1px solid #E2E8F0;line-height:1.5;">'
        f'<b>As of:</b> {stats.last_timestamp} IST<br>'
        f'<b>MD5:</b> <code style="font-size:10px;">{stats.observations_md5[:12]}…</code><br>'
        f'<b>Source:</b> Google Routes API v2'
        f'</div>',
        unsafe_allow_html=True,
    )


def render_sidebar(df, ranking, stats) -> None:
    """One call to render the global sidebar chrome on every page.

    Order: brand block → status pills → glossary expander → freshness footer.
    """
    from metrics import build_gating_status

    st.sidebar.markdown(
        '<div class="chandigarh-side-title">Chandigarh Mobility Audit</div>'
        '<div class="chandigarh-side-sub">Audit window · 13–26 May 2026</div>',
        unsafe_allow_html=True,
    )
    sidebar_peak_window_control()
    sidebar_status_pills(build_gating_status(df, ranking))
    sidebar_glossary_expander()
    sidebar_freshness_footer(stats)


# ---------------------------------------------------------------------------
# Page setup helper — called at top of every page
# ---------------------------------------------------------------------------

def apply_page_chrome(df, ranking, stats) -> None:
    """One-stop setup: inject CSS + render the sidebar."""
    inject_global_css()
    render_sidebar(df, ranking, stats)
