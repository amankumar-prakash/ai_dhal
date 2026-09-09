import { useMemo, useState } from "react";
import { Link, useNavigate } from "@tanstack/react-router";
import { ClipboardList, Play } from "lucide-react";
import { useTaskRunner } from "@/hooks/use-task-runner";
import { resultsUnlocked } from "@/lib/tasks";
import type { TaskStatus, TaskType } from "@/lib/rbac-types";
import { EmptyState } from "@/components/sd/primitives";

const STATUSES: TaskStatus[] = [
  "draft",
  "assigned",
  "in_progress",
  "blocked",
  "completed",
  "reviewed",
  "closed",
];

export const STATUS_LABEL: Record<TaskStatus, string> = {
  draft: "Draft",
  assigned: "Assigned",
  in_progress: "In Progress",
  blocked: "Blocked",
  completed: "Completed",
  reviewed: "Reviewed",
  closed: "Closed",
};

const STATUS_TONE: Record<TaskStatus, string> = {
  draft: "var(--text-muted)",
  assigned: "var(--text-secondary)",
  in_progress: "var(--accent-ember)",
  blocked: "var(--severity-critical)",
  completed: "var(--text-primary)",
  reviewed: "var(--text-primary)",
  closed: "var(--text-muted)",
};

export function StatusPill({ status }: { status: TaskStatus }) {
  return (
    <span
      className="micro inline-flex shrink-0 items-center gap-1 rounded-sm px-1.5 py-0.5"
      style={{ border: `1px solid ${STATUS_TONE[status]}`, color: STATUS_TONE[status] }}
    >
      {STATUS_LABEL[status]}
    </span>
  );
}

/** Filterable task list with a Start action for ready tasks. */
export function TaskBoard() {
  const { tasks, start } = useTaskRunner();
  const navigate = useNavigate();
  const [typeFilter, setTypeFilter] = useState<TaskType | "all">("all");
  const [statusFilter, setStatusFilter] = useState<TaskStatus | "all">("all");

  const filtered = useMemo(
    () =>
      tasks.filter((t) => {
        const typeOk =
          typeFilter === "all" ||
          t.task_type === typeFilter ||
          (t.task_type === "both" && (typeFilter === "red" || typeFilter === "blue"));
        const statusOk = statusFilter === "all" || t.status === statusFilter;
        return typeOk && statusOk;
      }),
    [tasks, typeFilter, statusFilter],
  );

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value as TaskType | "all")}
          className="micro rounded-sm px-2 py-1"
          style={{
            background: "var(--surface-raised)",
            border: "1px solid var(--border-hairline)",
            color: "var(--text-secondary)",
          }}
        >
          <option value="all">All types</option>
          <option value="red">Red</option>
          <option value="blue">Blue</option>
          <option value="both">Both</option>
        </select>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as TaskStatus | "all")}
          className="micro rounded-sm px-2 py-1"
          style={{
            background: "var(--surface-raised)",
            border: "1px solid var(--border-hairline)",
            color: "var(--text-secondary)",
          }}
        >
          <option value="all">All statuses</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {STATUS_LABEL[s]}
            </option>
          ))}
        </select>
      </div>

      {filtered.length === 0 ? (
        <EmptyState
          icon={<ClipboardList size={20} strokeWidth={1.5} />}
          label="No tasks match these filters — create one to get started."
        />
      ) : (
        <ul>
          {filtered.map((t) => {
            const canStart = t.status === "assigned" || t.status === "draft" || t.status === "blocked";
            return (
              <li
                key={t.id}
                className="border-b last:border-b-0"
                style={{ borderColor: "var(--border-hairline)" }}
              >
                <div className="flex flex-wrap items-center gap-3 px-4 py-3">
                  <Link
                    to="/tasks/$taskId"
                    params={{ taskId: t.id }}
                    className="flex min-w-0 flex-1 flex-wrap items-center gap-3 text-left transition-colors duration-150 ease-out"
                  >
                    <span
                      className="micro shrink-0 rounded-sm px-1.5 py-0.5 uppercase tracking-[0.04em]"
                      style={{
                        border: "1px solid var(--border-hairline)",
                        color:
                          t.task_type === "red"
                            ? "var(--severity-critical)"
                            : t.task_type === "both"
                              ? "var(--accent-ember)"
                              : "var(--text-secondary)",
                      }}
                    >
                      {t.task_type}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm">{t.target}</div>
                      <div className="mono micro truncate" style={{ color: "var(--text-muted)" }}>
                        {t.description || "no description"}
                        {resultsUnlocked(t.status) ? " · Attack Chain & Patches ready" : ""}
                      </div>
                    </div>
                    <StatusPill status={t.status} />
                  </Link>
                  {canStart && (
                    <button
                      onClick={() => {
                        void start(t.id).then(() => {
                          navigate({ to: "/tasks/$taskId", params: { taskId: t.id } });
                        });
                      }}
                      className="inline-flex items-center gap-1 rounded-sm px-2.5 py-1.5 text-sm"
                      style={{ background: "var(--accent-ember)", color: "var(--bg-base)" }}
                    >
                      <Play size={12} strokeWidth={1.5} />
                      Start
                    </button>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
