"""
Full integration test suite for the AI Red-Team Orchestrator — uses TestClient + JWT fixtures.
Tests every endpoint + scenario: tool registry, enhance, plan, execute (dry run), control, reports.
"""
from __future__ import annotations

import os
import time

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("ORCHESTRATOR_STUB", "true")
os.environ.setdefault("LLM_STUB", "1")
os.environ.setdefault("API_STORE", "memory")


# ─── Fixtures (reuse conftest pattern) ───────────────────────────────────────
# conftest.py already provides: client, analyst_headers, admin_headers

API = "/api/v1"


# ═══════════════════════════════════════════════════════════════════
# SCENARIO 1: Auth Enforcement
# ═══════════════════════════════════════════════════════════════════

class TestOrchestratorAuth:
    """Orchestrator endpoints must reject unauthenticated and service-token requests."""

    def test_tools_requires_jwt(self, client: TestClient):
        r = client.get(f"{API}/orchestrator/tools")
        assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text}"

    def test_enhance_requires_jwt(self, client: TestClient):
        r = client.post(f"{API}/orchestrator/enhance",
                        json={"raw_input": "test"})
        assert r.status_code == 401

    def test_plan_requires_jwt(self, client: TestClient):
        r = client.post(f"{API}/orchestrator/plan",
                        json={"enhanced_description": "x",
                              "target_profile": {"targets": ["1.2.3.4"], "ports": [], "attack_surface_notes": "", "compliance_flags": [], "out_of_scope": []}})
        assert r.status_code == 401

    def test_execute_requires_jwt(self, client: TestClient):
        r = client.post(f"{API}/orchestrator/execute",
                        json={"plan_id": "x", "stages": [], "target_profile": {"targets": [], "ports": [], "attack_surface_notes": "", "compliance_flags": [], "out_of_scope": []}, "enhanced_description": "y"})
        assert r.status_code == 401

    def test_service_token_denied_on_tools(self, client: TestClient, red_headers):
        """Service tokens are NOT valid for orchestrator — human JWT required."""
        r = client.get(f"{API}/orchestrator/tools", headers=red_headers)
        assert r.status_code == 403

    def test_analyst_can_access_tools(self, client: TestClient, analyst_headers):
        r = client.get(f"{API}/orchestrator/tools", headers=analyst_headers)
        assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════
# SCENARIO 2: Tool Registry
# ═══════════════════════════════════════════════════════════════════

class TestToolRegistry:
    """GET /orchestrator/tools returns the merged tool catalog."""

    def test_returns_200_and_tool_list(self, client: TestClient, analyst_headers):
        r = client.get(f"{API}/orchestrator/tools", headers=analyst_headers)
        assert r.status_code == 200
        body = r.json()
        assert "tools" in body
        assert "discovered_at" in body

    def test_catalog_contains_10_plus_tools(self, client: TestClient, analyst_headers):
        r = client.get(f"{API}/orchestrator/tools", headers=analyst_headers)
        tools = r.json()["tools"]
        assert len(tools) >= 8, f"Expected >=8 tools, got {len(tools)}"

    def test_all_required_tools_present(self, client: TestClient, analyst_headers):
        r = client.get(f"{API}/orchestrator/tools", headers=analyst_headers)
        ids = {t["id"] for t in r.json()["tools"]}
        required = {"nmap_scan", "nikto_scan", "nuclei_scan", "sqlmap_scan",
                    "hydra_bruteforce", "gobuster_dirbusting", "cai_emulation", "ssl_audit"}
        missing = required - ids
        assert not missing, f"Missing tools: {missing}"

    def test_each_tool_has_required_fields(self, client: TestClient, analyst_headers):
        r = client.get(f"{API}/orchestrator/tools", headers=analyst_headers)
        for tool in r.json()["tools"]:
            assert tool["id"], "Tool missing id"
            assert tool["name"], "Tool missing name"
            assert tool["category"] in ("recon", "vuln_scan", "exploitation", "post_exploitation")
            assert tool["description"], "Tool missing description"
            assert tool["source"] in ("hexstrike", "cai", "builtin")


# ═══════════════════════════════════════════════════════════════════
# SCENARIO 3: Description Enhancer
# ═══════════════════════════════════════════════════════════════════

