
"""
Chandigarh Urban Mobility Audit — Congestion Index Collector
 
Polls Google Routes API v2 every run for each OD pair in corridors.csv and
appends one row per pair to travel_log.csv. Designed to be invoked by cron
every 30 minutes during the audit window from 2026-07-27 to 2026-08-11 IST.

The collector enforces both a start and end boundary so it will not run
before the audit window opens or after it closes. This keeps the data pull
aligned with the requested study period even if cron is left enabled.
 
Maintainer notes:
  - API key is read from the GOOGLE_MAPS_API_KEY env var (.env file supported).
  - Hard auto-stop is enforced at the top of main(): no API calls are made
    after 2026-08-11 23:59:00 Asia/Kolkata.
  - Failures on individual corridors are logged and skipped; the batch never
    crashes on a single bad response.
"""
 
import csv
import logging
import os
import sys
import time
from datetime import datetime, timedelta 
from logging.handlers import RotatingFileHandler
from pathlib import Path
 
import pytz
import requests
from dotenv import load_dotenv
 
# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
 
SCRIPT_DIR = Path(__file__).resolve().parent
CORRIDORS_FILE = SCRIPT_DIR / "corridors.csv"
LOG_CSV = SCRIPT_DIR / "travel_log.csv"
LOG_FILE = SCRIPT_DIR / "collector.log"
 
ROUTES_ENDPOINT = "https://routes.googleapis.com/directions/v2:computeRoutes"
FIELD_MASK = "routes.duration,routes.staticDuration,routes.distanceMeters"
 
IST = pytz.timezone("Asia/Kolkata")
UTC = pytz.utc
 
# Enforce the audit window in IST.
WINDOW_START_IST = IST.localize(datetime(2026, 7, 27, 0, 0, 0))
WINDOW_END_IST = IST.localize(datetime(2026, 8, 11, 23, 59, 0))
 
REQUEST_TIMEOUT_SEC = 30
INTER_CALL_DELAY_SEC = 0.2
 
CSV_HEADER = [
    "timestamp_ist", "date", "time", "day_of_week", "hour", "is_weekend",
    "corridor_id", "corridor_name", "direction",
    "distance_m", "duration_traffic_s", "duration_freeflow_s",
    "congestion_ratio", "api_status", "error_msg",
]


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
 
def setup_logging() -> logging.Logger:
    """Configure a rotating file logger (10 MB x 5 backups)."""
    logger = logging.getLogger("patna_collector")
    logger.setLevel(logging.INFO)
 
    # Avoid duplicate handlers if main() is called repeatedly in the same process.
    if logger.handlers:
        return logger
 
    handler = RotatingFileHandler(
        LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(handler)
    return logger
 
  
# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
 
def parse_duration_seconds(value):
    """
    Google returns durations as strings like "1234s". Strip the trailing "s"
    and return an int. Returns None on any parse failure.
    """
    if value is None:
        return None
    s = str(value).strip()
    if s.endswith("s"):
        s = s[:-1]
    try:
        # Some responses may be "123.4s"; round to nearest second.
        return int(round(float(s)))
    except (ValueError, TypeError):
        return None
 
 
def now_ist():
    return datetime.now(IST)
 
 
from datetime import datetime, timedelta

def utc_rfc3339_now():
    """Return a UTC timestamp 5 minutes in the future."""
    future = datetime.now(UTC) + timedelta(minutes=5)
    return future.strftime("%Y-%m-%dT%H:%M:%SZ")
 
 
def build_time_fields(ts_ist: datetime) -> dict:
    """Derive the time-related CSV columns from an IST datetime."""
    return {
        "timestamp_ist": ts_ist.strftime("%Y-%m-%d %H:%M:%S"),
        "date": ts_ist.strftime("%Y-%m-%d"),
        "time": ts_ist.strftime("%H:%M:%S"),
        "day_of_week": ts_ist.strftime("%A"),
        "hour": ts_ist.hour,
        "is_weekend": "Y" if ts_ist.weekday() >= 5 else "N",
    }
 
 
def call_routes_api(api_key: str, row: dict, logger: logging.Logger) -> dict:
    """
    Call Google Routes API v2 for one OD pair.
 
    Returns a dict with keys: distance_m, duration_traffic_s,
    duration_freeflow_s, api_status, error_msg.
    On failure, numeric fields are None and api_status == "FAIL".
    """
    result = {
        "distance_m": None,
        "duration_traffic_s": None,
        "duration_freeflow_s": None,
        "api_status": "FAIL",
        "error_msg": "",
    }
 
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": FIELD_MASK,
    }
 
    body = {
        "origin": {
            "location": {
                "latLng": {
                    "latitude": float(row["origin_lat"]),
                    "longitude": float(row["origin_lng"]),
                }
            }
        },
        "destination": {
            "location": {
                "latLng": {
                    "latitude": float(row["dest_lat"]),
                    "longitude": float(row["dest_lng"]),
                }
            }
        },
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE_OPTIMAL",
        "departureTime": utc_rfc3339_now(),
    }
 
    try:
        resp = requests.post(
            ROUTES_ENDPOINT,
            headers=headers,
            json=body,
            timeout=REQUEST_TIMEOUT_SEC,
        )
 
        if resp.status_code != 200:
            # Trim error body so the CSV stays readable.
            snippet = (resp.text or "").strip().replace("\n", " ")[:300]
            result["error_msg"] = f"HTTP {resp.status_code}: {snippet}"
            logger.warning(
                "Corridor %s (%s) API error: %s",
                row.get("corridor_id"), row.get("direction"), result["error_msg"],
            )
            return result
 
        data = resp.json()
        routes = data.get("routes") or []
        if not routes:
            result["error_msg"] = "No routes returned"
            logger.warning(
                "Corridor %s (%s): empty routes list",
                row.get("corridor_id"), row.get("direction"),
            )
            return result
 
        route = routes[0]
        duration_traffic_s = parse_duration_seconds(route.get("duration"))
        duration_freeflow_s = parse_duration_seconds(route.get("staticDuration"))
        distance_m = route.get("distanceMeters")
 
        if not isinstance(distance_m, int):
            try:
                distance_m = int(distance_m) if distance_m is not None else None
            except (ValueError, TypeError):
                distance_m = None
 
        result.update({
            "distance_m": distance_m,
            "duration_traffic_s": duration_traffic_s,
            "duration_freeflow_s": duration_freeflow_s,
            "api_status": "OK",
            "error_msg": "",
        })
        return result
 
    except requests.exceptions.Timeout:
        result["error_msg"] = f"Request timed out after {REQUEST_TIMEOUT_SEC}s"
    except requests.exceptions.ConnectionError as e:
        result["error_msg"] = f"Connection error: {str(e)[:200]}"
    except requests.exceptions.RequestException as e:
        result["error_msg"] = f"Request failed: {str(e)[:200]}"
    except ValueError as e:
        # JSON decode error
        result["error_msg"] = f"Invalid JSON response: {str(e)[:200]}"
    except Exception as e:  # noqa: BLE001 — defensive catch-all per spec
        result["error_msg"] = f"Unexpected error: {type(e).__name__}: {str(e)[:200]}"
 
    logger.warning(
        "Corridor %s (%s) failed: %s",
        row.get("corridor_id"), row.get("direction"), result["error_msg"],
    )
    return result
 
 
