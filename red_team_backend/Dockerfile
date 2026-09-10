# Red team worker — Debian slim (CAI disabled; LLMLingua-2 / torch need glibc).
# Build from repo root: docker compose build red_team_backend
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HEXSTRIKE_MCP_SCRIPT=/app/hexstrike/hexstrike_mcp.py \
    ARTIFACT_ROOT=/tmp/ai_dhal/jobs \
    HF_HOME=/var/cache/huggingface \
    LLMLINGUA_DEVICE=cpu

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /tmp/ai_dhal/jobs /var/cache/huggingface

COPY red_team_backend/requirements.txt .
# CPU torch first (smaller), then the rest of the lockfile deps
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt

COPY red_team_backend/app ./app
RUN mkdir -p /app/hexstrike
COPY hexstrike_server/hexstrike-ai/hexstrike_mcp.py /app/hexstrike/hexstrike_mcp.py

EXPOSE 8001

HEALTHCHECK --interval=10s --timeout=5s --retries=5 \
  CMD curl -f http://127.0.0.1:8001/health || exit 1

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
