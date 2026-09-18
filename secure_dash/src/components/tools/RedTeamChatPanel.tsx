import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";
import {
  createRedTeamChatSession,
  decideRedTeamChatToolCall,
  fetchRedTeamChatSummary,
  openRedTeamChatEventStream,
  sendRedTeamChatMessage,
  stopRedTeamChatSession,
} from "@/lib/red-team-chat";
import type {
  RedTeamChatChannel,
  RedTeamChatStreamEvent,
  RedTeamChatTeam,
} from "@/lib/red-team-chat-types";
import { looksLikeTarget } from "@/components/tools/ToolLauncher";

type Line = {
  seq: number;
  type: string;
  channel: RedTeamChatChannel;
  text: string;
  callId?: string | null;
  tool?: string | null;
};

type Pending = { callId: string; tool: string; running: boolean };

const CHANNEL_COLOR: Record<RedTeamChatChannel, string> = {
  user: "var(--text-primary)",
  agent: "var(--accent-ember)",
  tool: "#8ab4f8",
  system: "var(--text-muted)",
};

export type RedTeamChatPanelHandle = {
  startJob: () => Promise<void>;
  active: boolean;
  starting: boolean;
};

type Props = {
  team: RedTeamChatTeam;
  taskId?: string;
  /** UI target — scoped into the agent system prompt for this session. */
  target?: string;
  onActiveChange?: (active: boolean) => void;
  onStartingChange?: (starting: boolean) => void;
};

