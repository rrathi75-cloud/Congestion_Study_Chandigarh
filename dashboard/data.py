"""
Data loader for the  Mobility Congestion Index dashboard. 

Single entry point: load_observations() returns a clean, deduped, OK-only
DataFrame joined to corridor geometry. data_quality_report() returns the
stats needed by the Methodology & Data Quality page.

Design rules (do not change without good reason):
  * Timestamps in the CSVs are IST clock-time. Treat them as tz-naive. Never
    call tz_localize on this column — the source is already IST.
  * api_status == "OK" filter removes the 56 bootstrap FAIL rows from
    2026-05-12 20:47 (one-shot "Timestamp must be future" bug from the
    original 28-corridor set, since fixed).
    Those FAILs are surfaced separately via data_quality_report() so the
    Methodology page can show them transparently.
  * Dedupe on (timestamp_ist, corridor_id, direction) keeping `last` —
    travel_log_*.csv snapshots overlap with each other and with the live
    travel_log.csv. Latest write wins.
  * corridor_id is mixed string/int (e.g. "9A", "11B", "5"). Always read
    as str so the join with corridors.csv doesn't silently drop "9A".
"""

from __future__ import annotations

import glob
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import streamlit as st

PROJECT_DIR = Path(__file__).resolve().parent.parent
CORRIDORS_FILE = PROJECT_DIR / "corridors.csv"
HOLIDAYS_FILE = PROJECT_DIR / "holidays_chandigarh.csv"

AUDIT_WINDOW_START = pd.Timestamp("2026-05-13")
AUDIT_WINDOW_END = pd.Timestamp("2026-05-26")

EXPECTED_BATCHES_PER_DAY = 48  # cron every 30 min
# OD-pair count expanded mid-window: 50 pairs (25 corridors × 2 directions)
# from 2026-07-27 through 2026-08-11 15:00 IST; 
# Constant below reflects the
# post-expansion steady state — use it as a reference only.
EXPECTED_RECORDS_PER_DAY = EXPECTED_BATCHES_PER_DAY * 50


def data_signature() -> str:
    """Hashable token that changes when any travel_log CSV changes.

    Every page passes this string as the cache key for load_observations() and
    data_quality_report(). When the collector writes a new batch (or a new
    daily CSV lands), the mtime/size of one of the files changes, the
    signature changes, and Streamlit's @st.cache_data invalidates on the
    spot — without waiting for the TTL to expire. Keeps the dashboard live
    against the cron-driven data flow.

    Cheap: stat is O(file count), no file reads.
    """
    paths = sorted(glob.glob(str(PROJECT_DIR / "travel_log_*.csv")))
    bare = PROJECT_DIR / "travel_log.csv"
    if bare.exists():
        paths.append(str(bare))
    corridors = CORRIDORS_FILE
    if corridors.exists():
        paths.append(str(corridors))
    holidays = HOLIDAYS_FILE
    if holidays.exists():
        paths.append(str(holidays))
    parts = []
    for p in paths:
        try:
            s = os.stat(p)
            parts.append(f"{p}:{s.st_mtime_ns}:{s.st_size}")
        except FileNotFoundError:
            continue
    return hashlib.md5("|".join(parts).encode("utf-8")).hexdigest()


def _read_one_log(path: Path) -> pd.DataFrame:
    return pd.read_csv(
        path,
        dtype={"corridor_id": str, "direction": str, "api_status": str},
        keep_default_na=True,
    )


def _read_all_logs() -> pd.DataFrame:
    paths = sorted(glob.glob(str(PROJECT_DIR / "travel_log_*.csv")))
    bare = PROJECT_DIR / "travel_log.csv"
    if bare.exists():
        paths.append(str(bare))
    if not paths:
        raise FileNotFoundError(
            f"No travel_log_*.csv files found in {PROJECT_DIR}"
        )
    frames = [_read_one_log(Path(p)) for p in paths]
    return pd.concat(frames, ignore_index=True)


def _read_corridors() -> pd.DataFrame:
    df = pd.read_csv(CORRIDORS_FILE, dtype={"corridor_id": str, "direction": str})
    return df


def _read_holidays() -> pd.DataFrame:
    if not HOLIDAYS_FILE.exists():
        return pd.DataFrame(columns=["date", "name", "impact", "exclude_from_weekday_default"])
    df = pd.read_csv(HOLIDAYS_FILE)
    df["date"] = pd.to_datetime(df["date"]).dt.date.astype(str)
    return df


def _classify_peak(hour: int) -> str:
    if 8 <= hour < 11:
        return "AM Peak"
    if 17 <= hour < 20:
        return "PM Peak"
    if 6 <= hour < 22:
        return "Off-Peak"
    return "Night"


