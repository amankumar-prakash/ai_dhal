# HexStrike recon API examples

Assume HexStrike at `http://localhost:8005` and target app on the Docker host
at port 3000.

## PowerShell helper pattern

```powershell
$base = 'http://localhost:8005'
$outDir = 'hexstrike_server/scan_reports'
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

function Invoke-HexApi($path, $body, $name, $timeoutSec = 400) {
  $json = $body | ConvertTo-Json -Depth 8 -Compress
  $resp = Invoke-RestMethod -Method Post -Uri "$base$path" `
    -ContentType 'application/json' -Body $json -TimeoutSec $timeoutSec
  $resp | ConvertTo-Json -Depth 6 |
    Set-Content (Join-Path $outDir "$name.json") -Encoding UTF8
  if ($null -ne $resp.stdout) {
    [string]$resp.stdout |
      Set-Content (Join-Path $outDir "$name.txt") -Encoding UTF8
  }
  $resp
}
```

## Measure SPA wildcard length

```powershell
# From HexStrike container perspective:
# curl -s http://host.docker.internal:3000/does-not-exist-xyz | wc -c
# Juice Shop often ~9903 — use as --exclude-length / --filter-size
```

## Minimal full recon sequence

```powershell
Invoke-HexApi '/api/tools/nmap' @{
  target = 'host.docker.internal'
  ports = '3000,80,443,8000,8080'
  scan_type = '-sV'
  additional_args = '-Pn -T4'
} '01_nmap'

Invoke-HexApi '/api/command' @{
  command = 'httpx-toolkit -u http://host.docker.internal:3000 -sc -title -tech-detect -server -cl -silent'
} '02_httpx'

Invoke-HexApi '/api/tools/gobuster' @{
  url = 'http://host.docker.internal:3000'
  mode = 'dir'
  wordlist = '/usr/share/dirb/wordlists/common.txt'
  additional_args = '-q -t 40 --exclude-length 9903'
} '03_gobuster'

Invoke-HexApi '/api/tools/katana' @{
  url = 'http://host.docker.internal:3000'
  depth = 2
  js_crawl = $true
  form_extraction = $true
  output_format = 'json'
  additional_args = '-silent -c 20'
} '04_katana'

Invoke-HexApi '/api/tools/nuclei' @{
  target = 'http://host.docker.internal:3000'
  severity = 'info,low,medium,high,critical'
  tags = 'exposure,token,config,misconfig,disclosure,panel,tech'
  additional_args = '-silent -rate-limit 50'
} '05_nuclei_exposure'
```

## Quick API surface probe (inside container)

Prefer a small `sh` script copied into the container (avoid CRLF). Probe at least:

- `/api-docs`, `/rest`, `/rest/products/search`
- `/api/Challenges`, `/api/Users`, `/api/Feedbacks`
- `/metrics`, `/ftp`, `/robots.txt`

Record `http_code`, `size_download`, `content_type` per path.
