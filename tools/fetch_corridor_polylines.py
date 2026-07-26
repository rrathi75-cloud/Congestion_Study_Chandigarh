#!/usr/bin/env python3
"""
One-time fetch of road-following polylines for every corridor in
corridors.csv, using the free OSRM (OpenStreetMap Routing Machine) public
demo server. Saves the result to corridor_polylines.json at the repo root.

Run locally once:
    python tools/fetch_corridor_polylines.py

The dashboard's Corridor Map page reads corridor_polylines.json and draws
each corridor along its actual road path, instead of a straight line.

Notes:
  * The polylines are for DISPLAY ONLY. They show the canonical road path
    between the two endpoints. Google's live measurements (which produce
    the Congestion Ratio numbers) may follow a different path on any given
    call — the route-invariance of ratio metrics is what protects us.
  * OSRM's public demo server is rate-limited; we pause between requests.
  * The script is safe to re-run — corridors that already have valid
    polylines in the JSON are skipped.
"""

from __future__ import annotations

import csv
import json
import sys
import time
from pathlib import Path

import requests

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
CORRIDORS_FILE = PROJECT_DIR / "corridors.csv"
OUTPUT_FILE = PROJECT_DIR / "corridor_polylines.json"

OSRM_BASE = "https://router.project-osrm.org/route/v1/driving"
INTER_CALL_DELAY_SEC = 1.2  # be polite to the public demo server
REQUEST_TIMEOUT_SEC = 15


def fetch_one(origin_lng: float, origin_lat: float,
              dest_lng: float, dest_lat: float) -> list[list[float]] | None:
    """Return a list of [lng, lat] points along the road path, or None on failure."""
    url = (
        f"{OSRM_BASE}/"
        f"{origin_lng:.6f},{origin_lat:.6f};"
        f"{dest_lng:.6f},{dest_lat:.6f}"
    )
    params = {"overview": "full", "geometries": "geojson"}
    try:
        resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT_SEC)
        if resp.status_code != 200:
            print(f"    HTTP {resp.status_code}: {resp.text[:120]}")
            return None
        data = resp.json()
        if data.get("code") != "Ok":
            print(f"    OSRM code: {data.get('code')}")
            return None
        routes = data.get("routes") or []
        if not routes:
            print("    no routes returned")
            return None
        # GeoJSON LineString coords are already [lng, lat] pairs.
        coords = routes[0]["geometry"]["coordinates"]
        return coords
    except requests.RequestException as e:
        print(f"    request failed: {e}")
        return None


def main() -> int:
    if not CORRIDORS_FILE.exists():
        print(f"ERROR: {CORRIDORS_FILE} not found", file=sys.stderr)
        return 1

    # Load existing JSON (if any) so we can resume / skip already-fetched paths.
    existing: dict = {}
    if OUTPUT_FILE.exists():
        try:
            existing = json.loads(OUTPUT_FILE.read_text())
            print(f"Loaded {len(existing)} existing polylines from {OUTPUT_FILE.name}")
        except json.JSONDecodeError:
            print(f"WARN: {OUTPUT_FILE} exists but is not valid JSON; ignoring.")

    with open(CORRIDORS_FILE, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            row = {k.lstrip("\ufeff"): v for k, v in row.items()}
            rows.append(row)

    print(f"Fetching polylines for {len(rows)} (corridor, direction) pairs from OSRM…")
    print(f"  Server: {OSRM_BASE}")
    print(f"  Delay between calls: {INTER_CALL_DELAY_SEC}s")
    print()

    results: dict = dict(existing)
    new_fetches = 0
    failures = 0

    for idx, row in enumerate(rows, start=1):
        key = f"{row['corridor_id']}__{row['direction']}"
        name = row["corridor_name"][:60]

        if key in results and results[key].get("coords"):
            print(f"[{idx:>2}/{len(rows)}] {key} — cached, skip ({name})")
            continue

        print(f"[{idx:>2}/{len(rows)}] {key} — fetching ({name})")

        coords = fetch_one(
            float(row["origin_lng"]), float(row["origin_lat"]),
            float(row["dest_lng"]),  float(row["dest_lat"]),
        )

        if coords is None:
            failures += 1
            results[key] = {
                "corridor_id": row["corridor_id"],
                "corridor_name": row["corridor_name"],
                "direction": row["direction"],
                "coords": None,
                "n_points": 0,
                "error": "OSRM fetch failed",
            }
        else:
            new_fetches += 1
            results[key] = {
                "corridor_id": row["corridor_id"],
                "corridor_name": row["corridor_name"],
                "direction": row["direction"],
                "coords": coords,
                "n_points": len(coords),
            }
            print(f"    {len(coords)} road points")

        # Persist after every call so partial progress is never lost.
        OUTPUT_FILE.write_text(json.dumps(results, indent=2))
        time.sleep(INTER_CALL_DELAY_SEC)

    print()
    print(f"Done. {new_fetches} new fetched, {failures} failed, "
          f"{len(results)} total entries in {OUTPUT_FILE.name}")
    return 0 if failures == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
