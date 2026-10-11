#!/usr/bin/env bash
# Run on the FRONTEND EC2 (Amazon Linux) from a checkout of the repo:
#   BACKEND_HOST=<backend private IP or DNS> sudo -E bash deploy/frontend/deploy-frontend.sh
# Builds the Vite app, installs it as a new immutable release, renders the Nginx config,
# validates it, then switches traffic atomically. Any failure restores the previous state.
set -euo pipefail

REPO_DIR="${REPO_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
WEB_ROOT="${WEB_ROOT:-/var/www/wasteflow}"
NGINX_CONF_DIR="${NGINX_CONF_DIR:-/etc/nginx/conf.d}"
NGINX_BIN="${NGINX_BIN:-nginx}"
SYSTEMCTL="${SYSTEMCTL:-systemctl}"
RELOAD="${RELOAD:-yes}"
KEEP="${KEEP:-5}"
NGINX_TEMPLATE="${NGINX_TEMPLATE:-$REPO_DIR/deploy/nginx/wasteflow-frontend.conf.template}"
SKIP_BUILD="${SKIP_BUILD:-no}"      # yes = use a prebuilt dist/ copied from another machine (no Node needed here)
DIST_DIR="${DIST_DIR:-$REPO_DIR/frontend/dist}"
BACKEND_HOST="${BACKEND_HOST:?Set BACKEND_HOST to the backend EC2 PRIVATE IP or private DNS name}"

[[ "$BACKEND_HOST" =~ ^[A-Za-z0-9.-]+$ ]] || { echo "BACKEND_HOST must be a hostname or IP"; exit 1; }
[[ "$BACKEND_HOST" != "localhost" && "$BACKEND_HOST" != 127.* ]] || [[ "${ALLOW_LOCAL_BACKEND:-no}" == "yes" ]] \
  || { echo "BACKEND_HOST must be the backend's private address, not localhost"; exit 1; }

CONF="$NGINX_CONF_DIR/wasteflow.conf"
RELEASE="$WEB_ROOT/releases/$(date +%Y%m%d%H%M%S)"
PREVIOUS="$(readlink -f "$WEB_ROOT/current" 2>/dev/null || true)"

if [[ "$SKIP_BUILD" == "yes" ]]; then
  echo "==> Using prebuilt $DIST_DIR"
else
  echo "==> Building frontend (npm ci + build)"
  ( cd "$REPO_DIR/frontend" && npm ci && npm run build )
fi
[[ -f "$DIST_DIR/index.html" ]] || { echo "No $DIST_DIR/index.html"; exit 1; }

echo "==> Installing release $RELEASE"
mkdir -p "$RELEASE" "$NGINX_CONF_DIR"
cp -r "$DIST_DIR/." "$RELEASE/"
chmod -R a+rX "$RELEASE"

restore() {
  echo "!! Deployment failed, restoring previous state"
  [[ -f "$CONF.bak" ]] && mv -f "$CONF.bak" "$CONF"
  [[ -n "$PREVIOUS" && -d "$PREVIOUS" ]] && { ln -sfn "$PREVIOUS" "$WEB_ROOT/current.new" && mv -T "$WEB_ROOT/current.new" "$WEB_ROOT/current"; }
  rm -rf "$RELEASE"
}
trap restore ERR

[[ -f "$CONF" ]] && cp -p "$CONF" "$CONF.bak"
sed -e "s/BACKEND_PRIVATE_HOST/$BACKEND_HOST/g" -e "s#/var/www/wasteflow#$WEB_ROOT#g" "$NGINX_TEMPLATE" > "$CONF"

ln -sfn "$RELEASE" "$WEB_ROOT/current.new"
mv -T "$WEB_ROOT/current.new" "$WEB_ROOT/current"

echo "==> Validating Nginx configuration"
$NGINX_BIN -t
[[ "$RELOAD" == "yes" ]] && $SYSTEMCTL reload nginx
trap - ERR
rm -f "$CONF.bak"

echo "==> Pruning old releases (keeping $KEEP)"
ls -1dt "$WEB_ROOT"/releases/*/ 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm -rf
echo "OK: now serving $RELEASE (previous: ${PREVIOUS:-none})"
