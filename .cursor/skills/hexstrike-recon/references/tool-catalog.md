# HexStrike tool catalog

Installed in `hexstrike_server` (Kali image). Default recon uses a **subset**;
this file is the full map.

Binary notes for this image:

| Expected name | Actual on PATH |
|---------------|----------------|
| `httpx` (ProjectDiscovery) | **`httpx-toolkit`** (`/usr/bin/httpx` is Python httpx) |
| `exiftool` | from `libimage-exiftool-perl` |
| `strings` / `objdump` | `binutils` |
| `volatility3` | `vol` (+ `volatility3` symlink) |
| `theharvester` | `theHarvester` |

Wordlists: `/usr/share/dirb/wordlists/common.txt`

---

## Network & reconnaissance

| Tool | Purpose |
|------|---------|
| nmap | Port scan, service/version detection, NSE scripts |
| masscan | Extremely fast asynchronous port scanner |
| rustscan | Fast port discovery; often paired with nmap |
| amass | Attack-surface / subdomain mapping |
| subfinder | Passivepassive/active subdomain discovery |
| nuclei | Template-based vuln/exposure scanner |
| fierce | DNS reconnaissance / zone guessing |
| dnsenum | DNS enumeration (records, brute, zone xfer attempts) |
| autorecon | Orchestrates multi-tool host recon |
| theHarvester | OSINT: emails, names, hosts from public sources |
| responder | LLMNR/NBT-NS/mDNS poisoning (internal network) |
| netexec | Network execution / auth testing across protocols (nxc) |
| enum4linux-ng | Samba/Windows enumeration (successor to enum4linux) |

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
| nikto | Web server misconfiguration scanner |
| sqlmap | Automated SQL injection testing |
| wpscan | WordPress vulnerability scanner |
| arjun | HTTP parameter discovery |
| paramspider | Mine parameters from web archives |
| dalfox | XSS scanning / parameter analysis |
| wafw00f | Web application firewall fingerprinting |

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
| ophcrack | Windows LM/NTCR rainbow-table cracker |

## Binary / RE / forensics

| Tool | Purpose |
|------|---------|
| gdb | Debugger |
| radare2 | Reverse engineering framework |
| binwalk | Firmware / binary carving and analysis |
| ghidra | NSA SRE framework (heavy) |
| checksec | ELF hardening checks (RELRO, NX, PIE, …) |
| strings | Extract printable strings |
| objdump | Disassemble / inspect object files |
| volatility3 (`vol`) | Memory forensics |
| foremost | File carving from disk/images |
| steghide | Steganography hide/extract |
| exiftool | Metadata read/write for media/docs |

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
| POST | `/api/tools/rustscan` | `target`, `ports`, … |
| POST | `/api/command` | `command` (raw shell in container) |

Many other `/api/tools/*` routes exist (nikto, ffuf, dirsearch, …) — same pattern:
POST JSON → `{ success, stdout, stderr, return_code, execution_time }`.

---

## When **not** to use a tool in recon

| Tool | Skip in default recon because |
|------|-------------------------------|
| sqlmap / dalfox | Active exploitation / injection testing |
| hydra / medusa / patator | Credential attacks |
| responder | Poisons local name resolution |
| ghidra / gdb / volatility3 | Need binaries/dumps, not live HTTP recon |
| amass / subfinder / gau | Need a real domain / public history |

Default recon = **ports → fingerprint → dirs → crawl → API probe → exposure nuclei**.
