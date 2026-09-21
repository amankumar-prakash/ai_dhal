"""Red-team supervised chat session: stub, approval gate, stop, busy lock, summary."""
from __future__ import annotations

import asyncio
import contextlib
from uuid import uuid4

from pydantic import BaseModel

from app.adapters import red_team_chat_session as sess
from app.adapters.red_team_chat_session import RedTeamChatSession, SessionRegistry
from app.orchestration.artifact_store import JobArtifactStore
from app.settings import WorkerSettings

_VALID_CHANNELS = {"user", "agent", "system", "tool"}


def _settings(tmp_path, **overrides):
    base = dict(
        red_team_chat_stub="1",
        llm_stub="1",
        llmlingua_enabled="0",
        artifact_root=str(tmp_path),
        red_team_chat_approval_timeout_seconds=300,
    )
    base.update(overrides)
    return WorkerSettings(**base)


class _Args(BaseModel):
    target: str = ""
    wordlist: str = ""


class _FakeTool:
    def __init__(self, name="whatweb", output=None):
        self.name = name
        self.description = f"{name} tool"
        self.args_schema = _Args
        self.calls = 0
        self._output = output or {"stdout": "banner", "success": True, "exit_code": 0}

    async def ainvoke(self, payload):
        self.calls += 1
        return self._output


class _SlowTool:
    def __init__(self, name="nmap_scan", delay=5):
        self.name = name
        self.description = "slow tool"
        self.args_schema = _Args
        self.delay = delay
        self.started = False
        self.cancelled = False
        self.completed = False

    async def ainvoke(self, payload):
        self.started = True
        try:
            await asyncio.sleep(self.delay)
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        self.completed = True
        return {"stdout": "done", "success": True}


def _running_session(reg, tmp_path):
    session = RedTeamChatSession(id=uuid4(), user_id="u1", team="red", status="running")
    session.store = JobArtifactStore(tmp_path, f"chat-{session.id}")
    reg._by_id[session.id] = session
    return session


async def test_stub_session_emits_channels(tmp_path):
    reg = SessionRegistry()
    settings = _settings(tmp_path)
    session = await reg.create(user_id="u1", team="red", message="hello", task_id=None, settings=settings)
    assert session.status == "running"
    if session.turn_task:
        await session.turn_task
    types = [e.type for e in session.events]
    assert "started" in types
    assert "user_echo" in types
    assert "agent_message" in types
    for ev in session.events:
        assert ev.channel in _VALID_CHANNELS


async def test_busy_lock_rejects_second_message(tmp_path):
    reg = SessionRegistry()
    session = _running_session(reg, tmp_path)
    session.busy = True
    try:
        await reg.send_message(session.id, "next", _settings(tmp_path))
        raised = False
    except RuntimeError:
        raised = True
    assert raised


async def test_pending_then_approve_runs_tool(tmp_path):
    reg = SessionRegistry()
    settings = _settings(tmp_path)
    session = _running_session(reg, tmp_path)
    inner = _FakeTool(output={"stdout": "A" * 3000, "success": True, "exit_code": 0})
    wrapped = reg._wrap_tool(session, inner, settings)

    task = asyncio.ensure_future(wrapped.coroutine(target="10.0.0.5"))
    session.turn_task = task
    await asyncio.sleep(0.05)
    assert session.pending_call is not None
    assert any(e.type == "tool_call_pending" for e in session.events)
    assert inner.calls == 0  # not invoked before approval

    call_id = session.pending_call.call_id
    await reg.decide_tool_call(session.id, call_id, "approve")
    await task

    assert inner.calls == 1
    assert any(e.type == "tool_call_approved" for e in session.events)
    results = [e for e in session.events if e.type == "tool_result"]
    assert results and len(results[0].text) <= 400  # bounded, not a wall of output

    raws = session.store.list_raw()
    assert raws and raws[0]["stdout"] == "A" * 3000  # full raw persisted byte-for-byte


async def test_stop_pending_never_runs_tool(tmp_path):
    reg = SessionRegistry()
    settings = _settings(tmp_path)
    session = _running_session(reg, tmp_path)
    session.busy = True
    inner = _FakeTool()
    wrapped = reg._wrap_tool(session, inner, settings)

    task = asyncio.ensure_future(wrapped.coroutine(target="10.0.0.5"))
    session.turn_task = task
    await asyncio.sleep(0.05)
    call_id = session.pending_call.call_id

    await reg.decide_tool_call(session.id, call_id, "stop", reason="not now")
    with contextlib.suppress(asyncio.CancelledError):
        await task

    assert inner.calls == 0
    assert any(e.type == "tool_call_stopped" for e in session.events)
    assert session.busy is False


async def test_stop_running_tool_cancels_midflight(tmp_path):
    reg = SessionRegistry()
    settings = _settings(tmp_path)
    session = _running_session(reg, tmp_path)
    session.busy = True
    inner = _SlowTool()
    wrapped = reg._wrap_tool(session, inner, settings)

    task = asyncio.ensure_future(wrapped.coroutine(target="10.0.0.5"))
    session.turn_task = task
    await asyncio.sleep(0.05)
    call_id = session.pending_call.call_id
    await reg.decide_tool_call(session.id, call_id, "approve")
    await asyncio.sleep(0.05)
    assert inner.started is True

    await reg.decide_tool_call(session.id, call_id, "stop")
    with contextlib.suppress(asyncio.CancelledError):
        await task

    assert inner.cancelled is True
    assert inner.completed is False
    assert session.busy is False
    assert any(e.type == "tool_call_stopped" for e in session.events)


