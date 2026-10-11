#!/usr/bin/env bash
# Run on the FRONTEND EC2. Switches back to the previous frontend release (or a named one):
#   sudo bash deploy/frontend/rollback-frontend.sh [release-name]
set -euo pipefail
WEB_ROOT="${WEB_ROOT:-/var/www/wasteflow}"
NGINX_BIN="${NGINX_BIN:-nginx}"; SYSTEMCTL="${SYSTEMCTL:-systemctl}"; RELOAD="${RELOAD:-yes}"

CURRENT="$(readlink -f "$WEB_ROOT/current")"
if [[ -n "${1:-}" ]]; then
  TARGET="$WEB_ROOT/releases/$1"
else
  TARGET="$(ls -1dt "$WEB_ROOT"/releases/*/ | sed 's:/$::' | grep -vxF "$CURRENT" | head -n1 || true)"
fi
[[ -n "$TARGET" && -d "$TARGET" ]] || { echo "No release to roll back to"; exit 1; }

ln -sfn "$TARGET" "$WEB_ROOT/current.new"
mv -T "$WEB_ROOT/current.new" "$WEB_ROOT/current"
$NGINX_BIN -t
[[ "$RELOAD" == "yes" ]] && $SYSTEMCTL reload nginx
echo "Rolled back: $CURRENT -> $TARGET"
echo "(Nginx config rollback: restore /etc/nginx/conf.d/wasteflow.conf from your copy, then nginx -t && systemctl reload nginx)"
