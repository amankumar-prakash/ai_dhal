"""Unit tests for artifact store, compression caps, and phase isolation."""
from __future__ import annotations

import json
from pathlib import Path

from app.orchestration.artifact_store import JobArtifactStore, empty_facts, merge_facts
from app.orchestration.compress import (
    build_phase_rollup,
    build_tool_summary,
    compress_for_llm,
    compress_text,
    consolidate_facts,
    estimate_tokens,
    update_job_context,
)
from app.orchestration.phases import RECON_PHASES, default_phase_order
from app.orchestration.report import finalize_scan_report, render_scan_report_markdown
from app.orchestration.tool_output import parse_tool_output
from app.settings import WorkerSettings


def test_artifact_store_writes_raw_summary_rollup_context(tmp_path: Path) -> None:
    store = JobArtifactStore(tmp_path, "job-1")
    seq = store.next_seq()
    store.write_raw(
        seq=seq,
        phase="surface",
        tool_name="nmap_scan",
        args={"target": "localhost"},
        stdout="80/tcp open http\n" * 500,
        command_summary="nmap -sT",
    )
    summary = build_tool_summary(
        job_id="job-1",
        seq=seq,
        phase="surface",
        tool_name="nmap_scan",
        target="http://localhost",
        stdout="80/tcp open http\n443/tcp open https",
        success=True,
        settings=WorkerSettings(llmlingua_enabled="0", tool_summary_tokens=50),
    )
    store.write_summary(seq=seq, tool_name="nmap_scan", payload=summary)
    rollup = build_phase_rollup(
        job_id="job-1",
        phase="surface",
        tools_run=["nmap_scan"],
        tools_skipped=[],
        summaries=[summary],
        settings=WorkerSettings(llmlingua_enabled="0", phase_rollup_tokens=100),
    )
    store.write_rollup("surface", rollup)
    ctx = store.read_context()
    ctx = update_job_context(
        ctx,
        rollup=rollup,
        settings=WorkerSettings(llmlingua_enabled="0", job_context_tokens=80),
    )
    store.write_context(ctx)

    raw = json.loads((store.tools_dir / "001_nmap_scan.raw.json").read_text(encoding="utf-8"))
    assert "80/tcp open http" in raw["stdout"]
    assert (store.tools_dir / "001_nmap_scan.summary.json").is_file()
    assert (store.phases_dir / "surface.rollup.json").is_file()
    saved = store.read_context()
    assert saved["token_stats"]["compressed_tokens"] <= 80
    # Raw multi-line dump must not be the job context payload
    assert raw["stdout"] not in (saved.get("narrative_compressed") or "")
    assert saved["facts"]["open_ports"]


def test_consolidate_nmap_and_gobuster_facts() -> None:
    nmap = consolidate_facts(
        "nmap_scan",
        "http://t",
        "80/tcp open http\n443/tcp open https",
    )
    assert {"port": 80, "proto": "tcp", "service": "http"} in nmap["open_ports"]
    gob = consolidate_facts(
        "gobuster_scan",
        "http://t",
        "/ftp (Status: 200)\n/api (Status: 200)",
    )
    assert {"path": "/ftp", "status": "200"} in gob["paths"]


def test_compress_text_respects_cap_without_llmlingua() -> None:
    settings = WorkerSettings(llmlingua_enabled="0")
    big = "word " * 5000
    result = compress_text(big, target_token=100, settings=settings)
    assert result["compressed_tokens"] <= 100
    assert result["method"] == "heuristic_truncate"
    assert estimate_tokens(result["compressed_prompt"]) <= 100


def test_next_prompt_facts_exclude_raw_stdout(tmp_path: Path) -> None:
    """Simulate phase handoff: prior_facts must not contain multi-KB raw dump."""
    settings = WorkerSettings(llmlingua_enabled="0", tool_summary_tokens=200)
    raw = ("OPEN PORT NOISE LINE\n" * 2000) + "80/tcp open http\n"
    summary = build_tool_summary(
        job_id="j",
        seq=1,
        phase="surface",
        tool_name="nmap_scan",
        target="http://localhost",
        stdout=raw,
        success=True,
        settings=settings,
    )
    # What the next tool agent receives
    prior = merge_facts(empty_facts(), summary["facts"])
    prior_json = json.dumps(prior)
    assert len(prior_json) < len(raw)
    assert "OPEN PORT NOISE LINE" not in prior_json or prior_json.count("OPEN PORT") < 10
    assert any(p.get("port") == 80 for p in prior["open_ports"])


