# Feature Specification: CAI Chat on Red/Blue Tool Pages

**Feature Branch**: `004-cai-tools-chat`  
**Created**: 2026-08-06  
**Status**: Draft  
**Input**: Red and Blue team tool pages include a UI chatbot. Backend starts CAI via `uv run cai` in `cai_pentesting`. Each chat turn runs/feeds the CAI worker and streams terminal stdout/stderr to the UI in real time. Gated by existing RBAC tool unlock; `DEMO_SAFE_MODE` and allowlist apply. **Red and Blue workers run on Kali Linux Docker images; CAI executes inside those containers.**

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Chat on Red Team tools with live CAI stream (Priority: P1) 🎯 MVP

An authorized analyst or manager opens Red Team tools, uses an in-page chat box to send a prompt, and sees CAI’s terminal-style output stream into the UI as it is produced. The Red worker is a **Kali** container; CAI runs there (not on the API host or in the browser).

**Why this priority**: Core value — interactive CAI in-product instead of only one-shot job stubs; Kali gives CAI a real pentest toolchain environment.

**Independent Test**: With Red tools unlocked and CAI workdir configured on the Kali red worker, send one chat message; streamed lines appear within seconds; session can be stopped.

**Acceptance Scenarios**:

1. **Given** a Manager (or Analyst with Red unlock) on `/tools/red`, **When** they send a chat message, **Then** the Kali red worker starts (or continues) CAI via `uv run cai` in `CAI_WORKDIR`, and terminal output streams into the chat/terminal panel.
2. **Given** a streaming CAI session, **When** CAI writes to stdout/stderr, **Then** the UI appends those lines in near-real time without requiring a full page refresh.
3. **Given** a User or Admin (no tool access), **When** they attempt the chat API or deep-link Red tools, **Then** access is denied with a clear permissions failure.
4. **Given** Compose is up, **When** an operator inspects the red worker image/OS, **Then** it is Kali-based (not a generic `python:slim` image).

---

### User Story 2 - Chat on Blue Team tools with live CAI stream (Priority: P1)

Same chatbot experience on Blue Team tools, with the **Kali** blue-side worker invoking CAI (blue-oriented agent when configured).

**Why this priority**: Parity with Red; both tool pages were requested.

**Independent Test**: With Blue unlock, send a chat message on `/tools/blue`; stream appears from blue Kali worker CAI session.

**Acceptance Scenarios**:

1. **Given** Blue tools access, **When** the user sends a chat message on `/tools/blue`, **Then** a CAI session is driven by the blue Kali worker and output streams to the UI.
2. **Given** an Analyst with only Red unlock, **When** they open Blue chat, **Then** they are denied (existing unlock rules).
3. **Given** Compose is up, **When** an operator inspects the blue worker image/OS, **Then** it is Kali-based.

---

### User Story 3 - Session control and failure visibility (Priority: P2)

Users can stop a running CAI chat session; misconfiguration and guardrail blocks are visible in the UI stream/status.

**Why this priority**: Lab operators need control and clear failure modes.

**Independent Test**: Start a session, click Stop — process ends and stream closes; with `CAI_WORKDIR` missing, UI shows a clear error (no silent hang).

**Acceptance Scenarios**:

1. **Given** an active CAI session, **When** the user stops it, **Then** the worker terminates the CAI process and the UI shows a terminal “session ended” state.
2. **Given** CAI unavailable or guardrail block (`DEMO_SAFE_MODE` / allowlist), **When** chat is started, **Then** the UI shows a durable error/status message instead of an empty spinner forever.

---

### Edge Cases

- CAI process crash mid-stream → UI shows exit/error and session marked failed.
- Concurrent chats from same user → one active session per user+team in v1 (new start replaces or rejects with message).
- Very long output → UI remains scrollable; stream does not drop solely due to length (lab-scale).
- Network disconnect mid-stream → client reconnects for buffered tail if session alive, or sees ended state.
- Prompt contains only whitespace → rejected by validation.
- Interactive CAI waiting for input → subsequent chat messages are written to session stdin.
- Host-mounted `cai_pentesting/.venv` built on a different Python/OS → worker MUST NOT rely on that host venv; use a Kali-native env (`uv` + container-local `UV_PROJECT_ENVIRONMENT`).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Red Team tools page MUST include a chatbot UI (prompt input + streaming terminal/transcript view).
- **FR-002**: Blue Team tools page MUST include the same chatbot UI pattern.
- **FR-003**: Submitting a chat message MUST cause the corresponding team backend to start or continue a CAI worker process using `uv run cai` (preferred) inside `CAI_WORKDIR` **on that team’s Kali container**.
- **FR-004**: CAI process stdout and stderr MUST stream to the UI in near-real time (terminal-like).
- **FR-005**: Chat MUST be authorized using the same Red/Blue tool unlock rules as existing tool pages.
- **FR-006**: Users MUST be able to stop an active CAI chat session.
- **FR-007**: LLM/CAI secrets and the CAI process MUST remain on workers — never on `api_service` or the browser.
- **FR-008**: `DEMO_SAFE_MODE` and `TARGET_ALLOWLIST` MUST apply to CAI chat (no silent bypass).
- **FR-009**: When CAI cannot start, the system MUST fail closed with a visible error in the UI.
- **FR-010**: Optional `taskId` search param MAY be shown as context; creating a platform job is not required for chat MVP.
- **FR-011**: `red_team_backend` and `blue_team_backend` Docker images MUST be based on official Kali Linux (`kalilinux/kali-rolling` or documented pin).
- **FR-012**: CAI MUST execute inside the Red/Blue Kali worker containers (same container as the FastAPI worker for v1), with a Kali-compatible Python/`uv` toolchain — not by shelling out to the host OS.

### Key Entities

- **CAI Chat Session**: Per-user, per-team interactive CAI process with status (starting / running / stopped / failed).
- **CAI Chat Message**: User-authored prompt associated with a session.
- **CAI Stream Event**: Ordered terminal chunk (stdout/stderr) or control event (started / ended / error).
- **Kali Worker Runtime**: Red/Blue container image based on Kali; hosts FastAPI + CAI spawn environment.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: From chat submit to first streamed terminal line under lab conditions in under 10 seconds when CAI and model are reachable.
- **SC-002**: 100% of denied-role attempts fail with a clear permissions error.
- **SC-003**: Stopping a session ends the worker CAI process (no orphan for that session).
- **SC-004**: Invalid/missing `CAI_WORKDIR` fails with a visible error in 100% of trials.
- **SC-005**: Red and Blue pages each demonstrate at least one successful streamed chat turn in lab acceptance.
- **SC-006**: `docker compose` Red and Blue services report a Kali base (e.g. `/etc/os-release` contains Kali) in lab acceptance.

## Assumptions

- Sibling repo `cai_pentesting` is available; workers use `CAI_WORKDIR` (volume into Kali containers).
- CAI CLI accepts optional initial prompt (`uv run cai "<prompt>"`) then REPL; follow-ups via stdin.
- Browser never talks to workers; API proxies stream.
- Existing HexStrike job launcher remains; chatbot is additive.
- Lab-scale concurrency only; MFA / transcript export out of scope.
- Red default agent `redteam_agent`; Blue via env (e.g. bug-bounty / blue agent).
- Kali base image is minimal; extra tool metapackages are optional via build args (default keeps image buildable in lab time).
- `api_service` and `secure_dash` stay on their current non-Kali images.
