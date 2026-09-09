# HexStrike tool catalog

Installed on this **Ubuntu 24.04 host** (no Docker). HexStrike listens on
port **8005**. Reinstall with
`hexstrike_server/install_host_tools.sh`. A Kali Dockerfile still exists
for Compose environments.

Default recon uses a **subset**; this file is the full map.

Binary notes for this image:

| Expected name | Actual on PATH |
|---------------|----------------|
| `httpx` (ProjectDiscovery) | **`httpx-toolkit`**; `/usr/local/bin/httpx` is a symlink to it (`/usr/bin/httpx` is Python httpx) |
| `gau` | Kali package `getallurls`; `/usr/local/bin/gau` symlink |
| `exiftool` | from `libimage-exiftool-perl` |
| `strings` / `objdump` / `readelf` | `binutils` |
| `hexdump` | `bsdextrautils` |
| `volatility3` | `vol` (+ `volatility3` symlink) |
| `theharvester` | `theHarvester` |
| `netexec` | also **`nxc`** (symlink if needed) |
| `ROPgadget` | package `python3-ropgadget`; `ropgadget` symlink for `/health` |
| `jwt-tool` | `jwt_tool` and `/opt/jwt_tool/jwt_tool.py` |
| `testssl.sh` | Kali package `testssl.sh` (also `testssl` symlink) |
| `one_gadget` | Ruby gem; `one-gadget` symlink for `/health` |
| `libc-database` | scripts at `/opt/libc-database` (no full libc download) |
| `gdb-peda` | Kali `gdb-peda` |
| `gdb-gef` | wrapper: `gdb -q -x /opt/gef/gef.py` |

Wordlists: `/usr/share/dirb/wordlists/common.txt`

Not installed (proprietary, GUI, cloud/K8s, or deferred): IDA Free, Binary Ninja, Burp Suite, Maltego, Pipl, OWASP ZAP, Autopsy, Metasploit/msfvenom, cloud CLIs, Trivy/Kube-Hunter/Checkov/etc.

---

## Network & reconnaissance

| Tool | Purpose |
|------|---------|
| nmap | Port scan, service/version detection, NSE scripts |
| masscan | Extremely fast asynchronous port scanner |
| rustscan | Fast port discovery; often paired with nmap |
| amass | Attack-surface / subdomain mapping |
| subfinder | Passive/active subdomain discovery |
| nuclei | Template-based vuln/exposure scanner |
| fierce | DNS reconnaissance / zone guessing |
| dnsenum | DNS enumeration (records, brute, zone xfer attempts) |
| autorecon | Orchestrates multi-tool host recon |
| theHarvester | OSINT: emails, names, hosts from public sources |
| responder | LLMNR/NBT-NS/mDNS poisoning (internal network) |
| netexec | Network execution / auth testing across protocols (nxc) |
| enum4linux | Classic Samba/Windows enumeration |
| enum4linux-ng | Samba/Windows enumeration (successor to enum4linux) |
| arp-scan | Local-net host discovery via ARP |
| nbtscan | NetBIOS name scan |
| rpcclient | MSRPC enumeration (`samba-common-bin`) |
| smbmap | SMB share enumeration |

## Web application

| Tool | Purpose |
|------|---------|
| gobuster | Directory, DNS, vhost, fuzz modes |
| feroxbuster | Recursive content discovery (Rust) |
| dirsearch | Python web path scanner |
| ffuf | Fast web fuzzer (paths, params, headers) |
| dirb | Classic HTTP object scanner |
| httpx-toolkit | HTTP probing, status, title, tech detect |
| katana | Next-gen crawler; JS endpoint extraction |
| hakrawler | Fast endpoint discovery crawler |
| gau / getallurls | URLs from Wayback / OTX / Common Crawl |
| waybackurls | Historical URLs from Wayback Machine |
| whatweb | Web technology fingerprinting |
| nikto | Web server misconfiguration scanner |
| sqlmap | Automated SQL injection testing |
| wpscan | WordPress vulnerability scanner |
| arjun | HTTP parameter discovery |
| paramspider | Mine parameters from web archives |
| x8 | Hidden HTTP parameter discovery |
| jaeles | Signature-based vuln scanning |
| dalfox | XSS scanning / parameter analysis |
| wafw00f | Web application firewall fingerprinting |
| wfuzz | Web application fuzzer |
| commix | Command injection testing |
| nosqlmap | NoSQL injection testing |
| tplmap | Server-side template injection testing |

