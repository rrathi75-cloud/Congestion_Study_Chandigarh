#!/usr/bin/env bash
# Launch the Chandigarh Mobility Congestion Index dashboard.
#
# Usage:
#   ./run_dashboard.sh
#
# The script auto-detects the project virtual environment created by setup.sh.
# It works with both Unix-style and Windows-style venv layouts used in this repo.

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

PORT="${STREAMLIT_PORT:-8502}"
HOST="${STREAMLIT_HOST:-0.0.0.0}"

if [[ -x "venv/Scripts/streamlit.exe" ]]; then
    STREAMLIT="venv/Scripts/streamlit.exe"
elif [[ -x "venv/Scripts/streamlit" ]]; then
    STREAMLIT="venv/Scripts/streamlit"
elif [[ -x "venv/bin/streamlit" ]]; then
    STREAMLIT="venv/bin/streamlit"
elif command -v streamlit >/dev/null 2>&1; then
    STREAMLIT="streamlit"
else
    echo "ERROR: streamlit not found. Run setup.sh first, or:" >&2
    echo "  pip install -r requirements.txt" >&2
    exit 1
fi

echo "Launching Chandigarh Congestion Index dashboard …"
echo "Opens at http://localhost:${PORT} (Ctrl+C to stop)."
exec "$STREAMLIT" run dashboard/app.py \
    --browser.gatherUsageStats false \
    --server.headless false \
    --server.port "$PORT" \
    --server.address "$HOST"
