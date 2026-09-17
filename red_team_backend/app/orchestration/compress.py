"""Heuristic tool-log consolidation + LLMLingua-2 compression with hard caps."""
from __future__ import annotations

import logging
import re
from typing import Any

from app.orchestration.artifact_store import empty_facts
from app.orchestration.model_context import (
    count_tokens,
    cut_to_tokens,
    llm_budget,
    split_token_chunks,
)
from app.settings import WorkerSettings, get_settings

log = logging.getLogger(__name__)

_compressor = None
_compressor_failed = False

# BERT-based LLMLingua-2 max position embeddings is 512; stay under that per chunk.
_LINGUA_CHUNK_TOKENS = 384
_FORCE_TOKENS = ["\n"]

_HTTP_LINE_RE = re.compile(
    r"(?P<url>https?://\S+)\s*(?:\[(?P<status>\d{3})\])?\s*(?:\[(?P<title>[^\]]*)\])?",
    re.I,
)


def estimate_tokens(text: str) -> int:
    return count_tokens(text or "")


def truncate_to_tokens(text: str, cap: int) -> str:
    return cut_to_tokens(text or "", cap)


def consolidate_facts(tool_name: str, target: str, stdout: str) -> dict[str, Any]:
    from app.pipelines.task_discovery import parse_findings

    facts = empty_facts()
    name = (tool_name or "").lower()
    text = stdout or ""

    for finding in parse_findings(tool_name, target, text):
        evidence = str(finding.get("evidence") or "")
        title = str(finding.get("title") or "")
        source = str(finding.get("source_tool") or name)
        sev = str(finding.get("severity") or "info")
        if "nmap" in source or "port" in title.lower():
            m = re.match(r"(\d+)/(tcp|udp)\s+open\s+(\S+)", evidence)
            if m:
                facts["open_ports"].append(
                    {"port": int(m.group(1)), "proto": m.group(2), "service": m.group(3)}
                )
            continue
        if "gobuster" in source or "ferox" in source or "path" in title.lower():
            pm = re.match(r"(/\S+)\s*\(Status:\s*(\d+)", evidence, re.I)
            if pm:
                facts["paths"].append({"path": pm.group(1), "status": pm.group(2)})
            continue
        if "katana" in source or evidence.startswith("http"):
            if evidence.startswith("http"):
                facts["urls"].append(evidence)
            continue
        if "nuclei" in source or sev in {"critical", "high", "medium", "low", "info"}:
            if "nuclei" in source or "[" in title:
                facts["exposures"].append(
                    {"severity": sev, "title": title[:240], "evidence": evidence[:500]}
                )
                continue
        if "httpx" in source or "probe" in source or "rest" in source:
            hm = _HTTP_LINE_RE.search(evidence)
            if hm:
                facts["http"] = {
                    **facts["http"],
                    "status": hm.group("status") or facts["http"].get("status"),
                    "title": (hm.group("title") or facts["http"].get("title") or "")[:200],
                    "url": hm.group("url") or target,
                }
            facts["urls"].append(evidence[:300])

    # Direct nmap parse fallback already covered by parse_findings.
    if "health" in name and text.strip():
        facts["http"] = {**facts["http"], "health": text.strip()[:400]}
    if not any(facts[k] for k in ("open_ports", "paths", "urls", "exposures")) and not facts["http"]:
        if text.strip():
            facts["errors"].append({"tool": tool_name, "note": text.strip()[:300]})
    return facts


def _get_compressor(settings: WorkerSettings):
    global _compressor, _compressor_failed
    if not settings.use_llmlingua or _compressor_failed:
        return None
    if _compressor is not None:
        return _compressor
    try:
        from llmlingua import PromptCompressor

        _compressor = PromptCompressor(
            model_name=settings.llmlingua_model,
            device_map=settings.llmlingua_device or "cpu",
            use_llmlingua2=True,
        )
        return _compressor
    except Exception as exc:  # noqa: BLE001
        _compressor_failed = True
        log.warning("LLMLingua-2 unavailable, using heuristic truncation only: %s", exc)
        return None


