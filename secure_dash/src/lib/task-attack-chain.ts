import { STAGES, type Stage } from "@/lib/security";
import type { TaskChainStep, TaskResults, TaskToolRun } from "@/lib/tasks-api";

export type ChainCategory = "tools" | "findings" | Stage;

export type ChainDetailItem = {
  id: string;
  title: string;
  severity: string;
  sourceTool?: string | null;
  evidence?: string;
  startedAt?: string | null;
  finishedAt?: string | null;
  createdAt?: string | null;
  exitCode?: number | null;
  command?: string | null;
  findings: Array<{ id: string; title: string; severity: string }>;
  remediation?: string | null;
};

export function asSeverity(
  value: string | undefined,
): "critical" | "high" | "medium" | "low" | "info" {
  if (value === "critical" || value === "high" || value === "medium" || value === "low" || value === "info") {
    return value;
  }
  return "info";
}

export function categoryOf(step: TaskChainStep): ChainCategory {
  const cat = (step.category || "").toLowerCase();
  if (cat === "tools" || cat === "findings") return cat;
  if (STAGES.includes(step.stage as Stage)) return step.stage as Stage;
  return "recon";
}

export function formatEvidence(evidence: unknown): string {
  if (evidence == null) return "";
  if (typeof evidence === "string") return evidence.trim();
  if (Array.isArray(evidence)) {
    return evidence
      .map((item) => {
        if (typeof item === "string") return item;
        if (item && typeof item === "object") {
          const rec = item as Record<string, unknown>;
          if (typeof rec.output === "string") return rec.output;
          if (typeof rec.evidence === "string") return rec.evidence;
        }
        return "";
      })
      .filter(Boolean)
      .join("\n");
  }
  if (typeof evidence === "object") {
    const rec = evidence as Record<string, unknown>;
    if (typeof rec.output === "string") return rec.output;
    if (typeof rec.stdout === "string") return rec.stdout;
    try {
      return JSON.stringify(evidence);
    } catch {
      return String(evidence);
    }
  }
  return String(evidence);
}

export function findingsForTool(
  toolName: string,
  findings: TaskResults["findings"] | undefined,
): TaskResults["findings"] {
  const name = toolName.trim().toLowerCase();
  if (!name) return [];
  return (findings ?? []).filter((f) => (f.source_tool || "").trim().toLowerCase() === name);
}

export function stepsFromResults(results: TaskResults): TaskChainStep[] {
  if (results.chain?.steps?.length) return results.chain.steps;
  const fromTools: TaskChainStep[] = (results.tools ?? []).map((t, i) => ({
    id: t.id,
    stage: "recon",
    sequence: i + 1,
    title: t.tool_name,
    severity: "info",
    category: "tools",
    source_tool: t.tool_name,
    evidence: t.command_summary,
    created_at: t.finished_at ?? t.started_at ?? t.created_at,
  }));
  const fromFindings: TaskChainStep[] = (results.findings ?? []).map((f, i) => ({
    id: f.id,
    stage: "recon",
    sequence: fromTools.length + i + 1,
    title: f.title,
    severity: f.severity,
    category: "findings",
    source_tool: f.source_tool,
    finding_id: f.id,
    evidence: formatEvidence(f.evidence) || undefined,
    created_at: f.created_at,
  }));
  return [...fromTools, ...fromFindings];
}

function toolToDetail(tool: TaskToolRun, findings: TaskResults["findings"] | undefined): ChainDetailItem {
  const related = findingsForTool(tool.tool_name, findings);
  return {
    id: tool.id,
    title: tool.tool_name,
    severity: tool.exit_code != null && tool.exit_code !== 0 ? "high" : "info",
    sourceTool: tool.tool_name,
    evidence: formatEvidence(tool.raw_output) || tool.command_summary || "",
    startedAt: tool.started_at,
    finishedAt: tool.finished_at,
    createdAt: tool.created_at,
    exitCode: tool.exit_code,
    command: tool.command_summary,
    findings: related.map((f) => ({ id: f.id, title: f.title, severity: f.severity })),
  };
}

function findingToDetail(finding: TaskResults["findings"][number]): ChainDetailItem {
  return {
    id: finding.id,
    title: finding.title,
    severity: finding.severity,
    sourceTool: finding.source_tool,
    evidence: formatEvidence(finding.evidence),
    createdAt: finding.created_at,
    findings: [],
    remediation: finding.remediation ?? undefined,
  };
}

function stepToDetail(
  step: TaskChainStep,
  results: TaskResults | undefined,
  usedToolIds: Set<string>,
): ChainDetailItem {
  const tools = results?.tools ?? [];
  const byId = tools.find((t) => t.id === step.id);
  const name = (step.source_tool || "").trim().toLowerCase();
  const byName = !byId
    ? tools.find((t) => !usedToolIds.has(t.id) && t.tool_name.trim().toLowerCase() === name)
    : undefined;
  const tool = byId ?? byName;
  if (tool) usedToolIds.add(tool.id);

  const finding = (results?.findings ?? []).find((f) => f.id === step.finding_id);
  const related = tool
    ? findingsForTool(tool.tool_name, results?.findings)
    : step.source_tool
      ? findingsForTool(step.source_tool, results?.findings)
      : [];

  return {
    id: step.id,
    title: step.title,
    severity: step.severity,
    sourceTool: step.source_tool ?? tool?.tool_name,
    evidence: formatEvidence(finding?.evidence) || step.evidence || "",
    startedAt: tool?.started_at,
    finishedAt: tool?.finished_at,
    createdAt: step.created_at ?? tool?.created_at ?? finding?.created_at,
    exitCode: tool?.exit_code,
    command: tool?.command_summary ?? undefined,
    findings: related.map((f) => ({ id: f.id, title: f.title, severity: f.severity })),
    remediation: finding?.remediation ?? undefined,
  };
}

export function detailsForCategory(
  cat: ChainCategory,
  steps: TaskChainStep[],
  results?: TaskResults,
): ChainDetailItem[] {
  if (cat === "tools" && (results?.tools?.length ?? 0) > 0) {
    return (results?.tools ?? []).map((t) => toolToDetail(t, results?.findings));
  }
  if (cat === "findings" && (results?.findings?.length ?? 0) > 0) {
    return (results?.findings ?? []).map(findingToDetail);
  }
  const used = new Set<string>();
  return steps.map((step) => stepToDetail(step, results, used));
}
