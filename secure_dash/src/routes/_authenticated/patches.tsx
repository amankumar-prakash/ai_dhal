import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ShieldCheck } from "lucide-react";
import { apiFetch } from "@/lib/api-client";
import { patchesQuery, relTime } from "@/lib/security";
import { useRealtime } from "@/hooks/use-realtime";
import {
  EmptyState,
  ErrorBanner,
  PageHeader,
  Panel,
  SkeletonRows,
} from "@/components/sd/primitives";

export const Route = createFileRoute("/_authenticated/patches")({
  head: () => ({
    meta: [{ title: "Patches — SecureDash" }],
  }),
  component: PatchesPage,
});

function PatchesPage() {
  useRealtime(["findings"]);
  const qc = useQueryClient();
  const patches = useQuery(patchesQuery);

  const apply = useMutation({
    mutationFn: (id: string) =>
      apiFetch(`/patches/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ status: "applied" }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["patches"] });
      qc.invalidateQueries({ queryKey: ["findings"] });
    },
  });

  return (
    <div className="mx-auto max-w-[1100px]">
      <PageHeader
        title="Patches"
        subtitle="Blue-team remediation proposals. Applying a patch marks the linked finding remediated."
      />
      {patches.isError ? (
        <ErrorBanner message="Patches unavailable." onRetry={() => patches.refetch()} />
      ) : (
        <Panel>
          {patches.isLoading ? (
            <SkeletonRows rows={4} height={44} />
          ) : (patches.data ?? []).length === 0 ? (
            <EmptyState
              icon={<ShieldCheck size={20} strokeWidth={1.5} />}
              label="No patches yet — run a blue vuln-scan."
            />
          ) : (
            <ul>
              {(patches.data ?? []).map((p) => (
                <li
                  key={p.id}
                  className="flex flex-wrap items-center gap-3 border-b px-4 py-3"
                  style={{ borderColor: "var(--border-hairline)" }}
                >
                  <div className="min-w-0 flex-1">
                    <div className="text-sm">{p.title}</div>
                    <div className="mono micro mt-1" style={{ color: "var(--text-muted)" }}>
                      {p.playbook} · {p.status}
                      {p.created_at ? ` · ${relTime(p.created_at)}` : ""}
                    </div>
                  </div>
                  {p.status !== "applied" && (
                    <button
                      className="rounded-sm px-3 py-1.5 text-sm"
                      style={{ background: "var(--accent-ember)", color: "var(--bg-base)" }}
                      disabled={apply.isPending}
                      onClick={() => apply.mutate(p.id)}
                    >
                      Apply
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Panel>
      )}
    </div>
  );
}
