import { useState } from "react";
import { ChevronDown, ChevronRight, Crosshair, Download, KeyRound, LogIn, Search, Terminal, Wrench } from "lucide-react";
import {
  duration,
  relTime,
  severityColor,
  severityLabel,
  severityRank,
  stageLabel,
  STAGES,
  type Severity,
  type Stage,
} from "@/lib/security";
import {
  asSeverity,
  categoryOf,
  detailsForCategory,
  stepsFromResults,
  type ChainCategory,
  type ChainDetailItem,
} from "@/lib/task-attack-chain";
import type { TaskChainStep, TaskResults } from "@/lib/tasks-api";
import { EmptyState, SeverityChip } from "@/components/sd/primitives";

export type { ChainCategory };

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

function runTimeLabel(item: ChainDetailItem): string {
  const start = item.startedAt || item.createdAt;
  if (!start && !item.finishedAt) return "Time not recorded";
  const parts: string[] = [];
  if (start) parts.push(relTime(start));
  if (item.startedAt && item.finishedAt) parts.push(`ran ${duration(item.startedAt, item.finishedAt)}`);
  else if (item.finishedAt) parts.push(`finished ${relTime(item.finishedAt)}`);
  return parts.join(" · ");
}

function DetailRows({
  category,
  items,
}: {
  category: ChainCategory;
  items: ChainDetailItem[];
}) {
  if (items.length === 0) {
    return (
      <p className="micro px-4 pb-4" style={{ color: "var(--text-muted)" }}>
        No activity recorded at this stage.
      </p>
    );
  }

  return (
    <ul className="border-t" style={{ borderColor: "var(--border-hairline)" }}>
      {items.map((item) => {
        const sev = asSeverity(item.severity);
        const failed = item.exitCode != null && item.exitCode !== 0;
        const ran = runTimeLabel(item);
        const meta =
          category === "tools"
            ? [item.command || "No command summary", ran].filter(Boolean).join(" · ")
            : [item.sourceTool ? `source ${item.sourceTool}` : "", ran !== "Time not recorded" ? ran : ""]
                .filter(Boolean)
                .join(" · ") || "—";
        return (
          <li
            key={item.id}
            className="border-b px-4 py-3 last:border-b-0"
            style={{ borderColor: "var(--border-hairline)" }}
          >
            <div className="flex flex-wrap items-start gap-2">
              {category !== "tools" && <SeverityChip severity={sev} />}
              <div className="min-w-0 flex-1">
                <div className="text-sm font-medium">{item.title}</div>
                <div className="mono micro mt-1" style={{ color: "var(--text-muted)" }}>
                  {meta}
                </div>
              </div>
              {category === "tools" ? (
                <span
                  className="mono micro"
                  style={{ color: failed ? "var(--accent-ember)" : "var(--text-secondary)" }}
                >
                  {item.exitCode == null ? "recorded" : `exit ${item.exitCode}`}
                </span>
              ) : (
                <span className="micro" style={{ color: severityColor(sev) }}>
                  {severityLabel[sev]}
                </span>
              )}
            </div>
            {item.evidence && category !== "tools" && (
              <pre
                className="mono mt-2 max-h-[160px] overflow-auto rounded-sm p-2 text-[12px] leading-5 whitespace-pre-wrap"
                style={{
                  background: "var(--bg-base)",
                  border: "1px solid var(--border-hairline)",
                  color: "var(--text-secondary)",
                }}
              >
                {item.evidence.slice(0, 800)}
              </pre>
            )}
            {item.remediation && (
              <p className="mt-2 text-sm" style={{ color: "var(--text-secondary)" }}>
                {item.remediation}
              </p>
            )}
            {category === "tools" && (
              <div className="mt-2">
                {item.findings.length === 0 ? (
                  <span className="micro" style={{ color: "var(--text-muted)" }}>
                    No findings from this tool
                  </span>
                ) : (
                  <ul className="flex flex-col gap-1">
                    {item.findings.map((f) => (
                      <li key={f.id} className="flex items-center gap-2">
                        <SeverityChip severity={asSeverity(f.severity)} variant="outline" />
                        <span className="text-sm">{f.title}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
}

export function TaskAttackChain({
  results,
  steps: stepsProp,
}: {
  results?: TaskResults;
  steps?: TaskChainStep[];
}) {
  const steps = stepsProp ?? (results ? stepsFromResults(results) : []);
  const [expanded, setExpanded] = useState<ChainCategory | null>(null);

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

  if (!steps.length) {
    return (
      <EmptyState
        icon={<Crosshair size={20} strokeWidth={1.5} />}
        label="No attack chain recorded for this task."
      />
    );
  }

  return (
    <div className="flex flex-col items-stretch gap-3">
      {categories.map((cat, i) => {
        const list = byCat.get(cat.id) ?? [];
        const sev = topSeverity(cat.id);
        const critical = sev === "critical";
        const isExpanded = expanded === cat.id;
        const Icon = cat.icon;
        const weight = Math.min(4, 1 + Math.floor(list.length / 2));
        const details = isExpanded ? detailsForCategory(cat.id, list, results) : [];
        const canExpand = list.length > 0;
        return (
          <div key={cat.id} className="flex flex-col items-stretch">
            <div
              className="w-full rounded-md"
              style={{
                background: isExpanded ? "var(--surface-raised)" : "var(--surface)",
                border: `1px solid ${isExpanded ? "var(--accent-ember)" : "var(--border-hairline)"}`,
                boxShadow: critical && !isExpanded ? "var(--glow-ember)" : undefined,
              }}
            >
              <button
                type="button"
                onClick={() => {
                  if (!canExpand) return;
                  setExpanded(isExpanded ? null : cat.id);
                }}
                className="w-full rounded-md p-4 text-left transition-colors duration-150 ease-out"
                aria-expanded={isExpanded}
                aria-controls={`attack-chain-${cat.id}`}
                disabled={!canExpand}
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
                <div className="mt-2 flex items-center gap-2">
                  {sev ? (
                    <>
                      <SeverityChip severity={sev} variant="outline" />
                      {isExpanded ? (
                        <ChevronDown size={14} strokeWidth={1.5} style={{ color: "var(--text-muted)" }} />
                      ) : (
                        <ChevronRight size={14} strokeWidth={1.5} style={{ color: "var(--text-muted)" }} />
                      )}
                    </>
                  ) : (
                    <span className="micro" style={{ color: "var(--text-muted)" }}>
                      No activity
                    </span>
                  )}
                </div>
              </button>
              {isExpanded && (
                <div id={`attack-chain-${cat.id}`}>
                  <DetailRows category={cat.id} items={details} />
                </div>
              )}
            </div>
            {i < categories.length - 1 && (
              <div className="flex shrink-0 items-center justify-center py-1" aria-hidden>
                <svg width="28" height="28" viewBox="0 0 28 28">
                  <line x1="14" y1="2" x2="14" y2="20" stroke="var(--border-hairline)" strokeWidth={weight} />
                  <path d="M9 20 L14 26 L19 20 Z" fill="var(--border-hairline)" />
                </svg>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
