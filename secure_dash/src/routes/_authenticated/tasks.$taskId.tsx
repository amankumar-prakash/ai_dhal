import { useMemo, useState } from "react";
import { createFileRoute, Link, useRouter } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Swords, ShieldAlert } from "lucide-react";
import { requireTasksRole } from "@/lib/route-guards";
import {
  analystRolesQuery,
  taskAuditQuery,
  taskQuery,
  transitionTask,
  type TaskAction,
} from "@/lib/tasks-api";
import { relTime } from "@/lib/security";
import { TaskNotes } from "@/components/tasks/TaskNotes";
import { TaskLinks } from "@/components/tasks/TaskLinks";
import { StatusPill } from "@/components/tasks/TaskBoard";
import { ErrorBanner, Eyebrow, PageHeader, Panel, SkeletonRows } from "@/components/sd/primitives";

export const Route = createFileRoute("/_authenticated/tasks/$taskId")({
  head: () => ({ meta: [{ title: "Task detail — SecureDash" }] }),
  beforeLoad: ({ context }) => {
    requireTasksRole(context.me);
  },
  component: TaskDetailPage,
});

const ACTION_LABEL: Record<TaskAction, string> = {
  assign: "Assign",
  start: "Start",
  block: "Block",
  unblock: "Unblock",
  complete: "Complete",
  review: "Mark reviewed",
  close: "Close",
  reassign: "Reassign",
};

const DESTRUCTIVE: Partial<Record<TaskAction, boolean>> = { block: true, close: true };

