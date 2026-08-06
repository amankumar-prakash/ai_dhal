# Tasks: Red/Blue Security Platform

**Input**: Design documents from `/specs/001-red-blue-platform/`

**Prerequisites**: plan.md (2026-08-04 LLM delta), spec.md, research.md, data-model.md, contracts/ (incl. `env.md`), quickstart.md

**Tests**: Included — SC-012 / root acceptance suite and AuthZ cases are explicit in the feature.

**Organization**: By user story (US1–US6). LLM keys from root `.env` → red + blue workers only (`contracts/env.md`).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Parallelizable (different files)
- **[Story]**: [US1]–[US6] on story phases only

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Monorepo scaffolds, Compose, `.env.example` with LLM + DB ownership

- [X] T001 Create `api_service/` layout (`app/main.py`, `deps.py`, `routers/`, `schemas/`, `services/`, `db/`, `tests/`, `Dockerfile`, `requirements.txt`) per plan.md
- [X] T002 [P] Scaffold `red_team_backend/` (`app/main.py`, `routers/jobs.py`, `adapters/`, `pipelines/`, `reporters/`, `tests/`, `Dockerfile`, `requirements.txt`)
- [X] T003 [P] Scaffold `blue_team_backend/` (`app/main.py`, `routers/jobs.py`, `adapters/`, `pipelines/`, `reporters/`, `tests/`, `Dockerfile`, `requirements.txt`)
- [X] T004 [P] Add root `docker-compose.yml` for `api_service`, `red_team_backend`, `blue_team_backend` with healthchecks; **no DB env on workers**; inject `OPENAI_API_KEY` + `LLM_MODEL` into red and blue only per `specs/001-red-blue-platform/contracts/env.md`
- [X] T005 [P] Ensure root `.env.example` documents API-only DB/JWT vars, service tokens, **`OPENAI_API_KEY` + `LLM_MODEL` (+ optional `LLM_BASE_URL` / `LLM_STUB`) for workers**, `VITE_API_BASE_URL`, allowlist, `DEMO_SAFE_MODE` (placeholders only; never commit real keys)
- [X] T006 [P] Create `docs/api-contracts.md` linking OpenAPI + `contracts/env.md`; stub `docs/threat-model.md`
- [X] T007 Update root `README.md` with architecture, Compose runbook, and secret placement (DB→API; LLM→workers)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Schema, API auth/DB, health, worker LLM settings loaders — BLOCKS all stories

**⚠️ CRITICAL**: Complete before user stories

- [X] T008 Write `secure_dash/supabase/migrations/<ts>_red_blue_platform.sql` for enums/tables/RLS per `data-model.md`
- [X] T009 Implement API config/DB access in `api_service/app/db/` (DB credentials only here)
- [X] T010 [P] Implement JWT + service-token deps in `api_service/app/deps.py`
- [X] T011 [P] Implement shared Pydantic schemas in `api_service/app/schemas/` aligned to `contracts/openapi.yaml`
- [X] T012 Implement health/ready in `api_service/app/main.py` and router registration skeleton
- [X] T013 [P] Add worker health endpoints in `red_team_backend/app/main.py` and `blue_team_backend/app/main.py`
- [X] T014 [P] Add LLM settings modules `red_team_backend/app/settings.py` and `blue_team_backend/app/settings.py` loading `OPENAI_API_KEY`, `LLM_MODEL`, optional `LLM_BASE_URL` / `LLM_STUB` (fail clearly if live mode missing key)
- [X] T015 [P] Add shared OpenAI-compatible LLM client stub/wrapper in `red_team_backend/app/adapters/llm_client.py` and `blue_team_backend/app/adapters/llm_client.py` (honor `LLM_STUB=1`)
- [X] T016 Add pytest baseline `api_service/tests/conftest.py` and worker conftest fixtures that mock LLM

**Checkpoint**: Compose up; API health/ready; workers see `LLM_MODEL` without DB env; stubs work without live key when `LLM_STUB=1`

