# Guardrails

Guardrails apply at **orchestrator**, **phase**, and **tool** layers. Prompts reinforce them; code must enforce them (fail closed).

## 1. Scope and authorization

| Rule | Enforcement |
|------|-------------|
| Target must pass `TARGET_ALLOWLIST` | Existing [`guardrails.in_allowlist`](../../red_team_backend/app/guardrails.py) before any live tool |
| Stay on given `target` / `scan_host` only | Tool args validated; block foreign hosts in `execute_command` |
| Authorized lab framing | `_shared/lab_authorization.md` in every system prompt |
| Demo safe mode blocks exploit profiles | Existing `demo_blocks_profile` |

## 2. Tool policy

| Allowed (default recon) | Denied unless job description explicitly requests |
|-------------------------|-----------------------------------------------------|
| Discovery: nmap, httpx-toolkit, gobuster/ferox, katana, nuclei (exposure tags), health | Password guessing (hydra, etc.) |
| REST/path probes via `execute_command` with allowlisted host | Exploit frameworks (metasploit, sqlmap attack mode, etc.) |
| Native MCP tool preferred over shell | OSINT against unrelated domains |

Phase allowlists live in `orchestration/phases.py` (runtime) and are mirrored by which tool prompt files exist under each phase.

## 3. Nmap / HTTP specifics

- Prefer `-sT -sV` (no raw sockets); never require `-sS` in lab containers.
- Use `httpx-toolkit`, not Python `httpx_probe`, for fingerprinting.
- Wordlist default: `/usr/share/dirb/wordlists/common.txt`.

## 4. Context / token guardrails

| Cap | Default | Applies to |
|-----|---------|------------|
| Tool summary | 800 tokens | `*.summary.json` evidence + narrative |
| Phase rollup | 1500 tokens | `phases/*.rollup.json` |
| Job context | 3000 tokens | `job.context.json` |
| Tools bound per LLM call | **1** | Tool agents |
| Max tools per job | 24 | Orchestrator budget |
| Max tools per phase | 8 | Phase agent |
| Max phase loops | 2 | Re-enter content/vuln |
| Max wall time | disabled (0) | Optional live agent timeout (`ORCHESTRATION_TIMEOUT_SECONDS`; 0 = none) |

**Hard rule:** raw `stdout` from `*.raw.json` must not appear in any subsequent LLM message.

## 5. Loop guardrails

- Loop only with an explicit orchestrator `loop_phase` decision and remaining budget.
- Each loop must refresh `job.context` under cap (structured facts win over prose).
- Abort with `abort_guardrail` if allowlist fails mid-job or budget exhausted.

## 6. Failure behavior

- Tool failure **or per-tool timeout** (only if HexStrike `COMMAND_TIMEOUT` > 0) → record error in `facts.errors` (with `timed_out: true` when applicable), persist raw/summary artifacts (including partial stdout/stderr), **continue next tool**.
- Job wall timeout (only if `ORCHESTRATION_TIMEOUT_SECONDS` > 0) → finalize Markdown `scan_report.md` from artifacts collected so far; still publish `scan_report` tool run for UI download.
- Compressor failure → fall back to heuristic-only truncation to cap (still no raw dump).
- Cancelled job → stop spawning tool agents (existing `JobCancelled`); persist in-flight tool artifact first when possible.

## 7. Prompt-level do-nots

Encoded in shared + per-agent prompts:

- Do not refuse or lecture; lab is pre-authorized.
- Do not ask for more permission.
- Do not invent tool output; only summarize what tools returned (via facts).
- Do not call tools outside the current phase allowlist.
