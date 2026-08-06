# Research: Red/Blue Security Platform

**Feature**: `001-red-blue-platform`  
**Date**: 2026-08-04  
**Status**: Complete — includes LLM key placement for workers (plan delta 2026-08-04)

## R1 — Central API as sole DB owner

- **Decision**: Implement `api_service` (FastAPI) as the only process with `SUPABASE_SERVICE_ROLE_KEY` / `DATABASE_URL`. Workers and UI never receive those secrets.
- **Rationale**: Spec FR-003/SC-002; prevents tool pipelines from becoming a DB blast radius; enables consistent AuthZ on all writes.
- **Alternatives considered**: Direct Supabase writes from UI (current pattern) — rejected for dual-write and weak worker integration; workers writing with service role — rejected as violates isolation.

## R2 — Auth model (analyst JWT + service token)

- **Decision**: Analysts call API with `Authorization: Bearer <supabase_access_token>`; API validates via Supabase JWT secret/JWKS. Workers use `X-Service-Token` (per-service shared secret). Service principals may insert/update findings, events, chains/steps, patches, tool_runs, job/scan status; may not delete assets or mutate `user_roles`.
- **Rationale**: Matches existing Supabase Auth in `secure_dash`; clear least-privilege split for automation.
- **Alternatives considered**: mTLS between services only — heavier for lab; embedding user JWT in workers — session coupling and over-privilege; PostgREST-only — insufficient for job dispatch orchestration.

## R3 — UI data path and Realtime

- **Decision**: Add `secure_dash/src/lib/api-client.ts` targeting `VITE_API_BASE_URL`. Refactor `security.ts` / `scan.functions.ts` (and related) off `supabase.from` for business tables. Keep Supabase client for Auth and Realtime subscribe on `threat_events`, `scans`, `findings` for live invalidation after API writes. Tighten RLS: authenticated SELECT-only (or equivalent); writes via API service role.
- **Rationale**: Preserves live Threat Detection UX (FR-012) without browser writes (FR-002).
- **Alternatives considered**: Polling-only UI — worse UX; SSE from API for all updates — duplicates Realtime already in place; full removal of Supabase client — would force reimplementing Auth.

## R4 — Job orchestration and dispatch

- **Decision**: `POST /api/v1/jobs` creates `jobs` row + related `scans` (`status=queued` → `dispatched`/`running`), then async HTTP `POST` to red or blue `/internal/jobs` with payload + callback base URL. Workers `PATCH` job/scan status and `POST` findings/events. Cancel sets `cancelled` and rejects conflicting writes with 409.
- **Rationale**: Simple lab-friendly orchestration without introducing a message broker in MVP.
- **Alternatives considered**: Redis/RQ/Celery — extra infra for S0–S2; DB listen/notify only — weaker worker push control; synchronous tool runs in API — couples API latency to scans.

## R5 — Red tooling integration

- **Decision**: Red pipelines call HexStrike (HTTP `:8888` / MCP) and CAI over HTTP adapters. S2 MVP uses HexStrike stub/mock for `surface-recon`; S4 wires CAI for deep-emulation / defensive-validation. Normalize outputs into findings + MITRE-tagged threat_events; emit `blocked_by_guardrail` when unsafe/out-of-scope.
- **Rationale**: Sibling repos already exist outside monorepo; stubs unblock UI/API acceptance.
- **Alternatives considered**: Shelling out to nmap directly in-repo only — loses HexStrike/CAI value; embedding CAI in-process — tighter coupling and harder isolation.

## R6 — Blue tooling and patches

- **Decision**: Blue `vuln_scan` adapters (nuclei/trivy-style, mockable) create `team=blue` findings; `monitor` emits blue threat_events; `patches` table + UI page for propose/apply; successful apply sets finding `remediated`.
- **Rationale**: Closes detect→remediate loop (User Story 3).
- **Alternatives considered**: Ticketing integration only — out of scope; auto-apply without propose — unsafe for lab demos.

## R7 — Schema strategy

- **Decision**: Keep existing enums/tables; add `team_side`, `job_status`, `patch_status`; alter scans/findings/threat_events/attack_chains with `team` (+ scan `job_id`, `source_service`; finding `source_tool`); add `jobs`, `patches`, `tool_runs`. Migration under `secure_dash/supabase/migrations/`.
- **Rationale**: FR-019 extend-not-replace; UI types already map to existing columns.
- **Alternatives considered**: Separate DB per team — overkill; replace scan model entirely — breaks seeded UI.

## R8 — Safety and hardening

- **Decision**: Configurable target allowlist enforced in red pipelines before exploit/recon beyond policy; demo/safe mode default so destructive actions only produce guardrail events. S5 adds rate limits, `tool_runs` audit completeness, CI for acceptance tests from root architecture plan.
- **Rationale**: FR-014/SC-008; dual-use tooling requires fail-closed scope.
- **Alternatives considered**: Trust analyst input alone — insufficient; live destructive demos by default — rejected.

## R9 — Local orchestration

- **Decision**: Root `docker-compose.yml` runs `api_service`, `red_team_backend`, `blue_team_backend` with healthchecks; UI optional (Vite dev outside or compose profile). Shared `.env.example` documents secrets placement: DB only on API; LLM vars on red/blue workers.
- **Rationale**: SC-009 / compose acceptance.
- **Alternatives considered**: Manual process managers only — fragile; K8s-first — overkill for lab.

## R10 — Contract and testing approach

- **Decision**: OpenAPI 3 contract in `specs/001-red-blue-platform/contracts/` is the source of truth for `/api/v1/*`; pytest covers authZ and job lifecycle; worker tests mock HexStrike/tools **and LLM** and assert API reporter behavior; UI contract alignment via shared job-create shape.
- **Rationale**: FR-018/SC-011/SC-012.
- **Alternatives considered**: Undocumented ad-hoc routes — rejected; GraphQL — unnecessary given CRUD + jobs shape.

## R11 — LLM keys for red and blue workers

- **Decision**: Both `red_team_backend` and `blue_team_backend` require LLM configuration from the **repository root `.env`**, passed through Compose `env_file` / `environment` into worker services only. Canonical vars (aligned with existing lab `.env`):
  - `OPENAI_API_KEY` — provider API key (required for live LLM calls)
  - `LLM_MODEL` — model id (e.g. `gpt-4o-mini`)
  - Optional later: `LLM_BASE_URL` for OpenAI-compatible gateways  
  Workers load these in app settings at startup. **Do not** put LLM keys on `api_service`, `secure_dash`, or browser `VITE_*` vars. **Do not** put `DATABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` on workers. Stub/mock mode may omit live calls in tests when `LLM_STUB=1` (or equivalent) is set.
- **Rationale**: User plan input — CAI/agent and blue reasoning pipelines need provider credentials; keeping keys on workers preserves DB isolation and avoids shipping secrets to the UI.
- **Alternatives considered**: LLM only on red — rejected (blue workers also require keys per user); keys only on API with workers proxying prompts — adds latency and expands API blast radius; keys in UI — rejected (secret leak).
