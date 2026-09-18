/**
 * Red-team supervised chat client — sessions, tool-call decisions, summary + SSE.
 */
import { apiBaseUrl, apiFetch, getAccessToken } from "@/lib/api-client";
import type {
  RedTeamChatSession,
  RedTeamChatStreamEvent,
  RedTeamChatTeam,
} from "@/lib/red-team-chat-types";

const BASE = "/red-team-chat";

/** Start Job. */
export function createRedTeamChatSession(body: {
  team: RedTeamChatTeam;
  message?: string;
  task_id?: string | null;
  target?: string | null;
}): Promise<RedTeamChatSession> {
  return apiFetch<RedTeamChatSession>(`${BASE}/sessions`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

/** Send a prompt. */
export function sendRedTeamChatMessage(
  sessionId: string,
  content: string,
  team: RedTeamChatTeam,
): Promise<RedTeamChatSession> {
  return apiFetch<RedTeamChatSession>(`${BASE}/sessions/${sessionId}/messages?team=${team}`, {
    method: "POST",
    body: JSON.stringify({ content }),
  });
}

/** Approve or stop a proposed/running tool call. */
export function decideRedTeamChatToolCall(
  sessionId: string,
  callId: string,
  decision: "approve" | "stop",
  team: RedTeamChatTeam,
  reason?: string,
): Promise<RedTeamChatSession> {
  return apiFetch<RedTeamChatSession>(
    `${BASE}/sessions/${sessionId}/tool-calls/${callId}/decision?team=${team}`,
    {
      method: "POST",
      body: JSON.stringify({ decision, reason: reason ?? null }),
    },
  );
}

/** End Job. */
export function stopRedTeamChatSession(
  sessionId: string,
  team: RedTeamChatTeam,
): Promise<RedTeamChatSession> {
  return apiFetch<RedTeamChatSession>(`${BASE}/sessions/${sessionId}/stop?team=${team}`, {
    method: "POST",
  });
}

/** URL for the downloadable session summary (Markdown). */
export function redTeamChatSummaryUrl(sessionId: string, team: RedTeamChatTeam): string {
  return `${apiBaseUrl()}${BASE}/sessions/${sessionId}/summary?team=${team}`;
}

/** Fetch the session summary as Markdown text. */
export async function fetchRedTeamChatSummary(
  sessionId: string,
  team: RedTeamChatTeam,
): Promise<string> {
  const token = await getAccessToken();
  const res = await fetch(redTeamChatSummaryUrl(sessionId, team), {
    headers: token ? { authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error(`Summary ${res.status}: ${await res.text().catch(() => res.statusText)}`);
  return res.text();
}

export type StreamHandlers = {
  onEvent: (ev: RedTeamChatStreamEvent) => void;
  onError?: (err: Error) => void;
  onDone?: () => void;
};

/** Open SSE via fetch+ReadableStream (EventSource cannot set Authorization). */
export async function openRedTeamChatEventStream(
  sessionId: string,
  team: RedTeamChatTeam,
  handlers: StreamHandlers,
  afterSeq = 0,
): Promise<{ abort: () => void }> {
  const ac = new AbortController();
  const token = await getAccessToken();
  const url = `${apiBaseUrl()}${BASE}/sessions/${sessionId}/events?team=${team}&after_seq=${afterSeq}`;

  (async () => {
    try {
      const res = await fetch(url, {
        headers: token ? { authorization: `Bearer ${token}` } : {},
        signal: ac.signal,
      });
      if (!res.ok || !res.body) {
        throw new Error(`SSE ${res.status}: ${await res.text().catch(() => res.statusText)}`);
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const parts = buf.split("\n\n");
        buf = parts.pop() ?? "";
        for (const block of parts) {
          const dataLine = block.split("\n").find((l) => l.startsWith("data: "));
          if (!dataLine) continue;
          try {
            const ev = JSON.parse(dataLine.slice(6)) as RedTeamChatStreamEvent;
            handlers.onEvent(ev);
            if (ev.type === "ended") {
              handlers.onDone?.();
              ac.abort();
              return;
            }
          } catch {
            /* ignore parse */
          }
        }
      }
      handlers.onDone?.();
    } catch (e) {
      if ((e as Error).name === "AbortError") return;
      handlers.onError?.(e instanceof Error ? e : new Error(String(e)));
    }
  })();

  return { abort: () => ac.abort() };
}
