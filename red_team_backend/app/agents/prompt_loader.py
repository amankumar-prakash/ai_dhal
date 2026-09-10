"""Load phase/tool markdown prompts from app/agents/prompts/."""
from __future__ import annotations

from pathlib import Path

_PROMPTS_ROOT = Path(__file__).resolve().parent / "prompts"


def prompts_root() -> Path:
    return _PROMPTS_ROOT


def load_prompt(relative: str) -> str:
    """Load a prompt file. `relative` like `phases/surface/tools/nmap_scan` (with or without .md)."""
    rel = relative[:-3] if relative.endswith(".md") else relative
    path = _PROMPTS_ROOT / f"{rel}.md"
    if not path.is_file():
        raise FileNotFoundError(f"Prompt not found: {path}")
    return path.read_text(encoding="utf-8")


def parse_prompt_sections(text: str) -> dict[str, str]:
    """Split markdown on ## System / ## User / ## Notes headings."""
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        if line.startswith("## "):
            current = line[3:].strip().lower()
            sections.setdefault(current, [])
            continue
        if current is None:
            current = "body"
            sections.setdefault(current, [])
        sections[current].append(line)
    return {k: "\n".join(v).strip() for k, v in sections.items()}


def build_system_prompt(relative: str, *, include_shared: bool = True) -> str:
    """Compose shared lab authorization + agent system section."""
    parts: list[str] = []
    if include_shared:
        shared = load_prompt("_shared/lab_authorization")
        shared_sections = parse_prompt_sections(shared)
        parts.append(shared_sections.get("system") or shared_sections.get("body") or shared)
        contracts = load_prompt("_shared/output_contracts")
        contract_sections = parse_prompt_sections(contracts)
        parts.append(contract_sections.get("system") or contract_sections.get("body") or contracts)
    agent = load_prompt(relative)
    agent_sections = parse_prompt_sections(agent)
    parts.append(agent_sections.get("system") or agent_sections.get("body") or agent)
    return "\n\n".join(p for p in parts if p.strip())


def render_user_prompt(relative: str, **placeholders: str) -> str:
    """Return the ## User section with `{key}` placeholders substituted."""
    agent = load_prompt(relative)
    sections = parse_prompt_sections(agent)
    user = sections.get("user") or ""
    for key, value in placeholders.items():
        user = user.replace("{" + key + "}", value)
    return user
