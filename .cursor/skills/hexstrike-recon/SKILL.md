---
name: hexstrike-recon
description: >-
  Runs authorized reconnaissance via HexStrike API (localhost:8005) — port
  scans, HTTP probing, content discovery, crawling, API enumeration, and
  exposure/leak checks. Explains which tool to use for each recon phase.
  Use when the user asks to recon, scan ports, discover APIs/endpoints, find
  data leaks, run nmap/gobuster/katana/nuclei/httpx, or use HexStrike against
  an allowlisted target (e.g. localhost:3000 / Juice Shop).
---

# HexStrike Recon

Authorized **discovery-only** recon through HexStrike (`hexstrike_server` on
port **8005**). Prefer the HTTP API over inventing shell one-offs.

**Safety:** Only scan targets in `TARGET_ALLOWLIST` / ownership the user confirms.
Stay on recon and exposure discovery — do not run exploit/weaponization flows
unless the user explicitly asks and scope is clear.

For the full tool catalog, see [references/tool-catalog.md](references/tool-catalog.md).

---

## 1. Preconditions

```
Progress:
- [ ] 1. HexStrike healthy: GET http://localhost:8005/health
- [ ] 2. Target reachable and allowlisted
- [ ] 3. Pick host form for Docker (see below)
- [ ] 4. Write reports under hexstrike_server/scan_reports/
```

| From | Target form |
|------|-------------|
| Host → app on host | `http://localhost:3000` |
| HexStrike **container** → app on host | `http://host.docker.internal:3000` (host `host.docker.internal`) |
| Container → container | `http://<compose_service>:<port>` |

Always check health first:

```http
GET http://localhost:8005/health
```

---

## 2. Recon phases (default pipeline)

Run in order. Save each JSON/stdout under `hexstrike_server/scan_reports/`.

| Phase | Goal | HexStrike API | Default tool |
|-------|------|---------------|--------------|
| 1. Ports | What is open? | `POST /api/tools/nmap` | nmap |
| 2. HTTP fingerprint | Status, title, tech | `POST /api/command` | **httpx-toolkit** |
| 3. Content discovery | Paths / dirs | `POST /api/tools/gobuster` or `feroxbuster` | gobuster / feroxbuster |
| 4. Crawl | Linked + JS endpoints | `POST /api/tools/katana` | katana |
| 5. API / params | REST surfaces, params | probe script + `arjun` | curl probes / arjun |
| 6. Exposure / leaks | Misconfig, docs, metrics | `POST /api/tools/nuclei` | nuclei (exposure tags) |

Optional deepeners: `rustscan`/`masscan` (wide ports), `dirsearch`, `nikto` (web misconfig), `paramspider` (archived params).

---

## 3. What each tool does (recon map)

### Network

| Tool | Does | Use when |
|------|------|----------|
| **nmap** | Port/service/version scan | Confirm open ports + banners |
| **rustscan** | Very fast port sweep | Broad port ranges before nmap `-sV` |
| **masscan** | Internet-scale port sweep | Huge ranges (lab only; rate carefully) |
| **amass** / **subfinder** | Subdomain enum | Domain-scoped recon (not bare IP:port) |
| **fierce** / **dnsenum** | DNS enum | Domain DNS mapping |
| **autorecon** | Multi-tool recon wrapper | Heavy automated host recon |
| **theHarvester** | OSINT emails/hosts | External OSINT phase |
| **responder** / **netexec** / **enum4linux-ng** | Network auth / SMB / AD-ish enum | Internal Windows/SMB targets — not typical for Juice Shop web |

### Web / API

| Tool | Does | Use when |
|------|------|----------|
| **httpx-toolkit** | Probe URLs: status, title, tech | Fingerprint after ports |
| **gobuster** | Dir/DNS/vhost brute | Path discovery with a wordlist |
| **feroxbuster** | Recursive content discovery | Deeper path recursion |
| **dirsearch** / **dirb** | Web path brute | Alternate dirbust engines |
| **ffuf** | Fast web fuzzer | Parameter/path fuzz with filters |
| **katana** | Crawl + JS URL extraction | Map app endpoints from HTML/JS |
| **nikto** | Classic web misconfig checks | Quick server/header issues |
| **arjun** | Hidden HTTP parameter discovery | After you have a concrete endpoint |
| **paramspider** | Params from archives | PassiveInternet**-facing domains with history |
| **wafw00f** | Detect WAF | Before noisy fuzzing |
| **nuclei** | Template scanner | Exposure/misconfig/tech (**leak-oriented tags**) |
| **sqlmap** / **dalfox** / **wpscan** | Injection / XSS / WordPress | **Not** default recon — only if user asks for those tests |

