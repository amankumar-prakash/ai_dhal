# Live tool & identity contracts (002 delivery deltas)

Companion to [openapi.yaml](./openapi.yaml), [access-matrix.json](./access-matrix.json), [route-guards.md](./route-guards.md).

## `GET /api/v1/me`

Authenticated analyst JWT. Returns:

```json
{
  "user_id": "uuid",
  "email": "string|null",
  "role": "user|security_analyst|security_manager|admin",
  "profile": { "status": "active|pending|disabled", "must_change_password": false },
  "tool_unlock": { "red": false, "blue": false }
}
```

`tool_unlock` computed per [data-model.md](../data-model.md) predicates. Used by UI route guards.

## Roles

- `GET /api/v1/roles` — Admin or Manager (Manager: read for assignee pickers); Admin full list.
- `POST /api/v1/roles` — Admin only; body `{ user_id, role }` with four `app_role` values.
- Principal resolution: DB `user_roles` after JWT verify (see research R13).

## Tasks (API)

CRUD + transitions under Access Matrix. Starting tools from `/tools/*` calls existing `POST /api/v1/jobs` with `team`/`profile`/`asset_ids` and sets `tasks.linked_job_id`.

## Bootstrap Admin

CLI (not HTTP): `python scripts/bootstrap_admin.py` using root `.env` `TEST_USERNAME` / `TEST_PASSWORD`.

## Worker → HexStrike

| Env | Default |
|-----|---------|
| `HEXSTRIKE_BASE_URL` | `http://host.docker.internal:8888` |
| `HEXSTRIKE_STUB` | `0` in lab; `1` in CI |

Example: `POST {HEXSTRIKE_BASE_URL}/api/tools/nmap` with target from allowlisted asset. Fail job if HTTP error and stub off.

## Worker → CAI

| Env | Notes |
|-----|--------|
| `CAI_WORKDIR` | Path to `cai_pentesting` on worker host/volume |
| `CAI_STUB` | `1` = stub plan; `0` = live one-shot invoke |
| `OPENAI_API_KEY` / `CAI_*` | Red worker only |

Deep-emulation profile requires CAI or fails when stub off.

## Safety

- `DEMO_SAFE_MODE=1` + destructive profile → `blocked_by_guardrail` event, no HexStrike/CAI call.
- Empty `TARGET_ALLOWLIST` = allow all (lab); non-empty = host must match.
- Never expose HexStrike/CAI credentials to `secure_dash` or browser.
