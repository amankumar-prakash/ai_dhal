from unittest.mock import AsyncMock, patch


def test_patch_applied_remediates_finding(client, analyst_headers, blue_headers):
    f = client.post(
        "/api/v1/findings",
        headers=blue_headers,
        json={"title": "vuln", "severity": "high", "team": "blue", "status": "open"},
    ).json()
    p = client.post(
        "/api/v1/patches",
        headers=blue_headers,
        json={"finding_id": f["id"], "title": "Upgrade", "playbook": "upgrade-package"},
    ).json()
    r = client.patch(
        f"/api/v1/patches/{p['id']}",
        headers=analyst_headers,
        json={"status": "applied"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "applied"
    findings = client.get("/api/v1/findings", headers=analyst_headers).json()
    match = next(x for x in findings if x["id"] == f["id"])
    assert match["status"] == "remediated"


def test_patch_failed_keeps_finding_open(client, analyst_headers, blue_headers):
    f = client.post(
        "/api/v1/findings",
        headers=blue_headers,
        json={"title": "vuln2", "severity": "high", "team": "blue", "status": "open"},
    ).json()
    p = client.post(
        "/api/v1/patches",
        headers=blue_headers,
        json={"finding_id": f["id"], "title": "Upgrade", "playbook": "upgrade-package"},
    ).json()
    client.patch(f"/api/v1/patches/{p['id']}", headers=analyst_headers, json={"status": "failed"})
    findings = client.get("/api/v1/findings", headers=analyst_headers).json()
    match = next(x for x in findings if x["id"] == f["id"])
    assert match["status"] == "open"
