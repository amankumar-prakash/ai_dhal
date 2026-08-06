# Tasks: CAI Chat on Red/Blue Tool Pages (Kali Workers)

**Input**: Design documents from `/specs/004-cai-tools-chat/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: AuthZ / stub / fail-closed tests already exist from prior chat MVP. Add Kali OS smoke checks in polish/quickstart (no new TDD suite required by spec).

**Organization**: By user story. Chat/SSE/UI foundation from the earlier 004 pass is marked **[X]**. Remaining work is the **Kali runtime** delta (FR-011/FR-012, SC-006).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Parallelizable (different files, no incomplete deps)
- **[Story]**: [US1]–[US3] on story phases only
- Paths from monorepo root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Env + deps for Kali workers and CAI container venv

- [X] T001 Document `CAI_WORKDIR`, `CAI_CHAT_STUB`, `CAI_AGENT_TYPE`, `CAI_AGENT_TYPE_BLUE` in root `.env.example`
- [ ] T002 Document `CAI_HOST_PATH`, `CAI_CONTAINER_VENV`, and Kali rebuild notes in root `.env.example`
- [X] T003 [P] Add Compose volume mount for CAI workdir + env passthrough on `red_team_backend` and `blue_team_backend` in `docker-compose.yml` (no CAI secrets on `api_service`)
- [ ] T004 [P] Pass `CAI_CONTAINER_VENV` / `UV_PROJECT_ENVIRONMENT` through worker `environment` in `docker-compose.yml`
- [X] T005 [P] Add CAI chat Pydantic shapes in `api_service/app/schemas/models.py`
- [X] T006 [P] Add TypeScript session/stream types in `secure_dash/src/lib/cai-chat-types.ts`
- [X] T007 [P] Add `cai-framework>=0.5.10` to `red_team_backend/requirements.txt`
- [ ] T008 [P] Add `cai-framework>=0.5.10` to `blue_team_backend/requirements.txt`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Kali Docker images + CAI spawn on workers + API proxy — **BLOCKS** live US1–US3 acceptance on Kali

**⚠️ CRITICAL**: Complete before claiming Kali acceptance (SC-006)

### Already shipped (chat foundation — keep)

- [X] T009 Extend `red_team_backend/app/settings.py` with `cai_workdir`, `cai_chat_stub`, `cai_agent_type`, soft timeouts
- [X] T010 [P] Extend `blue_team_backend/app/settings.py` with CAI settings
- [X] T011 Implement `red_team_backend/app/adapters/cai_session.py` (spawn/stub/stdin/SSE buffer/stop/guardrails/fail-closed + `UV_PROJECT_ENVIRONMENT`)
- [X] T012 Implement `red_team_backend/app/routers/cai_chat.py` and register in `red_team_backend/app/main.py`
- [X] T013 Implement `api_service/app/services/cai_proxy.py` and `api_service/app/routers/cai_chat.py` (JWT + tool unlock; SSE relay)
- [X] T014 Port blue `cai_session.py` + `cai_chat.py` and register in `blue_team_backend/app/main.py`

### Kali runtime (remaining)

- [ ] T015 Rewrite `red_team_backend/Dockerfile` to `FROM kalilinux/kali-rolling`, install `python3`/`pip`/`venv`/`curl`/`ca-certificates`, install `uv` + `requirements.txt`, `mkdir -p /var/cache/cai-venv`, optional `KALI_METAPACKAGE` build-arg (default empty), expose `8001`, uvicorn CMD per `specs/004-cai-tools-chat/contracts/kali-worker-runtime.md`
- [ ] T016 [P] Rewrite `blue_team_backend/Dockerfile` the same Kali pattern (port `8002`) per `contracts/kali-worker-runtime.md`
- [ ] T017 Align worker Compose healthchecks to `python3` in `docker-compose.yml` if Kali package layout requires it
- [ ] T018 Confirm `red_team_backend/app/adapters/cai_session.py` and `blue_team_backend/app/adapters/cai_session.py` prefer `uv run cai` with `CAI_CONTAINER_VENV` and never rely on host-mounted `.venv/bin/cai` shebangs
- [ ] T019 Rebuild and start Kali workers via `docker compose build/up` for `red_team_backend` and `blue_team_backend`; warm CAI with `uv sync` into `/var/cache/cai-venv` as in `specs/004-cai-tools-chat/quickstart.md`

**Checkpoint**: `grep -i kali /etc/os-release` inside both workers; stub or live `POST /cai/sessions` works on red

---

## Phase 3: User Story 1 — Red Team CAI chat on Kali (Priority: P1) 🎯 MVP

**Goal**: `/tools/red` chat streams CAI from the **Kali** red worker

**Independent Test**: Manager on `/tools/red` sends a message; streamed lines appear; red container is Kali; Admin/User denied on API

### Tests (already present)

- [X] T020 [P] [US1] Pytest stub session + stop in `red_team_backend/tests/test_cai_session.py`
- [X] T021 [P] [US1] API AuthZ Manager allow / Admin+User deny in `api_service/tests/test_cai_chat_authz.py`

### Implementation (UI already present; verify on Kali)

- [X] T022 [US1] `secure_dash/src/lib/cai-chat.ts` fetch+ReadableStream client
- [X] T023 [US1] `secure_dash/src/components/tools/CaiChatPanel.tsx`
- [X] T024 [US1] Embed `CaiChatPanel` `team="red"` in `secure_dash/src/routes/_authenticated/tools.red.tsx`
- [ ] T025 [US1] Prove Red Kali base (`docker compose exec red_team_backend grep -i kali /etc/os-release`) and one successful Red chat stream (stub or live) per quickstart V0+V1

**Checkpoint**: SC-001/SC-005 (red) + SC-006 (red)

---

## Phase 4: User Story 2 — Blue Team CAI chat on Kali (Priority: P1)

**Goal**: `/tools/blue` chat streams CAI from the **Kali** blue worker

**Independent Test**: Blue unlock → stream on `/tools/blue`; Red-only Analyst denied; blue OS is Kali

### Tests (already present)

- [X] T026 [P] [US2] API wrong-team Analyst denied blue sessions in `api_service/tests/test_cai_chat_authz.py`

### Implementation

- [X] T027 [US2] Embed `CaiChatPanel` `team="blue"` in `secure_dash/src/routes/_authenticated/tools.blue.tsx`
- [X] T028 [US2] API proxy `team=blue` → blue worker in `api_service/app/services/cai_proxy.py`
- [ ] T029 [US2] Prove Blue Kali base and one successful Blue chat stream per quickstart V0+V4

**Checkpoint**: SC-005 (blue) + SC-006 (blue)

---

## Phase 5: User Story 3 — Session control & failure visibility (Priority: P2)

**Goal**: Stop ends CAI; missing workdir / guardrail show durable errors (still true on Kali images)

**Independent Test**: Stop clears process; bad `CAI_WORKDIR` shows error (no infinite Working)

### Tests / implementation (already present)

- [X] T030 [P] [US3] Pytest fail-closed when workdir missing in `red_team_backend/tests/test_cai_session_fail.py`
- [X] T031 [US3] Stop control + sticky errors in `secure_dash/src/components/tools/CaiChatPanel.tsx`
- [X] T032 [US3] One active session per `(user_id, team)` + soft timeouts in worker `cai_session.py` adapters
- [ ] T033 [US3] Re-validate Stop + fail-closed (quickstart V3 + V6) against Kali red worker after image cutover

**Checkpoint**: SC-003 / SC-004 on Kali

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Docs and lab acceptance

- [X] T034 [P] Best-effort secret redaction in worker stream emitters
- [ ] T035 [P] Update root `README.md` with Kali worker images, `CAI_CONTAINER_VENV`, and `uv sync` warm-up
- [ ] T036 Run `specs/004-cai-tools-chat/quickstart.md` V0–V7 on Kali compose stack; fix gaps
- [X] T037 [P] CORS allows SSE/fetch streaming in `api_service/app/main.py`
- [ ] T038 [P] Note optional `KALI_METAPACKAGE` build-arg in `red_team_backend/Dockerfile` and `blue_team_backend/Dockerfile` comments (or README)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Immediate — finish T002/T004/T008 before rebuild
- **Foundational (Phase 2)**: Kali Dockerfiles (T015–T019) **BLOCK** SC-006 and live chat on Kali
- **US1 (Phase 3)**: After T019 — MVP validation on Red Kali
- **US2 (Phase 4)**: After T016/T019 — Blue Kali validation
- **US3 (Phase 5)**: After Red Kali up — re-validate stop/fail
- **Polish (Phase 6)**: After desired stories

### User Story Dependencies

- **US1**: Needs Phase 2 Kali red image; UI/API already done
- **US2**: Needs Phase 2 Kali blue image; panel already done
- **US3**: Needs Red Kali running; UI/worker policy already done

### Parallel Opportunities

- T004 ∥ T008 (compose env vs blue requirements)
- T015 ∥ T016 (red/blue Dockerfiles)
- After rebuild: T025 ∥ T029 (red vs blue prove)
- T035 ∥ T038 (docs)

---

## Parallel Example: Kali Dockerfiles

```bash
Task: T015 Rewrite red_team_backend/Dockerfile to Kali
Task: T016 Rewrite blue_team_backend/Dockerfile to Kali
Task: T008 Add cai-framework to blue_team_backend/requirements.txt
```

## Parallel Example: Acceptance probes

```bash
Task: T025 Prove Red Kali + chat stream
Task: T029 Prove Blue Kali + chat stream
```

---

## Implementation Strategy

### MVP First (US1 on Kali)

1. Finish Phase 1 open items (T002, T004, T008)
2. Phase 2 Kali Dockerfiles + rebuild + `uv sync` (T015–T019)
3. Phase 3 T025 Red prove
4. **STOP** — validate Red chat on Kali

### Incremental Delivery

1. US2 Blue Kali prove (T029)
2. US3 re-validate stop/fail (T033)
3. Polish quickstart + README (T035–T036, T038)

### Suggested MVP scope

**T002, T004, T008, T015–T019, T025** (Kali red worker + proven Red chat).

---

## Notes

- Do not put `OPENAI_API_KEY` on `api_service`
- Keep one-shot `cai_client.plan_chain` for deep-emulation; chat uses `cai_session.py`
- Lean Kali by default; do not install `kali-linux-large` unless build-arg set
- Next: `/speckit-implement`
