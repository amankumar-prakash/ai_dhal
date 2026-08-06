# Research: CAI Chat on Kali Workers (004)

**Date**: 2026-08-06  
**Feature**: `004-cai-tools-chat`  
**Driver**: Red/Blue must use Kali Docker images; CAI runs on them.

## R1 — How to invoke CAI from workers

**Decision**: Prefer `uv run cai` with `cwd=CAI_WORKDIR` (mounted `cai_pentesting`). Set `UV_PROJECT_ENVIRONMENT` / `CAI_CONTAINER_VENV` to a **container-writable** path (e.g. `/var/cache/cai-venv`) so `uv` creates a Kali-native venv. Do **not** execute host-mounted `.venv/bin/cai` when that interpreter is missing or wrong-arch. Initial message may be CLI argv; follow-ups via stdin.

**Rationale**: Matches operator workflow; avoids shebang/`python3.13` host-venv failures seen on slim images.

**Alternatives considered**: Embed `cai-framework` as a library in the worker (heavy; couples versions); always call host `.venv` binaries (fails across OS/Python).

## R2 — Streaming transport

**Decision**: **SSE** worker → API → browser (unchanged from prior plan).

- Worker: `GET /cai/sessions/{id}/events` (service token).
- API: `/api/v1/cai/...` with JWT + tool unlock; proxies stream.
- UI: `fetch` stream + Bearer (not bare `EventSource`).

**Rationale**: One-way terminal output; workers stay private.

**Alternatives considered**: WebSocket; polling; browser→worker direct.

## R3 — Process model (PTY vs pipes)

**Decision**: Start with **asyncio subprocess pipes**; escalate to PTY if prompt-toolkit requires TTY.

**Rationale**: Abstract behind `CaiSession`; keep v1 simple on Kali.

## R4 — AuthZ

**Decision**: Reuse `/me` `tool_unlock.red` / `tool_unlock.blue` (Manager always). User/Admin → 403.

## R5 — Red vs Blue agent

**Decision**: Env-driven on each Kali worker:

| Team | Env | Default |
|------|-----|---------|
| Red | `CAI_AGENT_TYPE` | `redteam_agent` |
| Blue | `CAI_AGENT_TYPE` (compose: `CAI_AGENT_TYPE_BLUE`) | `bug_bounter_agent` |

## R6 — Guardrails

**Decision**: Apply `DEMO_SAFE_MODE` + `TARGET_ALLOWLIST` before spawn / before stdin that embeds disallowed targets. Block → stream `error` with `blocked_by_guardrail`.

## R7 — Docker / CAI path on Kali

**Decision**:

1. Compose volume: `${CAI_HOST_PATH}:/cai` (rw enough for CAI logs if needed).
2. `CAI_WORKDIR=/cai`.
3. `CAI_CONTAINER_VENV=/var/cache/cai-venv` (image `mkdir`; not on the host bind mount).
4. Optional image build step or first-boot `uv sync` against `/cai` into that venv (document in quickstart; prefer warm sync in CI/lab once after rebuild).

**Rationale**: Source stays sibling repo; **runtime Python env is Kali-owned**.

**Alternatives considered**: Copy entire `cai_pentesting` into image at build (stale drift); nest second container for CAI only.

## R8 — CI stub

**Decision**: `CAI_CHAT_STUB=1` → synthetic stream; no real CAI. Live path with stub off must fail closed on spawn errors.

## R9 — Relationship to existing `cai_client.py`

**Decision**: Keep one-shot `plan_chain` for deep-emulation jobs. Interactive chat stays in `cai_session.py`.

## R10 — Kali base image (NEW)

**Decision**: Both worker Dockerfiles use official **`kalilinux/kali-rolling`** (pin digest or weekly tag in lab notes when stability matters). Install at build:

- `python3`, `python3-venv`, `python3-pip`, `curl`, `ca-certificates`
- `uv` (pip or official installer)
- Worker Python deps from `requirements.txt` (FastAPI/uvicorn/httpx/…)
- Optional build-arg `KALI_METAPACKAGE` (empty default | `kali-linux-headless` | curated package list) — **default empty/lean** for lab build time

`api_service` remains `python:3.12-slim` (or current). UI unchanged.

**Rationale**: Spec FR-011/FR-012; Kali is the natural OS for red/blue tooling; official image is maintained weekly on Docker Hub.

**Alternatives considered**:

| Option | Why rejected |
|--------|----------------|
| Keep `python:3.12-slim` + install nmap ad hoc | Not Kali; tool/agent parity weak; prior CAI spawn breakage |
| `kalilinux/kali-last-release` only | More stable but less current; rolling is default Kali ops choice |
| Full `kali-linux-large` always | Multi-GB images; slow rebuilds; overkill for chat MVP |
| Separate Kali+CAI sidecar + docker.sock | Extra hop, privilege, compose complexity for v1 |

## R11 — Healthchecks on Kali

**Decision**: Keep HTTP healthchecks against worker `/health` using `python3 -c urllib…` (ensure `python3` present). Avoid assuming Debian `python` package name mismatches.

## Open items resolved by assumption

| Topic | Resolution |
|-------|------------|
| Persistence of transcripts | Ephemeral buffer in worker memory |
| Max session length | Soft idle/absolute timeouts then auto-stop |
| Multiple tabs | Fan-out SSE from same session buffer |
| Nested containers | Out of scope for v1 |
| Which Kali tools preinstalled | Lean default; metapackage opt-in via build-arg |
