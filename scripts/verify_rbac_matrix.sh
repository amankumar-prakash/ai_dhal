#!/usr/bin/env bash
# Exercise Access Matrix allow/deny against a running API (requires bootstrap Admin JWT).
# Usage:
#   ACCESS_TOKEN=... ./scripts/verify_rbac_matrix.sh
# Optional: API_BASE=http://localhost:8000/api/v1
set -euo pipefail
API_BASE="${API_BASE:-http://localhost:8000/api/v1}"
TOKEN="${ACCESS_TOKEN:-}"
if [[ -z "$TOKEN" ]]; then
  echo "Set ACCESS_TOKEN to a user JWT (from browser session or sign-in)." >&2
  exit 1
fi
auth=(-H "Authorization: Bearer $TOKEN")
echo "GET $API_BASE/me"
curl -sf "${auth[@]}" "$API_BASE/me" | tee /tmp/me.json
ROLE=$(python3 -c "import json; print(json.load(open('/tmp/me.json'))['role'])")
echo "Role=$ROLE"
case "$ROLE" in
  admin)
    curl -sf "${auth[@]}" "$API_BASE/admin/users" >/dev/null && echo "OK admin list users"
    code=$(curl -s -o /dev/null -w "%{http_code}" "${auth[@]}" "$API_BASE/assets" || true)
    [[ "$code" == "403" ]] && echo "OK admin denied assets" || echo "FAIL expected 403 assets got $code"
    ;;
  user)
    curl -sf "${auth[@]}" "$API_BASE/assets" >/dev/null && echo "OK user read assets"
    code=$(curl -s -o /dev/null -w "%{http_code}" "${auth[@]}" "$API_BASE/tasks" || true)
    [[ "$code" == "403" ]] && echo "OK user denied tasks" || echo "FAIL expected 403 tasks got $code"
    ;;
  security_manager|security_analyst)
    curl -sf "${auth[@]}" "$API_BASE/tasks" >/dev/null && echo "OK $ROLE list tasks"
    ;;
  *)
    echo "Unknown role $ROLE"
    ;;
esac
echo "Done (partial matrix smoke — expand as needed)."