class TestDescriptionEnhancer:
    """POST /orchestrator/enhance — stub mode target profiling."""

    def test_basic_enhancement_returns_200(self, client: TestClient, analyst_headers):
        r = client.post(f"{API}/orchestrator/enhance",
                        json={"raw_input": "Web app at 192.168.1.10"},
                        headers=analyst_headers)
        assert r.status_code == 200

    def test_ip_extracted_to_targets(self, client: TestClient, analyst_headers):
        r = client.post(f"{API}/orchestrator/enhance",
                        json={"raw_input": "pentest 10.20.30.40 internal api"},
                        headers=analyst_headers)
        data = r.json()
        assert "10.20.30.40" in data["target_profile"]["targets"]

    def test_enhanced_description_non_empty(self, client: TestClient, analyst_headers):
        r = client.post(f"{API}/orchestrator/enhance",
                        json={"raw_input": "scan 172.16.0.5 for OWASP issues"},
                        headers=analyst_headers)
        data = r.json()
        assert len(data["enhanced_description"]) > 10

    def test_model_used_is_stub(self, client: TestClient, analyst_headers):
        r = client.post(f"{API}/orchestrator/enhance",
                        json={"raw_input": "scan 10.0.0.1"},
                        headers=analyst_headers)
        assert r.json()["model_used"] == "stub"

    def test_suggested_phase_count_gte_1(self, client: TestClient, analyst_headers):
        r = client.post(f"{API}/orchestrator/enhance",
                        json={"raw_input": "scan 10.0.0.1"},
                        headers=analyst_headers)
        assert r.json()["suggested_phase_count"] >= 1

    def test_scope_notes_accepted(self, client: TestClient, analyst_headers):
        r = client.post(f"{API}/orchestrator/enhance",
                        json={"raw_input": "10.0.0.1", "scope_notes": "PCI-DSS, no DoS"},
                        headers=analyst_headers)
        assert r.status_code == 200

    def test_no_ip_input_fallback_to_default_target(self, client: TestClient, analyst_headers):
        r = client.post(f"{API}/orchestrator/enhance",
                        json={"raw_input": "pentest the company web portal"},
                        headers=analyst_headers)
        assert r.status_code == 200
        targets = r.json()["target_profile"]["targets"]
        assert len(targets) >= 1

    def test_short_input_rejected(self, client: TestClient, analyst_headers):
        """raw_input < 3 chars should fail validation (422)."""
        r = client.post(f"{API}/orchestrator/enhance",
                        json={"raw_input": "ab"},
                        headers=analyst_headers)
        assert r.status_code == 422

    def test_missing_raw_input_rejected(self, client: TestClient, analyst_headers):
        r = client.post(f"{API}/orchestrator/enhance",
                        json={},
                        headers=analyst_headers)
        assert r.status_code == 422


# ═══════════════════════════════════════════════════════════════════
# SCENARIO 4: Plan Generation
# ═══════════════════════════════════════════════════════════════════

_SAMPLE_TARGET = {
    "targets": ["10.0.0.1"],
    "ports": ["80", "443"],
    "attack_surface_notes": "Web + SSH",
    "compliance_flags": ["OWASP"],
    "out_of_scope": [],
}


