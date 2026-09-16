"""Human-readable Markdown scan report from job artifacts."""
from __future__ import annotations

from typing import Any

from app.orchestration.artifact_store import JobArtifactStore, empty_facts


def _bullets(items: list[Any], *, limit: int = 40) -> list[str]:
    lines: list[str] = []
    for item in items[:limit]:
        if isinstance(item, dict):
            if "port" in item:
                lines.append(
                    f"- `{item.get('port')}/{item.get('proto', 'tcp')}` "
                    f"{item.get('service') or ''}".rstrip()
                )
            elif "path" in item:
                lines.append(f"- `{item.get('path')}` (status {item.get('status')})")
            elif "title" in item:
                sev = item.get("severity") or "info"
                lines.append(f"- **[{sev}]** {item.get('title')}")
                if item.get("evidence"):
                    lines.append(f"  - evidence: `{item.get('evidence')}`")
            elif "note" in item:
                tool = item.get("tool") or "tool"
                flag = " _(timed out)_" if item.get("timed_out") else ""
                lines.append(f"- `{tool}`{flag}: {item.get('note')}")
            else:
                lines.append(f"- `{item}`")
        else:
            lines.append(f"- `{item}`")
    if len(items) > limit:
        lines.append(f"- …and {len(items) - limit} more")
    return lines


def render_scan_report_markdown(store: JobArtifactStore) -> str:
    """Build a release-style Markdown document from context, rollups, and summaries."""
    ctx = store.read_context()
    facts = ctx.get("facts") or empty_facts()
    budget = ctx.get("budget") or {}
    summaries = store.list_summaries()
    raws = {r.get("seq"): r for r in store.list_raw()}
    rollups = store.list_rollups()

    timed_out_tools = [
        s.get("tool_name")
        for s in summaries
        if s.get("timed_out")
        or any(e.get("timed_out") for e in (s.get("facts") or {}).get("errors") or [])
    ]
    job_timed_out = bool(ctx.get("timed_out")) or any(
        e.get("tool") == "orchestrator" and e.get("timed_out")
        for e in (facts.get("errors") or [])
        if isinstance(e, dict)
    )

    status = "partial (timeout)" if job_timed_out or timed_out_tools else "completed"
    lines: list[str] = [
        f"# Scan report — `{ctx.get('target') or store.job_id}`",
        "",
        f"- **Job ID:** `{store.job_id}`",
        f"- **Host:** `{ctx.get('scan_host') or '—'}`",
        f"- **Status:** {status}",
        f"- **Phases completed:** {', '.join(ctx.get('phases_completed') or []) or 'none'}",
        f"- **Tools used:** {budget.get('tools_used', len(summaries))} / {budget.get('max_tools', '—')}",
        "",
        "## Executive summary",
        "",
        (ctx.get("narrative_compressed") or "No narrative available yet.").strip() or "—",
        "",
        "## Findings",
        "",
    ]

    sections = [
        ("Open ports", facts.get("open_ports") or []),
        ("Discovered paths", facts.get("paths") or []),
        ("URLs", facts.get("urls") or []),
        ("Exposures", facts.get("exposures") or []),
        ("Errors / timeouts", facts.get("errors") or []),
    ]
    for title, items in sections:
        lines.append(f"### {title}")
        lines.append("")
        if not items:
            lines.append("_None_")
        else:
            lines.extend(_bullets(items))
        lines.append("")

    http = facts.get("http") or {}
    if http:
        lines.extend(["### HTTP fingerprint", "", f"```json\n{http}\n```", ""])

    if rollups:
        lines.extend(["## Phase rollups", ""])
        for rollup in rollups:
            lines.append(f"### Phase `{rollup.get('phase')}`")
            lines.append("")
            lines.append(f"- Tools run: {', '.join(rollup.get('tools_run') or []) or 'none'}")
            if rollup.get("tools_skipped"):
                lines.append(f"- Skipped: {', '.join(rollup.get('tools_skipped') or [])}")
            if rollup.get("next_hints"):
                lines.append("- Hints:")
                for hint in rollup.get("next_hints") or []:
                    lines.append(f"  - {hint}")
            narrative = (rollup.get("narrative_compressed") or "").strip()
            if narrative:
                lines.extend(["", narrative])
            lines.append("")

    if summaries:
        lines.extend(["## Tool results", ""])
        for summary in summaries:
            name = summary.get("tool_name") or "tool"
            seq = summary.get("seq")
            raw = raws.get(seq) or {}
            ok = summary.get("success")
            to = summary.get("timed_out") or raw.get("timed_out")
            badge = "TIMEOUT" if to else ("OK" if ok else "FAILED")
            lines.append(f"### `{seq:03d}` {name} — {badge}" if isinstance(seq, int) else f"### {name} — {badge}")
            lines.append("")
            if raw.get("command_summary"):
                lines.append(f"- Command: `{raw.get('command_summary')}`")
            evidence = (summary.get("evidence_compressed") or "").strip()
            if evidence:
                lines.append(f"- Evidence: {evidence}")
            stdout = (raw.get("stdout") or "")[:2000]
            stderr = (raw.get("stderr") or "")[:1000]
            if stdout.strip():
                lines.extend(["", "```", stdout.rstrip(), "```"])
            if stderr.strip():
                lines.extend(["", "**stderr**", "", "```", stderr.rstrip(), "```"])
            if to and not stdout.strip() and not stderr.strip():
                lines.append("_Timed out with no captured output._")
            lines.append("")

    lines.extend(
        [
            "---",
            "",
            "_Generated from job artifacts (`job.context.json`, phase rollups, tool summaries). "
            "Raw tool blobs remain on disk under `tools/*.raw.json`._",
            "",
        ]
    )
    return "\n".join(lines)


def finalize_scan_report(
    store: JobArtifactStore,
    *,
    timed_out: bool = False,
    timeout_note: str | None = None,
) -> str:
    """Persist Markdown report; optionally stamp job-level timeout into context."""
    if timed_out or timeout_note:
        ctx = store.read_context()
        facts = dict(ctx.get("facts") or empty_facts())
        errors = list(facts.get("errors") or [])
        note = timeout_note or "EST/job wall time reached; scan halted before completion"
        errors.append({"tool": "orchestrator", "note": note, "timed_out": True})
        facts["errors"] = errors
        ctx["facts"] = facts
        ctx["timed_out"] = True
        store.write_context(ctx)

    markdown = render_scan_report_markdown(store)
    store.write_report(markdown)
    return markdown


def scan_report_tool_call(markdown: str, *, timed_out: bool = False) -> dict[str, Any]:
    """Reporter-shaped tool call so the UI/API can download the Markdown report."""
    return {
        "tool_name": "scan_report",
        "args": {"format": "markdown"},
        "output": {
            "success": True,
            "stdout": markdown[:4000],
            "command_summary": "Generated scan_report.md",
            "markdown": markdown,
            "timed_out": timed_out,
            "exit_code": 0,
        },
    }
