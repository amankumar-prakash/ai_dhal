import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link2 } from "lucide-react";
import { addTaskLink, taskLinksQuery } from "@/lib/tasks-api";
import type { TaskLinkKind } from "@/lib/rbac-types";
import { EmptyState, ErrorBanner, Eyebrow, SkeletonRows } from "@/components/sd/primitives";

export function TaskLinks({ taskId, canWrite }: { taskId: string; canWrite: boolean }) {
  const qc = useQueryClient();
  const links = useQuery(taskLinksQuery(taskId));
  const [kind, setKind] = useState<TaskLinkKind>("finding");
  const [refId, setRefId] = useState("");

  const mutation = useMutation({
    mutationFn: () => addTaskLink(taskId, kind, refId),
    onSuccess: () => {
      setRefId("");
      qc.invalidateQueries({ queryKey: ["tasks", "links", taskId] });
      qc.invalidateQueries({ queryKey: ["tasks", "audit", taskId] });
    },
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    if (!refId.trim()) return;
    mutation.mutate();
  }

  return (
    <div>
      <Eyebrow>Linked findings & scans</Eyebrow>
      {links.isError ? (
        <ErrorBanner message="Could not load links." onRetry={() => links.refetch()} />
      ) : links.isLoading ? (
        <SkeletonRows rows={2} height={32} />
      ) : (links.data ?? []).length === 0 ? (
        <EmptyState icon={<Link2 size={18} strokeWidth={1.5} />} label="No linked records yet." />
      ) : (
        <ul className="mt-2 flex flex-col gap-1">
          {(links.data ?? []).map((l) => (
            <li
              key={l.id}
              className="mono micro flex items-center gap-2"
              style={{ color: "var(--text-secondary)" }}
            >
              <span
                className="rounded-sm px-1.5 py-0.5"
                style={{ border: "1px solid var(--border-hairline)" }}
              >
                {l.kind}
              </span>
              {l.ref_id}
            </li>
          ))}
        </ul>
      )}
      {mutation.isError && (
        <div className="mt-2">
          <ErrorBanner
            message={
              mutation.error instanceof Error ? mutation.error.message : "Could not add link"
            }
          />
        </div>
      )}
      {canWrite && (
        <form onSubmit={submit} className="mt-3 flex gap-2">
          <select
            value={kind}
            onChange={(e) => setKind(e.target.value as TaskLinkKind)}
            className="micro rounded-sm px-2 py-2"
            style={{
              background: "var(--surface-raised)",
              border: "1px solid var(--border-hairline)",
              color: "var(--text-secondary)",
            }}
          >
            <option value="finding">Finding</option>
            <option value="scan">Scan</option>
          </select>
          <input
            value={refId}
            onChange={(e) => setRefId(e.target.value)}
            placeholder="Finding/scan UUID"
            className="mono flex-1 rounded-sm px-3 py-2 text-sm"
            style={{
              background: "var(--surface-raised)",
              border: "1px solid var(--border-hairline)",
              color: "var(--text-primary)",
            }}
          />
          <button
            type="submit"
            disabled={mutation.isPending || !refId.trim()}
            className="rounded-sm px-3 py-2 text-sm font-medium disabled:opacity-50"
            style={{ background: "var(--accent-ember)", color: "var(--bg-base)" }}
          >
            Link
          </button>
        </form>
      )}
    </div>
  );
}
