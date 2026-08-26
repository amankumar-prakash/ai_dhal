"""Interactive CAI session manager — spawn uv run cai, stream lines, stdin follow-ups.

CAI DISABLED — not mounted; kept for reference only.
"""
from __future__ import annotations

import asyncio
import os
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Literal
from uuid import UUID, uuid4

from app.settings import WorkerSettings, get_settings

EventType = Literal["started", "stdout", "stderr", "user_echo", "status", "error", "ended"]
_SECRET_RE = re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[=:]\s*\S+")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _redact(text: str) -> str:
    return _SECRET_RE.sub(r"\1=***", text)


@dataclass
class StreamEvent:
    session_id: UUID
    seq: int
    type: EventType
    text: str = ""
    ts: datetime = field(default_factory=_now)

    def as_dict(self) -> dict[str, Any]:
        return {
            "session_id": str(self.session_id),
            "seq": self.seq,
            "type": self.type,
            "text": self.text,
            "ts": self.ts.isoformat(),
        }


@dataclass
class CaiSession:
    id: UUID
    user_id: str
    team: str
    status: str = "starting"
    task_id: str | None = None
    agent_type: str = "redteam_agent"
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)
    ended_at: datetime | None = None
    error: str | None = None
    proc: asyncio.subprocess.Process | None = None
    events: list[StreamEvent] = field(default_factory=list)
    waiters: list[asyncio.Event] = field(default_factory=list)
    _reader_task: asyncio.Task | None = None
    _idle_task: asyncio.Task | None = None
    _seq: int = 0
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def public(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "team": self.team,
            "status": self.status,
            "task_id": self.task_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "error": self.error,
        }

    def emit(self, etype: EventType, text: str = "") -> StreamEvent:
        self._seq += 1
        ev = StreamEvent(session_id=self.id, seq=self._seq, type=etype, text=_redact(text))
        self.events.append(ev)
        if len(self.events) > 2000:
            self.events = self.events[-2000:]
        self.updated_at = _now()
        for w in self.waiters:
            w.set()
        return ev


