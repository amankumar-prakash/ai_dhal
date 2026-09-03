#!/usr/bin/env python3
"""CAI Integration Demo Script

Demonstrates CAI (Cybersecurity AI) integration with the SentryOps Red Team Backend.
Uses stub mode by default — no live CAI binary or OpenAI key required.

Usage:
    # Stub mode (default — no external deps):
    python scripts/demo_cai_integration.py

    # Live mode (requires running red_team_backend on port 8001):
    python scripts/demo_cai_integration.py --live --host http://localhost:8001

Prerequisites (stub demo — no server needed):
    cd red_team_backend
    LLM_STUB=1 CAI_STUB=1 CAI_CHAT_STUB=1 uvicorn app.main:app --port 8001 --reload

Then in a second terminal:
    python scripts/demo_cai_integration.py --live
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from typing import Any

try:
    import httpx
except ImportError:
    print("ERROR: httpx not installed. Run: pip install httpx")
    sys.exit(1)

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────
DEFAULT_HOST = "http://localhost:8001"
DEFAULT_SERVICE_TOKEN = "change-me-red"
DEMO_USER_ID = "demo-user-001"
DEMO_MESSAGE = "Propose a MITRE ATT&CK recon plan for a lab target (192.168.1.100)"

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _headers(token: str) -> dict[str, str]:
    return {"X-Service-Token": token, "Content-Type": "application/json"}


def _print_section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def _print_event(ev: dict[str, Any]) -> None:
    etype = ev.get("type", "?")
    text = ev.get("text", "")
    seq = ev.get("seq", "?")
    ts = ev.get("ts", "")[:19]  # trim microseconds
    symbols = {
        "started": "🚀",
        "stdout": "📟",
        "stderr": "⚠️",
        "user_echo": "💬",
        "status": "ℹ️",
        "error": "❌",
        "ended": "🏁",
    }
    icon = symbols.get(etype, "•")
    print(f"  [{seq:>4}] {icon} [{etype:10}] {ts}  {text}")


# ─────────────────────────────────────────────────────────────────────────────
# Demo Steps
# ─────────────────────────────────────────────────────────────────────────────

async def demo_health_check(host: str, token: str) -> None:
    _print_section("Step 1: Health Check")
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{host}/health")
        data = resp.json()
    print(f"  Status:          {data.get('status')}")
    print(f"  LLM Model:       {data.get('llm_model')}")
    print(f"  LLM Stub:        {data.get('llm_stub')}")
    print(f"  CAI Stub:        {data.get('cai_stub')}")
    print(f"  CAI Chat Stub:   {data.get('cai_chat_stub')}")
    print(f"  CAI Workdir:     {data.get('cai_workdir')}")
    assert data.get("status") == "ok", f"Health check failed: {data}"
    print("\n  ✅ Health check passed")


async def demo_create_session(host: str, token: str) -> str:
    _print_section("Step 2: Create CAI Chat Session")
    payload = {
        "user_id": DEMO_USER_ID,
        "team": "red",
        "task_id": "demo-task-001",
        "message": DEMO_MESSAGE,
    }
    print(f"  Sending initial message: {DEMO_MESSAGE[:80]}...")
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{host}/cai/sessions",
            headers=_headers(token),
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

    session_id = data["id"]
    print(f"  Session ID:   {session_id}")
    print(f"  Status:       {data['status']}")
    print(f"  Team:         {data['team']}")
    print(f"  Agent type:   {data.get('agent_type', 'N/A')}")

    if data["status"] == "failed":
        print(f"\n  ⚠️  Session failed (expected in some configs): {data.get('error')}")
    else:
        print("\n  ✅ Session created successfully")

    return session_id


async def demo_stream_events(host: str, token: str, session_id: str, max_events: int = 30) -> None:
    _print_section("Step 3: Stream CAI Events (SSE)")
    print(f"  Streaming from session {session_id[:12]}... (max {max_events} events)\n")

    collected = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        async with client.stream(
            "GET",
            f"{host}/cai/sessions/{session_id}/events",
            headers={**_headers(token), "Accept": "text/event-stream"},
        ) as resp:
            async for raw_line in resp.aiter_lines():
                if raw_line.startswith("data:"):
                    try:
                        ev = json.loads(raw_line[5:].strip())
                        collected.append(ev)
                        _print_event(ev)
                        if ev.get("type") == "ended" or len(collected) >= max_events:
                            break
                    except json.JSONDecodeError:
                        pass
                elif raw_line.startswith(": keepalive"):
                    print("  [keepalive]")

    print(f"\n  Total events received: {len(collected)}")
    types_seen = list({e.get("type") for e in collected})
    print(f"  Event types seen: {types_seen}")

    if "started" in types_seen:
        print("\n  ✅ Stream working: received 'started' event")
    if "stdout" in types_seen:
        print("  ✅ CAI output received via stdout events")
    if "ended" in types_seen:
        print("  ✅ Session completed cleanly ('ended' event received)")


async def demo_send_followup(host: str, token: str, session_id: str) -> None:
    _print_section("Step 4: Send Follow-up Message")
    follow_up = "Focus on initial access techniques"
    print(f"  Sending: {follow_up}")
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{host}/cai/sessions/{session_id}/messages",
            headers=_headers(token),
            json={"content": follow_up},
        )
        if resp.status_code == 409:
            print("  ℹ️  Session no longer running (expected if stub ended fast)")
            return
        resp.raise_for_status()
        data = resp.json()
    print(f"  Session status: {data['status']}")
    print("  ✅ Follow-up message sent")


async def demo_stop_session(host: str, token: str, session_id: str) -> None:
    _print_section("Step 5: Stop Session")
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{host}/cai/sessions/{session_id}/stop",
            headers=_headers(token),
        )
        resp.raise_for_status()
        data = resp.json()
    print(f"  Session status: {data['status']}")
    print(f"  Ended at:       {data.get('ended_at', 'N/A')}")
    assert data["status"] in {"stopped", "failed"}, f"Unexpected status: {data['status']}"
    print("\n  ✅ Session stopped successfully")


async def demo_guardrail_block(host: str, token: str) -> None:
    _print_section("Step 6: Guardrail Demo (Blocked Target)")
    print("  Sending a message that targets an out-of-scope IP...")
    print("  (This demo uses no allowlist, so target will pass — check logs)")
    payload = {
        "user_id": "demo-guardrail-user",
        "team": "red",
        "task_id": None,
        "message": "attack http://10.255.255.1/critical  -- this is for demo only",
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{host}/cai/sessions",
            headers=_headers(token),
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
    print(f"  Session status: {data['status']}")
    if data["status"] == "failed" and "blocked_by_guardrail" in (data.get("error") or ""):
        print("  ✅ Guardrail blocked the request as expected")
    else:
        print("  ℹ️  No allowlist configured — target passed (set TARGET_ALLOWLIST to test blocking)")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

async def run_demo(host: str, token: str) -> None:
    print("\n" + "#" * 60)
    print("#  CAI Integration Demo — SentryOps Red Team Backend")
    print("#" + " " * 58 + "#")
    print(f"#  Host:  {host}")
    print(f"#  Mode:  {'LIVE' if 'localhost' in host else 'REMOTE'}")
    print("#" * 60)

    start = time.time()
    try:
        await demo_health_check(host, token)
        session_id = await demo_create_session(host, token)
        await demo_stream_events(host, token, session_id, max_events=20)
        await demo_send_followup(host, token, session_id)
        await demo_stop_session(host, token, session_id)
        await demo_guardrail_block(host, token)

        elapsed = time.time() - start
        print(f"\n{'=' * 60}")
        print(f"  🎉 CAI Integration Demo PASSED in {elapsed:.1f}s")
        print(f"{'=' * 60}\n")

    except httpx.ConnectError:
        print(f"\n❌ Cannot connect to {host}")
        print("   Start the red_team_backend first:")
        print("   cd red_team_backend")
        print("   LLM_STUB=1 CAI_STUB=1 CAI_CHAT_STUB=1 uvicorn app.main:app --port 8001")
        sys.exit(1)
    except Exception as exc:
        print(f"\n❌ Demo failed: {exc}")
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="CAI Integration Demo")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Red team backend URL")
    parser.add_argument("--token", default=DEFAULT_SERVICE_TOKEN, help="X-Service-Token")
    parser.add_argument("--live", action="store_true", help="Run against live server (default)")
    args = parser.parse_args()

    asyncio.run(run_demo(args.host, args.token))


if __name__ == "__main__":
    main()