---

## Phase 3: User Story 1 — Analyst manages data via platform API (Priority: P1) 🎯 MVP

**Goal**: JWT CRUD for entities; UI via `api-client`; Auth + Realtime only on Supabase

**Independent Test**: Sign in → assets CRUD via API; unauthenticated 401; no business-table browser writes

### Tests for User Story 1

- [X] T017 [P] [US1] `api_service/tests/test_assets_auth.py` — JWT vs anonymous
- [X] T018 [P] [US1] `api_service/tests/test_scans_authz.py` — admin vs analyst delete
- [X] T019 [P] [US1] `api_service/tests/test_rls_writes_denied.py` — authenticated cannot insert business rows via PostgREST

### Implementation for User Story 1

- [X] T020 [P] [US1] CRUD service in `api_service/app/services/crud.py` for assets, scans, findings, threat_events, chains/steps, roles
- [X] T021 [P] [US1] Routers `api_service/app/routers/assets.py`, `scans.py`, `findings.py`, `threat_events.py`, `attack_chains.py`, `roles.py`
- [X] T022 [US1] Register US1 routers in `api_service/app/main.py`
- [X] T023 [US1] Create `secure_dash/src/lib/api-client.ts` (`VITE_API_BASE_URL` + access token)
- [X] T024 [US1] Refactor `secure_dash/src/lib/security.ts` to API (no business `supabase.from` writes/reads)
- [X] T025 [US1] Audit `secure_dash/src/` — Supabase only for auth + Realtime; dashboard routes load via API

**Checkpoint**: US1 MVP — dashboard API-backed

---

## Phase 4: User Story 2 — Red-team reconnaissance job (Priority: P1)

**Goal**: Jobs + dispatch; red `surface-recon` (HexStrike stub OK); findings/events in UI; LLM client available for later profiles

**Independent Test**: UI red job → completed with ≥1 finding; empty assets → 422; red has no DB creds; LLM env present or stubbed

### Tests for User Story 2

- [X] T026 [P] [US2] `api_service/tests/test_jobs_create.py` — create job+scans; reject empty `asset_ids`
- [X] T027 [P] [US2] `red_team_backend/tests/test_surface_recon.py` — mock HexStrike → finding payload
- [X] T028 [P] [US2] `red_team_backend/tests/test_api_reporter.py` — retry on 503
- [X] T029 [P] [US2] `red_team_backend/tests/test_llm_settings.py` — settings load `LLM_MODEL`; stub mode skips live calls

### Implementation for User Story 2

- [X] T030 [US2] Jobs router + cancel/409 in `api_service/app/routers/jobs.py` and CRUD helpers
- [X] T031 [US2] Dispatch in `api_service/app/services/dispatch.py` to red `/internal/jobs` per `contracts/internal-jobs.md`
- [X] T032 [US2] On create: `jobs` + `scans` then dispatch
- [X] T033 [P] [US2] `red_team_backend/app/reporters/api_reporter.py` (service token, retry)
- [X] T034 [P] [US2] `red_team_backend/app/adapters/hexstrike_client.py` stub/client
- [X] T035 [US2] `red_team_backend/app/pipelines/surface_recon.py` writing findings/events via reporter
- [X] T036 [US2] `red_team_backend/app/routers/jobs.py` `POST /internal/jobs` profile routing
- [X] T037 [US2] Change `secure_dash/src/lib/scan.functions.ts` to `POST /api/v1/jobs`
- [X] T038 [US2] Red team/profile controls on `secure_dash/src/routes/_authenticated/scans.tsx`

**Checkpoint**: US2 red job E2E with stub tools; LLM settings ready

---

## Phase 5: User Story 6 — Safe isolation & boundaries (Priority: P1)

**Goal**: DB isolation; service-token least privilege; allowlist/guardrails; Compose health; confirm LLM not on API/UI

