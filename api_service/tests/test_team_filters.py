def test_team_filters(client, analyst_headers, red_headers, blue_headers):
    client.post(
        "/api/v1/findings",
        headers=red_headers,
        json={"title": "r", "severity": "low", "team": "red"},
    )
    client.post(
        "/api/v1/findings",
        headers=blue_headers,
        json={"title": "b", "severity": "low", "team": "blue"},
    )
    red = client.get("/api/v1/findings?team=red", headers=analyst_headers).json()
    blue = client.get("/api/v1/findings?team=blue", headers=analyst_headers).json()
    assert all(f.get("team") == "red" for f in red)
    assert all(f.get("team") == "blue" for f in blue)
    assert len(red) >= 1 and len(blue) >= 1
