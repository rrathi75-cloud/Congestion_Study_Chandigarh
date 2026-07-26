#!/usr/bin/env bash
# Chandigarh Mobility Audit — one-shot setup script for Ubuntu 22.04.
#
# What this does:
#   1. Installs system Python 3 + pip + venv (idempotent).
#   2. Creates ./venv and installs Python dependencies from requirements.txt.
#   3. Adds a cron entry that runs the collector every 30 minutes during the
#      audit window. The collector script itself also enforces the 2026-07-27
#      to 2026-08-11 date window, so it will stop automatically outside it.
#
# Run this from the project directory (e.g. ~/chandigarh-mobility):
#   chmod +x setup.sh && ./setup.sh

set -euo pipefail

# Resolve the directory this script lives in. The cron entry will use this
# path verbatim, so the script works whether the project sits in
# /home/$USER/chandigarh-mobility or somewhere else.
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY_SCRIPT="$PROJECT_DIR/collect_travel_times.py"
VENV_PY="$PROJECT_DIR/venv/bin/python"
CRON_LOG="$PROJECT_DIR/cron.log"

CRON_LINE="*/30 * * * * cd \"$PROJECT_DIR\" && \"$VENV_PY\" \"$PY_SCRIPT\" >> \"$CRON_LOG\" 2>&1"

echo "==> Chandigarh Mobility setup starting"
echo "    Project dir: $PROJECT_DIR"

# --- Step 1: system packages ---
echo "==> Installing system dependencies (python3, pip, venv)…"
sudo apt update
sudo apt install -y python3 python3-pip python3-venv

# --- Step 2: virtual environment + Python deps ---
if [ ! -d "$PROJECT_DIR/venv" ]; then
    echo "==> Creating virtual environment at $PROJECT_DIR/venv"
    python3 -m venv "$PROJECT_DIR/venv"
else
    echo "==> venv already exists, reusing it"
fi

echo "==> Installing Python requirements…"
"$PROJECT_DIR/venv/bin/pip" install --upgrade pip
"$PROJECT_DIR/venv/bin/pip" install -r "$PROJECT_DIR/requirements.txt"

# --- Step 3: cron entry (idempotent) ---
echo "==> Configuring cron entry…"

# Read existing crontab (suppress error if user has none yet).
EXISTING_CRON="$(crontab -l 2>/dev/null || true)"

# Match by the script path so we never duplicate an entry, even if other
# fields drift over time.
if echo "$EXISTING_CRON" | grep -F "$PY_SCRIPT" > /dev/null 2>&1; then
    echo "    Cron entry for $PY_SCRIPT already exists — leaving it alone."
else
    # Append our line and reinstall the crontab.
    {
        echo "$EXISTING_CRON"
        echo "$CRON_LINE"
    } | sed '/^$/d' | crontab -
    echo "    Added cron entry:"
    echo "    $CRON_LINE"
fi

echo
echo "==> Setup complete."
echo "    Next steps:"
echo "      1. Copy .env.example to .env and put your real API key in it:"
echo "           cp .env.example .env && nano .env"
echo "      2. Run a one-off test:"
echo "           ./venv/bin/python collect_travel_times.py"
echo "      3. Watch cron:"
echo "           crontab -l"
echo "           tail -f $CRON_LOG"
