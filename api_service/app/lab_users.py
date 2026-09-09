"""Local lab accounts used when Supabase Auth is unreachable."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import NAMESPACE_DNS, UUID, uuid4, uuid5

from app.config import Settings, get_settings
from app.db.store import get_store
from app.services import identity


def _usable_email(email: str) -> bool:
    value = (email or "").strip()
    if not value or "@" not in value:
        return False
    if "REDACTED" in value.upper() or value.startswith("["):
        return False
    return True


def lab_accounts(settings: Settings | None = None) -> list[dict[str, str]]:
    settings = settings or get_settings()
    rows: list[dict[str, str]] = []
    if _usable_email(settings.test_manager_username) and settings.test_manager_password:
        rows.append(
            {
                "email": settings.test_manager_username.strip().lower(),
                "password": settings.test_manager_password,
                "role": "security_manager",
                "display_name": "Lab Manager",
            }
        )
    if _usable_email(settings.test_username) and settings.test_password:
        rows.append(
            {
                "email": settings.test_username.strip().lower(),
                "password": settings.test_password,
                "role": "admin",
                "display_name": "Lab Admin",
            }
        )
    return rows


def user_id_for_email(email: str) -> UUID:
    return uuid5(NAMESPACE_DNS, email.strip().lower())


def seed_lab_identities() -> None:
    settings = get_settings()
    if (settings.api_store or "").lower() != "memory":
        return
    store = get_store()
    now = datetime.now(timezone.utc)
    for acct in lab_accounts(settings):
        uid = user_id_for_email(acct["email"])
        identity.upsert_profile(
            uid,
            {
                "email": acct["email"],
                "display_name": acct["display_name"],
                "status": "active",
                "must_change_password": False,
                "invite_expires_at": None,
                "invite_consumed_at": now,
            },
        )
        existing_roles = [
            r for r in store.list_all("roles") if str(r.get("user_id")) == str(uid)
        ]
        if not existing_roles:
            store.create("roles", {"id": uuid4(), "user_id": uid, "role": acct["role"]})


def find_lab_account(email: str, password: str, settings: Settings | None = None) -> dict[str, Any] | None:
    from hmac import compare_digest

    want = email.strip().lower()
    for acct in lab_accounts(settings):
        if acct["email"] == want and compare_digest(acct["password"], password):
            return acct
    return None
