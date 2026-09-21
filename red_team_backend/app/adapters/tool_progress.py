"""Approximate tool-run progress for red-team chat.

Wordlist tools: percent from elapsed * assumed RPS / list size.
Everything else: elapsed / a per-tool duration guess.
HexStrike's own process fraction is ignored when it is 0 or the stuck-at-50%
placeholder (COMMAND_TIMEOUT=0).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

ProgressMode = Literal["wordlist", "guess"]

# Conservative requests/sec by tool family when a list size is known.
_RPS_BY_FAMILY: dict[str, float] = {
    "gobuster": 80.0,
    "ffuf": 80.0,
    "feroxbuster": 60.0,
    "dirb": 40.0,
    "dirsearch": 50.0,
    "wfuzz": 40.0,
    "arjun": 30.0,
    "x8": 30.0,
    "hydra": 16.0,
    "john": 50.0,
    "hashcat": 80.0,
}

# Seconds to 95% when there is no countable list.
_DURATION_GUESS_SEC: dict[str, float] = {
    "nuclei": 180.0,
    "katana": 120.0,
    "nmap": 90.0,
    "amass": 120.0,
    "gobuster": 90.0,
    "feroxbuster": 90.0,
    "ffuf": 90.0,
    "dirb": 90.0,
    "dirsearch": 90.0,
    "hydra": 120.0,
    "httpx": 30.0,
    "whatweb": 20.0,
    "subfinder": 45.0,
    "hakrawler": 60.0,
}

_DEFAULT_RPS = 40.0
_DEFAULT_DURATION_SEC = 60.0

# Longer needles first so "directory-list-2.3-medium.txt" wins over "medium.txt".
_WORDLIST_SIZES: tuple[tuple[str, int], ...] = (
    ("directory-list-2.3-medium.txt", 220_560),
    ("directory-list-2.3-small.txt", 87_664),
    ("directory-list-2.3-big.txt", 1_273_829),
    ("raft-large-words.txt", 119_609),
    ("raft-medium-words.txt", 63_088),
    ("raft-small-words.txt", 43_081),
    ("rockyou.txt", 14_344_391),
    ("dirb/big.txt", 20_469),
    ("dirb/common.txt", 4_614),
    ("dirbuster/directory-list-2.3-medium.txt", 220_560),
    ("big.txt", 20_469),
    ("common.txt", 4_614),
)

_FAMILY_PREFIXES: tuple[str, ...] = (
    "feroxbuster",
    "gobuster",
    "dirsearch",
    "dirb",
    "ffuf",
    "wfuzz",
    "hydra",
    "hashcat",
    "nuclei",
    "katana",
    "subfinder",
    "hakrawler",
    "whatweb",
    "httpx",
    "amass",
    "nmap",
    "john",
    "arjun",
    "x8",
)

_W_FLAG_RE = re.compile(r"(?:^|\s)-w(?:\s+|=)(\S+)", re.I)

_LIST_KEYS = ("wordlist", "w", "username_file", "password_file", "userlist", "passlist")


@dataclass(frozen=True)
class ProgressEstimate:
    progress_pct: int
    mode: ProgressMode
    list_total: int | None = None

    def as_args(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "progress_pct": self.progress_pct,
            "mode": self.mode,
        }
        if self.list_total is not None:
            payload["list_total"] = self.list_total
        return payload


def tool_family(tool: str) -> str:
    n = (tool or "").lower().replace("-", "_")
    for prefix in _FAMILY_PREFIXES:
        if n == prefix or n.startswith(prefix + "_") or prefix in n.split("_"):
            return prefix
        if prefix in n.replace("_", ""):
            return prefix
    return n.split("_")[0] if n else "tool"


def estimate_progress(
    tool: str,
    args: dict[str, Any] | None,
    elapsed_sec: float,
    *,
    done: bool = False,
    prev_pct: int = 0,
    hexstrike_fraction: float | None = None,
) -> ProgressEstimate:
    """Return a 1–95 (running) or 100 (done) percent that never decreases."""
    if done:
        total, _mode = _list_total(tool, args)
        return ProgressEstimate(progress_pct=100, mode=_mode, list_total=total)

    elapsed = max(0.0, float(elapsed_sec))
    total, mode = _list_total(tool, args)
    family = tool_family(tool)

    if total and total > 0:
        rps = _RPS_BY_FAMILY.get(family, _DEFAULT_RPS)
        raw = (elapsed * rps / total) * 100.0
        mode = "wordlist"
    else:
        duration = _DURATION_GUESS_SEC.get(family, _DEFAULT_DURATION_SEC)
        raw = (elapsed / duration) * 100.0 if duration > 0 else 0.0
        mode = "guess"
        total = None

    pct = int(raw)
    hs = _usable_hexstrike_pct(hexstrike_fraction)
    if hs is not None:
        pct = max(pct, hs)
    pct = max(prev_pct, pct)
    pct = min(95, max(1, pct))
    return ProgressEstimate(progress_pct=pct, mode=mode, list_total=total)


def _usable_hexstrike_pct(fraction: float | None) -> int | None:
    if fraction is None:
        return None
    try:
        frac = float(fraction)
    except (TypeError, ValueError):
        return None
    if frac <= 0:
        return None
    # Default COMMAND_TIMEOUT=0 parks HexStrike progress at 0.5 forever.
    if abs(frac - 0.5) < 0.01:
        return None
    return min(95, max(1, int(round(frac * 100))))


def _list_total(tool: str, args: dict[str, Any] | None) -> tuple[int | None, ProgressMode]:
    kwargs = args if isinstance(args, dict) else {}
    family = tool_family(tool)

    user_n = _count_list(kwargs.get("username_file") or kwargs.get("userlist"))
    pass_n = _count_list(kwargs.get("password_file") or kwargs.get("passlist"))
    if kwargs.get("username") or kwargs.get("login"):
        user_n = user_n or 1
    if kwargs.get("password"):
        pass_n = pass_n or 1
    if family == "hydra" or (user_n and pass_n):
        if user_n and pass_n:
            return user_n * pass_n, "wordlist"

    paths = _wordlist_paths(kwargs)
    for path in paths:
        n = _count_list(path)
        if n:
            return n, "wordlist"
    return None, "guess"


def _wordlist_paths(kwargs: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for key in _LIST_KEYS:
        val = kwargs.get(key)
        if isinstance(val, str) and val.strip():
            found.append(val.strip())
    extra = kwargs.get("additional_args") or kwargs.get("extra_args") or kwargs.get("args") or ""
    if isinstance(extra, str):
        for m in _W_FLAG_RE.finditer(extra):
            found.append(m.group(1).strip("\"'"))
    return found


def _count_list(path: Any) -> int | None:
    if not isinstance(path, str) or not path.strip():
        return None
    raw = path.strip()
    local = Path(raw)
    if local.is_file():
        try:
            with local.open("rb") as fh:
                return max(1, sum(1 for _ in fh))
        except OSError:
            pass
    lowered = raw.replace("\\", "/").lower()
    best: tuple[int, int] | None = None  # (needle_len, size)
    for needle, size in _WORDLIST_SIZES:
        if needle in lowered:
            nlen = len(needle)
            if best is None or nlen > best[0]:
                best = (nlen, size)
    return best[1] if best else None
