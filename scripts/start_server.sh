#!/usr/bin/env bash
# CR-035: Server startup guard — prevents duplicate process accumulation
# that can exhaust PostgreSQL max_connections.
#
# Usage:
#   bash scripts/start_server.sh          # default port 8000
#   bash scripts/start_server.sh 8001     # custom port
#   bash scripts/start_server.sh 8000 --reload  # extra uvicorn args

set -euo pipefail

PORT="${1:-8000}"
shift 2>/dev/null || true  # remaining args forwarded to uvicorn

# ── Guard: check for existing process on target port ──
if netstat -ano 2>/dev/null | grep -q ":${PORT}.*LISTEN"; then
    echo "ERROR: Port ${PORT} already in use."
    echo "  Existing process:"
    netstat -ano | grep ":${PORT}.*LISTEN"
    echo ""
    echo "  To fix: kill the existing process, then retry."
    echo "  Example: taskkill //F //PID <pid>"
    exit 1
fi

echo "Starting uvicorn on port ${PORT}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT}" "$@"
