# Implementation Plan: Supabase as Primary Data & Auth Platform

**Branch**: `003-supabase-primary-db` | **Date**: 2026-08-05 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-supabase-primary-db/spec.md`  
**Auth delta**: Prefer [JWT signing keys](https://supabase.com/docs/guides/auth/signing-keys) + JWKS verification; legacy JWT secret is deprecated.

## Summary

Replace the API’s default in-memory store with **Supabase Postgres** as the system of record, keep **Supabase Auth** as the sole UI identity provider, and access data from `api_service` via **[supabase-py](https://supabase.com/docs/reference/python/introduction)** using a **secret API key**. Verify user access tokens with the project **JWKS** (`/auth/v1/.well-known/jwks.json`) under the signing-keys system—not by hard-coding HS256 against a legacy JWT secret. Apply versioned migrations under `secure_dash/supabase/migrations/`. Workers never receive DB credentials.

## Technical Context

**Language/Version**: Python 3.12 (api_service); TypeScript (secure_dash)

**Primary Dependencies**: FastAPI; supabase-py; PyJWT (+ JWKS / `PyJWKClient`); `@supabase/supabase-js` (UI)

**Storage**: Supabase Postgres (primary); Storage optional (P3); Realtime for live UI

**Auth / JWT**: Asymmetric signing keys (`ES256` preferred) via JWKS; optional deprecated `SUPABASE_JWT_SECRET` fallback for unmigrated labs

**API keys**: Publishable (`sb_publishable_...`) on UI; secret (`sb_secret_...`) or legacy service_role on API only

**Testing**: pytest (memory or mocked JWKS); migration + JWKS smoke curls

**Target Platform**: Lab Linux + hosted Supabase project from root `.env`

**Project Type**: Monorepo web + API + workers

**Performance Goals**: Local JWT verify (no Auth round-trip per request) when using asymmetric keys

**Constraints**: Secret key only on API; no JWT secret required for modern projects; RLS on; migrations versioned; no secrets in git

**Scale/Scope**: Single lab project; 001 schema + red/blue extensions

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status |
|------|--------|
| DB / secret API credentials only on API | PASS |
| LLM keys only on workers | PASS |
| Browser never gets secret/service_role | PASS |
| Versioned migrations | PASS |
| RLS on application tables | PASS |
| User JWT verify without embedding extractable signing private key | PASS (JWKS / public keys) |

**Post-design re-check**: PASS — env + access contracts updated for signing keys (2026-08-05).

## Project Structure

### Documentation (this feature)

```text
specs/003-supabase-primary-db/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── env.md
│   └── supabase-access.md
└── tasks.md            # via /speckit-tasks
```

### Source Code (repository root)

```text
api_service/
├── requirements.txt
├── app/
│   ├── config.py              # secret key + optional JWKS URL; JWT_SECRET deprecated
│   ├── deps.py                # CHANGE — JWKS verify (not HS256-only)
│   ├── db/
│   │   ├── memory.py
│   │   └── supabase_client.py
│   └── services/crud.py       # supabase store path

secure_dash/
├── .env                       # publishable key only
└── supabase/migrations/

.env                           # URL + SECRET_KEY; no JWT_SECRET required
```

**Structure Decision**: Extend monorepo; JWT verification helper lives in `api_service` (e.g. `app/auth/jwks.py` or inside `deps.py`).

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Dual store (memory + supabase) | Offline CI | Memory-only blocks durable lab |
| JWKS + optional HS256 fallback | Zero-downtime migration from legacy | HS256-only breaks after signing-key rotation |
| Publishable/secret API keys vs signing keys | Independent rotation | Conflating JWT secret with API keys causes outages |
