import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, ShieldCheck, ShieldOff } from "lucide-react";
import { listAdminUsers, patchAdminUser, reissueCredentials } from "@/lib/admin-provision";
import { APP_ROLES, ROLE_LABELS } from "@/lib/roles";
import type { AppRole } from "@/lib/rbac-types";
import { EmptyState, ErrorBanner, SkeletonRows } from "@/components/sd/primitives";

export const adminUsersQueryKey = ["admin-users"];

type ReissuedMap = Record<string, { temporary_password: string; invite_expires_at: string }>;

export function UserList() {
  const qc = useQueryClient();
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: adminUsersQueryKey,
    queryFn: listAdminUsers,
  });
  const [reissued, setReissued] = useState<ReissuedMap>({});

  const invalidate = () => qc.invalidateQueries({ queryKey: adminUsersQueryKey });

  const roleMutation = useMutation({
    mutationFn: ({ id, role }: { id: string; role: AppRole }) => patchAdminUser(id, { role }),
    onSuccess: invalidate,
  });
  const statusMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: "active" | "disabled" }) =>
      patchAdminUser(id, { status }),
    onSuccess: invalidate,
  });
  const reissueMutation = useMutation({
    mutationFn: (id: string) => reissueCredentials(id),
    onSuccess: (res, id) => {
      if (res.temporary_password && res.invite_expires_at) {
        setReissued((prev) => ({
          ...prev,
          [id]: {
            temporary_password: res.temporary_password!,
            invite_expires_at: res.invite_expires_at!,
          },
        }));
      }
      invalidate();
    },
  });

  if (isError) {
    return <ErrorBanner message="Could not load users." onRetry={() => refetch()} />;
  }
  if (isLoading) {
    return <SkeletonRows rows={4} height={48} />;
  }

  const users = data ?? [];
  if (users.length === 0) {
    return <EmptyState label="No users provisioned yet. Create the first one above." />;
  }

  return (
    <div>
      <div
        className="flex items-center gap-4 border-b px-4 py-2"
        style={{ borderColor: "var(--border-hairline)" }}
      >
        <span className="eyebrow flex-1">User</span>
        <span className="eyebrow w-[170px]">Role</span>
        <span className="eyebrow w-[90px]">Status</span>
        <span className="eyebrow w-[170px]">Last login</span>
        <span className="eyebrow w-[80px]">Actions</span>
      </div>
      <ul>
        {users.map((u) => (
          <li
            key={u.id}
            className="border-b last:border-b-0"
            style={{ borderColor: "var(--border-hairline)" }}
          >
            <div className="flex flex-wrap items-center gap-4 px-4 py-3">
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm">{u.display_name || u.email || u.id}</div>
                <div className="mono micro truncate" style={{ color: "var(--text-muted)" }}>
                  {u.email ?? "—"}
                </div>
              </div>
              <select
                value={u.role ?? ""}
                disabled={roleMutation.isPending}
                onChange={(e) => roleMutation.mutate({ id: u.id, role: e.target.value as AppRole })}
                className="micro w-[170px] rounded-sm px-2 py-1"
                style={{
                  background: "var(--surface-raised)",
                  border: "1px solid var(--border-hairline)",
                  color: "var(--text-secondary)",
                }}
              >
                {!u.role && <option value="">—</option>}
                {APP_ROLES.map((r) => (
                  <option key={r} value={r}>
                    {ROLE_LABELS[r]}
                  </option>
                ))}
              </select>
              <span className="w-[90px]">
                <span
                  className="micro inline-flex items-center gap-1 rounded-sm px-1.5 py-0.5 uppercase tracking-[0.04em]"
                  style={{
                    border: "1px solid var(--border-hairline)",
                    color:
                      u.status === "disabled"
                        ? "var(--severity-critical)"
                        : "var(--text-secondary)",
                  }}
                >
                  {u.status}
                </span>
              </span>
              <span className="mono micro w-[170px]" style={{ color: "var(--text-muted)" }}>
                {u.last_login_at ? new Date(u.last_login_at).toLocaleString() : "never"}
              </span>
              <div className="flex w-[80px] items-center gap-3">
                <button
                  title={u.status === "disabled" ? "Enable user" : "Disable user"}
                  onClick={() =>
                    statusMutation.mutate({
                      id: u.id,
                      status: u.status === "disabled" ? "active" : "disabled",
                    })
                  }
                  disabled={statusMutation.isPending}
                  style={{ color: "var(--text-secondary)" }}
                >
                  {u.status === "disabled" ? (
                    <ShieldCheck size={16} strokeWidth={1.5} />
                  ) : (
                    <ShieldOff size={16} strokeWidth={1.5} />
                  )}
                </button>
                <button
                  title="Reissue one-time credentials"
                  onClick={() => reissueMutation.mutate(u.id)}
                  disabled={reissueMutation.isPending}
                  style={{ color: "var(--text-secondary)" }}
                >
                  <KeyRound size={16} strokeWidth={1.5} />
                </button>
              </div>
            </div>
            {reissued[u.id] && (
              <div
                className="mx-4 mb-3 rounded-sm p-3"
                style={{
                  background: "var(--surface-raised)",
                  border: "1px solid var(--border-hairline)",
                }}
              >
                <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
                  New one-time credential for this user — shown once.
                </p>
                <div
                  className="mono mt-2 rounded-sm px-2 py-1.5 text-sm"
                  style={{ background: "var(--bg-base)" }}
                >
                  {reissued[u.id].temporary_password}
                </div>
                <div className="micro mt-1" style={{ color: "var(--text-muted)" }}>
                  Expires {new Date(reissued[u.id].invite_expires_at).toLocaleString()}
                </div>
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
