"""Target allowlist + demo-safe guardrails."""
from __future__ import annotations


def in_allowlist(host: str, allowlist: str) -> bool:
    if not allowlist.strip():
        return True
    patterns = [p.strip() for p in allowlist.split(",") if p.strip()]
    return any(p in host or host.endswith(p) for p in patterns)


def demo_blocks_profile(profile: str, demo_safe_mode: str) -> bool:
    if demo_safe_mode.strip() not in {"1", "true", "True", "yes"}:
        return False
    return "exploit" in (profile or "")
