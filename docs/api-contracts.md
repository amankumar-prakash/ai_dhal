# API contracts

Canonical OpenAPI: [`specs/001-red-blue-platform/contracts/openapi.yaml`](../specs/001-red-blue-platform/contracts/openapi.yaml)

Internal worker jobs: [`specs/001-red-blue-platform/contracts/internal-jobs.md`](../specs/001-red-blue-platform/contracts/internal-jobs.md)

**Supabase primary store + signing keys (003):** [`specs/003-supabase-primary-db/contracts/env.md`](../specs/003-supabase-primary-db/contracts/env.md) and [`supabase-access.md`](../specs/003-supabase-primary-db/contracts/supabase-access.md)

| Surface | Base | Auth |
|---------|------|------|
| Platform API | `http://localhost:8000/api/v1` | Bearer user JWT (**JWKS** verify) or `X-Service-Token` (workers) |
| Red worker | `http://localhost:8001` | Internal `POST /internal/jobs` |
| Blue worker | `http://localhost:8002` | Internal `POST /internal/jobs` |
| secure_dash | Vite app | Supabase Auth + Realtime (publishable key); business CRUD via platform API |

**Keys**

- Browser: publishable (`sb_publishable_…`) only  
- API data: secret (`sb_secret_…`) or legacy service_role — never in `VITE_*`  
- User JWT: verify via `{SUPABASE_URL}/auth/v1/.well-known/jwks.json` (legacy JWT secret deprecated)
