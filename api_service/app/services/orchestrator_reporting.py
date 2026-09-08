"""Orchestrator Reporting — aggregates findings and exports reports in multiple formats."""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime

from app.schemas.orchestrator import (
    FindingSummary,
    OrchestratorReport,
    OrchestratorRunState,
    Severity,
    SeverityBreakdown,
    TargetProfile,
)


def build_report(
    run_state: OrchestratorRunState,
    target_profile: TargetProfile,
    enhanced_description: str,
    findings: list[FindingSummary],
    plan_id: str,
    title: str = "Red-Team Engagement Report",
) -> OrchestratorReport:
    """Build a normalised OrchestratorReport from run state and findings."""
    breakdown = SeverityBreakdown()
    for f in findings:
        if f.severity == "critical":
            breakdown.critical += 1
        elif f.severity == "high":
            breakdown.high += 1
        elif f.severity == "medium":
            breakdown.medium += 1
        elif f.severity == "low":
            breakdown.low += 1
        else:
            breakdown.info += 1

    return OrchestratorReport(
        run_id=run_state.run_id,
        plan_id=plan_id,
        title=title,
        target_profile=target_profile,
        enhanced_description=enhanced_description,
        status=run_state.status,
        started_at=run_state.started_at,
        finished_at=run_state.finished_at,
        severity_breakdown=breakdown,
        findings=findings,
        stages_summary=run_state.stages,
        generated_at=datetime.utcnow(),
    )


def export_json(report: OrchestratorReport) -> str:
    """Export report as JSON string."""
    return report.model_dump_json(indent=2)


def export_csv(report: OrchestratorReport) -> str:
    """Export findings as CSV string."""
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["id", "severity", "title", "tool_name", "stage_id", "description", "cve", "remediation", "detected_at"],
    )
    writer.writeheader()
    for f in report.findings:
        writer.writerow({
            "id": f.id,
            "severity": f.severity,
            "title": f.title,
            "tool_name": f.tool_name,
            "stage_id": f.stage_id,
            "description": f.description[:300],
            "cve": f.cve or "",
            "remediation": f.remediation or "",
            "detected_at": f.detected_at.isoformat() if f.detected_at else "",
        })
    return output.getvalue()


def export_markdown(report: OrchestratorReport) -> str:
    """Export report as Markdown string."""
    sb = report.severity_breakdown
    targets = ", ".join(report.target_profile.targets) or "N/A"

    md_lines = [
        f"# {report.title}",
        "",
        f"**Run ID:** `{report.run_id}`  ",
        f"**Plan ID:** `{report.plan_id}`  ",
        f"**Status:** `{report.status}`  ",
        f"**Targets:** {targets}  ",
        f"**Generated:** {report.generated_at.strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "## Engagement Description",
        "",
        report.enhanced_description,
        "",
        "## Severity Summary",
        "",
        f"| Severity | Count |",
        f"|----------|-------|",
        f"| 🔴 Critical | {sb.critical} |",
        f"| 🟠 High | {sb.high} |",
        f"| 🟡 Medium | {sb.medium} |",
        f"| 🟢 Low | {sb.low} |",
        f"| ℹ️ Info | {sb.info} |",
        "",
        "## Findings",
        "",
    ]

    if not report.findings:
        md_lines.append("*No significant findings recorded.*")
    else:
        for i, f in enumerate(report.findings, 1):
            severity_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢", "info": "ℹ️"}.get(f.severity, "")
            md_lines += [
                f"### {i}. {severity_icon} {f.title}",
                "",
                f"- **Tool:** {f.tool_name}",
                f"- **Severity:** {f.severity.upper()}",
                f"- **Stage:** `{f.stage_id}`",
                f"- **Detected:** {f.detected_at.strftime('%Y-%m-%d %H:%M') if f.detected_at else 'N/A'}",
            ]
            if f.cve:
                md_lines.append(f"- **CVE:** {f.cve}")
            md_lines += [
                "",
                f"**Description:** {f.description}",
                "",
            ]
            if f.evidence:
                md_lines += [
                    "**Evidence (excerpt):**",
                    "```",
                    f.evidence[:500],
                    "```",
                    "",
                ]
            if f.remediation:
                md_lines.append(f"**Remediation:** {f.remediation}")
                md_lines.append("")

    md_lines += [
        "## Stage Execution Summary",
        "",
        "| Stage | Status | Steps |",
        "|-------|--------|-------|",
    ]
    for stage in report.stages_summary:
        md_lines.append(f"| {stage.label} | `{stage.status}` | {len(stage.steps)} |")

    return "\n".join(md_lines)