function TaskDetailPage() {
  const { taskId } = Route.useParams();
  const { me } = Route.useRouteContext();
  const qc = useQueryClient();
  const router = useRouter();

  const task = useQuery(taskQuery(taskId));
  const audit = useQuery(taskAuditQuery(taskId));
  const analysts = useQuery(analystRolesQuery);

  const [error, setError] = useState<string | null>(null);
  const [assigneePick, setAssigneePick] = useState("");

  const isManager = me.role === "security_manager";
  const isAssignee = task.data?.assignee_id === me.user_id;
  const canAct = isManager || isAssignee;

  const invalidateAll = () => {
    qc.invalidateQueries({ queryKey: ["tasks"] });
    qc.invalidateQueries({ queryKey: ["tasks", "detail", taskId] });
    qc.invalidateQueries({ queryKey: ["tasks", "audit", taskId] });
    // Starting/completing a task changes `/me`'s tool_unlock for the Analyst.
    router.invalidate();
  };

  const actionMutation = useMutation({
    mutationFn: (action: TaskAction) => transitionTask(taskId, action),
    onSuccess: () => {
      setError(null);
      invalidateAll();
    },
    onError: (e) => setError(e instanceof Error ? e.message : "Action failed"),
  });

  const assignMutation = useMutation({
    mutationFn: () =>
      transitionTask(taskId, task.data?.assignee_id ? "reassign" : "assign", assigneePick),
    onSuccess: () => {
      setError(null);
      setAssigneePick("");
      invalidateAll();
    },
    onError: (e) => setError(e instanceof Error ? e.message : "Could not assign"),
  });

  const availableActions = useMemo<TaskAction[]>(() => {
    if (!task.data) return [];
    const status = task.data.status;
    const actions: TaskAction[] = [];
    if (canAct) {
      if (status === "assigned" || status === "blocked") actions.push("start");
      if (status === "in_progress") actions.push("block", "complete");
      if (status === "blocked") actions.push("unblock", "complete");
    }
    if (isManager) {
      if (status === "completed") actions.push("review");
      if (status === "reviewed" || status === "completed") actions.push("close");
    }
    return actions;
  }, [task.data, canAct, isManager]);

  if (task.isError) {
    return (
      <ErrorBanner
        message="Task not found or no longer available."
        onRetry={() => task.refetch()}
      />
    );
  }
  if (task.isLoading || !task.data) {
    return <SkeletonRows rows={4} height={44} />;
  }

  const t = task.data;
  const readOnly = t.status === "closed";
  const toolsPath = t.task_type === "red" ? "/tools/red" : "/tools/blue";

  return (
    <div className="mx-auto max-w-[900px]">
      <Link
        to="/tasks"
        className="micro mb-3 inline-flex items-center gap-1"
        style={{ color: "var(--text-secondary)" }}
      >
        <ArrowLeft size={12} strokeWidth={1.5} /> Back to tasks
      </Link>
      <PageHeader
        title={t.target}
        subtitle={t.description || undefined}
        right={<StatusPill status={t.status} />}
      />

      {error && (
        <div className="mb-4">
          <ErrorBanner message={error} />
        </div>
      )}

      <Panel className="p-4">
        <div className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
          <div>
            <Eyebrow>Type</Eyebrow>
            <div className="mt-1 uppercase">{t.task_type}</div>
          </div>
          <div>
            <Eyebrow>Patch scope</Eyebrow>
            <div className="mt-1">{t.patch_scope || "—"}</div>
          </div>
          <div>
            <Eyebrow>Started</Eyebrow>
            <div className="mono mt-1">{relTime(t.started_at)}</div>
          </div>
          <div>
            <Eyebrow>Closed</Eyebrow>
            <div className="mono mt-1">{relTime(t.closed_at)}</div>
          </div>
        </div>

        {readOnly ? (
          <p className="mt-4 text-sm" style={{ color: "var(--text-muted)" }}>
            This task is closed and read-only.
          </p>
        ) : (
          <>
            {availableActions.length > 0 && (
              <div className="mt-4 flex flex-wrap gap-2">
                {availableActions.map((a) => (
                  <button
                    key={a}
                    onClick={() => actionMutation.mutate(a)}
                    disabled={actionMutation.isPending}
                    className="rounded-sm px-3 py-1.5 text-sm font-medium disabled:opacity-50"
                    style={{
                      background: DESTRUCTIVE[a] ? "var(--surface-raised)" : "var(--accent-ember)",
                      border: DESTRUCTIVE[a] ? "1px solid var(--border-hairline)" : "none",
                      color: DESTRUCTIVE[a] ? "var(--text-primary)" : "var(--bg-base)",
                    }}
                  >
                    {ACTION_LABEL[a]}
                  </button>
                ))}
              </div>
            )}
            {t.status === "in_progress" && (isManager || isAssignee) && (
              <Link
                to={toolsPath}
                search={{ taskId: t.id }}
                className="mt-3 inline-flex items-center gap-1 micro"
                style={{ color: "var(--text-secondary)" }}
              >
                {t.task_type === "red" ? (
                  <Swords size={12} strokeWidth={1.5} />
                ) : (
                  <ShieldAlert size={12} strokeWidth={1.5} />
                )}
                Open {t.task_type === "red" ? "Red" : "Blue"} Tools for this task
              </Link>
            )}
            {isManager && (
              <div
                className="mt-4 flex flex-wrap items-center gap-2 border-t pt-4"
                style={{ borderColor: "var(--border-hairline)" }}
              >
                <select
                  value={assigneePick}
                  onChange={(e) => setAssigneePick(e.target.value)}
                  className="mono micro rounded-sm px-2 py-1.5"
                  style={{
                    background: "var(--surface-raised)",
                    border: "1px solid var(--border-hairline)",
                    color: "var(--text-secondary)",
                  }}
                >
                  <option value="">Pick an Analyst…</option>
                  {(analysts.data ?? []).map((r) => (
                    <option key={r.user_id} value={r.user_id}>
                      {r.user_id}
                    </option>
                  ))}
                </select>
                <button
                  onClick={() => assignMutation.mutate()}
                  disabled={!assigneePick || assignMutation.isPending}
                  className="rounded-sm px-3 py-1.5 text-sm disabled:opacity-50"
                  style={{
                    border: "1px solid var(--border-hairline)",
                    color: "var(--text-primary)",
                  }}
                >
                  {t.assignee_id ? "Reassign" : "Assign"}
                </button>
              </div>
            )}
            {!canAct && availableActions.length === 0 && !isManager && (
              <p className="mt-4 text-sm" style={{ color: "var(--text-muted)" }}>
                Only the assignee or a Security Manager can act on this task.
              </p>
            )}
          </>
        )}
      </Panel>

      <div className="mt-6 grid grid-cols-1 gap-6 md:grid-cols-2">
        <Panel className="p-4">
          <TaskNotes taskId={taskId} canWrite={canAct && !readOnly} />
        </Panel>
        <Panel className="p-4">
          <TaskLinks taskId={taskId} canWrite={canAct && !readOnly} />
        </Panel>
      </div>

      <Panel className="mt-6 p-4">
        <Eyebrow>Audit trail</Eyebrow>
        {audit.isLoading ? (
          <SkeletonRows rows={2} height={28} />
        ) : (audit.data ?? []).length === 0 ? (
          <p className="mt-2 text-sm" style={{ color: "var(--text-muted)" }}>
            No events yet.
          </p>
        ) : (
          <ul className="mt-2 flex flex-col gap-1">
            {(audit.data ?? []).map((ev) => (
              <li
                key={ev.id}
                className="mono micro flex flex-wrap items-center gap-2"
                style={{ color: "var(--text-secondary)" }}
              >
                <span style={{ color: "var(--text-muted)" }}>{relTime(ev.created_at)}</span>
                <span>{ev.action}</span>
                {ev.from_status && ev.to_status && (
                  <span style={{ color: "var(--text-muted)" }}>
                    {ev.from_status} → {ev.to_status}
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}
