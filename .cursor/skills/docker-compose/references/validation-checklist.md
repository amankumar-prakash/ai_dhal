# Docker Compose validation checklist — sample exercise

Use this to verify the **docker-compose** skill wires a multi-service stack correctly.

## Exercise: API + worker + dependency service

**Goal:** Add a third service (`tool_server`) that two workers depend on, with
correct health-gated startup order.

### Stack design

| Service | Port | Role |
|---------|------|------|
| `api_gateway` | 8000 | Public API; depends on workers |
| `worker_a` | 8001 | Calls `TOOL_SERVER_URL` on boot |
| `worker_b` | 8002 | Calls `TOOL_SERVER_URL` on boot |
| `tool_server` | 9000 | Upstream tool/API server |

### Agent steps

```
- [ ] 1. Gather ports, env vars, health paths (ask if missing)
- [ ] 2. Add tool_server with build, ports, healthcheck (+ start_period if slow)
- [ ] 3. Set worker env: TOOL_SERVER_URL=http://tool_server:9000
- [ ] 4. Add depends_on: tool_server: condition: service_healthy on both workers
- [ ] 5. Ensure api_gateway uses http://worker_a:8001 (not localhost)
- [ ] 6. docker compose config — no errors
- [ ] 7. docker compose up -d tool_server — wait healthy
- [ ] 8. docker compose up -d — full stack
- [ ] 9. curl host ports for each /health endpoint
- [ ] 10. docker compose exec worker_a curl -f http://tool_server:9000/health
```

### Acceptance criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | Config valid | `docker compose config` exit 0 |
| 2 | All services running | `docker compose ps` — no Restarting |
| 3 | tool_server healthy first | start_period respected; workers start after |
| 4 | Host ports reachable | curl each mapped /health |
| 5 | Internal DNS works | exec curl from worker → tool_server by name |
| 6 | No secrets in compose | literals are placeholders or ${VAR} refs |
| 7 | env_file pattern | secrets in `.env`, not committed |

### Anti-patterns to catch

- [ ] Worker uses `http://localhost:9000` for tool_server
- [ ] Worker uses `http://host.docker.internal:9000` when tool_server is in compose
- [ ] `depends_on: - tool_server` without `condition: service_healthy`
- [ ] Port collision (9000 already bound by standalone container)

### Report template

```markdown
## Compose validation report

- Services: [list]
- config: PASS / FAIL
- Startup order: PASS / FAIL
- Host health checks: PASS / FAIL
- Internal DNS: PASS / FAIL
- Secrets hygiene: PASS / FAIL
- Notes: [fixes applied]
```

### Optional: ai_dhal replay

Apply skill to add `hexstrike_server` per
[security-stack-patterns.md](security-stack-patterns.md) and confirm against
the same acceptance criteria.
