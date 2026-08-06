# Quickstart Validation: Red/Blue Security Platform

**Feature**: `001-red-blue-platform`  
**Date**: 2026-08-04  
**Purpose**: Runnable checks that prove the feature end-to-end. Implementation lives in later `/speckit-tasks` / implement phases — this guide is validation-oriented.

## Prerequisites

- Docker + Docker Compose available on the lab host
- Supabase project (or local Supabase) with existing migration applied, plus the new red/blue migration from [data-model.md](./data-model.md)
- Root `.env` populated from `.env.example` (see [contracts/env.md](./contracts/env.md)):
  - DB credentials **only** for `api_service`
  - `SUPABASE_JWT_SECRET` (or JWKS) for API JWT validation
  - Distinct `RED_SERVICE_TOKEN` / `BLUE_SERVICE_TOKEN`
  - **`OPENAI_API_KEY` and `LLM_MODEL` for both `red_team_backend` and `blue_team_backend`**
  - `VITE_API_BASE_URL` for `secure_dash`
- Optional: HexStrike / CAI reachable; otherwise enable worker **mock/stub** mode (`LLM_STUB=1` for LLM)

## Setup

```bash
# from repo root
cp .env.example .env   # fill OPENAI_API_KEY, LLM_MODEL, DB, tokens — never commit .env
docker compose up -d --build api_service red_team_backend blue_team_backend
# apply migrations via your usual Supabase workflow
cd secure_dash && npm run dev   # or bun / project standard
```

Confirm workers received LLM env (without printing secrets):

```bash
docker compose exec red_team_backend printenv LLM_MODEL
docker compose exec blue_team_backend printenv LLM_MODEL
# OPENAI_API_KEY should be set in both; must NOT appear on api_service
```

Health expectations:

```bash
curl -sf http://localhost:8000/api/v1/health
curl -sf http://localhost:8000/api/v1/ready
# red/blue health ports per compose (document in root README when added)
```

## Validation scenarios

### V1 — API auth + asset CRUD (S0/S1)

1. Without token: `POST /api/v1/assets` → **401**.
2. With valid analyst JWT: create asset → **201**; `GET /assets` returns it.
3. Confirm UI dashboard/assets load via API (no business-table `supabase.from` writes).

**Pass**: SC-001 (partial), FR-001 smoke.

### V2 — AuthZ boundaries

1. Service token `POST /findings` → **201**.
2. Service token `DELETE /assets/{id}` → **403**.
3. Service token role mutation → **403**.
4. Analyst JWT must not satisfy service-only routes if separated.

**Pass**: SC-005 / FR-004 / FR-013.

### V3 — Red surface-recon job (S2)

1. Sign in to UI → Scans → select assets → team **red** → profile **surface-recon** → start.
2. Observe job/scans transition queued → dispatched/running → completed (within job timeout).
3. At least one finding or threat_event visible; Realtime refresh without full reload on Threats.

**Pass**: SC-003, SC-006.

Equivalent API:

```http
POST /api/v1/jobs
Authorization: Bearer <jwt>
Content-Type: application/json

{"team":"red","profile":"surface-recon","asset_ids":["<asset-uuid>"]}
```

Empty `asset_ids` → **422** (see [contracts/openapi.yaml](./contracts/openapi.yaml)).

### V4 — Blue scan + patch (S3)

1. Start blue `vuln-scan` job → blue-attributed finding with `source_tool`.
2. Patches page: propose patch → status `proposed`.
3. Apply success → patch `applied`, finding `remediated`.
4. (Optional) force apply failure → patch `failed`, finding stays open.

**Pass**: SC-004 / FR-008 / FR-009.

### V5 — Team filters (S2/S3)

1. Ensure mixed red/blue events exist.
2. Filter Threats/Findings/KPIs by team — no cross-team leakage in filtered view.

**Pass**: SC-007.

### V6 — Safety allowlist (S2+/S5)

1. Configure allowlist excluding a target asset.
2. Start red job including that asset.
3. Expect guardrail threat_event; zero exploit/destructive tool calls in demo/safe mode.

**Pass**: SC-008 / FR-014.

### V7 — Isolation review

```bash
# example checks once compose exists
grep -R "DATABASE_URL\|SERVICE_ROLE" red_team_backend blue_team_backend || true
# expect matches only under api_service / docs examples that are not runtime env for workers
```

**Pass**: SC-002 / FR-003.

### V8 — Compose smoke (S0+)

`docker compose up` → API + red + blue health **200**.

**Pass**: SC-009.

### V9 — Contract alignment (S1+)

- OpenAPI in [contracts/openapi.yaml](./contracts/openapi.yaml) matches implemented routes.
- UI job-create payload matches `JobCreate` schema.

**Pass**: SC-011.

### V10 — Automated suite (S5)

Run API/worker pytest suites and UI gate checks covering cases listed in root architecture acceptance/tests; CI green.

**Pass**: SC-012.

## References

- [spec.md](./spec.md) — requirements & success criteria  
- [data-model.md](./data-model.md) — entities & transitions  
- [contracts/README.md](./contracts/README.md) — API surface  
- [research.md](./research.md) — locked technical decisions  
- Root `plan.md` — stage exit gates S0–S5  
