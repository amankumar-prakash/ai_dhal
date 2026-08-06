# Tasks: SentryOps Role-Based User Journeys (+ live tools)

**Input**: Design documents from `/specs/002-rbac-user-journeys/`

**Prerequisites**: plan.md (2026-08-05), spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included for matrix unlock / lifecycle AuthZ / bootstrap smoke (SC-001, SC-003, SC-012, V0/V7). Full TDD optional beyond listed tasks.

**Organization**: By user story + delivery deltas (bootstrap TEST_USER, live HexStrike/CAI).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Parallelizable (different files, no incomplete deps)
- **[Story]**: [US1]–[US5] on story phases; live-tools phase uses [LT]
- Paths are repo-absolute from monorepo root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Shared AuthZ helpers, types, folders, env docs

- [X] T001 Create `secure_dash/src/lib/access-matrix.ts` from `specs/002-rbac-user-journeys/contracts/access-matrix.json` (incl. `review_or_close_task`, `assign_admin_role`, unlock predicates)
- [X] T002 [P] Create `secure_dash/src/lib/roles.ts` with four-role constants and `hasRole` helpers
- [X] T003 [P] Create `secure_dash/src/lib/rbac-types.ts` for Profile, Task, TaskNote, TaskLink, Notification, TaskAuditEvent per `specs/002-rbac-user-journeys/data-model.md`
- [X] T004 [P] Scaffold `secure_dash/src/components/admin/`, `secure_dash/src/components/tasks/`, `secure_dash/src/components/auth/` directories
- [X] T005 [P] Ensure root `.env.example` documents `TEST_USERNAME`, `TEST_PASSWORD`, `HEXSTRIKE_BASE_URL`, `HEXSTRIKE_STUB`, `CAI_WORKDIR`, `CAI_STUB` per plan
- [X] T006 [P] Add Compose env passthrough placeholders for HexStrike/CAI on `red_team_backend` / `blue_team_backend` in `docker-compose.yml` (no secrets on `api_service`)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Schema, API principal from `user_roles`, `/me`, bootstrap Admin from TEST_USER, password gate, Admin redirect — BLOCKS all stories

**⚠️ CRITICAL**: Complete before user stories

- [X] T007 Write `secure_dash/supabase/migrations/20260805140000_rbac_user_journeys.sql` extending `app_role` (`user`, `security_analyst`, `security_manager`, `admin`); migrate `analyst` → `security_analyst`
- [X] T008 In same migration, create `profiles`, `tasks`, `task_notes`, `task_links`, `task_audit_events`, `notifications` per `specs/002-rbac-user-journeys/data-model.md`
- [X] T009 In same migration, add RLS policies aligned to Access Matrix (defense-in-depth; API remains primary writer)
- [X] T010 Update `secure_dash/src/integrations/supabase/types.ts` for new enums/tables
- [X] T011 Extend `api_service/app/schemas/models.py` with Profile, Task, RoleAssign (four roles), MeResponse shapes from `contracts/live-tools-and-identity.md`
- [X] T012 Update `api_service/app/deps.py` so `get_principal` resolves app role from `user_roles` via store (not JWT `authenticated` alone); map four roles to PrincipalKind
- [X] T013 Implement `GET /api/v1/me` in `api_service/app/routers/me.py` returning role, profile flags, `tool_unlock` per data-model predicates; register in `api_service/app/main.py`
- [X] T014 Extend `api_service/app/services/crud.py` + store for profiles/roles list/assign and task unlock helpers used by `/me`
- [X] T015 Implement `scripts/bootstrap_admin.py` reading root `.env` `TEST_USERNAME`/`TEST_PASSWORD`/`SUPABASE_URL`/`SUPABASE_SECRET_KEY` to create/confirm Auth user, upsert `profiles` (active, `must_change_password=false`), upsert `user_roles.admin`
- [X] T016 Wire `secure_dash/src/lib/api-client.ts` helper `fetchMe()` calling `GET /api/v1/me`
- [X] T017 Extend `secure_dash/src/routes/_authenticated/route.tsx` to load `/me` into router context (role, `must_change_password`, tool_unlock)
- [X] T018 Implement `secure_dash/src/components/auth/ForcePasswordChange.tsx` and block authenticated routes until password changed (invited users)
- [X] T019 [P] Handle invite-expiry rejection messaging in `secure_dash/src/routes/auth.tsx`
- [X] T020 Redirect Admin from ops home to `/admin` per `contracts/route-guards.md` in `secure_dash/src/routes/_authenticated/route.tsx` or `index.tsx`
- [X] T021 Implement unlock helpers `canOpenRedTools` / `canOpenBlueTools` in `secure_dash/src/lib/tasks.ts` matching API predicates