export const RedTeamChatPanel = forwardRef<RedTeamChatPanelHandle, Props>(function RedTeamChatPanel(
  { team, taskId, target = "", onActiveChange, onStartingChange },
  ref,
) {
  const [prompt, setPrompt] = useState("");
  const [lines, setLines] = useState<Line[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [status, setStatus] = useState<string>("idle");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [starting, setStarting] = useState(false);
  const [pending, setPending] = useState<Pending | null>(null);
  const [endedSession, setEndedSession] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const streamAbort = useRef<{ abort: () => void } | null>(null);
  const lastSeq = useRef(0);

  const active = !!sessionId && !["stopped", "ended", "failed"].includes(status);

  useEffect(() => {
    onActiveChange?.(active);
  }, [active, onActiveChange]);

  useEffect(() => {
    onStartingChange?.(starting);
  }, [starting, onStartingChange]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [lines]);

  useEffect(() => {
    return () => streamAbort.current?.abort();
  }, []);

  function pushEvent(ev: RedTeamChatStreamEvent) {
    if (ev.seq) lastSeq.current = Math.max(lastSeq.current, ev.seq);

    switch (ev.type) {
      case "status":
        if (ev.text) setStatus(ev.text);
        if (ev.text === "ready") {
          setBusy(false);
          setPending(null);
        }
        // Keep "target: …" status lines visible in the transcript.
        if (!ev.text || ev.text === "ready") return;
        break;
      case "started":
        setStatus(ev.text || "running");
        break;
      case "error":
        setError(ev.text || "Red-team chat error");
        setBusy(false);
        setPending(null);
        break;
      case "ended":
        setStatus("ended");
        setBusy(false);
        setPending(null);
        break;
      case "tool_call_pending":
        setBusy(true);
        if (ev.call_id) setPending({ callId: ev.call_id, tool: ev.tool || "tool", running: false });
        break;
      case "tool_call_approved":
        setPending((p) => (p && p.callId === ev.call_id ? { ...p, running: true } : p));
        break;
      case "tool_call_stopped":
        setPending((p) => (p && p.callId === ev.call_id ? null : p));
        break;
      case "tool_result":
        setPending((p) => (p && p.callId === ev.call_id ? null : p));
        break;
      default:
        break;
    }

    setLines((prev) => [
      ...prev,
      { seq: ev.seq, type: ev.type, channel: ev.channel, text: ev.text, callId: ev.call_id, tool: ev.tool },
    ]);
  }

  async function attachStream(id: string) {
    streamAbort.current?.abort();
    streamAbort.current = await openRedTeamChatEventStream(
      id,
      team,
      {
        onEvent: pushEvent,
        onError: (err) => setError(err.message),
        onDone: () => setBusy(false),
      },
      lastSeq.current,
    );
  }

  async function onStartJob() {
    const scoped = target.trim();
    if (!looksLikeTarget(scoped)) {
      setError("Enter a valid target (IP or hostname) above before starting");
      return;
    }
    setError(null);
    setLines([]);
    lastSeq.current = 0;
    setPending(null);
    setEndedSession(null);
    setBusy(false);
    setStarting(true);
    try {
      const session = await createRedTeamChatSession({
        team,
        task_id: taskId ?? null,
        target: scoped,
      });
      setSessionId(session.id);
      setStatus(session.status);
      await attachStream(session.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Start Job failed");
    } finally {
      setStarting(false);
    }
  }

  useImperativeHandle(
    ref,
    () => ({
      startJob: onStartJob,
      active,
      starting,
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps -- startJob closes over latest target/status
    [active, starting, target, team, taskId],
  );

  async function onSend(e: React.FormEvent) {
    e.preventDefault();
    const content = prompt.trim();
    if (!content) {
      setError("Enter a non-empty prompt");
      return;
    }
    if (!sessionId || busy) return;
    setError(null);
    setBusy(true);
    try {
      await sendRedTeamChatMessage(sessionId, content, team);
      setPrompt("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Send failed");
      setBusy(false);
    }
  }

  async function onStopCurrentTool() {
    if (!sessionId || !pending) return;
    try {
      await decideRedTeamChatToolCall(sessionId, pending.callId, "stop", team);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Stop failed");
    }
  }

  async function onApprove(callId: string) {
    if (!sessionId) return;
    try {
      await decideRedTeamChatToolCall(sessionId, callId, "approve", team);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Approve failed");
    }
  }

  async function onEndJob() {
    if (!sessionId) return;
    const ending = sessionId;
    try {
      await stopRedTeamChatSession(ending, team);
      setStatus("stopped");
      setEndedSession(ending);
    } catch (err) {
      setError(err instanceof Error ? err.message : "End Job failed");
    } finally {
      streamAbort.current?.abort();
      setBusy(false);
      setPending(null);
      setSessionId(null);
    }
  }

  async function onDownloadSummary() {
    if (!endedSession) return;
    try {
      const md = await fetchRedTeamChatSummary(endedSession, team);
      const blob = new Blob([md], { type: "text/markdown" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `red-team-chat-${endedSession}.md`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Download failed");
    }
  }

  return (
    <div className="mt-8 flex flex-col gap-3">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="text-sm font-semibold tracking-tight">Red Team Chat</h2>
        <span className="mono micro" style={{ color: "var(--text-muted)" }}>
          {status}
          {busy ? " · busy" : ""}
          {target.trim() ? ` · ${target.trim()}` : ""}
          {taskId ? ` · task ${taskId.slice(0, 8)}…` : ""}
        </span>
      </div>

      {error && (
        <div
          role="alert"
          className="rounded-sm px-3 py-2 text-sm"
          style={{
            border: "1px solid var(--border-hairline)",
            background: "var(--surface)",
            color: "var(--accent-ember)",
          }}
        >
          {error}
        </div>
      )}

      <div
        className="mono max-h-[360px] min-h-[200px] overflow-y-auto rounded-sm p-3 text-[12px] leading-5"
        style={{
          background: "var(--bg-base)",
          border: "1px solid var(--border-hairline)",
          color: "var(--text-secondary)",
        }}
      >
        {lines.length === 0 ? (
          <div style={{ color: "var(--text-muted)" }}>
            Enter a target above, press Start job, then message the {team} HexStrike agent. Every
            tool call it proposes waits for your approval before it runs.
          </div>
        ) : (
          lines.map((l, i) => {
            const isPendingLine =
              l.type === "tool_call_pending" && pending?.callId === l.callId;
            return (
              <div
                key={`${l.seq}-${i}`}
                style={
                  isPendingLine
                    ? { background: "var(--surface)", borderRadius: 2, padding: "2px 4px" }
                    : undefined
                }
              >
                <span style={{ color: CHANNEL_COLOR[l.channel] }}>[{l.channel}] </span>
                {l.text}
                {isPendingLine && pending && (
                  <span className="ml-2 inline-flex gap-2">
                    <button
                      type="button"
                      onClick={() => onApprove(pending.callId)}
                      className="micro rounded-sm px-2 py-0.5"
                      style={{ background: "var(--accent-ember)", color: "var(--bg-base)" }}
                    >
                      Approve
                    </button>
                    <button
                      type="button"
                      onClick={onStopCurrentTool}
                      className="micro rounded-sm px-2 py-0.5"
                      style={{
                        border: "1px solid var(--border-hairline)",
                        color: "var(--text-primary)",
                      }}
                    >
                      Stop current tool
                    </button>
                  </span>
                )}
              </div>
            );
          })
        )}
        <div ref={bottomRef} />
      </div>

      <form onSubmit={onSend} className="flex flex-wrap gap-2">
        <input
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder={active ? "Message the HexStrike agent…" : "Start a job to begin"}
          className="mono min-w-[220px] flex-1 rounded-sm px-3 py-2 text-sm"
          style={{
            background: "var(--surface-raised)",
            border: "1px solid var(--border-hairline)",
            color: "var(--text-primary)",
          }}
          disabled={!active || busy}
        />
        <button
          type="submit"
          disabled={!active || busy}
          className="rounded-sm px-3 py-2 text-sm font-medium disabled:opacity-60"
          style={{ background: "var(--accent-ember)", color: "var(--bg-base)" }}
        >
          Send
        </button>
        <button
          type="button"
          onClick={onStartJob}
          disabled={active || starting}
          className="rounded-sm px-3 py-2 text-sm disabled:opacity-60"
          style={{
            background: "var(--surface-raised)",
            border: "1px solid var(--border-hairline)",
            color: "var(--text-primary)",
          }}
        >
          Start Job
        </button>
        <button
          type="button"
          onClick={onStopCurrentTool}
          disabled={!active || !busy || !pending}
          className="rounded-sm px-3 py-2 text-sm disabled:opacity-60"
          style={{
            background: "var(--surface-raised)",
            border: "1px solid var(--border-hairline)",
            color: "var(--text-primary)",
          }}
        >
          Stop current tool
        </button>
        <button
          type="button"
          onClick={onEndJob}
          disabled={!active}
          className="rounded-sm px-3 py-2 text-sm disabled:opacity-60"
          style={{
            background: "var(--surface-raised)",
            border: "1px solid var(--border-hairline)",
            color: "var(--text-primary)",
          }}
        >
          End Job
        </button>
      </form>

      {endedSession && (
        <button
          type="button"
          onClick={onDownloadSummary}
          className="mono micro self-start rounded-sm px-2 py-1"
          style={{ border: "1px solid var(--border-hairline)", color: "var(--text-secondary)" }}
        >
          Download summary of last job
        </button>
      )}
    </div>
  );
});
