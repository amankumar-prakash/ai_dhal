# Quickstart Validation: Supabase Primary Store

**Feature**: `003-supabase-primary-db`  
**Date**: 2026-08-05

## Prerequisites

- Supabase project URL + **secret** API key (`sb_secret_...` or legacy service_role) in root `.env` ([contracts/env.md](./contracts/env.md))
- Publishable key in `secure_dash/.env`
- Project using **JWT signing keys** (or plan to migrate from legacy JWT secret) — see [Signing keys](https://supabase.com/docs/guides/auth/signing-keys)
- Migrations under `secure_dash/supabase/migrations/`

## 0. Confirm signing keys / JWKS

```bash
curl -sS "$SUPABASE_URL/auth/v1/.well-known/jwks.json"
# Expect {"keys":[...]} for asymmetric signing keys
```

Dashboard: **Project Settings → JWT** (signing keys). Prefer asymmetric (`ES256`). Do **not** configure the API to depend on the legacy JWT secret once you rotate.

## 1. Apply migrations

**Option A — Dashboard SQL**: paste `20260804120000_red_blue_platform.sql` (skip base if already applied).

**Option B**: `DATABASE_URL=... ./scripts/apply_supabase_migrations.sh`

**Option C**: `cd secure_dash && supabase db push`

## 2. Configure API

```bash
# root .env
API_STORE=supabase
SUPABASE_URL=https://<ref>.supabase.co
SUPABASE_SECRET_KEY=sb_secret_...          # preferred
# SUPABASE_SERVICE_ROLE_KEY=...            # legacy alias OK temporarily
# Do NOT set SUPABASE_JWT_SECRET unless still on legacy HS256-only
```

```bash
cd api_service
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
curl -sf http://localhost:8000/api/v1/ready
```

## 3. Verify schema

```bash
curl -s "$SUPABASE_URL/rest/v1/jobs?select=id&limit=1" \
  -H "apikey: $SUPABASE_PUBLISHABLE_KEY" \
  -H "Authorization: Bearer $SUPABASE_PUBLISHABLE_KEY"
# Expect 200, NOT PGRST205
```

## 4. Auth + persistence smoke

1. Sign in via UI → call protected API with access token  
2. API must accept JWTs signed by the **current signing key** (JWKS verify)  
3. Restart API → data still present  
4. Confirm no secret key in browser env

## 5. Realtime (optional)

Threats view updates after API insert without full reload.

## Pass criteria

SC-001–SC-006 in [spec.md](./spec.md), plus: signed-in API calls succeed **without** `SUPABASE_JWT_SECRET` when JWKS is available.

## Schema verify script

```bash
chmod +x scripts/verify_supabase_schema.sh
./scripts/verify_supabase_schema.sh
```
