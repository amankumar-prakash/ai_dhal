#!/usr/bin/env bash
# Probe remote Supabase schema for red/blue extension objects.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

load_var() {
  local key="$1" file="$2"
  python3 - <<PY
from pathlib import Path
key = "$key"
for line in Path("$file").read_text().splitlines():
    if line.startswith(key + "="):
        print(line.split("=", 1)[1].strip().strip('"').strip("'"))
        break
PY
}

ENV_FILE="${1:-$ROOT/.env}"
UI_ENV="$ROOT/secure_dash/.env"
URL="$(load_var SUPABASE_URL "$ENV_FILE")"
KEY="$(load_var SUPABASE_PUBLISHABLE_KEY "$UI_ENV")"
if [[ -z "$KEY" ]]; then
  KEY="$(load_var SUPABASE_KEY "$ENV_FILE")"
fi
if [[ -z "$KEY" ]]; then
  KEY="$(load_var VITE_SUPABASE_PUBLISHABLE_KEY "$UI_ENV")"
fi
if [[ -z "$URL" || -z "$KEY" ]]; then
  echo "Need SUPABASE_URL and a publishable key (secure_dash/.env or SUPABASE_KEY)"
  exit 1
fi

fail=0
probe() {
  local path="$1" expect="$2"
  code=$(curl -sS -o /tmp/sb_probe.json -w "%{http_code}" \
    "$URL/rest/v1/$path" \
    -H "apikey: $KEY" \
    -H "Authorization: Bearer $KEY")
  body=$(head -c 200 /tmp/sb_probe.json)
  if [[ "$expect" == "ok" ]]; then
    if [[ "$code" == "200" ]]; then
      echo "OK  $path ($code)"
    else
      echo "FAIL $path ($code) $body"
      fail=1
    fi
  fi
}

echo "Project: $URL"
probe "jobs?select=id&limit=1" ok
probe "patches?select=id&limit=1" ok
probe "tool_runs?select=id&limit=1" ok
probe "scans?select=team,job_id,source_service&limit=1" ok
probe "job_progress_events?select=id&limit=1" ok

if [[ $fail -ne 0 ]]; then
  echo "Schema verify failed — apply secure_dash/supabase/migrations/20260804120000_red_blue_platform.sql"
  exit 1
fi
echo "schema verify passed"
