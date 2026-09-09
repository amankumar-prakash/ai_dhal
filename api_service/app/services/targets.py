"""Parse task targets into hostname, URL, and allowlist entries."""
from __future__ import annotations

import os
from urllib.parse import urlparse


def parse_target(target: str) -> dict[str, str | list[str] | int | None]:
    raw = (target or "").strip()
    if not raw:
        return {"hostname": "unknown", "url": "", "allowlist": [], "port": None}

    url = raw if "://" in raw else f"http://{raw}"
    try:
        parsed = urlparse(url)
        host = parsed.hostname or ""
        port = parsed.port
    except ValueError:
        host = ""
        port = None
        parsed = None

    if not host:
        host = raw.split("/")[0]
        if "@" in host:
            host = host.split("@")[-1]
        host = host.split(":")[0] or raw

    allowlist: list[str] = []
    for item in (raw, url, host):
        if item and item not in allowlist:
            allowlist.append(item)
    if port:
        hostport = f"{host}:{port}"
        if hostport not in allowlist:
            allowlist.append(hostport)
    return {"hostname": host, "url": url, "allowlist": allowlist, "port": port}


def lab_reachable_url(url: str) -> str:
    """Map this instance's public Juice Shop URL to the in-container bind.

    NAT hairpin to $PUBLIC_IPADDR:$VAST_TCP_PORT_10200 fails from inside the
    container; HexStrike must scan http://127.0.0.1:10200 instead.
    """
    raw = (url or "").strip()
    if not raw:
        return raw
    parsed_url = raw if "://" in raw else f"http://{raw}"
    try:
        parsed = urlparse(parsed_url)
    except ValueError:
        return raw
    public_ip = (os.environ.get("PUBLIC_IPADDR") or "").strip()
    juice_ext = (os.environ.get("VAST_TCP_PORT_10200") or "").strip()
    host = parsed.hostname or ""
    port = parsed.port
    if public_ip and juice_ext and host == public_ip and str(port) == str(juice_ext):
        return "http://127.0.0.1:10200"
    return raw


def merge_allowlists(*lists: list[str]) -> list[str]:
    merged: list[str] = []
    for items in lists:
        for item in items:
            if item and item not in merged:
                merged.append(item)
    return merged


def ids_equal(left: object, right: object) -> bool:
    return left is not None and right is not None and str(left) == str(right)
