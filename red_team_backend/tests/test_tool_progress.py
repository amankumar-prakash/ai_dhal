"""Unit tests for chat tool-progress estimates."""
from __future__ import annotations

from app.adapters.tool_progress import estimate_progress, tool_family


def test_wordlist_lookup_common_txt():
    est = estimate_progress(
        "gobuster_scan",
        {"wordlist": "/usr/share/wordlists/dirb/common.txt", "url": "http://t"},
        10,
    )
    assert est.mode == "wordlist"
    assert est.list_total == 4614
    # 10s * 80 rps / 4614 ≈ 17%
    assert est.progress_pct == 17
    assert 1 <= est.progress_pct <= 95


def test_wordlist_from_dash_w_flag():
    est = estimate_progress(
        "ffuf_scan",
        {"additional_args": "-t 20 -w /usr/share/wordlists/dirb/big.txt"},
        0,
    )
    assert est.mode == "wordlist"
    assert est.list_total == 20469
    assert est.progress_pct == 1


def test_hydra_product_of_local_lists(tmp_path):
    users = tmp_path / "users.txt"
    pwds = tmp_path / "pass.txt"
    users.write_text("a\nb\n")
    pwds.write_text("1\n2\n3\n")
    est = estimate_progress(
        "hydra",
        {"username_file": str(users), "password_file": str(pwds)},
        0.2,
    )
    assert est.mode == "wordlist"
    assert est.list_total == 6
    # 0.2s * 16 rps / 6 * 100 ≈ 53
    assert est.progress_pct == 53


def test_unknown_tool_uses_duration_guess():
    est = estimate_progress("katana_crawl", {"url": "https://t"}, 60)
    assert est.mode == "guess"
    assert est.list_total is None
    # 60 / 120 * 100 = 50
    assert est.progress_pct == 50


def test_clamps_at_95_while_running():
    est = estimate_progress("nmap_scan", {}, 10_000)
    assert est.mode == "guess"
    assert est.progress_pct == 95


def test_never_goes_backwards():
    later = estimate_progress("katana_crawl", {}, 1, prev_pct=40)
    assert later.progress_pct == 40


def test_done_is_100():
    est = estimate_progress(
        "gobuster_scan",
        {"wordlist": "/usr/share/wordlists/dirb/common.txt"},
        0,
        done=True,
    )
    assert est.progress_pct == 100
    assert est.mode == "wordlist"
    assert est.list_total == 4614


def test_ignores_hexstrike_stuck_at_half():
    est = estimate_progress("nmap_scan", {}, 5, hexstrike_fraction=0.5)
    # 5 / 90 * 100 ≈ 5, not 50
    assert est.progress_pct == 5


def test_uses_usable_hexstrike_fraction():
    est = estimate_progress("nmap_scan", {}, 1, hexstrike_fraction=0.8)
    assert est.progress_pct == 80


def test_local_file_line_count_beats_table(tmp_path):
    wl = tmp_path / "common.txt"
    wl.write_text("one\ntwo\nthree\n")
    est = estimate_progress("gobuster_scan", {"wordlist": str(wl)}, 0)
    assert est.mode == "wordlist"
    assert est.list_total == 3


def test_as_args_payload():
    est = estimate_progress("gobuster_scan", {"wordlist": "/usr/share/dirb/wordlists/common.txt"}, 0)
    payload = est.as_args()
    assert payload["progress_pct"] == 1
    assert payload["mode"] == "wordlist"
    assert payload["list_total"] == 4614


def test_tool_family_prefixes():
    assert tool_family("katana_crawl") == "katana"
    assert tool_family("nmap_scan") == "nmap"
    assert tool_family("feroxbuster_scan") == "feroxbuster"
