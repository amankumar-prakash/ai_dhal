# SentryOps / Red–Blue Platform

Lab monorepo: analyst UI (`secure_dash`), platform API (`api_service`), and red/blue workers.

## Architecture

```text
secure_dash ──JWT──► api_service ──► Postgres/Supabase (API only)
                         │
            ┌────────────┴────────────┐
            ▼                         ▼
     red_team_backend          blue_team_backend
     (LLM + tools)             (LLM + vuln/patch)
            │                         │
            └──── service token ──────┘
                         ▼
                   api_service (report findings/events)
```

**Secret placement**

| Secret | Where |
|--------|--------|
| `DATABASE_URL` / Supabase service role | `api_service` only |
| `OPENAI_API_KEY`, `LLM_MODEL` | `red_team_backend` + `blue_team_backend` only |
| `VITE_*` | Public UI config (API base URL, Supabase anon) — never LLM or DB |

## Quick start (Compose)

```bash
cp .env.example .env
# optional: set OPENAI_API_KEY; leave LLM_STUB=1 for offline
docker compose up --build
```

| Service | Port |
|---------|------|
| API | http://localhost:8000/api/v1/health |
| Red | http://localhost:8001/health |
| Blue | http://localhost:8002/health |

Default `API_STORE=supabase` (shared Postgres). Set `API_STORE=memory` only for offline tests. Apply `secure_dash/supabase/migrations/` to your project (see below).

UI: set `VITE_API_BASE_URL=http://localhost:8000/api/v1` in `secure_dash` env and run the Vite app as usual.

## Apply Supabase migrations

Remote schema must include the red/blue extension (`jobs`, `patches`, `tool_runs`, team columns).

```bash
# Option A — Dashboard: SQL Editor → paste
#   secure_dash/supabase/migrations/20260804120000_red_blue_platform.sql

# Option B — connection string in root .env (DATABASE_URL=postgresql://...)
chmod +x scripts/apply_supabase_migrations.sh
./scripts/apply_supabase_migrations.sh
```

Also set in root `.env` (API only): `SUPABASE_SECRET_KEY` (or legacy `SUPABASE_SERVICE_ROLE_KEY`), `API_STORE=supabase`.
User JWTs are verified via JWKS (`/auth/v1/.well-known/jwks.json`) under [signing keys](https://supabase.com/docs/guides/auth/signing-keys)—do not rely on the legacy JWT secret.
Never put the secret key in `secure_dash/.env`.

## Bootstrap first Admin (RBAC)

Out-of-band only (no in-app wizard). Set in **root** `.env` (source of truth for `TEST_*` — not `secure_dash/.env`):

```bash
TEST_USERNAME=admin@example.com
TEST_PASSWORD='your-lab-password'
```

Apply RBAC migration `secure_dash/supabase/migrations/20260805140000_rbac_user_journeys.sql`, then:

```bash
python scripts/bootstrap_admin.py
```

Signs in as that user → Admin Panel at `/admin`. Re-run the script for zero-Admin recovery.

Design: `specs/002-rbac-user-journeys/`.

## CAI Chat on Red/Blue tool pages

Interactive CAI (`uv run cai`) streams to `/tools/red` and `/tools/blue` chat panels.
**Red and blue workers use Kali Linux images** (`kalilinux/kali-rolling`); CAI runs inside those containers.

```bash
# root .env
CAI_HOST_PATH=/home/kali/workspace/cai_pentesting   # mounted at /cai in Kali workers
CAI_WORKDIR=/cai                                    # path inside container
CAI_CONTAINER_VENV=/var/cache/cai-venv              # Kali-native uv env (ignore host .venv)
CAI_CHAT_STUB=1                                     # synthetic stream for CI/lab without CAI
# Live chat:
CAI_CHAT_STUB=0
CAI_AGENT_TYPE=redteam_agent
CAI_AGENT_TYPE_BLUE=bug_bounter_agent
```

```bash
docker compose build red_team_backend blue_team_backend
docker compose up -d red_team_backend blue_team_backend api_service
# Warm CAI once per image lifecycle (live chat):
docker compose exec red_team_backend \
  sh -c 'cd /cai && UV_PROJECT_ENVIRONMENT=/var/cache/cai-venv uv sync'
```

Optional Dockerfile build-arg `KALI_METAPACKAGE` (e.g. `kali-linux-headless`) installs extra Kali tools; default image stays lean.

Sign in as Manager (or Analyst with tool unlock), open tools page, use **CAI Chat**. API proxies SSE; secrets stay on workers. See `specs/004-cai-tools-chat/quickstart.md`.

## Live HexStrike + CAI (lab)

By default `HEXSTRIKE_STUB=1` and `CAI_STUB=1` in root `.env`, so red/blue workers use
in-process stub findings/plans and never touch the network. To exercise the real tools:

1. Start HexStrike's Flask API on the host (see `../hexstrike-ai`, `python3 hexstrike_server.py`,
   default port `8888`). From inside the worker containers it's reachable at
   `http://host.docker.internal:8888` (already wired via `extra_hosts` in `docker-compose.yml`).
