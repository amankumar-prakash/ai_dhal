"""CAI (Cybersecurity AI) client — stub plan or live one-shot CLI invocation.

Live mode runs `uv run cai "<prompt>"` (falling back to a bare `cai` on `PATH`) inside
`CAI_WORKDIR`, treating the CLI's stdout as the kill-chain plan text. It fails closed
(raises `RuntimeError`) when the workdir is missing, no CAI executable is found, the
process errors, or it times out — never silently falls back to the stub plan.
"""
from __future__ import annotations

import asyncio
import os
import shutil
from pathlib import Path
from typing import Any

from app.adapters import llm_client
from app.settings import WorkerSettings, get_settings

_TIMEOUT_SECONDS = 120
_STAGES = ["recon", "initial_access", "execution", "persistence", "exfiltration"]


def _build_prompt(job: dict[str, Any]) -> str:
    return (
        "Propose a concise MITRE ATT&CK kill-chain plan (stages: "
        f"{', '.join(_STAGES)}) for red-team job {job.get('job_id')} "
        f"with profile {job.get('profile')}. Keep it to a short plan, one stage per line."
    )


async def _run_live(job: dict[str, Any], settings: WorkerSettings) -> dict[str, Any]:
    workdir = settings.cai_workdir.strip()
    if not workdir or not Path(workdir).is_dir():
        raise RuntimeError(
            "CAI_WORKDIR is not set or does not exist; cannot run live CAI "
            "(set CAI_STUB=1 to use the stub planner instead)"
        )

    prompt = _build_prompt(job)
    if shutil.which("uv"):
        cmd = ["uv", "run", "cai", prompt]
    elif shutil.which("cai"):
        cmd = ["cai", prompt]
    else:
        raise RuntimeError("Neither 'uv' nor 'cai' executable found on PATH; cannot run live CAI")

    env = os.environ.copy()
    env.setdefault("CAI_STREAM", "false")
    env.setdefault("CAI_LICENSE_OFF", "1")

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=workdir,
            env=env,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except OSError as exc:
        raise RuntimeError(f"Failed to launch live CAI ({' '.join(cmd)}) in {workdir}: {exc}") from exc

    try:
        stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=_TIMEOUT_SECONDS)
    except asyncio.TimeoutError as exc:
        proc.kill()
        await proc.wait()
        raise RuntimeError(
            f"Live CAI invocation timed out after {_TIMEOUT_SECONDS}s for job {job.get('job_id')}"
        ) from exc

    if proc.returncode != 0:
        raise RuntimeError(
            f"Live CAI exited with code {proc.returncode} for job {job.get('job_id')}: "
            f"{stderr_b.decode(errors='replace').strip()[:500]}"
        )

    stdout_text = stdout_b.decode(errors="replace").strip()
    if not stdout_text:
        raise RuntimeError(f"Live CAI produced no output for job {job.get('job_id')}")

    return {
        "source": "cai",
        "model": settings.llm_model,
        "plan": stdout_text[:4000],
        "stages": _STAGES,
    }


async def plan_chain(job: dict[str, Any], settings: WorkerSettings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()

    if settings.stub_cai:
        note = await llm_client.complete(
            f"Propose MITRE kill-chain steps for job {job.get('job_id')} profile {job.get('profile')}",
            settings,
        )
        return {
            "source": "cai-stub",
            "model": settings.llm_model,
            "plan": note[:800],
            "stages": _STAGES,
        }

    return await _run_live(job, settings)
