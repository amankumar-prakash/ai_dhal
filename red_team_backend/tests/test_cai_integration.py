"""CAI integration tests — stub mode (no live CAI binary or API key required).

These tests verify the full CAI integration:
- Session create / stream / stop lifecycle
- cai_client.plan_chain stub output
- Guardrail blocks in chat (out-of-scope target)
- deep_emulation pipeline completes with CAI plan
- send_message in stub mode

Run with:
    cd red_team_backend
    LLM_STUB=1 CAI_STUB=1 CAI_CHAT_STUB=1 pytest tests/test_cai_integration.py -v
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.adapters import cai_client, cai_session as sess
from app.settings import WorkerSettings


# -------------------------------------------------
# Helpers
# -------------------------------------------------

def _stub_settings(**overrides) -> WorkerSettings:
    """Return a WorkerSettings instance with CAI in stub mode."""
    from app.settings import get_settings
    get_settings.cache_clear()
    defaults = dict(
        llm_stub="1",
        cai_stub="1",
        cai_chat_stub="1",
        cai_workdir="",
        demo_safe_mode="0",   # disable demo blocks so stub runs freely
        target_allowlist="",  # no allowlist = all targets pass
    )
    defaults.update(overrides)
    return WorkerSettings(**defaults)


# -------------------------------------------------
# 1. CAI Session lifecycle (stub mode)
# -------------------------------------------------

@pytest.mark.asyncio
async def test_cai_stub_session_creates_and_streams():
    """Stub session: status=running, emits started+user_echo+stdout events."""
    settings = _stub_settings()
    registry = sess.SessionRegistry()

    session = await registry.create(
        user_id="test-user-1",
        team="red",
        message="scan 192.168.1.1",
        task_id="task-001",
        settings=settings,
    )

    # Stub chat should always start successfully
    assert session.status in {"running", "starting"}, \
        f"Expected running/starting, got {session.status!r}: {session.error}"

    # Wait for async stub feed to emit events
    await asyncio.sleep(0.3)

    event_types = [e.type for e in session.events]
    assert "started" in event_types, f"Missing 'started': {event_types}"
    assert "user_echo" in event_types, f"Missing 'user_echo': {event_types}"
    assert "stdout" in event_types, f"Missing 'stdout': {event_types}"

    user_echo_events = [e for e in session.events if e.type == "user_echo"]
    assert any("192.168.1.1" in e.text for e in user_echo_events), \
        f"User message not echoed: {[e.text for e in user_echo_events]}"



@pytest.mark.asyncio
async def test_cai_stub_session_stop():
    """Stopping a stub session transitions it to stopped state."""
    settings = _stub_settings()
    registry = sess.SessionRegistry()

    session = await registry.create(
        user_id="test-user-2",
        team="red",
        message="ping",
        task_id=None,
        settings=settings,
    )
    assert session.status == "running"
    stopped = await registry.stop(session.id)
    assert stopped.status == "stopped"
    assert stopped.ended_at is not None


@pytest.mark.asyncio
async def test_cai_stub_send_message():
    """Sending a follow-up message to a running stub session emits stdout."""
    settings = _stub_settings()
    registry = sess.SessionRegistry()

    session = await registry.create(
        user_id="test-user-3",
        team="red",
        message="initial prompt",
        task_id=None,
        settings=settings,
    )
    await asyncio.sleep(0.1)
    assert session.status == "running"

    updated = await registry.send_message(session.id, "follow-up question", settings)
    assert updated.status == "running"

    stdout_texts = [e.text for e in session.events if e.type == "stdout"]
    assert any("follow-up" in t for t in stdout_texts)


# -------------------------------------------------
# 2. Guardrail blocks
# -------------------------------------------------

@pytest.mark.asyncio
async def test_cai_guardrail_blocks_out_of_scope_ip():
    """Chat with out-of-scope IP => session fails with blocked_by_guardrail."""
    settings = _stub_settings(target_allowlist="192.168.1.0", demo_safe_mode="1")
    registry = sess.SessionRegistry()

    session = await registry.create(
        user_id="test-user-4",
        team="red",
        message="attack http://10.0.0.99/admin",
        task_id=None,
        settings=settings,
    )

    assert session.status == "failed"
    assert session.error is not None
    assert "blocked_by_guardrail" in session.error


@pytest.mark.asyncio
async def test_cai_guardrail_allows_in_scope():
    """Chat with allowlisted target passes guardrail => session starts."""
    settings = _stub_settings(target_allowlist="192.168.1.0", demo_safe_mode="1")
    registry = sess.SessionRegistry()

    session = await registry.create(
        user_id="test-user-5",
        team="red",
        message="scan http://192.168.1.0/api",
        task_id=None,
        settings=settings,
    )
    assert session.status in {"running", "starting"}


# -------------------------------------------------
# 3. cai_client.plan_chain stub
# -------------------------------------------------

@pytest.mark.asyncio
async def test_cai_plan_chain_stub_returns_stages():
    """plan_chain stub returns expected structure with all MITRE stages."""
    settings = _stub_settings()
    job = {"job_id": "job-abc-001", "profile": "deep-emulation"}

    result = await cai_client.plan_chain(job, settings)

    assert result["source"] == "cai-stub"
    assert "plan" in result
    assert "stages" in result
    expected_stages = ["recon", "initial_access", "execution", "persistence", "exfiltration"]
    assert result["stages"] == expected_stages
    assert len(result["plan"]) > 0


@pytest.mark.asyncio
async def test_cai_plan_chain_fails_closed_missing_workdir():
    """plan_chain in live mode raises RuntimeError if workdir not set."""
    settings = WorkerSettings(llm_stub="1", cai_stub="0", cai_workdir="")
    job = {"job_id": "job-fail-closed", "profile": "deep-emulation"}

    with pytest.raises(RuntimeError, match="CAI_WORKDIR"):
        await cai_client.plan_chain(job, settings)


# -------------------------------------------------
# 4. Session fail-closed for missing workdir
# -------------------------------------------------

@pytest.mark.asyncio
async def test_cai_session_fails_closed_nonexistent_workdir():
    """Live CAI session fails closed when workdir doesn t exist."""
    settings = WorkerSettings(
        llm_stub="1",
        cai_stub="1",
        cai_chat_stub="0",
        cai_workdir="/nonexistent-path-xyz123",
    )
    registry = sess.SessionRegistry()
    session = await registry.create(
        user_id="test-user-fail",
        team="red",
        message="test",
        task_id=None,
        settings=settings,
    )
    assert session.status == "failed"
    assert session.error is not None
    assert "CAI_WORKDIR" in session.error


# -------------------------------------------------
# 5. One session per user+team (replace policy)
# -------------------------------------------------

@pytest.mark.asyncio
async def test_cai_one_active_session_per_user_team():
    """Creating a new session replaces the previous one for same user+team."""
    settings = _stub_settings()
    registry = sess.SessionRegistry()

    session1 = await registry.create(
        user_id="test-user-replace",
        team="red",
        message="first",
        task_id=None,
        settings=settings,
    )
    session2 = await registry.create(
        user_id="test-user-replace",
        team="red",
        message="second",
        task_id=None,
        settings=settings,
    )

    assert session1.id != session2.id
    assert session1.status in {"stopped", "stopping", "failed"}
    assert session2.status in {"running", "starting"}


# -------------------------------------------------
# 6. Secret redaction in events
# -------------------------------------------------

def test_cai_secret_redaction_in_stream_events():
    """StreamEvent with sensitive text is redacted before storing."""
    from app.adapters.cai_session import CaiSession
    from uuid import uuid4

    session = CaiSession(id=uuid4(), user_id="u", team="red")
    ev = session.emit("stdout", "Setting API_KEY=sk-supersecret123 in env")

    assert "sk-supersecret123" not in ev.text
    assert "***" in ev.text


# -------------------------------------------------
# 7. Deep emulation pipeline with CAI stub
# -------------------------------------------------

@pytest.mark.asyncio
async def test_deep_emulation_runs_with_cai_stub():
    """deep_emulation.run() with CAI stub completes and creates 5 chain steps."""
    from app.pipelines import deep_emulation

    settings = _stub_settings(api_base_url="http://localhost:8000/api/v1", hexstrike_stub="1")
    job = {"job_id": "de-job-001", "profile": "deep-emulation", "assets": [], "team": "red"}

    with patch("app.pipelines.deep_emulation.ApiReporter") as mock_reporter_cls:
        mock_reporter = MagicMock()
        mock_reporter.patch_job = AsyncMock(return_value=None)
        mock_reporter.post_threat_event = AsyncMock(return_value=None)
        mock_reporter.post_attack_chain = AsyncMock(return_value={"id": "chain-001"})
        mock_reporter.post_chain_step = AsyncMock(return_value=None)
        mock_reporter_cls.return_value = mock_reporter

        with patch("app.pipelines.surface_recon.run", new_callable=AsyncMock):
            await deep_emulation.run(job, settings)

    mock_reporter.post_attack_chain.assert_called_once()
    assert mock_reporter.post_chain_step.call_count == 5

    titles = [call.args[1]["title"] for call in mock_reporter.post_chain_step.call_args_list]
    assert any("cai-stub" in title for title in titles)
