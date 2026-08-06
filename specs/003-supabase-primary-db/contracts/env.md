# Environment: Supabase primary store

**Auth docs**: [JWT Signing Keys](https://supabase.com/docs/guides/auth/signing-keys)

## Root `.env` (api_service — never commit real values)

```bash
API_STORE=supabase
SUPABASE_URL=https://<project-ref>.supabase.co

# Elevated Data API key (API ONLY) — prefer new secret key
SUPABASE_SECRET_KEY=sb_secret_...
# Alias still accepted in implement for legacy JWT-based service_role:
# SUPABASE_SERVICE_ROLE_KEY=eyJ...

# User JWT verification: JWKS (signing keys) — no shared JWT secret required
# Discovery URL is derived: {SUPABASE_URL}/auth/v1/.well-known/jwks.json
# SUPABASE_JWKS_URL=   # optional override

# DEPRECATED — only if project still on legacy JWT secret / HS256 and not migrated:
# SUPABASE_JWT_SECRET=

# DATABASE_URL=   # optional; for scripts/apply_supabase_migrations.sh
```

## `secure_dash/.env` (browser)

```bash
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_PUBLISHABLE_KEY=sb_publishable_...
VITE_SUPABASE_URL=...
VITE_SUPABASE_PUBLISHABLE_KEY=...
VITE_API_BASE_URL=http://localhost:8000/api/v1
# NEVER put SUPABASE_SECRET_KEY / service_role here
```

## Ownership

| Variable | api_service | workers | secure_dash |
|----------|-------------|---------|-------------|
| `SUPABASE_URL` | yes | no | yes |
| `SUPABASE_SECRET_KEY` / service_role | yes | **no** | **no** |
| Publishable key | no | no | yes |
| JWKS (public) | fetched by API | no | optional (client libs) |
| Legacy `SUPABASE_JWT_SECRET` | deprecated optional | no | no |
| `OPENAI_API_KEY` | **no** | yes | no |

## Signing keys vs API keys

| Concern | Mechanism |
|---------|-----------|
| Who can call Data API as backend | Secret / service_role **API key** |
| How to verify user access tokens | **Signing keys** via JWKS (`ES256`/`RS256` preferred) |
| Browser Auth + Realtime | Publishable / anon **API key** |

Do not confuse the legacy “JWT Secret” dashboard value with the new signing-keys system. After migration, verifying every JWT only against the legacy secret **will break** when Auth rotates to asymmetric keys.

## Ready check

API `/api/v1/ready` MUST fail clearly if `API_STORE=supabase` and URL/secret key missing.  
When JWKS mode is enabled, ready MAY probe JWKS reachability (optional soft check).
