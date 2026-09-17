"""Application-wide magic-string constants.

Centralising these avoids silent typos when the same string is
referenced in routers, services, and tests.
"""
from __future__ import annotations

# ── Job / Scan profiles ───────────────────────────────────────────────────────
PROFILE_TASK_DISCOVERY = "task-discovery"

# ── Tool-run names (used in results assembly) ─────────────────────────────────
TOOL_SCAN_REPORT = "scan_report"

# ── Task / job terminal states ────────────────────────────────────────────────
TERMINAL_JOB_STATUSES = frozenset({"completed", "failed", "cancelled"})
TERMINAL_TASK_STATUSES = frozenset({"completed", "reviewed", "closed"})
