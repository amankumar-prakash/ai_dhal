# Contracts: Red/Blue Platform

| Artifact | Purpose |
|----------|---------|
| [openapi.yaml](./openapi.yaml) | Platform REST API |
| [internal-jobs.md](./internal-jobs.md) | API → worker job dispatch |
| [env.md](./env.md) | Root `.env` ownership — DB on API; **LLM keys on red + blue workers** |

---

# OpenAPI Contract: Platform API (`api_service`)

**Version**: 0.1.0  
**Base path**: `/api/v1`  
**Auth**:
- Analyst/Admin: `Authorization: Bearer <supabase_access_token>`
- Workers: `X-Service-Token: <shared_secret>`

Normative machine-readable file: [openapi.yaml](./openapi.yaml)

## Endpoint summary

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/health` | none | Liveness |
| GET | `/ready` | none | Readiness (DB reachable) |
| GET/POST | `/assets` | JWT | List / create assets |
| GET/PATCH/DELETE | `/assets/{id}` | JWT (DELETE admin) | Asset detail / update / delete |
| GET/POST | `/scans` | JWT | List / create scans |
| GET/PATCH/DELETE | `/scans/{id}` | JWT (DELETE admin) | Scan detail |
| GET/POST | `/findings` | JWT or service (POST) | List / create findings |
| GET/PATCH | `/findings/{id}` | JWT or service | Update status etc. |
| GET/POST | `/threat-events` | JWT or service (POST) | List / create events |
| GET/POST | `/attack-chains` | JWT or service | Chains |
| GET/POST | `/attack-chains/{id}/steps` | JWT or service | Steps |
| GET/POST | `/jobs` | JWT (POST create) | List / create jobs |
| GET/PATCH | `/jobs/{id}` | JWT or service (PATCH status) | Get / update / cancel |
| POST | `/jobs/{id}/cancel` | JWT | Cancel job |
| GET/POST | `/patches` | JWT (service may PATCH apply evidence) | Patches |
| GET/PATCH | `/patches/{id}` | JWT | Propose→apply lifecycle |
| GET/POST | `/tool-runs` | service | Audit tool invocations |
| GET | `/roles` | JWT | List roles (self/admin rules) |
| POST/DELETE | `/roles` | JWT admin | Manage roles |

## Job create payload (UI contract)

```json
{
  "team": "red",
  "profile": "surface-recon",
  "asset_ids": ["uuid", "uuid"],
  "tools": null
}
```

Validation: `asset_ids` minItems 1 → else **422**.  
On success **201**: job + related scans in `queued`/`dispatched`.

## Worker internal dispatch (red/blue)

Not part of public OpenAPI; documented in [internal-jobs.md](./internal-jobs.md).

## AuthZ matrix (normative)

| Action | Anonymous | Analyst JWT | Admin JWT | Service token |
|--------|-----------|-------------|-----------|---------------|
| Any CRUD without auth | 401 | — | — | — |
| Create finding / threat event / tool_run | 401 | if allowed by route | yes | yes |
| DELETE asset | 401 | 403 | 204 | 403 |
| Change user_roles | 401 | 403 | 2xx | 403 |
| PATCH job status | 401 | limited | yes | yes |
| Cancel job | 401 | yes (own/ops policy) | yes | no (use PATCH carefully) |
| Progress write on cancelled/terminal job | — | 409 | 409 | 409 |
