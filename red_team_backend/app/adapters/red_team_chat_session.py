"""Supervised red-team chat sessions.

A session drives a LangChain agent bound to the full HexStrike MCP tool catalog.
Every tool call the agent proposes is paused and streamed to the operator as a
`tool_call_pending` event; the real MCP tool only runs after an explicit
`approve` decision. `stop` (or an approval timeout) prevents/cancels execution
and ends the current turn immediately.

There is no tool denylist — safety is the human-in-the-loop approval gate.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Literal
from uuid import UUID, uuid4

from app.orchestration.artifact_store import JobArtifactStore
from app.settings import WorkerSettings, get_settings

log = logging.getLogger(__name__)

EventType = Literal[
    "started",
    "status",
    "error",
    "ended",
    "user_echo",
    "agent_message",
    "tool_call_pending",
    "tool_call_approved",
    "tool_call_stopped",
    "tool_result",
]
Channel = Literal["user", "agent", "system", "tool"]

_CHANNEL_FOR_TYPE: dict[str, Channel] = {
    "started": "system",
    "status": "system",
    "error": "system",
    "ended": "system",
    "user_echo": "user",
    "agent_message": "agent",
    "tool_call_pending": "tool",
    "tool_call_approved": "tool",
    "tool_call_stopped": "tool",
    "tool_result": "tool",
}

_SECRET_RE = re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[=:]\s*\S+")

_SYSTEM_PROMPT = (
    "You are a red-team reconnaissance assistant operating strictly within an "
    "authorized lab. You have access to the HexStrike security tool catalog. "
    "When a task needs a tool, call it with precise arguments. A human operator "
    "reviews and approves every tool call before it runs, so state clearly what "
    "you intend to do and why. Prefer discovery/recon over exploitation unless "
    "the operator explicitly directs otherwise. Only act on in-scope targets."
)


def _system_prompt_for(target: str | None) -> str:
    base = _SYSTEM_PROMPT
    t = (target or "").strip()
    if not t:
        return base
    return (
        f"{base} The operator selected this session target in the UI: `{t}`. "
        "When they say 'the target', 'that host', or omit a hostname/IP, use this "
        "target. Prefer the hostname form for tools (strip scheme/path/port as needed)."
    )

_TOOL_RESULT_MAX = 200


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _redact(text: str) -> str:
    return _SECRET_RE.sub(r"\1=***", text or "")


def _message_text(msg: Any) -> str:
    content = getattr(msg, "content", None)
    if content is None and isinstance(msg, dict):
        content = msg.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                parts.append(str(block.get("text") or block.get("content") or ""))
            else:
                parts.append(str(block))
        return "".join(parts)
    return str(content or "")


def _is_ai_message(msg: Any) -> bool:
    if getattr(msg, "type", None) == "ai":
        return True
    if isinstance(msg, dict):
        return msg.get("role") in {"assistant", "ai"}
    return type(msg).__name__ == "AIMessage"


@dataclass
class StreamEvent:
    session_id: UUID
    seq: int
    type: EventType
    text: str = ""
    channel: Channel = "system"
    ts: datetime = field(default_factory=_now)
    call_id: str | None = None
    tool: str | None = None
    args: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "session_id": str(self.session_id),
            "seq": self.seq,
            "type": self.type,
            "channel": self.channel,
            "text": self.text,
            "ts": self.ts.isoformat(),
        }
        if self.call_id is not None:
            payload["call_id"] = self.call_id
        if self.tool is not None:
            payload["tool"] = self.tool
        if self.args is not None:
            payload["args"] = self.args
        return payload


@dataclass
class PendingCall:
    call_id: str
    tool: str
    args: dict[str, Any]
    event: asyncio.Event
    decision: str | None = None
    running_task: "asyncio.Task[Any] | None" = None


@dataclass
class RedTeamChatSession:
    id: UUID
    user_id: str
    team: str
    status: str = "starting"
    task_id: str | None = None
    target: str | None = None
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)
    ended_at: datetime | None = None
    error: str | None = None
    busy: bool = False
    messages: list[Any] = field(default_factory=list)
    events: list[StreamEvent] = field(default_factory=list)
    waiters: list[asyncio.Event] = field(default_factory=list)
    turn_task: "asyncio.Task[Any] | None" = None
    pending_call: PendingCall | None = None
    store: JobArtifactStore | None = None
    summary_md: str | None = None
    _seq: int = 0

    def public(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "team": self.team,
            "status": self.status,
            "task_id": self.task_id,
            "target": self.target,
            "busy": self.busy,
            "pending_call_id": self.pending_call.call_id if self.pending_call else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "error": self.error,
        }

    def emit(
        self,
        etype: EventType,
        text: str = "",
        *,
        call_id: str | None = None,
        tool: str | None = None,
        args: dict[str, Any] | None = None,
    ) -> StreamEvent:
        self._seq += 1
        ev = StreamEvent(
            session_id=self.id,
            seq=self._seq,
            type=etype,
            text=_redact(text),
            channel=_CHANNEL_FOR_TYPE.get(etype, "system"),
            call_id=call_id,
            tool=tool,
            args=args,
        )
        self.events.append(ev)
        if len(self.events) > 5000:
            self.events = self.events[-5000:]
        self.updated_at = _now()
        self._append_transcript(ev)
        for w in self.waiters:
            w.set()
        return ev

    def _append_transcript(self, ev: StreamEvent) -> None:
        if self.store is None:
            return
        try:
            path = self.store.root / "transcript.jsonl"
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(ev.as_dict(), default=str) + "\n")
        except Exception:  # noqa: BLE001 - transcript is best-effort
            pass


class SessionRegistry:
    def __init__(self) -> None:
        self._by_id: dict[UUID, RedTeamChatSession] = {}
        self._active_key: dict[tuple[str, str], UUID] = {}
        self._lock = asyncio.Lock()

    async def get(self, session_id: UUID) -> RedTeamChatSession | None:
        return self._by_id.get(session_id)

    async def create(
        self,
        *,
        user_id: str,
        team: str,
        message: str | None,
        task_id: str | None,
        target: str | None = None,
        settings: WorkerSettings | None = None,
    ) -> RedTeamChatSession:
        settings = settings or get_settings()
        async with self._lock:
            key = (user_id, team)
            old_id = self._active_key.get(key)
            if old_id and old_id in self._by_id:
                old = self._by_id[old_id]
                if old.status in {"starting", "running"}:
                    await self._end_unlocked(old)
            sid = uuid4()
            session = RedTeamChatSession(
                id=sid,
                user_id=user_id,
                team=team,
                task_id=task_id,
                target=(target or "").strip() or None,
            )
            try:
                session.store = JobArtifactStore(settings.artifact_root, f"chat-{sid}")
            except Exception as exc:  # noqa: BLE001 - artifacts are best-effort
                log.warning("chat artifact store unavailable: %s", exc)
                session.store = None
            self._by_id[sid] = session
            self._active_key[key] = sid

        session.status = "running"
        session.emit("started", "session started")
        if session.target:
            session.emit("status", f"target: {session.target}")

        if message and message.strip():
            text = message.strip()
            blocked = self._guardrail_block(text, settings, session_target=session.target)
            if blocked:
                session.emit("error", blocked)
                return session
            session.busy = True
            session.turn_task = asyncio.create_task(self._run_turn(session, text, settings))
        return session

    async def send_message(
        self,
        session_id: UUID,
        content: str,
        settings: WorkerSettings | None = None,
    ) -> RedTeamChatSession:
        settings = settings or get_settings()
        session = self._by_id.get(session_id)
        if not session:
            raise KeyError("session not found")
        if session.status != "running":
            raise RuntimeError("session not running")
        if session.busy:
            raise RuntimeError(
                "a message is already being processed; stop the current tool to interrupt it"
            )
        text = content.strip()
        if not text:
            raise ValueError("empty message")
        blocked = self._guardrail_block(text, settings, session_target=session.target)
        if blocked:
            session.emit("error", blocked)
            raise RuntimeError(blocked)
        session.busy = True
        session.turn_task = asyncio.create_task(self._run_turn(session, text, settings))
        return session

    async def decide_tool_call(
        self,
        session_id: UUID,
        call_id: str,
        decision: str,
        reason: str | None = None,
    ) -> RedTeamChatSession:
        session = self._by_id.get(session_id)
        if not session:
            raise KeyError("session not found")
        pc = session.pending_call
        if pc is None or pc.call_id != call_id:
            raise LookupError("no matching pending tool call")
        if decision == "approve":
            pc.decision = "approve"
            pc.event.set()
            return session
        if decision != "stop":
            raise ValueError("decision must be 'approve' or 'stop'")

        # Stop: whether pending or running, cut it and end the current turn now.
        pc.decision = "stop"
        note = f"{pc.tool} stopped by operator" + (f": {reason}" if reason else "")
        session.emit("tool_call_stopped", note, call_id=call_id, tool=pc.tool)
        session.messages.append(
            {"role": "assistant", "content": f"(Operator stopped tool {pc.tool} before it completed.)"}
        )
        pc.event.set()
        running = pc.running_task
        if running is not None and not running.done():
            running.cancel()
        if session.turn_task is not None and not session.turn_task.done():
            session.turn_task.cancel()
        session.pending_call = None
        session.busy = False
        return session

    async def stop(self, session_id: UUID) -> RedTeamChatSession:
        """End Job: terminate the session and finalize its summary."""
        session = self._by_id.get(session_id)
        if not session:
            raise KeyError("session not found")
        async with self._lock:
            await self._end_unlocked(session)
        return session

    def summary_markdown(self, session_id: UUID) -> str:
        session = self._by_id.get(session_id)
        if not session:
            raise KeyError("session not found")
        if session.summary_md is None:
            session.summary_md = self._render_summary(session)
        return session.summary_md

    async def _end_unlocked(self, session: RedTeamChatSession) -> None:
        if session.status in {"stopped", "failed"}:
            if session.summary_md is None:
                session.summary_md = self._render_summary(session)
            return
        session.status = "stopping"
        pc = session.pending_call
        if pc is not None and pc.decision is None:
            pc.decision = "stop"
            session.emit("tool_call_stopped", f"{pc.tool} stopped (job ended)", call_id=pc.call_id, tool=pc.tool)
            pc.event.set()
            if pc.running_task is not None and not pc.running_task.done():
                pc.running_task.cancel()
        if session.turn_task is not None and not session.turn_task.done():
            session.turn_task.cancel()
        session.pending_call = None
        session.busy = False
        session.status = "stopped"
        session.ended_at = _now()
        session.summary_md = self._render_summary(session)
        if session.store is not None:
            try:
                session.store.write_report(session.summary_md)
            except Exception:  # noqa: BLE001
                pass
        session.emit("ended", "session ended")

    async def _run_turn(
        self,
        session: RedTeamChatSession,
        message: str,
        settings: WorkerSettings,
    ) -> None:
        try:
            session.emit("user_echo", message)
            session.messages.append({"role": "user", "content": message})
            if settings.stub_red_team_chat:
                await self._stub_turn(session, message)
            else:
                await self._live_turn(session, settings)
        except asyncio.CancelledError:
            session.emit("status", "turn stopped by operator")
        except Exception as exc:  # noqa: BLE001
            log.exception("red_team_chat turn failed")
            # Unwrap ExceptionGroup / TaskGroup wrappers for a useful UI message.
            detail = str(exc)
            if isinstance(exc, BaseExceptionGroup) and exc.exceptions:
                detail = str(exc.exceptions[0])
            session.emit("error", detail)
        finally:
            session.busy = False
            session.turn_task = None
            session.pending_call = None
            if session.status == "running":
                # Signals the UI that the turn finished and input can re-enable.
                session.emit("status", "ready")

    async def _stub_turn(self, session: RedTeamChatSession, message: str) -> None:
        await asyncio.sleep(0)
        reply = f"[stub] received: {message[:120]}"
        session.messages.append({"role": "assistant", "content": reply})
        session.emit("agent_message", reply)

    async def _live_turn(self, session: RedTeamChatSession, settings: WorkerSettings) -> None:
        from langchain.agents import create_agent
        from langchain_mcp_adapters.tools import load_mcp_tools

        from app.adapters.llm_model_factory import build_agent_model
        from app.adapters.mcp_client import create_mcp_client
        from app.pipelines.task_discovery import select_recon_tools

        settings.require_llm_for_live()
        client = create_mcp_client(settings)
        pre_len = len(session.messages)
        async with client.session("hexstrike-ai") as mcp_session:
            mcp_tools = await load_mcp_tools(mcp_session)
            if not mcp_tools:
                raise RuntimeError("HexStrike MCP returned no tools")
            # OpenAI rejects >128 function tools; keep recon priorities first.
            mcp_tools = select_recon_tools(mcp_tools)
            wrapped = [self._wrap_tool(session, tool, settings) for tool in mcp_tools]
            model = build_agent_model(settings)
            agent = create_agent(model, wrapped, system_prompt=_system_prompt_for(session.target))
            result = await agent.ainvoke(
                {"messages": session.messages},
                config={"recursion_limit": max(2, settings.red_team_chat_max_turns * 2)},
            )
        msgs = result.get("messages") if isinstance(result, dict) else None
        if msgs:
            session.messages = list(msgs)
            for msg in msgs[pre_len:]:
                if _is_ai_message(msg):
                    text = _message_text(msg).strip()
                    if text:
                        session.emit("agent_message", text)

    def _wrap_tool(self, session: RedTeamChatSession, inner: Any, settings: WorkerSettings) -> Any:
        from langchain_core.tools import StructuredTool

        from app.orchestration.compress import build_tool_summary, compress_for_llm
        from app.orchestration.tool_output import parse_tool_output

        tool_name = getattr(inner, "name", None) or "tool"

        async def _run(**kwargs: Any) -> str:
            call_id = uuid4().hex
            pending = PendingCall(call_id=call_id, tool=tool_name, args=kwargs, event=asyncio.Event())
            session.pending_call = pending
            session.emit(
                "tool_call_pending",
                f"{tool_name} {json.dumps(kwargs, default=str)[:300]}",
                call_id=call_id,
                tool=tool_name,
                args=kwargs,
            )
            try:
                await asyncio.wait_for(
                    pending.event.wait(),
                    timeout=max(1, settings.red_team_chat_approval_timeout_seconds),
                )
            except asyncio.TimeoutError:
                pending.decision = "stop"
                session.emit(
                    "tool_call_stopped",
                    f"{tool_name} auto-stopped (approval timeout)",
                    call_id=call_id,
                    tool=tool_name,
                )
                session.messages.append(
                    {"role": "assistant", "content": f"(Tool {tool_name} timed out awaiting approval.)"}
                )
                session.pending_call = None
                raise asyncio.CancelledError()

            if pending.decision != "approve":
                # Stop was recorded elsewhere (decide_tool_call already emitted / cancelling).
                raise asyncio.CancelledError()

            session.emit("tool_call_approved", f"{tool_name} approved", call_id=call_id, tool=tool_name)

            async def _invoke() -> Any:
                if hasattr(inner, "ainvoke"):
                    return await inner.ainvoke(kwargs)
                return inner.invoke(kwargs)

            inner_task = asyncio.ensure_future(_invoke())
            pending.running_task = inner_task
            result = await inner_task

            raw_text = result if isinstance(result, str) else json.dumps(result, default=str)
            parsed = parse_tool_output(result)
            stdout = parsed.get("stdout") or raw_text
            stderr = parsed.get("stderr") or ""
            success = bool(parsed.get("success"))
            exit_code = int(parsed.get("exit_code") if parsed.get("exit_code") is not None else 0)

            summary = None
            if session.store is not None:
                try:
                    seq = session.store.next_seq()
                    session.store.write_raw(
                        seq=seq,
                        phase="chat",
                        tool_name=tool_name,
                        args=kwargs,
                        stdout=stdout,
                        stderr=stderr,
                        success=success,
                        exit_code=exit_code,
                        command_summary=f"{tool_name} {json.dumps(kwargs, default=str)[:200]}",
                    )
                    summary = build_tool_summary(
                        job_id=session.store.job_id,
                        seq=seq,
                        phase="chat",
                        tool_name=tool_name,
                        target=str(kwargs.get("target") or kwargs.get("url") or ""),
                        stdout=stdout,
                        stderr=stderr,
                        success=success,
                        settings=settings,
                    )
                    session.store.write_summary(seq=seq, tool_name=tool_name, payload=summary)
                except Exception as exc:  # noqa: BLE001
                    log.warning("chat tool artifact persist failed: %s", exc)

            excerpt = ""
            if summary is not None:
                excerpt = (summary.get("evidence_compressed") or "").strip()
            if not excerpt:
                excerpt = (stdout or stderr or "").strip()
            excerpt = excerpt.replace("\n", " ")[:_TOOL_RESULT_MAX]
            session.emit(
                "tool_result",
                f"{tool_name}: {'ok' if success else 'failed'} — {excerpt}".rstrip(" —"),
                call_id=call_id,
                tool=tool_name,
            )
            session.pending_call = None

            compressed = compress_for_llm(raw_text, reserved_tokens=2000, settings=settings)
            return compressed["compressed_prompt"]

        return StructuredTool.from_function(
            name=tool_name,
            description=getattr(inner, "description", None) or tool_name,
            coroutine=_run,
            args_schema=getattr(inner, "args_schema", None),
        )

    def _guardrail_block(
        self,
        message: str,
        settings: WorkerSettings,
        *,
        session_target: str | None = None,
    ) -> str | None:
        allow = [x.strip() for x in (settings.target_allowlist or "").split(",") if x.strip()]
        demo = (settings.demo_safe_mode or "1").strip() in {"1", "true", "True", "yes"}
        if not allow:
            return None
        hosts = re.findall(r"https?://([^/\s:]+)", message, flags=re.I)
        hosts += re.findall(r"\b(\d{1,3}(?:\.\d{1,3}){3})\b", message)
        # Bare hostnames (e.g. insightbot.nitor.in) mentioned without a scheme.
        hosts += re.findall(
            r"\b([A-Za-z0-9.-]+\.[A-Za-z]{2,})(?:[:/\s]|$)",
            message,
        )
        if session_target:
            st = session_target.strip()
            m = re.match(r"https?://([^/\s:]+)", st, flags=re.I)
            hosts.append(m.group(1) if m else st.split("/")[0].split(":")[0])
        checked: set[str] = set()
        for h in hosts:
            h = h.strip().rstrip(".")
            if not h or h in checked:
                continue
            checked.add(h)
            if h not in allow and not any(h.endswith(a) or a in h or h in a for a in allow):
                if demo or allow:
                    return f"blocked_by_guardrail: target {h} not in TARGET_ALLOWLIST"
        return None

    def _render_summary(self, session: RedTeamChatSession) -> str:
        lines: list[str] = [
            f"# Red Team Chat summary — session `{session.id}`",
            "",
            f"- **Team:** {session.team}",
            f"- **Status:** {session.status}",
            f"- **Task:** {session.task_id or '—'}",
            f"- **Started:** {session.created_at.isoformat()}",
            f"- **Ended:** {session.ended_at.isoformat() if session.ended_at else '—'}",
            "",
            "## Transcript",
            "",
        ]
        tool_rows: list[str] = []
        decisions: dict[str, str] = {}
        for ev in session.events:
            if ev.type == "user_echo":
                lines.append(f"- **user:** {ev.text}")
            elif ev.type == "agent_message":
                lines.append(f"- **agent:** {ev.text}")
            elif ev.type == "tool_call_pending":
                lines.append(f"- **tool (proposed):** {ev.text}")
            elif ev.type == "tool_call_approved" and ev.call_id:
                decisions[ev.call_id] = "approved"
            elif ev.type == "tool_call_stopped" and ev.call_id:
                decisions[ev.call_id] = "stopped"
            elif ev.type == "tool_result":
                lines.append(f"- **tool (result):** {ev.text}")
                tool_rows.append(f"- {ev.tool or 'tool'}: {ev.text}")
            elif ev.type in {"error", "status", "ended", "started"}:
                lines.append(f"- **system:** [{ev.type}] {ev.text}")
        lines.extend(["", "## Tool calls", ""])
        if tool_rows:
            lines.extend(tool_rows)
        else:
            lines.append("_No tools were run._")
        lines.extend(["", "---", "_Raw tool output persisted under the session artifact folder._", ""])
        return "\n".join(lines)

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
                yield StreamEvent(session_id=session.id, seq=last, type="status", text="", channel="system")
            finally:
                if waiter in session.waiters:
                    session.waiters.remove(waiter)


_registry = SessionRegistry()


def get_registry() -> SessionRegistry:
    return _registry
