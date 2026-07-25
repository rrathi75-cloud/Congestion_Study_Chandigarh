#!/usr/bin/env python3
"""
Chandigarh Urban Mobility Audit — Congestion Index Collector
 
Polls Google Routes API v2 every run for each OD pair in corridors.csv and
appends one row per pair to travel_log.csv. Designed to be invoked by cron
every 30 minutes between now and 2026-05-28 23:59 IST.
 
For this audit, the operator halted cron on 2026-08-11— collection ended
two days short of the in-script cutoff. The final audit window is 27july–11 august
2026. The in-script cutoff below remains in place as a safety net if cron
is ever restarted.
 
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
from datetime import datetime
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
 
# Hard auto-stop: collection window closes at this IST instant.
CUTOFF_IST = IST.localize(datetime(2026, 8, 11, 23, 59, 0))
 
REQUEST_TIMEOUT_SEC = 30
INTER_CALL_DELAY_SEC = 0.2
 
CSV_HEADER = [
    "timestamp_ist", "date", "time", "day_of_week", "hour", "is_weekend",
    "corridor_id", "corridor_name", "direction",
    "distance_m", "duration_traffic_s", "duration_freeflow_s",
    "congestion_ratio", "api_status", "error_msg",
]

 
