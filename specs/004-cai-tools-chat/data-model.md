# Data Model: CAI Chat Sessions + Kali Runtime (004)

**Feature**: `004-cai-tools-chat`  
**Date**: 2026-08-06

MVP storage is **ephemeral on Kali workers** (in-process). Shapes below are API/UI contracts; Postgres tables are optional follow-up.

## Enums

### `cai_team`

`red` | `blue`

### `cai_session_status`

`starting` | `running` | `stopping` | `stopped` | `failed`

### `cai_stream_event_type`

`started` | `stdout` | `stderr` | `user_echo` | `status` | `error` | `ended`

## Entities

### KaliWorkerRuntime (deployment entity)

| Field | Notes |
|-------|--------|
| `team` | `red` / `blue` |
| `base_image` | `kalilinux/kali-rolling` (+ optional digest pin) |
| `cai_workdir` | e.g. `/cai` (bind mount of sibling repo) |
| `cai_container_venv` | e.g. `/var/cache/cai-venv` (not host `.venv`) |
| `service_token_env` | `RED_SERVICE_TOKEN` / `BLUE_SERVICE_TOKEN` |
| `agent_type` | from env |

**Rules**:
- FastAPI worker and CAI child process share this runtime (same container).
- Host-mounted project `.venv` is **not** a runtime dependency.

### CaiChatSession

| Field | Notes |
|-------|--------|
| `id` | UUID |
| `team` | red / blue |
| `user_id` | JWT subject (owner) |
| `status` | see enum |
| `task_id` | optional UUID context from UI search param |
| `agent_type` | e.g. `redteam_agent` |
| `pid` | worker-local only (not exposed to browser) |
| `created_at`, `updated_at`, `ended_at` | |
| `error` | last failure message if `failed` |

**Rules**:
- One **active** (`starting`|`running`) session per `(user_id, team)` in v1.
- Only owner may message/stop.
- Stop → `stopping` → `stopped` (or `failed` if kill errors).

### CaiChatMessage (logical)

| Field | Notes |
|-------|--------|
| `session_id` | |
| `role` | `user` (assistant text arrives as stream events in MVP) |
| `content` | non-empty trimmed string |
| `created_at` | |

### CaiStreamEvent

| Field | Notes |
|-------|--------|
| `session_id` | |
| `seq` | monotonic int per session |
| `type` | `cai_stream_event_type` |
| `text` | line/chunk for stdout/stderr/user_echo/error |
| `ts` | ISO timestamp |

**Buffer**: Worker keeps last N events (e.g. 2000) for SSE reconnect (`?after_seq=`).

## State machine

```text
(none) ──create/send──► starting ──process_up──► running
                           │                      │
                           │                      ├── message → stdin write (stay running)
                           │                      ├── stop → stopping → stopped
                           │                      └── crash → failed
                           └── spawn_error ──► failed
```

## Relationships

```text
KaliWorkerRuntime (red|blue)
  └── hosts CaiChatSession*
        └── emits CaiStreamEvent*

User ── owns ── CaiChatSession (per team)
Optional Task ── context only ── Session.task_id
```

## Non-goals (v1)

- Persisting full transcripts to Supabase
- Sharing sessions across users
- Choosing arbitrary shell commands from UI outside CAI stdin
- Separate Kali sidecar container for CAI
- Shipping full `kali-linux-large` by default
