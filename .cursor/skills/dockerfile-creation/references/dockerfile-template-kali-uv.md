# Dockerfile template — Kali + uv + Python API (security tooling)

Based on `hexstrike_server/Dockerfile` and `red_team_backend/Dockerfile`.

```dockerfile
# [Service name] — Kali Linux base; runs via `uv run [entry].py`.
# Build: docker build -t [image] .
# Run:   docker run --rm -p [PORT]:[PORT] [image]
FROM kalilinux/kali-rolling

ENV DEBIAN_FRONTEND=noninteractive

# System + build deps
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        python3-venv \
        curl \
        ca-certificates \
        wget \
        gnupg \
        build-essential \
        libffi-dev \
        libssl-dev \
        libxml2-dev \
        libxslt1-dev \
        zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Optional: Browser Agent (Kali package names)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        chromium \
        chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# Optional: Google Chrome (prefer signed-by keyring over apt-key)
RUN wget -q -O /tmp/linux_signing_key.pub https://dl.google.com/linux/linux_signing_key.pub \
    && gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg /tmp/linux_signing_key.pub \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" \
       > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends google-chrome-stable \
    && rm -rf /var/lib/apt/lists/* /tmp/linux_signing_key.pub

WORKDIR /app

# Layer cache: deps before source
COPY [subdir]/requirements.txt .

RUN python3 -m pip install --no-cache-dir --break-system-packages uv \
    && uv python install 3.12 \
    && uv init . --python 3.12 --name [project-name] \
    && uv python pin 3.12 \
    && uv add -r requirements.txt

COPY [subdir]/ .

ENV PYTHONUNBUFFERED=1 \
    CHROME_BIN=/usr/bin/google-chrome-stable \
    CHROMIUM_PATH=/usr/bin/chromium \
    CHROMEDRIVER_PATH=/usr/bin/chromedriver

EXPOSE [PORT]

CMD ["uv", "run", "[entry].py", "--port", "[PORT]"]
```

## Optional hardening block (append before CMD)

```dockerfile
RUN groupadd -r appuser && useradd -r -g appuser -d /app appuser \
    && chown -R appuser:appuser /app
USER appuser
```

Note: Chrome/Selenium may need extra caps or `--no-sandbox` flags when non-root.
