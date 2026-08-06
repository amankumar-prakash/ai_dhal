# Threat model (stub)

## Trust boundaries

1. **Browser** — Supabase Auth session only. No DB write keys. Business mutations go through the platform API with the user JWT.
2. **api_service** — Sole holder of `DATABASE_URL` / Supabase service role. Enforces JWT and service-token AuthZ.
3. **red_team_backend / blue_team_backend** — Hold `OPENAI_API_KEY` + service tokens. **Must not** receive DB credentials. Report findings/events via API.

## Assets at risk

- LLM API keys on workers
- Service tokens that can insert findings / patch jobs
- JWT secret used to validate analyst sessions

## Mitigations (lab)

- `DEMO_SAFE_MODE` + `TARGET_ALLOWLIST` on red worker
- Service tokens denied for asset delete and role assignment
- `LLM_STUB=1` for offline/CI (no live LLM calls)
- Browser RLS: SELECT-only on operational tables after migration

## Out of scope (this stub)

Full STRIDE treatment, production key rotation, and network segmentation beyond Compose service isolation.