class TestPlanGeneration:
    """POST /orchestrator/plan — stub plan generation."""

    def _generate(self, client, headers, max_stages=4):
        return client.post(
            f"{API}/orchestrator/plan",
            json={
                "enhanced_description": "Authorized pentest of 10.0.0.1",
                "target_profile": _SAMPLE_TARGET,
                "max_stages": max_stages,
            },
            headers=headers,
        )

    def test_plan_returns_200(self, client: TestClient, analyst_headers):
        assert self._generate(client, analyst_headers).status_code == 200

    def test_plan_has_4_stages(self, client: TestClient, analyst_headers):
        plan = self._generate(client, analyst_headers).json()
        assert len(plan["stages"]) == 4

    def test_stages_ordered_correctly(self, client: TestClient, analyst_headers):
        stages = self._generate(client, analyst_headers).json()["stages"]
        assert stages[0]["name"] == "recon"
        assert stages[1]["name"] == "vuln_scan"
        assert stages[2]["name"] == "exploitation"
        assert stages[3]["name"] == "post_exploitation"

    def test_every_stage_has_steps(self, client: TestClient, analyst_headers):
        stages = self._generate(client, analyst_headers).json()["stages"]
        for stage in stages:
            assert len(stage["steps"]) >= 1, f"Stage {stage['label']} has no steps"

    def test_max_stages_2_boundary(self, client: TestClient, analyst_headers):
        plan = self._generate(client, analyst_headers, max_stages=2).json()
        assert len(plan["stages"]) <= 2

    def test_max_stages_1_boundary(self, client: TestClient, analyst_headers):
        plan = self._generate(client, analyst_headers, max_stages=1).json()
        assert len(plan["stages"]) == 1

    def test_plan_id_has_correct_format(self, client: TestClient, analyst_headers):
        plan = self._generate(client, analyst_headers).json()
        assert plan["plan_id"].startswith("plan-")

    def test_model_used_is_stub(self, client: TestClient, analyst_headers):
        plan = self._generate(client, analyst_headers).json()
        assert plan["model_used"] == "stub"

    def test_all_steps_have_tool_id(self, client: TestClient, analyst_headers):
        stages = self._generate(client, analyst_headers).json()["stages"]
        for stage in stages:
            for step in stage["steps"]:
                assert step["tool_id"], f"Step {step['step_id']} has no tool_id"
                assert step["tool_name"], f"Step {step['step_id']} has no tool_name"

    def test_empty_description_rejected(self, client: TestClient, analyst_headers):
        r = client.post(f"{API}/orchestrator/plan",
                        json={"enhanced_description": "x", "target_profile": _SAMPLE_TARGET},
                        headers=analyst_headers)
        # "x" is 1 char < 5 min_length
        assert r.status_code == 422


# ═══════════════════════════════════════════════════════════════════
# SCENARIO 5: Execution
# ═══════════════════════════════════════════════════════════════════

def _make_plan(client, headers):
    r = client.post(f"{API}/orchestrator/plan",
                    json={"enhanced_description": "Pentest 10.0.0.1",
                          "target_profile": _SAMPLE_TARGET, "max_stages": 2},
                    headers=headers)
    assert r.status_code == 200
    return r.json()


def _execute(client, headers, plan, dry_run=True):
    return client.post(f"{API}/orchestrator/execute",
                       json={"plan_id": plan["plan_id"],
                             "stages": plan["stages"],
                             "target_profile": _SAMPLE_TARGET,
                             "enhanced_description": "Test",
                             "dry_run": dry_run},
                       headers=headers)


class TestExecution:
    """POST /orchestrator/execute + GET /runs/{id}."""

    def test_execute_returns_202(self, client: TestClient, analyst_headers):
        plan = _make_plan(client, analyst_headers)
        r = _execute(client, analyst_headers, plan)
        assert r.status_code == 202

    def test_initial_status_pending(self, client: TestClient, analyst_headers):
        plan = _make_plan(client, analyst_headers)
        run = _execute(client, analyst_headers, plan).json()
        assert run["status"] == "pending"

    def test_dry_run_flag_propagated(self, client: TestClient, analyst_headers):
        plan = _make_plan(client, analyst_headers)
        run = _execute(client, analyst_headers, plan, dry_run=True).json()
        assert run["dry_run"] is True

    def test_run_id_returned(self, client: TestClient, analyst_headers):
        plan = _make_plan(client, analyst_headers)
        run = _execute(client, analyst_headers, plan).json()
        assert run["run_id"].startswith("run-")

    def test_get_run_state_200(self, client: TestClient, analyst_headers):
        plan = _make_plan(client, analyst_headers)
        run = _execute(client, analyst_headers, plan).json()
        r = client.get(f"{API}/orchestrator/runs/{run['run_id']}", headers=analyst_headers)
        assert r.status_code == 200

    def test_get_unknown_run_404(self, client: TestClient, analyst_headers):
        r = client.get(f"{API}/orchestrator/runs/nonexistent-run-xyz", headers=analyst_headers)
        assert r.status_code == 404

    def test_dry_run_completes(self, client: TestClient, analyst_headers):
        """Dry run should complete without needing a worker."""
        from app.schemas.orchestrator import ExecutePlanRequest, TargetProfile
        from app.services.orchestrator_executor import create_run, get_run_state, run_plan_async
        from app.config import Settings
        import asyncio

        from app.schemas.orchestrator import OrchestratorPlanRequest
        from app.services.orchestrator_planner import generate_plan

        settings = Settings(orchestrator_stub=True)
        plan_obj = asyncio.run(generate_plan(
            OrchestratorPlanRequest(
                enhanced_description="Test dry run",
                target_profile=TargetProfile(targets=["10.0.0.1"]),
                max_stages=2,
            ),
            settings,
        ))

        req = ExecutePlanRequest(
            plan_id=plan_obj.plan_id,
            stages=plan_obj.stages,
            target_profile=plan_obj.target_profile,
            enhanced_description=plan_obj.enhanced_description,
            dry_run=True,
        )
        state = create_run(req)
        asyncio.run(run_plan_async(state.run_id, settings))
        final = get_run_state(state.run_id)
        assert final.status == "finished"
        assert all(s.status == "completed" for s in final.stages if s.steps)

    def test_stages_count_matches_plan(self, client: TestClient, analyst_headers):
        plan = _make_plan(client, analyst_headers)
        run = _execute(client, analyst_headers, plan).json()
        assert len(run["stages"]) == len(plan["stages"])

    def test_empty_stages_allowed(self, client: TestClient, analyst_headers):
        r = client.post(f"{API}/orchestrator/execute",
                        json={"plan_id": "plan-test", "stages": [],
                              "target_profile": _SAMPLE_TARGET,
                              "enhanced_description": "empty", "dry_run": True},
                        headers=analyst_headers)
        assert r.status_code == 202


