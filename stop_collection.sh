#!/usr/bin/env bash
# Chandigarh Mobility Audit — remove the cron entry installed by setup.sh.
#
# Usage:
#   chmod +x stop_collection.sh && ./stop_collection.sh

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY_SCRIPT="$PROJECT_DIR/collect_travel_times.py"

EXISTING_CRON="$(crontab -l 2>/dev/null || true)"

if [ -z "$EXISTING_CRON" ]; then
    echo "No crontab present for user $USER — nothing to remove."
    exit 0
fi

if ! echo "$EXISTING_CRON" | grep -F "$PY_SCRIPT" > /dev/null 2>&1; then
    echo "No cron entry referencing $PY_SCRIPT found — nothing to remove."
    exit 0
fi

# Drop every line that references our script, then reinstall the crontab.
NEW_CRON="$(echo "$EXISTING_CRON" | grep -F -v "$PY_SCRIPT" || true)"

if [ -z "$NEW_CRON" ]; then
    # No remaining lines — clear the crontab entirely.
    crontab -r 2>/dev/null || true
else
    echo "$NEW_CRON" | crontab -
fi

echo "Cron entry for $PY_SCRIPT removed."
echo "Verify with: crontab -l"
