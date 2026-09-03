import { useState } from "react";
import { Crosshair, Download, KeyRound, LogIn, Terminal } from "lucide-react";
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
import type { DummyChainRecord } from "@/lib/task-runner-dummy";
import { EmptyState, Eyebrow, Panel, SeverityChip } from "@/components/sd/primitives";

const STAGE_ICON: Record<Stage, typeof Crosshair> = {
  recon: Crosshair,
  initial_access: LogIn,
  execution: Terminal,
  persistence: KeyRound,
  exfiltration: Download,
};

export function TaskAttackChain({ steps }: { steps: DummyChainRecord[] }) {
  const [selected, setSelected] = useState<Stage | null>(STAGES[0]);

  const byStage = new Map<Stage, DummyChainRecord[]>();
  for (const stage of STAGES) {
    byStage.set(
      stage,
      steps.filter((s) => s.stage === stage).sort((a, b) => a.sequence - b.sequence),
    );
  }

  const topSeverity = (stage: Stage): Severity | null => {
    const list = byStage.get(stage) ?? [];
    if (!list.length) return null;
    return list.reduce<Severity>(
      (acc, s) => (severityRank(s.severity) < severityRank(acc) ? s.severity : acc),
      "info",
    );
  };

  const panelSteps = selected ? (byStage.get(selected) ?? []) : [];

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
        {STAGES.map((stage, i) => {
          const list = byStage.get(stage) ?? [];
          const sev = topSeverity(stage);
          const critical = sev === "critical";
          const isSelected = selected === stage;
          const Icon = STAGE_ICON[stage];
          const weight = Math.min(4, 1 + Math.floor(list.length / 2));
          return (
            <div key={stage} className="flex flex-1 flex-col items-stretch xl:flex-row xl:items-center">
              <button
                onClick={() => setSelected(isSelected ? null : stage)}
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
                  <span className="flex-1 text-sm font-medium">{stageLabel[stage]}</span>
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
              {i < STAGES.length - 1 && (
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
            <Eyebrow>{stageLabel[selected]} — linked records</Eyebrow>
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
                  <SeverityChip severity={step.severity} />
                  <div className="min-w-0 flex-1">
                    <div className="text-sm">{step.title}</div>
                    <div className="mono micro mt-1" style={{ color: "var(--text-muted)" }}>
                      {step.technique} · {step.source_ip} · {relTime(step.occurred_at)}
                      {step.cve ? ` · ${step.cve} (CVSS ${step.cvss?.toFixed(1)})` : ""}
                    </div>
                  </div>
                  <span className="micro" style={{ color: severityColor(step.severity) }}>
                    {severityLabel[step.severity]}
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
