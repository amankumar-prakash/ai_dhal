# Security-tooling Dockerfile patterns (optional)

Use when the container needs OS-level security tools, browser automation, or
matches a Kali-based worker fleet (e.g. ai_dhal, SentryOps-style stacks).

## When to use Kali vs slim images

| Choose Kali | Choose slim official image |
|-------------|---------------------------|
| Needs nmap, nuclei, etc. at runtime | Pure Python/Node API with HTTP clients only |
| Browser agent (Selenium) + many OS deps | Calls external tool server over HTTP |
| Team convention: all workers on Kali | Minimal attack surface preferred |

## ai_dhal session reference (HexStrike MCP server)

| Item | Value |
|------|-------|
| Purpose | HexStrike AI MCP/API server |
| Base | `kalilinux/kali-rolling` (switched from Ubuntu 24.04 per user request) |
| Python | 3.12 via uv |
| Key deps | flask, selenium, angr, pwntools, mitmproxy, fastmcp |
| Browser | chromium + Google Chrome stable |
| Port | 8005 (app default 8888 — align CMD + compose) |
| Start | `uv run hexstrike_server.py --port 8005` |
| Health | `GET /health` → `{"status":"healthy"}` |

## uv on Debian/Kali (PEP 668)

```dockerfile
python3 -m pip install --no-cache-dir --break-system-packages uv
```

Bootstrap `uv` only; app deps via `uv add` into project `.venv`.

## Browser packages by distro

| Distro | Chromium | Driver |
|--------|----------|--------|
| Kali | `chromium` | `chromium-driver` |
| Ubuntu | `chromium` or `chromium-browser` | `chromium-chromedriver` or `chromium-driver` |

Google Chrome repo: use `gpg --dearmor` + `signed-by=` — not deprecated `apt-key`.

## Templates

- Full Kali + uv: [dockerfile-template-kali-uv.md](dockerfile-template-kali-uv.md)
- Kali + uvicorn worker: [dockerfile-template-uvicorn.md](dockerfile-template-uvicorn.md)

## Known session gaps (harden next)

- Non-root user not added in initial HexStrike Dockerfile
- Heavy deps (angr/pwntools) → 5–10 min builds; set expectations
- `/api/intelligence/analyze-target` is slow — use `/health` for probes only
