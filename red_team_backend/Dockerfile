# Red team worker — Kali Linux base; CAI runs in this container via `uv run cai`.
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
RUN python3 -m pip install --no-cache-dir --break-system-packages -r requirements.txt uv \
    && mkdir -p /var/cache/cai-venv

COPY app ./app

ENV PYTHONUNBUFFERED=1 \
    CAI_WORKDIR=/cai \
    UV_PROJECT_ENVIRONMENT=/var/cache/cai-venv \
    CAI_CONTAINER_VENV=/var/cache/cai-venv

EXPOSE 8001
CMD ["python3", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