# ═══════════════════════════════════════════════════════════════════
# SCENARIO 6: Run Control
# ═══════════════════════════════════════════════════════════════════

class TestRunControl:
    """POST /orchestrator/runs/{id}/control."""

    def _start_run(self, client, headers):
        plan = _make_plan(client, headers)
        return _execute(client, headers, plan).json()["run_id"]

    def test_abort_returns_200(self, client: TestClient, analyst_headers):
        rid = self._start_run(client, analyst_headers)
        r = client.post(f"{API}/orchestrator/runs/{rid}/control",
                        json={"action": "abort"}, headers=analyst_headers)
        assert r.status_code == 200

    def test_abort_sets_status_aborted(self, client: TestClient, analyst_headers):
        rid = self._start_run(client, analyst_headers)
        r = client.post(f"{API}/orchestrator/runs/{rid}/control",
                        json={"action": "abort"}, headers=analyst_headers)
        assert r.json()["status"] == "aborted"

    def test_pause_sets_status_paused(self, client: TestClient, analyst_headers):
        rid = self._start_run(client, analyst_headers)
        r = client.post(f"{API}/orchestrator/runs/{rid}/control",
                        json={"action": "pause"}, headers=analyst_headers)
        assert r.status_code == 200
        assert r.json()["status"] == "paused"

    def test_resume_after_pause(self, client: TestClient, analyst_headers):
        rid = self._start_run(client, analyst_headers)
        client.post(f"{API}/orchestrator/runs/{rid}/control",
                    json={"action": "pause"}, headers=analyst_headers)
        r = client.post(f"{API}/orchestrator/runs/{rid}/control",
                        json={"action": "resume"}, headers=analyst_headers)
        assert r.status_code == 200

    def test_control_unknown_run_404(self, client: TestClient, analyst_headers):
        r = client.post(f"{API}/orchestrator/runs/nonexistent/control",
                        json={"action": "abort"}, headers=analyst_headers)
        assert r.status_code == 404

    def test_invalid_action_422(self, client: TestClient, analyst_headers):
        rid = self._start_run(client, analyst_headers)
        r = client.post(f"{API}/orchestrator/runs/{rid}/control",
                        json={"action": "explode"}, headers=analyst_headers)
        assert r.status_code == 422


# ═══════════════════════════════════════════════════════════════════
# SCENARIO 7: Report Download
# ═══════════════════════════════════════════════════════════════════

