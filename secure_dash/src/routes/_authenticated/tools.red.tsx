import { useCallback, useRef, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { ToolLauncher } from "@/components/tools/ToolLauncher";
import {
  RedTeamChatPanel,
  type RedTeamChatPanelHandle,
} from "@/components/tools/RedTeamChatPanel";
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
  const [target, setTarget] = useState("");
  const [chatActive, setChatActive] = useState(false);
  const [chatStarting, setChatStarting] = useState(false);
  const chatRef = useRef<RedTeamChatPanelHandle>(null);

  const startChat = useCallback(async () => {
    await chatRef.current?.startJob();
  }, []);

  return (
    <div className="mx-auto max-w-[900px]">
      <PageHeader
        title="Red Team Tools"
        subtitle="Chat with the HexStrike agent against an in-scope target."
      />
      <ToolLauncher
        team="red"
        taskId={taskId}
        chatMode
        target={target}
        onTargetChange={setTarget}
        onStartChat={startChat}
        chatStarting={chatStarting}
        chatActive={chatActive}
      />
      <RedTeamChatPanel
        ref={chatRef}
        team="red"
        taskId={taskId}
        target={target}
        onActiveChange={setChatActive}
        onStartingChange={setChatStarting}
      />
    </div>
  );
}
