# Research: SentryOps Role-Based User Journeys (+ live tools)

**Feature**: `002-rbac-user-journeys`  
**Date**: 2026-08-05  
**Status**: Complete — Clarifications 2026-08-04 + delivery deltas (UI implement, TEST_USER admin seed, live HexStrike/CAI)

## R1 — AuthZ enforcement

- **Decision**: Dual enforcement — TanStack Router guards + **`api_service` principal** reading `user_roles` / task unlock predicates. RLS remains defense-in-depth for any residual browser reads; business CRUD stays on API (003).
- **Rationale**: FR-001; UI-only checks insufficient; JWT `role=authenticated` is not app role.
- **Alternatives considered**: Nav-only hiding — rejected; JWT-claim-only admin — rejected (empty `user_roles`, chicken-and-egg).

## R2 — Role model

- **Decision**: `app_role`: `user | security_analyst | security_manager | admin`; migrate legacy `analyst` → `security_analyst`. One primary role per user in v1.
- **Rationale**: FR-002.
- **Alternatives considered**: Keep `analyst` only — naming mismatch with matrix.

## R3 — Admin provisioning & Admin-to-Admin

- **Decision**: Server-only Auth Admin API (service role on API or secure_dash server fn) for create/invite/re-issue/role patch/deactivate with session revoke. Admin may assign `admin` and demote/disable any Admin including the last.
- **Rationale**: Clarify Q1; FR-004, FR-018.
- **Alternatives considered**: Forbid Admin grant / protect last Admin — rejected by clarify.

## R4 — First Admin bootstrap (TEST_USER)

- **Decision**: Out-of-band script `scripts/bootstrap_admin.py` reads **root** `.env` `TEST_USERNAME` + `TEST_PASSWORD` (document in `.env.example`). Ensures Auth user exists (create if missing), sets `email_confirm=true`, upserts `profiles` (`status=active`, `must_change_password=false` for lab seed), upserts `user_roles` = `admin`. No in-app first-run wizard.
- **Rationale**: Clarify Q4; user request to seed TEST_USER as admin; FR-019.
- **Alternatives considered**: Manual Dashboard-only — error-prone; first-run wizard — rejected; leave `must_change_password=true` on lab seed — blocks automation (lab seed clears flag; invited users still force change).

## R5 — One-time credentials

- **Decision**: 24h unused TTL or consumed on first login; `must_change_password` gate until reset (invited users). Lab bootstrap Admin skips force-change.
- **Rationale**: FR-005, FR-006.
- **Alternatives considered**: Magic-link-only — optional later.

## R6 — Tasks vs 001 jobs/scans

- **Decision**: First-class `tasks`; optional `linked_job_id` to platform jobs. Tool **pages** gated by task unlock; starting a tool run creates/links a `001` job via `POST /api/v1/jobs`.
- **Rationale**: Spec assumptions; keeps lifecycle separate from scan rows.
- **Alternatives considered**: Reuse scans as tasks — wrong lifecycle.

## R7 — Analyst tool unlock (multi-task)

- **Decision**: Unlock Red iff ∃ own task `status=in_progress ∧ task_type=red`; likewise Blue. Manager always both. Admin never tools.
- **Rationale**: Clarify Q2; FR-009.
- **Alternatives considered**: Single In Progress only — rejected.

## R8 — Task notes and links

- **Decision**: `task_notes` + `task_links` (finding|scan). Optional for Complete.
- **Rationale**: Clarify Q3; FR-017.
- **Alternatives considered**: Mandatory Finding create — rejected.

## R9 — Lifecycle AuthZ

- **Decision**: Manager: start any, Complete/Reviewed/Closed any (audit). Analyst: Block + Complete own only; deny Reviewed/Closed.
- **Rationale**: Clarify Q5; FR-010–011.
- **Alternatives considered**: Assignee-only Complete — rejected.

## R10 — Assigned scope for Analyst reads

- **Decision**: API filters threats/findings/scans for Analysts by assets on their non-closed tasks; Manager/User org-wide per matrix; Admin denied ops endpoints.
- **Rationale**: FR-015 + API-primary.
- **Alternatives considered**: Org-wide Analyst — violates matrix.

## R11 — Notifications

- **Decision**: In-app `notifications` for assign, reassign, completed-for-review.
- **Rationale**: FR-012–013.
- **Alternatives considered**: Email-only — slower to validate.

## R12 — Relationship to workers / live tools (UPDATED)

- **Decision**: **Live by default in lab**. Replace stub adapters:
  - **HexStrike**: HTTP client to sibling server `HEXSTRIKE_BASE_URL` (default `http://host.docker.internal:8888`, port from `HEXSTRIKE_PORT`). Use documented routes (e.g. `POST /api/tools/nmap`). Normalize responses into findings/threat_events/tool_runs via existing API reporter. Compose: do not put HexStrike secrets on `api_service`.
  - **CAI**: For `deep-emulation`, invoke sibling `/home/kali/workspace/cai_pentesting` non-interactively (`uv run` with env `CAI_*` / `OPENAI_API_KEY` on **red worker only**) with a bounded prompt summarizing job assets; parse/plan stages into attack_chain steps. Interactive REPL is for humans; workers use one-shot invocation with timeout.
  - **Stubs**: Only when `HEXSTRIKE_STUB=1` / `CAI_STUB=1` / `LLM_STUB=1` (CI). Missing live endpoint with stub off → job `failed` with clear error (no silent fake success).
- **Rationale**: User delivery delta; current stubs complete jobs without real tooling; siblings exist on host.
- **Alternatives considered**: Keep stubs until later S4 — rejected for this plan; call HexStrike MCP from UI — rejected (tools on workers only); embed Metasploit/exploit payloads — out of scope / safety.

## R13 — Principal resolution

- **Decision**: After JWT verify, `get_principal` loads `user_roles` for `sub` via store; map to `PrincipalKind`. If no row → treat as `user` (least privilege) or deny ops until assigned. Optional JWT `app_metadata.role` override only if explicitly documented for break-glass.
- **Rationale**: Fixes empty-table + JWT `authenticated` bug.
- **Alternatives considered**: Continue JWT-only — broken for Admin seed.

## R14 — UI surfaces to implement

- **Decision**: Ship `/admin` (users CRUD, role assign, invite re-issue), `/tasks` + detail (matrix AuthZ), `/tools/red` + `/tools/blue` (unlock + Start job → API), password-change gate, role home redirects (Admin → `/admin`, others → `/`).
- **Rationale**: Spec US1–US5; currently only thin `/roles` API stub and no UI.
- **Alternatives considered**: API-only without UI — fails user request.

## R15 — Env contract additions

| Variable | Where | Purpose |
|----------|--------|---------|
| `TEST_USERNAME` / `TEST_PASSWORD` | root `.env` | Bootstrap Admin |
| `HEXSTRIKE_BASE_URL` | red/blue workers | Live HexStrike |
| `HEXSTRIKE_STUB` | workers | CI stub |
| `CAI_WORKDIR` / `CAI_STUB` | red worker | Live CAI invoke |
| Existing `OPENAI_API_KEY`, `LLM_*`, `DEMO_SAFE_MODE`, `TARGET_ALLOWLIST` | workers | Unchanged ownership |
