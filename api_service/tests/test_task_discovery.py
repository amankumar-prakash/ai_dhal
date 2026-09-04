"""Task start dispatches a red job; results assemble tools/findings/chain/patches."""
from __future__ import annotations

from uuid import uuid4
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.db import memory
from app.services import identity
from app.services.targets import parse_target


def test_parse_target_url():
    parsed = parse_target("http://juice.lab:25429/rest")
    assert parsed["hostname"] == "juice.lab"
    assert "juice.lab" in parsed["allowlist"]
    assert parsed["port"] == 25429


def test_lab_reachable_url_rewrites_public_juice_shop(monkeypatch):
    from app.services.targets import lab_reachable_url

    monkeypatch.setenv("PUBLIC_IPADDR", "81.183.231.113")
    monkeypatch.setenv("VAST_TCP_PORT_10200", "25429")
    assert lab_reachable_url("http://81.183.231.113:25429") == "http://127.0.0.1:10200"
    assert lab_reachable_url("http://juice.lab:25429") == "http://juice.lab:25429"


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("API_STORE", "memory")
    memory.reset()
    from app.config import get_settings

    get_settings.cache_clear()
    from app.main import app

    return TestClient(app)


def _auth(monkeypatch, uid, role):
    identity.set_role(uid, role)
    identity.upsert_profile(
        uid, {"email": f"{role}@t", "status": "active", "must_change_password": False}
    )

    def fake_decode(token, settings):
        return {"sub": str(uid), "email": f"{role}@t"}

    monkeypatch.setattr("app.deps.decode_access_token", fake_decode)


