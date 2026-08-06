# Implementation Plan: CAI Chat on Red/Blue Tool Pages (Kali Workers)

**Branch**: `004-cai-tools-chat` | **Date**: 2026-08-06 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/004-cai-tools-chat/spec.md`  
**Plan delta**: Red/Blue workers use **Kali Docker images**; CAI runs **inside** those containers.

## Summary

Add an in-page **CAI chatbot** to `/tools/red` and `/tools/blue`. On send, `api_service` authorizes via existing tool unlock and proxies to the matching worker. **`red_team_backend` and `blue_team_backend` are built `FROM kalilinux/kali-rolling`**, install Python + `uv`, and spawn **`uv run cai`** in `CAI_WORKDIR` (mounted `cai_pentesting`) using a **container-local** virtualenv so host `.venv` shebangs cannot break spawn. **Stdout/stderr** stream to the UI (SSE). Stop ends the process. Secrets and CAI stay on Kali workers; HexStrike job launchers remain; `api_service` stays non-Kali.

## Technical Context

**Language/Version**: TypeScript / React 19 (`secure_dash`); Python 3.12 (`api_service`); Python 3.x from Kali apt + `uv` on Red/Blue workers; CAI via `uv run cai` inside Kali

**Primary Dependencies**: TanStack Router/Query; FastAPI; httpx; asyncio subprocess; browser fetch-SSE; sibling `cai-framework` via `uv`; Docker base `kalilinux/kali-rolling`

**Storage**: Ephemeral in-memory session registry on workers (v1); optional append-only stream buffer per session; no new Postgres tables for MVP

**Testing**: pytest worker session/stream with `CAI_CHAT_STUB=1`; API AuthZ unlock tests; Compose smoke that Red/Blue `/etc/os-release` is Kali and live chat streams when stub off

**Target Platform**: Lab monorepo — Compose Kali workers + API + Vite UI; CAI executes in-worker on Kali (not host shell)

**Project Type**: Web app + API + Kali worker containers integrating external CAI CLI

**Performance Goals**: First streamed line &lt;10s when model reachable; Kali image build time acceptable for lab (optional metapackage via build-arg, default lean)

**Constraints**: No LLM/CAI secrets on API/UI; RBAC tool unlock; `DEMO_SAFE_MODE` + allowlist; fail closed; never exec host-mounted `.venv` binaries that target wrong OS/Python; browser must not reach workers

**Scale/Scope**: One active CAI session per user+team; Red + Blue Kali chat panels; lab concurrency; no nested “CAI sidecar” in v1

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution template unfilled — gates from product norms + this spec:

| Gate | Status |
|------|--------|
| Secrets isolation (workers hold LLM/CAI) | PASS |
| AuthZ reuses tool unlock | PASS |
| Fail closed when CAI missing | PASS |
| Stream via API proxy (no worker exposure) | PASS |
| Guardrails (DEMO_SAFE_MODE / allowlist) | PASS |
| No exploit PoCs in repo | PASS |
| CAI runtime on Kali workers only (not API) | PASS |

**Post-design re-check**: PASS — Kali Dockerfiles + contracts keep CAI spawn on Red/Blue; SSE proxy on API; stub only for CI; container-local uv env documented.

## Project Structure

### Documentation (this feature)

```text
specs/004-cai-tools-chat/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── README.md
│   ├── cai-chat-stream.md
│   └── kali-worker-runtime.md   # NEW / updated
└── tasks.md                     # via /speckit-tasks (refresh after this plan)
```

### Source Code (repository root)

```text
red_team_backend/
├── Dockerfile                    # FROM kalilinux/kali-rolling; python3; uv; FastAPI app
├── app/adapters/cai_session.py   # spawn uv run cai with UV_PROJECT_ENVIRONMENT
└── app/routers/cai_chat.py

blue_team_backend/
├── Dockerfile                    # same Kali pattern; blue agent env
├── app/adapters/cai_session.py
└── app/routers/cai_chat.py

docker-compose.yml                # workers build Kali images; CAI volume; CAI_CONTAINER_VENV

api_service/                      # unchanged base image; cai_chat proxy only
secure_dash/                      # CaiChatPanel (existing feature UI)
```

**Structure Decision**: Keep FastAPI workers as the Red/Blue services; change only their **base image and CAI spawn environment** to Kali. Do not introduce a second Kali sidecar container in v1.

## Complexity Tracking

| Decision | Why needed | Simpler alternative rejected |
|----------|------------|------------------------------|
| Kali base for both workers | Spec: CAI runs in a real pentest OS; tools + agent expectations | Stay on `python:3.12-slim` (breaks host-venv CAI; no Kali toolchain) |
| Container-local `UV_PROJECT_ENVIRONMENT` | Host bind-mount `.venv` has wrong Python shebang/symlink | Exec host `.venv/bin/cai` directly (ENOENT in container) |
| CAI in same container as FastAPI | One network hop; existing service-token proxy | Nested Kali+CAI sidecar (docker-in-docker / extra compose service) |
| Lean Kali + optional metapackage build-arg | Lab build time vs full `kali-linux-large` | Always install large metapackage (multi-GB, slow CI) |
| Persistent CAI process + stdin | Interactive `uv run cai` REPL | One-shot only |
| SSE via API proxy | Auth + private workers | Direct browser→worker |
