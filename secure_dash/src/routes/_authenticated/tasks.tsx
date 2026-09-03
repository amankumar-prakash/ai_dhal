import { createFileRoute, Outlet, useRouterState } from "@tanstack/react-router";
import { CreateTaskForm } from "@/components/tasks/CreateTaskForm";
import { TaskBoard } from "@/components/tasks/TaskBoard";
import { PageHeader, Panel } from "@/components/sd/primitives";

export const Route = createFileRoute("/_authenticated/tasks")({
  head: () => ({ meta: [{ title: "Task Runner — SecureDash" }] }),
  component: TaskRunnerPage,
});

function TaskRunnerPage() {
  const detailActive = useRouterState({
    select: (s) => s.matches.some((m) => m.routeId === "/_authenticated/tasks/$taskId"),
  });

  if (detailActive) return <Outlet />;

  return (
    <div className="mx-auto max-w-[1200px]">
      <PageHeader
        title="Task Runner"
        subtitle="Create a task, start the run, then review the Attack Chain and Patches once it finishes."
      />
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[340px_1fr]">
        <CreateTaskForm />
        <Panel>
          <TaskBoard />
        </Panel>
      </div>
    </div>
  );
}
