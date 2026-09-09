#!/bin/bash
# Install HexStrike CLI tools on the host (Ubuntu). Skip missing apt packages.
# Cloud/K8s/GUI/proprietary tools are intentionally omitted (see tool-catalog.md).
set -u
export DEBIAN_FRONTEND=noninteractive
export GOPATH="${GOPATH:-/opt/go}"
export GOBIN="$GOPATH/bin"
export PATH="/usr/local/go/bin:$GOBIN:/usr/local/bin:${PATH}"
mkdir -p "$GOBIN" /usr/local/bin /opt

log() { echo "[hexstrike-tools] $*"; }
have() { command -v "$1" >/dev/null 2>&1; }

apt_try() {
  local pkg
  for pkg in "$@"; do
    if apt-get install -y --no-install-recommends "$pkg" >/tmp/apt-"$pkg".log 2>&1; then
      log "apt installed $pkg"
    else
      log "SKIP apt $pkg"
    fi
  done
}

log "apt-get update"
apt-get update -y

log "build deps + Ubuntu-packaged tools"
apt_try \
  git curl wget unzip ca-certificates gnupg file build-essential \
  python3 python3-pip python3-venv python3-dev \
  libffi-dev libssl-dev libxml2-dev libxslt1-dev zlib1g-dev \
  ruby ruby-dev \
  nmap masscan gobuster dirb nikto sqlmap hydra john hashcat medusa \
  gdb radare2 binwalk binutils foremost steghide libimage-exiftool-perl \
  arp-scan nbtscan samba-common-bin smbclient enum4linux \
  whatweb wfuzz sslscan hashid xxd bsdextrautils upx-ucl httpie \
  ffuf tcpdump tshark ophcrack patator checksec seclists \
  wpscan recon-ng outguess smbmap commix

# Official Go (Ubuntu golang is often too old for ProjectDiscovery / jaeles)
if ! have go || ! go version | grep -qE 'go1\.(2[2-9]|[3-9])'; then
  log "installing Go 1.23.6"
  wget -qO /tmp/go.tgz https://go.dev/dl/go1.23.6.linux-amd64.tar.gz
  rm -rf /usr/local/go
  tar -C /usr/local -xzf /tmp/go.tgz
  rm -f /tmp/go.tgz
  ln -sf /usr/local/go/bin/go /usr/local/bin/go
  ln -sf /usr/local/go/bin/gofmt /usr/local/bin/gofmt
fi
log "go $(go version)"

go_install() {
  local spec="$1"
  log "go install $spec"
  if go install -v "$spec"; then
    log "ok $spec"
  else
    log "SKIP go $spec"
  fi
}

go_install github.com/projectdiscovery/katana/cmd/katana@latest
go_install github.com/hahwul/dalfox/v2@latest
go_install github.com/tomnomnom/anew@latest
go_install github.com/tomnomnom/qsreplace@latest
go_install github.com/tomnomnom/waybackurls@latest
go_install github.com/jaeles-project/jaeles@latest
go_install github.com/haccer/subjack@latest
go_install github.com/hakluke/hakrawler@latest
go_install github.com/lc/gau/v2/cmd/gau@latest
go_install github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest
go_install github.com/owasp-amass/amass/v4/...@master
go_install github.com/ffuf/ffuf/v2@latest
go_install github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest
go_install github.com/projectdiscovery/httpx/cmd/httpx@latest

# Copy Go bins onto PATH (keep GOPATH copies too)
if [ -d "$GOBIN" ]; then
  find "$GOBIN" -maxdepth 1 -type f -executable -exec install -m 0755 {} /usr/local/bin/ \;
fi

