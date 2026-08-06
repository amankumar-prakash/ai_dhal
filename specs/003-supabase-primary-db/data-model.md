# Data Model: Supabase Primary Store

**Feature**: `003-supabase-primary-db`  
**Date**: 2026-08-05  
**Baseline**: [001 data-model](../001-red-blue-platform/data-model.md) + migrations in `secure_dash/supabase/migrations/`

## Source of truth

| Layer | Role |
|-------|------|
| `20260729100800_*.sql` | Base enums/tables (assets, scans, findings, threat_events, chains, user_roles) + seed |
| `20260804120000_red_blue_platform.sql` | `team_side`, jobs, patches, tool_runs, team columns, revoke browser writes, RLS read policies |

No new domain entities in 003 — this feature **adopts** the existing model as the live Supabase schema.

## Apply order

1. Ensure base migration already applied (remote currently has base tables).
2. Apply `20260804120000_red_blue_platform.sql` (currently **not** applied — `jobs`/`patches`/`tool_runs` missing; `scans.team` missing).
3. Future changes → new timestamped SQL files only.

## RLS summary (post-001 extension)

| Principal | Business tables | `user_roles` |
|-----------|-----------------|--------------|
| `anon` / unauthenticated | No elevated access | No |
| `authenticated` (browser JWT) | SELECT (where policies exist); INSERT/UPDATE/DELETE revoked on operational tables | Self-read |
| `service_role` (API only) | Full access used by `api_service` after AuthZ | As implemented in API |

## Entity map (unchanged from 001)

```text
User ──requested_by──► Job ──┬──► Scan ──► Finding ──► Patch
                             │         │
                             │         └──► ThreatEvent
                             └──► ToolRun
Scan ──► AttackChain ──► AttackChainStep
Asset ◄── Scan | Finding | ThreatEvent | Patch
```

## Validation rules (runtime)

- Jobs: `asset_ids` non-empty
- Patch `applied` → finding `remediated`
- Terminal job status → further progress updates → 409

## Storage (optional P3)

- Recommended bucket name: `evidence` (lab)
- Helper stub: `api_service/app/db/storage.py` (`upload_bytes`, `create_signed_url`)
- Core job/scan pipelines must not require Storage
- Not required for jobs MVP

