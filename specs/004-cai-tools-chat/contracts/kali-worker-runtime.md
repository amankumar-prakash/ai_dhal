# Contract: Kali Worker Runtime (Red/Blue)

**Feature**: `004-cai-tools-chat`  
**Date**: 2026-08-06

## Scope

Defines how Red/Blue backend containers are built and where CAI runs. Chat HTTP/SSE shapes remain in [cai-chat-stream.md](./cai-chat-stream.md).

## Image

| Service | Base | App |
|---------|------|-----|
| `red_team_backend` | `kalilinux/kali-rolling` | FastAPI on `:8001` |
| `blue_team_backend` | `kalilinux/kali-rolling` | FastAPI on `:8002` |
| `api_service` | **not** Kali (current Python slim) | proxies only |

### Dockerfile requirements (both workers)

1. `FROM kalilinux/kali-rolling` (optional digest pin in comments/CI).
2. `apt-get update` + install at least: `python3`, `python3-pip`, `python3-venv`, `curl`, `ca-certificates`.
3. Install `uv` and worker `requirements.txt`.
4. `mkdir -p /var/cache/cai-venv`.
5. Env defaults:
   - `CAI_WORKDIR=/cai`
   - `UV_PROJECT_ENVIRONMENT=/var/cache/cai-venv`
   - `CAI_CONTAINER_VENV=/var/cache/cai-venv`
6. Optional build-arg `KALI_METAPACKAGE` (default empty). If set, `apt-get install -y $KALI_METAPACKAGE` after update.
7. Expose worker port; `CMD` uvicorn as today.

## Compose

- Volume: `${CAI_HOST_PATH:-../cai_pentesting}:/cai`
- Pass through existing LLM / HexStrike / token / guardrail env vars.
- Healthcheck: HTTP to `/health` via `python3`.

## CAI process contract (inside Kali container)

```bash
cd "$CAI_WORKDIR"   # /cai
export UV_PROJECT_ENVIRONMENT="${CAI_CONTAINER_VENV:-/var/cache/cai-venv}"
uv run cai                 # or: uv run cai "<initial_prompt>"
```

| MUST | MUST NOT |
|------|----------|
| Run CAI as child of the Kali worker process | Run CAI on `api_service` or in the browser |
| Use Kali/`uv`-managed env under `CAI_CONTAINER_VENV` | Rely on host bind-mount `.venv/bin/*` shebangs |
| Fail closed if workdir missing or spawn fails | Silently stub when `CAI_CHAT_STUB=0` |

Child env (minimum): `CAI_AGENT_TYPE`, `OPENAI_API_KEY` / model vars from worker settings, `CAI_STREAM=true`, `CAI_LICENSE_OFF=1` (lab), `PROMPT_TOOLKIT_NO_CPR=1`.

## Acceptance probes

```bash
# OS
grep -qi kali /etc/os-release

# Toolchain
command -v uv
command -v python3

# Spawn path (live)
test -d "$CAI_WORKDIR"
```

## Out of scope

- Docker-in-Docker / privileged Kali nesting
- Guaranteeing full Kali tool metapackage contents in default image
- Changing UI or API AuthZ contracts (see 002 + cai-chat-stream)
