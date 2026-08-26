# docker-compose.yml template — multi-service stack

Generic pattern: gateway + workers + shared upstream service.

```yaml
services:
  api_gateway:
    build: ./api_service
    ports:
      - "8000:8000"
    env_file: .env
    environment:
      WORKER_A_URL: http://worker_a:8001
      WORKER_B_URL: http://worker_b:8002
    healthcheck:
      test: ["CMD", "curl", "-f", "http://127.0.0.1:8000/health"]
      interval: 10s
      timeout: 5s
      retries: 5
    depends_on:
      worker_a:
        condition: service_healthy
      worker_b:
        condition: service_healthy

  worker_a:
    build: ./worker_a
    ports:
      - "8001:8001"
    env_file: .env
    environment:
      TOOL_SERVER_URL: ${TOOL_SERVER_URL:-http://tool_server:9000}
    depends_on:
      tool_server:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://127.0.0.1:8001/health"]
      interval: 10s
      timeout: 5s
      retries: 5

  worker_b:
    build: ./worker_b
    ports:
      - "8002:8002"
    env_file: .env
    environment:
      TOOL_SERVER_URL: ${TOOL_SERVER_URL:-http://tool_server:9000}
    depends_on:
      tool_server:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://127.0.0.1:8002/health"]
      interval: 10s
      timeout: 5s
      retries: 5

  tool_server:
    build: ./tool_server
    ports:
      - "9000:9000"
    environment:
      PYTHONUNBUFFERED: "1"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://127.0.0.1:9000/health"]
      interval: 15s
      timeout: 10s
      retries: 5
      start_period: 30s
```

## Adding a new service — checklist

1. Dockerfile in `./new_service/` (see dockerfile-creation skill)
2. Service block: `build`, `ports`, `healthcheck`
3. Update consumers: internal URL `http://new_service:PORT`
4. `depends_on: new_service: condition: service_healthy`
5. `docker compose config` then `docker compose up -d new_service`

## ai_dhal concrete example

See [security-stack-patterns.md](security-stack-patterns.md) for hexstrike_server wiring.
