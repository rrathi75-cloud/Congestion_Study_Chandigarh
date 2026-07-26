"""
Auto-narrative module — turns the metric tables into plain-English
sentences for the Executive Summary and the per-page "so what" callouts.

Pure functions, no Streamlit imports. All findings degrade gracefully
when their underlying metric is Locked (gating thresholds in metrics.py).
"""

from __future__ import annotations

import pandas as pd

from metrics import (
    GATING, gating_state, peak_observations, weekday_observations,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bold(name: str) -> str:
    return f"<b>{name}</b>"


def _phci_state(ranking: pd.DataFrame) -> str:
    if ranking.empty:
        return "Locked"
    return gating_state(int(ranking["n_peak"].min()), "phci_weekday")


def _bti_state(bti_df: pd.DataFrame) -> str:
    if bti_df.empty:
        return "Locked"
    return gating_state(int(bti_df["n"].min()), "bti")


# ---------------------------------------------------------------------------
# Top 3 findings — Executive Summary headline narrative
# ---------------------------------------------------------------------------

def top_findings(
    df: pd.DataFrame,
    ranking: pd.DataFrame,
    asymmetry: pd.DataFrame,
    bti_df: pd.DataFrame,
    minutes_lost: pd.DataFrame,
) -> list[str]:
    """Return up to 3 plain-English HTML-formatted bullet sentences.

    Each finding checks the gating state of its source metric; if Locked,
    a generic "more findings unlock with more data" stub is emitted instead.
    """
    out: list[str] = []

    # 1) Highest-PHCI corridor
    phci_state = _phci_state(ranking)
    if phci_state == "Locked" or ranking.empty:
        out.append("Top-ranked-corridor finding will unlock once each corridor has "
                   f"≥ {GATING['phci_weekday'].min_n} weekday peak observations.")
    else:
        w = ranking.iloc[0]
        pct = (float(w["phci"]) - 1.0) * 100
        dir_pretty = {"A_to_B": "A→B", "B_to_A": "B→A"}.get(
            str(w["phci_direction"]), str(w["phci_direction"]))
        prelim = " <i>(preliminary)</i>" if phci_state == "Preliminary" else ""
        out.append(
            f"{_bold(str(w['corridor_name']))} carries the highest peak-hour "
            f"congestion in the audit set — peak-hour drivers spend "
            f"<b>{pct:+.0f}% longer</b> than free-flow time, concentrated at "
            f"<b>{int(w['phci_hour']):02d}:00</b> (direction {dir_pretty}, "
            f"PHCI {float(w['phci']):.2f}){prelim}."
        )

    # 2) Largest absolute delay (cross-checks short-vs-long corridors)
    # Only corridors that actually lose time qualify — minutes_lost can go
    # slightly negative when reroutes shorten the path during congestion.
    positive_ml = (
        minutes_lost[minutes_lost["minutes_lost"] > 0]
        if minutes_lost is not None and not minutes_lost.empty
        else None
    )
    if positive_ml is None or positive_ml.empty:
        out.append("Absolute-delay finding will unlock once peak-window data accumulates.")
    else:
        m = positive_ml.iloc[0]
        out.append(
            f"{_bold(str(m['corridor_name']))} loses <b>{float(m['minutes_lost']):.1f} minutes "
            f"per peak trip</b> ({float(m['median_traffic_min']):.1f} min vs. "
            f"{float(m['median_freeflow_min']):.1f} min free-flow) — the largest "
            f"absolute peak delay of the network."
        )

    # 3) Lowest-reliability corridor
    bti_state = _bti_state(bti_df)
    if bti_state == "Locked" or bti_df.empty:
        out.append("Reliability finding will unlock when peak-window samples reach "
                   f"≥ {GATING['bti'].min_n} per corridor.")
    else:
        b = bti_df.dropna(subset=["bti"]).iloc[0]
        bti_v = float(b["bti"])
        buffer_min = bti_v * 30  # buffer for a notional 30-min trip
        prelim = " <i>(preliminary — BTI uses p95, sensitive to small n)</i>" if bti_state == "Preliminary" else ""
        out.append(
            f"{_bold(str(b['corridor_name']))} shows the lowest trip-time "
            f"reliability (BTI {bti_v:.2f}) — a 30-min trip there must be "
            f"buffered to <b>{30 + buffer_min:.0f} minutes</b> to be on-time "
            f"95 days out of 100{prelim}."
        )

    return out


def top_findings_html(*args, **kwargs) -> str:
    """Render `top_findings(...)` as an HTML <ul> for use inside callout(...)."""
    items = top_findings(*args, **kwargs)
    if not items:
        return "Findings will appear once data accumulates."
    return "<ul>" + "".join(f"<li>{x}</li>" for x in items) + "</ul>"


# ---------------------------------------------------------------------------
# Network ranking summary — Page 1 callout
# ---------------------------------------------------------------------------

def ranking_callout(ranking: pd.DataFrame) -> str:
    if ranking.empty:
        return "Ranking unlocks once each corridor has weekday peak-hour observations."
    top3 = ranking.head(3)
    above_freeflow = ranking["phci"] - 1.0
    network_excess = above_freeflow.sum()
    top3_excess = (top3["phci"] - 1.0).sum()
    share = (top3_excess / network_excess * 100) if network_excess > 0 else 0
    names = ", ".join(_bold(n) for n in top3["corridor_name"].astype(str).tolist())
    return (
        f"Top 3 corridors — {names} — together account for "
        f"<b>{share:.0f}% of all peak-hour congestion above free-flow</b> across the network. "
        "These warrant first-priority intervention."
    )


# ---------------------------------------------------------------------------
# Heatmap pattern detection — Page 2 callout
# ---------------------------------------------------------------------------

def heatmap_patterns(df: pd.DataFrame, top_k: int = 3) -> str:
    """Identify 1–3 specific patterns in the corridor × hour grid."""
    wk = weekday_observations(df)
    if wk.empty:
        return "Patterns will surface once weekday observations accumulate."

    # Per (corridor, hour) median CR
    grid = (
        wk.groupby(["corridor_id", "corridor_name", "hour"])
        ["congestion_ratio"].median().reset_index()
    )
    grid["hour_int"] = grid["hour"].astype(int)
    findings: list[str] = []

    # Pattern A — chronic all-day congestion: CR > 1.25 over many hours.
    chronic = (
        grid[grid["hour_int"].between(8, 20) & (grid["congestion_ratio"] > 1.25)]
        .groupby(["corridor_id", "corridor_name"])
        .size().reset_index(name="hot_hours")
        .sort_values("hot_hours", ascending=False)
    )
    chronic = chronic[chronic["hot_hours"] >= 6].head(top_k)
    if not chronic.empty:
        names = ", ".join(_bold(n) for n in chronic["corridor_name"].astype(str).tolist())
        findings.append(
            f"<b>Sustained all-day congestion</b> on {names} — elevated for "
            f"six or more hours each weekday. Indicates a <i>capacity</i> "
            "constraint rather than a peak-hour signal-timing issue."
        )

    # Pattern B — two-peak directional commute: CR spikes only in 8-10 and 17-19.
    peaks_only = []
    for (cid, cname), sub in grid.groupby(["corridor_id", "corridor_name"]):
        am = sub[sub["hour_int"].isin([8, 9, 10])]["congestion_ratio"].max() or 0
        pm = sub[sub["hour_int"].isin([17, 18, 19])]["congestion_ratio"].max() or 0
        midday = sub[sub["hour_int"].isin([11, 12, 13, 14, 15])]["congestion_ratio"].max() or 0
        if am > 1.3 and pm > 1.3 and midday < 1.15:
            peaks_only.append((cid, cname, max(am, pm)))
    peaks_only.sort(key=lambda x: x[2], reverse=True)
    if peaks_only:
        names = ", ".join(_bold(c[1]) for c in peaks_only[:top_k])
        findings.append(
            f"<b>Two-peak directional pattern</b> on {names} — quiet midday with sharp "
            "AM and PM peaks. Classic commuter flow; consider one-way or contra-flow "
            "regulation rather than capacity expansion."
        )

    # Pattern C — late-evening market spread: CR > 1.2 at 20-21.
    late = (
        grid[grid["hour_int"].isin([20, 21]) & (grid["congestion_ratio"] > 1.2)]
        .groupby(["corridor_id", "corridor_name"])
        ["congestion_ratio"].max().reset_index()
        .sort_values("congestion_ratio", ascending=False)
        .head(top_k)
    )
    if not late.empty:
        names = ", ".join(_bold(n) for n in late["corridor_name"].astype(str).tolist())
        findings.append(
            f"<b>Late-evening congestion</b> persists on {names} after 20:00 — "
            "likely after-office market traffic; merits an evening enforcement window."
        )

    if not findings:
        return ("No strong network-wide patterns yet. Read individual rows: "
                "wide red bands indicate sustained congestion; narrow AM/PM red "
                "blocks indicate directional commuter flow.")
    return "<ul>" + "".join(f"<li>{f}</li>" for f in findings) + "</ul>"


# ---------------------------------------------------------------------------
# Direction-asymmetry implication — Page 3 callout
# ---------------------------------------------------------------------------

def asymmetry_implication(asymmetry: pd.DataFrame) -> str:
    if asymmetry.empty:
        return "Direction asymmetry unlocks with more peak-window data per direction."
    sub = asymmetry.dropna(subset=["asymmetry_pct"]).copy()
    if sub.empty:
        return "Asymmetry not yet computable for any corridor."
    sub = sub.sort_values("asymmetry_pct", ascending=False).head(3)
    items = []
    for _, r in sub.iterrows():
        a2b = r.get("median_cr_A_to_B", float("nan"))
        b2a = r.get("median_cr_B_to_A", float("nan"))
        worse = "A→B" if (a2b or 0) > (b2a or 0) else "B→A"
        items.append(
            f"<li>{_bold(str(r['corridor_name']))} — <b>{r['asymmetry_pct']:.0f}%</b> "
            f"asymmetry in {r['peak']}, worse in {worse}.</li>"
        )
    return (
        "Highest direction asymmetries:<ul>" + "".join(items) + "</ul>"
        "<b>Policy lens:</b> high asymmetry → directional intervention "
        "(one-way rule, contra-flow, time-of-day signal bias). Low asymmetry "
        "with high PHCI → uniform congestion → capacity issue."
    )


# ---------------------------------------------------------------------------
# Reliability translation — Page 4 callout
# ---------------------------------------------------------------------------

def reliability_translation(bti_df: pd.DataFrame) -> str:
    if bti_df is None or bti_df.empty:
        return "Reliability unlocks once peak-window observations accumulate."
    sub = bti_df.dropna(subset=["bti"]).sort_values("bti", ascending=False).head(3)
    if sub.empty:
        return "BTI not yet computable."
    items = []
    _DIR = {"A_to_B": "A→B", "B_to_A": "B→A"}
    for _, r in sub.iterrows():
        bti_v = float(r["bti"])
        buf = bti_v * 30
        dir_pretty = _DIR.get(str(r["direction"]), str(r["direction"]))
        items.append(
            f"<li>{_bold(str(r['corridor_name']))} ({dir_pretty}) — "
            f"BTI <b>{bti_v:.2f}</b>: a 30-min trip must be buffered to "
            f"<b>{30 + buf:.0f} min</b> to arrive on-time 95% of days.</li>"
        )
    return (
        "Lowest-reliability corridors (BTI = extra time as a % of median):"
        + "<ul>" + "".join(items) + "</ul>"
        "<b>So what:</b> reliability matters as much as average speed. A corridor "
        "with PHCI 1.4 and BTI 0.5 imposes a larger planning cost on commuters "
        "than one with PHCI 1.6 and BTI 0.2 — predictability lets people plan."
    )


# ---------------------------------------------------------------------------
# Map narrative — Page 5 callout
# ---------------------------------------------------------------------------

def map_narrative(ranking: pd.DataFrame, top_n: int = 3) -> str:
    if ranking.empty:
        return "Map narrative unlocks with more peak-window data."
    top = ranking.head(top_n)
    items = []
    for _, r in top.iterrows():
        items.append(
            f"<li><b>★ Rank {int(r['rank'])} — {r['corridor_name']}</b> "
            f"(PHCI {float(r['phci']):.2f}, peaks at {int(r['phci_hour']):02d}:00)</li>"
        )
    return (
        "The thickest, most-saturated lines on this map are the priority corridors:"
        + "<ul>" + "".join(items) + "</ul>"
        "Hover any line for full statistics. Faded lines are the remaining "
        f"{38 - top_n} corridors, drawn for geographic context."
    )
