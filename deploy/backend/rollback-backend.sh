#!/usr/bin/env bash
# Run on the BACKEND EC2: switch to the previous backend release (or a named one) and restart.
#   sudo bash deploy/backend/rollback-backend.sh [release-name]
set -euo pipefail
APP_ROOT="${APP_ROOT:-/opt/wasteflow}"; SERVICE="${SERVICE:-wasteflow-backend}"
SYSTEMCTL="${SYSTEMCTL:-systemctl}"; MCP_SERVICE="${MCP_SERVICE-wasteflow-mcp}"; HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8000/health}"
CURRENT="$(readlink -f "$APP_ROOT/current")"
if [[ -n "${1:-}" ]]; then TARGET="$APP_ROOT/releases/$1"
else TARGET="$(ls -1dt "$APP_ROOT"/releases/*/ | sed 's:/$::' | grep -vxF "$CURRENT" | head -n1 || true)"; fi
[[ -n "$TARGET" && -d "$TARGET" ]] || { echo "No release to roll back to"; exit 1; }
ln -sfn "$TARGET" "$APP_ROOT/current.new"; mv -T "$APP_ROOT/current.new" "$APP_ROOT/current"
if [[ -n "$MCP_SERVICE" ]] && $SYSTEMCTL cat "$MCP_SERVICE" >/dev/null 2>&1; then $SYSTEMCTL restart "$MCP_SERVICE"; fi
$SYSTEMCTL restart "$SERVICE"
sleep 3; curl -fsS --max-time 5 "$HEALTH_URL" && echo && echo "Rolled back: $CURRENT -> $TARGET"
