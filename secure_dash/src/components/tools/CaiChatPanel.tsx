import { useEffect, useRef, useState } from "react";
import {
  createCaiSession,
  openCaiEventStream,
  sendCaiMessage,
  stopCaiSession,
} from "@/lib/cai-chat";
import type { CaiStreamEvent, CaiTeam } from "@/lib/cai-chat-types";

type Line = { seq: number; type: string; text: string };

export function CaiChatPanel({ team, taskId }: { team: CaiTeam; taskId?: string }) {
  const [prompt, setPrompt] = useState("");
  const [lines, setLines] = useState<Line[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [status, setStatus] = useState<string>("idle");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const streamAbort = useRef<{ abort: () => void } | null>(null);
  const lastSeq = useRef(0);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [lines]);

  useEffect(() => {
    return () => streamAbort.current?.abort();
  }, []);

  function pushEvent(ev: CaiStreamEvent) {
    if (ev.seq) lastSeq.current = Math.max(lastSeq.current, ev.seq);
    if (ev.type === "status" && !ev.text) return;
    if (ev.type === "error") setError(ev.text || "CAI error");
    if (ev.type === "ended") setStatus("ended");
    if (ev.type === "started" || ev.type === "status") setStatus(ev.text || ev.type);
    setLines((prev) => [...prev, { seq: ev.seq, type: ev.type, text: ev.text }]);
  }

  async function attachStream(id: string) {
    streamAbort.current?.abort();
    streamAbort.current = await openCaiEventStream(
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

  async function onSend(e: React.FormEvent) {
    e.preventDefault();
    const content = prompt.trim();
    if (!content) {
      setError("Enter a non-empty prompt");
      return;
    }
    setError(null);
    setBusy(true);
    try {
      if (!sessionId) {
        const session = await createCaiSession({
          team,
          message: content,
          task_id: taskId ?? null,
        });
        setSessionId(session.id);
        setStatus(session.status);
        setPrompt("");
        await attachStream(session.id);
      } else {
        await sendCaiMessage(sessionId, content, team);
        setPrompt("");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Send failed");
      setBusy(false);
    }
  }

  async function onStop() {
    if (!sessionId) return;
    setBusy(true);
    try {
      await stopCaiSession(sessionId, team);
      setStatus("stopped");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Stop failed");
    } finally {
      streamAbort.current?.abort();
      setBusy(false);
    }
  }

  return (
    <div className="mt-8 flex flex-col gap-3">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="text-sm font-semibold tracking-tight">CAI Chat</h2>
        <span className="mono micro" style={{ color: "var(--text-muted)" }}>
          {status}
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
            Send a prompt to start <code>uv run cai</code> on the {team} worker. Output streams here.
          </div>
        ) : (
          lines.map((l, i) => (
            <div key={`${l.seq}-${i}`}>
              <span style={{ color: "var(--text-muted)" }}>[{l.type}] </span>
              {l.text}
            </div>
          ))
        )}
        <div ref={bottomRef} />
      </div>

      <form onSubmit={onSend} className="flex gap-2">
        <input
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="Message CAI…"
          className="mono flex-1 rounded-sm px-3 py-2 text-sm"
          style={{
            background: "var(--surface-raised)",
            border: "1px solid var(--border-hairline)",
            color: "var(--text-primary)",
          }}
          disabled={busy && status === "starting"}
        />
        <button
          type="submit"
          disabled={busy && !sessionId}
          className="rounded-sm px-3 py-2 text-sm font-medium disabled:opacity-60"
          style={{ background: "var(--accent-ember)", color: "var(--bg-base)" }}
        >
          {sessionId ? "Send" : "Start"}
        </button>
        <button
          type="button"
          onClick={onStop}
          disabled={!sessionId || status === "stopped" || status === "ended"}
          className="rounded-sm px-3 py-2 text-sm disabled:opacity-60"
          style={{
            background: "var(--surface-raised)",
            border: "1px solid var(--border-hairline)",
            color: "var(--text-primary)",
          }}
        >
          Stop
        </button>
      </form>
    </div>
  );
}
