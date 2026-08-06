# Contract: CAI Chat Sessions & Stream

**Feature**: `004-cai-tools-chat`  
**Date**: 2026-08-06

## Auth

| Surface | Auth |
|---------|------|
| Browser → `api_service` | Bearer JWT; require `tool_unlock[team]` or Manager |
| `api_service` → worker | `X-Service-Token` (red or blue token matching `team`) |

Admin and User → **403** on all `/cai/*` routes.

## API (`api_service`) — prefix `/api/v1/cai`

### `POST /sessions`

Create or replace active session for `(user, team)`.

```json
{
  "team": "red",
  "task_id": null,
  "message": "Perform recon on http://10.0.2.2"
}
```

- If `message` present: spawn CAI with initial prompt (CLI argv) or spawn then write stdin.
- Response `201`:

```json
{
  "id": "uuid",
  "team": "red",
  "status": "starting",
  "task_id": null,
  "created_at": "ISO-8601"
}
```

### `POST /sessions/{id}/messages`

```json
{ "content": "follow-up prompt" }
```

Writes to CAI stdin; echoes `user_echo` on stream. `409` if session not `running`.

### `POST /sessions/{id}/stop`

Stops CAI process. `200` with final status.

### `GET /sessions/{id}`

Session metadata (no pid).

### `GET /sessions/{id}/events` — SSE

`Content-Type: text/event-stream`

Query: `after_seq` optional.

Each event:

```text
id: 42
event: cai
data: {"session_id":"...","seq":42,"type":"stdout","text":"...","ts":"..."}
```

Control types: `started`, `stdout`, `stderr`, `user_echo`, `status`, `error`, `ended`.

**Browser note**: Prefer `fetch` + `ReadableStream` with `Authorization` header (native `EventSource` cannot set Bearer).

## Worker endpoints — prefix `/cai` (service token)

Mirror of create / message / stop / events so API can proxy:

- `POST /cai/sessions` body includes `user_id` from API
- `POST /cai/sessions/{id}/messages`
- `POST /cai/sessions/{id}/stop`
- `GET /cai/sessions/{id}/events`

Workers validate service token only (API already enforced user AuthZ).

## Process contract

CAI runs **inside the Kali Red/Blue worker container** (see [kali-worker-runtime.md](./kali-worker-runtime.md)):

```bash
cd "$CAI_WORKDIR"    # typically /cai
export UV_PROJECT_ENVIRONMENT="${CAI_CONTAINER_VENV:-/var/cache/cai-venv}"
uv run cai           # or: uv run cai "<initial_prompt>"
```

Env (worker → child): `CAI_AGENT_TYPE`, `CAI_MODEL`, `OPENAI_API_KEY` / provider keys from worker env, `CAI_STREAM=true` recommended, `CAI_LICENSE_OFF=1` for lab if required, `PROMPT_TOOLKIT_NO_CPR=1`.

Stub: `CAI_CHAT_STUB=1` → synthetic timed stdout lines; no real process.

## Errors

| Code | When |
|------|------|
| 403 | No tool unlock / wrong role |
| 404 | Unknown session |
| 409 | Session not accepting messages |
| 503 / stream `error` | CAI workdir missing, spawn failed, guardrail block |

## Safety

- Do not stream secrets (redact lines matching `API_KEY=` patterns best-effort).
- Guardrail block → `type=error`, `text` explains `blocked_by_guardrail`.
