"""Job artifact persistence — raw tool output never re-enters LLM prompts."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def empty_facts() -> dict[str, Any]:
    return {
        "open_ports": [],
        "paths": [],
        "urls": [],
        "http": {},
        "exposures": [],
        "errors": [],
    }


def merge_facts(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    out = empty_facts()
    for key in out:
        if key == "http":
            merged = dict(base.get("http") or {})
            merged.update(incoming.get("http") or {})
            out["http"] = merged
            continue
        seen: set[str] = set()
        items: list[Any] = []
        for src in (base.get(key) or [], incoming.get(key) or []):
            for item in src:
                marker = json.dumps(item, sort_keys=True, default=str)
                if marker in seen:
                    continue
                seen.add(marker)
                items.append(item)
        out[key] = items
    return out


class JobArtifactStore:
    def __init__(self, root: str | Path, job_id: str) -> None:
        self.job_id = str(job_id)
        self.root = Path(root) / self.job_id
        self.tools_dir = self.root / "tools"
        self.phases_dir = self.root / "phases"
        self.tools_dir.mkdir(parents=True, exist_ok=True)
        self.phases_dir.mkdir(parents=True, exist_ok=True)
        self._seq = 0
        if not self.context_path.is_file():
            self.write_context(self.default_context())

    @property
    def context_path(self) -> Path:
        return self.root / "job.context.json"

    def default_context(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "job_id": self.job_id,
            "target": "",
            "scan_host": "",
            "phases_completed": [],
            "loop_count": 0,
            "facts": empty_facts(),
            "narrative_compressed": "",
            "budget": {
                "tools_used": 0,
                "max_tools": 24,
                "phase_loops_used": 0,
                "max_phase_loops": 2,
            },
            "token_stats": {"compressed_tokens": 0, "cap": 3000},
        }

    def _write_json(self, path: Path, payload: dict[str, Any]) -> Path:
        path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        return path

    def read_json(self, path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    def read_context(self) -> dict[str, Any]:
        return self.read_json(self.context_path)

    def write_context(self, payload: dict[str, Any]) -> Path:
        return self._write_json(self.context_path, payload)

    def next_seq(self) -> int:
        self._seq += 1
        return self._seq

    def write_raw(
        self,
        *,
        seq: int,
        phase: str,
        tool_name: str,
        args: dict[str, Any],
        stdout: str,
        stderr: str = "",
        success: bool = True,
        exit_code: int = 0,
        command_summary: str = "",
        started_at: str | None = None,
        finished_at: str | None = None,
    ) -> Path:
        payload = {
            "schema_version": 1,
            "job_id": self.job_id,
            "seq": seq,
            "phase": phase,
            "tool_name": tool_name,
            "args": args,
            "started_at": started_at or _now(),
            "finished_at": finished_at or _now(),
            "success": success,
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": stderr,
            "command_summary": command_summary or tool_name,
        }
        path = self.tools_dir / f"{seq:03d}_{tool_name}.raw.json"
        return self._write_json(path, payload)

    def write_summary(self, *, seq: int, tool_name: str, payload: dict[str, Any]) -> Path:
        path = self.tools_dir / f"{seq:03d}_{tool_name}.summary.json"
        return self._write_json(path, payload)

    def write_rollup(self, phase: str, payload: dict[str, Any]) -> Path:
        path = self.phases_dir / f"{phase}.rollup.json"
        return self._write_json(path, payload)

    def read_rollup(self, phase: str) -> dict[str, Any] | None:
        path = self.phases_dir / f"{phase}.rollup.json"
        if not path.is_file():
            return None
        return self.read_json(path)
