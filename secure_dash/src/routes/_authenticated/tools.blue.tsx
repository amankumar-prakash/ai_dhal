import { createFileRoute } from "@tanstack/react-router";
import { requireToolAccess } from "@/lib/route-guards";
import { ToolLauncher } from "@/components/tools/ToolLauncher";
import { CaiChatPanel } from "@/components/tools/CaiChatPanel";
import { PageHeader } from "@/components/sd/primitives";

export const Route = createFileRoute("/_authenticated/tools/blue")({
  head: () => ({ meta: [{ title: "Blue Team Tools — SecureDash" }] }),
  validateSearch: (search: Record<string, unknown>) => ({
    taskId: typeof search.taskId === "string" ? search.taskId : undefined,
  }),
  beforeLoad: ({ context }) => {
    requireToolAccess(context.me, "blue");
  },
  component: BlueToolsPage,
});

function BlueToolsPage() {
  const { taskId } = Route.useSearch();
  return (
    <div className="mx-auto max-w-[900px]">
      <PageHeader
        title="Blue Team Tools"
        subtitle="Launch defensive validation jobs against monitored assets."
      />
      <ToolLauncher team="blue" taskId={taskId} />
      <CaiChatPanel team="blue" taskId={taskId} />
    </div>
  );
}
