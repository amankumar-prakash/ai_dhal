# SentryOps / Red–Blue Platform

Lab monorepo: analyst UI (`secure_dash`), platform API (`api_service`), red/blue workers, and HexStrike.

This document is the **install and system-configuration runbook**. Specs under `specs/` cover feature validation; this file is what you need to stand the stack up.

## Architecture

```text
secure_dash ──JWT──► api_service ──► Postgres/Supabase (API only)
                         │
            ┌────────────┴────────────┐
            ▼                         ▼
     red_team_backend          blue_team_backend
     (LLM + HexStrike)         (LLM + HexStrike + CAI)
            │                         │
            └──── service token ──────┘
                         ▼
                   api_service (report findings/events)

hexstrike_server (nmap, nuclei, …) ◄── red/blue workers
```

**Secret placement**

| Secret | Where |
|--------|--------|
| `DATABASE_URL` / `SUPABASE_SECRET_KEY` (or legacy service role) | `api_service` only |
| `OPENAI_API_KEY`, `LLM_MODEL` | `red_team_backend` + `blue_team_backend` only |
| `RED_SERVICE_TOKEN` / `BLUE_SERVICE_TOKEN` | API (validate) + matching worker (send) |
| `VITE_*` / publishable Supabase key | Public UI config — never LLM or DB secrets |

---

## Repository layout

```text
ai_dhal/
├── docker-compose.yml          # API, red, blue, hexstrike
├── .env.example                # names only — copy to .env
├── api_service/                # FastAPI CRUD + job orchestration (port 8000)
├── red_team_backend/           # Alpine Python worker (port 8001)
├── blue_team_backend/          # Kali worker + CAI chat (port 8002)
├── hexstrike_server/           # Kali HexStrike MCP/API (port 8005)
├── secure_dash/                # TanStack Start / Vite UI (port 5173)
│   └── supabase/migrations/    # Postgres schema
└── scripts/                    # migrations, bootstrap, smoke checks
```

---

## Prerequisites

