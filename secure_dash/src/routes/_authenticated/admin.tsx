import { createFileRoute } from "@tanstack/react-router";
import { ShieldCheck } from "lucide-react";
import { CreateUserForm } from "@/components/admin/CreateUserForm";
import { UserList, adminUsersQueryKey } from "@/components/admin/UserList";
import { PageHeader, Panel } from "@/components/sd/primitives";
import { useQueryClient } from "@tanstack/react-query";

export const Route = createFileRoute("/_authenticated/admin")({
  head: () => ({
    meta: [{ title: "Admin — SecureDash" }],
  }),
  component: AdminPage,
});

function AdminPage() {
  const qc = useQueryClient();

  return (
    <div className="mx-auto max-w-[1200px]">
      <PageHeader
        title="Admin"
        subtitle="Provision users and assign roles."
      />
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[320px_1fr]">
        <CreateUserForm onCreated={() => qc.invalidateQueries({ queryKey: adminUsersQueryKey })} />
        <Panel>
          <div
            className="flex items-center gap-2 border-b p-4"
            style={{ borderColor: "var(--border-hairline)" }}
          >
            <ShieldCheck size={16} strokeWidth={1.5} style={{ color: "var(--text-secondary)" }} />
            <span className="eyebrow">Provisioned users</span>
          </div>
          <UserList />
        </Panel>
      </div>
    </div>
  );
}
