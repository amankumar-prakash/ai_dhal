"""Defensive validation profile."""
from __future__ import annotations

from typing import Any

from app.pipelines import surface_recon


async def run(job: dict[str, Any]) -> None:
    await surface_recon.run(job)