def test_phase_registry_covers_default_recon() -> None:
    assert default_phase_order() == ["surface", "content", "vuln"]
    names = {t.logical_name for p in RECON_PHASES for t in p.tools}
    assert "nmap_scan" in names
    assert "nuclei_scan" in names
    assert "gobuster_scan" in names


def test_parse_tool_output_preserves_partial_timeout() -> None:
    payload = {
        "stdout": "80/tcp open http\n",
        "stderr": "",
        "timed_out": True,
        "partial_results": True,
        "return_code": -1,
        "success": True,
    }
    parsed = parse_tool_output(payload)
    assert parsed["timed_out"] is True
    assert parsed["partial_results"] is True
    assert "80/tcp open http" in parsed["stdout"]
    assert parsed["success"] is False


def test_build_tool_summary_records_timeout_error() -> None:
    summary = build_tool_summary(
        job_id="j",
        seq=2,
        phase="surface",
        tool_name="httpx_toolkit",
        target="http://t",
        stdout="",
        success=False,
        timed_out=True,
        settings=WorkerSettings(llmlingua_enabled="0"),
    )
    assert summary["timed_out"] is True
    assert any(e.get("timed_out") for e in summary["facts"]["errors"])


def test_scan_report_markdown_includes_timeouts(tmp_path: Path) -> None:
    store = JobArtifactStore(tmp_path, "job-report")
    ctx = store.read_context()
    ctx["target"] = "http://juice.lab:3000"
    ctx["scan_host"] = "juice.lab"
    store.write_context(ctx)
    seq = store.next_seq()
    store.write_raw(
        seq=seq,
        phase="surface",
        tool_name="httpx_toolkit",
        args={},
        stdout="partial line",
        success=False,
        exit_code=-1,
        timed_out=True,
        partial_results=True,
        command_summary="httpx-toolkit …",
    )
    summary = build_tool_summary(
        job_id="job-report",
        seq=seq,
        phase="surface",
        tool_name="httpx_toolkit",
        target="http://juice.lab:3000",
        stdout="partial line",
        success=False,
        timed_out=True,
        settings=WorkerSettings(llmlingua_enabled="0"),
    )
    store.write_summary(seq=seq, tool_name="httpx_toolkit", payload=summary)
    md = finalize_scan_report(store, timed_out=True, timeout_note="wall timeout")
    assert "Scan report" in md
    assert "TIMEOUT" in md or "timeout" in md.lower()
    assert (store.root / "scan_report.md").is_file()
    assert "wall timeout" in (store.read_context()["facts"]["errors"][-1]["note"])
    assert render_scan_report_markdown(store).startswith("# Scan report")


def test_run_recon_importable() -> None:
    from app.orchestration import run_recon

    assert callable(run_recon)


def test_compress_text_hard_truncates_after_lingua(monkeypatch) -> None:
    from app.orchestration import compress as compress_mod

    class _FatCompressor:
        def compress_prompt(self, original, **kwargs):  # noqa: ANN001
            return {
                "compressed_prompt": original,
                "origin_tokens": 9999,
                "compressed_tokens": 9999,
            }

    monkeypatch.setattr(compress_mod, "_get_compressor", lambda _settings: _FatCompressor())
    settings = WorkerSettings(llmlingua_enabled="1")
    big = "word " * 5000
    result = compress_text(big, target_token=100, settings=settings)
    assert result["method"] == "llmlingua2"
    assert result["compressed_tokens"] <= 100
    assert estimate_tokens(result["compressed_prompt"]) <= 100


def test_compress_for_llm_uses_model_window() -> None:
    settings = WorkerSettings(
        llm_model="gpt-4o-mini",
        llm_context_window=1000,
        llm_compress_trigger_ratio=0.8,
        llmlingua_enabled="0",
    )
    big = "https://example.test/page/scan " * 8000
    result = compress_for_llm(big, reserved_tokens=50, settings=settings)
    assert result["window"] == 1000
    assert result["trigger"] == 800
    assert result["reserved"] == 50
    assert result["cap"] == 750
    assert result["method"] == "heuristic_truncate"
    assert result["compressed_tokens"] <= 750
    assert "https://example.test" in result["compressed_prompt"]


