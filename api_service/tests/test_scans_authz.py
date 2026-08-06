def test_analyst_cannot_delete_scan(client, analyst_headers):
    a = client.post(
        "/api/v1/assets",
        headers=analyst_headers,
        json={"name": "t", "hostname": "t.local"},
    ).json()
    scan = client.post(
        "/api/v1/scans",
        headers=analyst_headers,
        json={"target": "t.local", "profile": "surface-recon", "asset_id": a["id"], "team": "red"},
    ).json()
    r = client.delete(f"/api/v1/scans/{scan['id']}", headers=analyst_headers)
    assert r.status_code == 403


def test_admin_can_delete_scan(client, admin_headers, analyst_headers):
    a = client.post(
        "/api/v1/assets",
        headers=analyst_headers,
        json={"name": "t2", "hostname": "t2.local"},
    ).json()
    scan = client.post(
        "/api/v1/scans",
        headers=analyst_headers,
        json={"target": "t2.local", "profile": "surface-recon", "asset_id": a["id"], "team": "red"},
    ).json()
    r = client.delete(f"/api/v1/scans/{scan['id']}", headers=admin_headers)
    assert r.status_code == 204
