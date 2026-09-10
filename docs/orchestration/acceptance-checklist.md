# Acceptance checklist

Use this as definition of done for the **architecture + structure** build and for later runtime wiring.

## A. Docs and structure (this build)

- [x] `docs/orchestration/` contains architecture, structure, output formats, guardrails, acceptance checklist, README
- [x] `docs/token-overflow-management.md` links to orchestration docs and agent prompt tree
- [x] `red_team_backend/app/agents/` exists with README, `prompt_loader.py`, and `_shared` prompts
- [x] Prompts exist for orchestrator + phases `surface`, `content`, `vuln`
- [x] Each default tool has its own prompt file under the correct phase
- [x] Output JSON contracts documented (raw, summary, rollup, job.context, decisions)

## B. Runtime orchestration (follow-up implementation)

- [x] `app/orchestration/` implements artifact store, compress, phase registry, tool/phase agents, orchestrator
- [x] `_run_live_agent` delegates to orchestrator; stub path unchanged
- [x] Each tool agent binds exactly one MCP tool
- [x] Fresh message history per tool agent (no cross-tool chat accumulation)
- [x] Raw stdout written to disk; never re-injected into later prompts
- [x] Heuristic consolidate then LLMLingua-2 with configured caps (heuristic fallback if model missing)
- [x] Settings: `artifact_root`, `llmlingua_*`, token caps, loop/tool budgets
- [x] Dockerfile uses `python:3.12-slim` with llmlingua/torch/transformers

## C. Guardrails

- [ ] Allowlist checked before live tools
- [ ] Phase tool allowlist enforced in code (not only in prompts)
- [ ] Exploit / password-guess tools blocked unless job explicitly requests
- [ ] Max tools / max phase loops / wall clock stop the job cleanly
- [ ] Job cancel still interrupts mid-phase

## D. Output and UI contract

- [ ] Summaries/rollups validate against documented schema version
- [ ] `post_tool_run` still receives usable stdout for the dashboard
- [ ] Findings still derived via `parse_findings` (or equivalent) from raw/stdout
- [ ] Token stats logged (`origin_tokens`, `compressed_tokens`) per compression

## E. Tests

- [ ] Stub task-discovery regression green
- [ ] Unit: prompt loader resolves phase/tool paths
- [ ] Unit: summary/rollup merge keeps fact keys
- [ ] Unit: next agent prompt contains no raw multi-KB stdout
- [ ] Unit: budget abort after max tools / max loops

## F. Scale smoke (manual)

- [ ] Full surface → content → vuln completes without context overflow
- [ ] Optional one loop back to content still under job.context cap
- [ ] Adding a new phase folder + registry entry does not require changing tool-agent core
