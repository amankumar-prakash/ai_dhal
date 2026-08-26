---
name: dockerfile-creation
description: >-
  Creates, reviews, and hardens Dockerfiles for any application container — base
  image selection, dependency install, non-root users, healthchecks, and layer
  caching. Use whenever the user mentions Dockerfile, containerize,
  containerization, docker build, docker image, "set up a Dockerfile," "why
  won't my container start," "container keeps crashing," image hardening,
  multi-stage builds, or needs to dockerize Python/Node/Go/web services — even
  if they don't say "docker skill."
---

# Dockerfile Creation

Build production-ready Dockerfiles for **any** application stack. Gather
requirements first, follow layer-caching best practices, verify against
acceptance criteria, then harden.

For multi-service stacks, also read [docker-compose skill](../docker-compose/SKILL.md).

**Optional:** Security-tooling patterns (Kali, uv, browser agents) are in
[references/security-tooling-patterns.md](references/security-tooling-patterns.md).

## Common base image choices

| Use case | Typical base |
|----------|--------------|
| Python API | `python:3.12-slim-bookworm` or distro + uv |
| Node.js | `node:20-alpine` or `node:20-bookworm-slim` |
| Go | multi-stage: `golang:1.22-alpine` → `alpine:3.19` |
| Needs OS packages / CLI tools | `ubuntu:24.04`, `debian:bookworm-slim` |
| Preinstalled security tools | `kalilinux/kali-rolling` (see security reference) |

Always document *why* when not using the language's official slim image.

---

## 1. Mandatory requirements (ask if missing — do not guess)

Before writing a Dockerfile, confirm or ask for:

| # | Requirement | Notes |
|---|-------------|-------|
| 1 | **Base image / OS + version** | Document *why* (e.g. Kali for preinstalled security tools) |
| 2 | **Language + runtime version** | e.g. Python 3.12 |
| 3 | **Package manager + manifest** | `requirements.txt`, `package.json`, `pyproject.toml`; uv/poetry/npm |
| 4 | **Exposed ports + protocol** | e.g. `8005/tcp` HTTP |
| 5 | **Env vars and secrets** | **Never** bake secrets into layers; use `env_file`, runtime `-e`, or build secrets |
| 6 | **Persistent data / volumes** | Named vs bind mounts; what must survive restart |
| 7 | **Networking** | Bridge default; inter-container DNS names; host.docker.internal needs |
| 8 | **Startup command / entrypoint** | e.g. `uv run hexstrike_server.py --port 8005`; init process if zombie-reaping needed |
| 9 | **Healthcheck** | HTTP endpoint (e.g. `/health`) or `CMD` probe |
| 10 | **Non-root user** | **Default yes** — create `appuser` unless root required (Chrome sandbox, raw sockets) |
| 11 | **Target platform** | amd64/arm64; `--platform` or buildx for multi-arch |
| 12 | **Multi-stage need** | Separate build deps from runtime when compile step is heavy |

Use `AskQuestion` or a short bullet list when 3+ items are unknown.

---

## 2. Step-by-step build workflow

```
Progress:
- [ ] 1. Read sibling Dockerfiles / project conventions in repo
- [ ] 2. Choose base image (slim official image unless OS tools required)
- [ ] 3. Add .dockerignore
- [ ] 4. Install system packages (single RUN, clean apt cache)
- [ ] 5. Copy dependency manifest only → install deps (cache layer)
- [ ] 6. Copy application source
- [ ] 7. Set ENV (e.g. PYTHONUNBUFFERED=1, bind 0.0.0.0)
- [ ] 8. Create non-root USER (default)
- [ ] 9. EXPOSE + CMD/ENTRYPOINT + HEALTHCHECK
- [ ] 10. docker build && docker run — verify health
```

### Step details

**1. Mirror existing patterns**
Check for Dockerfiles in the repo before inventing structure.

**2. Dependency layer (cache-friendly)**
Copy lockfiles/manifests before application source:
```dockerfile
WORKDIR /app
COPY requirements.txt .          # or package.json, go.mod, etc.
RUN pip install -r requirements.txt   # or npm ci, go mod download
COPY . .
```

**3. Python with uv (when project uses uv)**
```dockerfile
RUN pip install uv \
    && uv python install 3.12 \
    && uv init . --python 3.12 \
    && uv python pin 3.12 \
    && uv add -r requirements.txt
```

**4. CMD / bind address**
Services must listen on `0.0.0.0` inside the container for port mapping.
```dockerfile
EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

**5. Non-root user (default)**
```dockerfile
RUN addgroup --system app && adduser --system --ingroup app app \
    && chown -R app:app /app
USER app
```

**6. Verify**
```bash
docker build -t myapp .
docker run --rm -d --name test -p 8080:8080 myapp
curl -f http://localhost:8080/health
docker logs test
docker rm -f test
```

---

## 3. Acceptance criteria (definition of done)

- [ ] `docker build` completes with no errors
- [ ] Container starts and stays running (no crash loop)
- [ ] Healthcheck reports healthy within expected time (`start_period` if slow boot)
- [ ] Exposed port reachable from host (`curl` or equivalent)
- [ ] Volumes persist data across container recreate (if applicable)
- [ ] No secrets in image layers (`docker history --no-trunc <image>` spot-check)
- [ ] Runs as non-root unless explicitly justified
- [ ] Image size reasonable; multi-stage used when compile deps are large
- [ ] `.dockerignore` prevents `.git` / venv bloat

---

## 4. Pitfalls

See [references/pitfalls.md](references/pitfalls.md) for general and security-specific issues.

Top general pitfalls:
- Binding `127.0.0.1` instead of `0.0.0.0` → port mapping fails
- Copying source before deps → no layer cache, slow rebuilds
- Secrets in `ENV`/`ARG` → visible in `docker history`
- Missing `.dockerignore` → `.git`/venv bloats context
- Using slow endpoints as health probes

---

## 5. Templates

- Generic Python slim: [references/dockerfile-template-python-slim.md](references/dockerfile-template-python-slim.md)
- Security-tooling (Kali + uv): [references/dockerfile-template-kali-uv.md](references/dockerfile-template-kali-uv.md)

---

## 6. Validation

Run the sample exercise in [references/validation-checklist.md](references/validation-checklist.md)
to verify the skill works end-to-end.

---

## 7. Review checklist (hardening pass)

When reviewing an existing Dockerfile:

1. Secrets not in `ENV` or `ARG` defaults
2. `latest` tag pinned or justified
3. Minimal RUN layers; apt cache cleaned
4. Dependency manifest copied before full source
5. `HEALTHCHECK` or documented compose healthcheck
6. `EXPOSE` matches CMD port
7. Non-root `USER` set
8. No unnecessary `--privileged` or root-only caps