**Checkpoint**: Migration applied; `python scripts/bootstrap_admin.py` makes TEST_USER admin; `/api/v1/me` returns `admin`; password gate + Admin redirect work

---

## Phase 3: User Story 1 — Admin provisions users (Priority: P1) 🎯 MVP

**Goal**: Admin Panel; create any role including Admin; one-time credentials; demote/disable including last Admin; Admin denied ops pages

**Independent Test**: Bootstrap Admin → create Analyst (+ optional Admin) → first login password change; Admin cannot open `/tasks`; demote last Admin allowed

### Tests for User Story 1

- [X] T022 [P] [US1] Matrix unit tests for Admin allow `/admin`, deny ops, `assign_admin_role` in `secure_dash/src/lib/access-matrix.test.ts`
- [X] T023 [P] [US1] API test principal resolves `admin` from `user_roles` in `api_service/tests/test_rbac_principal.py`

### Implementation for User Story 1

- [X] T024 [US1] Implement Admin user provision endpoints in `api_service/app/routers/admin_users.py` (create/invite 24h, list, role/status patch, session revoke; no last-Admin guard) using Supabase Auth Admin via secret key
- [X] T025 [US1] Implement `secure_dash/src/lib/admin-provision.ts` API client wrappers for Admin user CRUD
- [X] T026 [P] [US1] Build `secure_dash/src/components/admin/UserList.tsx`
- [X] T027 [P] [US1] Build `secure_dash/src/components/admin/CreateUserForm.tsx` with four-role select + one-time credentials copy-once UI
- [X] T028 [US1] Add Admin-only route `secure_dash/src/routes/_authenticated/admin.tsx` with `beforeLoad` guard using `/me`
- [X] T029 [US1] Wire Admin-only nav in `secure_dash/src/components/sd/AppShell.tsx`
- [X] T030 [US1] Deny Admin deep-links to `/`, `/threats`, `/scans`, `/tasks`, `/tools/*`, `/patches`, `/attack-chain` with permissions message

**Checkpoint**: US1 identity MVP demoable with TEST_USER Admin

---

## Phase 4: User Story 2 — Read-only User (Priority: P1)

**Goal**: User dashboard explainer; RO threats/scans; deny Tasks/tools/Admin; unavailable resource state

**Independent Test**: As User, RO posture; `/tasks` and `/admin` blocked; empty explainer shows

### Tests for User Story 2

- [X] T031 [P] [US2] Matrix tests: User allow RO dashboard/threats/scans; deny tasks/tools/admin in `secure_dash/src/lib/access-matrix.test.ts`

### Implementation for User Story 2

- [X] T032 [US2] Enforce User RO on mutate actions in ops UI (`secure_dash/src/routes/_authenticated/threats.tsx`, `scans.tsx`) — hide/disable assign/resolve/start
- [X] T033 [US2] Add empty/onboarding explainer on `secure_dash/src/routes/_authenticated/index.tsx` for User with no data
- [X] T034 [US2] Add “no longer available” empty state for missing threat/scan detail views in `secure_dash/src/routes/_authenticated/threats.tsx` (and scans detail if present)
- [X] T035 [US2] Route guards deny User `/tasks`, `/tools/*`, `/admin` in respective `beforeLoad` or shared guard helper `secure_dash/src/lib/route-guards.ts`
- [X] T036 [US2] API deny User on task/admin mutate endpoints (403) in `api_service/app/deps.py` / routers

**Checkpoint**: User journey independently verifiable

---

## Phase 5: User Story 3 — Security Manager tasks (Priority: P1)

**Goal**: Manager creates/assigns/filters tasks; start any (audit on-behalf); both tool pages; Complete/Reviewed/Closed any

**Independent Test**: Manager creates Red+Blue tasks, assigns Analyst, starts on behalf (audit), opens both tools

### Tests for User Story 3

- [X] T037 [P] [US3] API tests Manager task create/start-on-behalf audit in `api_service/tests/test_tasks_manager.py`

### Implementation for User Story 3

