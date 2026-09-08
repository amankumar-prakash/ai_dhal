import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { requireToolAccess } from "@/lib/route-guards";
import { ToolLauncher } from "@/components/tools/ToolLauncher";
import { CaiChatPanel } from "@/components/tools/CaiChatPanel";
import { OrchestratorPanel } from "@/components/tools/OrchestratorPanel";
import { PageHeader } from "@/components/sd/primitives";

export const Route = createFileRoute("/_authenticated/tools/red")({
  head: () => ({ meta: [{ title: "Red Team Tools — SecureDash" }] }),
  validateSearch: (search: Record<string, unknown>) => ({
    taskId: typeof search.taskId === "string" ? search.taskId : undefined,
  }),
  beforeLoad: ({ context }) => {
    requireToolAccess(context.me, "red");
  },
  component: RedToolsPage,
});

type Tab = "tools" | "cai" | "orchestrator";

const TAB_LABELS: { key: Tab; label: string; icon: string }[] = [
  { key: "tools", label: "Direct Tools", icon: "🔧" },
  { key: "cai", label: "CAI Chat", icon: "🤖" },
  { key: "orchestrator", label: "AI Orchestrator", icon: "🧠" },
];

function RedToolsPage() {
  const { taskId } = Route.useSearch();
  const [activeTab, setActiveTab] = useState<Tab>("tools");

  return (
    <div className="mx-auto max-w-[900px]">
      <PageHeader
        title="Red Team Tools"
        subtitle="Launch offensive validation jobs against monitored assets."
      />

      {/* Tab Bar */}
      <div
        style={{
          display: "flex",
          gap: 4,
          marginBottom: 0,
          background: "#0f172a",
          border: "1px solid #1e293b",
          borderRadius: 12,
          padding: 4,
        }}
      >
        {TAB_LABELS.map(({ key, label, icon }) => (
          <button
            key={key}
            id={`red-tools-tab-${key}`}
            onClick={() => setActiveTab(key)}
            style={{
              flex: 1,
              padding: "9px 12px",
              borderRadius: 9,
              border: "none",
              cursor: "pointer",
              fontSize: 13,
              fontWeight: activeTab === key ? 700 : 500,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 6,
              background:
                activeTab === key
                  ? "linear-gradient(135deg, #4f46e5, #7c3aed)"
                  : "transparent",
              color: activeTab === key ? "#fff" : "#64748b",
              transition: "all 0.2s",
            }}
          >
            <span>{icon}</span>
            {label}
            {key === "orchestrator" && (
              <span
                style={{
                  padding: "1px 7px",
                  borderRadius: 999,
                  fontSize: 9,
                  fontWeight: 700,
                  background: "#6366f122",
                  color: activeTab === key ? "#c7d2fe" : "#818cf8",
                  border: "1px solid #6366f144",
                  letterSpacing: "0.06em",
                }}
              >
                AI
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === "tools" && (
        <>
          <ToolLauncher team="red" taskId={taskId} />
        </>
      )}
      {activeTab === "cai" && (
        <>
          <CaiChatPanel team="red" taskId={taskId} />
        </>
      )}
      {activeTab === "orchestrator" && (
        <OrchestratorPanel taskId={taskId} />
      )}
    </div>
  );
}
