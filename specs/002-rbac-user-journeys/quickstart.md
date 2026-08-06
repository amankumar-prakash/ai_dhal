# Quickstart Validation: SentryOps RBAC + live tools

**Feature**: `002-rbac-user-journeys`  
**Date**: 2026-08-05  
**Purpose**: Prove role journeys, Admin bootstrap from TEST_USER, and live HexStrike/CAI jobs.

## Prerequisites

- Migrations: base + red/blue + **RBAC** migration applied ([data-model.md](./data-model.md))
- Root `.env`: `SUPABASE_URL`, `SUPABASE_SECRET_KEY`, `TEST_USERNAME`, `TEST_PASSWORD`, `API_STORE=supabase`
- Compose API + workers up; UI Vite with aligned `VITE_*`
- For live tools: HexStrike server on `:8888` (`HEXSTRIKE_STUB=0`); CAI sibling available for deep profile (`CAI_STUB=0`)
- CI may set `HEXSTRIKE_STUB=1` `CAI_STUB=1` `LLM_STUB=1`

## Setup

```bash
# from repo root
cp .env.example .env   # ensure TEST_USERNAME / TEST_PASSWORD set
./scripts/apply_supabase_migrations.sh   # includes RBAC migration when added
python scripts/bootstrap_admin.py        # seeds TEST_USER as admin

docker compose up -d --build
cd secure_dash && npm run dev -- --port 8080
```

Sign in at `/auth` with `TEST_USERNAME` / `TEST_PASSWORD` → must land on **Admin Panel** (`/admin`), not ops dashboard.

## Validation scenarios

### V0 — Bootstrap Admin (delivery delta)

1. Empty `user_roles` → run bootstrap → row `admin` for TEST user.
2. Sign in → `/admin`; `/`, `/threats`, `/tasks` denied.
3. `GET /api/v1/me` → `role=admin`, `tool_unlock` both false.

**Pass**: FR-019 + TEST_USER seed.

### V1 — Admin provision (US1)

1. Create Analyst (and optionally another Admin) → one-time credentials once; 24h expiry.
2. First Analyst login → forced password change.
3. Admin demotes/disables another Admin (including last) → allowed; recover via bootstrap.

**Pass**: FR-003–FR-006, FR-018, SC-002, SC-007, SC-009.

### V2 — Read-only User (US2)

Same as prior: dashboard/threats/scans RO; tasks/tools/admin denied.

**Pass**: FR-007, FR-014, SC-010.

### V3 — Manager tasks (US3)

Create/assign/start Red+Blue; both tool pages; filters; audit on-behalf start.

**Pass**: FR-010, SC-004, SC-005.

### V4 — Analyst unlock + notes (US4)

Red-only then both; notes/links; complete → Manager notified; reassign.

**Pass**: FR-008–009, FR-012–013, FR-017, SC-003, SC-006, SC-011.

### V5 — Lifecycle AuthZ (US5)

Manager Reviewed/Closed; Analyst denied Reviewed/Closed.

**Pass**: FR-011, SC-008, SC-012.

### V6 — Access Matrix sweep (SC-001)

Script against [access-matrix.json](./contracts/access-matrix.json) + [live-tools-and-identity.md](./contracts/live-tools-and-identity.md) `/me` unlock fields.

### V7 — Live tools (delivery delta)

1. Manager/Analyst with unlock starts Red **surface-recon** on allowlisted asset.
2. Job leaves stub: `tool_runs.tool_name` ≠ `nmap-stub`; findings `source_tool` from HexStrike; HexStrike server receives request.
3. **deep-emulation** with `CAI_STUB=0` produces chain steps / `source_tag=cai` (or job `failed` with clear error if CAI down — not silent stub success).
4. With `HEXSTRIKE_STUB=1` in CI, stub path still completes for regression.

**Pass**: research R12; no silent fake success when stubs off.

## References

- [spec.md](./spec.md)  
- [plan.md](./plan.md)  
- [research.md](./research.md)  
- [data-model.md](./data-model.md)  
- [contracts/](./contracts/)  
