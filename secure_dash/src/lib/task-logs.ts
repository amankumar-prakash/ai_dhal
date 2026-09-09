import type { TaskProgressEvent, TaskToolRun } from "@/lib/tasks-api";

export const LIVE_JOB = new Set(["queued", "dispatched", "running"]);

export function isLiveJobStatus(status?: string | null): boolean {
  return !!status && LIVE_JOB.has(status);
}

export function kindTone(kind: string): string {
  if (kind === "thinking") return "var(--text-muted)";
  if (kind === "tool") return "var(--accent-ember)";
  if (kind === "process") return "var(--text-secondary)";
  if (kind === "status") return "var(--text-primary)";
  return "var(--text-muted)";
}

export function progressLines(
  progress: TaskProgressEvent[] | undefined,
  tools: TaskToolRun[] | undefined,
): TaskProgressEvent[] {
  if (progress?.length) return progress;
  return (tools ?? []).map((t) => ({
    kind: "tool",
    message: t.command_summary ? `${t.tool_name} — ${t.command_summary}` : t.tool_name,
    created_at: t.finished_at ?? t.started_at,
  }));
}

export function formatRawOutput(raw: Record<string, unknown> | null | undefined): string {
  if (!raw || Object.keys(raw).length === 0) return "";
  const stdout = raw.stdout ?? raw.output ?? raw.text;
  if (typeof stdout === "string" && stdout.trim()) return stdout;
  try {
    return JSON.stringify(raw, null, 2);
  } catch {
    return String(raw);
  }
}

export function runHeadline(opts: {
  taskStatus: string;
  jobStatus?: string | null;
  stopped?: boolean;
}): { live: boolean; label: string } {
  const { taskStatus, jobStatus, stopped } = opts;
  const live = taskStatus === "in_progress" && (!jobStatus || LIVE_JOB.has(jobStatus));
  if (stopped || jobStatus === "cancelled") {
    return { live: false, label: "Last run — stopped" };
  }
  if (jobStatus === "failed") {
    return { live: false, label: "Last run — failed" };
  }
  if (live) {
    return { live: true, label: jobStatus ? `Live run · job ${jobStatus}` : "Live run" };
  }
  if (jobStatus === "completed" || taskStatus === "completed" || taskStatus === "reviewed" || taskStatus === "closed") {
    return { live: false, label: "Last run — completed" };
  }
  if (jobStatus) {
    return { live: false, label: `Last run · job ${jobStatus}` };
  }
  return { live: false, label: "No run yet" };
}
