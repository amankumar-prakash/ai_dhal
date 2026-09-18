from unittest.mock import AsyncMock, patch


def test_job_rejects_empty_assets(client, analyst_headers):
    r = client.post(
        "/api/v1/jobs",
        headers=analyst_headers,
        json={"team": "red", "profile": "surface-recon", "asset_ids": []},
    )
    assert r.status_code == 422


def test_job_create_dispatches(client, analyst_headers):
    a = client.post(
        "/api/v1/assets",
        headers=analyst_headers,
        json={"name": "j", "hostname": "j.local"},
    ).json()
    with patch("app.routers.jobs.dispatch_job", new_callable=AsyncMock) as disp:
        disp.side_effect = lambda job, settings: {**job, "status": "dispatched"}
        r = client.post(
            "/api/v1/jobs",
            headers=analyst_headers,
            json={"team": "red", "profile": "surface-recon", "asset_ids": [a["id"]]},
        )
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "dispatched"
    assert a["id"] in [str(x) for x in body["asset_ids"]] or a["id"] in body["asset_ids"]
    scans = client.get("/api/v1/scans", headers=analyst_headers).json()
    assert any(s.get("job_id") == body["id"] for s in scans)


def test_job_rejects_missing_asset_and_target(client, analyst_headers):
    r = client.post(
        "/api/v1/jobs",
        headers=analyst_headers,
        json={"team": "red", "profile": "surface-recon"},
    )
    assert r.status_code == 422


def test_job_create_from_typed_target(client, analyst_headers):
    with patch("app.routers.jobs.dispatch_job", new_callable=AsyncMock) as disp:
        disp.side_effect = lambda job, settings: {**job, "status": "dispatched"}
        r = client.post(
            "/api/v1/jobs",
            headers=analyst_headers,
            json={"team": "red", "profile": "surface-recon", "target": "10.0.0.5"},
        )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "dispatched"
    assert len(body["asset_ids"]) == 1
    assets = client.get("/api/v1/assets", headers=analyst_headers).json()
    assert any(a.get("hostname") == "10.0.0.5" for a in assets)


def test_typed_target_reuses_asset(client, analyst_headers):
    with patch("app.routers.jobs.dispatch_job", new_callable=AsyncMock) as disp:
        disp.side_effect = lambda job, settings: {**job, "status": "dispatched"}
        first = client.post(
            "/api/v1/jobs",
            headers=analyst_headers,
            json={"team": "red", "profile": "surface-recon", "target": "10.0.0.9"},
        ).json()
        second = client.post(
            "/api/v1/jobs",
            headers=analyst_headers,
            json={"team": "red", "profile": "surface-recon", "target": "10.0.0.9"},
        ).json()
    assert first["asset_ids"] == second["asset_ids"]
    assets = client.get("/api/v1/assets", headers=analyst_headers).json()
    assert sum(1 for a in assets if a.get("hostname") == "10.0.0.9") == 1
