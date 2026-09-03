import { useState, type FormEvent } from "react";
import { ListPlus } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useTaskRunner } from "@/hooks/use-task-runner";
import { assigneeRolesQuery } from "@/lib/tasks-api";
import { assetsQuery } from "@/lib/security";
import type { TaskType } from "@/lib/rbac-types";
import { ErrorBanner, Eyebrow, Panel } from "@/components/sd/primitives";

const inputStyle = {
  background: "var(--surface-raised)",
  border: "1px solid var(--border-hairline)",
  color: "var(--text-primary)",
} as const;

export function CreateTaskForm({ onCreated }: { onCreated?: () => void }) {
  const { create } = useTaskRunner();
  const assets = useQuery(assetsQuery);
  const roles = useQuery(assigneeRolesQuery);
  const [target, setTarget] = useState("");
  const [description, setDescription] = useState("");
  const [patchScope, setPatchScope] = useState("");
  const [taskType, setTaskType] = useState<TaskType>("red");
  const [assetId, setAssetId] = useState("");
  const [assigneeId, setAssigneeId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!target.trim()) {
      setError("Target is required.");
      return;
    }
    setPending(true);
    try {
      await create({
        target,
        description,
        patch_scope: patchScope,
        task_type: taskType === "both" ? "red" : taskType,
        asset_id: assetId || null,
        assignee_id: assigneeId || null,
      });
      setTarget("");
      setDescription("");
      setPatchScope("");
      setAssetId("");
      setAssigneeId("");
      onCreated?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create task");
    } finally {
      setPending(false);
    }
  }

  return (
    <Panel className="p-4">
      <Eyebrow>New task</Eyebrow>
      {error && (
        <div className="mt-3">
          <ErrorBanner message={error} />
        </div>
      )}
      <form onSubmit={submit} className="mt-3 flex flex-col gap-3">
        <label className="flex flex-col gap-1">
          <span className="eyebrow">Target</span>
          <input
            required
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            placeholder="http://shop.internal.lab:3000"
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
            placeholder="Phases: nmap, httpx-toolkit, gobuster, katana, nuclei"
            className="rounded-sm px-3 py-2 text-sm"
            style={inputStyle}
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="eyebrow">Patch scope</span>
          <input
            value={patchScope}
            onChange={(e) => setPatchScope(e.target.value)}
            placeholder="edge + WAF"
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
            <span className="eyebrow">Asset</span>
            <select
              value={assetId}
              onChange={(e) => setAssetId(e.target.value)}
              className="rounded-sm px-3 py-2 text-sm"
              style={inputStyle}
            >
              <option value="">Create from target</option>
              {(assets.data ?? []).map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </select>
          </label>
        </div>
        <label className="flex flex-col gap-1">
          <span className="eyebrow">Assignee</span>
          <select
            value={assigneeId}
            onChange={(e) => setAssigneeId(e.target.value)}
            className="rounded-sm px-3 py-2 text-sm"
            style={inputStyle}
          >
            <option value="">Unassigned</option>
            {(roles.data ?? []).map((r) => (
              <option key={r.user_id} value={r.user_id}>
                {r.role} · {r.user_id.slice(0, 8)}
              </option>
            ))}
          </select>
        </label>
        <button
          type="submit"
          disabled={pending}
          className="mt-1 inline-flex items-center justify-center gap-2 rounded-sm px-3 py-2 text-sm font-medium disabled:opacity-60"
          style={{ background: "var(--accent-ember)", color: "var(--bg-base)" }}
        >
          <ListPlus size={16} strokeWidth={1.5} />
          {pending ? "Creating…" : "Create task"}
        </button>
      </form>
    </Panel>
  );
}