def load_observations() -> pd.DataFrame:
    """Return the clean OK-only observation dataframe used by every page.

    Columns include all 15 from the raw CSV plus:
      * timestamp_ist parsed as tz-naive datetime
      * weekday_or_weekend ("Weekday" / "Weekend")
      * peak_label ("AM Peak" / "PM Peak" / "Off-Peak" / "Night")
      * is_chandigarh_holiday (bool)
      * origin_lat, origin_lng, dest_lat, dest_lng, est_distance_km
        (joined from corridors.csv on (corridor_id, direction))
    """
    raw = _read_all_logs()

    raw = raw.drop_duplicates(
        subset=["timestamp_ist", "corridor_id", "direction"], keep="last"
    )

    # Coerce numeric columns (CSV may store them as strings when a row failed).
    for col in ("distance_m", "duration_traffic_s", "duration_freeflow_s", "congestion_ratio"):
        raw[col] = pd.to_numeric(raw[col], errors="coerce")

    df = raw[
        (raw["api_status"] == "OK")
        & raw["duration_freeflow_s"].gt(0)
        & raw["congestion_ratio"].notna()
    ].copy()

    df["timestamp_ist"] = pd.to_datetime(df["timestamp_ist"])
    df["date"] = pd.to_datetime(df["date"]).dt.date.astype(str)

    # Restrict to the audit window. The collector emits a one-shot bootstrap
    # batch on 2026-07-26 (one day before the window opens) and may continue
    # past 2026-08-11 if cron isn't stopped; neither belongs in the published
    # numbers. Keeping these would pollute PHCI/ADCI hour-20 medians and would
    # contradict the audit-window dates printed on every page header.
    window_start = AUDIT_WINDOW_START.date().isoformat()
    window_end = AUDIT_WINDOW_END.date().isoformat()
    df = df[df["date"].between(window_start, window_end)].copy()

    df["weekday_or_weekend"] = df["is_weekend"].map({"Y": "Weekend", "N": "Weekday"})
    df["peak_label"] = df["hour"].astype(int).map(_classify_peak)

    holidays = _read_holidays()
    holiday_dates = set(holidays["date"]) if not holidays.empty else set()
    df["is_chandigarh_holiday"] = df["date"].isin(holiday_dates)

    corridors = _read_corridors()
    df = df.merge(
        corridors[
            [
                "corridor_id",
                "direction",
                "origin_lat",
                "origin_lng",
                "dest_lat",
                "dest_lng",
                "est_distance_km",
            ]
        ],
        on=["corridor_id", "direction"],
        how="left",
    )

    return df.reset_index(drop=True)


def load_fail_rows() -> pd.DataFrame:
    """The FAIL rows, separately, for the Methodology page's transparency log.

    Restricted to the audit window — the bootstrap 2026-05-12 FAILs from the
    one-shot 'Timestamp must be future' bug are excluded because they
    pre-date the audit and are not part of the published evidence base.
    """
    raw = _read_all_logs()
    raw = raw.drop_duplicates(
        subset=["timestamp_ist", "corridor_id", "direction"], keep="last"
    )
    fails = raw[raw["api_status"] == "FAIL"].copy()
    fails["date"] = pd.to_datetime(fails["date"]).dt.date.astype(str)
    window_start = AUDIT_WINDOW_START.date().isoformat()
    window_end = AUDIT_WINDOW_END.date().isoformat()
    fails = fails[fails["date"].between(window_start, window_end)]
    return fails.reset_index(drop=True)


@dataclass(frozen=True)
class CoverageStats:
    total_observations: int
    fail_count: int
    fail_pct: float
    first_timestamp: str
    last_timestamp: str
    days_covered: int
    corridors_covered: int
    observations_md5: str
    corridors_md5: str


