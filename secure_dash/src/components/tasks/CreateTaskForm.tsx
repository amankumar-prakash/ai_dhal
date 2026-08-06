import { useState, type FormEvent } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ListPlus } from "lucide-react";
import { analystRolesQuery, createTask } from "@/lib/tasks-api";
import { assetsQuery } from "@/lib/security";
import type { TaskType } from "@/lib/rbac-types";
import { ErrorBanner, Eyebrow, Panel } from "@/components/sd/primitives";

const inputStyle = {
  background: "var(--surface-raised)",
  border: "1px solid var(--border-hairline)",
  color: "var(--text-primary)",
} as const;

/** Security Manager only — creation is gated at the route level. */
export function CreateTaskForm({ onCreated }: { onCreated?: () => void }) {
  const [target, setTarget] = useState("");
  const [description, setDescription] = useState("");
  const [patchScope, setPatchScope] = useState("");
  const [taskType, setTaskType] = useState<TaskType>("red");
  const [assetId, setAssetId] = useState("");
  const [assigneeId, setAssigneeId] = useState("");

  const assets = useQuery(assetsQuery);
  const analysts = useQuery(analystRolesQuery);

  const mutation = useMutation({
    mutationFn: () =>
      createTask({
        target,
        description,
        patch_scope: patchScope,
        task_type: taskType,
        asset_id: assetId || null,
        assignee_id: assigneeId || null,
      }),
    onSuccess: () => {
      setTarget("");
      setDescription("");
      setPatchScope("");
      setAssetId("");
      setAssigneeId("");
      onCreated?.();
    },
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    mutation.reset();
    mutation.mutate();
  }

  return (
    <Panel className="p-4">
      <Eyebrow>New task</Eyebrow>
      {mutation.isError && (
        <div className="mt-3">
          <ErrorBanner
            message={
              mutation.error instanceof Error ? mutation.error.message : "Could not create task"
            }
          />
        </div>
      )}
      <form onSubmit={submit} className="mt-3 flex flex-col gap-3">
        <label className="flex flex-col gap-1">
          <span className="eyebrow">Target</span>
          <input
            required
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            className="mono rounded-sm px-3 py-2 text-sm"
            style={inputStyle}
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="eyebrow">Description</span>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={2}
            className="rounded-sm px-3 py-2 text-sm"
            style={inputStyle}
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="eyebrow">Patch scope</span>
          <input
            value={patchScope}
            onChange={(e) => setPatchScope(e.target.value)}
            className="rounded-sm px-3 py-2 text-sm"
            style={inputStyle}
          />
        </label>
        <div className="grid grid-cols-2 gap-3">
          <label className="flex flex-col gap-1">
            <span className="eyebrow">Type</span>
            <select
              value={taskType}
              onChange={(e) => setTaskType(e.target.value as TaskType)}
              className="rounded-sm px-3 py-2 text-sm"
              style={inputStyle}
            >
              <option value="red">Red</option>
              <option value="blue">Blue</option>
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="eyebrow">Asset (optional)</span>
            <select
              value={assetId}
              onChange={(e) => setAssetId(e.target.value)}
              className="rounded-sm px-3 py-2 text-sm"
              style={inputStyle}
            >
              <option value="">Unassigned</option>
              {(assets.data ?? []).map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </select>
          </label>
        </div>
        <label className="flex flex-col gap-1">
          <span className="eyebrow">Assignee (optional)</span>
          <select
            value={assigneeId}
            onChange={(e) => setAssigneeId(e.target.value)}
            className="mono rounded-sm px-3 py-2 text-sm"
            style={inputStyle}
          >
            <option value="">Unassigned — Draft</option>
            {(analysts.data ?? []).map((r) => (
              <option key={r.user_id} value={r.user_id}>
                {r.user_id}
              </option>
            ))}
          </select>
          <span className="micro" style={{ color: "var(--text-muted)" }}>
            Listed by Analyst user ID. Assign later from the task detail if you need to pick by
            name.
          </span>
        </label>
        <button
          type="submit"
          disabled={mutation.isPending}
          className="mt-1 inline-flex items-center justify-center gap-2 rounded-sm px-3 py-2 text-sm font-medium disabled:opacity-60"
          style={{ background: "var(--accent-ember)", color: "var(--bg-base)" }}
        >
          <ListPlus size={16} strokeWidth={1.5} />
          {mutation.isPending ? "Creating…" : "Create task"}
        </button>
      </form>
    </Panel>
  );
}
