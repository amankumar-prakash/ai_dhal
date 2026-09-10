# Output formats

All LLM-facing artifacts are JSON. Raw tool blobs are stored but **never** pasted back into prompts.

Placeholders and schemas below are the contract for phase/tool agents and the compressor.

## 1. Tool raw (`tools/{seq}_{tool}.raw.json`)

Source of truth for UI / forensics.

```json
{
  "schema_version": 1,
  "job_id": "uuid",
  "seq": 1,
  "phase": "surface",
  "tool_name": "nmap_scan",
  "args": {},
  "started_at": "ISO-8601",
  "finished_at": "ISO-8601",
  "success": true,
  "exit_code": 0,
  "stdout": "…full…",
  "stderr": "",
  "command_summary": "nmap -sT -sV …"
}
```

## 2. Tool summary (`tools/{seq}_{tool}.summary.json`)

What the next agent may see. Structured facts first; optional compressed prose second.

```json
{
  "schema_version": 1,
  "job_id": "uuid",
  "seq": 1,
  "phase": "surface",
  "tool_name": "nmap_scan",
  "success": true,
  "facts": {
    "open_ports": [
      {"port": 80, "proto": "tcp", "service": "http"}
    ],
    "paths": [],
    "urls": [],
    "http": {},
    "exposures": [],
    "errors": []
  },
  "evidence_compressed": "short prose from LLMLingua-2 or heuristic",
  "token_stats": {
    "origin_tokens": 12000,
    "compressed_tokens": 400,
    "cap": 800
  }
}
```

### Fact keys by tool (expected)

| Tool | Primary `facts` keys |
|------|----------------------|
| `nmap_scan` | `open_ports[]` |
| `httpx_toolkit` | `http` (status, title, tech, server) |
| `gobuster_scan` / `feroxbuster_scan` | `paths[]` `{path, status}` |
| `katana_crawl` | `urls[]` |
| `rest_api_probe` | `urls[]`, `http` |
| `nuclei_scan` | `exposures[]` `{severity, title, evidence}` |
| `server_health` | `http` / health flags |

## 3. Phase rollup (`phases/{phase}.rollup.json`)

```json
{
  "schema_version": 1,
  "job_id": "uuid",
  "phase": "content",
  "status": "completed",
  "tools_run": ["gobuster_scan", "katana_crawl"],
  "tools_skipped": ["feroxbuster_scan"],
  "facts": {
    "open_ports": [],
    "paths": [{"path": "/ftp", "status": "200"}],
    "urls": ["http://target/rest"],
    "http": {},
    "exposures": [],
    "errors": []
  },
  "narrative_compressed": "…",
  "next_hints": ["probe /ftp for listing", "nuclei on /rest"],
  "token_stats": {"compressed_tokens": 900, "cap": 1500}
}
```

## 4. Job context (`job.context.json`)

Rolling state for orchestrator and subsequent phases. Hard-capped.

```json
{
  "schema_version": 1,
  "job_id": "uuid",
  "target": "http://localhost:3000",
  "scan_host": "localhost",
  "phases_completed": ["surface"],
  "loop_count": 0,
  "facts": {
    "open_ports": [{"port": 3000, "proto": "tcp", "service": "http"}],
    "paths": [],
    "urls": [],
    "http": {"status": 200, "title": "OWASP Juice Shop"},
    "exposures": [],
    "errors": []
  },
  "narrative_compressed": "…",
  "budget": {
    "tools_used": 3,
    "max_tools": 24,
    "phase_loops_used": 0,
    "max_phase_loops": 2
  },
  "token_stats": {"compressed_tokens": 1200, "cap": 3000}
}
```

## 5. Phase agent decision (LLM → orchestrator)

Phase agents should return JSON only (no markdown fence required if model supports JSON mode):

```json
{
  "action": "run_tool",
  "tool": "nmap_scan",
  "args_hint": {"scan_type": "-sT -sV", "additional_args": "-Pn -T4"},
  "reason": "need open ports before content discovery"
}
```

Other `action` values: `skip_tool`, `retry_tool`, `finish_phase`.

## 6. Orchestrator decision

```json
{
  "action": "run_phase",
  "phase": "content",
  "reason": "surface complete; paths unknown"
}
```

Other `action` values: `loop_phase`, `finish_job`, `abort_guardrail`.

## 7. Reporter bridge (unchanged UI)

Orchestrator still emits the existing tool-call list shape for `task_discovery.run()`:

```json
{
  "tool_name": "nmap_scan",
  "args": {},
  "output": {
    "success": true,
    "stdout": "…from raw artifact…",
    "command_summary": "…"
  }
}
```

UI continues to use `post_tool_run` / findings; LLM path uses summaries only.
