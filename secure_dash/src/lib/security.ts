import { queryOptions } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

export type Severity = "critical" | "high" | "medium" | "low" | "info";
export type ThreatStatus =
  "new" | "investigating" | "resolved" | "blocked" | "blocked_by_guardrail";
export type ScanStatus = "queued" | "running" | "completed" | "failed";
export type Stage = "recon" | "initial_access" | "execution" | "persistence" | "exfiltration";

export const SEVERITIES: Severity[] = ["critical", "high", "medium", "low", "info"];

export const severityLabel: Record<Severity, string> = {
  critical: "Critical",
  high: "High",
  medium: "Medium",
  low: "Low",
  info: "Info",
};

export function severityColor(s: Severity): string {
  return `var(--severity-${s})`;
}

export function severityRank(s: Severity): number {
  return SEVERITIES.indexOf(s);
}

export const threatStatusLabel: Record<ThreatStatus, string> = {
  new: "New",
  investigating: "Investigating",
  resolved: "Resolved",
  blocked: "Blocked",
  blocked_by_guardrail: "Guardrail block",
};

export const stageLabel: Record<Stage, string> = {
  recon: "Recon",
  initial_access: "Initial Access",
  execution: "Execution",
  persistence: "Persistence",
  exfiltration: "Exfiltration",
};

export const STAGES: Stage[] = [
  "recon",
  "initial_access",
  "execution",
  "persistence",
  "exfiltration",
];

/* ---------- formatting ---------- */

export function relTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const diff = Date.now() - new Date(iso).getTime();
  const s = Math.max(0, Math.round(diff / 1000));
  if (s < 60) return `${s}s ago`;
  const m = Math.round(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 48) return `${h}h ago`;
  return `${Math.round(h / 24)}d ago`;
}

export function absTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toISOString().replace("T", " ").slice(0, 19) + "Z";
}

export function duration(fromIso: string, toIso?: string | null): string {
  const end = toIso ? new Date(toIso).getTime() : Date.now();
  const total = Math.max(0, Math.round((end - new Date(fromIso).getTime()) / 1000));
  const m = Math.floor(total / 60);
  const s = total % 60;
  if (m >= 60) {
    const h = Math.floor(m / 60);
    return `${h}h ${m % 60}m`;
  }
  return `${m}m ${String(s).padStart(2, "0")}s`;
}

/* ---------- rows ---------- */

export type Asset = {
  id: string;
  name: string;
  hostname: string;
  ip_address: string;
  kind: string;
  criticality: Severity;
};

export type TeamSide = "red" | "blue";

export type Finding = {
  id: string;
  scan_id: string | null;
  asset_id: string | null;
  cve: string | null;
  title: string;
  severity: Severity;
  cvss: number;
  status: string;
  remediation: string | null;
  evidence: Array<{ tool: string; output: string }>;
  detected_at: string;
  resolved_at: string | null;
  team?: TeamSide | null;
};

export type ThreatEvent = {
  id: string;
  scan_id: string | null;
  asset_id: string | null;
  finding_id: string | null;
  technique: string;
  technique_name: string | null;
  description: string;
  source_ip: string;
  severity: Severity;
  status: ThreatStatus;
  source_tag: string;
  raw_payload: Record<string, unknown>;
  occurred_at: string;
  team?: TeamSide | null;
};

export type Scan = {
  id: string;
  target: string;
  asset_id: string | null;
  profile: string;
  status: ScanStatus;
  started_at: string;
  finished_at: string | null;
  findings_count: number;
  team?: TeamSide;
};

export type Patch = {
  id: string;
  finding_id: string;
  asset_id: string | null;
  title: string;
  playbook: string;
  status: string;
  evidence: unknown[];
  applied_at: string | null;
  created_at?: string;
};

export type ChainStep = {
  id: string;
  chain_id: string;
  stage: Stage;
  sequence: number;
  title: string;
  severity: Severity;
  threat_event_id: string | null;
  finding_id: string | null;
};

/* ---------- queries (platform API) ---------- */

function withTeam(path: string, team?: TeamSide | "all"): string {
  if (!team || team === "all") return path;
  return `${path}?team=${team}`;
}

export const assetsQuery = queryOptions({
  queryKey: ["assets"],
  queryFn: () => apiFetch<Asset[]>("/assets"),
});

export function findingsQueryOptions(team?: TeamSide | "all") {
  return queryOptions({
    queryKey: ["findings", team ?? "all"],
    queryFn: () => apiFetch<Finding[]>(withTeam("/findings", team)),
  });
}

export const findingsQuery = findingsQueryOptions();

export function eventsQueryOptions(team?: TeamSide | "all") {
  return queryOptions({
    queryKey: ["threat_events", team ?? "all"],
    queryFn: () => apiFetch<ThreatEvent[]>(withTeam("/threat-events", team)),
  });
}

export const eventsQuery = eventsQueryOptions();

export function scansQueryOptions(team?: TeamSide | "all") {
  return queryOptions({
    queryKey: ["scans", team ?? "all"],
    queryFn: () => apiFetch<Scan[]>(withTeam("/scans", team)),
  });
}

export const scansQuery = scansQueryOptions();

export const chainStepsQuery = queryOptions({
  queryKey: ["attack_chain_steps"],
  queryFn: async () => {
    const chains = await apiFetch<{ id: string }[]>("/attack-chains");
    const steps: ChainStep[] = [];
    for (const c of chains) {
      const part = await apiFetch<ChainStep[]>(`/attack-chains/${c.id}/steps`);
      steps.push(...part);
    }
    return steps;
  },
});

export const patchesQuery = queryOptions({
  queryKey: ["patches"],
  queryFn: () => apiFetch<Patch[]>("/patches"),
});

/* ---------- derived metrics ---------- */

export function riskScore(findings: Finding[], assetCount: number): number {
  const open = findings.filter((f) => !f.resolved_at);
  if (!open.length || !assetCount) return 0;
  const k = 3.2;
  const sum = open.reduce((acc, f) => {
    const ageDays = (Date.now() - new Date(f.detected_at).getTime()) / 86400000;
    const recency = Math.max(0.35, 1 - ageDays / 45);
    return acc + Number(f.cvss) * recency;
  }, 0);
  return Math.min(100, Math.max(0, Math.round((sum / assetCount) * k)));
}

export function mttrHours(findings: Finding[]): number | null {
  const closed = findings.filter((f) => f.resolved_at);
  if (!closed.length) return null;
  const total = closed.reduce(
    (acc, f) =>
      acc + (new Date(f.resolved_at!).getTime() - new Date(f.detected_at).getTime()) / 3600000,
    0,
  );
  return Math.round((total / closed.length) * 10) / 10;
}

export function severityCounts(findings: Finding[]): Record<Severity, number> {
  const base: Record<Severity, number> = {
    critical: 0,
    high: 0,
    medium: 0,
    low: 0,
    info: 0,
  };
  for (const f of findings) if (!f.resolved_at) base[f.severity] += 1;
  return base;
}

/** Deterministic 30-day open-finding trend derived from detection dates. */
export function trend30d(findings: Finding[]): { day: number; value: number }[] {
  const out: { day: number; value: number }[] = [];
  for (let d = 29; d >= 0; d--) {
    const cutoff = Date.now() - d * 86400000;
    const value = findings.filter((f) => {
      const det = new Date(f.detected_at).getTime();
      const res = f.resolved_at ? new Date(f.resolved_at).getTime() : Infinity;
      return det <= cutoff && res > cutoff;
    }).length;
    out.push({ day: 29 - d, value });
  }
  return out;
}
