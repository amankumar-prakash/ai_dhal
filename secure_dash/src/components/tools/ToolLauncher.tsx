import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createJob } from "@/lib/api-client";
import { linkJobToTask } from "@/lib/tasks-api";
import { type TeamSide } from "@/lib/security";
import { ErrorBanner, Eyebrow, Panel } from "@/components/sd/primitives";

/** Loose IP-or-hostname check just to gate the button; the API resolves the real asset. */
export function looksLikeTarget(value: string): boolean {
  const v = value.trim();
  if (!v) return false;
  const stripped = v.replace(/^\w+:\/\//, "").split("/")[0].split(":")[0];
  return /^[A-Za-z0-9.-]+$/.test(stripped) && stripped.includes(".") === true;
}

const PROFILES: Record<TeamSide, { value: string; label: string }[]> = {
  red: [
    { value: "surface-recon", label: "Surface recon" },
    { value: "defensive-validation", label: "Defensive validation" },
    { value: "deep-emulation", label: "Deep emulation" },
  ],
  blue: [
    { value: "vuln-scan", label: "Vuln scan" },
    { value: "monitor", label: "Monitor tick" },
  ],
};

type Props = {
  team: TeamSide;
  taskId?: string;
  /** When true, Start job starts the HexStrike chat instead of dispatching a platform job. */
  chatMode?: boolean;
  target?: string;
  onTargetChange?: (value: string) => void;
  onStartChat?: () => void | Promise<void>;
  chatStarting?: boolean;
  chatActive?: boolean;
};

/** Starts a platform job via `POST /jobs`, or (chatMode) starts the supervised chat. */
export function ToolLauncher({
  team,
  taskId,
  chatMode = false,
  target: controlledTarget,
  onTargetChange,
  onStartChat,
  chatStarting = false,
  chatActive = false,
}: Props) {
  const qc = useQueryClient();
  const [internalTarget, setInternalTarget] = useState("");
  const [profile, setProfile] = useState(PROFILES[team][0].value);
  const [lastJobId, setLastJobId] = useState<string | null>(null);

  const target = controlledTarget ?? internalTarget;
  const setTarget = onTargetChange ?? setInternalTarget;

  const mutation = useMutation({
    mutationFn: async () => {
      const job = await createJob({ team, profile, target: target.trim() });
      if (taskId) {
        await linkJobToTask(taskId, job.id);
        qc.invalidateQueries({ queryKey: ["tasks", "detail", taskId] });
      }
      return job;
    },
    onSuccess: (job) => {
      setLastJobId(job.id);
      qc.invalidateQueries({ queryKey: ["scans"] });
    },
  });

  const canStart = looksLikeTarget(target);
  const starting = chatMode ? chatStarting : mutation.isPending;
  const startDisabled = !canStart || starting || (chatMode && chatActive);

  return (
    <Panel className="p-4">
      <Eyebrow>Launch {team === "red" ? "Red" : "Blue"} job</Eyebrow>
      {mutation.isError && !chatMode && (
        <div className="mt-3">
          <ErrorBanner
            message={
              mutation.error instanceof Error ? mutation.error.message : "Could not start job"
            }
          />
        </div>
      )}
      {taskId && (
        <p className="micro mt-2" style={{ color: "var(--text-muted)" }}>
          Linked to task <span className="mono">{taskId}</span>
          {chatMode ? " — chat session attaches to it." : " — the job id attaches to it automatically."}
        </p>
      )}
      <div className="mt-3">
        <label className="micro block" style={{ color: "var(--text-secondary)" }}>
          Target (IP address or hostname)
          <input
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            placeholder="e.g. 10.0.0.5 or host.corp.internal"
            className="mono mt-1 block w-full rounded-sm px-3 py-2 text-sm"
            style={{
              background: "var(--surface-raised)",
              border: "1px solid var(--border-hairline)",
              color: "var(--text-primary)",
            }}
          />
        </label>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-3">
        {!chatMode && (
          <select
            value={profile}
            onChange={(e) => setProfile(e.target.value)}
            className="micro rounded-sm px-2 py-1"
            style={{
              background: "var(--surface-raised)",
              border: "1px solid var(--border-hairline)",
              color: "var(--text-secondary)",
            }}
          >
            {PROFILES[team].map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </select>
        )}
        <button
          disabled={startDisabled}
          onClick={() => {
            if (chatMode) void onStartChat?.();
            else mutation.mutate();
          }}
          className="rounded-sm px-3 py-2 text-sm font-medium disabled:opacity-50"
          style={{ background: "var(--accent-ember)", color: "var(--bg-base)" }}
        >
          {starting ? (chatMode ? "Starting…" : "Dispatching…") : "Start job"}
        </button>
      </div>
      {chatMode && (
        <p className="micro mt-3" style={{ color: "var(--text-muted)" }}>
          Starts a HexStrike chat session scoped to this target. Approve each tool call in the
          terminal below.
        </p>
      )}
      {!chatMode && lastJobId && (
        <p className="mono micro mt-3" style={{ color: "var(--text-secondary)" }}>
          Job {lastJobId} dispatched — check Scan Report for progress.
        </p>
      )}
    </Panel>
  );
}