| Tool | Version / notes |
|------|-----------------|
| **Docker Engine + Compose v2** | Required for the recommended path |
| **Python** | 3.12 (API and red images; native venv) |
| **Node.js + npm** | 20+ via [nvm](https://github.com/nvm-sh/nvm); used by `secure_dash` |
| **Git** | Clone this repo |
| **Supabase project** | Auth + Postgres. Lab can use `API_STORE=memory` without it |
| **psql** (`postgresql-client`) | Only if applying SQL from the CLI |
| **uv** | Optional; HexStrike image installs it. Needed for native HexStrike / CAI |
| **OpenAI (or compatible) API key** | Required when `LLM_STUB=0` |
| **CAI checkout** | Optional sibling repo for blue CAI chat (see [CAI](#9-cai-blue-worker)) |

**Host resources (Compose):** HexStrike and blue images are Kali-based and large (security tools + Chromium). Allow several GB of disk and a few minutes for the first `docker compose build`.

**Python PEP 668:** on Kali/Debian, always use a venv — do not `pip install` into system Python.

---

## 1. Clone and create env files

```bash
git clone <this-repository-url>
cd ai_dhal

cp .env.example .env
# fill values in .env — never commit it

# UI (publishable keys only)
cp secure_dash/.env.example secure_dash/.env   # if present; otherwise create from the table below
```

Root `.env` is the **source of truth** for Compose (`env_file: .env`) and for `scripts/bootstrap_admin.py`. Native runs also load a `.env` from the **service working directory** (`api_service/.env`, `red_team_backend/.env`, `blue_team_backend/.env`). Keep those copies in sync with root `.env`, or symlink them.

Never put `SUPABASE_SECRET_KEY`, `DATABASE_URL`, or `OPENAI_API_KEY` in `secure_dash/.env`.

---

## 2. Environment reference

Copy names from `.env.example`. Real values stay in gitignored `.env` files.

### 2.1 Root `.env` — API (`api_service`)

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `API_STORE` | yes | `supabase` | `supabase` (shared Postgres) or `memory` (offline / pytest only) |
| `SUPABASE_URL` | if supabase | — | `https://<project-ref>.supabase.co` |
| `SUPABASE_SECRET_KEY` | if supabase | — | `sb_secret_…` (Settings → API Keys). Preferred |
| `SUPABASE_SERVICE_ROLE_KEY` | alias | — | Legacy JWT service_role; accepted if secret key unset |
| `SUPABASE_JWKS_URL` | no | derived | Override JWKS URL. Default `{SUPABASE_URL}/auth/v1/.well-known/jwks.json` |
| `SUPABASE_JWT_SECRET` | no | — | **Deprecated** HS256 fallback. Only if the project is not on signing keys |
| `DATABASE_URL` | for CLI migrations | — | Postgres URI (Settings → Database). Not used by workers |
| `RED_SERVICE_TOKEN` | yes | `change-me-red` | Shared secret: API validates, red worker sends |
| `BLUE_SERVICE_TOKEN` | yes | `change-me-blue` | Shared secret: API validates, blue worker sends |
| `RED_WORKER_URL` | native | `http://localhost:8001` | Compose overrides to `http://red_team_backend:8001` |
| `BLUE_WORKER_URL` | native | `http://localhost:8002` | Compose overrides to `http://blue_team_backend:8002` |
| `TEST_USERNAME` | bootstrap | — | First Admin email (`scripts/bootstrap_admin.py`) |
| `TEST_PASSWORD` | bootstrap | — | First Admin password |
| `TEST_MANAGER_USERNAME` | lab | — | Optional seeded manager account |
| `TEST_MANAGER_PASSWORD` | lab | — | Optional seeded manager password |

User JWTs are verified via JWKS. Do not rely on the legacy JWT secret once signing keys are enabled: [Supabase signing keys](https://supabase.com/docs/guides/auth/signing-keys).

### 2.2 Root `.env` — workers (LLM + tools)

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `OPENAI_API_KEY` | when `LLM_STUB=0` | — | LLM provider key (workers only) |
| `LLM_MODEL` | yes | `gpt-4o-mini` | Chat model id |
| `LLM_BASE_URL` | no | provider default | Compatible OpenAI-style base URL |
| `LLM_STUB` | no | `1` | `1` = no live LLM (CI/offline). `0` = real calls |
| `HEXSTRIKE_BASE_URL` | live tools | native: `http://localhost:8005` | HexStrike HTTP API. **Compose:** use `http://hexstrike_server:8005` (red is hardcoded to that) |
| `HEXSTRIKE_STUB` | no | `0` | `1` = in-process stub findings. `0` = call HexStrike; fail closed if unreachable |
| `HEXSTRIKE_MCP_SCRIPT` | Compose red | `/app/hexstrike/hexstrike_mcp.py` | MCP script path inside the red image |
| `DEMO_SAFE_MODE` | recommended | `1` | Lab guardrails; keep on unless you intend live targeting |
| `TARGET_ALLOWLIST` | recommended | empty | Comma-separated allowed targets (e.g. `http://localhost:3000`). Empty + safe mode = no live exploits |

### 2.3 Root `.env` — CAI (blue worker; red CAI is disabled)

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `CAI_HOST_PATH` | Compose volume | `../cai_pentesting` | Host path mounted at `/cai` in the blue container |
| `CAI_WORKDIR` | live CAI | `/cai` | Path **inside** the worker. Native: absolute host path to the CAI repo |
| `CAI_STUB` | no | `0` | `1` = stub deep-emulation plan. `0` = `uv run cai` (fail closed) |
| `CAI_CHAT_STUB` | no | `1` | `1` = synthetic SSE for `/tools/blue` chat. `0` = live `uv run cai` |
| `CAI_CONTAINER_VENV` | Compose | `/var/cache/cai-venv` | Kali-native uv env (not the host `.venv`) |
| `CAI_AGENT_TYPE` | red chat | `redteam_agent` | Unused while red CAI is disabled |
| `CAI_AGENT_TYPE_BLUE` | blue chat | `bug_bounter_agent` | Agent type for blue CAI chat |

### 2.4 `secure_dash/.env` — browser (public)

| Variable | Required | Purpose |
|----------|----------|---------|
| `VITE_SUPABASE_URL` | yes | Same project URL as the API |
| `VITE_SUPABASE_PUBLISHABLE_KEY` | yes | `sb_publishable_…` (anon). **Never** secret/service_role |
| `VITE_SUPABASE_PROJECT_ID` | yes | Project ref |
| `SUPABASE_URL` / `SUPABASE_PUBLISHABLE_KEY` / `SUPABASE_PROJECT_ID` | yes | Non-`VITE_` copies used by some tooling |
| `VITE_API_BASE_URL` | yes | Direct: `http://localhost:8000/api/v1`. Same-origin via Vite proxy: `/api/v1` |

Vite proxies `/api` → `http://127.0.0.1:8000` (`secure_dash/vite.config.ts`). Use `VITE_API_BASE_URL=/api/v1` when the UI is reached through a reverse proxy and the browser should stay same-origin.

### 2.5 Ownership matrix

| Variable | API | Red | Blue | UI |
|----------|:---:|:---:|:----:|:--:|
| `DATABASE_URL` / `SUPABASE_SECRET_KEY` | yes | no | no | **no** |
| `SUPABASE_URL` | yes | no | no | yes (public) |
| Publishable key | no | no | no | yes |
| `RED_SERVICE_TOKEN` | yes | yes | no | no |
| `BLUE_SERVICE_TOKEN` | yes | no | yes | no |
| `OPENAI_API_KEY` / `LLM_MODEL` | **no** | yes | yes | no |
| `HEXSTRIKE_*` | no | yes | yes | no |
| `CAI_*` | no | disabled | yes | no |
| `DEMO_SAFE_MODE` / `TARGET_ALLOWLIST` | no | yes | yes | no |
| `VITE_*` | no | no | no | yes |

`scripts/smoke_env_isolation.sh` asserts Compose keeps DB secrets off workers and LLM vars off the API.

### 2.6 Compose vs native URLs

| Setting | Docker Compose | Native (host processes) |
|---------|----------------|-------------------------|
| `RED_WORKER_URL` | `http://red_team_backend:8001` (compose `environment`) | `http://localhost:8001` |
| `BLUE_WORKER_URL` | `http://blue_team_backend:8002` | `http://localhost:8002` |
| `HEXSTRIKE_BASE_URL` | `http://hexstrike_server:8005` | `http://localhost:8005` |
| `CAI_WORKDIR` | `/cai` (volume from `CAI_HOST_PATH`) | absolute path to CAI checkout |
| API from workers | `http://api_service:8000/api/v1` | `http://localhost:8000/api/v1` |

If root `.env` sets `HEXSTRIKE_BASE_URL=http://localhost:8005`, **blue in Compose** will inherit that and fail to reach HexStrike. Either omit it (blue default is `http://hexstrike_server:8005`) or set the compose DNS name. Red ignores `.env` for this and always uses `http://hexstrike_server:8005`.

---

## 3. Supabase / Postgres

Skip this section if you only need offline tests (`API_STORE=memory`).

1. Create a Supabase project.
2. **API keys** (Settings → API Keys):
   - Secret (`sb_secret_…`) → root `.env` as `SUPABASE_SECRET_KEY`
   - Publishable (`sb_publishable_…`) → `secure_dash/.env` only
3. **Signing keys** (Settings → JWT): prefer asymmetric. Confirm JWKS:

   ```bash
   curl -sS "$SUPABASE_URL/auth/v1/.well-known/jwks.json"
   # expect {"keys":[...]}
   ```

4. Apply migrations under `secure_dash/supabase/migrations/` (order matters):

   | File | What it adds |
   |------|----------------|
   | `20260729100800_…sql` | Base app schema |
   | `20260804120000_red_blue_platform.sql` | `jobs`, `patches`, `tool_runs`, team columns |
   | `20260805140000_rbac_user_journeys.sql` | RBAC / user journeys |
   | `20260903120000_task_discovery_chain_fields.sql` | Task discovery chain fields |

   **Option A — Dashboard:** SQL Editor → paste each file (skip base if tables already exist).

   **Option B — CLI** (needs `DATABASE_URL` and `psql`):

   ```bash
   chmod +x scripts/apply_supabase_migrations.sh
   ./scripts/apply_supabase_migrations.sh
   ```

   **Option C:** `cd secure_dash && supabase db push` (linked CLI).

5. Verify schema:

   ```bash
   chmod +x scripts/verify_supabase_schema.sh
   ./scripts/verify_supabase_schema.sh
   ```

   Expect `jobs`, `patches`, `tool_runs`, `scans` to return HTTP 200 (not `PGRST205`).

Set `API_STORE=supabase` in root `.env`. Restart `api_service` after changing store or keys.

---

## 4. Install and run — Docker Compose (recommended)

```bash
cd ai_dhal
cp .env.example .env   # then edit

docker compose up --build
# or detached:
docker compose up -d --build
```

| Service | Image | Host port | Health |
|---------|-------|-----------|--------|
| `api_service` | `python:3.12-slim` | **8000** | `GET /api/v1/health` |
| `red_team_backend` | `python:3.12-alpine` | **8001** | `GET /health` |
| `blue_team_backend` | `kalilinux/kali-rolling` | **8002** | `GET /health` |
| `hexstrike_server` | `kalilinux/kali-rolling` + tools | **8005** | `GET /health` |

Workers wait until HexStrike is healthy. UI is **not** in Compose — run it on the host ([§6](#6-analyst-ui-secure_dash)).

```bash
docker compose ps
curl -sf http://localhost:8000/api/v1/health
curl -sf http://localhost:8000/api/v1/ready
curl -sf http://localhost:8001/health
curl -sf http://localhost:8002/health
curl -sf http://localhost:8005/health
```

Rebuild after Dockerfile or requirements changes:

```bash
docker compose build red_team_backend blue_team_backend hexstrike_server api_service
docker compose up -d
```

Optional extra Kali tools on **blue** (lean by default):

```bash
docker compose build --build-arg KALI_METAPACKAGE=kali-linux-headless blue_team_backend
```

Logs: `docker compose logs -f api_service red_team_backend blue_team_backend hexstrike_server`.

---

## 5. Install and run — native (no Docker)

Use this on a single host (or when Compose is unavailable). Bind the same ports as Compose.

### 5.1 Python venv (API + workers)

```bash
cd ai_dhal
python3 -m venv .venv
source .venv/bin/activate
pip install -r api_service/requirements.txt \
  -r red_team_backend/requirements.txt \
  -r blue_team_backend/requirements.txt
```

Copy or symlink root `.env` into each service directory so pydantic-settings finds it:

```bash
ln -sf ../.env api_service/.env
ln -sf ../.env red_team_backend/.env
ln -sf ../.env blue_team_backend/.env
```

Native `.env` URLs:

```bash
RED_WORKER_URL=http://localhost:8001
BLUE_WORKER_URL=http://localhost:8002
HEXSTRIKE_BASE_URL=http://localhost:8005
```

Four terminals (venv activated):

```bash
# API
cd api_service && uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Red
cd red_team_backend && uvicorn app.main:app --reload --host 127.0.0.1 --port 8001

# Blue (Kali/Debian: python3 -m)
cd blue_team_backend && python3 -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8002
```

### 5.2 HexStrike native

Needs Kali (or the tools listed in `hexstrike_server/Dockerfile`) plus [uv](https://docs.astral.sh/uv/).

```bash
cd hexstrike_server/hexstrike-ai
python3 -m pip install --user uv   # if needed
uv python install 3.12
uv sync                            # or: uv add -r requirements.txt
uv run hexstrike_server.py --port 8005
```

Upstream default port is **8888** (`HEXSTRIKE_PORT`). This lab uses **8005** to match Compose. Point workers at `HEXSTRIKE_BASE_URL=http://localhost:8005`.

Without the Kali toolset, keep `HEXSTRIKE_STUB=1` on the workers.

---

## 6. Analyst UI (`secure_dash`)

```bash
cd secure_dash
# Node via nvm if not on PATH:
#   . /opt/nvm/nvm.sh    # Vast / nvm hosts
npm install
npm run dev
```

Vite listens on **`127.0.0.1:5173`** (`strictPort: true`). Open `http://localhost:5173`.

| `VITE_API_BASE_URL` | When |
|---------------------|------|
| `/api/v1` | Browser hits Vite; `/api` is proxied to `127.0.0.1:8000` |
| `http://localhost:8000/api/v1` | Browser talks to the API directly (CORS enabled on the API) |

Build: `npm run build` / preview: `npm run preview`.

---

## 7. Bootstrap first Admin (RBAC)

Out-of-band only (no in-app wizard). In **root** `.env`:

```bash
TEST_USERNAME=admin@example.com
TEST_PASSWORD='your-lab-password'
API_STORE=supabase
SUPABASE_URL=https://<ref>.supabase.co
SUPABASE_SECRET_KEY=sb_secret_...
```

Apply the RBAC migration, then:

```bash
source .venv/bin/activate   # needs `supabase` Python package
python scripts/bootstrap_admin.py
```

Signs in as that user → Admin Panel at `/admin`. Re-run for zero-Admin recovery. Design: `specs/002-rbac-user-journeys/`.

---

## 8. HexStrike (live tools)

Compose starts `hexstrike_server` on **8005**. Red’s `surface-recon` calls `POST {HEXSTRIKE_BASE_URL}/api/tools/nmap`; blue’s vuln-scan calls `POST {HEXSTRIKE_BASE_URL}/api/tools/nuclei`.

- **`HEXSTRIKE_STUB=1`** — in-process stub findings; no network. Use in CI/offline.
- **`HEXSTRIKE_STUB=0`** — live HexStrike. If the server is down or returns an error, the job **fails closed** (`jobs.status=failed` + `error`). It never silently falls back to stubs.

```bash
# Compose (already wired)
docker compose up -d hexstrike_server
curl -sf http://localhost:8005/health
```

Covered by `red_team_backend/tests/test_hexstrike_live_fail.py` and `blue_team_backend/tests/test_hexstrike_live_fail.py`.

---

## 9. CAI (blue worker)

Red CAI is **disabled** (Alpine image; CAI routes commented out). Blue still runs CAI on Kali.

Interactive CAI (`uv run cai`) streams to `/tools/blue`. Secrets stay on the worker; the API proxies SSE.

```bash
# root .env
CAI_HOST_PATH=/absolute/path/to/cai_pentesting
CAI_WORKDIR=/cai
CAI_CONTAINER_VENV=/var/cache/cai-venv
CAI_CHAT_STUB=0          # 1 = synthetic stream
CAI_STUB=0
CAI_AGENT_TYPE_BLUE=bug_bounter_agent
OPENAI_API_KEY=…         # also in the CAI checkout .env as needed
```

```bash
docker compose build blue_team_backend
docker compose up -d blue_team_backend api_service

# Warm CAI once per image lifecycle (live chat):
docker compose exec blue_team_backend \
  sh -c 'cd /cai && UV_PROJECT_ENVIRONMENT=/var/cache/cai-venv uv sync'
```

For **native** blue: set `CAI_WORKDIR` to the absolute CAI path on the host; run `uv sync` there. `cai_client.py` runs `uv run cai "<prompt>"` (~120s timeout) and treats stdout as the plan. Missing workdir, missing `uv`/`cai`, non-zero exit, or timeout **fails the job closed**.

Sign in as Manager (or Analyst with tool unlock). Admin cannot open tools. See `specs/004-cai-tools-chat/quickstart.md`.

---

## 10. Safety / lab targeting

Keep these on for any shared or demo host:

```bash
DEMO_SAFE_MODE=1
TARGET_ALLOWLIST=http://localhost:3000
```

Jobs against non-allowlisted assets should emit a guardrail threat event and must not run exploit/destructive tools. Change allowlist and restart the affected worker.

---

## 11. Ports and health

| Process | Bind | Check |
|---------|------|--------|
| Analyst UI | `127.0.0.1:5173` | browser |
| Platform API | `0.0.0.0:8000` | `GET /api/v1/health`, `GET /api/v1/ready` |
| Red worker | `0.0.0.0:8001` | `GET /health` |
| Blue worker | `0.0.0.0:8002` | `GET /health` |
| HexStrike | `0.0.0.0:8005` | `GET /health` |

Workers authenticate to the API with `X-Service-Token`. Analysts use `Authorization: Bearer <Supabase JWT>`.

---

## 12. Tests

Prefer a venv (PEP 668):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r api_service/requirements.txt \
  -r red_team_backend/requirements.txt \
  -r blue_team_backend/requirements.txt

cd api_service && API_STORE=memory LLM_STUB=1 pytest -q
# memory tests may mint HS256 tokens with a local test secret; production uses JWKS
cd ../red_team_backend && LLM_STUB=1 pytest -q
cd ../blue_team_backend && LLM_STUB=1 pytest -q
cd .. && ./scripts/smoke_env_isolation.sh
```

UI: `cd secure_dash && npm test`.

CI (`.github/workflows/platform-tests.yml`) sets `LLM_STUB=1`, `API_STORE=memory`, and dummy service tokens.

Keep `HEXSTRIKE_STUB=1` / `CAI_STUB=1` / `CAI_CHAT_STUB=1` in CI and offline runs.

End-to-end checks: `specs/001-red-blue-platform/quickstart.md` (V1–V10).

### Env isolation smoke

```bash
chmod +x scripts/smoke_env_isolation.sh
./scripts/smoke_env_isolation.sh
# expected: env isolation OK / smoke_env_isolation passed
```

No containers need to be running. Fails if Compose is missing API/red/blue, LLM injection on workers, or the isolation comments.

---

## 13. Helper scripts

| Script | Purpose |
|--------|---------|
| `scripts/apply_supabase_migrations.sh` | Apply `secure_dash/supabase/migrations/*.sql` via `psql` + `DATABASE_URL` |
| `scripts/verify_supabase_schema.sh` | REST probe for `jobs` / `patches` / `tool_runs` / `scans` |
| `scripts/bootstrap_admin.py` | Create/confirm Admin from `TEST_USERNAME` / `TEST_PASSWORD` |
| `scripts/smoke_env_isolation.sh` | Compose secret-placement check |
| `scripts/verify_rbac_matrix.sh` | Partial RBAC smoke (`ACCESS_TOKEN=<jwt>`) |

---

## Offline / stub profile

Minimal `.env` for tests without Supabase, LLM, HexStrike, or CAI:

```bash
API_STORE=memory
LLM_STUB=1
HEXSTRIKE_STUB=1
CAI_STUB=1
CAI_CHAT_STUB=1
RED_SERVICE_TOKEN=change-me-red
BLUE_SERVICE_TOKEN=change-me-blue
DEMO_SAFE_MODE=1
```

---

## Further reading

- `docs/api-contracts.md` — API surfaces and auth
- `docs/threat-model.md` — trust boundaries
- `specs/001-red-blue-platform/` — platform + jobs
- `specs/002-rbac-user-journeys/` — roles and Admin bootstrap
- `specs/003-supabase-primary-db/` — store, JWKS, env contract
- `specs/004-cai-tools-chat/` — Kali CAI chat
- `hexstrike_server/hexstrike-ai/README.md` — HexStrike tools and MCP
