def test_assets_require_auth(client):
    assert client.get("/api/v1/assets").status_code == 401


def test_assets_with_jwt(client, analyst_headers):
    r = client.get("/api/v1/assets", headers=analyst_headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_create_asset(client, analyst_headers):
    r = client.post(
        "/api/v1/assets",
        headers=analyst_headers,
        json={"name": "lab-host", "hostname": "lab.local", "ip_address": "10.0.0.1"},
    )
    assert r.status_code == 201
    assert r.json()["name"] == "lab-host"
