import { createFileRoute, Outlet, useRouterState } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import { requireTasksRole } from "@/lib/route-guards";
import { CreateTaskForm } from "@/components/tasks/CreateTaskForm";
import { TaskBoard } from "@/components/tasks/TaskBoard";
import { PageHeader, Panel } from "@/components/sd/primitives";

export const Route = createFileRoute("/_authenticated/tasks")({
  head: () => ({ meta: [{ title: "Tasks — SecureDash" }] }),
  beforeLoad: ({ context }) => {
    requireTasksRole(context.me);
  },
  component: TasksPage,
});

function TasksPage() {
  const { me } = Route.useRouteContext();
  const qc = useQueryClient();
  const isManager = me.role === "security_manager";

  // `/tasks/$taskId` fully replaces the board (rather than nesting under it).
  const detailActive = useRouterState({
    select: (s) => s.matches.some((m) => m.routeId === "/_authenticated/tasks/$taskId"),
  });

  if (detailActive) return <Outlet />;

  return (
    <div className="mx-auto max-w-[1200px]">
      <PageHeader
        title="Tasks"
        subtitle={
          isManager
            ? "Create, assign and track Red/Blue tasks across the team."
            : "Tasks assigned to you. Start one to unlock its team tools."
        }
      />
      <div className={isManager ? "grid grid-cols-1 gap-6 lg:grid-cols-[340px_1fr]" : ""}>
        {isManager && (
          <CreateTaskForm onCreated={() => qc.invalidateQueries({ queryKey: ["tasks"] })} />
        )}
        <Panel>
          <TaskBoard isManager={isManager} />
        </Panel>
      </div>
    </div>
  );
}