async def test_wrapped_tool_persists_raw_and_compresses_observation(tmp_path: Path) -> None:
    from langchain_core.tools import tool

    from app.orchestration.tool_agent import ToolCapture, wrap_mcp_tool

    blob = "https://insightbot.example/page/%s?q=scan\n" % 0
    blob = blob + ("OPEN PORT NOISE LINE\n" * 20000)

    @tool
    def dummy_scan(target: str) -> str:
        """Return a huge crawl dump."""
        return blob

    store = JobArtifactStore(tmp_path, "job-wrap")
    settings = WorkerSettings(
        llmlingua_enabled="0",
        llm_model="gpt-4o-mini",
        llm_context_window=1000,
        llm_compress_trigger_ratio=0.8,
    )
    capture = ToolCapture()
    wrapped = wrap_mcp_tool(
        dummy_scan,
        store=store,
        tool_name="katana_crawl",
        phase="content",
        settings=settings,
        reserved_tokens=50,
        capture=capture,
        command_summary="dummy_scan",
        started_at="t0",
    )
    result = await wrapped.ainvoke({"target": "http://t"})
    assert capture.seq == 1
    raw = store.list_raw()[0]
    assert blob[:80] in raw["stdout"]
    assert "OPEN PORT NOISE LINE" in raw["stdout"]
    assert estimate_tokens(result) <= 750
    assert len(result) < len(blob)
    assert capture.llm_compress is not None
    assert capture.llm_compress["method"] == "heuristic_truncate"
    assert capture.parsed is not None
    assert capture.parsed["stdout"] == blob


async def test_wrapped_tool_fake_lingua_still_caps_observation(tmp_path: Path, monkeypatch) -> None:
    from langchain_core.tools import tool

    from app.orchestration import compress as compress_mod
    from app.orchestration.tool_agent import ToolCapture, wrap_mcp_tool

    class _FatCompressor:
        def compress_prompt(self, original, **kwargs):  # noqa: ANN001
            return {"compressed_prompt": original, "origin_tokens": 1, "compressed_tokens": 1}

    monkeypatch.setattr(compress_mod, "_get_compressor", lambda _settings: _FatCompressor())
    blob = "OPEN PORT NOISE LINE\n" * 20000

    @tool
    def dummy_scan(target: str) -> str:
        """Huge dump that fake lingua refuses to shrink."""
        return blob

    store = JobArtifactStore(tmp_path, "job-lingua")
    settings = WorkerSettings(
        llmlingua_enabled="1",
        llm_model="gpt-4o-mini",
        llm_context_window=1000,
        llm_compress_trigger_ratio=0.8,
    )
    capture = ToolCapture()
    wrapped = wrap_mcp_tool(
        dummy_scan,
        store=store,
        tool_name="katana_crawl",
        phase="content",
        settings=settings,
        reserved_tokens=50,
        capture=capture,
        command_summary="dummy_scan",
        started_at="t0",
    )
    result = await wrapped.ainvoke({"target": "http://t"})
    assert blob[:40] in store.list_raw()[0]["stdout"]
    assert estimate_tokens(result) <= 750
    assert capture.llm_compress is not None
    assert capture.llm_compress["method"] == "llmlingua2"


async def test_wrapped_tool_passthrough_when_under_trigger(tmp_path: Path) -> None:
    from langchain_core.tools import tool

    from app.orchestration.tool_agent import ToolCapture, wrap_mcp_tool

    small = "80/tcp open http\n"

    @tool
    def dummy_scan(target: str) -> str:
        """Tiny nmap-like line."""
        return small

    store = JobArtifactStore(tmp_path, "job-small")
    settings = WorkerSettings(llmlingua_enabled="0", llm_model="gpt-4o-mini")
    capture = ToolCapture()
    wrapped = wrap_mcp_tool(
        dummy_scan,
        store=store,
        tool_name="nmap_scan",
        phase="surface",
        settings=settings,
        reserved_tokens=10,
        capture=capture,
        command_summary="nmap",
        started_at="t0",
    )
    result = await wrapped.ainvoke({"target": "localhost"})
    assert result == small
    assert capture.llm_compress is not None
    assert capture.llm_compress["method"] == "passthrough"
    assert store.list_raw()[0]["stdout"] == small
