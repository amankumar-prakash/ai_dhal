# Red team worker — Alpine Python (CAI disabled).
# Build from repo root: docker compose build red_team_backend
FROM python:3.12-alpine

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HEXSTRIKE_MCP_SCRIPT=/app/hexstrike/hexstrike_mcp.py

WORKDIR /app

# curl for healthchecks; build deps only while installing wheels that need compile
RUN apk add --no-cache curl ca-certificates \
    && apk add --no-cache --virtual .build-deps \
        gcc \
        musl-dev \
        libffi-dev \
        openssl-dev

COPY red_team_backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && apk del .build-deps

COPY red_team_backend/app ./app
RUN mkdir -p /app/hexstrike
COPY hexstrike_server/hexstrike-ai/hexstrike_mcp.py /app/hexstrike/hexstrike_mcp.py

EXPOSE 8001

HEALTHCHECK --interval=10s --timeout=5s --retries=5 \
  CMD curl -f http://127.0.0.1:8001/health || exit 1

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