## TLS

| Tool | Purpose |
|------|---------|
| testssl.sh | SSL/TLS configuration and vuln checks |
| sslscan | Cipher/protocol enumeration |
| sslyze | SSL/TLS configuration analyzer |

## URL processing

| Tool | Purpose |
|------|---------|
| anew | Append only new lines to a file |
| qsreplace | Replace query-string values |
| uro | Deduplicate similar URLs |

## Password & authentication

| Tool | Purpose |
|------|---------|
| hydra | Online network login brute-force |
| john | Offline password cracker (John the Ripper) |
| hashcat | GPU/CPU hash cracking |
| medusa | Parallel modular login brute-forcer |
| patator | Multi-purpose brute-forcer |
| crackmapexec | Legacy name; prefer **netexec** on modern Kali |
| evil-winrm | WinRM shell for Windows targets |
| hash-identifier | Guess hash algorithm from sample |
| hashid | Identify hash types from samples |
| ophcrack | Windows LM/NT rainbow-table cracker |
| jwt_tool | JWT testing (algorithm confusion, etc.) |

## Binary / RE / exploit helpers

| Tool | Purpose |
|------|---------|
| gdb | Debugger |
| gdb-peda | PEDA GDB plugin (apt) |
| gdb-gef | GEF wrapper around gdb |
| radare2 | Reverse engineering framework |
| binwalk | Firmware / binary carving and analysis |
| ghidra | NSA SRE framework (heavy) |
| checksec | ELF hardening checks (RELRO, NX, PIE, …) |
| strings | Extract printable strings |
| objdump | Disassemble / inspect object files |
| xxd / hexdump | Hex dump |
| ROPgadget | ROP gadget search |
| ropper | ROP gadget finder |
| one_gadget | One-shot libc RCE gadgets |
| pwninit | CTF binary pwn setup |
| libc-database | libc identification scripts (`/opt/libc-database`) |
| upx | Pack/unpack binaries (`upx-ucl`) |
| pwntools / angr | Python libs via uv venv (not standalone CLIs) |

## Forensics / stego (light)

| Tool | Purpose |
|------|---------|
| volatility3 (`vol`) | Memory forensics |
| foremost | File carving from disk/images |
| steghide | Steganography hide/extract |
| outguess | Steganography hide/extract |
| zsteg | PNG/BMP stego detection |
| exiftool | Metadata read/write for media/docs |

## OSINT / bug bounty extras

| Tool | Purpose |
|------|---------|
| recon-ng | OSINT recon framework |
| sherlock | Username lookup across sites |
| social-analyzer | Social profile OSINT |
| aquatone | Visual recon / screenshots |
| subjack | Subdomain takeover checks |
| trufflehog | Secret/credential scanning |

---

## HexStrike HTTP surface (recon-relevant)

| Method | Path | Typical body keys |
|--------|------|-------------------|
| GET | `/health` | — |
| POST | `/api/tools/nmap` | `target`, `ports`, `scan_type`, `additional_args` |
| POST | `/api/tools/gobuster` | `url`, `mode`, `wordlist`, `additional_args` |
| POST | `/api/tools/feroxbuster` | `url`, `wordlist`, `threads`, `additional_args` |
| POST | `/api/tools/katana` | `url`, `depth`, `js_crawl`, `form_extraction` |
| POST | `/api/tools/nuclei` | `target`, `severity`, `tags`, `template` |
| POST | `/api/tools/arjun` | `url`, `additional_args` |
| POST | `/api/tools/hakrawler` | `url`, `depth` |
| POST | `/api/tools/gau` | domain / URLs |
| POST | `/api/tools/rustscan` | `target`, `ports`, … |
| POST | `/api/command` | `command` (raw shell in container) |

Many other `/api/tools/*` routes exist (nikto, ffuf, dirsearch, jwt, ssl, …) — same pattern:
POST JSON → `{ success, stdout, stderr, return_code, execution_time }`.

---

## When **not** to use a tool in recon

| Tool | Skip in default recon because |
|------|-------------------------------|
| sqlmap / dalfox / commix / tplmap / nosqlmap | Active exploitation / injection testing |
| hydra / medusa / patator | Credential attacks |
| responder | Poisons local name resolution |
| ghidra / gdb / volatility3 | Need binaries/dumps, not live HTTP recon |
| amass / subfinder / gau | Need a real domain / public history |

Default recon = **ports → fingerprint → dirs → crawl → API probe → exposure nuclei**.
