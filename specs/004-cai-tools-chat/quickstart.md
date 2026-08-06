# Quickstart: CAI Chat on Kali Workers (004)

**Feature**: `004-cai-tools-chat`  
**Date**: 2026-08-06

## Prerequisites

- RBAC usable (Manager or Analyst with tool unlock); Admin cannot open tools.
- Sibling CAI checkout: `~/workspace/cai_pentesting` (project source; host `.venv` optional for host CLI only).
- Root `.env`:

```bash
CAI_HOST_PATH=/home/kali/workspace/cai_pentesting
CAI_WORKDIR=/cai
CAI_CHAT_STUB=0
CAI_STUB=0
CAI_CONTAINER_VENV=/var/cache/cai-venv
DEMO_SAFE_MODE=1
TARGET_ALLOWLIST=
OPENAI_API_KEY=…          # on workers via compose env_file
```

- Rebuild **Kali** workers after Dockerfile changes:

```bash
docker compose build red_team_backend blue_team_backend
docker compose up -d red_team_backend blue_team_backend api_service
```

- Warm CAI env inside Kali (once per image/volume lifecycle):

```bash
docker compose exec red_team_backend \
  sh -c 'cd /cai && UV_PROJECT_ENVIRONMENT=/var/cache/cai-venv uv sync'
# optional: same for blue_team_backend
```

- UI `:8080`, API `:8000`.

## V0 — Prove Kali base

```bash
docker compose exec red_team_backend grep -i kali /etc/os-release
docker compose exec blue_team_backend grep -i kali /etc/os-release
```

**Expect**: Kali ID/name lines present.

## V1 — Red chat stream (MVP)

1. Sign in as Manager (or Analyst with Red unlock).
2. Open `/tools/red`.
3. Send a lab-safe prompt (or allowlisted target).
4. **Expect**: status → running; CAI banner/lines stream; first line within ~10s when model is up.

## V2 — Follow-up turn

1. With session running, send a second message.
2. **Expect**: `user_echo` then more stdout (stdin to CAI).

## V3 — Stop

1. Click **Stop**.
2. **Expect**: `ended` / stopped; no orphan CAI for that session.

## V4 — Blue parity

1. Open `/tools/blue` with Blue unlock; send a message.
2. **Expect**: stream from blue Kali worker.

## V5 — AuthZ deny

1. As User or Admin: `POST /api/v1/cai/sessions` → **403**.

## V6 — Fail closed

1. `CAI_WORKDIR=/nonexistent` on red; restart; send chat.
2. **Expect**: visible `error` event; no infinite spinner.

## V7 — CI stub

1. `CAI_CHAT_STUB=1` → synthetic lines without real CAI.
2. Stub off + spawn failure → fail closed (no fake success).

## Worker-direct smoke (optional)

```bash
curl -sS -X POST http://127.0.0.1:8001/cai/sessions \
  -H "X-Service-Token: $RED_SERVICE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"lab","team":"red","message":"ping"}'
# then GET .../events with same token
```

## References

- [contracts/cai-chat-stream.md](./contracts/cai-chat-stream.md)
- [contracts/kali-worker-runtime.md](./contracts/kali-worker-runtime.md)
- [data-model.md](./data-model.md)