- [X] T038 [US3] Implement task CRUD + transition service in `api_service/app/services/tasks.py` (Draft→Assigned→In Progress, on-behalf start audit)
- [X] T039 [US3] Add `api_service/app/routers/tasks.py` endpoints (list/create/get/patch transitions, filters) registered in `main.py`
- [X] T040 [US3] Add UI API helpers in `secure_dash/src/lib/tasks-api.ts`
- [X] T041 [P] [US3] Build `secure_dash/src/components/tasks/TaskBoard.tsx` with filters (analyst, type, status, date)
- [X] T042 [P] [US3] Build `secure_dash/src/components/tasks/CreateTaskForm.tsx` (target, description, patch_scope, type, assignee)
- [X] T043 [US3] Add routes `secure_dash/src/routes/_authenticated/tasks.tsx` and `tasks.$taskId.tsx` with Manager/Analyst guards
- [X] T044 [US3] Wire Tasks nav for Manager/Analyst in `secure_dash/src/components/sd/AppShell.tsx`
- [X] T045 [US3] Allow Manager unconditional `/tools/red` and `/tools/blue` access in route guards

**Checkpoint**: Manager planning journey works without Analyst unlock logic complete

---

## Phase 6: User Story 4 — Security Analyst execution (Priority: P1)

**Goal**: Own tasks only; Start unlocks tools by type; notes/links; Complete notifies Manager; reassign notifies former assignee

**Independent Test**: Red-only In Progress → Red tools OK, Blue denied; both types → both OK; notes+link visible; reassign removes unlock

### Tests for User Story 4

- [X] T046 [P] [US4] Unlock predicate tests (single-type vs both) in `secure_dash/src/lib/tasks.test.ts` and `/me` tool_unlock in `api_service/tests/test_me_unlock.py`

### Implementation for User Story 4

- [X] T047 [US4] Enforce Analyst own-only task list filter in `api_service/app/services/tasks.py`
- [X] T048 [US4] Analyst Start Task transition + recompute unlock; metadata fields read-only in `secure_dash/src/routes/_authenticated/tasks.$taskId.tsx`
- [X] T049 [US4] Implement notes/links API in `api_service/app/routers/tasks.py` + UI on task detail (`TaskNotes.tsx`, `TaskLinks.tsx` under `secure_dash/src/components/tasks/`)
- [X] T050 [US4] Notifications create on Complete→Manager and Reassign→former assignee in `api_service/app/services/notifications.py`; toast/list in `secure_dash/src/components/sd/AppShell.tsx` or notifications widget
- [X] T051 [US4] Add `secure_dash/src/routes/_authenticated/tools.red.tsx` and `tools.blue.tsx` shells with unlock guards; Start job via `POST /api/v1/jobs` and set `tasks.linked_job_id`
- [X] T052 [US4] Deny Analyst opposite-tool deep links with clear permissions message
- [X] T053 [US4] Apply Analyst assigned-scope filtering for threats/scans reads in `api_service` list endpoints (asset join to non-closed tasks)

**Checkpoint**: Analyst execution + tool gating independently testable

---

## Phase 7: User Story 5 — Task lifecycle review/closure (Priority: P2)

**Goal**: Full status machine; Manager Complete/Reviewed/Closed any; Analyst denied Reviewed/Closed; Closed read-only

**Independent Test**: Walk Draft→…→Closed; Manager Reviewed/Closed OK; Analyst Reviewed/Closed denied; reassign→Assigned

### Tests for User Story 5

- [X] T054 [P] [US5] Lifecycle AuthZ tests Manager vs Analyst Reviewed/Closed in `api_service/tests/test_task_lifecycle_authz.py`

### Implementation for User Story 5

- [X] T055 [US5] Complete transition graph (Blocked, Reviewed, Closed, Reassign→Assigned) in `api_service/app/services/tasks.py` with audit events
- [X] T056 [US5] UI status actions + badges on `secure_dash/src/routes/_authenticated/tasks.$taskId.tsx` respecting AuthZ
- [X] T057 [US5] Make Closed tasks read-only in API (reject updates) and UI

**Checkpoint**: SC-008 / SC-012 satisfiable

---

## Phase 8: Live tools — HexStrike + CAI (Delivery delta) [LT]

**Goal**: Profiles/jobs call live HexStrike/CAI; stubs only when `*_STUB=1`; fail clearly when live unavailable

**Independent Test**: Quickstart V7 — surface-recon hits HexStrike; deep-emulation uses CAI or fails loudly; CI stubs still pass

