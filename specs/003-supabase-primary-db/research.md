# Research: Supabase as Primary Data & Auth Platform

**Feature**: `003-supabase-primary-db`  
**Date**: 2026-08-05  
**Delta**: 2026-08-05 — JWT **signing keys** (not legacy JWT secret) per [Signing keys guide](https://supabase.com/docs/guides/auth/signing-keys)

## R1 — Python data access client

- **Decision**: Use official **supabase-py** (`supabase` package) in `api_service` with `create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)` (prefer `sb_secret_...`; legacy `service_role` JWT still works until disabled) per [Python introduction](https://supabase.com/docs/reference/python/introduction).
- **Rationale**: Matches product mandate; supports table CRUD, filters, RPC; same mental model as JS client already used in UI.
- **Alternatives considered**: raw `asyncpg`/`DATABASE_URL` (more control, more code); PostgREST via httpx only (reimplements client). Rejected for speed-to-correctness and docs alignment.

## R2 — Default store mode

- **Decision**: Prefer `API_STORE=supabase` when URL + secret/service key are set; retain `memory` only when explicitly set or when credentials missing in local pytest.
- **Rationale**: Spec requires shared store as primary; memory remains useful for unit tests and air-gapped smoke.
- **Alternatives considered**: Always supabase (breaks offline pytest); always memory (current gap).

## R3 — Auth boundary + JWT verification (UPDATED)

- **Decision**: UI keeps `@supabase/supabase-js` Auth with **publishable** key (`sb_publishable_...`). Backend validates user access tokens via the project **JWKS** endpoint (asymmetric signing keys), **not** the legacy JWT secret:
  - Discovery: `GET {SUPABASE_URL}/auth/v1/.well-known/jwks.json`
  - Prefer algorithms from keys (typically `ES256` / `RS256`); cache JWKS with short TTL and refresh on `kid` miss
  - Optional lab fallback: shared-secret signing key / legacy JWT secret **only** if project has not migrated and `SUPABASE_JWT_SECRET` is set — document as deprecated
- **Rationale**: Supabase [signing keys](https://supabase.com/docs/guides/auth/signing-keys) system is recommended; legacy JWT secret is no longer recommended. Asymmetric verification is local/fast, supports zero-downtime rotation, and does not put Auth in the hot path. Publishable/secret API keys are independent of the signing key.
- **Alternatives considered**:
  - Always `HS256` + `SUPABASE_JWT_SECRET` — current `deps.py`; breaks after migrate/rotate to asymmetric keys
  - Call Auth on every request to validate — worse latency/reliability
  - `getClaims()` only on UI — API still needs local verification for Bearer tokens

## R4 — Migrations application

- **Decision**: Source of truth remains `secure_dash/supabase/migrations/*.sql`. Apply via SQL Editor, `supabase db push`, or `DATABASE_URL` + `scripts/apply_supabase_migrations.sh`. Verify with PostgREST probes.
- **Rationale**: Remote may lack red/blue extension tables/columns.
- **Alternatives considered**: Auto-migrate on API startup (risky); dashboard-only edits (not versioned).

## R5 — RLS + elevated API key

- **Decision**: Keep RLS enabled; API uses **secret** API key (`sb_secret_...`) or legacy `service_role` JWT for data access after FastAPI AuthZ. Browser uses publishable key only.
- **Rationale**: Aligns with 001 design + new [API keys](https://supabase.com/docs/guides/getting-started/api-keys) model.
- **Alternatives considered**: Disable RLS; grant authenticated INSERT again.

## R6 — Realtime & Storage

- **Decision**: Realtime on published tables; Storage deferred to P3.
- **Rationale**: Spec P2/P3 priorities.
- **Alternatives considered**: Polling-only; local disk as SoR.

## R7 — Credentials layout (UPDATED)

- **Decision**:
  - Root `.env` (API): `SUPABASE_URL`, `SUPABASE_SECRET_KEY` (or `SUPABASE_SERVICE_ROLE_KEY` alias), `API_STORE=supabase`. **Do not require** `SUPABASE_JWT_SECRET` for primary path.
  - Optional: `SUPABASE_JWT_SECRET` / `SUPABASE_JWT_AUD` only for legacy HS256 projects.
  - `secure_dash/.env`: URL + `SUPABASE_PUBLISHABLE_KEY` / `VITE_*` (no secret key).
- **Rationale**: Signing keys ≠ API keys; JWKS covers user JWT verify; secret key is for backend Data API only.
- **Alternatives considered**: Mandating JWT secret for all deploys (fails modern projects).

## R8 — Signing key algorithm preference

- **Decision**: Prefer project **asymmetric** signing key (NIST P-256 / `ES256` recommended by Supabase). API verifies with JWKS. Do not mint user JWTs in `api_service` unless importing a private key for that purpose (out of scope).
- **Rationale**: Best practices from signing-keys guide; shared-secret signing keys are discouraged for production.
- **Alternatives considered**: Import HMAC shared secret as signing key (simpler PyJWT, weaker ops story).
