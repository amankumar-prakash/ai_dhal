# Structure

## Repository layout (target)

```text
docs/
  token-overflow-management.md          # plan + root cause
  orchestration/
    README.md
    architecture.md
    structure.md                        # this file
    output-formats.md
    guardrails.md
    acceptance-checklist.md

red_team_backend/app/
  agents/                               # prompts + loader (this build)
    README.md
    __init__.py
    prompt_loader.py
    prompts/
      _shared/
        lab_authorization.md
        output_contracts.md
      orchestrator/
        system.md
        decide.md
      phases/
        surface/
          phase_agent.md
          tools/
            server_health.md
            nmap_scan.md
            httpx_toolkit.md
        content/
          phase_agent.md
          tools/
            gobuster_scan.md
            feroxbuster_scan.md
            katana_crawl.md
            rest_api_probe.md
        vuln/
          phase_agent.md
          tools/
            nuclei_scan.md

  orchestration/                        # runtime (implementation follow-up)
    __init__.py
    artifact_store.py
    compress.py
    phases.py
    tool_agent.py
    phase_agent.py
    orchestrator.py

  pipelines/task_discovery.py           # wires orchestrator; keeps reporter loop
  guardrails.py                         # allowlist + demo (existing)
  settings.py                           # new caps / artifact / llmlingua keys
```

## Agent folder rules

1. **One file per agent role** — orchestrator, phase agent, or tool agent.
2. **Phase isolation** — tools live only under their phase directory.
3. **Shared policy once** — `_shared/lab_authorization.md` is included by loader into every system prompt; do not duplicate long policy in each tool file.
4. **Templates use placeholders** — `{target}`, `{scan_host}`, `{job_context}`, `{phase_rollup}`, `{prior_facts}`, `{tool_summary_budget}`.
5. **No raw stdout in prompts** — prompt files must instruct agents to consume summaries/rollups only.

## Prompt load path (runtime)

```text
load_shared("lab_authorization")
+ load("orchestrator/system")           # orchestrator
+ load(f"phases/{phase}/phase_agent")   # phase agent
+ load(f"phases/{phase}/tools/{tool}")  # tool agent
```

`prompt_loader.py` resolves paths relative to `app/agents/prompts/`.

## On-disk job artifacts

```text
{artifact_root}/{job_id}/
  job.context.json
  phases/
    surface.rollup.json
    content.rollup.json
    vuln.rollup.json
  tools/
    001_server_health.raw.json
    001_server_health.summary.json
    002_nmap_scan.raw.json
    002_nmap_scan.summary.json
    …
```

## What this build includes vs later

| Included | Optional hardening |
|----------|-------------------|
| Docs under `docs/orchestration/` | Bake HF weights into image |
| `app/agents/prompts/**` + loader | Tuned auto phase loops |
| `app/orchestration/*` runtime | Live HexStrike e2e CI |
| `_run_live_agent` → `run_recon` | |
| Output JSON schemas in docs | |
