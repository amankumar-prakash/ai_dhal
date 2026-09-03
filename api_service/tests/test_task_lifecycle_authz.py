"""Lifecycle: any ops role can review/close; status rules still apply."""
from __future__ import annotations

from uuid import uuid4

import pytest

from app.db import memory
from app.deps import Principal, PrincipalKind
from app.schemas.models import TaskCreate, TaskPatch
from app.services import identity, tasks as task_svc
from fastapi import HTTPException


@pytest.fixture(autouse=True)
def _mem(monkeypatch):
    monkeypatch.setenv("API_STORE", "memory")
    memory.reset()
    from app.config import get_settings

    get_settings.cache_clear()


def test_analyst_can_review_close():
    mgr = uuid4()
    analyst = uuid4()
    identity.set_role(mgr, "security_manager")
    identity.set_role(analyst, "security_analyst")
    mgr_p = Principal(kind=PrincipalKind.security_manager, user_id=str(mgr), role="security_manager")
    an_p = Principal(kind=PrincipalKind.security_analyst, user_id=str(analyst), role="security_analyst")
    task = task_svc.create_task(
        TaskCreate(target="t", description="d", patch_scope="p", task_type="blue", assignee_id=analyst),
        mgr_p,
    )
    tid = task["id"]
    task_svc.apply_patch(tid, TaskPatch(action="start"), an_p)
    task_svc.apply_patch(tid, TaskPatch(action="complete"), an_p)
    reviewed = task_svc.apply_patch(tid, TaskPatch(action="review"), an_p)
    assert reviewed["status"] == "reviewed"
    closed = task_svc.apply_patch(tid, TaskPatch(action="close"), an_p)
    assert closed["status"] == "closed"


def test_user_can_create_and_close():
    user = uuid4()
    identity.set_role(user, "user")
    user_p = Principal(kind=PrincipalKind.user, user_id=str(user), role="user")
    task = task_svc.create_task(
        TaskCreate(target="u", description="d", patch_scope="p", task_type="red", assignee_id=user),
        user_p,
    )
    tid = task["id"]
    task_svc.apply_patch(tid, TaskPatch(action="start"), user_p)
    task_svc.apply_patch(tid, TaskPatch(action="complete"), user_p)
    closed = task_svc.apply_patch(tid, TaskPatch(action="close"), user_p)
    assert closed["status"] == "closed"


def test_invalid_transition_still_rejected():
    user = uuid4()
    identity.set_role(user, "user")
    user_p = Principal(kind=PrincipalKind.user, user_id=str(user), role="user")
    task = task_svc.create_task(
        TaskCreate(target="bad", description="d", patch_scope="p", task_type="red"),
        user_p,
    )
    with pytest.raises(HTTPException) as ei:
        task_svc.apply_patch(task["id"], TaskPatch(action="review"), user_p)
    assert ei.value.status_code == 400
