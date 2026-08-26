# Security stack compose patterns (optional)

ai_dhal session: adding `hexstrike_server` to an existing API + worker stack.

## Service graph

```
api_service (8000)
  └── depends_on: red_team_backend, blue_team_backend

red_team_backend (8001)
  └── depends_on: hexstrike_server (healthy)

blue_team_backend (8002)
  └── depends_on: hexstrike_server (healthy)

hexstrike_server (8005)
  └── no upstream depends
```

## Key wiring change

**Before:** `HEXSTRIKE_BASE_URL=http://host.docker.internal:8888` (tool server on host)

**After:** `HEXSTRIKE_BASE_URL=http://hexstrike_server:8005` (in-stack DNS)

## hexstrike_server block (session)

```yaml
  hexstrike_server:
    build: ./hexstrike_server
    ports:
      - "8005:8005"
    environment:
      PYTHONUNBUFFERED: "1"
      HEXSTRIKE_PORT: "8005"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://127.0.0.1:8005/health"]
      interval: 15s
      timeout: 10s
      retries: 5
      start_period: 30s
```

## Verification (session results)

- `docker compose config --services` → 4 services
- `docker compose up -d hexstrike_server` → **healthy**
- `curl http://localhost:8005/health` → `status: healthy`, `version: 6.0.0`

Full stack template: [compose-template-multi-service.md](compose-template-multi-service.md)
