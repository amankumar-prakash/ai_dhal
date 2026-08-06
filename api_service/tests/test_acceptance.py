from unittest.mock import AsyncMock, patch


def test_cancel_terminal_409(client, analyst_headers):
    a = client.post(
        "/api/v1/assets",
        headers=analyst_headers,
        json={"name": "c", "hostname": "c.local"},
    ).json()
    with patch("app.routers.jobs.dispatch_job", new_callable=AsyncMock) as disp:
        disp.side_effect = lambda job, settings: {**job, "status": "dispatched"}
        job = client.post(
            "/api/v1/jobs",
            headers=analyst_headers,
            json={"team": "red", "profile": "surface-recon", "asset_ids": [a["id"]]},
        ).json()
    client.post(f"/api/v1/jobs/{job['id']}/cancel", headers=analyst_headers)
    r = client.post(f"/api/v1/jobs/{job['id']}/cancel", headers=analyst_headers)
    assert r.status_code == 409


def test_health(client):
    assert client.get("/api/v1/health").status_code == 200


def test_compose_health_paths(client):
    assert client.get("/api/v1/ready").json()["status"] == "ready"