**Independent Test**: Only API has DB secrets; workers have LLM not DB; service token cannot delete assets; out-of-scope → guardrail; health 200

### Tests for User Story 6

- [X] T039 [P] [US6] `api_service/tests/test_service_token_authz.py`
- [X] T040 [P] [US6] `red_team_backend/tests/test_allowlist_guardrail.py`
- [X] T041 [P] [US6] Compose/env smoke: API lacks `OPENAI_API_KEY`; workers lack `DATABASE_URL` — `scripts/smoke_env_isolation.sh` or `api_service/tests/test_compose_health.py`

### Implementation for User Story 6

- [X] T042 [US6] Enforce service-token capability matrix in `api_service/app/deps.py` + routers
- [X] T043 [US6] Allowlist + `DEMO_SAFE_MODE` gating in `red_team_backend/app/` before tool/LLM exploit paths; emit `blocked_by_guardrail` events
- [X] T044 [US6] Document and enforce Compose env isolation in `docker-compose.yml` + `README.md` (DB→API; LLM→workers)
- [X] T045 [US6] Finalize healthchecks for api/red/blue in `docker-compose.yml`

**Checkpoint**: US6 safety + secret placement green

---

## Phase 6: User Story 3 — Blue scan + patches (Priority: P2)

**Goal**: Blue vuln_scan (LLM-capable settings); patches propose/apply → remediated

**Independent Test**: Blue job → blue finding; propose/apply patch; blue has `LLM_MODEL` or stub

### Tests for User Story 3

- [X] T046 [P] [US3] `blue_team_backend/tests/test_vuln_scan.py`
- [X] T047 [P] [US3] `api_service/tests/test_patches.py`
- [X] T048 [P] [US3] `blue_team_backend/tests/test_patch_pipeline.py`
- [X] T049 [P] [US3] `blue_team_backend/tests/test_llm_settings.py` — same env contract as red

### Implementation for User Story 3

- [X] T050 [P] [US3] `api_service/app/routers/patches.py` (`applied` → finding `remediated`)
- [X] T051 [US3] Extend dispatch for `team=blue` in `api_service/app/services/dispatch.py`
- [X] T052 [P] [US3] `blue_team_backend/app/reporters/api_reporter.py`
- [X] T053 [P] [US3] Vuln adapters + `pipelines/vuln_scan.py` (may call `llm_client` when not stubbed)
- [X] T054 [P] [US3] `pipelines/patch.py` propose/dry-run/apply
- [X] T055 [US3] `blue_team_backend/app/routers/jobs.py` for blue profiles
- [X] T056 [US3] Blue launcher on `scans.tsx` + Patches route under `secure_dash/src/routes/_authenticated/`

**Checkpoint**: US3 blue MVP + patches

---

## Phase 7: User Story 4 — Team filters + live updates (Priority: P2)

**Goal**: `?team=` filters; Realtime after API writes

**Independent Test**: Filter red/blue; new threat_event via API refreshes UI

### Tests for User Story 4

- [X] T057 [P] [US4] `api_service/tests/test_team_filters.py`

### Implementation for User Story 4

- [X] T058 [US4] Team query params on list routers in `api_service/app/routers/`
- [X] T059 [US4] Team filters on `threats.tsx` / dashboard KPIs via `security.ts`
- [X] T060 [US4] Confirm `use-realtime.ts` still invalidates on API-originated inserts

**Checkpoint**: US4 filters + live OK

---

## Phase 8: User Story 5 — Deep profiles, monitors, chains (Priority: P3)

**Goal**: CAI/deep red using LLM client; blue monitor; attack_chain builder

**Independent Test**: Deep red builds chain; monitor tick creates blue event; seeded attack-chain page OK

### Tests for User Story 5

- [X] T061 [P] [US5] `blue_team_backend/tests/test_monitor.py`
- [X] T062 [P] [US5] `red_team_backend/tests/test_mitre_mapping.py`
- [X] T063 [P] [US5] `red_team_backend/tests/test_llm_client_stub.py` — deep pipeline uses stub LLM without network

