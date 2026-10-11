#!/usr/bin/env bash
# Run on the BACKEND EC2 (Amazon Linux 2023) from a checkout of the repo:
#   sudo bash deploy/backend/deploy-backend.sh
# Creates an immutable release (own virtualenv), runs the unit tests, switches the
# `current` symlink, restarts the service and checks /health. If the new release is
# unhealthy it switches back to the previous one automatically.
set -euo pipefail

REPO_DIR="${REPO_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
APP_ROOT="${APP_ROOT:-/opt/wasteflow}"
SERVICE="${SERVICE:-wasteflow-backend}"
SERVICE_USER="${SERVICE_USER:-wasteflow}"
MCP_SERVICE="${MCP_SERVICE-wasteflow-mcp}"   # empty = skip (e.g. MCP not installed yet)
PYTHON="${PYTHON:-python3.11}"
SYSTEMCTL="${SYSTEMCTL:-systemctl}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8000/health}"
HEALTH_WAIT="${HEALTH_WAIT:-30}"
KEEP="${KEEP:-5}"

RELEASE="$APP_ROOT/releases/$(date +%Y%m%d%H%M%S)"
SWITCHED=no
cleanup_unswitched() { if [[ "$SWITCHED" == "no" ]]; then rm -rf "$RELEASE"; fi; }
trap cleanup_unswitched EXIT
PREVIOUS="$(readlink -f "$APP_ROOT/current" 2>/dev/null || true)"

restart_services() {
  if [[ -n "$MCP_SERVICE" ]] && $SYSTEMCTL cat "$MCP_SERVICE" >/dev/null 2>&1; then $SYSTEMCTL restart "$MCP_SERVICE"; fi
  $SYSTEMCTL restart "$SERVICE"
}
switch_to() { ln -sfn "$1" "$APP_ROOT/current.new" && mv -T "$APP_ROOT/current.new" "$APP_ROOT/current"; }
healthy() {
  for _ in $(seq 1 "$HEALTH_WAIT"); do
    curl -fsS --max-time 3 "$HEALTH_URL" >/dev/null 2>&1 && return 0
    sleep 1
  done
  return 1
}

echo "==> Creating release $RELEASE"
mkdir -p "$RELEASE"
cp -r "$REPO_DIR/backend" "$RELEASE/backend"
cp -r "$REPO_DIR/mcp-server" "$RELEASE/mcp-server"
rm -rf "$RELEASE/mcp-server/.venv" "$RELEASE/mcp-server/.env" "$RELEASE/mcp-server/.pytest_cache"
rm -rf "$RELEASE/backend/.venv" "$RELEASE/backend/venv" "$RELEASE/backend/.env" "$RELEASE/backend/.pytest_cache"
find "$RELEASE" -name __pycache__ -type d -prune -exec rm -rf {} +
# (the release venv is shared by the backend and the MCP server; both import the same app/ package)

echo "==> Installing dependencies ($($PYTHON --version))"
"$PYTHON" -m venv "$RELEASE/backend/.venv"
"$RELEASE/backend/.venv/bin/python" -m pip install --quiet --upgrade pip
"$RELEASE/backend/.venv/bin/python" -m pip install --quiet -r "$RELEASE/backend/requirements.txt"

echo "==> Unit tests (no database needed; run from the checkout, which has schema.sql/frontend/deploy)"
( cd "$REPO_DIR/backend" && PYTHONDONTWRITEBYTECODE=1 "$RELEASE/backend/.venv/bin/python" -m pytest -q -m "not integration" -p no:cacheprovider )
echo "==> MCP server unit tests"
( cd "$REPO_DIR/mcp-server" && PYTHONDONTWRITEBYTECODE=1 "$RELEASE/backend/.venv/bin/python" -m pytest -q -m "not integration" -p no:cacheprovider )

if id "$SERVICE_USER" >/dev/null 2>&1; then chown -R "$SERVICE_USER:$SERVICE_USER" "$RELEASE"; else echo "warn: user $SERVICE_USER not found, skipping chown"; fi

echo "==> Switching to the new release and restarting $SERVICE"
switch_to "$RELEASE"
SWITCHED=yes
restart_services

if healthy; then
  echo "==> Healthy. Pruning old releases (keeping $KEEP)"
  ls -1dt "$APP_ROOT"/releases/*/ | tail -n +$((KEEP + 1)) | xargs -r rm -rf
  echo "OK: $RELEASE is live (previous: ${PREVIOUS:-none})"
else
  echo "!! $HEALTH_URL did not become healthy within ${HEALTH_WAIT}s"
  if [[ -n "$PREVIOUS" && -d "$PREVIOUS" ]]; then
    echo "!! Rolling back to $PREVIOUS"
    switch_to "$PREVIOUS"
    restart_services
  fi
  rm -rf "$RELEASE"   # never leave a broken release behind for rollback to pick up
  echo "Inspect: journalctl -u $SERVICE -n 100 --no-pager"
  exit 1
fi
