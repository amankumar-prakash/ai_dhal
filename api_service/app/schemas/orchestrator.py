"""Pydantic schemas for the AI Red-Team Orchestrator."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


# ─── Enums ──────────────────────────────────────────────────────────────────

OrchestratorRunStatus = Literal[
    "pending", "enhancing", "planning", "executing",
    "paused", "finished", "failed", "aborted"
]

StageName = Literal[
    "recon", "vuln_scan", "exploitation", "post_exploitation", "custom"
]

Severity = Literal["critical", "high", "medium", "low", "info"]


# ─── Tool Registry ───────────────────────────────────────────────────────────

class ToolParam(BaseModel):
    name: str
    type: str  # string | integer | boolean | list
    required: bool = False
    description: str = ""
    default: Any = None


class ToolDefinition(BaseModel):
    id: str                          # e.g. "nmap_scan"
    name: str                        # e.g. "Nmap Port Scanner"
    category: str                    # recon | vuln_scan | exploitation | post_exploitation
    description: str
    params: list[ToolParam] = Field(default_factory=list)
    source: Literal["hexstrike", "cai", "builtin"] = "hexstrike"


class ToolRegistryResponse(BaseModel):
    tools: list[ToolDefinition]
    discovered_at: datetime


# ─── Description Enhancement ─────────────────────────────────────────────────

class EnhanceDescriptionRequest(BaseModel):
    raw_input: str = Field(
        ...,
        description="Free-form target description, e.g. 'web app at 10.0.0.5, test for OWASP Top 10'",
        min_length=3,
    )
    scope_notes: str | None = Field(
        None,
        description="Additional scope restrictions or compliance flags",
    )


class TargetProfile(BaseModel):
    targets: list[str] = Field(default_factory=list, description="IPs, hostnames, or CIDR ranges")
    ports: list[str] = Field(default_factory=list, description="Port/protocol hints")
    attack_surface_notes: str = ""
    compliance_flags: list[str] = Field(default_factory=list)  # e.g. ["PCI-DSS", "OWASP"]
    out_of_scope: list[str] = Field(default_factory=list)


class EnhanceDescriptionResponse(BaseModel):
    enhanced_description: str
    target_profile: TargetProfile
    suggested_phase_count: int = 4
    model_used: str = "stub"


# ─── Plan ────────────────────────────────────────────────────────────────────

class ToolStep(BaseModel):
    step_id: str                     # unique within the stage
    tool_id: str                     # references ToolDefinition.id
    tool_name: str
    description: str
    params: dict[str, Any] = Field(default_factory=dict)
    expected_output: str = ""
    enabled: bool = True


class PlanStage(BaseModel):
    stage_id: str
    name: StageName
    label: str
    description: str
    steps: list[ToolStep] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)  # stage_ids


class OrchestratorPlan(BaseModel):
    plan_id: str
    title: str
    target_profile: TargetProfile
    enhanced_description: str
    stages: list[PlanStage]
    created_at: datetime = Field(default_factory=datetime.utcnow)
    model_used: str = "stub"
    raw_llm_output: str | None = None


class OrchestratorPlanRequest(BaseModel):
    enhanced_description: str = Field(..., min_length=5)
    target_profile: TargetProfile
    tool_ids: list[str] | None = Field(
        None, description="Restrict to specific tool IDs; None = use all available"
    )
    max_stages: int = Field(4, ge=1, le=8)


# ─── Execution ───────────────────────────────────────────────────────────────

class ExecutePlanRequest(BaseModel):
    plan_id: str
    stages: list[PlanStage]          # sent back so analyst can customise
    target_profile: TargetProfile
    enhanced_description: str
    dry_run: bool = False            # simulate without real dispatch


class StepExecutionLog(BaseModel):
    step_id: str
    tool_id: str
    tool_name: str
    status: Literal["pending", "running", "completed", "failed", "skipped"]
    started_at: datetime | None = None
    finished_at: datetime | None = None
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    params_used: dict[str, Any] = Field(default_factory=dict)


class StageExecutionLog(BaseModel):
    stage_id: str
    label: str
    status: Literal["pending", "running", "completed", "failed", "skipped"]
    started_at: datetime | None = None
    finished_at: datetime | None = None
    steps: list[StepExecutionLog] = Field(default_factory=list)


class OrchestratorRunState(BaseModel):
    run_id: str
    plan_id: str
    status: OrchestratorRunStatus
    current_stage_id: str | None = None
    stages: list[StageExecutionLog] = Field(default_factory=list)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None
    dry_run: bool = False


# ─── Control ────────────────────────────────────────────────────────────────

class RunControlRequest(BaseModel):
    action: Literal["pause", "resume", "abort"]


# ─── Findings & Report ───────────────────────────────────────────────────────

class FindingSummary(BaseModel):
    id: str
    run_id: str
    stage_id: str
    step_id: str
    tool_name: str
    title: str
    severity: Severity
    description: str
    evidence: str = ""
    cve: str | None = None
    remediation: str | None = None
    detected_at: datetime = Field(default_factory=datetime.utcnow)


class SeverityBreakdown(BaseModel):
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    info: int = 0


class OrchestratorReport(BaseModel):
    run_id: str
    plan_id: str
    title: str
    target_profile: TargetProfile
    enhanced_description: str
    status: OrchestratorRunStatus
    started_at: datetime | None = None
    finished_at: datetime | None = None
    severity_breakdown: SeverityBreakdown = Field(default_factory=SeverityBreakdown)
    findings: list[FindingSummary] = Field(default_factory=list)
    stages_summary: list[StageExecutionLog] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.utcnow)
