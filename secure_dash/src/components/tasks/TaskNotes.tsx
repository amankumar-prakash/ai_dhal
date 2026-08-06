import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { addTaskNote, taskNotesQuery } from "@/lib/tasks-api";
import { relTime } from "@/lib/security";
import { EmptyState, ErrorBanner, Eyebrow, SkeletonRows } from "@/components/sd/primitives";

export function TaskNotes({ taskId, canWrite }: { taskId: string; canWrite: boolean }) {
  const qc = useQueryClient();
  const notes = useQuery(taskNotesQuery(taskId));
  const [body, setBody] = useState("");

  const mutation = useMutation({
    mutationFn: () => addTaskNote(taskId, body),
    onSuccess: () => {
      setBody("");
      qc.invalidateQueries({ queryKey: ["tasks", "notes", taskId] });
      qc.invalidateQueries({ queryKey: ["tasks", "audit", taskId] });
    },
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    if (!body.trim()) return;
    mutation.mutate();
  }

  return (
    <div>
      <Eyebrow>Notes</Eyebrow>
      {notes.isError ? (
        <ErrorBanner message="Could not load notes." onRetry={() => notes.refetch()} />
      ) : notes.isLoading ? (
        <SkeletonRows rows={2} height={40} />
      ) : (notes.data ?? []).length === 0 ? (
        <EmptyState label="No notes yet." />
      ) : (
        <ul className="mt-2 flex flex-col gap-2">
          {(notes.data ?? []).map((n) => (
            <li
              key={n.id}
              className="rounded-sm p-3"
              style={{
                background: "var(--surface-raised)",
                border: "1px solid var(--border-hairline)",
              }}
            >
              <p className="text-sm whitespace-pre-wrap">{n.body}</p>
              <div className="mono micro mt-1" style={{ color: "var(--text-muted)" }}>
                {relTime(n.created_at)}
              </div>
            </li>
          ))}
        </ul>
      )}
      {mutation.isError && (
        <div className="mt-2">
          <ErrorBanner
            message={
              mutation.error instanceof Error ? mutation.error.message : "Could not add note"
            }
          />
        </div>
      )}
      {canWrite && (
        <form onSubmit={submit} className="mt-3 flex gap-2">
          <input
            value={body}
            onChange={(e) => setBody(e.target.value)}
            placeholder="Add a note…"
            className="flex-1 rounded-sm px-3 py-2 text-sm"
            style={{
              background: "var(--surface-raised)",
              border: "1px solid var(--border-hairline)",
              color: "var(--text-primary)",
            }}
          />
          <button
            type="submit"
            disabled={mutation.isPending || !body.trim()}
            className="rounded-sm px-3 py-2 text-sm font-medium disabled:opacity-50"
            style={{ background: "var(--accent-ember)", color: "var(--bg-base)" }}
          >
            Add
          </button>
        </form>
      )}
    </div>
  );
}
