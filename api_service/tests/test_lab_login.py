from app.lab_users import lab_accounts


def test_lab_accounts_skip_redacted_placeholders(monkeypatch):
    monkeypatch.setenv("TEST_USERNAME", "[REDACTED_EMAIL_ADDRESS_1]")
    monkeypatch.setenv("TEST_PASSWORD", "testpassword")
    monkeypatch.setenv("TEST_MANAGER_USERNAME", "manager@example.com")
    monkeypatch.setenv("TEST_MANAGER_PASSWORD", "Manager1@1234")
    from app.config import get_settings

    get_settings.cache_clear()
    rows = lab_accounts(get_settings())
    emails = {r["email"] for r in rows}
    assert "manager@example.com" in emails
    assert not any("redacted" in e for e in emails)


def test_login_accepts_lab_admin(client, monkeypatch):
    monkeypatch.setenv("TEST_USERNAME", "admin@example.com")
    monkeypatch.setenv("TEST_PASSWORD", "testpassword")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-secret-at-least-32-chars-long!!")
    monkeypatch.setenv("API_STORE", "memory")
    from app.config import get_settings

    get_settings.cache_clear()
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "testpassword"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["role"] == "admin"
    assert body["access_token"]

    me = client.get("/api/v1/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["role"] == "admin"


def test_login_rejects_unknown_password(client, monkeypatch):
    monkeypatch.setenv("TEST_USERNAME", "admin@example.com")
    monkeypatch.setenv("TEST_PASSWORD", "testpassword")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-secret-at-least-32-chars-long!!")
    from app.config import get_settings

    get_settings.cache_clear()
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "wrong-password"},
    )
    assert r.status_code == 401
