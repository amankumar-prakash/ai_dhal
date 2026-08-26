"""MCP client adapter — loads server config from mcp.json and connects via langchain_mcp_adapters."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools

from app.settings import WorkerSettings, get_settings

_MCP_CONFIG_PATH = Path(__file__).resolve().parent.parent / "mcp.json"
_HEXSTRIKE_MCP_FILENAME = "hexstrike_mcp.py"


def _repo_hexstrike_mcp_script() -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "hexstrike_server"
        / "hexstrike-ai"
        / _HEXSTRIKE_MCP_FILENAME
    )


def resolve_hexstrike_mcp_script(settings: WorkerSettings | None = None) -> Path:
    """Return the hexstrike_mcp.py path for stdio MCP transport."""
    settings = settings or get_settings()
    if settings.hexstrike_mcp_script.strip():
        path = Path(settings.hexstrike_mcp_script)
        if path.is_file():
            return path
        raise FileNotFoundError(f"HEXSTRIKE_MCP_SCRIPT not found: {path}")

    for candidate in (
        Path("/app/hexstrike/hexstrike_mcp.py"),
        _repo_hexstrike_mcp_script(),
    ):
        if candidate.is_file():
            return candidate

    raise FileNotFoundError(
        "hexstrike_mcp.py not found; set HEXSTRIKE_MCP_SCRIPT or mount/copy the script"
    )


def load_mcp_server_config(path: Path | None = None) -> dict[str, Any]:
    config_path = path or _MCP_CONFIG_PATH
    with config_path.open(encoding="utf-8") as fh:
        return json.load(fh)


def build_mcp_connections(settings: WorkerSettings | None = None) -> dict[str, dict[str, Any]]:
    """Translate mcp.json entries into MultiServerMCPClient connection specs."""
    settings = settings or get_settings()
    servers = load_mcp_server_config().get("mcpServers", {})
    connections: dict[str, dict[str, Any]] = {}

    for name, cfg in servers.items():
        if cfg.get("disabled"):
            continue

        args = list(cfg.get("args", []))
        for index, arg in enumerate(args):
            if _HEXSTRIKE_MCP_FILENAME in arg:
                args[index] = str(resolve_hexstrike_mcp_script(settings))
            elif arg == "--server" and index + 1 < len(args):
                args[index + 1] = settings.hexstrike_base_url.rstrip("/")

        connections[name] = {
            "command": sys.executable,
            "args": args,
            "transport": cfg.get("transport", "stdio"),
        }
        if url := cfg.get("url"):
            connections[name]["url"] = url

    if not connections:
        raise RuntimeError(f"No enabled MCP servers found in {_MCP_CONFIG_PATH}")

    return connections


def create_mcp_client(settings: WorkerSettings | None = None) -> MultiServerMCPClient:
    return MultiServerMCPClient(build_mcp_connections(settings))


async def list_tool_names(
    server_name: str = "hexstrike-ai",
    settings: WorkerSettings | None = None,
) -> list[str]:
    client = create_mcp_client(settings)
    async with client.session(server_name) as session:
        tools = await load_mcp_tools(session)
        return [tool.name for tool in tools]
