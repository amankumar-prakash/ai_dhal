from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


TeamSide = Literal["red", "blue"]
JobStatus = Literal["queued", "dispatched", "running", "completed", "failed", "cancelled"]
PatchStatus = Literal["proposed", "approved", "applied", "failed", "rolled_back"]


class AssetCreate(BaseModel):
    name: str
    hostname: str | None = None
    ip_address: str | None = None
    kind: str | None = "host"
    criticality: str | None = "medium"


class Asset(AssetCreate):
    id: UUID
    created_at: datetime


class ScanCreate(BaseModel):
    target: str
    asset_id: UUID | None = None
    profile: str
    team: TeamSide = "red"


class ScanPatch(BaseModel):
    status: str | None = None
    findings_count: int | None = None
    finished_at: datetime | None = None
    error: str | None = None


class Scan(BaseModel):
    id: UUID
    target: str
    asset_id: UUID | None = None
    profile: str
    status: str
    team: TeamSide = "red"
    job_id: UUID | None = None
    source_service: str | None = None
    findings_count: int = 0
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_by: UUID | None = None
    created_at: datetime | None = None


class FindingCreate(BaseModel):
    title: str
    severity: str = "medium"
    scan_id: UUID | None = None
    asset_id: UUID | None = None
    cve: str | None = None
    team: TeamSide | None = None
    source_tool: str | None = None
    remediation: str | None = None
    evidence: Any = None
    status: str = "open"
    cvss: float | None = 0


class FindingPatch(BaseModel):
    status: str | None = None
    remediation: str | None = None
    evidence: Any = None
    resolved_at: datetime | None = None


class Finding(FindingCreate):
    id: UUID
    detected_at: datetime | None = None
    resolved_at: datetime | None = None
    created_at: datetime | None = None


class ThreatEventCreate(BaseModel):
    technique: str | None = "T0000"
    technique_name: str | None = None
    description: str | None = None
    severity: str = "medium"
    status: str = "new"
    team: TeamSide | None = None
    source_tag: str | None = None
    scan_id: UUID | None = None
    asset_id: UUID | None = None
    finding_id: UUID | None = None
    source_ip: str | None = "0.0.0.0"
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class ThreatEvent(ThreatEventCreate):
    id: UUID
    occurred_at: datetime | None = None
    created_at: datetime | None = None


class JobCreate(BaseModel):
    team: TeamSide
    profile: str
    asset_ids: list[UUID] = Field(min_length=1)
    tools: list[str] | None = None


class JobPatch(BaseModel):
    status: JobStatus | None = None
    error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class Job(BaseModel):
    id: UUID
    team: TeamSide
    profile: str
    status: JobStatus
    asset_ids: list[UUID]
    requested_by: UUID | None = None
    error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime | None = None


class PatchCreate(BaseModel):
    finding_id: UUID
    title: str
    playbook: str
    asset_id: UUID | None = None


class PatchPatch(BaseModel):
    status: PatchStatus | None = None
    evidence: list[Any] | None = None


class Patch(BaseModel):
    id: UUID
    finding_id: UUID
    asset_id: UUID | None = None
    title: str
    playbook: str
    status: PatchStatus
    evidence: list[Any] = Field(default_factory=list)
    created_by: UUID | None = None
    applied_at: datetime | None = None
    created_at: datetime | None = None


class AttackChainCreate(BaseModel):
    name: str
    scan_id: UUID | None = None
    team: TeamSide = "red"


class AttackChainStepCreate(BaseModel):
    stage: str
    sequence: int
    title: str
    severity: str | None = "medium"
    threat_event_id: UUID | None = None
    finding_id: UUID | None = None
    category: str | None = None
    source_tool: str | None = None
    evidence: str | None = None


class ToolRunCreate(BaseModel):
    job_id: UUID
    team: TeamSide
    tool_name: str
    command_summary: str | None = None
    exit_code: int | None = None
    raw_output: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime | None = None
    finished_at: datetime | None = None


AppRole = Literal["user", "security_analyst", "security_manager", "admin"]
UserAccountStatus = Literal["pending", "active", "disabled"]
TaskType = Literal["red", "blue"]
TaskStatus = Literal[
    "draft", "assigned", "in_progress", "blocked", "completed", "reviewed", "closed"
]
TaskLinkKind = Literal["finding", "scan"]
TaskAuditAction = Literal[
    "created",
    "assigned",
    "started",
    "started_on_behalf",
    "blocked",
    "unblocked",
    "completed",
    "reviewed",
    "closed",
    "reassigned",
    "note_added",
    "link_added",
]
NotificationType = Literal[
    "task_assigned", "task_reassigned", "task_completed_for_review", "generic"
]


class RoleAssign(BaseModel):
    user_id: UUID
    role: AppRole


class ProfileOut(BaseModel):
    id: UUID
    email: str | None = None
    display_name: str | None = None
    status: UserAccountStatus = "pending"
    must_change_password: bool = False
    invite_expires_at: datetime | None = None
    invite_consumed_at: datetime | None = None
    last_login_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class MeResponse(BaseModel):
    user_id: UUID
    email: str | None = None
    role: AppRole
    profile: ProfileOut | None = None
    tool_unlock: dict[str, bool]


class TaskCreate(BaseModel):
    target: str
    description: str = ""
    patch_scope: str = ""
    asset_id: UUID | None = None
    task_type: TaskType
    assignee_id: UUID | None = None


class TaskPatch(BaseModel):
    target: str | None = None
    description: str | None = None
    patch_scope: str | None = None
    asset_id: UUID | None = None
    task_type: TaskType | None = None
    assignee_id: UUID | None = None
    status: TaskStatus | None = None
    linked_job_id: UUID | None = None
    action: Literal[
        "assign",
        "start",
        "block",
        "unblock",
        "complete",
        "review",
        "close",
        "reassign",
    ] | None = None


class TaskNoteCreate(BaseModel):
    body: str


class TaskLinkCreate(BaseModel):
    kind: TaskLinkKind
    ref_id: UUID


class AdminUserCreate(BaseModel):
    email: str
    role: AppRole
    display_name: str | None = None
    temporary_password: str | None = None


class AdminUserPatch(BaseModel):
    role: AppRole | None = None
    status: UserAccountStatus | None = None
    display_name: str | None = None
    reissue_invite: bool = False


CaiTeam = Literal["red", "blue"]
CaiSessionStatus = Literal["starting", "running", "stopping", "stopped", "failed"]


class CaiSessionCreate(BaseModel):
    team: CaiTeam
    task_id: UUID | None = None
    message: str | None = None


class CaiMessageCreate(BaseModel):
    content: str


class CaiSessionOut(BaseModel):
    id: UUID
    team: CaiTeam
    status: CaiSessionStatus
    task_id: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    ended_at: datetime | None = None
    error: str | None = None


class CaiStreamEvent(BaseModel):
    session_id: UUID
    seq: int
    type: Literal["started", "stdout", "stderr", "user_echo", "status", "error", "ended"]
    text: str = ""
    ts: datetime | None = None
