import { useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowLeft, GitBranch, Play, ShieldAlert, ShieldCheck, Swords } from "lucide-react";
import { relTime } from "@/lib/security";
import { DUMMY_ASSIGNEES, resultsUnlocked } from "@/lib/task-runner-dummy";
import { useTaskRunner } from "@/hooks/use-task-runner";
import { StatusPill } from "@/components/tasks/TaskBoard";
import { TaskAttackChain } from "@/components/tasks/TaskAttackChain";
import { TaskPatches } from "@/components/tasks/TaskPatches";
import { ErrorBanner, Eyebrow, PageHeader, Panel } from "@/components/sd/primitives";

export const Route = createFileRoute("/_authenticated/tasks/$taskId")({
  head: () => ({ meta: [{ title: "Task — SecureDash" }] }),
  component: TaskDetailPage,
});

type DetailTab = "overview" | "attack-chain" | "patches";

function assigneeLabel(id: string | null): string {
  if (!id) return "Unassigned";
  return DUMMY_ASSIGNEES.find((a) => a.user_id === id)?.label ?? id;
}

function TaskDetailPage() {
  const { taskId } = Route.useParams();
  const { getTask, getResults, start, complete, applyPatch } = useTaskRunner();
  const task = getTask(taskId);
  const results = getResults(taskId);
  const unlocked = task ? resultsUnlocked(task.status) : false;

  const [tab, setTab] = useState<DetailTab>("overview");

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
        <ErrorBanner message="Task not found or no longer available." />
      </div>
    );
  }

  const canStart = task.status === "assigned" || task.status === "draft" || task.status === "blocked";
  const canComplete = task.status === "in_progress" || task.status === "blocked";
  const showRedTools = task.task_type === "red" || task.task_type === "both";
  const showBlueTools = task.task_type === "blue" || task.task_type === "both";

  function handleStart() {
    start(taskId);
    setTab("overview");
  }

  function handleComplete() {
    complete(taskId);
    setTab("attack-chain");
  }

  const tabs: { id: DetailTab; label: string; visible: boolean }[] = [
    { id: "overview", label: "Overview", visible: true },
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
              <div className="mt-1">{assigneeLabel(task.assignee_id)}</div>
            </div>
            <div>
              <Eyebrow>Patch scope</Eyebrow>
              <div className="mt-1">{task.patch_scope || "—"}</div>
            </div>
            <div>
              <Eyebrow>Started</Eyebrow>
              <div className="mono mt-1">{relTime(task.started_at)}</div>
            </div>
          </div>

          {task.status === "in_progress" && (
            <div
              className="mt-4 rounded-sm p-3"
              style={{
                background: "var(--surface-raised)",
                border: "1px solid var(--border-hairline)",
              }}
            >
              <div className="flex items-center gap-2">
                <span className="live-dot size-2 rounded-full" style={{ background: "var(--accent-ember)" }} />
                <span className="text-sm">Run in progress</span>
              </div>
              <p className="micro mt-1" style={{ color: "var(--text-muted)" }}>
                Complete the task to reveal the Attack Chain and Patches for this target.
              </p>
              <span
                className="mt-3 block h-0.5 w-full overflow-hidden"
                style={{ background: "var(--surface)" }}
              >
                <span
                  className="indeterminate-bar block h-full w-1/3"
                  style={{ background: "var(--accent-ember)" }}
                />
              </span>
            </div>
          )}

          <div className="mt-4 flex flex-wrap gap-2">
            {canStart && (
              <button
                onClick={handleStart}
                className="inline-flex items-center gap-1.5 rounded-sm px-3 py-1.5 text-sm font-medium"
                style={{ background: "var(--accent-ember)", color: "var(--bg-base)" }}
              >
                <Play size={14} strokeWidth={1.5} />
                Start task
              </button>
            )}
            {canComplete && (
              <button
                onClick={handleComplete}
                className="rounded-sm px-3 py-1.5 text-sm font-medium"
                style={{ background: "var(--accent-ember)", color: "var(--bg-base)" }}
              >
                Complete task
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

      {tab === "attack-chain" && unlocked && (
        <TaskAttackChain steps={results?.chain ?? []} />
      )}

      {tab === "patches" && unlocked && (
        <TaskPatches
          patches={results?.patches ?? []}
          onApply={(id) => applyPatch(taskId, id)}
        />
      )}
    </div>
  );
}
