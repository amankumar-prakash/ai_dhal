# Hierarchical Agents + LLMLingua-2 for Token Overflow

Replace the single 128-tool LangChain ReAct agent in task-discovery with a hierarchical phase→tool agent orchestrator, persist every raw tool result outside the LLM context, and always compress forwarded context with heuristic consolidation + LLMLingua-2 so each LLM call stays within a small fixed budget.

## Docs in this build

| Doc | Contents |
|-----|----------|
| [orchestration/README.md](orchestration/README.md) | Index |
| [orchestration/architecture.md](orchestration/architecture.md) | Layers, data flow, scaling |
| [orchestration/structure.md](orchestration/structure.md) | Repo + agent prompt tree + artifacts |
| [orchestration/output-formats.md](orchestration/output-formats.md) | JSON contracts |
| [orchestration/guardrails.md](orchestration/guardrails.md) | Scope, budgets, tool policy |
| [orchestration/acceptance-checklist.md](orchestration/acceptance-checklist.md) | Definition of done |

**Agent prompts (code):** [`red_team_backend/app/agents/`](../red_team_backend/app/agents/)

## Implementation status

**Included now:**

- Orchestration documentation set (architecture, structure, formats, guardrails, checklist)
- `app/agents/` prompt tree split by orchestrator / phase / tool
- `prompt_loader.py` to compose shared + agent system prompts
- `app/orchestration/` runtime: artifact store, compress, phases, tool/phase agents, orchestrator
- `task_discovery._run_live_agent` delegates to `orchestrator.run_recon`
- Settings caps + Docker slim + llmlingua/torch deps + compose env

**Follow-up hardening:**

- Bake/download LLMLingua-2 weights at image build
- Auto phase-loop policy tuning
- Broader integration tests against live HexStrike

## Root cause (today)

Overflow lives in [`red_team_backend/app/pipelines/task_discovery.py`](../red_team_backend/app/pipelines/task_discovery.py) `_run_live_agent`:

- One agent binds up to **128 HexStrike tools** (`select_recon_tools` / `_OPENAI_MAX_TOOLS`).
- `agent.astream(..., stream_mode="values")` replays the **full growing message history** (every prior tool’s raw stdout) on every step.
- Truncation (`stdout[:8000]`) happens only when posting to the API reporter — **never before re-entering the LLM**.
- Tool schemas alone often burn tens of thousands of tokens before any tool runs.

LLMLingua-2 alone cannot fix “10× any modern context window.” Structure must isolate context first; compression is the second line of defense.

## Architecture (summary)

See [orchestration/architecture.md](orchestration/architecture.md) for the full model.

```text
Orchestrator → Phase agent (surface|content|vuln)
                 → Tool agent (exactly 1 MCP tool, fresh chat)
                      → raw → ArtifactStore
                      → heuristic + LLMLingua-2 → summary / rollup / job.context
```

Default phases: **surface** (health, nmap, httpx-toolkit) → **content** (gobuster/ferox, katana, REST probe) → **vuln** (nuclei exposure tags). Loops re-enter a phase with capped `job.context` only.

## Structure (summary)

See [orchestration/structure.md](orchestration/structure.md).

```text
red_team_backend/app/agents/prompts/
  _shared/                 lab_authorization, output_contracts
  orchestrator/            system, decide
  phases/surface/tools/    server_health, nmap_scan, httpx_toolkit
  phases/content/tools/    gobuster, ferox, katana, rest_api_probe
  phases/vuln/tools/       nuclei_scan
```

## Output format / guardrails / acceptance

- Contracts: [orchestration/output-formats.md](orchestration/output-formats.md)
- Guardrails: [orchestration/guardrails.md](orchestration/guardrails.md)
- Checklist: [orchestration/acceptance-checklist.md](orchestration/acceptance-checklist.md)

## Persistence (runtime follow-up)

Per-job directory under `artifact_root`:

- `tools/{seq}_{tool}.raw.json` / `.summary.json`
- `phases/{phase}.rollup.json`
- `job.context.json`

**Hard rule:** raw blobs never re-enter an LLM prompt.

## Compression pipeline (runtime follow-up)

1. Heuristic consolidate (`parse_findings`-style facts)
2. LLMLingua-2 (`llmlingua`, bert-base meetingbank model)
3. Hard caps: tool 800 / phase 1500 / job.context 3000 tokens

## Docker / deps (runtime follow-up)

- Switch worker to `python:3.12-slim`
- Add `llmlingua`, `torch` (CPU), `transformers`

## Out of scope (this iteration)

- Rewriting surface-recon / deep-emulation
- Re-enabling CAI
- Changing HexStrike MCP itself
