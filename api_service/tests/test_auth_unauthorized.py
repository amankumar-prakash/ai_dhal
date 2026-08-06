def test_assets_require_auth(client):
    assert client.get("/api/v1/assets").status_code == 401