2. Set in root `.env`:

   ```bash
   HEXSTRIKE_BASE_URL=http://host.docker.internal:8888   # or http://localhost:8888 for local (non-docker) runs
   HEXSTRIKE_STUB=0
   ```

   Red's `surface-recon` calls `POST {HEXSTRIKE_BASE_URL}/api/tools/nmap`; blue's vuln-scan calls
   `POST {HEXSTRIKE_BASE_URL}/api/tools/nuclei`. Findings then report `source_tool`/`tool_runs.tool_name`
   as `nmap`/`nuclei` (not `*-stub`). If the HexStrike server is unreachable or returns an error, the
   job fails closed (`jobs.status=failed` with an `error` message) — it never silently falls back to stub data.
3. For red's `deep-emulation` profile, point at a local [CAI](https://github.com/aliasrobotics/cai)
   checkout (e.g. `../cai_pentesting`) that has its own `.env` with `OPENAI_API_KEY` / `CAI_MODEL` and
   has run `uv sync` at least once:

   ```bash
   CAI_WORKDIR=/absolute/path/to/cai_pentesting
   CAI_STUB=0
   ```

   `cai_client.py` runs a one-shot `uv run cai "<prompt>"` (falling back to a bare `cai` on `PATH`) inside
   `CAI_WORKDIR` with a ~120s timeout and treats stdout as the plan. A missing workdir, missing `uv`/`cai`,
   non-zero exit, or timeout raises and fails the job closed — same "no silent stub" guarantee as HexStrike.
4. Restart the affected worker(s) (`docker compose up -d --build red_team_backend blue_team_backend`, or
   re-run locally) so the new env is picked up.

Keep `HEXSTRIKE_STUB=1` / `CAI_STUB=1` in CI and offline test runs — `red_team_backend/tests/test_hexstrike_live_fail.py`
and `blue_team_backend/tests/test_hexstrike_live_fail.py` cover the live-and-unreachable fail-closed path without
needing a real HexStrike/CAI instance.

## Env isolation smoke script

`scripts/smoke_env_isolation.sh` checks that `docker-compose.yml` keeps DB secrets on the API and LLM vars on the workers. No containers need to be running.

**Prerequisites:** Python 3 on `PATH`; run from the repo root.

```bash
cd /home/kali/workspace/pentesting_ui   # or your clone path
chmod +x scripts/smoke_env_isolation.sh   # once
./scripts/smoke_env_isolation.sh
```

**Expected success output:**

```text
env isolation OK
smoke_env_isolation passed
```

**Failure:** exits non-zero if the Compose file is missing the API/red/blue services, LLM injection on workers, the “do NOT pass OPENAI_API_KEY” note on the API, or the “No DATABASE_URL” notes on workers.

## Tests

Prefer a venv on Kali/Debian (PEP 668):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r api_service/requirements.txt \
  -r red_team_backend/requirements.txt \
  -r blue_team_backend/requirements.txt

cd api_service && API_STORE=memory LLM_STUB=1 pytest -q
# (memory tests may still mint HS256 tokens with a local test secret; production path uses JWKS)
cd ../red_team_backend && LLM_STUB=1 pytest -q
cd ../blue_team_backend && LLM_STUB=1 pytest -q
cd .. && ./scripts/smoke_env_isolation.sh
```

See `specs/001-red-blue-platform/quickstart.md` for V1–V10 checks.