# GitHub release binaries
log "rustscan deb"
if wget -qO /tmp/rustscan.deb.zip https://github.com/bee-san/RustScan/releases/download/2.4.1/rustscan.deb.zip; then
  unzip -qo /tmp/rustscan.deb.zip -d /tmp/rustscan
  apt-get install -y --no-install-recommends /tmp/rustscan/*.deb || log "SKIP rustscan deb"
  rm -rf /tmp/rustscan /tmp/rustscan.deb.zip
fi

log "feroxbuster"
if wget -qO /tmp/ferox.zip "https://github.com/epi052/feroxbuster/releases/latest/download/x86_64-linux-feroxbuster.zip"; then
  unzip -qo /tmp/ferox.zip -d /tmp/ferox
  if [ -f /tmp/ferox/feroxbuster ]; then install -m 0755 /tmp/ferox/feroxbuster /usr/local/bin/feroxbuster; fi
  rm -rf /tmp/ferox /tmp/ferox.zip
fi

log "pwninit"
wget -qO /usr/local/bin/pwninit https://github.com/io12/pwninit/releases/download/3.3.1/pwninit \
  && chmod +x /usr/local/bin/pwninit || log "SKIP pwninit"

log "aquatone"
if wget -qO /tmp/aquatone.zip https://github.com/michenriksen/aquatone/releases/download/v1.7.0/aquatone_linux_amd64_1.7.0.zip; then
  unzip -qo /tmp/aquatone.zip -d /tmp/aquatone
  install -m 0755 /tmp/aquatone/aquatone /usr/local/bin/aquatone
  rm -rf /tmp/aquatone /tmp/aquatone.zip
fi

log "x8 github release"
python3 - <<'PY' || true
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
    print("SKIP x8: no linux asset", [a["name"] for a in assets])
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
        if f == "x8" or (f.startswith("x8") and not f.endswith((".md", ".txt"))):
            found = os.path.join(root, f)
            break
    if found:
        break
if not found:
    print("SKIP x8: binary not found")
    raise SystemExit(0)
os.chmod(found, os.stat(found).st_mode | stat.S_IEXEC)
os.replace(found, "/usr/local/bin/x8")
print("installed x8 from", pick["name"])
PY
rm -rf /tmp/x8dir /tmp/x8-asset

# Python CLIs (system PATH; --break-system-packages on Ubuntu 24.04)
PIP=(python3 -m pip install --no-cache-dir --break-system-packages)
log "pip CLIs"
"${PIP[@]}" volatility3 uro social-analyzer arjun dirsearch wafw00f \
  sslyze ROPgadget ropper theHarvester fierce autorecon netexec smbmap \
  paramspider hashid 2>/tmp/pip-tools.log || log "WARN pip batch had failures; see /tmp/pip-tools.log"
# hash-identifier: tiny script if missing
if ! have hash-identifier && ! have hash_identifier; then
  "${PIP[@]}" hash-identifier 2>/dev/null || true
fi

# jwt_tool
if [ ! -f /opt/jwt_tool/jwt_tool.py ]; then
  git clone --depth 1 https://github.com/ticarpi/jwt_tool.git /opt/jwt_tool
fi
ln -sf /opt/jwt_tool/jwt_tool.py /usr/local/bin/jwt_tool
chmod +x /opt/jwt_tool/jwt_tool.py || true

# testssl.sh
if [ ! -x /opt/testssl.sh/testssl.sh ]; then
  git clone --depth 1 https://github.com/drwetter/testssl.sh.git /opt/testssl.sh
fi
ln -sf /opt/testssl.sh/testssl.sh /usr/local/bin/testssl.sh
ln -sf /opt/testssl.sh/testssl.sh /usr/local/bin/testssl

# nosqlmap
if ! have nosqlmap; then
  git clone --depth 1 https://github.com/codingo/NoSQLMap.git /opt/NoSQLMap || true
  if [ -f /opt/NoSQLMap/nosqlmap.py ]; then
    printf '#!/bin/sh\nexec python3 /opt/NoSQLMap/nosqlmap.py "$@"\n' > /usr/local/bin/nosqlmap
    chmod +x /usr/local/bin/nosqlmap
  fi
fi

# tplmap
git clone --depth 1 https://github.com/epinna/tplmap.git /opt/tplmap 2>/dev/null || true
if [ -f /opt/tplmap/tplmap.py ]; then
  printf '#!/bin/sh\nexec python3 /opt/tplmap/tplmap.py "$@"\n' > /usr/local/bin/tplmap
  chmod +x /usr/local/bin/tplmap
fi

# enum4linux-ng
if ! have enum4linux-ng; then
  git clone --depth 1 https://github.com/cddmp/enum4linux-ng.git /opt/enum4linux-ng || true
  if [ -f /opt/enum4linux-ng/enum4linux-ng.py ]; then
    printf '#!/bin/sh\nexec python3 /opt/enum4linux-ng/enum4linux-ng.py "$@"\n' > /usr/local/bin/enum4linux-ng
    chmod +x /usr/local/bin/enum4linux-ng
  fi
fi

# responder
if ! have responder; then
  git clone --depth 1 https://github.com/lgandx/Responder.git /opt/Responder || true
  if [ -f /opt/Responder/Responder.py ]; then
    printf '#!/bin/sh\nexec python3 /opt/Responder/Responder.py "$@"\n' > /usr/local/bin/responder
    chmod +x /usr/local/bin/responder
  fi
fi

# dnsenum
if ! have dnsenum; then
  git clone --depth 1 https://github.com/fwaeytens/dnsenum.git /opt/dnsenum || true
  if [ -f /opt/dnsenum/dnsenum.pl ]; then
    ln -sf /opt/dnsenum/dnsenum.pl /usr/local/bin/dnsenum
    chmod +x /opt/dnsenum/dnsenum.pl || true
  fi
fi

# gdb plugins
git clone --depth 1 https://github.com/hugsy/gef.git /opt/gef 2>/dev/null || true
printf '#!/bin/sh\nexec gdb -q -ex "source /opt/gef/gef.py" "$@"\n' > /usr/local/bin/gdb-gef
chmod +x /usr/local/bin/gdb-gef
git clone --depth 1 https://github.com/longld/peda.git /opt/peda 2>/dev/null || true
printf '#!/bin/sh\nexec gdb -q -ex "source /opt/peda/peda.py" "$@"\n' > /usr/local/bin/gdb-peda
chmod +x /usr/local/bin/gdb-peda

# libc-database scripts only
git clone --depth 1 https://github.com/niklasb/libc-database.git /opt/libc-database 2>/dev/null || true
printf '#!/bin/sh\ncd /opt/libc-database || exit 1\nexec ./find "$@"\n' > /usr/local/bin/libc-database
chmod +x /usr/local/bin/libc-database

# sherlock (pip package name varies)
"${PIP[@]}" sherlock-project 2>/dev/null || "${PIP[@]}" sherlock 2>/dev/null || \
  git clone --depth 1 https://github.com/sherlock-project/sherlock.git /opt/sherlock

# Ruby gems
log "gems"
gem install --no-document one_gadget zsteg wpscan evil-winrm 2>/tmp/gem-tools.log || log "WARN gem failures; see /tmp/gem-tools.log"

# PATH aliases HexStrike /health expects
have httpx-toolkit || { have httpx && ln -sf "$(command -v httpx)" /usr/local/bin/httpx-toolkit; }
# Prefer ProjectDiscovery httpx at /usr/local/bin/httpx (already GOPATH install)
if have getallurls && ! have gau; then ln -sf "$(command -v getallurls)" /usr/local/bin/gau; fi
if have ROPgadget; then ln -sf "$(command -v ROPgadget)" /usr/local/bin/ropgadget; fi
if have netexec && ! have nxc; then ln -sf "$(command -v netexec)" /usr/local/bin/nxc; fi
if have one_gadget; then ln -sf "$(command -v one_gadget)" /usr/local/bin/one-gadget; fi
if have vol && ! have volatility3; then ln -sf "$(command -v vol)" /usr/local/bin/volatility3; fi
if have theHarvester && ! have theharvester; then ln -sf "$(command -v theHarvester)" /usr/local/bin/theharvester; fi
if have jwt_tool && [ ! -e /opt/jwt_tool/jwt_tool.py ]; then
  mkdir -p /opt/jwt_tool
  ln -sf "$(command -v jwt_tool)" /opt/jwt_tool/jwt_tool.py
fi
# hash-identifier alias
if have hashid && ! have hash-identifier; then ln -sf "$(command -v hashid)" /usr/local/bin/hash-identifier; fi
if have exiftool || have /usr/bin/exiftool; then true; fi

# httpx-toolkit name used by recon skill; PD binary is httpx
if have httpx && [ ! -x /usr/local/bin/httpx-toolkit ]; then
  ln -sf "$(command -v httpx)" /usr/local/bin/httpx-toolkit
fi

log "done. sample which:"
for t in nmap rustscan masscan hakrawler gau waybackurls testssl.sh sslscan jwt_tool \
         smbmap rpcclient ROPgadget httpx httpx-toolkit nuclei katana feroxbuster \
         anew qsreplace uro jaeles dalfox one_gadget pwninit zsteg subfinder amass; do
  printf '  %-16s %s\n' "$t" "$(command -v "$t" 2>/dev/null || echo MISSING)"
done