### Implementation for User Story 5

- [X] T064 [P] [US5] `red_team_backend/app/adapters/cai_client.py` (HTTP to sibling CAI; uses worker LLM settings as needed)
- [X] T065 [P] [US5] `deep_emulation` / `defensive_validation` pipelines in `red_team_backend/app/pipelines/`
- [X] T066 [US5] Attack_chain builder via reporter/helpers
- [X] T067 [US5] `blue_team_backend/app/pipelines/monitor.py` (+ optional LLM assist via `llm_client`)
- [X] T068 [US5] Expose deep/monitor profiles on `scans.tsx`; verify `attack-chain.tsx` regression

**Checkpoint**: US5 kill-chain / monitor demo

---

## Phase 9: Polish & Cross-Cutting (S5)

- [X] T069 [P] Tool-runs endpoint + worker emission in `api_service` routers + red/blue reporters
- [X] T070 [P] Rate limiting on `api_service/app/main.py` for job create
- [X] T071 Expand pytest to remaining acceptance cases (cancel 409, failed tool, OpenAPI JobCreate) under `api_service/tests/` and worker `tests/`
- [X] T072 [P] CI workflow running API/worker tests with `LLM_STUB=1` + compose health smoke
- [X] T073 [P] Sync `docs/`, root `README.md` with ports/env (LLM on workers)
- [X] T074 Run `specs/001-red-blue-platform/quickstart.md` V1–V10 including LLM env checks; fix gaps
- [X] T075 [P] Confirm UI `JobCreate` types match `contracts/openapi.yaml`

---

## Dependencies & Execution Order

### Phase Dependencies

- Setup → Foundational (**BLOCKS** stories)
- US1 after Foundational — MVP
- US2 after Foundational; UI api-client from US1 recommended
- US6 with/after US2 (isolation + allowlist)
- US3 after jobs/dispatch (US2)
- US4 after US1 lists; best after US2/US3 data
- US5 after US2/US3 pipelines + LLM client
- Polish last

### User Story Dependencies

- **US1**: No other stories
- **US2**: Jobs schema + auth; LLM settings from Foundational
- **US6**: Auth matrix + red pipeline hooks; env isolation
- **US3**: Dispatch pattern; blue LLM settings
- **US4**: API list endpoints
- **US5**: Workers + LLM client

### Parallel Opportunities

- T002/T003/T004/T005 Setup
- T014/T015 LLM settings+clients on red/blue
- US1 routers after crud service
- US2 reporter/HexStrike in parallel
- US3 blue adapters in parallel

---

## Parallel Example: Setup / Foundational LLM

```bash
Task: "red_team_backend/app/settings.py + llm_client.py"
Task: "blue_team_backend/app/settings.py + llm_client.py"
Task: "docker-compose.yml LLM env for workers only"
```

## Parallel Example: User Story 2

```bash
Task: "red_team_backend/app/reporters/api_reporter.py"
Task: "red_team_backend/app/adapters/hexstrike_client.py"
Task: "api_service/tests/test_jobs_create.py"
```

---

## Implementation Strategy

### MVP First

1. Setup + Foundational (incl. LLM env wiring)  
2. US1 API-backed dashboard  
3. **STOP** — validate  

### Incremental

US1 → US2+US6 (red + safety + secret placement) → US3 → US4 → US5 → Polish  

### Env must-haves (do not drop)

- `OPENAI_API_KEY` + `LLM_MODEL` on **both** workers from root `.env`  
- Never on `api_service` or `VITE_*`  
- `LLM_STUB=1` for CI / offline tests  

---

## Notes

- Suggested MVP: **Phases 1–3 (US1)**  
- First offensive demo: **US1+US2+US6**  
- Prefer HexStrike/CAI/LLM stubs until S4 live wiring  
- Format: `- [ ] Txxx [P?] [USn?] …` with file paths  
