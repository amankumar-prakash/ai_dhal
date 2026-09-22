"""Async resource sampler — CPU/memory of the worker process tree per job.

Runs a background task for the job lifetime, sampling every
``resource_sample_interval_seconds``. A lightweight :meth:`span` context marks
which activity (a tool name, or ``"summarize"``) is currently active so we can
report per-span peak CPU/RSS. Samples are written to ``job.resources.log``.
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

from app.orchestration.artifact_store import JobArtifactStore
from app.settings import WorkerSettings

log = logging.getLogger(__name__)

try:  # psutil is optional; the sampler degrades to a no-op without it.
    import psutil
except Exception:  # pragma: no cover - import guard
    psutil = None  # type: ignore[assignment]


@dataclass
class SpanPeak:
    """Peak resource usage captured while a named span was active."""

    name: str
    cpu_peak: float = 0.0
    rss_peak_mb: float = 0.0
    sys_cpu_peak: float = 0.0
    sys_mem_peak: float = 0.0
    samples: int = 0
    _t0: float = field(default_factory=time.monotonic)
    _elapsed_ms: int | None = None

    def duration_ms(self) -> int:
        if self._elapsed_ms is not None:
            return self._elapsed_ms
        return int((time.monotonic() - self._t0) * 1000)

    def finish(self) -> None:
        if self._elapsed_ms is None:
            self._elapsed_ms = int((time.monotonic() - self._t0) * 1000)


class ResourceSampler:
    """Background CPU/memory sampler scoped to a single job."""

    def __init__(self, store: JobArtifactStore, settings: WorkerSettings) -> None:
        self.store = store
        self.settings = settings
        self.interval = max(0.5, float(settings.resource_sample_interval_seconds or 5.0))
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()
        self._current: SpanPeak | None = None
        self._proc = psutil.Process(os.getpid()) if psutil else None
        self.enabled = bool(psutil) and settings.use_resource_sampler

    async def __aenter__(self) -> "ResourceSampler":
        if self.enabled and self._proc is not None:
            with contextlib.suppress(Exception):
                # Prime per-process CPU counters so the first reading is real.
                self._proc.cpu_percent(None)
                psutil.cpu_percent(None)
            self._task = asyncio.create_task(self._run())
        return self

    async def __aexit__(self, *exc: Any) -> None:
        self._stop.set()
        if self._task is not None:
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

    def _sample(self) -> dict[str, Any]:
        assert self._proc is not None
        cpu = 0.0
        rss = 0.0
        procs = [self._proc]
        with contextlib.suppress(Exception):
            procs += self._proc.children(recursive=True)
        for proc in procs:
            try:
                cpu += proc.cpu_percent(None)
                rss += proc.memory_info().rss
            except Exception:  # noqa: BLE001 - process may have exited mid-scan
                continue
        vm = psutil.virtual_memory()
        return {
            "cpu_percent": round(cpu, 1),
            "rss_mb": round(rss / (1024 * 1024), 1),
            "sys_cpu_percent": round(psutil.cpu_percent(None), 1),
            "sys_mem_percent": round(vm.percent, 1),
            "active_processes": len(procs),
            "span": self._current.name if self._current else None,
        }

    def _capture_current(self) -> None:
        sample = self._sample()
        self.store.log_resource_sample(sample)
        cur = self._current
        if cur is not None:
            cur.cpu_peak = max(cur.cpu_peak, sample["cpu_percent"])
            cur.rss_peak_mb = max(cur.rss_peak_mb, sample["rss_mb"])
            cur.sys_cpu_peak = max(cur.sys_cpu_peak, sample["sys_cpu_percent"])
            cur.sys_mem_peak = max(cur.sys_mem_peak, sample["sys_mem_percent"])
            cur.samples += 1

    async def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self._capture_current()
            except Exception as exc:  # noqa: BLE001
                log.debug("resource sample failed: %s", exc)
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(self._stop.wait(), timeout=self.interval)

    @contextlib.contextmanager
    def span(self, name: str):
        """Mark ``name`` as the active activity; yields a :class:`SpanPeak`."""
        prev = self._current
        peak = SpanPeak(name=name)
        self._current = peak
        if self.enabled:
            with contextlib.suppress(Exception):
                self._capture_current()
        try:
            yield peak
        finally:
            if self.enabled:
                with contextlib.suppress(Exception):
                    self._capture_current()
            peak.finish()
            self._current = prev
