"""Fail-closed CAI chat when workdir missing."""
# Covered in test_cai_session.py::test_fail_closed_missing_workdir — keep file for task T024 path.
from app.adapters.cai_session import SessionRegistry
from app.settings import WorkerSettings
import pytest


@pytest.mark.asyncio
async def test_workdir_missing_fail_closed():
    reg = SessionRegistry()
    s = await reg.create(
        user_id="u",
        team="red",
        message="x",
        task_id=None,
        settings=WorkerSettings(cai_chat_stub="0", cai_workdir="/nope"),
    )
    assert s.status == "failed"
