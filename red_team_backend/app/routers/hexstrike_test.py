"""HexStrike MCP + LangChain agent test routes."""
from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, HTTPException
from langchain.agents import create_agent
from langchain_mcp_adapters.tools import load_mcp_tools
from pydantic import BaseModel, Field

from app.adapters.mcp_client import create_mcp_client
from app.settings import get_settings

router = APIRouter(tags=["hexstrike-test"])

_DEFAULT_SERVER = "hexstrike-ai"


class TestHexstrikeBody(BaseModel):
    message: str = Field(
        default="Call server_health and summarize the HexStrike server status.",
        min_length=1,
    )
    server: str = _DEFAULT_SERVER


def _ensure_openai_env() -> None:
    settings = get_settings()
    settings.require_llm_for_live()
    if settings.openai_api_key:
        os.environ.setdefault("OPENAI_API_KEY", settings.openai_api_key)


def _extract_agent_text(result: Any) -> str:
    messages = result.get("messages") if isinstance(result, dict) else None
    if not messages:
        return str(result)
    last = messages[-1]
    content = getattr(last, "content", None)
    if content is not None:
        return str(content)
    if isinstance(last, dict):
        return str(last.get("content", last))
    return str(last)


@router.post("/test_hexstrike")
async def test_hexstrike(body: TestHexstrikeBody) -> dict[str, Any]:
    """Run a one-shot LangChain agent against HexStrike MCP tools."""
    settings = get_settings()

    if settings.stub_llm:
        return {
            "mode": "stub",
            "server": body.server,
            "message": body.message,
            "response": (
                f"[stub-llm:{settings.llm_model}] Would invoke HexStrike MCP with: "
                f"{body.message[:200]}"
            ),
        }

    _ensure_openai_env()
    model = f"openai:{settings.llm_model}"
    client = create_mcp_client(settings)

    try:
        async with client.session(body.server) as session:
            tools = await load_mcp_tools(session)
            agent = create_agent(model, tools)
            result = await agent.ainvoke(
                {"messages": [{"role": "user", "content": body.message}]}
            )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"MCP server not found: {body.server}") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"HexStrike MCP agent failed: {exc}") from exc

    return {
        "mode": "live",
        "server": body.server,
        "model": settings.llm_model,
        "message": body.message,
        "tool_count": len(tools),
        "response": _extract_agent_text(result),
    }
