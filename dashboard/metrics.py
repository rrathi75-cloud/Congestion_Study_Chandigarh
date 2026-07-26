"""
Congestion metrics for the chandigarh Mobility audit dashboard.

All formulas live here. The dashboard pages, the Excel exporter, and the
Methodology page render their numbers from these functions — single source
of truth across every output.

Hard-coded peak windows (08:00-11:00 AM, 17:00-20:00 PM IST) are deliberate.
Data-driven peak detection is unstable on 2-14 days of data and invites the
"you fit the window to make the numbers look bad" objection. Anchor to
govt office hours and the National Urban Transport Policy convention.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Peak-window definition (overridable from sidebar, but ships with policy default)
# ---------------------------------------------------------------------------

AM_PEAK_HOURS = (8, 9, 10)
PM_PEAK_HOURS = (17, 18, 19)
PEAK_HOURS = AM_PEAK_HOURS + PM_PEAK_HOURS
ACTIVE_HOURS = tuple(range(6, 23))  # 06:00-22:59 IST; matches latex h ∈ [6, 22] and the hourly-heatmap default.

# MoUD / NUTP Service Level Benchmark peak window (06-10 AM, 04-08 PM weekdays).
# The SLB-indicator strip on the Executive Summary is locked to this window
# regardless of the user-selected preset — these indicators are defined on the
# MoUD band by name, so they don't change as the auditor toggles the dashboard.
MOUD_AM_PEAK_HOURS = (6, 7, 8, 9)
MOUD_PM_PEAK_HOURS = (16, 17, 18, 19)
MOUD_PEAK_HOURS = MOUD_AM_PEAK_HOURS + MOUD_PM_PEAK_HOURS

# Sidebar-selectable peak-window presets. The user-facing override lets a
# senior reviewer reproduce every page under the MoUD/NUTP window without
# editing code; the default is the Bihar govt office-hours band the rest of
# the methodology page anchors to.
PEAK_PRESETS = {
    "UT_govt": {
        "label": "UT govt office hours",
        "short": "UT govt (08–11 / 17–20)",
        "long": "08:00–11:00 AM, 17:00–20:00 PM IST — National Urban Transport "
                "Policy convention, anchored to Chandigarh UT govt office hours.",
        "am": AM_PEAK_HOURS,
        "pm": PM_PEAK_HOURS,
    },
    "moud_nutp": {
        "label": "MoUD / NUTP SLB standard",
        "short": "MoUD/NUTP (06–10 / 16–20)",
        "long": "06:00–10:00 AM, 16:00–20:00 PM IST — the peak band the "
                "Ministry of Urban Development / NUTP Service Level Benchmarks specify.",
        "am": MOUD_AM_PEAK_HOURS,
        "pm": MOUD_PM_PEAK_HOURS,
    },
}
DEFAULT_PEAK_PRESET = "UT_govt"


def active_peak_preset() -> str:
    """Return the active peak-window preset key (from Streamlit session state).

    Defaults to UT_govt when no session state is present (e.g. Excel export
    run outside the dashboard process). Safe to call from non-Streamlit code.
    """
    try:
        import streamlit as st  # local import: keeps metrics.py importable from CLI
        return st.session_state.get("peak_preset", DEFAULT_PEAK_PRESET)
    except Exception:
        return DEFAULT_PEAK_PRESET


def active_peak_hours() -> tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]]:
    """Return (am_hours, pm_hours, peak_hours) for the active preset."""
    preset = PEAK_PRESETS.get(active_peak_preset(), PEAK_PRESETS[DEFAULT_PEAK_PRESET])
    am = tuple(preset["am"])
    pm = tuple(preset["pm"])
    return am, pm, am + pm


# ---------------------------------------------------------------------------
# Gating thresholds — n-based sufficiency for each metric
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Threshold:
    min_n: int
    stable_n: int
    label: str


GATING = {
    "phci_weekday": Threshold(min_n=30, stable_n=100,
                              label="weekday peak-hour observations per corridor"),
    "phci_weekend": Threshold(min_n=20, stable_n=60,
                              label="weekend peak-hour observations per corridor"),
    "heatmap_cell_weekday": Threshold(min_n=1, stable_n=4,
                                      label="observations per (corridor, hour, weekday) cell"),
    "heatmap_weekend": Threshold(min_n=1, stable_n=2,
                                 label="weekend days of data"),
    "direction_asymmetry": Threshold(min_n=10, stable_n=30,
                                     label="observations per direction in the peak window"),
    "bti": Threshold(min_n=15, stable_n=40,
                     label="peak-window observations per corridor for BTI"),
    "cv":  Threshold(min_n=10, stable_n=30,
                     label="peak-window observations per corridor for CV"),
}


def gating_state(n: int, key: str) -> str:
    """Return one of 'Locked', 'Preliminary', 'Stable' for the given n."""
    t = GATING[key]
    if n < t.min_n:
        return "Locked"
    if n < t.stable_n:
        return "Preliminary"
    return "Stable"


# Short corridors where ratio is sensitive to signal-cycle noise.
SHORT_CORRIDOR_IDS = {"1", "4", "10", "17", "21", "23"}


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------

def weekday_observations(df: pd.DataFrame, include_holidays: bool = False) -> pd.DataFrame:
    out = df[df["weekday_or_weekend"] == "Weekday"]
    if not include_holidays:
        out = out[~out["is_chandigarh_holiday"]]
    return out


def weekend_observations(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["weekday_or_weekend"] == "Weekend"]


def peak_observations(df: pd.DataFrame) -> pd.DataFrame:
    _, _, peak = active_peak_hours()
    return df[df["hour"].astype(int).isin(peak)]


def am_peak_observations(df: pd.DataFrame) -> pd.DataFrame:
    am, _, _ = active_peak_hours()
    return df[df["hour"].astype(int).isin(am)]


def pm_peak_observations(df: pd.DataFrame) -> pd.DataFrame:
    _, pm, _ = active_peak_hours()
    return df[df["hour"].astype(int).isin(pm)]


# ---------------------------------------------------------------------------
# Core metrics
# ---------------------------------------------------------------------------

def hourly_median_cr(df: pd.DataFrame) -> pd.DataFrame:
    """Median congestion ratio per (corridor_id, direction, hour, weekday_or_weekend).

    Also returns the observation count n for each cell.
    """
    grouped = (
        df.groupby(["corridor_id", "corridor_name", "direction", "hour", "weekday_or_weekend"])
        .agg(
            median_cr=("congestion_ratio", "median"),
            n=("congestion_ratio", "size"),
        )
        .reset_index()
    )
    return grouped


def phci(df: pd.DataFrame) -> pd.DataFrame:
    """Peak-Hour Congestion Index per corridor.

    For each corridor, take the max over the peak hours of the per-(direction, hour)
    weekday median congestion ratio. Both directions are aggregated by taking the
    max — represents the peak-hour high in the peak direction.
    """
    wk = weekday_observations(df)
    wk_peak = peak_observations(wk)

    if wk_peak.empty:
        return pd.DataFrame(
            columns=["corridor_id", "corridor_name", "phci", "phci_hour",
                     "phci_direction", "n_peak"]
        )

    cell = (
        wk_peak.groupby(["corridor_id", "corridor_name", "direction", "hour"])
        .agg(median_cr=("congestion_ratio", "median"),
             n=("congestion_ratio", "size"))
        .reset_index()
    )
    idx = cell.groupby(["corridor_id", "corridor_name"])["median_cr"].idxmax()
    worst = cell.loc[idx].reset_index(drop=True)

    n_per_corridor = (
        wk_peak.groupby("corridor_id").size().rename("n_peak").reset_index()
    )

    out = worst.merge(n_per_corridor, on="corridor_id", how="left").rename(
        columns={"median_cr": "phci", "hour": "phci_hour", "direction": "phci_direction"}
    )
    return out[["corridor_id", "corridor_name", "phci", "phci_hour",
                "phci_direction", "n_peak"]].sort_values("phci", ascending=False)


def adci(df: pd.DataFrame) -> pd.DataFrame:
    """All-Day Congestion Index — mean over active hours (06-22 IST) of the hourly median CR."""
    wk = weekday_observations(df)
    active = wk[wk["hour"].astype(int).isin(ACTIVE_HOURS)]
    if active.empty:
        return pd.DataFrame(columns=["corridor_id", "corridor_name", "adci", "n_active"])

    hourly = (
        active.groupby(["corridor_id", "corridor_name", "hour"])
        .agg(median_cr=("congestion_ratio", "median"))
        .reset_index()
    )
    out = (
        hourly.groupby(["corridor_id", "corridor_name"])
        .agg(adci=("median_cr", "mean"))
        .reset_index()
    )
    n_active = active.groupby("corridor_id").size().rename("n_active").reset_index()
    out = out.merge(n_active, on="corridor_id", how="left")
    return out.sort_values("adci", ascending=False)


def bti(df: pd.DataFrame) -> pd.DataFrame:
    """Buffer Time Index per corridor, direction (FHWA standard).

    BTI = (p95(duration_traffic_s) - median(duration_traffic_s)) / median(...)
    Computed over the peak window only. Higher = less reliable commute.
    """
    wk_peak = peak_observations(weekday_observations(df))

    def _agg(g: pd.DataFrame) -> pd.Series:
        n = len(g)
        med = g["duration_traffic_s"].median()
        p95 = g["duration_traffic_s"].quantile(0.95)
        bti_val = (p95 - med) / med if med and med > 0 else np.nan
        return pd.Series(
            {
                "median_peak_s": med,
                "p95_peak_s": p95,
                "bti": bti_val,
                "n": n,
            }
        )

    if wk_peak.empty:
        return pd.DataFrame(columns=["corridor_id", "corridor_name", "direction",
                                     "median_peak_s", "p95_peak_s", "bti", "n"])

    grouped = (
        wk_peak.groupby(["corridor_id", "corridor_name", "direction"])
        .apply(_agg, include_groups=False)
        .reset_index()
    )
    return grouped.sort_values("bti", ascending=False)


def cv(df: pd.DataFrame) -> pd.DataFrame:
    """Coefficient of variation of peak-window traffic duration per corridor, direction."""
    wk_peak = peak_observations(weekday_observations(df))

    def _agg(g: pd.DataFrame) -> pd.Series:
        n = len(g)
        mu = g["duration_traffic_s"].mean()
        sigma = g["duration_traffic_s"].std(ddof=1) if n > 1 else 0.0
        cv_val = sigma / mu if mu and mu > 0 else np.nan
        return pd.Series({"mu_peak_s": mu, "sigma_peak_s": sigma, "cv": cv_val, "n": n})

    if wk_peak.empty:
        return pd.DataFrame(columns=["corridor_id", "corridor_name", "direction",
                                     "mu_peak_s", "sigma_peak_s", "cv", "n"])

    grouped = (
        wk_peak.groupby(["corridor_id", "corridor_name", "direction"])
        .apply(_agg, include_groups=False)
        .reset_index()
    )
    return grouped.sort_values("cv", ascending=False)


def direction_asymmetry(df: pd.DataFrame) -> pd.DataFrame:
    """AM and PM peak median CR per direction, with asymmetry %.

    asymmetry_pct = |CR_A_to_B - CR_B_to_A| / max(CR_A_to_B, CR_B_to_A) * 100
    """
    wk = weekday_observations(df)

    def _peak_table(sub: pd.DataFrame, label: str) -> pd.DataFrame:
        agg = (
            sub.groupby(["corridor_id", "corridor_name", "direction"])
            .agg(median_cr=("congestion_ratio", "median"),
                 n=("congestion_ratio", "size"))
            .reset_index()
        )
        wide = agg.pivot_table(
            index=["corridor_id", "corridor_name"],
            columns="direction",
            values=["median_cr", "n"],
            aggfunc="first",
        )
        wide.columns = [f"{a}_{b}" for a, b in wide.columns]
        wide = wide.reset_index()
        for col in ("median_cr_A_to_B", "median_cr_B_to_A", "n_A_to_B", "n_B_to_A"):
            if col not in wide.columns:
                wide[col] = np.nan
        denom = wide[["median_cr_A_to_B", "median_cr_B_to_A"]].max(axis=1)
        diff = (wide["median_cr_A_to_B"] - wide["median_cr_B_to_A"]).abs()
        wide["asymmetry_pct"] = (100.0 * diff / denom).round(2)
        wide["peak"] = label
        return wide

    am = _peak_table(am_peak_observations(wk), "AM Peak")
    pm = _peak_table(pm_peak_observations(wk), "PM Peak")
    return pd.concat([am, pm], ignore_index=True)


def ranking_table(df: pd.DataFrame) -> pd.DataFrame:
    """The headline ranking table used on page 1 and the Excel Ranking sheet."""
    p = phci(df)
    a = adci(df)[["corridor_id", "adci", "n_active"]]

    # For BTI / CV we surface the worst-direction value per corridor. Earlier
    # this paired the max with sum(n) across both directions, which made the
    # exposed sample size look twice as large as the value it supports. Pick
    # the row that owns the max and report its n directly.
    bti_per_corr = bti(df)
    b_idx = bti_per_corr.groupby("corridor_id")["bti"].idxmax()
    b = bti_per_corr.loc[b_idx, ["corridor_id", "bti", "n"]].rename(columns={"n": "n_bti"})

    cv_per_corr = cv(df)
    c_idx = cv_per_corr.groupby("corridor_id")["cv"].idxmax()
    c = cv_per_corr.loc[c_idx, ["corridor_id", "cv", "n"]].rename(columns={"n": "n_cv"})

    out = (
        p.merge(a, on="corridor_id", how="left")
        .merge(b, on="corridor_id", how="left")
        .merge(c, on="corridor_id", how="left")
    )
    out["is_short_corridor"] = out["corridor_id"].isin(SHORT_CORRIDOR_IDS)
    out = out.sort_values("phci", ascending=False).reset_index(drop=True)
    out.insert(0, "rank", out.index + 1)
    return out


def build_gating_status(df: pd.DataFrame, ranking: pd.DataFrame) -> list[tuple[str, str, str]]:
    """Return (label, state, detail) tuples for the global feature-gating strip.

    Used by the sidebar status pills and by the Executive Summary footer to give
    one consistent picture of which metrics are Locked / Preliminary / Stable.
    """
    out: list[tuple[str, str, str]] = []

    if ranking.empty:
        out.append(("Ranking", "Locked", "Awaiting first batches"))
    else:
        min_n_peak = int(ranking["n_peak"].min())
        state = gating_state(min_n_peak, "phci_weekday")
        out.append(("Weekday PHCI", state,
                    f"min n={min_n_peak} per corridor; need ≥ {GATING['phci_weekday'].stable_n} for Stable"))

    wkend = weekend_observations(df)
    wkend_days = wkend["date"].nunique() if not wkend.empty else 0
    if wkend_days == 0:
        out.append(("Weekend heatmap", "Locked", "Awaiting first weekend day in window"))
    elif wkend_days == 1:
        out.append(("Weekend heatmap", "Preliminary", "1 weekend day in; second arrives next weekend day"))
    else:
        out.append(("Weekend heatmap", "Stable", f"{wkend_days} weekend days"))

    wk_peak = peak_observations(weekday_observations(df))
    if wk_peak.empty:
        out.append(("BTI / Reliability", "Locked", "Awaiting peak-window observations"))
    else:
        per_corridor = wk_peak.groupby("corridor_id").size()
        min_n = int(per_corridor.min())
        state = gating_state(min_n, "bti")
        out.append(("BTI / Reliability", state,
                    f"min n={min_n}; need ≥ {GATING['bti'].stable_n} for Stable"))

    if not wk_peak.empty:
        am = wk_peak[wk_peak["hour"].astype(int).isin([8, 9, 10])]
        n_am = int(am.groupby(["corridor_id", "direction"]).size().min()) if not am.empty else 0
        state = gating_state(n_am, "direction_asymmetry")
        out.append(("Direction asymmetry", state,
                    f"min n={n_am} per direction in AM peak"))
    else:
        out.append(("Direction asymmetry", "Locked", "Awaiting peak-window data"))

    return out


def slb_indicators(df: pd.DataFrame, threshold_cr: float = 1.5) -> dict:
    """Compute the three MoUD/NUTP Service Level Benchmark indicators.

    SLB-1 Traffic Congestion at peak — network-wide weekday peak median CR,
          using the MoUD 06-10 / 16-20 window (not our internal 08-11 / 17-20).
    SLB-2 Time Delay in Traffic — median additional travel time per km in the
          MoUD peak window, taken across the corridors.
    SLB-3 % Congested Roads — share of monitored corridors whose peak-window
          median CR is at or above `threshold_cr` (default 1.5×).

    Returns a dict keyed by short name, each value carrying value / detail /
    gating state / sample-size info.
    """
    wk = weekday_observations(df)
    moud_peak = wk[wk["hour"].astype(int).isin(MOUD_PEAK_HOURS)]

    n_corridors_total = int(df["corridor_id"].nunique()) if not df.empty else 0

    out: dict = {}

    if moud_peak.empty:
        for k in ("traffic_congestion_at_peak", "time_delay_in_traffic", "pct_congested_roads"):
            out[k] = {"state": "Locked", "n": 0}
        out["n_corridors_total"] = n_corridors_total
        return out

    n_per_corr_min = int(moud_peak.groupby("corridor_id").size().min())
    state = gating_state(n_per_corr_min, "phci_weekday")

    # --- Peak-of-peak reality (per-corridor worst hour, within MoUD window) -
    # The framework values below take medians across 8 hours × all corridors,
    # which structurally dilutes individual corridors' peak-hour congestion.
    # These per-(corridor, hour) cell aggregates surface what residents actually
    # experience at the worst corridor in its own peak hour.
    cell = (
        moud_peak.groupby(["corridor_id", "corridor_name", "hour"])
        .agg(
            median_cr=("congestion_ratio", "median"),
            median_traffic_s=("duration_traffic_s", "median"),
            median_freeflow_s=("duration_freeflow_s", "median"),
            est_distance_km=("est_distance_km", "first"),
        )
        .reset_index()
    )
    if cell.empty:
        peak_cr_max = float("nan"); peak_cr_corr = ""; peak_cr_hour = -1
        peak_delay_max = float("nan"); peak_delay_corr = ""
        n_corr_peak_ge_threshold = 0
        n_corr_peak_ge_soft = 0
    else:
        idx = cell.groupby("corridor_id")["median_cr"].idxmax()
        corr_peak = cell.loc[idx].reset_index(drop=True)
        # SLB-3 reality (threshold counts include every monitored corridor — the
        # whole-population count is robust to any individual corridor's noise).
        n_corr_peak_ge_threshold = int((corr_peak["median_cr"] >= threshold_cr).sum())
        n_corr_peak_ge_soft = int((corr_peak["median_cr"] >= 1.25).sum())
        # SLB-1/2 single-worst-corridor picks exclude short corridors flagged as
        # signal-cycle-noisy elsewhere in the methodology — keeps the named
        # exemplar defensible rather than pinned to a 1-km outlier.
        stable = corr_peak[~corr_peak["corridor_id"].astype(str).isin(SHORT_CORRIDOR_IDS)]
        if not stable.empty:
            top_row = stable.sort_values("median_cr", ascending=False).iloc[0]
            peak_cr_max = float(top_row["median_cr"])
            peak_cr_corr = str(top_row["corridor_name"])
            peak_cr_hour = int(top_row["hour"])
        else:
            peak_cr_max = float("nan"); peak_cr_corr = ""; peak_cr_hour = -1
        corr_peak_delay = stable.dropna(subset=["est_distance_km"]).copy()
        corr_peak_delay["delay_min_per_km"] = (
            (corr_peak_delay["median_traffic_s"] - corr_peak_delay["median_freeflow_s"]) / 60.0
            / corr_peak_delay["est_distance_km"].replace(0, np.nan)
        )
        if not corr_peak_delay.empty:
            delay_top = corr_peak_delay.sort_values("delay_min_per_km", ascending=False).iloc[0]
            peak_delay_max = float(delay_top["delay_min_per_km"])
            peak_delay_corr = str(delay_top["corridor_name"])
        else:
            peak_delay_max = float("nan"); peak_delay_corr = ""

    # --- SLB-1 Traffic Congestion at peak -----------------------------------
    median_cr_network = float(moud_peak["congestion_ratio"].median())
    out["traffic_congestion_at_peak"] = {
        "median_cr": median_cr_network,
        "pct_over_freeflow": (median_cr_network - 1.0) * 100.0,
        "peak_hour_max_cr": peak_cr_max,
        "peak_hour_max_pct_over_freeflow": (peak_cr_max - 1.0) * 100.0 if peak_cr_max == peak_cr_max else float("nan"),
        "peak_hour_max_corridor": peak_cr_corr,
        "peak_hour_max_hour": peak_cr_hour,
        "n_obs": int(len(moud_peak)),
        "n_per_corr_min": n_per_corr_min,
        "state": state,
    }

    # --- SLB-2 Time Delay in Traffic ----------------------------------------
    per_corr = (
        moud_peak.dropna(subset=["est_distance_km"])
        .groupby("corridor_id")
        .agg(
            median_traffic_s=("duration_traffic_s", "median"),
            median_freeflow_s=("duration_freeflow_s", "median"),
            est_distance_km=("est_distance_km", "first"),
        )
    )
    per_corr["delay_min_per_km"] = (
        (per_corr["median_traffic_s"] - per_corr["median_freeflow_s"])
        / 60.0
        / per_corr["est_distance_km"].replace(0, np.nan)
    )
    median_delay_per_km = float(per_corr["delay_min_per_km"].median()) if not per_corr.empty else np.nan
    p95_delay_per_km = float(per_corr["delay_min_per_km"].quantile(0.95)) if not per_corr.empty else np.nan
    out["time_delay_in_traffic"] = {
        "median_min_per_km": median_delay_per_km,
        "p95_min_per_km": p95_delay_per_km,
        "peak_hour_max_min_per_km": peak_delay_max,
        "peak_hour_max_corridor": peak_delay_corr,
        "n_obs": int(len(moud_peak)),
        "n_per_corr_min": n_per_corr_min,
        "state": state,
    }

    # --- SLB-3 % Congested Roads --------------------------------------------
    per_corr_cr = moud_peak.groupby(["corridor_id", "corridor_name"])["congestion_ratio"].median()
    n_corr = int(per_corr_cr.shape[0])
    n_congested = int((per_corr_cr >= threshold_cr).sum())
    pct = round(100.0 * n_congested / n_corr, 1) if n_corr else 0.0
    pct_peak = round(100.0 * n_corr_peak_ge_threshold / n_corr, 1) if n_corr else 0.0
    pct_peak_soft = round(100.0 * n_corr_peak_ge_soft / n_corr, 1) if n_corr else 0.0
    out["pct_congested_roads"] = {
        "n_congested": n_congested,
        "n_corridors": n_corr,
        "pct": pct,
        "threshold_cr": threshold_cr,
        # Peak-hour reality: counts of corridors that cross the threshold at
        # their own peak hour rather than via the diluted 8-hour median.
        "n_peak_hour_above_threshold": n_corr_peak_ge_threshold,
        "pct_peak_hour_above_threshold": pct_peak,
        "n_peak_hour_above_soft": n_corr_peak_ge_soft,
        "pct_peak_hour_above_soft": pct_peak_soft,
        "soft_threshold_cr": 1.25,
        "n_per_corr_min": n_per_corr_min,
        "state": state,
    }

    out["n_corridors_total"] = n_corridors_total
    return out


def minutes_lost_table(df: pd.DataFrame) -> pd.DataFrame:
    """Secondary ranking by absolute minutes lost in peak (cross-context for short corridors)."""
    wk_peak = peak_observations(weekday_observations(df))
    out = (
        wk_peak.groupby(["corridor_id", "corridor_name"])
        .agg(
            median_traffic_min=("duration_traffic_s", lambda s: s.median() / 60.0),
            median_freeflow_min=("duration_freeflow_s", lambda s: s.median() / 60.0),
            n=("congestion_ratio", "size"),
        )
        .reset_index()
    )
    out["minutes_lost"] = (out["median_traffic_min"] - out["median_freeflow_min"]).round(2)
    out["median_traffic_min"] = out["median_traffic_min"].round(2)
    out["median_freeflow_min"] = out["median_freeflow_min"].round(2)
    return out.sort_values("minutes_lost", ascending=False).reset_index(drop=True)
