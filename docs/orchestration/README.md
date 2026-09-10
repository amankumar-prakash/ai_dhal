# Task-discovery orchestration docs

Hierarchical phase → tool agents, artifact persistence, and LLMLingua-2 compression for the red-team worker.

| Doc | Purpose |
|-----|---------|
| [architecture.md](architecture.md) | Layers, data flow, scaling with phases/loops |
| [structure.md](structure.md) | Repo layout, agent prompt tree, artifact layout |
| [output-formats.md](output-formats.md) | JSON contracts for raw, summary, rollup, job.context |
| [guardrails.md](guardrails.md) | Scope, allowlist, tool bans, budget stops |
| [acceptance-checklist.md](acceptance-checklist.md) | Definition of done for this build |
| [../token-overflow-management.md](../token-overflow-management.md) | Problem statement + implementation plan |

**Code home for prompts:** [`red_team_backend/app/agents/`](../../red_team_backend/app/agents/)
