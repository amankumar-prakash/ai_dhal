# Tasks: Supabase as Primary Data & Auth Platform

**Input**: Design documents from `/specs/003-supabase-primary-db/`

**Prerequisites**: plan.md (signing-keys delta), spec.md, research.md, data-model.md, contracts/ (`env.md`, `supabase-access.md`), quickstart.md

**Tests**: Not mandated as TDD in spec; include focused verification tasks where SC/quickstart require them (JWKS mock, store selection, migration probes).

**Organization**: By user story (US1–US5). Prefer JWKS + secret API key; legacy JWT secret only as deprecated fallback.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Parallelizable (different files)
- **[Story]**: [US1]–[US5] on story phases only

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm deps, env templates, and docs for Supabase-primary + signing keys

- [X] T001 Verify `supabase>=2.10.0` in `api_service/requirements.txt` and install into project venv
- [X] T002 [P] Align root `.env.example` with `specs/003-supabase-primary-db/contracts/env.md` (`SUPABASE_SECRET_KEY`, JWKS notes, deprecated `SUPABASE_JWT_SECRET`)
- [X] T003 [P] Align `secure_dash/.env` / example vars to publishable-only keys (no secret/service_role); sync `VITE_SUPABASE_*` with project URL
- [X] T004 [P] Update root `README.md` Apply-migrations + Auth (JWKS) sections to match quickstart.md

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Config, JWKS verifier, supabase client, store switch — BLOCKS all stories

**⚠️ CRITICAL**: Complete before user stories

- [X] T005 Extend `api_service/app/config.py` for `supabase_secret_key` (alias `supabase_service_role_key`), optional `supabase_jwks_url`, deprecate required JWT secret
- [X] T006 [P] Implement JWKS loader/verifier in `api_service/app/auth/jwks.py` using PyJWT `PyJWKClient` against `{SUPABASE_URL}/auth/v1/.well-known/jwks.json` per `contracts/supabase-access.md`
- [X] T007 Wire `api_service/app/deps.py` to verify user Bearer tokens via JWKS (algs from keys); keep optional HS256 fallback only if `SUPABASE_JWT_SECRET` set
- [X] T008 Harden `api_service/app/db/supabase_client.py` to `create_client(url, secret_key)` and clear errors when secret missing under `API_STORE=supabase`
- [X] T009 Add store facade `api_service/app/db/store.py` selecting memory vs supabase from `API_STORE`
- [X] T010 Update `api_service/app/main.py` `/api/v1/ready` to fail clearly when `API_STORE=supabase` and URL/secret missing; optional JWKS reachability soft-check
- [X] T011 [P] Add `api_service/tests/test_jwks_auth.py` with mocked JWKS / tokens (ES256 or fixture) proving HS256-only path is not required

**Checkpoint**: Config + JWKS + client ready; memory still works for unit tests; ready endpoint gates supabase mode

---

## Phase 3: User Story 1 — Persist data in shared store (Priority: P1) 🎯 MVP

**Goal**: API CRUD for business entities uses Supabase Postgres via supabase-py; data survives API restart

**Independent Test**: Create asset via API with JWT → restart API → asset still listed (`API_STORE=supabase`)

### Implementation for User Story 1

- [X] T012 [US1] Implement Supabase-backed asset CRUD in `api_service/app/db/supabase_store.py` (or module under `app/db/`) mapping to `assets` table
- [X] T013 [US1] Route `api_service/app/services/crud.py` asset/scan/finding/threat_event/job/patch/chain/role/tool_run helpers through store facade (supabase when selected)
- [X] T014 [US1] Ensure UUID/datetime JSON serialization matches PostgREST responses in `api_service/app/schemas/models.py` as needed
- [X] T015 [US1] Keep `api_service/app/db/memory.py` as explicit `API_STORE=memory` path for pytest without cloud
- [X] T016 [US1] Confirm `secure_dash/src/lib/api-client.ts` + `security.ts` still load lists via API (no regression to `supabase.from` business writes)
- [ ] T017 [US1] Smoke: document restart persistence check in `specs/003-supabase-primary-db/quickstart.md` §4 and run once against configured project

**Checkpoint**: US1 MVP — durable assets/jobs path via API when supabase mode + migrations applied

---

## Phase 4: User Story 2 — Platform identity + JWKS (Priority: P1)

**Goal**: UI Auth + API verifies access tokens via signing keys; secret key never in browser

**Independent Test**: Sign in → protected API 200; no token → 401; grep UI env for secret key → absent

### Implementation for User Story 2

- [X] T018 [P] [US2] Audit `secure_dash/src/integrations/supabase/` uses publishable key only; document in `docs/api-contracts.md` or README
- [X] T019 [US2] Ensure `api_service/app/deps.py` maps `sub` + `app_metadata.role` / `authenticated` → analyst/admin as today after JWKS verify
- [X] T020 [P] [US2] Add `api_service/tests/test_auth_unauthorized.py` — missing Bearer → 401 on `/api/v1/assets`
- [X] T021 [US2] Align docker-compose `api_service` env with `SUPABASE_URL` + `SUPABASE_SECRET_KEY` (no JWT secret required) in `docker-compose.yml`
- [X] T022 [US2] Credential review checklist note in `specs/003-supabase-primary-db/quickstart.md` (no `VITE_*` secret key)

**Checkpoint**: US2 — JWKS auth path green without legacy JWT secret

---

## Phase 5: User Story 3 — Versioned migrations applied (Priority: P1)

