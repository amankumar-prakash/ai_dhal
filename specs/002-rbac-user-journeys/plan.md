# Implementation Plan: SentryOps Role-Based User Journeys (+ live tools)

**Branch**: `002-rbac-user-journeys` | **Date**: 2026-08-05 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-rbac-user-journeys/spec.md` (Clarifications 2026-08-04)  
**Plus delivery deltas (2026-08-05)**: (1) implement Admin/Manager/Analyst UI that is missing today; (2) seed `TEST_USERNAME`/`TEST_PASSWORD` from root `.env` as first Admin; (3) replace red/blue worker **stubs** with live HexStrike + CAI job tooling.

**Note**: Re-planned after platform moved to `api_service` + Supabase primary (003). Prior 002 plan assumed more direct Supabase RLS from the browser; this plan routes AuthZ and ops data through the API while keeping route guards in `secure_dash`.

## Summary

Deliver the **four-role Access Matrix** in `secure_dash` (Admin Panel, Tasks, conditional Red/Blue tool pages, forced password change) with roles persisted in Postgres (`profiles` + extended `user_roles`) and enforced by **API principal resolution** + TanStack route guards. Bootstrap the first Admin from root env test credentials (out-of-band). Wire `red_team_backend` / `blue_team_backend` adapters to **live** HexStrike HTTP (`:8888`) and CAI for deep profiles so Scan “Start run” / task tool pages execute real jobs (still gated by allowlist + `DEMO_SAFE_MODE`).

## Technical Context

**Language/Version**: TypeScript / React 19 (`secure_dash`); Python 3.12 (`api_service`, `red_team_backend`, `blue_team_backend`)

**Primary Dependencies**: `@supabase/supabase-js` (Auth); TanStack Start/Router/Query; FastAPI; supabase-py; httpx → HexStrike Flask API; CAI (`cai_pentesting` / `uv run cai`) for deep-emulation planning

**Storage**: Supabase Postgres — extend `app_role`; add `profiles`, `tasks`, `task_notes`, `task_links`, `task_audit_events`, `notifications`; keep 001 tables; API uses secret key; browser never gets secret

**Testing**: Matrix allow/deny scripts; unlock predicate unit tests; bootstrap-admin smoke; live-tool integration tests with `HEXSTRIKE_STUB=0` against lab allowlist (or recorded fixtures); pytest workers with stub flag for CI

**Target Platform**: Lab monorepo — Compose API/workers + Vite UI; sibling HexStrike + CAI on host

**Project Type**: Web app + API workers integrating external tool servers

**Performance Goals**: Admin user list and task board interactive under lab volumes; tool jobs stream status via existing job/scan PATCH path

**Constraints**: Admin identity-only (no ops pages); service role never in browser; first Admin out-of-band only; HexStrike/CAI only against `TARGET_ALLOWLIST`; `DEMO_SAFE_MODE=1` blocks destructive profiles; no exploit PoCs in repo

**Scale/Scope**: Four roles; Admin/Tasks/tools routes; notes/links; live recon (HexStrike) + deep plan (CAI); blue vuln path may use HexStrike nuclei/trivy endpoints where available

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution template unfilled — gates from clarified spec + delivery deltas:

| Gate | Status |
|------|--------|
| Access Matrix canonical | PASS |
| Admin ops-data isolation | PASS |
| Tool unlock = any matching In Progress type | PASS |
| Out-of-band first Admin; Admin may manage Admins | PASS |
| Manager Complete/Reviewed/Closed; Analyst cannot Reviewed/Closed | PASS |
| Notes + optional links | PASS |
| API owns business CRUD (003) | PASS — roles/tasks via `api_service` |
| Live tools (no silent stubs in lab default) | PASS — stubs only when `*_STUB=1` for CI |
| Secrets isolation (DB on API; LLM/HexStrike/CAI on workers) | PASS |

**Post-Phase 1 re-check**: PASS — data-model/contracts/quickstart encode clarify + live-tool + TEST_USER bootstrap.

## Project Structure

### Documentation (this feature)

```text
specs/002-rbac-user-journeys/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
└── tasks.md              # regenerate via /speckit-tasks after this plan
```

### Source Code (repository root)

```text
secure_dash/
├── supabase/migrations/<ts>_rbac_user_journeys.sql
├── src/lib/{access-matrix,roles,tasks,notifications}.ts
├── src/lib/admin-provision.server.ts
├── src/components/{admin,tasks,auth}/
└── src/routes/_authenticated/
    ├── admin.tsx | tasks*.tsx | tools.red.tsx | tools.blue.tsx
    └── (existing ops routes guarded)

scripts/
├── bootstrap_admin.py          # reads root .env TEST_USERNAME/TEST_PASSWORD
└── verify_rbac_matrix.sh

api_service/app/
├── deps.py                     # resolve role from user_roles (not JWT only)
├── routers/{roles,tasks,me}.py
└── services/crud.py            # profiles/tasks/roles

red_team_backend/app/adapters/
├── hexstrike_client.py         # HTTP → HEXSTRIKE_BASE_URL (live)
└── cai_client.py               # live CAI invoke (subprocess/API)

blue_team_backend/app/adapters/
└── hexstrike_client.py         # nuclei/trivy via HexStrike when configured
```

**Structure Decision**: RBAC UI in `secure_dash`; AuthZ source of truth in API + DB; workers call sibling HexStrike/CAI over HTTP/process; bootstrap script at repo `scripts/`.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Four roles + Admin identity-only | Spec matrix | Merging Manager into Admin violates ops isolation |
| Task notes/links tables | FR-017 | Status-only incomplete |
| Live HexStrike/CAI from workers | User delivery delta; stubs fake success | Keeping stubs fails real job validation |
| Dual AuthZ (guards + API) | FR-001 + 003 API-primary | UI-only or RLS-only insufficient |

## Clarification + delivery deltas

1. Admin may create/demote/disable Admins including last → no last-Admin guard  
2. Tool unlock = union of In Progress task types  
3. `task_notes` + `task_links`  
4. Bootstrap Admin via `TEST_USERNAME`/`TEST_PASSWORD` in **root** `.env` (also ensure Auth user exists + `user_roles.admin` + profile)  
5. Manager Complete/Reviewed/Closed on any task; Analyst Block/Complete own only  
6. **Live tools**: `HEXSTRIKE_BASE_URL` (default `http://host.docker.internal:8888`); CAI via configured command/env; `HEXSTRIKE_STUB`/`CAI_STUB`/`LLM_STUB` only for CI  
7. Principal role from **`user_roles` table** (service lookup), with JWT `app_metadata.role` as optional override for break-glass  