def compute_congestion_ratio(traffic_s, freeflow_s):
    if traffic_s is None or freeflow_s is None:
        return ""
    if freeflow_s <= 0:
        return ""
    return round(traffic_s / freeflow_s, 3)
 
 
def append_row(row_dict: dict):
    """Append one row to travel_log.csv, writing the header if the file is new."""
    file_exists = LOG_CSV.exists()
    with open(LOG_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADER)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row_dict)
 
 
# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
 
def main():
    logger = setup_logging()
 
    # --- Audit-window guard (must happen before any API call) ---
    current_ist = now_ist()
    if current_ist < WINDOW_START_IST:
        msg = "Collection window has not started yet — exiting"
        logger.info(msg)
        print(msg)
        sys.exit(0)

    if current_ist > WINDOW_END_IST:
        msg = "Collection window closed — exiting"
        logger.info(msg)
        print(msg)
        sys.exit(0)
 
    # Load .env from the script directory so cron picks it up regardless of cwd.
    load_dotenv(dotenv_path=SCRIPT_DIR / ".env")
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY", "").strip()
    if not api_key:
        logger.error("GOOGLE_MAPS_API_KEY is not set. Aborting run.")
        print("ERROR: GOOGLE_MAPS_API_KEY is not set. See .env.example.")
        sys.exit(1)
 
    if not CORRIDORS_FILE.exists():
        logger.error("corridors.csv not found at %s. Aborting run.", CORRIDORS_FILE)
        print(f"ERROR: corridors.csv not found at {CORRIDORS_FILE}")
        sys.exit(1)
 
    # Load corridor rows.
    # Use utf-8-sig so that CSV files saved by Excel/VS Code with a UTF-8 BOM
    # are read correctly and the first column name (corridor_id) is not corrupted.
    with open(CORRIDORS_FILE, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        corridors = list(reader)
 
    if not corridors:
        logger.error("corridors.csv is empty. Aborting run.")
        print("ERROR: corridors.csv is empty.")
        sys.exit(1)
 
    total = len(corridors)
    success = 0
    failed = 0
 
    logger.info("Starting batch: %d corridors at %s IST",
                total, current_ist.strftime("%Y-%m-%d %H:%M:%S"))
 
    for idx, row in enumerate(corridors):
        # Use a fresh per-corridor IST timestamp so the log reflects the
        # actual time of each call (batches can take a minute or two).
        ts_ist = now_ist()
 
        api_result = call_routes_api(api_key, row, logger)
 
        record = build_time_fields(ts_ist)
        record.update({
            "corridor_id": row.get("corridor_id", ""),
            "corridor_name": row.get("corridor_name", ""),
            "direction": row.get("direction", ""),
            "distance_m": api_result["distance_m"] if api_result["distance_m"] is not None else "",
            "duration_traffic_s": api_result["duration_traffic_s"] if api_result["duration_traffic_s"] is not None else "",
            "duration_freeflow_s": api_result["duration_freeflow_s"] if api_result["duration_freeflow_s"] is not None else "",
            "congestion_ratio": compute_congestion_ratio(
                api_result["duration_traffic_s"], api_result["duration_freeflow_s"]
            ),
            "api_status": api_result["api_status"],
            "error_msg": api_result["error_msg"],
        })
 
        try:
            append_row(record)
        except Exception as e:  # noqa: BLE001
            logger.error("Failed to write CSV row for corridor %s: %s",
                         row.get("corridor_id"), e)
 
        if api_result["api_status"] == "OK":
            success += 1
        else:
            failed += 1
 
        # Polite delay between calls; skip the wait after the last one.
        if idx < total - 1:
            time.sleep(INTER_CALL_DELAY_SEC)
 
    summary_ts = now_ist().strftime("%Y-%m-%d %H:%M IST")
    summary = f"[{summary_ts}] {success}/{total} success, {failed} failed"
    logger.info(summary)
    print(summary)
 
 
if __name__ == "__main__":
    main()

 
