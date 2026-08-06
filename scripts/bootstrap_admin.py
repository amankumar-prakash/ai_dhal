#!/usr/bin/env python3
"""Out-of-band first Admin bootstrap from root .env TEST_USERNAME / TEST_PASSWORD.

Usage (from repo root):
  python scripts/bootstrap_admin.py

Requires: SUPABASE_URL, SUPABASE_SECRET_KEY (or SUPABASE_SERVICE_ROLE_KEY),
TEST_USERNAME, TEST_PASSWORD.
Creates/confirms Auth user, upserts profiles (active, must_change_password=false),
upserts user_roles.admin. Safe to re-run for zero-Admin recovery.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_dotenv(path: Path) -> None:
    """Load root .env, overriding shell exports (lab shells often have stale SUPABASE_URL)."""
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip().strip('"').strip("'")
        os.environ[k] = v


def main() -> int:
    _load_dotenv(ROOT / ".env")
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SECRET_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    email = os.environ.get("TEST_USERNAME", "").strip()
    password = os.environ.get("TEST_PASSWORD", "").strip()
    if not url or not key:
        print("ERROR: SUPABASE_URL and SUPABASE_SECRET_KEY required", file=sys.stderr)
        return 1
    if not email or not password:
        print("ERROR: TEST_USERNAME and TEST_PASSWORD required", file=sys.stderr)
        return 1

    from supabase import create_client

    sb = create_client(url, key)

    # Find or create user
    user_id: str | None = None
    try:
        listed = sb.auth.admin.list_users()
        users = getattr(listed, "users", None) or listed
        if isinstance(users, list):
            for u in users:
                uemail = getattr(u, "email", None) or (u.get("email") if isinstance(u, dict) else None)
                uid = getattr(u, "id", None) or (u.get("id") if isinstance(u, dict) else None)
                if uemail and uemail.lower() == email.lower():
                    user_id = str(uid)
                    break
    except Exception as exc:  # noqa: BLE001
        print(f"WARN list_users: {exc}")

    if user_id:
        sb.auth.admin.update_user_by_id(
            user_id,
            {"password": password, "email_confirm": True},
        )
        print(f"Updated Auth user {email} ({user_id})")
    else:
        created = sb.auth.admin.create_user(
            {
                "email": email,
                "password": password,
                "email_confirm": True,
                "user_metadata": {"display_name": "Lab Admin"},
            }
        )
        user = created.user
        if not user:
            print("ERROR: create_user returned no user", file=sys.stderr)
            return 1
        user_id = str(user.id)
        print(f"Created Auth user {email} ({user_id})")

    # Profile upsert
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    profile = {
        "id": user_id,
        "email": email,
        "display_name": "Lab Admin",
        "status": "active",
        "must_change_password": False,
        "invite_expires_at": None,
        "invite_consumed_at": now,
        "updated_at": now,
    }
    existing = sb.table("profiles").select("id").eq("id", user_id).limit(1).execute()
    if existing.data:
        sb.table("profiles").update(profile).eq("id", user_id).execute()
    else:
        profile["created_at"] = now
        sb.table("profiles").insert(profile).execute()
    print("Upserted profiles (active, must_change_password=false)")

    # Role: replace any existing with admin
    roles = sb.table("user_roles").select("id").eq("user_id", user_id).execute()
    for row in roles.data or []:
        sb.table("user_roles").delete().eq("id", row["id"]).execute()
    sb.table("user_roles").insert({"user_id": user_id, "role": "admin"}).execute()
    print("Upserted user_roles → admin")
    print("OK: bootstrap complete. Sign in with TEST_USERNAME / TEST_PASSWORD.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
