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

# System + build deps for Python/uv, Go tool installs, gems, and git clones
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
        git \
        ruby \
        ruby-dev \
        file \
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

# ---------------------------------------------------------------------------
# Phase 1 — extra Kali apt packages (skip if missing on this rolling snapshot)
# ---------------------------------------------------------------------------
RUN apt-get update \
    && for pkg in \
        arp-scan \
        nbtscan \
        samba-common-bin \
        smbclient \
        enum4linux \
        smbmap \
        hakrawler \
        getallurls \
        waybackurls \
        whatweb \
        wfuzz \
        commix \
        jwt-tool \
        sslscan \
        sslyze \
        testssl.sh \
        hashid \
        gdb-peda \
        ropper \
        python3-ropgadget \
        xxd \
        bsdextrautils \
        upx-ucl \
        outguess \
        recon-ng \
        sherlock \
        trufflehog \
        nosqlmap \
        httpie \
    ; do \
        if apt-get install -y --no-install-recommends "$pkg"; then \
            echo "installed $pkg"; \
        else \
            echo "SKIP missing apt package: $pkg"; \
        fi; \
    done \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /opt/jwt_tool \
    && if command -v httpx-toolkit >/dev/null 2>&1; then \
        ln -sf "$(command -v httpx-toolkit)" /usr/local/bin/httpx; \
    fi \
    && if command -v getallurls >/dev/null 2>&1 && ! command -v gau >/dev/null 2>&1; then \
        ln -sf "$(command -v getallurls)" /usr/local/bin/gau; \
    fi \
    && if command -v ROPgadget >/dev/null 2>&1; then \
        ln -sf "$(command -v ROPgadget)" /usr/local/bin/ropgadget; \
    fi \
    && if command -v netexec >/dev/null 2>&1 && ! command -v nxc >/dev/null 2>&1; then \
        ln -sf "$(command -v netexec)" /usr/local/bin/nxc; \
    fi \
    && if command -v jwt_tool >/dev/null 2>&1; then \
        ln -sf "$(command -v jwt_tool)" /usr/local/bin/jwt_tool; \
        ln -sf "$(command -v jwt_tool)" /opt/jwt_tool/jwt_tool.py; \
    elif command -v jwt-tool >/dev/null 2>&1; then \
        ln -sf "$(command -v jwt-tool)" /usr/local/bin/jwt_tool; \
        ln -sf "$(command -v jwt-tool)" /opt/jwt_tool/jwt_tool.py; \
    fi \
    && if command -v testssl >/dev/null 2>&1 && ! command -v testssl.sh >/dev/null 2>&1; then \
        ln -sf "$(command -v testssl)" /usr/local/bin/testssl.sh; \
    elif command -v testssl.sh >/dev/null 2>&1 && ! command -v testssl >/dev/null 2>&1; then \
        ln -sf "$(command -v testssl.sh)" /usr/local/bin/testssl; \
    fi

