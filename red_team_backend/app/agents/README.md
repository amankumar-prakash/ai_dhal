# Red-team agents (prompts)

Prompt library for hierarchical recon: **orchestrator → phase agent → tool agent**.

Runtime code that *runs* these agents lives under `app/orchestration/` (follow-up). This package owns **text only** plus a small loader.

## Layout

```text
prompts/
  _shared/           # included into every system prompt
  orchestrator/      # job-level decisions
  phases/
    surface/tools/   # health, nmap, httpx
    content/tools/   # gobuster/ferox, katana, rest probe
    vuln/tools/      # nuclei
```

## Loading

```python
from app.agents.prompt_loader import load_prompt, build_system_prompt

system = build_system_prompt("phases/surface/tools/nmap_scan")
user = load_prompt("phases/surface/tools/nmap_scan", section="user")  # if split later
```

Today most files are a single markdown document with `## System` and `## User` sections.

## Docs

See [`docs/orchestration/`](../../../docs/orchestration/) for architecture, output formats, guardrails, and acceptance checklist.
