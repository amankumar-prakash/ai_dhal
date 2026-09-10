# Shared output contracts

## System

When you return a decision or structured result, use JSON matching the project contracts:

- Tool summaries expose `facts` with keys: `open_ports`, `paths`, `urls`, `http`, `exposures`, `errors` (use only relevant keys).
- Phase decisions: `{"action":"run_tool"|"skip_tool"|"retry_tool"|"finish_phase", "tool": "...", "args_hint": {}, "reason": "..."}`
- Orchestrator decisions: `{"action":"run_phase"|"loop_phase"|"finish_job"|"abort_guardrail", "phase": "...", "reason": "..."}`

Do not wrap JSON in markdown fences unless required by the channel.
Do not paste multi-kilobyte raw stdout into your reply.
