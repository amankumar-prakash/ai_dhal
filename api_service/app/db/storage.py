"""Optional Supabase Storage helper — unused until evidence upload is scheduled."""
from __future__ import annotations

from typing import Any

from app.db.supabase_client import get_supabase


def upload_bytes(bucket: str, path: str, data: bytes, content_type: str = "application/octet-stream") -> dict[str, Any]:
    sb = get_supabase()
    sb.storage.from_(bucket).upload(path, data, file_options={"content-type": content_type})
    return {"bucket": bucket, "path": path}


def create_signed_url(bucket: str, path: str, expires_in: int = 3600) -> str:
    sb = get_supabase()
    resp = sb.storage.from_(bucket).create_signed_url(path, expires_in)
    return resp.get("signedURL") or resp.get("signedUrl") or ""
