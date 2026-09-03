import { createFileRoute } from "@tanstack/react-router";
import { ToolLauncher } from "@/components/tools/ToolLauncher";
import { CaiChatPanel } from "@/components/tools/CaiChatPanel";
import { PageHeader } from "@/components/sd/primitives";

export const Route = createFileRoute("/_authenticated/tools/red")({
  head: () => ({ meta: [{ title: "Red Team Tools — SecureDash" }] }),
  validateSearch: (search: Record<string, unknown>) => ({
    taskId: typeof search.taskId === "string" ? search.taskId : undefined,
  }),
  component: RedToolsPage,
});

function RedToolsPage() {
  const { taskId } = Route.useSearch();
  return (
    <div className="mx-auto max-w-[900px]">
      <PageHeader
        title="Red Team Tools"
        subtitle="Launch offensive validation jobs against monitored assets."
      />
      <ToolLauncher team="red" taskId={taskId} />
      <CaiChatPanel team="red" taskId={taskId} />
    </div>
  );
}
