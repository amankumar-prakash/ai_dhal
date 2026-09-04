import { useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, GitBranch, Play, ScrollText, ShieldAlert, ShieldCheck, Square, Swords } from "lucide-react";
import { relTime } from "@/lib/security";
import { resultsUnlocked } from "@/lib/tasks";
import { applyTaskPatch, taskQuery, taskResultsQuery, transitionTask } from "@/lib/tasks-api";
import { StatusPill } from "@/components/tasks/TaskBoard";
import { TaskAttackChain } from "@/components/tasks/TaskAttackChain";
import { TaskLogs } from "@/components/tasks/TaskLogs";
import { TaskPatches } from "@/components/tasks/TaskPatches";
import { TaskRunClock, TaskRunProgress } from "@/components/tasks/TaskRunProgress";
import { ErrorBanner, Eyebrow, PageHeader, Panel } from "@/components/sd/primitives";

export const Route = createFileRoute("/_authenticated/tasks/$taskId")({
  head: () => ({ meta: [{ title: "Task — SecureDash" }] }),
  component: TaskDetailPage,
});

type DetailTab = "overview" | "logs" | "attack-chain" | "patches";

function TaskDetailPage() {
  const { taskId } = Route.useParams();
  const qc = useQueryClient();
  const [tab, setTab] = useState<DetailTab>("overview");

  const taskQ = useQuery({
    ...taskQuery(taskId),
    refetchInterval: (q) => (q.state.data?.status === "in_progress" ? 3000 : false),
  });
  const resultsQ = useQuery({
    ...taskResultsQuery(taskId),
    refetchInterval: (q) => {
      const status = q.state.data?.job?.status ?? taskQ.data?.status;
      return status === "running" || status === "dispatched" || status === "queued" || status === "in_progress"
        ? 1000
        : false;
    },
  });

  const startMut = useMutation({
    mutationFn: () => transitionTask(taskId, "start"),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tasks"] });
      qc.invalidateQueries({ queryKey: ["tasks", "detail", taskId] });
      qc.invalidateQueries({ queryKey: ["tasks", "results", taskId] });
      setTab("overview");
    },
  });

  const stopMut = useMutation({
    mutationFn: () => transitionTask(taskId, "stop"),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tasks"] });
      qc.invalidateQueries({ queryKey: ["tasks", "detail", taskId] });
      qc.invalidateQueries({ queryKey: ["tasks", "results", taskId] });
    },
  });

  const applyMut = useMutation({
    mutationFn: (patchId: string) => applyTaskPatch(patchId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tasks", "results", taskId] });
      qc.invalidateQueries({ queryKey: ["patches"] });
    },
  });

  const task = taskQ.data;
  const results = resultsQ.data;
  const unlocked = task ? resultsUnlocked(task.status) : false;

  if (taskQ.isError) {
    return (
      <div className="mx-auto max-w-[900px]">
        <Link
          to="/tasks"
          className="micro mb-3 inline-flex items-center gap-1"
          style={{ color: "var(--text-secondary)" }}
        >
          <ArrowLeft size={12} strokeWidth={1.5} /> Back to Task Runner
        </Link>
        <ErrorBanner
          message={taskQ.error instanceof Error ? taskQ.error.message : "Task not found or no longer available."}
        />
      </div>
    );
  }

  if (!task) {
    return (
      <div className="mx-auto max-w-[900px]">
        <Link
          to="/tasks"
          className="micro mb-3 inline-flex items-center gap-1"
          style={{ color: "var(--text-secondary)" }}
        >
          <ArrowLeft size={12} strokeWidth={1.5} /> Back to Task Runner
        </Link>
        <p className="micro" style={{ color: "var(--text-muted)" }}>
          Loading task…
        </p>
      </div>
    );
  }

  const jobError = results?.job?.error;
  const jobStatus = results?.job?.status;
  const jobFailed = jobStatus === "failed";
  const jobLive = !jobStatus || jobStatus === "queued" || jobStatus === "dispatched" || jobStatus === "running";
  const canStart =
    task.status === "assigned" ||
    task.status === "draft" ||
    task.status === "blocked" ||
    (task.status === "in_progress" && jobFailed);
  const canStop = task.status === "in_progress" && jobLive && !jobFailed;
  const showRunCard =
    task.status === "in_progress" || (task.status === "blocked" && jobStatus === "cancelled");
  const showLiveClock = task.status === "in_progress" && jobLive && !jobFailed;
  const showRedTools = task.task_type === "red" || task.task_type === "both";
  const showBlueTools = task.task_type === "blue" || task.task_type === "both";

  const tabs: { id: DetailTab; label: string; visible: boolean }[] = [
    { id: "overview", label: "Overview", visible: true },
    { id: "logs", label: "Logs", visible: true },
    { id: "attack-chain", label: "Attack Chain", visible: unlocked },
    { id: "patches", label: "Patches", visible: unlocked },
  ];

  return (
    <div className="mx-auto max-w-[1100px]">
      <Link
        to="/tasks"
        className="micro mb-3 inline-flex items-center gap-1"
        style={{ color: "var(--text-secondary)" }}
      >
        <ArrowLeft size={12} strokeWidth={1.5} /> Back to Task Runner
      </Link>
      <PageHeader
        title={task.target}
        subtitle={task.description || undefined}
        right={<StatusPill status={task.status} />}
      />

      <div
        className="mb-6 flex flex-wrap gap-1 border-b"
        style={{ borderColor: "var(--border-hairline)" }}
        role="tablist"
        aria-label="Task sections"
      >
        {tabs
          .filter((t) => t.visible)
          .map((t) => {
            const active = tab === t.id;
            return (
              <button
                key={t.id}
                role="tab"
                aria-selected={active}
                onClick={() => setTab(t.id)}
                className="inline-flex items-center gap-1.5 px-3 py-2 text-sm"
                style={{
                  color: active ? "var(--text-primary)" : "var(--text-secondary)",
                  borderBottom: `2px solid ${active ? "var(--text-primary)" : "transparent"}`,
                }}
              >
                {t.id === "logs" && <ScrollText size={14} strokeWidth={1.5} />}
                {t.id === "attack-chain" && <GitBranch size={14} strokeWidth={1.5} />}
                {t.id === "patches" && <ShieldCheck size={14} strokeWidth={1.5} />}
                {t.label}
              </button>
            );
          })}
        {!unlocked && (
          <span className="micro ml-auto self-center px-2" style={{ color: "var(--text-muted)" }}>
            Attack Chain and Patches unlock after the task completes
          </span>
        )}
      </div>

      {tab === "overview" && (
        <Panel className="p-4">
          <div className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
            <div>
              <Eyebrow>Type</Eyebrow>
              <div className="mt-1 uppercase">{task.task_type}</div>
            </div>
            <div>
              <Eyebrow>Assignee</Eyebrow>
              <div className="mt-1 mono">{task.assignee_id ? task.assignee_id.slice(0, 8) : "Unassigned"}</div>
            </div>
            <div>
              <Eyebrow>Patch scope</Eyebrow>
              <div className="mt-1">{task.patch_scope || "—"}</div>
            </div>
            <div>
              {showRunCard ? (
                <TaskRunClock task={task} results={results} ticking={showLiveClock} />
              ) : (
                <>
                  <Eyebrow>Started</Eyebrow>
                  <div className="mono mt-1">{relTime(task.started_at)}</div>
                </>
              )}
            </div>
          </div>

          {showRunCard && (
            <TaskRunProgress
              task={task}
              results={results}
              stopped={task.status === "blocked" || jobStatus === "cancelled"}
            />
          )}

          {jobError && (
            <div className="mt-4">
              <ErrorBanner message={jobError} />
            </div>
          )}

          {startMut.isError && (
            <div className="mt-4">
              <ErrorBanner
                message={
                  startMut.error instanceof Error
                    ? startMut.error.message
                    : "Could not start the task"
                }
              />
            </div>
          )}

          {stopMut.isError && (
            <div className="mt-4">
              <ErrorBanner
                message={
                  stopMut.error instanceof Error ? stopMut.error.message : "Could not stop the task"
                }
              />
            </div>
          )}

          <div className="mt-4 flex flex-wrap gap-2">
            {canStop && (
              <button
                onClick={() => {
                  if (
                    !window.confirm(
                      "Stop this run? HexStrike processes will be killed.",
                    )
                  ) {
                    return;
                  }
                  stopMut.mutate();
                }}
                disabled={stopMut.isPending}
                className="inline-flex items-center gap-1.5 rounded-sm px-3 py-1.5 text-sm disabled:opacity-60"
                style={{
                  border: "1px solid var(--accent-ember)",
                  color: "var(--accent-ember)",
                }}
              >
                <Square size={14} strokeWidth={1.5} />
                {stopMut.isPending ? "Stopping…" : "Stop"}
              </button>
            )}
            {canStart && (
              <button
                onClick={() => startMut.mutate()}
                disabled={startMut.isPending}
                className="inline-flex items-center gap-1.5 rounded-sm px-3 py-1.5 text-sm font-medium disabled:opacity-60"
                style={{ background: "var(--accent-ember)", color: "var(--bg-base)" }}
              >
                <Play size={14} strokeWidth={1.5} />
                {startMut.isPending ? "Starting…" : jobFailed ? "Retry task" : "Start task"}
              </button>
            )}
            {task.status === "in_progress" && showRedTools && (
              <Link
                to="/tools/red"
                search={{ taskId: task.id }}
                className="inline-flex items-center gap-1 rounded-sm px-3 py-1.5 text-sm"
                style={{
                  border: "1px solid var(--border-hairline)",
                  color: "var(--text-primary)",
                }}
              >
                <Swords size={14} strokeWidth={1.5} />
                Open Red Tools
              </Link>
            )}
            {task.status === "in_progress" && showBlueTools && (
              <Link
                to="/tools/blue"
                search={{ taskId: task.id }}
                className="inline-flex items-center gap-1 rounded-sm px-3 py-1.5 text-sm"
                style={{
                  border: "1px solid var(--border-hairline)",
                  color: "var(--text-primary)",
                }}
              >
                <ShieldAlert size={14} strokeWidth={1.5} />
                Open Blue Tools
              </Link>
            )}
          </div>
        </Panel>
      )}

      {tab === "logs" && <TaskLogs task={task} results={results} />}

      {tab === "attack-chain" && unlocked && <TaskAttackChain results={results} />}

      {tab === "patches" && unlocked && (
        <TaskPatches
          patches={results?.patches ?? []}
          onApply={(id) => applyMut.mutate(id)}
        />
      )}
    </div>
  );
}