**Goal**: Remote schema matches repo migrations (`jobs`, `patches`, `tool_runs`, team columns, RLS)

**Independent Test**: PostgREST `jobs`/`patches`/`tool_runs` not `PGRST205`; `scans?select=team` not `42703`

### Implementation for User Story 3

- [ ] T023 [US3] Apply `secure_dash/supabase/migrations/20260804120000_red_blue_platform.sql` to remote (Dashboard SQL or `scripts/apply_supabase_migrations.sh` with `DATABASE_URL`)
- [ ] T024 [P] [US3] Add `scripts/verify_supabase_schema.sh` probing jobs/patches/tool_runs/scans.team per `contracts/supabase-access.md`
- [ ] T025 [US3] Confirm RLS still enabled / browser cannot INSERT business rows with publishable key only (document expected error)
- [ ] T026 [P] [US3] Record apply/verify steps in `specs/003-supabase-primary-db/quickstart.md` §1 and §3 as pass/fail log

**Checkpoint**: US3 — remote schema ready for durable US1 E2E

---

## Phase 6: User Story 4 — Realtime after API writes (Priority: P2)

**Goal**: Threats/scans/findings live UI still invalidates when API writes to Supabase tables

**Independent Test**: Open Threats → API/worker inserts threat_event → UI updates without full reload

### Implementation for User Story 4

- [X] T027 [US4] Verify `secure_dash/src/hooks/use-realtime.ts` subscriptions still cover `threat_events`, `scans`, `findings` (and jobs/patches if published)
- [X] T028 [US4] Confirm migration publication includes needed tables; extend `secure_dash/supabase/migrations/` only if jobs/patches Realtime required and missing
- [ ] T029 [US4] Manual demo checklist entry in `specs/003-supabase-primary-db/quickstart.md` §5

**Checkpoint**: US4 — live updates OK with API→Supabase writes

---

## Phase 7: User Story 5 — Optional Storage (Priority: P3)

**Goal**: Evidence/files use Supabase Storage when introduced; core jobs work without Storage

**Independent Test**: Without bucket, scan/job flows succeed; with bucket, authorized upload/retrieve works

### Implementation for User Story 5

- [X] T030 [P] [US5] Design note + optional bucket name in `specs/003-supabase-primary-db/data-model.md` (evidence)
- [X] T031 [US5] Stub Storage helper `api_service/app/db/storage.py` (upload/signed URL) behind feature flag / unused until UI needs it
- [X] T032 [US5] Ensure job/scan pipelines do not require Storage (no hard dependency in `dispatch` / workers)

**Checkpoint**: US5 — Storage optional; MVP unaffected

---

## Phase 8: Polish & Cross-Cutting

- [X] T033 [P] Sync `docs/api-contracts.md` with JWKS + secret key ownership
- [X] T034 [P] Update `specs/001-red-blue-platform/contracts/env.md` pointer or note: JWT secret deprecated in favor of 003 contracts
- [ ] T035 Run full `specs/003-supabase-primary-db/quickstart.md` V0–V5; fix gaps
- [X] T036 [P] CI: keep API tests with `API_STORE=memory`; optional job for JWKS unit tests without live cloud in `.github/workflows/platform-tests.yml`
- [X] T037 Confirm workers still lack DB/secret keys in `docker-compose.yml` + `scripts/smoke_env_isolation.sh`

---

## Dependencies & Execution Order

### Phase Dependencies

- Setup → Foundational (**BLOCKS** stories)
- US1 after Foundational; **full E2E** also needs US3 migrations applied
- US2 after Foundational (can parallel US1)
- US3 after Foundational (can parallel US2; should precede durable US1 demo)
- US4 after US1 writes hit Supabase
- US5 last (optional)
- Polish last

### User Story Dependencies

- **US1**: Store facade + client; migrations for real project E2E
- **US2**: JWKS module; no dependency on US1 data
- **US3**: Migration files already in repo; operator/credentials
- **US4**: US1 API inserts + existing UI realtime hook
- **US5**: Independent optional stub

### Parallel Opportunities

- T002/T003/T004 Setup docs
- T006 JWKS module while T008 client hardening (after T005 config)
- US2 + US3 in parallel after Phase 2
- T024 verify script || T018 UI audit

---

## Parallel Example: Foundational

```bash
Task: "api_service/app/auth/jwks.py JWKS verifier"
Task: "api_service/app/db/supabase_client.py secret key client"
Task: "api_service/tests/test_jwks_auth.py mocked keys"
```

## Parallel Example: US2 + US3

```bash
Task: "deps.py JWKS principal mapping"
Task: "scripts/verify_supabase_schema.sh"
Task: "Apply 20260804120000_red_blue_platform.sql"
```

---

## Implementation Strategy

### MVP First

1. Setup + Foundational (JWKS + client + store facade)  
2. US3 apply migrations  
3. US2 auth verify  
4. US1 supabase CRUD  
5. **STOP** — restart persistence demo  

### Incremental

US3 → US2 → US1 → US4 → US5 → Polish  

### Must not drop

- JWKS primary verify ([signing keys](https://supabase.com/docs/guides/auth/signing-keys))  
- Secret/publishable API key split  
- `API_STORE=memory` for offline pytest  
- Workers: no Supabase secret  

---

## Notes

- Suggested MVP: **Phases 1–5 (US1+US2+US3)**  
- US5 is stub-level unless evidence upload is scheduled  
- Format: `- [ ] Txxx [P?] [USn?] …` with file paths  