- [X] T058 [LT] Implement live HexStrike HTTP client in `red_team_backend/app/adapters/hexstrike_client.py` using `HEXSTRIKE_BASE_URL` / `HEXSTRIKE_STUB` (nmap route); normalize findings; no silent stub when stub off
- [X] T059 [P] [LT] Implement live CAI one-shot invoke in `red_team_backend/app/adapters/cai_client.py` using `CAI_WORKDIR` / `CAI_STUB` / worker LLM env; wire `deep_emulation.py`
- [X] T060 [P] [LT] Add HexStrike client for blue vuln path in `blue_team_backend/app/adapters/hexstrike_client.py` (nuclei/trivy or documented endpoints) used by `vuln_scan.py`
- [X] T061 [LT] Propagate `DEMO_SAFE_MODE` + allowlist from dispatch payload into workers; block destructive calls with `blocked_by_guardrail`
- [X] T062 [LT] Set `findings.source_tool`, `threat_events.source_tag`, `tool_runs.tool_name` per data-model live provenance (not `*-stub` when live)
- [X] T063 [LT] Update worker settings in `red_team_backend/app/settings.py` and `blue_team_backend/app/settings.py` for HexStrike/CAI env; document in `README.md`
- [X] T064 [P] [LT] Pytest: stub-on path still works in `red_team_backend/tests/test_surface_recon.py`; live-off without stub fails closed in new `red_team_backend/tests/test_hexstrike_live_fail.py`

**Checkpoint**: Lab jobs no longer fake-complete when stubs disabled

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Matrix sweep, docs, env alignment

- [X] T065 [P] Add `scripts/verify_rbac_matrix.sh` exercising Access Matrix allow/deny via API (`contracts/access-matrix.json`)
- [X] T066 [P] Align `secure_dash/.env` TEST_* with root or document single source in `README.md`
- [X] T067 Run `specs/002-rbac-user-journeys/quickstart.md` V0–V7 checklist and fix gaps
- [X] T068 [P] Update root `README.md` with bootstrap Admin + HexStrike/CAI lab prerequisites
- [X] T069 Ensure CORS remains valid for new UI origins if tools routes added; no secret leakage in Compose

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Immediate
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS** all stories + live tools UI that needs `/me`
- **US1–US5 (Phases 3–7)**: Depend on Foundational; can proceed in priority order (US1→US2→US3→US4→US5)
- **Live tools (Phase 8)**: Can start after Setup in parallel with Foundational for adapter code; end-to-end V7 needs jobs + unlock (US4) + workers
- **Polish (Phase 9)**: After desired stories + LT

### User Story Dependencies

- **US1 (P1)**: After Foundational — MVP
- **US2 (P1)**: After Foundational; uses role guards from US1 patterns
- **US3 (P1)**: After Foundational; tasks API
- **US4 (P1)**: After US3 task model exists (own-list + start)
- **US5 (P2)**: Extends US3/US4 transitions
- **LT**: Independent adapters; E2E after US4 tool pages

### Parallel Opportunities

- T001–T006 Setup [P] together
- T010, T019, T022/T023, T026/T027, T031, T037, T041/T042, T046, T054, T059/T060, T064–T066, T068 marked [P]
- After Foundational: US1 and US2 can parallel; LT adapter files parallel with US1

---

## Parallel Example: User Story 1

```bash
# Parallel tests:
Task: T022 access-matrix.test.ts Admin cells
Task: T023 test_rbac_principal.py

# Parallel UI components after provision API:
Task: T026 UserList.tsx
Task: T027 CreateUserForm.tsx
```

## Parallel Example: Live tools

```bash
Task: T058 red hexstrike_client.py
Task: T059 red cai_client.py
Task: T060 blue hexstrike_client.py
```

---

## Implementation Strategy

### MVP First (US1 only)

1. Phase 1 Setup  
2. Phase 2 Foundational (bootstrap TEST_USER + `/me`)  
3. Phase 3 US1 Admin Panel  
4. **STOP** — validate V0 + V1  

### Incremental Delivery

1. US2 User RO → V2  
2. US3 Manager tasks → V3  
3. US4 Analyst + tool pages → V4  
4. US5 Lifecycle → V5  
5. Phase 8 Live tools → V7  
6. Polish → V6 matrix script  

### Suggested MVP scope

**Phases 1–3 only** (Setup + Foundational + US1): Admin bootstrap from `TEST_USERNAME`/`TEST_PASSWORD` and Admin Panel provisioning.

---

## Notes

- Do not keep silent HexStrike/CAI stubs when `*_STUB` is unset/`0`
- Admin identity-only: never show ops nav to Admin
- Regenerate nothing here for 003; this feature builds on API-primary store already shipped
- Next command: `/speckit-implement` (or `/speckit-analyze` first if desired)
