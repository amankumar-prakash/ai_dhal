# Dockerfile validation checklist — sample exercise

Use this to verify the **dockerfile-creation** skill produces a working container.
The agent should complete this exercise using only the skill (no ad-hoc guessing).

## Exercise: containerize a minimal Python health API

**Goal:** Create a Dockerfile for a Flask/FastAPI app that exposes `GET /health`.

### Inputs (agent gathers or uses these defaults)

| Requirement | Default for exercise |
|-------------|---------------------|
| Base image | `python:3.12-slim-bookworm` |
| Runtime | Python 3.12 |
| Manifest | `requirements.txt` with `flask>=3.0` |
| Port | 8080 |
| Health | `GET /health` → `{"status":"ok"}` |
| Non-root | Yes |
| Secrets | None baked in |

### Agent steps

```
- [ ] 1. Confirm requirements (or use defaults above)
- [ ] 2. Write .dockerignore
- [ ] 3. Write Dockerfile from template (deps layer before COPY .)
- [ ] 4. Add USER app, EXPOSE 8080, HEALTHCHECK, CMD on 0.0.0.0
- [ ] 5. docker build -t skill-test-api .
- [ ] 6. docker run --rm -d --name skill-test -p 8080:8080 skill-test-api
- [ ] 7. curl -f http://localhost:8080/health
- [ ] 8. docker history skill-test-api — no secrets in layers
- [ ] 9. docker inspect — confirm User is not root (if USER set)
- [ ] 10. docker rm -f skill-test
```

### Acceptance criteria (must all pass)

| # | Criterion | Check command |
|---|-----------|---------------|
| 1 | Build succeeds | `docker build` exit 0 |
| 2 | Container stays up | `docker ps` shows running 30s+ |
| 3 | Health reachable | `curl -f http://localhost:8080/health` |
| 4 | Response body correct | contains `"status"` |
| 5 | No secrets in layers | `docker history --no-trunc skill-test-api` |
| 6 | Non-root (if required) | `docker inspect skill-test-api --format '{{.Config.User}}'` ≠ empty/root |
| 7 | Port mapping works | curl from host, not only inside container |

### Optional: security-tooling variant

Repeat with:
- Base: `kalilinux/kali-rolling`
- uv workflow per [security-tooling-patterns.md](security-tooling-patterns.md)
- Port 8005, entry `uv run server.py --port 8005`

Document build time if heavy deps present (>5 min acceptable with note).

### Report template

```markdown
## Dockerfile validation report

- Image: [name:tag]
- Base: [FROM line]
- Build: PASS / FAIL
- Runtime: PASS / FAIL (crash loop?)
- Health: PASS / FAIL
- Non-root: PASS / FAIL / N/A
- Secrets scan: PASS / FAIL
- Notes: [pitfalls hit, fixes applied]
```
