# Environment Contract (Compose / `.env`)

**Feature**: `001-red-blue-platform`  
**Updated**: 2026-08-04

Secrets live in repository **root** `.env` (gitignored). `.env.example` documents names only—never real keys.

## Variable ownership

| Variable | `api_service` | `red_team_backend` | `blue_team_backend` | `secure_dash` (browser) |
|----------|:-------------:|:------------------:|:-------------------:|:-----------------------:|
| `DATABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` | Yes | No | No | No |
| `SUPABASE_JWT_SECRET` (or JWKS URL) | Yes | No | No | No |

> **003 update**: Prefer JWKS signing-key verification and `SUPABASE_SECRET_KEY` (`sb_secret_…`). See [`../003-supabase-primary-db/contracts/env.md`](../003-supabase-primary-db/contracts/env.md). Legacy JWT secret is deprecated.
| `RED_SERVICE_TOKEN` | Yes (validate) | Yes (send) | No | No |
| `BLUE_SERVICE_TOKEN` | Yes (validate) | No | Yes (send) | No |
| `OPENAI_API_KEY` | No | **Yes** | **Yes** | No |
| `LLM_MODEL` | No | **Yes** | **Yes** | No |
| `LLM_BASE_URL` (optional) | No | Yes | Yes | No |
| `LLM_STUB` (optional, tests) | No | Yes | Yes | No |
| `VITE_API_BASE_URL` | No | No | No | Yes (public) |
| Allowlist / `DEMO_SAFE_MODE` | optional | Yes (red) | optional | No |

## Worker startup expectation

- Red and blue workers **require** `OPENAI_API_KEY` and `LLM_MODEL` for live LLM-backed pipelines.
- If `LLM_STUB=1`, workers may skip live provider calls (CI / HexStrike-only MVP).
- Missing LLM env without stub → fail readiness or fail LLM-dependent jobs with a clear error (do not silently call without auth).

## Compose sketch

```yaml
# illustrative — red_team_backend / blue_team_backend
env_file: .env
environment:
  OPENAI_API_KEY: ${OPENAI_API_KEY}
  LLM_MODEL: ${LLM_MODEL}
  # no DATABASE_URL here
```