class SessionRegistry:
    def __init__(self) -> None:
        self._by_id: dict[UUID, CaiSession] = {}
        self._active_key: dict[tuple[str, str], UUID] = {}
        self._lock = asyncio.Lock()

    async def get(self, session_id: UUID) -> CaiSession | None:
        return self._by_id.get(session_id)

    async def create(
        self,
        *,
        user_id: str,
        team: str,
        message: str | None,
        task_id: str | None,
        settings: WorkerSettings | None = None,
        agent_type: str | None = None,
    ) -> CaiSession:
        settings = settings or get_settings()
        async with self._lock:
            key = (user_id, team)
            old_id = self._active_key.get(key)
            if old_id and old_id in self._by_id:
                old = self._by_id[old_id]
                if old.status in {"starting", "running"}:
                    await self._stop_unlocked(old)
            sid = uuid4()
            session = CaiSession(
                id=sid,
                user_id=user_id,
                team=team,
                task_id=task_id,
                agent_type=agent_type or getattr(settings, "cai_agent_type", "redteam_agent"),
            )
            self._by_id[sid] = session
            self._active_key[key] = sid

        blocked = self._guardrail_block(message or "", settings)
        if blocked:
            session.status = "failed"
            session.error = blocked
            session.emit("error", blocked)
            session.emit("ended", "blocked_by_guardrail")
            session.ended_at = _now()
            return session

        if getattr(settings, "stub_cai_chat", False):
            await self._start_stub(session, message)
            return session

        try:
            await self._start_live(session, message, settings)
        except Exception as exc:  # noqa: BLE001
            session.status = "failed"
            session.error = str(exc)
            session.emit("error", str(exc))
            session.emit("ended", "failed")
            session.ended_at = _now()
        return session

    def _guardrail_block(self, message: str, settings: WorkerSettings) -> str | None:
        allow = [x.strip() for x in (settings.target_allowlist or "").split(",") if x.strip()]
        demo = (settings.demo_safe_mode or "1").strip() in {"1", "true", "True", "yes"}
        if not allow:
            return None
        # If message mentions http(s) host not in allowlist → block
        hosts = re.findall(r"https?://([^/\s:]+)", message, flags=re.I)
        hosts += re.findall(r"\b(\d{1,3}(?:\.\d{1,3}){3})\b", message)
        for h in hosts:
            if h not in allow and not any(h.endswith(a) or a in h for a in allow):
                if demo or allow:
                    return f"blocked_by_guardrail: target {h} not in TARGET_ALLOWLIST"
        return None

    async def _start_stub(self, session: CaiSession, message: str | None) -> None:
        session.status = "running"
        session.emit("started", "CAI_CHAT_STUB=1")
        session.emit("status", "stub session running")
        if message:
            session.emit("user_echo", message)

        async def _feed() -> None:
            for line in [
                "[stub] CAI banner",
                "[stub] agent ready",
                f"[stub] processed: {(message or 'ping')[:80]}",
            ]:
                await asyncio.sleep(0.05)
                if session.status not in {"running", "starting"}:
                    return
                session.emit("stdout", line)
            # leave running until stop for multi-turn

        session._reader_task = asyncio.create_task(_feed())
        session._idle_task = asyncio.create_task(self._idle_watch(session, 1800))

    async def _start_live(
        self, session: CaiSession, message: str | None, settings: WorkerSettings
    ) -> None:
        workdir = (settings.cai_workdir or "").strip()
        if not workdir or not Path(workdir).is_dir():
            raise RuntimeError(
                "CAI_WORKDIR is not set or does not exist; cannot start CAI chat "
                "(set CAI_CHAT_STUB=1 for stub streams)"
            )
        # Host-mounted .venv often has a host Python shebang/symlink that does not
        # exist in the worker image — keep a container-local uv env instead.
        container_venv = (os.environ.get("CAI_CONTAINER_VENV") or "/var/cache/cai-venv").strip()
        env = os.environ.copy()
        env["UV_PROJECT_ENVIRONMENT"] = container_venv
        env["CAI_AGENT_TYPE"] = session.agent_type
        env.setdefault("CAI_STREAM", "true")
        env.setdefault("CAI_LICENSE_OFF", "1")
        env.setdefault("PROMPT_TOOLKIT_NO_CPR", "1")
        if settings.openai_api_key:
            env["OPENAI_API_KEY"] = settings.openai_api_key
        if settings.llm_model:
            env.setdefault("CAI_MODEL", settings.llm_model)

        # Prefer uv + container-local venv. Never exec host-mounted workdir/.venv
        # binaries (wrong OS/Python shebang on Kali workers).
        if shutil.which("uv"):
            cmd = ["uv", "run", "cai"]
        else:
            candidate = Path(container_venv) / "bin" / "cai"
            if candidate.is_file():
                py = candidate.parent / "python"
                if py.is_file() and os.access(py, os.X_OK):
                    cmd = [str(py), str(candidate)]
                else:
                    cmd = [str(candidate)]
            elif shutil.which("cai"):
                cmd = ["cai"]
            else:
                raise RuntimeError(
                    "Neither uv nor cai executable found "
                    f"(expected UV_PROJECT_ENVIRONMENT={container_venv})"
                )

        if message and message.strip():
            cmd = [*cmd, message.strip()]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=workdir,
            env=env,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        session.proc = proc
        session.status = "running"
        session.emit("started", f"spawned {' '.join(cmd[:3])}…")
        if message:
            session.emit("user_echo", message.strip())
        session._reader_task = asyncio.create_task(self._read_pipes(session))
        session._idle_task = asyncio.create_task(self._idle_watch(session, 1800))

    async def _read_pipes(self, session: CaiSession) -> None:
        assert session.proc and session.proc.stdout and session.proc.stderr

        async def _pump(stream: asyncio.StreamReader, etype: EventType) -> None:
            while True:
                line = await stream.readline()
                if not line:
                    break
                session.emit(etype, line.decode(errors="replace").rstrip("\n"))

        await asyncio.gather(
            _pump(session.proc.stdout, "stdout"),
            _pump(session.proc.stderr, "stderr"),
        )
        code = await session.proc.wait()
        if session.status in {"running", "starting", "stopping"}:
            session.status = "stopped" if code == 0 or session.status == "stopping" else "failed"
            if code not in (0, None) and session.status == "failed":
                session.error = f"CAI exited with code {code}"
                session.emit("error", session.error)
            session.emit("ended", f"exit={code}")
            session.ended_at = _now()

    async def _idle_watch(self, session: CaiSession, seconds: int) -> None:
        try:
            await asyncio.sleep(seconds)
            if session.status == "running":
                session.emit("status", "idle timeout — stopping")
                await self.stop(session.id)
        except asyncio.CancelledError:
            return

    async def send_message(self, session_id: UUID, content: str, settings: WorkerSettings | None = None) -> CaiSession:
        settings = settings or get_settings()
        session = self._by_id.get(session_id)
        if not session:
            raise KeyError("session not found")
        if session.status != "running":
            raise RuntimeError("session not running")
        text = content.strip()
        if not text:
            raise ValueError("empty message")
        blocked = self._guardrail_block(text, settings)
        if blocked:
            session.emit("error", blocked)
            raise RuntimeError(blocked)
        session.emit("user_echo", text)
        if getattr(settings, "stub_cai_chat", False):
            session.emit("stdout", f"[stub] reply to: {text[:120]}")
            return session
        if not session.proc or not session.proc.stdin:
            raise RuntimeError("CAI stdin unavailable")
        session.proc.stdin.write((text + "\n").encode())
        await session.proc.stdin.drain()
        return session

    async def stop(self, session_id: UUID) -> CaiSession:
        session = self._by_id.get(session_id)
        if not session:
            raise KeyError("session not found")
        async with self._lock:
            await self._stop_unlocked(session)
        return session

    async def _stop_unlocked(self, session: CaiSession) -> None:
        if session.status in {"stopped", "failed"}:
            return
        session.status = "stopping"
        session.emit("status", "stopping")
        if session._idle_task:
            session._idle_task.cancel()
        if getattr(get_settings(), "stub_cai_chat", False) or session.proc is None:
            session.status = "stopped"
            session.emit("ended", "stopped")
            session.ended_at = _now()
            if session._reader_task:
                session._reader_task.cancel()
            return
        proc = session.proc
        try:
            if proc.stdin:
                try:
                    proc.stdin.write(b"/exit\n")
                    await proc.stdin.drain()
                except Exception:  # noqa: BLE001
                    pass
            try:
                await asyncio.wait_for(proc.wait(), timeout=5)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
        finally:
            session.status = "stopped"
            session.emit("ended", "stopped")
            session.ended_at = _now()

    async def events_after(self, session_id: UUID, after_seq: int = 0) -> AsyncIterator[StreamEvent]:
        session = self._by_id.get(session_id)
        if not session:
            raise KeyError("session not found")
        last = after_seq
        while True:
            batch = [e for e in session.events if e.seq > last]
            for e in batch:
                last = e.seq
                yield e
                if e.type == "ended":
                    return
            if session.status in {"stopped", "failed"} and not batch:
                return
            waiter = asyncio.Event()
            session.waiters.append(waiter)
            try:
                await asyncio.wait_for(waiter.wait(), timeout=15)
            except asyncio.TimeoutError:
                # heartbeat as status comment via empty wait — client keeps connection
                yield StreamEvent(session_id=session.id, seq=last, type="status", text="")
            finally:
                if waiter in session.waiters:
                    session.waiters.remove(waiter)


_registry = SessionRegistry()


def get_registry() -> SessionRegistry:
    return _registry
