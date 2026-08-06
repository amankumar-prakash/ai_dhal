import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createJob } from "@/lib/api-client";
import { linkJobToTask } from "@/lib/tasks-api";
import { assetsQuery, type TeamSide } from "@/lib/security";
import { ErrorBanner, Eyebrow, Panel } from "@/components/sd/primitives";

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

/** Starts a platform job via `POST /jobs`; optionally links the job back onto a task. */
export function ToolLauncher({ team, taskId }: { team: TeamSide; taskId?: string }) {
  const qc = useQueryClient();
  const assets = useQuery(assetsQuery);
  const [selected, setSelected] = useState<string[]>([]);
  const [profile, setProfile] = useState(PROFILES[team][0].value);
  const [lastJobId, setLastJobId] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: async () => {
      const job = await createJob({ team, profile, asset_ids: selected });
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

  return (
    <Panel className="p-4">
      <Eyebrow>Launch {team === "red" ? "Red" : "Blue"} job</Eyebrow>
      {mutation.isError && (
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
          Linked to task <span className="mono">{taskId}</span> — the job id attaches to it
          automatically.
        </p>
      )}
      <div className="mt-3 flex flex-wrap gap-2">
        {(assets.data ?? []).map((a) => {
          const on = selected.includes(a.id);
          return (
            <button
              key={a.id}
              onClick={() => setSelected((p) => (on ? p.filter((x) => x !== a.id) : [...p, a.id]))}
              className="micro rounded-sm px-2 py-1"
              style={{
                border: `1px solid ${on ? "var(--text-primary)" : "var(--border-hairline)"}`,
                color: on ? "var(--text-primary)" : "var(--text-secondary)",
                background: on ? "var(--surface)" : "transparent",
              }}
              aria-pressed={on}
            >
              {a.name}
            </button>
          );
        })}
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-3">
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
        <button
          disabled={!selected.length || mutation.isPending}
          onClick={() => mutation.mutate()}
          className="rounded-sm px-3 py-2 text-sm font-medium disabled:opacity-50"
          style={{ background: "var(--accent-ember)", color: "var(--bg-base)" }}
        >
          {mutation.isPending ? "Dispatching…" : "Start job"}
        </button>
      </div>
      {lastJobId && (
        <p className="mono micro mt-3" style={{ color: "var(--text-secondary)" }}>
          Job {lastJobId} dispatched — check Scan Report for progress.
        </p>
      )}
    </Panel>
  );
}