# Tools not packaged in this Kali image: rustscan (release), Go CLIs, volatility3 (pip)
# Keep golang-go until Phase 2 Go installs finish.
RUN wget -qO /tmp/rustscan.deb.zip \
        https://github.com/bee-san/RustScan/releases/download/2.4.1/rustscan.deb.zip \
    && unzip -qo /tmp/rustscan.deb.zip -d /tmp/rustscan \
    && apt-get update \
    && apt-get install -y --no-install-recommends /tmp/rustscan/*.deb \
    && rm -rf /var/lib/apt/lists/* /tmp/rustscan /tmp/rustscan.deb.zip \
    && go install -v github.com/projectdiscovery/katana/cmd/katana@latest \
    && go install -v github.com/hahwul/dalfox/v2@latest \
    && go install -v github.com/tomnomnom/anew@latest \
    && go install -v github.com/tomnomnom/qsreplace@latest \
    && go install -v github.com/jaeles-project/jaeles@latest \
    && go install -v github.com/haccer/subjack@latest \
    && install -m 0755 /opt/go/bin/* /usr/local/bin/ \
    && rm -rf /opt/go/pkg /opt/go/src /root/.cache/go-build \
    && python3 -m pip install --no-cache-dir --break-system-packages volatility3 \
    && ln -sf /usr/local/bin/vol /usr/local/bin/volatility3

# ---------------------------------------------------------------------------
# Phase 2 — pip / gem / GitHub / git clones (not in Kali apt, or apt fallback)
# ---------------------------------------------------------------------------
RUN python3 -m pip install --no-cache-dir --break-system-packages uro social-analyzer \
    && gem install --no-document one_gadget zsteg \
    && if command -v one_gadget >/dev/null 2>&1; then \
        ln -sf "$(command -v one_gadget)" /usr/local/bin/one-gadget; \
    fi \
    && if [ ! -f /opt/jwt_tool/jwt_tool.py ]; then \
        git clone --depth 1 https://github.com/ticarpi/jwt_tool.git /opt/jwt_tool \
        && ln -sf /opt/jwt_tool/jwt_tool.py /usr/local/bin/jwt_tool \
        && chmod +x /opt/jwt_tool/jwt_tool.py; \
    fi \
    && if ! command -v nosqlmap >/dev/null 2>&1 && ! command -v NoSQLMap >/dev/null 2>&1; then \
        git clone --depth 1 https://github.com/codingo/NoSQLMap.git /opt/NoSQLMap \
        && printf '#!/bin/sh\nexec python3 /opt/NoSQLMap/nosqlmap.py "$@"\n' > /usr/local/bin/nosqlmap \
        && chmod +x /usr/local/bin/nosqlmap; \
    fi \
    && git clone --depth 1 https://github.com/epinna/tplmap.git /opt/tplmap \
    && printf '#!/bin/sh\nexec python3 /opt/tplmap/tplmap.py "$@"\n' > /usr/local/bin/tplmap \
    && chmod +x /usr/local/bin/tplmap \
    && git clone --depth 1 https://github.com/hugsy/gef.git /opt/gef \
    && printf '#!/bin/sh\nexec gdb -q -x /opt/gef/gef.py "$@"\n' > /usr/local/bin/gdb-gef \
    && chmod +x /usr/local/bin/gdb-gef \
    && git clone --depth 1 https://github.com/niklasb/libc-database.git /opt/libc-database \
    && printf '#!/bin/sh\ncd /opt/libc-database || exit 1\nexec ./find "$@"\n' > /usr/local/bin/libc-database \
    && chmod +x /usr/local/bin/libc-database \
    && wget -qO /usr/local/bin/pwninit \
        https://github.com/io12/pwninit/releases/download/3.3.1/pwninit \
    && chmod +x /usr/local/bin/pwninit \
    && wget -qO /tmp/aquatone.zip \
        https://github.com/michenriksen/aquatone/releases/download/v1.7.0/aquatone_linux_amd64_1.7.0.zip \
    && unzip -qo /tmp/aquatone.zip -d /tmp/aquatone \
    && install -m 0755 /tmp/aquatone/aquatone /usr/local/bin/aquatone \
    && rm -rf /tmp/aquatone /tmp/aquatone.zip

# x8: pick a linux GitHub release asset when present (no cargo toolchain)
RUN python3 <<'PY'
import json, os, stat, tarfile, zipfile, urllib.request
url = "https://api.github.com/repos/Sh1Yo/x8/releases/latest"
try:
    with urllib.request.urlopen(url, timeout=60) as r:
        data = json.load(r)
except Exception as e:
    print("SKIP x8: cannot query GitHub", e)
    raise SystemExit(0)
assets = data.get("assets") or []
pick = None
for a in assets:
    n = a["name"].lower()
    if any(x in n for x in ("sha256", "sha512", ".sig")):
        continue
    if "linux" in n and ("x86_64" in n or "amd64" in n or "musl" in n):
        pick = a
        break
if pick is None:
    for a in assets:
        if a["name"] == "x8":
            pick = a
            break
if pick is None:
    print("SKIP x8: no linux asset in", [a["name"] for a in assets])
    raise SystemExit(0)
dest = "/tmp/x8-asset"
urllib.request.urlretrieve(pick["browser_download_url"], dest)
name = pick["name"].lower()
os.makedirs("/tmp/x8dir", exist_ok=True)
if name.endswith(".zip"):
    with zipfile.ZipFile(dest) as z:
        z.extractall("/tmp/x8dir")
elif name.endswith(".tar.gz") or name.endswith(".tgz"):
    with tarfile.open(dest) as t:
        t.extractall("/tmp/x8dir")
else:
    os.replace(dest, "/tmp/x8dir/x8")
found = None
for root, _dirs, files in os.walk("/tmp/x8dir"):
    for f in files:
        if f == "x8" or f.startswith("x8"):
            found = os.path.join(root, f)
            break
    if found:
        break
if not found:
    print("SKIP x8: extracted but binary not found")
    raise SystemExit(0)
os.chmod(found, os.stat(found).st_mode | stat.S_IEXEC)
os.replace(found, "/usr/local/bin/x8")
print("installed x8 from", pick["name"])
PY
RUN rm -rf /tmp/x8dir /tmp/x8-asset \
    && apt-get purge -y golang-go \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/* /root/.cache/go-build

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
