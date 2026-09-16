"""Normalize HexStrike / MCP tool payloads (including timeouts + partial stdout)."""
from __future__ import annotations

import json
from typing import Any


def _as_dict(output: Any) -> dict[str, Any] | None:
    if isinstance(output, dict):
        return output
    if not isinstance(output, str):
        return None
    text = output.strip()
    if not text or text[0] not in "{[":
        return None
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
    return data if isinstance(data, dict) else None


def parse_tool_output(output: Any) -> dict[str, Any]:
    """Extract stdout/stderr/timeout flags from MCP tool content.

    HexStrike returns dict-shaped JSON with timed_out / partial_results when a
    COMMAND_TIMEOUT (if configured) kills a process. Prefer those fields so partial
    scan output is preserved even when success is false.
    """
    data = _as_dict(output)
    if data is None:
        text = "" if output is None else str(output)
        timed_out = "timeout" in text.lower() or "timed out" in text.lower()
        return {
            "stdout": text,
            "stderr": "",
            "timed_out": timed_out,
            "partial_results": bool(text.strip()) and timed_out,
            "success": bool(text.strip()) and not timed_out,
            "exit_code": -1 if timed_out else (0 if text.strip() else 1),
            "raw": output,
        }

    stdout = data.get("stdout")
    if stdout is None:
        stdout = data.get("content") or data.get("output") or ""
    stderr = data.get("stderr") or ""
    timed_out = bool(data.get("timed_out"))
    if not timed_out:
        err_blob = f"{stderr}\n{stdout}\n{data.get('error') or ''}".lower()
        timed_out = "timed out" in err_blob or "command timed out" in err_blob
    partial = bool(data.get("partial_results")) or (timed_out and bool(str(stdout).strip() or str(stderr).strip()))
    if "success" in data:
        success = bool(data.get("success"))
    else:
        success = not timed_out and int(data.get("return_code") or data.get("exit_code") or 0) == 0
    exit_code = data.get("exit_code", data.get("return_code"))
    if exit_code is None:
        exit_code = -1 if timed_out else (0 if success else 1)
    return {
        "stdout": str(stdout or ""),
        "stderr": str(stderr or ""),
        "timed_out": timed_out,
        "partial_results": partial,
        "success": success and not timed_out,
        "exit_code": int(exit_code) if exit_code is not None else 1,
        "raw": data,
    }
