# Implementation Plan: Red/Blue Security Platform

**Branch**: `001-red-blue-platform` | **Date**: 2026-08-04 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-red-blue-platform/spec.md` plus plan delta: *red and blue workers require LLM keys provided via root `.env`*.

**Note**: Re-planned 2026-08-04 to lock worker LLM configuration.

## Summary

Introduce a monorepo platform where **`api_service`** is the sole database reader/writer for operational security data; **`secure_dash`** performs business CRUD and job starts only via that API; **`red_team_backend`** and **`blue_team_backend`** execute offensive/defensive pipelines (including LLM-backed reasoning where profiles need it) and report results with service-token auth. **LLM API keys and model id are supplied from the root `.env` and injected only into red/blue worker containers**—never into the browser, and not required on `api_service`. Delivery follows stages S0–S5.

## Technical Context

**Language/Version**: Python 3.12 (api_service, red_team_backend, blue_team_backend); TypeScript / React 19 (secure_dash via Vite + TanStack Start)

**Primary Dependencies**: FastAPI + Pydantic + httpx (API & workers); supabase-py or asyncpg (API DB access); existing `@supabase/supabase-js`, TanStack Query/Router, Zod (UI); HexStrike HTTP/MCP + CAI (red); LLM provider SDK/HTTP (OpenAI-compatible) on **both** workers; nuclei/trivy-style adapters (blue, stubbable)

**Storage**: Supabase Postgres (existing + red/blue migration); RLS SELECT-only for browser on operational tables

**Testing**: pytest (API + workers); worker tests may mock LLM; compose health; contract checks against OpenAPI

**Target Platform**: Linux (Kali/dev lab); Docker Compose local orchestration

**Project Type**: Multi-service web monorepo (API + two workers + existing dashboard)

**Performance Goals**: Interactive analyst console under lab volumes; job progress visible within seconds of worker patches

**Constraints**: Only `api_service` holds DB credentials; workers have **no** DB credentials but **do** receive `OPENAI_API_KEY` (or provider equivalent) + `LLM_MODEL` from `.env` via Compose; UI never gets LLM keys; allowlist + demo/safe mode for red; service token least privilege

**Scale/Scope**: One local deployment; stages S0–S5; sibling HexStrike/CAI over HTTP; LLM used by red (CAI/deep profiles) and blue (monitor/reasoning assistants as designed)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution template unfilled — informal gates:

| Gate | Status |
|------|--------|
| Single DB owner (`api_service` only) | PASS |
| UI business data via platform API only | PASS |
| Workers report via service token with least privilege | PASS |
| LLM secrets only on workers (from `.env`), not UI/DB | PASS |
| Safety: allowlist + guardrail events in demo mode | PASS |
| Testable acceptance | PASS |

**Post-Phase 1 re-check**: PASS — env contract documents LLM vars for red/blue only; DB isolation unchanged.

## Project Structure

### Documentation (this feature)

```text
specs/001-red-blue-platform/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
pentesting_ui/
├── docker-compose.yml
├── .env.example
├── README.md
├── docs/
│   ├── api-contracts.md          # human summary; OpenAPI source of truth in specs/.../contracts
│   └── threat-model.md
├── api_service/
│   ├── app/
│   │   ├── main.py
│   │   ├── deps.py               # JWT + service-token auth
│   │   ├── routers/              # assets, scans, findings, threat_events, attack_chains, jobs, patches, roles
│   │   ├── schemas/
│   │   ├── services/             # crud.py, dispatch.py
│   │   └── db/
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
├── red_team_backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── routers/jobs.py
│   │   ├── adapters/             # cai_client, hexstrike_client
│   │   ├── pipelines/            # surface_recon, deep_emulation, defensive_validation
│   │   └── reporters/api_reporter.py
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
├── blue_team_backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── routers/jobs.py
│   │   ├── adapters/
│   │   ├── pipelines/            # vuln_scan, monitor, patch
│   │   └── reporters/api_reporter.py
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
└── secure_dash/                  # EXISTING
    ├── src/lib/api-client.ts     # NEW
    ├── src/lib/security.ts       # CHANGE — API instead of supabase.from for business tables
    ├── src/lib/scan.functions.ts # CHANGE — POST jobs via API
    ├── src/routes/...            # team filters, patches route
    └── supabase/migrations/      # existing + new red_blue_platform migration
```

**Structure Decision**: Multi-service monorepo matching the locked architecture in root `plan.md`. Existing `secure_dash` retained; `api_service` and `blue_team_backend` are new; `red_team_backend` folder exists and will be filled. Sibling HexStrike/CAI remain outside the monorepo.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Four runtime services (API + red + blue + UI) | Hard DB isolation and independent offensive/defensive tool runtimes | Single process with shared DB credentials would violate FR-003 and blur red/blue blast radius |
| Dual auth modes (analyst JWT + service token) | Workers must write results without acting as users | User JWT in workers would couple workers to interactive sessions and over-privilege them |

## Implementation Stages (delivery order)

| Stage | Scope | Exit gate |
|-------|-------|-----------|
| **S0** | Compose, `.env.example` (DB on API; LLM keys on red/blue), migration, API skeleton + auth | API health + JWT CRUD smoke on assets; workers start with LLM env present (or documented stub mode) |
| **S1** | All entity routers; OpenAPI; RLS tighten; UI reads via API | Dashboard loads without `supabase.from` for business tables |
| **S2** | Jobs + dispatch; red `surface-recon` (HexStrike stub OK) | UI red job → completed scan with ≥1 finding |
| **S3** | Blue vuln_scan + patches CRUD/UI | Blue job → finding + proposed patch; apply → remediated |
| **S4** | CAI deep profiles; blue monitor; attack_chain builder | Kill-chain demo end-to-end |
| **S5** | Allowlists, `tool_runs`, rate limits, CI suite | Spec success criteria / acceptance green |