def _md5(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def data_quality_report(df: pd.DataFrame | None = None) -> dict:
    """Return the structured dict consumed by the Methodology page.

    Keys:
      stats        : CoverageStats dataclass with headline numbers.
      coverage     : DataFrame indexed by corridor_id, columns = dates,
                     values = observation count (long-form is also fine).
      fail_log     : Full FAIL-rows dataframe (one row per failed call).
      fail_summary : DataFrame of FAIL counts grouped by error pattern.
      distance_drift: DataFrame: corridor_id, direction, distinct distances,
                      min/max/median distance, delta_m, delta_pct_of_est,
                      pct_rows_outside_modal_5pct, reroute_flag,
                      high_path_variability_flag.
      cr_distribution: pd.Series of all CR values (for CDF plotting).
    """
    obs = df if df is not None else load_observations()
    fails = load_fail_rows()

    total = len(obs)
    fail_n = len(fails)
    fail_pct = round(100.0 * fail_n / (total + fail_n), 3) if (total + fail_n) else 0.0

    obs_sorted = obs.sort_values(
        ["timestamp_ist", "corridor_id", "direction"]
    ).reset_index(drop=True)
    # Hash row-by-row via pandas, not via CSV serialisation. ~10× faster on
    # 40k rows and scales linearly with row count, where to_csv allocated a
    # full string copy each call.
    md5_obs = hashlib.md5(
        pd.util.hash_pandas_object(obs_sorted, index=False).values.tobytes()
    ).hexdigest()

    corridors = _read_corridors()
    md5_corr = hashlib.md5(
        pd.util.hash_pandas_object(corridors, index=False).values.tobytes()
    ).hexdigest()

    stats = CoverageStats(
        total_observations=total,
        fail_count=fail_n,
        fail_pct=fail_pct,
        first_timestamp=str(obs["timestamp_ist"].min()),
        last_timestamp=str(obs["timestamp_ist"].max()),
        days_covered=obs["date"].nunique(),
        corridors_covered=obs["corridor_id"].nunique(),
        observations_md5=md5_obs,
        corridors_md5=md5_corr,
    )

    coverage = (
        obs.groupby(["corridor_id", "date"])
        .size()
        .reset_index(name="n_obs")
    )

    if fail_n:
        fail_summary = (
            fails["error_msg"]
            .fillna("(empty)")
            .str.slice(0, 60)
            .value_counts()
            .rename_axis("error_pattern")
            .reset_index(name="count")
        )
    else:
        fail_summary = pd.DataFrame(columns=["error_pattern", "count"])

    drift = (
        obs.groupby(["corridor_id", "direction"])
        .agg(
            distinct_distances=("distance_m", "nunique"),
            min_distance_m=("distance_m", "min"),
            max_distance_m=("distance_m", "max"),
            est_distance_km=("est_distance_km", "first"),
        )
        .reset_index()
    )
    drift["delta_m"] = drift["max_distance_m"] - drift["min_distance_m"]
    drift["delta_pct_of_est"] = (
        100.0 * drift["delta_m"] / (drift["est_distance_km"] * 1000.0)
    ).round(2)
    drift["reroute_flag"] = drift["delta_pct_of_est"] > 25.0

    # Per-route path-variability metric: share of distance readings falling
    # outside a ±5% band around the route's median distance. More
    # interpretable than min/max spread because it weights by how often the
    # routing engine departed from the dominant path, not just how far it
    # ever wandered. Threshold 30% defines the high_path_variability flag
    # surfaced in the standalone observation on the Methodology page.
    modal_rows = []
    for (cid, dirn), group in obs.groupby(["corridor_id", "direction"]):
        dists = group["distance_m"].dropna()
        if dists.empty:
            modal_rows.append({
                "corridor_id": cid, "direction": dirn,
                "median_distance_m": pd.NA,
                "pct_rows_outside_modal_5pct": pd.NA,
            })
            continue
        med = float(dists.median())
        lo, hi = med * 0.95, med * 1.05
        pct_out = round(100.0 * ((dists < lo) | (dists > hi)).mean(), 1)
        modal_rows.append({
            "corridor_id": cid, "direction": dirn,
            "median_distance_m": int(round(med)),
            "pct_rows_outside_modal_5pct": pct_out,
        })
    modal = pd.DataFrame(modal_rows)
    drift = drift.merge(modal, on=["corridor_id", "direction"], how="left")
    drift["high_path_variability_flag"] = (
        drift["pct_rows_outside_modal_5pct"].fillna(0) > 30.0
    )

    return {
        "stats": stats,
        "coverage": coverage,
        "fail_log": fails,
        "fail_summary": fail_summary,
        "distance_drift": drift.sort_values(
            "pct_rows_outside_modal_5pct", ascending=False, na_position="last"
        ),
        "cr_distribution": obs["congestion_ratio"].copy(),
    }


# ---------------------------------------------------------------------------
# Shared Streamlit caches
# ---------------------------------------------------------------------------
# Every page used to wrap load_observations/data_quality_report in its own
# @st.cache_data. Streamlit keys cache slots by the decorated function's
# module + qualname, so the per-page wrappers each occupied a separate cache
# slot — navigating between pages re-ran the full report on every page even
# though the inputs were identical. The two functions below are decorated
# once here, so every page shares the same cache slot keyed by the file
# signature. First page hit fills the cache; subsequent page hits across the
# whole app are instant until a new travel_log batch lands.

@st.cache_data(ttl=600, show_spinner="Loading observations…")
def cached_observations(sig: str) -> pd.DataFrame:
    return load_observations()


@st.cache_data(ttl=600, show_spinner=False)
def cached_quality_report(sig: str) -> dict:
    # Reuse the cached observations frame instead of letting
    # data_quality_report re-read every travel_log CSV from disk.
    return data_quality_report(cached_observations(sig))
