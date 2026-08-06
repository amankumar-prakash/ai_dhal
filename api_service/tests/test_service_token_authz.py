def test_service_cannot_delete_asset(client, red_headers, analyst_headers):
    a = client.post(
        "/api/v1/assets",
        headers=analyst_headers,
        json={"name": "x", "hostname": "x.local"},
    ).json()
    r = client.delete(f"/api/v1/assets/{a['id']}", headers=red_headers)
    assert r.status_code in (401, 403)


def test_service_can_post_finding(client, red_headers):
    r = client.post(
        "/api/v1/findings",
        headers=red_headers,
        json={"title": "open port", "severity": "medium", "team": "red"},
    )
    assert r.status_code == 201


def test_service_cannot_assign_role(client, red_headers):
    r = client.post(
        "/api/v1/roles",
        headers=red_headers,
        json={"user_id": "11111111-1111-1111-1111-111111111111", "role": "admin"},
    )
    assert r.status_code in (401, 403)
