# Contract: Supabase access patterns

**Client docs**: [supabase-py introduction](https://supabase.com/docs/reference/python/introduction)  
**Auth docs**: [JWT Signing Keys](https://supabase.com/docs/guides/auth/signing-keys)

## Backend data access (`api_service`)

```python
from supabase import create_client

supabase = create_client(settings.supabase_url, settings.supabase_secret_key)
supabase.table("assets").select("*").execute()
supabase.table("assets").insert({...}).execute()
supabase.table("jobs").update({"status": "running"}).eq("id", job_id).execute()
```

- Use **secret** API key (`sb_secret_...`) or legacy `service_role` only inside `api_service`.
- Enforce AuthZ in FastAPI before mutating; elevated keys bypass RLS.

## Backend user JWT verification (signing keys)

User `Authorization: Bearer <access_token>` MUST be verified against the project JWKS — **not** assumed HS256 with a shared JWT secret.

```http
GET {SUPABASE_URL}/auth/v1/.well-known/jwks.json
```

Implementer requirements:

1. Resolve signing key by JWT header `kid` from JWKS.
2. Accept asymmetric algs present in JWKS (commonly `ES256`, `RS256`).
3. Cache JWKS; refresh when `kid` unknown (standby/rotation).
4. Validate standard claims (`exp`, `sub`); map `role`/`app_metadata` for AuthZ as today.
5. Legacy path: if JWKS empty/unavailable **and** `SUPABASE_JWT_SECRET` set, allow HS256 for transitional labs only.

Do **not** hard-code `algorithms=["HS256"]` as the only verifier once the project uses signing keys.

## Frontend (`secure_dash`)

- `@supabase/supabase-js` with **publishable** key for Auth + Realtime.
- Business CRUD via `VITE_API_BASE_URL` + user Bearer access token.

## Workers

- No Supabase client; report via API + `X-Service-Token`.

## Migration verify (PostgREST)

After apply, these MUST NOT return `PGRST205` / `42703`:

- `GET /rest/v1/jobs?select=id&limit=1`
- `GET /rest/v1/patches?select=id&limit=1`
- `GET /rest/v1/tool_runs?select=id&limit=1`
- `GET /rest/v1/scans?select=team,job_id,source_service&limit=1`

## JWKS smoke

```bash
curl -sS "$SUPABASE_URL/auth/v1/.well-known/jwks.json" | head
# Expect JSON with "keys": [ ... ] when signing keys are enabled
```
