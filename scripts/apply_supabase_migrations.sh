#!/usr/bin/env bash
# Apply versioned SQL migrations to the remote Supabase Postgres.
# Requires DATABASE_URL (Session mode or direct) from Supabase → Project Settings → Database.
# Service role key alone cannot run arbitrary SQL via PostgREST.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MIG_DIR="$ROOT/secure_dash/supabase/migrations"

if [[ -z "${DATABASE_URL:-}" ]]; then
  if [[ -f "$ROOT/.env" ]]; then
    # shellcheck disable=SC1091
    set -a
    # Load only DATABASE_URL without printing secrets
    DATABASE_URL="$(python3 - <<PY
from pathlib import Path
for line in Path("$ROOT/.env").read_text().splitlines():
    if line.startswith("DATABASE_URL=") and not line.strip().endswith("="):
        print(line.split("=",1)[1].strip().strip('"').strip("'"))
        break
PY
)"
    set +a
  fi
fi

if [[ -z "${DATABASE_URL:-}" ]]; then
  cat <<'EOF'
DATABASE_URL is not set.

Cannot apply SQL with only the publishable key or an empty SUPABASE_SERVICE_ROLE_KEY.

Do one of the following:

1) Dashboard (recommended for lab):
   Supabase → SQL → New query → paste:
   secure_dash/supabase/migrations/20260804120000_red_blue_platform.sql
   (Skip the base migration if assets/scans already exist.)

2) Set DATABASE_URL in root .env (Settings → Database → Connection string, URI),
   then re-run:
   ./scripts/apply_supabase_migrations.sh

3) Linked CLI:
   cd secure_dash && supabase db push
EOF
  exit 1
fi

if ! command -v psql >/dev/null 2>&1; then
  echo "psql not found. Install postgresql-client or use the Dashboard SQL method."
  exit 1
fi

echo "Applying migrations from $MIG_DIR"
# Prefer red/blue extension if base already applied; apply in sorted order
for f in "$MIG_DIR"/*.sql; do
  echo "==> $(basename "$f")"
  psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f "$f" || {
    echo "Note: base migration may fail if already applied; run the 20260804 file alone if needed."
    exit 1
  }
done
echo "Migrations applied."