### Password / binary (usually out of default recon)

Hydra/john/hashcat/… and gdb/ghidra/… are installed for later phases.
Do **not** include them in the default recon pipeline.

---

## 4. HexStrike API recipes

Base: `http://localhost:8005`

### Ports — nmap

```json
POST /api/tools/nmap
{
  "target": "host.docker.internal",
  "ports": "3000,80,443,8000,8080,8443",
  "scan_type": "-sV",
  "additional_args": "-Pn -T4"
}
```

### HTTP fingerprint — use httpx-toolkit via command

`/api/tools/httpx` expects a **file list** (`-l`). For a single URL use:

```json
POST /api/command
{
  "command": "httpx-toolkit -u http://host.docker.internal:3000 -sc -title -tech-detect -server -cl -silent"
}
```

**Pitfall:** `/usr/bin/httpx` is the **Python** httpx CLI. Always call **`httpx-toolkit`**.

### Content discovery — gobuster

Wordlist on this image: `/usr/share/dirb/wordlists/common.txt`  
(not `/usr/share/wordlists/dirb/...`)

```json
POST /api/tools/gobuster
{
  "url": "http://host.docker.internal:3000",
  "mode": "dir",
  "wordlist": "/usr/share/dirb/wordlists/common.txt",
  "additional_args": "-q -t 40 --exclude-length 9903"
}
```

### Crawl — katana

```json
POST /api/tools/katana
{
  "url": "http://host.docker.internal:3000",
  "depth": 2,
  "js_crawl": true,
  "form_extraction": true,
  "output_format": "json",
  "additional_args": "-silent -c 20"
}
```

### Exposure / leaks — nuclei

```json
POST /api/tools/nuclei
{
  "target": "http://host.docker.internal:3000",
  "severity": "info,low,medium,high,critical",
  "tags": "exposure,token,config,misconfig,disclosure,panel,tech",
  "additional_args": "-silent -rate-limit 50"
}
```

### Feroxbuster

Do **not** pass `-t` in `additional_args` — the API already adds `-t <threads>`.

```json
POST /api/tools/feroxbuster
{
  "url": "http://host.docker.internal:3000",
  "wordlist": "/usr/share/dirb/wordlists/common.txt",
  "threads": 40,
  "additional_args": "-d 1 -q --filter-status 404 --filter-size 9903"
}
```

---

## 5. SPA / Juice Shop pitfalls

OWASP Juice Shop returns **HTTP 200** with the same HTML length for many unknown paths.

| Symptom | Fix |
|---------|-----|
| Gobuster: “wildcard / exclude length” | `--exclude-length 9903` (measure real SPA size first) |
| Ferox “threads multiple times” | Set `threads` only; no `-t` in `additional_args` |
| Dirbust noise | Prefer status+size filters; verify hits with `curl -sI` / body content-type |
| “Swagger yaml” is HTML | Often Swagger **UI**; still counts as API docs exposure |

Always verify interesting hits with a direct GET (status, `Content-Type`, size).

---

## 6. Report format

After the pipeline, summarize for the user:

1. **Ports** — open ports + services  
2. **Fingerprint** — product/title/tech  
3. **Endpoints** — dirs, `/api/*`, `/rest/*`, docs  
4. **Leaks / exposure** — metrics, FTP listings, unauth JSON, missing headers  
5. **Artifacts** — paths under `hexstrike_server/scan_reports/`

Keep the summary actionable; do not dump full nuclei/katana blobs unless asked.

---

## 7. Quick decision guide

| User asks for… | Run |
|----------------|-----|
| “Scan ports” | nmap (± rustscan first) |
| “What’s running / tech?” | httpx-toolkit |
| “Find hidden paths” | gobuster or feroxbuster |
| “Map the app / APIs” | katana → probe `/api`, `/rest`, `/api-docs` |
| “Data leaks / exposure” | nuclei exposure tags + check `/metrics`, `/ftp`, open JSON APIs |
| “Full recon” | All six phases above |

---

## Additional resources

- Tool catalog (all installed categories): [references/tool-catalog.md](references/tool-catalog.md)
- Example API bodies and filters: [references/api-examples.md](references/api-examples.md)