def _split_chunks(text: str, chunk_tokens: int = _LINGUA_CHUNK_TOKENS) -> list[str]:
    return split_token_chunks(text, chunk_tokens)


def _lingua_compress_chunk(compressor: Any, chunk: str, target_token: int) -> str:
    result = compressor.compress_prompt(
        chunk,
        rate=None,
        target_token=max(1, target_token),
        force_tokens=list(_FORCE_TOKENS),
        drop_consecutive=True,
    )
    return result.get("compressed_prompt") or chunk


def _lingua_compress(compressor: Any, text: str, target_token: int) -> str:
    chunks = _split_chunks(text)
    if not chunks:
        return text
    origin = estimate_tokens(text) or 1
    if len(chunks) == 1:
        return _lingua_compress_chunk(compressor, chunks[0], target_token)
    pieces: list[str] = []
    for chunk in chunks:
        chunk_tokens = estimate_tokens(chunk) or 1
        chunk_target = max(1, int(target_token * chunk_tokens / origin))
        if chunk_tokens <= chunk_target:
            pieces.append(chunk)
            continue
        try:
            pieces.append(_lingua_compress_chunk(compressor, chunk, chunk_target))
        except Exception as exc:  # noqa: BLE001
            log.warning("LLMLingua-2 chunk compress failed, keeping heuristic slice: %s", exc)
            pieces.append(truncate_to_tokens(chunk, chunk_target))
    return "\n".join(pieces)


