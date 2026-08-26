# HexStrike AI MCP server — Kali Linux base; runs via `uv run hexstrike_server.py`.
# Pattern mirrors red_team_backend (uv + Python 3.12).
#
# Build from repo root:
#   docker compose build hexstrike_server
#   docker build -f hexstrike_server/Dockerfile -t hexstrike-server ./hexstrike_server
# Run:
#   docker run --rm -p 8005:8005 hexstrike-server
FROM kalilinux/kali-rolling

ENV DEBIAN_FRONTEND=noninteractive \
    GOPATH=/opt/go \
    PATH="/opt/go/bin:/usr/local/bin:${PATH}"

# System + build deps for Python/uv and Go tool installs
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        python3-venv \
        curl \
        ca-certificates \
        wget \
        gnupg \
        unzip \
        build-essential \
        libffi-dev \
        libssl-dev \
        libxml2-dev \
        libxslt1-dev \
        zlib1g-dev \
        golang-go \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------------
# Security tools (HexStrike README essential set)
# httpx → httpx-toolkit (Kali); exiftool → libimage-exiftool-perl;
# strings/objdump → binutils
# ---------------------------------------------------------------------------
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        # Network & Reconnaissance
        nmap \
        masscan \
        amass \
        subfinder \
        nuclei \
        fierce \
        dnsenum \
        autorecon \
        theharvester \
        responder \
        netexec \
        enum4linux-ng \
        # Web Application Security
        gobuster \
        feroxbuster \
        dirsearch \
        ffuf \
        dirb \
        httpx-toolkit \
        nikto \
        sqlmap \
        wpscan \
        arjun \
        paramspider \
        wafw00f \
        # Password & Authentication
        hydra \
        john \
        hashcat \
        medusa \
        patator \
        crackmapexec \
        evil-winrm \
        hash-identifier \
        ophcrack \
        ophcrack-cli \
        # Binary Analysis & Reverse Engineering
        gdb \
        radare2 \
        binwalk \
        ghidra \
        checksec \
        binutils \
        foremost \
        steghide \
        libimage-exiftool-perl \
    && rm -rf /var/lib/apt/lists/*

# Tools not packaged in this Kali image: rustscan (release), katana/dalfox (Go), volatility3 (pip)
RUN wget -qO /tmp/rustscan.deb.zip \
        https://github.com/bee-san/RustScan/releases/download/2.4.1/rustscan.deb.zip \
    && unzip -qo /tmp/rustscan.deb.zip -d /tmp/rustscan \
    && apt-get update \
    && apt-get install -y --no-install-recommends /tmp/rustscan/*.deb \
    && rm -rf /var/lib/apt/lists/* /tmp/rustscan /tmp/rustscan.deb.zip \
    && go install -v github.com/projectdiscovery/katana/cmd/katana@latest \
    && go install -v github.com/hahwul/dalfox/v2@latest \
    && install -m 0755 /opt/go/bin/katana /opt/go/bin/dalfox /usr/local/bin/ \
    && rm -rf /opt/go/pkg /opt/go/src /root/.cache/go-build \
    && python3 -m pip install --no-cache-dir --break-system-packages volatility3 \
    && ln -sf /usr/local/bin/vol /usr/local/bin/volatility3 \
    && apt-get purge -y golang-go \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Browser Agent: Chromium + chromedriver (Kali packages)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        chromium \
        chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# Google Chrome stable (alternative Browser Agent runtime)
RUN wget -q -O /tmp/linux_signing_key.pub https://dl.google.com/linux/linux_signing_key.pub \
    && gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg /tmp/linux_signing_key.pub \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" \
       > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends google-chrome-stable \
    && rm -rf /var/lib/apt/lists/* /tmp/linux_signing_key.pub

WORKDIR /app

COPY hexstrike-ai/requirements.txt .

# 1. Install uv
# 2. uv python install / pin 3.12
# 3. uv init
# 4. uv add -r requirements.txt
RUN python3 -m pip install --no-cache-dir --break-system-packages uv \
    && uv python install 3.12 \
    && uv init . --python 3.12 --name hexstrike-ai \
    && uv python pin 3.12 \
    && uv add -r requirements.txt

COPY hexstrike-ai/ .

ENV PYTHONUNBUFFERED=1 \
    CHROME_BIN=/usr/bin/google-chrome-stable \
    CHROMIUM_PATH=/usr/bin/chromium \
    CHROMEDRIVER_PATH=/usr/bin/chromedriver

EXPOSE 8005

HEALTHCHECK --interval=15s --timeout=10s --retries=5 --start-period=30s \
  CMD curl -f http://127.0.0.1:8005/health || exit 1

# Start the MCP / API server on port 8005
# Debug: docker run ... hexstrike-server uv run hexstrike_server.py --debug --port 8005
CMD ["uv", "run", "hexstrike_server.py", "--port", "8005"]
