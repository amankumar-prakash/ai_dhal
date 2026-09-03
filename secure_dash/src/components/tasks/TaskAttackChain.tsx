import { useState } from "react";
import { Crosshair, Download, KeyRound, LogIn, Search, Terminal, Wrench } from "lucide-react";
import {
  relTime,
  severityColor,
  severityLabel,
  severityRank,
  stageLabel,
  STAGES,
  type Severity,
  type Stage,
} from "@/lib/security";
import type { TaskChainStep, TaskResults } from "@/lib/tasks-api";
import { EmptyState, Eyebrow, Panel, SeverityChip } from "@/components/sd/primitives";

export type ChainCategory = "tools" | "findings" | Stage;

const EXTRA: { id: ChainCategory; label: string; icon: typeof Wrench }[] = [
  { id: "tools", label: "Tools", icon: Wrench },
  { id: "findings", label: "Findings", icon: Search },
];

const STAGE_ICON: Record<Stage, typeof Crosshair> = {
  recon: Crosshair,
  initial_access: LogIn,
  execution: Terminal,
  persistence: KeyRound,
  exfiltration: Download,
};

function asSeverity(value: string | undefined): Severity {
  if (value === "critical" || value === "high" || value === "medium" || value === "low" || value === "info") {
    return value;
  }
  return "info";
}

function categoryOf(step: TaskChainStep): ChainCategory {
  const cat = (step.category || "").toLowerCase();
  if (cat === "tools" || cat === "findings") return cat;
  if (STAGES.includes(step.stage as Stage)) return step.stage as Stage;
  return "recon";
}

function stepsFromResults(results: TaskResults): TaskChainStep[] {
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
    evidence: typeof f.evidence === "string" ? f.evidence : undefined,
  }));
  return [...fromTools, ...fromFindings];
}

export function TaskAttackChain({
  results,
  steps: stepsProp,
}: {
  results?: TaskResults;
  steps?: TaskChainStep[];
}) {
  const steps = stepsProp ?? (results ? stepsFromResults(results) : []);
  const [selected, setSelected] = useState<ChainCategory | null>("tools");

  const categories: { id: ChainCategory; label: string; icon: typeof Wrench }[] = [
    ...EXTRA,
    ...STAGES.map((s) => ({ id: s as ChainCategory, label: stageLabel[s], icon: STAGE_ICON[s] })),
  ];

  const byCat = new Map<ChainCategory, TaskChainStep[]>();
  for (const c of categories) byCat.set(c.id, []);
  for (const step of steps) {
    const cat = categoryOf(step);
    const list = byCat.get(cat) ?? [];
    list.push(step);
    byCat.set(cat, list);
  }
  for (const list of byCat.values()) {
    list.sort((a, b) => a.sequence - b.sequence);
  }

  const topSeverity = (cat: ChainCategory): Severity | null => {
    const list = byCat.get(cat) ?? [];
    if (!list.length) return null;
    return list.reduce<Severity>(
      (acc, s) => (severityRank(asSeverity(s.severity)) < severityRank(acc) ? asSeverity(s.severity) : acc),
      "info",
    );
  };

  const panelSteps = selected ? (byCat.get(selected) ?? []) : [];

  if (!steps.length) {
    return (
      <EmptyState
        icon={<Crosshair size={20} strokeWidth={1.5} />}
        label="No attack chain recorded for this task."
      />
    );
  }

  return (
    <div>
      <div className="flex flex-col items-stretch gap-3 xl:flex-row xl:items-center">
        {categories.map((cat, i) => {
          const list = byCat.get(cat.id) ?? [];
          const sev = topSeverity(cat.id);
          const critical = sev === "critical";
          const isSelected = selected === cat.id;
          const Icon = cat.icon;
          const weight = Math.min(4, 1 + Math.floor(list.length / 2));
          return (
            <div key={cat.id} className="flex flex-1 flex-col items-stretch xl:flex-row xl:items-center">
              <button
                onClick={() => setSelected(isSelected ? null : cat.id)}
                className="w-full rounded-md p-4 text-left transition-colors duration-150 ease-out"
                style={{
                  background: isSelected ? "var(--surface-raised)" : "var(--surface)",
                  border: `1px solid ${isSelected ? "var(--accent-ember)" : "var(--border-hairline)"}`,
                  boxShadow: critical && !isSelected ? "var(--glow-ember)" : undefined,
                }}
                aria-pressed={isSelected}
              >
                <div className="flex items-center gap-2">
                  <Icon size={20} strokeWidth={1.5} style={{ color: "var(--text-secondary)" }} />
                  <span className="flex-1 text-sm font-medium">{cat.label}</span>
                  <span
                    className="mono micro rounded-sm px-1.5 py-0.5"
                    style={{
                      border: "1px solid var(--border-hairline)",
                      color: "var(--text-secondary)",
                    }}
                  >
                    {list.length}
                  </span>
                </div>
                <div className="mt-2">
                  {sev ? (
                    <SeverityChip severity={sev} variant="outline" />
                  ) : (
                    <span className="micro" style={{ color: "var(--text-muted)" }}>
                      No activity
                    </span>
                  )}
                </div>
              </button>
              {i < categories.length - 1 && (
                <div className="flex shrink-0 items-center justify-center py-1 xl:px-1 xl:py-0" aria-hidden>
                  <svg width="28" height="28" viewBox="0 0 28 28" className="hidden xl:block">
                    <line x1="2" y1="14" x2="20" y2="14" stroke="var(--border-hairline)" strokeWidth={weight} />
                    <path d="M20 9 L26 14 L20 19 Z" fill="var(--border-hairline)" />
                  </svg>
                  <svg width="28" height="28" viewBox="0 0 28 28" className="xl:hidden">
                    <line x1="14" y1="2" x2="14" y2="20" stroke="var(--border-hairline)" strokeWidth={weight} />
                    <path d="M9 20 L14 26 L19 20 Z" fill="var(--border-hairline)" />
                  </svg>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {selected && (
        <Panel className="mt-6">
          <div
            className="flex items-center justify-between border-b p-4"
            style={{ borderColor: "var(--border-hairline)" }}
          >
            <Eyebrow>
              {categories.find((c) => c.id === selected)?.label} — linked records
            </Eyebrow>
            <button className="micro" style={{ color: "var(--text-muted)" }} onClick={() => setSelected(null)}>
              Close
            </button>
          </div>
          {panelSteps.length === 0 ? (
            <EmptyState
              icon={<Crosshair size={20} strokeWidth={1.5} />}
              label="No activity recorded at this stage."
            />
          ) : (
            <ul>
              {panelSteps.map((step) => (
                <li
                  key={step.id}
                  className="flex flex-wrap items-start gap-3 border-b px-4 py-3 last:border-b-0"
                  style={{ borderColor: "var(--border-hairline)" }}
                >
                  <span className="mono micro" style={{ color: "var(--text-muted)" }}>
                    #{step.sequence}
                  </span>
                  <SeverityChip severity={asSeverity(step.severity)} />
                  <div className="min-w-0 flex-1">
                    <div className="text-sm">{step.title}</div>
                    <div className="mono micro mt-1" style={{ color: "var(--text-muted)" }}>
                      {step.source_tool ? `${step.source_tool} · ` : ""}
                      {step.evidence ? String(step.evidence).slice(0, 160) : relTime(undefined)}
                    </div>
                  </div>
                  <span className="micro" style={{ color: severityColor(asSeverity(step.severity)) }}>
                    {severityLabel[asSeverity(step.severity)]}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      )}
    </div>
  );
}
