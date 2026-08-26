# Docker Compose pitfalls

## General

### localhost for inter-container URLs

Inside a container, `localhost` is that container only. Use service name:
`http://tool_server:9000`.

### depends_on without health condition

Downstream starts before upstream is ready → connection refused on boot.
Use `condition: service_healthy` and define upstream healthcheck.

### Missing start_period

Slow-boot services (DB migrations, tool enumeration) fail first probes.
Add `start_period: 30s` (or longer).

### Port already allocated

Standalone `docker run -p PORT` conflicts with compose. Remove stale container first.

### Service name vs container name

DNS uses compose **service key**, not generated container name.

### Secrets in committed compose

Use `env_file: .env` and `${VAR:-placeholder}` — never real keys in YAML.

---

## Security-stack specific

See [security-stack-patterns.md](security-stack-patterns.md).

| Pitfall | Resolution |
|---------|------------|
| host.docker.internal for in-stack service | Use `http://hexstrike_server:8005` |
| Port 8888 vs 8005 mismatch | Align compose, Dockerfile CMD, worker env |
| Gateway depends on tool server unnecessarily | OK if only workers call tool server |
| Shell env overrides .env | Document `.env` as source of truth |