async def test_approval_timeout_auto_stops(tmp_path):
    reg = SessionRegistry()
    settings = _settings(tmp_path, red_team_chat_approval_timeout_seconds=1)
    session = _running_session(reg, tmp_path)
    inner = _FakeTool()
    wrapped = reg._wrap_tool(session, inner, settings)

    task = asyncio.ensure_future(wrapped.coroutine(target="10.0.0.5"))
    session.turn_task = task
    with contextlib.suppress(asyncio.CancelledError):
        await asyncio.wait_for(task, timeout=3)

    assert inner.calls == 0
    assert any("timeout" in e.text.lower() and e.type == "tool_call_stopped" for e in session.events)


async def test_decide_unknown_call_id_errors(tmp_path):
    reg = SessionRegistry()
    session = _running_session(reg, tmp_path)
    try:
        await reg.decide_tool_call(session.id, "does-not-exist", "approve")
        raised = False
    except LookupError:
        raised = True
    assert raised


async def test_guardrail_blocks_out_of_scope(tmp_path):
    reg = SessionRegistry()
    settings = _settings(tmp_path, target_allowlist="10.0.0.5")
    session = await reg.create(
        user_id="u1", team="red", message="scan http://evil.example", task_id=None, settings=settings
    )
    assert any(e.type == "error" and "guardrail" in e.text for e in session.events)
    assert session.turn_task is None


async def test_end_job_generates_summary(tmp_path):
    reg = SessionRegistry()
    settings = _settings(tmp_path)
    session = await reg.create(user_id="u1", team="red", message="hello", task_id=None, settings=settings)
    if session.turn_task:
        await session.turn_task
    await reg.stop(session.id)
    assert session.status == "stopped"
    assert any(e.type == "ended" for e in session.events)
    summary = reg.summary_markdown(session.id)
    assert "Red Team Chat summary" in summary
    assert session.store.read_report() is not None


async def test_send_on_stopped_session_raises(tmp_path):
    reg = SessionRegistry()
    settings = _settings(tmp_path)
    session = await reg.create(user_id="u1", team="red", message=None, task_id=None, settings=settings)
    await reg.stop(session.id)
    try:
        await reg.send_message(session.id, "hi", settings)
        raised = False
    except RuntimeError:
        raised = True
    assert raised


async def test_start_job_dedupes_previous_session(tmp_path):
    reg = SessionRegistry()
    settings = _settings(tmp_path)
    first = await reg.create(user_id="u1", team="red", message=None, task_id=None, settings=settings)
    second = await reg.create(user_id="u1", team="red", message=None, task_id=None, settings=settings)
    assert first.id != second.id
    assert first.status == "stopped"
    assert second.status == "running"
    assert second.messages == []


def _progress_events(session):
    return [e for e in session.events if e.type == "tool_progress"]


async def test_running_tool_emits_progress_then_100(tmp_path):
    reg = SessionRegistry()
    settings = _settings(tmp_path)
    session = _running_session(reg, tmp_path)
    inner = _SlowTool(delay=1.1)
    wrapped = reg._wrap_tool(session, inner, settings)

    task = asyncio.ensure_future(wrapped.coroutine(target="10.0.0.5"))
    session.turn_task = task
    await asyncio.sleep(0.05)
    call_id = session.pending_call.call_id
    await reg.decide_tool_call(session.id, call_id, "approve")
    await asyncio.sleep(0.15)

    mid = _progress_events(session)
    assert mid, "expected at least one in-flight tool_progress event"
    assert all(e.args and 1 <= int(e.args["progress_pct"]) <= 95 for e in mid)
    assert all(e.args.get("mode") == "guess" for e in mid)
    assert all(e.call_id == call_id for e in mid)

    await task
    finals = [e for e in _progress_events(session) if e.args and e.args.get("progress_pct") == 100]
    assert finals
    transcript = (session.store.root / "transcript.jsonl").read_text(encoding="utf-8")
    assert "tool_progress" not in transcript
    summary = reg._render_summary(session)
    assert "tool_progress" not in summary


async def test_wordlist_tool_progress_uses_list_total(tmp_path):
    reg = SessionRegistry()
    settings = _settings(tmp_path)
    session = _running_session(reg, tmp_path)
    inner = _SlowTool(name="gobuster_scan", delay=0.2)
    wrapped = reg._wrap_tool(session, inner, settings)

    task = asyncio.ensure_future(
        wrapped.coroutine(target="10.0.0.5", wordlist="/usr/share/wordlists/dirb/common.txt")
    )
    session.turn_task = task
    await asyncio.sleep(0.05)
    await reg.decide_tool_call(session.id, session.pending_call.call_id, "approve")
    await task

    mid = [e for e in _progress_events(session) if e.args and int(e.args["progress_pct"]) < 100]
    assert mid
    assert any(e.args.get("mode") == "wordlist" and e.args.get("list_total") == 4614 for e in mid)


async def test_stop_running_tool_does_not_emit_100(tmp_path):
    reg = SessionRegistry()
    settings = _settings(tmp_path)
    session = _running_session(reg, tmp_path)
    session.busy = True
    inner = _SlowTool(delay=5)
    wrapped = reg._wrap_tool(session, inner, settings)

    task = asyncio.ensure_future(wrapped.coroutine(target="10.0.0.5"))
    session.turn_task = task
    await asyncio.sleep(0.05)
    call_id = session.pending_call.call_id
    await reg.decide_tool_call(session.id, call_id, "approve")
    await asyncio.sleep(0.15)
    await reg.decide_tool_call(session.id, call_id, "stop")
    with contextlib.suppress(asyncio.CancelledError):
        await task

    assert inner.cancelled is True
    pcts = [e.args.get("progress_pct") for e in _progress_events(session) if e.args]
    assert 100 not in pcts
