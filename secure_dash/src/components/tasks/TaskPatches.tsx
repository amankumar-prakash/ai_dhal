import { ShieldCheck } from "lucide-react";
import { relTime, type Patch } from "@/lib/security";
import { EmptyState, Panel } from "@/components/sd/primitives";

export function TaskPatches({
  patches,
  onApply,
}: {
  patches: Patch[];
  onApply: (id: string) => void;
}) {
  if (!patches.length) {
    return (
      <EmptyState
        icon={<ShieldCheck size={20} strokeWidth={1.5} />}
        label="No patches proposed for this task."
      />
    );
  }

  return (
    <Panel>
      <ul>
        {patches.map((p) => (
          <li
            key={p.id}
            className="flex flex-wrap items-center gap-3 border-b px-4 py-3 last:border-b-0"
            style={{ borderColor: "var(--border-hairline)" }}
          >
            <div className="min-w-0 flex-1">
              <div className="text-sm">{p.title}</div>
              <div className="mono micro mt-1" style={{ color: "var(--text-muted)" }}>
                {p.playbook} · {p.status}
                {p.created_at ? ` · ${relTime(p.created_at)}` : ""}
                {p.applied_at ? ` · applied ${relTime(p.applied_at)}` : ""}
              </div>
            </div>
            {p.status !== "applied" ? (
              <button
                className="rounded-sm px-3 py-1.5 text-sm"
                style={{ background: "var(--accent-ember)", color: "var(--bg-base)" }}
                onClick={() => onApply(p.id)}
              >
                Apply
              </button>
            ) : (
              <span className="micro" style={{ color: "var(--text-secondary)" }}>
                Applied
              </span>
            )}
          </li>
        ))}
      </ul>
    </Panel>
  );
}