def test_start_creates_job_and_results_unlock_on_complete(client, monkeypatch):
    mgr = uuid4()
    analyst = uuid4()
    identity.set_role(analyst, "security_analyst")
    identity.upsert_profile(
        analyst, {"email": "an@t", "status": "active", "must_change_password": False}
    )
    _auth(monkeypatch, mgr, "security_manager")
    headers = {"Authorization": "Bearer x"}

    created = client.post(
        "/api/v1/tasks",
        headers=headers,
        json={
            "target": "http://juice.lab:25429",
            "description": "Phases: nmap, httpx-toolkit, gobuster, katana, nuclei",
            "patch_scope": "none",
            "task_type": "red",
            "assignee_id": str(analyst),
        },
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["id"]

    with patch("app.services.dispatch.dispatch_job", new_callable=AsyncMock) as disp:

        async def fake_dispatch(job, settings, task=None):
            return {**job, "status": "dispatched"}

        disp.side_effect = fake_dispatch
        started = client.patch(
            f"/api/v1/tasks/{task_id}",
            headers=headers,
            json={"action": "start"},
        )
    assert started.status_code == 200, started.text
    body = started.json()
    assert body["status"] == "in_progress"
    assert body["linked_job_id"]
    assert body["asset_id"]
    job_id = body["linked_job_id"]

    empty = client.get(f"/api/v1/tasks/{task_id}/results", headers=headers)
    assert empty.status_code == 200
    assert empty.json()["job"]["id"] == job_id
    assert empty.json()["tools"] == []

    red = {"X-Service-Token": "change-me-red"}
    finding = client.post(
        "/api/v1/findings",
        headers=red,
        json={
            "title": "Open port 80/tcp (http)",
            "severity": "medium",
            "team": "red",
            "source_tool": "nmap",
            "evidence": "80/tcp open http",
            "asset_id": body["asset_id"],
            "status": "open",
        },
    )
    assert finding.status_code == 201, finding.text
    fid = finding.json()["id"]

    tool = client.post(
        "/api/v1/tool-runs",
        headers=red,
        json={
            "job_id": job_id,
            "team": "red",
            "tool_name": "nmap_scan",
            "command_summary": "nmap -sV http://juice.lab:25429",
            "exit_code": 0,
            "raw_output": {"stdout": "80/tcp open http"},
        },
    )
    assert tool.status_code == 201, tool.text

    chain = client.post(
        "/api/v1/attack-chains",
        headers=red,
        json={"name": f"Task discovery {job_id[:8]}", "team": "red"},
    )
    assert chain.status_code == 201, chain.text
    cid = chain.json()["id"]
    step = client.post(
        f"/api/v1/attack-chains/{cid}/steps",
        headers=red,
        json={
            "stage": "recon",
            "sequence": 1,
            "title": "nmap_scan completed",
            "severity": "info",
            "category": "tools",
            "source_tool": "nmap_scan",
            "evidence": "80/tcp open http",
        },
    )
    assert step.status_code == 201, step.text

    patch_row = client.post(
        "/api/v1/patches",
        headers=red,
        json={
            "finding_id": fid,
            "title": "Restrict bind address and close unused ports",
            "playbook": "network-hardening",
            "asset_id": body["asset_id"],
        },
    )
    assert patch_row.status_code == 201, patch_row.text

    results = client.get(f"/api/v1/tasks/{task_id}/results", headers=headers)
    assert results.status_code == 200
    payload = results.json()
    assert len(payload["tools"]) == 1
    assert payload["tools"][0]["tool_name"] == "nmap_scan"
    assert payload["tools"][0]["started_at"]
    assert payload["tools"][0]["finished_at"]
    assert len(payload["findings"]) == 1
    assert len(payload["patches"]) == 1
    assert payload["chain"]
    assert payload["chain"]["steps"][0]["category"] == "tools"

    completed = client.patch(
        f"/api/v1/jobs/{job_id}",
        headers=red,
        json={"status": "completed"},
    )
    assert completed.status_code == 200, completed.text

    done = client.get(f"/api/v1/tasks/{task_id}", headers=headers)
    assert done.status_code == 200
    assert done.json()["status"] == "completed"


def _start_red_task(client, monkeypatch, headers):
    created = client.post(
        "/api/v1/tasks",
        headers=headers,
        json={
            "target": "http://juice.lab:25429",
            "description": "recon",
            "patch_scope": "none",
            "task_type": "red",
        },
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["id"]
    with patch("app.services.dispatch.dispatch_job", new_callable=AsyncMock) as disp:

        async def fake_dispatch(job, settings, task=None):
            return {**job, "status": "dispatched"}

        disp.side_effect = fake_dispatch
        started = client.patch(
            f"/api/v1/tasks/{task_id}",
            headers=headers,
            json={"action": "start"},
        )
    assert started.status_code == 200, started.text
    return started.json()


def test_progress_appends_and_lists_on_results(client, monkeypatch):
    mgr = uuid4()
    _auth(monkeypatch, mgr, "security_manager")
    headers = {"Authorization": "Bearer x"}
    task = _start_red_task(client, monkeypatch, headers)
    job_id = task["linked_job_id"]
    red = {"X-Service-Token": "change-me-red"}

    posted = client.post(
        f"/api/v1/jobs/{job_id}/progress",
        headers=red,
        json={
            "kind": "thinking",
            "message": "planning nmap",
            "meta": {"estimated_duration_seconds": 30},
        },
    )
    assert posted.status_code == 201, posted.text

    running = client.patch(
        f"/api/v1/jobs/{job_id}",
        headers=red,
        json={"status": "running"},
    )
    assert running.status_code == 200
    assert running.json()["started_at"]

    results = client.get(f"/api/v1/tasks/{task['id']}/results", headers=headers)
    assert results.status_code == 200
    payload = results.json()
    assert payload["progress"][0]["kind"] == "thinking"
    assert payload["progress"][0]["message"] == "planning nmap"
    assert payload["job"]["estimated_duration_seconds"] == 30
    assert payload["job"]["started_at"]


def test_stop_blocks_task_and_cancels_job(client, monkeypatch):
    mgr = uuid4()
    _auth(monkeypatch, mgr, "security_manager")
    headers = {"Authorization": "Bearer x"}
    task = _start_red_task(client, monkeypatch, headers)
    job_id = task["linked_job_id"]

    with patch("app.services.dispatch.cancel_worker_job", new_callable=AsyncMock) as cancel:
        stopped = client.patch(
            f"/api/v1/tasks/{task['id']}",
            headers=headers,
            json={"action": "stop"},
        )
    assert stopped.status_code == 200, stopped.text
    assert stopped.json()["status"] == "blocked"
    cancel.assert_called()

    job = client.get(f"/api/v1/jobs/{job_id}", headers=headers)
    assert job.status_code == 200
    assert job.json()["status"] == "cancelled"

    red = {"X-Service-Token": "change-me-red"}
    refused = client.post(
        f"/api/v1/jobs/{job_id}/progress",
        headers=red,
        json={"kind": "status", "message": "still going"},
    )
    assert refused.status_code == 409

    again = client.patch(
        f"/api/v1/tasks/{task['id']}",
        headers=headers,
        json={"action": "stop"},
    )
    assert again.status_code == 400
