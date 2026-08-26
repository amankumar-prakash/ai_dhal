# Dockerfile template — Kali + uv + uvicorn worker

Based on `red_team_backend/Dockerfile`.

```dockerfile
# Worker — Kali Linux base; CAI/app runs in this container.
# Optional tools: docker build --build-arg KALI_METAPACKAGE=kali-linux-headless .
FROM kalilinux/kali-rolling

ARG KALI_METAPACKAGE=
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        python3-venv \
        curl \
        ca-certificates \
    && if [ -n "$KALI_METAPACKAGE" ]; then \
         apt-get install -y --no-install-recommends $KALI_METAPACKAGE; \
       fi \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN python3 -m pip install --no-cache-dir --break-system-packages uv \
    && uv python install 3.12 \
    && uv init . --python 3.12 \
    && uv add -r requirements.txt \
    && mkdir -p /var/cache/cai-venv

COPY app ./app

ENV PYTHONUNBUFFERED=1 \
    CAI_WORKDIR=/cai \
    UV_PROJECT_ENVIRONMENT=/var/cache/cai-venv \
    CAI_CONTAINER_VENV=/var/cache/cai-venv

EXPOSE 8001
# Use app venv explicitly when runtime UV_PROJECT_ENVIRONMENT is for another tool.
CMD ["/app/.venv/bin/python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
```