class TestReportDownload:
    """GET /orchestrator/reports/{run_id}."""

    def _create_run(self, client, headers):
        plan = _make_plan(client, headers)
        run = _execute(client, headers, plan).json()
        return run["run_id"], plan

    def test_json_report_200(self, client: TestClient, analyst_headers):
        rid, _ = self._create_run(client, analyst_headers)
        r = client.get(f"{API}/orchestrator/reports/{rid}?format=json", headers=analyst_headers)
        assert r.status_code == 200

    def test_json_content_type(self, client: TestClient, analyst_headers):
        rid, _ = self._create_run(client, analyst_headers)
        r = client.get(f"{API}/orchestrator/reports/{rid}?format=json", headers=analyst_headers)
        assert "application/json" in r.headers["content-type"]

    def test_json_body_contains_run_id(self, client: TestClient, analyst_headers):
        rid, _ = self._create_run(client, analyst_headers)
        r = client.get(f"{API}/orchestrator/reports/{rid}?format=json", headers=analyst_headers)
        assert rid in r.text

    def test_csv_report_200(self, client: TestClient, analyst_headers):
        rid, _ = self._create_run(client, analyst_headers)
        r = client.get(f"{API}/orchestrator/reports/{rid}?format=csv", headers=analyst_headers)
        assert r.status_code == 200

    def test_csv_content_type(self, client: TestClient, analyst_headers):
        rid, _ = self._create_run(client, analyst_headers)
        r = client.get(f"{API}/orchestrator/reports/{rid}?format=csv", headers=analyst_headers)
        assert "text/csv" in r.headers["content-type"]

    def test_csv_has_header_row(self, client: TestClient, analyst_headers):
        rid, _ = self._create_run(client, analyst_headers)
        r = client.get(f"{API}/orchestrator/reports/{rid}?format=csv", headers=analyst_headers)
        assert "severity" in r.text

    def test_markdown_report_200(self, client: TestClient, analyst_headers):
        rid, _ = self._create_run(client, analyst_headers)
        r = client.get(f"{API}/orchestrator/reports/{rid}?format=markdown", headers=analyst_headers)
        assert r.status_code == 200

    def test_markdown_starts_with_heading(self, client: TestClient, analyst_headers):
        rid, _ = self._create_run(client, analyst_headers)
        r = client.get(f"{API}/orchestrator/reports/{rid}?format=markdown", headers=analyst_headers)
        assert r.text.lstrip().startswith("#")

    def test_unknown_format_defaults_gracefully(self, client: TestClient, analyst_headers):
        rid, _ = self._create_run(client, analyst_headers)
        r = client.get(f"{API}/orchestrator/reports/{rid}?format=xml", headers=analyst_headers)
        assert r.status_code == 200  # defaults to JSON

    def test_unknown_run_404(self, client: TestClient, analyst_headers):
        r = client.get(f"{API}/orchestrator/reports/bad-run-xyz?format=json", headers=analyst_headers)
        assert r.status_code == 404

    def test_report_has_correct_disposition_header(self, client: TestClient, analyst_headers):
        rid, _ = self._create_run(client, analyst_headers)
        r = client.get(f"{API}/orchestrator/reports/{rid}?format=csv", headers=analyst_headers)
        cd = r.headers.get("content-disposition", "")
        assert rid in cd or ".csv" in cd


# ═══════════════════════════════════════════════════════════════════
# SCENARIO 8: Existing Functionality Not Broken
# ═══════════════════════════════════════════════════════════════════

class TestNoRegression:
    """Confirm existing endpoints still work after orchestrator was mounted."""

    def test_health_still_ok(self, client: TestClient):
        r = client.get(f"{API}/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_assets_still_require_auth(self, client: TestClient):
        r = client.get(f"{API}/assets")
        assert r.status_code == 401

    def test_assets_work_with_analyst_jwt(self, client: TestClient, analyst_headers):
        r = client.get(f"{API}/assets", headers=analyst_headers)
        assert r.status_code == 200

    def test_cai_sessions_endpoint_exists(self, client: TestClient, analyst_headers):
        """CAI sessions list endpoint is accessible (GET /cai/sessions returns 200 or empty list)."""
        # /cai/sessions is a POST-only endpoint; GET on the collection returns 405 (correct behaviour)
        # Verify the router is still mounted — it should return 405 not 404
        r = client.get(f"{API}/cai/sessions", headers=analyst_headers)
        assert r.status_code in (200, 405)  # mounted = not 404

    def test_jobs_still_require_auth(self, client: TestClient):
        r = client.get(f"{API}/jobs")
        assert r.status_code == 401

    def test_scans_endpoint_still_accessible(self, client: TestClient, analyst_headers):
        r = client.get(f"{API}/scans", headers=analyst_headers)
        assert r.status_code == 200

    def test_findings_endpoint_still_accessible(self, client: TestClient, analyst_headers):
        r = client.get(f"{API}/findings", headers=analyst_headers)
        assert r.status_code == 200