def compress_text(text: str, *, target_token: int, settings: WorkerSettings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    original = text or ""
    cap = max(1, int(target_token or 1))
    origin = estimate_tokens(original)
    if origin <= cap:
        return {
            "compressed_prompt": original,
            "origin_tokens": origin,
            "compressed_tokens": origin,
            "method": "passthrough",
        }

    compressor = _get_compressor(settings)
    if compressor is not None:
        try:
            compressed = _lingua_compress(compressor, original, cap)
            compressed = truncate_to_tokens(compressed, cap)
            return {
                "compressed_prompt": compressed,
                "origin_tokens": origin,
                "compressed_tokens": estimate_tokens(compressed),
                "method": "llmlingua2",
            }
        except Exception as exc:  # noqa: BLE001
            log.warning("LLMLingua-2 compress failed, truncating: %s", exc)

    truncated = truncate_to_tokens(original, cap)
    return {
        "compressed_prompt": truncated,
        "origin_tokens": origin,
        "compressed_tokens": estimate_tokens(truncated),
        "method": "heuristic_truncate",
    }


def compress_for_llm(
    text: str,
    *,
    reserved_tokens: int,
    settings: WorkerSettings | None = None,
) -> dict[str, Any]:
    """Compress `text` so reserved + result stays at or under 80% of the model window."""
    settings = settings or get_settings()
    budget = llm_budget(settings, reserved_tokens)
    result = compress_text(text, target_token=budget["remaining"], settings=settings)
    result.update(
        {
            "model": budget["model"],
            "window": budget["window"],
            "trigger": budget["trigger"],
            "reserved": budget["reserved"],
            "cap": budget["remaining"],
        }
    )
    return result


def build_tool_summary(
    *,
    job_id: str,
    seq: int,
    phase: str,
    tool_name: str,
    target: str,
    stdout: str,
    success: bool,
    settings: WorkerSettings | None = None,
    timed_out: bool = False,
    stderr: str = "",
) -> dict[str, Any]:
    settings = settings or get_settings()
    # Prefer stdout; keep stderr available for timeout / error notes.
    combined = stdout or ""
    if stderr and stderr not in combined:
        combined = f"{combined}\n{stderr}".strip() if combined else stderr
    facts = consolidate_facts(tool_name, target, combined)
    if timed_out:
        facts["errors"].append(
            {
                "tool": tool_name,
                "note": "EST (estimated) time reached and scan halted before completion",
                "timed_out": True,
            }
        )
    elif not success and not any(facts[k] for k in ("open_ports", "paths", "urls", "exposures")) and not facts["http"]:
        note = (stderr or stdout or "tool failed").strip()[:300]
        if note and not any(
            isinstance(e, dict) and e.get("note") == note for e in facts["errors"]
        ):
            facts["errors"].append({"tool": tool_name, "note": note, "timed_out": False})
    # Keep structured facts; compress leftover prose only.
    prose = combined if len(combined or "") < 2000 else (combined or "")[:2000]
    # Prefer a short evidence string from facts rather than raw dump.
    evidence_bits: list[str] = []
    for port in facts["open_ports"][:20]:
        evidence_bits.append(f"{port.get('port')}/{port.get('proto')} {port.get('service')}")
    for path in facts["paths"][:30]:
        evidence_bits.append(f"{path.get('path')} {path.get('status')}")
    for url in facts["urls"][:20]:
        evidence_bits.append(str(url))
    for exp in facts["exposures"][:20]:
        evidence_bits.append(f"[{exp.get('severity')}] {exp.get('title')}")
    if facts["http"]:
        evidence_bits.append(json_safe(facts["http"]))
    prose_src = "\n".join(evidence_bits) if evidence_bits else prose
    compressed = compress_text(prose_src, target_token=settings.tool_summary_tokens, settings=settings)
    return {
        "schema_version": 1,
        "job_id": job_id,
        "seq": seq,
        "phase": phase,
        "tool_name": tool_name,
        "success": success and not timed_out,
        "timed_out": timed_out,
        "facts": facts,
        "evidence_compressed": compressed["compressed_prompt"],
        "token_stats": {
            "origin_tokens": compressed["origin_tokens"],
            "compressed_tokens": compressed["compressed_tokens"],
            "cap": settings.tool_summary_tokens,
            "method": compressed["method"],
        },
    }


def build_phase_rollup(
    *,
    job_id: str,
    phase: str,
    tools_run: list[str],
    tools_skipped: list[str],
    summaries: list[dict[str, Any]],
    settings: WorkerSettings | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    facts = empty_facts()
    from app.orchestration.artifact_store import merge_facts

    for summary in summaries:
        facts = merge_facts(facts, summary.get("facts") or empty_facts())
    narrative = " | ".join(
        f"{s.get('tool_name')}: {(s.get('evidence_compressed') or '')[:200]}" for s in summaries
    )
    compressed = compress_text(narrative, target_token=settings.phase_rollup_tokens, settings=settings)
    hints: list[str] = []
    if facts["paths"]:
        hints.append("probe interesting paths from content discovery")
    if facts["urls"]:
        hints.append("nuclei on discovered URLs")
    return {
        "schema_version": 1,
        "job_id": job_id,
        "phase": phase,
        "status": "completed",
        "tools_run": tools_run,
        "tools_skipped": tools_skipped,
        "facts": facts,
        "narrative_compressed": compressed["compressed_prompt"],
        "next_hints": hints[:5],
        "token_stats": {
            "compressed_tokens": compressed["compressed_tokens"],
            "cap": settings.phase_rollup_tokens,
            "method": compressed["method"],
        },
    }


def update_job_context(
    context: dict[str, Any],
    *,
    rollup: dict[str, Any],
    settings: WorkerSettings | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    from app.orchestration.artifact_store import merge_facts

    ctx = dict(context)
    facts = merge_facts(ctx.get("facts") or empty_facts(), rollup.get("facts") or empty_facts())
    phases = list(ctx.get("phases_completed") or [])
    phase = rollup.get("phase")
    if phase and phase not in phases:
        phases.append(phase)
    narrative = f"{ctx.get('narrative_compressed') or ''}\n{rollup.get('narrative_compressed') or ''}".strip()
    compressed = compress_text(narrative, target_token=settings.job_context_tokens, settings=settings)
    ctx["facts"] = facts
    ctx["phases_completed"] = phases
    ctx["narrative_compressed"] = compressed["compressed_prompt"]
    ctx["token_stats"] = {
        "compressed_tokens": compressed["compressed_tokens"],
        "cap": settings.job_context_tokens,
        "method": compressed["method"],
    }
    return ctx


def json_safe(value: Any) -> str:
    import json

    return json.dumps(value, default=str)
