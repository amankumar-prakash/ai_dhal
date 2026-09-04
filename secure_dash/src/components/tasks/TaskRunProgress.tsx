import { useEffect, useMemo, useRef, useState } from "react";
import { Eyebrow } from "@/components/sd/primitives";
import { duration } from "@/lib/security";
import { LIVE_JOB, kindTone, progressLines } from "@/lib/task-logs";
import type { Task } from "@/lib/rbac-types";
import type { TaskResults } from "@/lib/tasks-api";

export function formatClock(totalSeconds: number): string {
  const s = Math.max(0, Math.round(totalSeconds));
  const m = Math.floor(s / 60);
  const r = s % 60;
  if (m >= 60) {
    const h = Math.floor(m / 60);
    return `${h}h ${m % 60}m`;
  }
  return `${m}m ${String(r).padStart(2, "0")}s`;
}

export function useTaskClock(
  startedAt: string | null | undefined,
  estimateSec: number,
  ticking: boolean,
  finishedAt?: string | null,
): { elapsedLabel: string; remainingLabel: string; elapsedSec: number; pct: number } {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (!ticking) return;
    const id = window.setInterval(() => setTick((n) => n + 1), 1000);
    return () => window.clearInterval(id);
  }, [ticking]);

  const elapsedSec = useMemo(() => {
    if (!startedAt) return 0;
    const end = finishedAt ? new Date(finishedAt).getTime() : Date.now();
    return Math.max(0, Math.round((end - new Date(startedAt).getTime()) / 1000));
  }, [startedAt, finishedAt, tick]);

  const remaining = Math.max(0, estimateSec - elapsedSec);
  const over = elapsedSec > estimateSec;
  const pct = estimateSec <= 0 ? 0 : Math.min(ticking ? 95 : 100, (elapsedSec / estimateSec) * 100);

  return {
    elapsedLabel: startedAt ? duration(startedAt, ticking ? null : finishedAt ?? new Date().toISOString()) : "—",
    remainingLabel: over ? `over by ${formatClock(elapsedSec - estimateSec)}` : formatClock(remaining),
    elapsedSec,
    pct,
  };
}

export function TaskRunProgress({
  task,
  results,
  stopped,
}: {
  task: Task;
  results: TaskResults | undefined;
  stopped?: boolean;
}) {
  const job = results?.job ?? null;
  const jobStatus = job?.status;
  const running = task.status === "in_progress" && (!jobStatus || LIVE_JOB.has(jobStatus));
  const progress = results?.progress ?? [];
  const tools = results?.tools ?? [];
  const estimate =
    job?.estimated_duration_seconds && job.estimated_duration_seconds > 0
      ? job.estimated_duration_seconds
      : 900;
  const processEta = [...progress]
    .reverse()
    .find((p) => p.kind === "process" && p.meta && p.meta.eta != null);
  const clock = useTaskClock(
    task.started_at,
    estimate,
    running,
    job?.finished_at ?? (stopped ? new Date().toISOString() : null),
  );
  const logRef = useRef<HTMLDivElement>(null);

  const lines = useMemo(() => progressLines(progress, tools), [progress, tools]);

  const current = [...lines].reverse().find((l) => l.kind === "process" || l.kind === "tool");

  useEffect(() => {
    const el = logRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [lines.length]);

  const header = stopped
    ? "Stopped"
    : `Run in progress${jobStatus ? ` · job ${jobStatus}` : ""}`;

  return (
    <div
      className="mt-4 rounded-sm p-3"
      style={{
        background: "var(--surface-raised)",
        border: "1px solid var(--border-hairline)",
      }}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          {running && (
            <span className="live-dot size-2 rounded-full" style={{ background: "var(--accent-ember)" }} />
          )}
          <span className="text-sm">{header}</span>
        </div>
        {current && (
          <span className="micro mono truncate" style={{ color: "var(--text-secondary)", maxWidth: "60%" }}>
            {current.message}
          </span>
        )}
      </div>
      {processEta?.meta?.eta != null && running && (
        <p className="micro mt-1" style={{ color: "var(--text-muted)" }}>
          Current tool remaining {String(processEta.meta.eta)}
        </p>
      )}
      <div
        ref={logRef}
        className="mono mt-3 max-h-[320px] min-h-[160px] overflow-y-auto rounded-sm p-3 text-[12px] leading-5"
        style={{
          background: "var(--bg-base)",
          border: "1px solid var(--border-hairline)",
          color: "var(--text-secondary)",
        }}
      >
        {lines.length === 0 ? (
          <div style={{ color: "var(--text-muted)" }}>
            HexStrike tools report here as they run. Attack Chain and Patches unlock when the job completes.
          </div>
        ) : (
          lines.map((line, i) => (
            <div key={line.id ?? `${line.kind}-${i}`}>
              <span style={{ color: kindTone(line.kind) }}>[{line.kind}] </span>
              {line.message}
            </div>
          ))
        )}
      </div>
      <span className="mt-3 block h-0.5 w-full overflow-hidden" style={{ background: "var(--surface)" }}>
        <span
          className="block h-full"
          style={{
            width: `${clock.pct}%`,
            background: "var(--accent-ember)",
            transition: "width 0.4s linear",
          }}
        />
      </span>
    </div>
  );
}

export function TaskRunClock({
  task,
  results,
  ticking,
}: {
  task: Task;
  results: TaskResults | undefined;
  ticking: boolean;
}) {
  const estimate = results?.job?.estimated_duration_seconds || 900;
  const clock = useTaskClock(task.started_at, estimate, ticking, results?.job?.finished_at);
  return (
    <div>
      <Eyebrow>Elapsed</Eyebrow>
      <div className="mono mt-1">{clock.elapsedLabel}</div>
      <div className="mt-2">
        <Eyebrow>Est.</Eyebrow>
      </div>
      <div className="mono mt-1">{clock.remainingLabel}</div>
    </div>
  );
}
