"""CAI session stub stream + stop.

CAI DISABLED — tests commented out.
"""
from __future__ import annotations

# import asyncio
#
# import pytest
#
# from app.adapters import cai_session as sess
# from app.settings import WorkerSettings
#
#
# @pytest.mark.asyncio
# async def test_stub_session_streams_and_stop(monkeypatch):
#     monkeypatch.setenv("CAI_CHAT_STUB", "1")
#     from app.settings import get_settings
#
#     get_settings.cache_clear()
#     settings = WorkerSettings(cai_chat_stub="1", cai_workdir="")
#     reg = sess.SessionRegistry()
#     session = await reg.create(
#         user_id="u1",
#         team="red",
#         message="hello",
#         task_id=None,
#         settings=settings,
#     )
#     assert session.status == "running"
#     await asyncio.sleep(0.2)
#     types = [e.type for e in session.events]
#     assert "started" in types
#     assert "user_echo" in types
#     stopped = await reg.stop(session.id)
#     assert stopped.status == "stopped"
#
#
# @pytest.mark.asyncio
# async def test_fail_closed_missing_workdir(monkeypatch):
#     get_settings = __import__("app.settings", fromlist=["get_settings"]).get_settings
#     get_settings.cache_clear()
#     settings = WorkerSettings(cai_chat_stub="0", cai_workdir="/nonexistent-cai-path-xyz")
#     reg = sess.SessionRegistry()
#     session = await reg.create(
#         user_id="u1",
#         team="red",
#         message="x",
#         task_id=None,
#         settings=settings,
#     )
#     assert session.status == "failed"
#     assert session.error and "CAI_WORKDIR" in session.error
