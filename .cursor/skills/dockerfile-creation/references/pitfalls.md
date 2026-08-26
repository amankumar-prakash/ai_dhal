# Dockerfile pitfalls

## General

### Binding 127.0.0.1 instead of 0.0.0.0

Port mapping fails from host. Flask/uvicorn/gunicorn must bind `0.0.0.0`.

### Copy source before dependencies

Rebuilds reinstall deps every code change. Copy manifest/lockfile first.

### Secrets in ENV or ARG

Visible in `docker history`. Use runtime env, `env_file`, or build secrets.

### Missing .dockerignore

`.git`, `node_modules`, `.venv` inflate context and slow builds.

### Slow endpoint as HEALTHCHECK

Use a fast `/health` or `/ready` — not analytics or AI endpoints.

### Running as root

Default to non-root `USER` after installs. Document exception if Chrome/sandbox needs it.

---

## Security-tooling specific

See also [security-tooling-patterns.md](security-tooling-patterns.md).

| Pitfall | Resolution |
|---------|------------|
| Ubuntu vs Kali browser package names | Kali: `chromium`, `chromium-driver` |
| Deprecated `apt-key` for Chrome | `gpg --dearmor` + `signed-by=` keyring |
| Heavy Python deps (angr, pwntools) | 5–10 min builds; cache requirements layer |
| App default port ≠ CMD port | Align Dockerfile, compose, and client env URLs |
| Nested `.git` in COPY | `.dockerignore` with `**/.git` |
| PEP 668 on Kali/Debian pip | `--break-system-packages` only to bootstrap uv |
