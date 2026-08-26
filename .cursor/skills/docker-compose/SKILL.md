---
name: docker-compose
description: >-
  Creates, reviews, and hardens docker-compose.yml files — service wiring,
  depends_on with health conditions, env_file handling, volumes, networking,
  and healthchecks. Use whenever the user mentions docker-compose, compose file,
  docker compose up, multi-container setup, add a service to compose,
  container orchestration, service dependencies, "wire up containers," stack
  deployment, or asks why compose services won't start in order — even if they
  don't say "docker skill." Pair with dockerfile-creation for new services.
---

# Docker Compose

Orchestrate multi-container stacks for **any** application: add services, wire
internal DNS, enforce startup order via healthchecks, and keep secrets out of
committed files.

For single-container images, see [dockerfile-creation skill](../dockerfile-creation/SKILL.md).

**Optional:** ai_dhal / security-tooling stack patterns are in
[references/security-stack-patterns.md](references/security-stack-patterns.md).

---

## 1. Mandatory requirements (ask if missing — do not guess)

Before editing `docker-compose.yml`:

| # | Requirement | Notes |
|---|-------------|-------|
| 1 | **Services list + roles** | API gateway, workers, tool servers, databases |
| 2 | **Build context vs image** | `build: ./path` or `image: name:tag` |
| 3 | **Port mappings** | Host:container; avoid conflicts |
| 4 | **Inter-service URLs** | Use service names, not `localhost`, for container-to-container |
| 5 | **Env vars + secrets** | `env_file` + `environment`; never commit real secrets |
| 6 | **Volumes** | Bind mounts for dev (`../cai_pentesting:/cai`); named for prod data |
| 7 | **depends_on + health** | `condition: service_healthy` when downstream needs ready upstream |
| 8 | **Healthcheck per service** | Match actual endpoint path |
| 9 | **Networks** | Default bridge usually fine; custom network if isolation needed |
| 10 | **Platform / profiles** | Optional `profiles:` for dev-only or heavy services |

## Core conventions (all stacks)

| Pattern | Rule |
|---------|------|
| Internal URLs | `http://<service_name>:<port>` — compose DNS = service key, not `localhost` |
| Secrets | `env_file: .env` (gitignored) + `${VAR:-default}` in `environment` |
| Startup order | `depends_on: svc: condition: service_healthy` when downstream is HTTP client on boot |
| Host → container | `ports: ["HOST:CONTAINER"]` |
| Host machine from container | `extra_hosts: ["host.docker.internal:host-gateway"]` (Linux) |

---

## 2. Step-by-step workflow

```
Progress:
- [ ] 1. Read existing compose file and service dependency graph
- [ ] 2. Add new service (build/image, ports, environment, healthcheck)
- [ ] 3. Set start_period on slow-boot services
- [ ] 4. Update consumer env vars to internal service URLs
- [ ] 5. Add depends_on with service_healthy where needed
- [ ] 6. docker compose config — validate YAML
- [ ] 7. docker compose up -d [service]
- [ ] 8. Verify health from host + cross-container if applicable
```

### Service block template

```yaml
  my_service:
    build: ./my_service          # or image: org/my-service:tag
    ports:
      - "8080:8080"
    env_file: .env
    environment:
      UPSTREAM_URL: ${UPSTREAM_URL:-http://other_service:9000}
    healthcheck:
      test: ["CMD", "curl", "-f", "http://127.0.0.1:8080/health"]
      interval: 15s
      timeout: 10s
      retries: 5
      start_period: 30s
```

### Wiring downstream consumers

```yaml
  consumer_service:
    environment:
      API_URL: ${API_URL:-http://my_service:8080}
    depends_on:
      my_service:
        condition: service_healthy
```

### Validate before up

```bash
docker compose config
docker compose config --services
docker compose up -d my_service
docker compose ps
curl -f http://localhost:8080/health
```

---

## 3. Acceptance criteria (definition of done)

- [ ] `docker compose config` validates with no errors
- [ ] `docker compose up -d` starts all services without crash loops
- [ ] Services start in correct dependency order (healthy upstream before downstream)
- [ ] Each service healthcheck reports healthy within `start_period + retries * interval`
- [ ] Host-mapped ports reachable (`curl localhost:PORT/health`)
- [ ] Inter-container URLs work (exec into consumer, curl upstream by service name)
- [ ] Secrets loaded from `.env` / env_file — not hardcoded in compose
- [ ] Volume data survives `docker compose down` + `up` (when volumes defined)
- [ ] No port conflicts between services

---

## 4. Pitfalls

See [references/pitfalls.md](references/pitfalls.md).

Top general pitfalls:
- Using `localhost` for inter-container URLs → use service name
- `depends_on` without `service_healthy` → race on startup
- Missing `start_period` on slow services → false unhealthy
- Port conflicts with standalone containers on same host port
- Secrets committed in compose `environment` literals

---

## 5. Templates

- Generic multi-service: [references/compose-template-multi-service.md](references/compose-template-multi-service.md)

---

## 6. Validation

Sample exercise: [references/validation-checklist.md](references/validation-checklist.md)

---

## 7. Review checklist

1. Service names are valid DNS labels (lowercase, underscores OK in compose v2+)
2. `build.context` paths exist relative to compose file
3. Every long-boot service has healthcheck + `start_period`
4. Downstream `depends_on` uses `service_healthy` when HTTP client on start
5. `env_file: .env` documented in `.env.example`
6. No secrets with real values in committed compose
7. Comments explain non-obvious env overrides
