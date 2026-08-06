/**
 * CAI chat client — sessions + fetch-based SSE (Bearer auth).
 */
import { apiBaseUrl, apiFetch, getAccessToken } from "@/lib/api-client";
import type { CaiSession, CaiStreamEvent, CaiTeam } from "@/lib/cai-chat-types";

export function createCaiSession(body: {
  team: CaiTeam;
  message?: string;
  task_id?: string | null;
}): Promise<CaiSession> {
  return apiFetch<CaiSession>("/cai/sessions", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function sendCaiMessage(sessionId: string, content: string, team: CaiTeam): Promise<CaiSession> {
  return apiFetch<CaiSession>(`/cai/sessions/${sessionId}/messages?team=${team}`, {
    method: "POST",
    body: JSON.stringify({ content }),
  });
}

export function stopCaiSession(sessionId: string, team: CaiTeam): Promise<CaiSession> {
  return apiFetch<CaiSession>(`/cai/sessions/${sessionId}/stop?team=${team}`, {
    method: "POST",
  });
}

export type StreamHandlers = {
  onEvent: (ev: CaiStreamEvent) => void;
  onError?: (err: Error) => void;
  onDone?: () => void;
};

/** Open SSE via fetch+ReadableStream (EventSource cannot set Authorization). */
export async function openCaiEventStream(
  sessionId: string,
  team: CaiTeam,
  handlers: StreamHandlers,
  afterSeq = 0,
): Promise<{ abort: () => void }> {
  const ac = new AbortController();
  const token = await getAccessToken();
  const url = `${apiBaseUrl()}/cai/sessions/${sessionId}/events?team=${team}&after_seq=${afterSeq}`;

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
            const ev = JSON.parse(dataLine.slice(6)) as CaiStreamEvent;
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
