import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown, ChevronRight, ScrollText } from "lucide-react";
import { absTime, duration, relTime } from "@/lib/security";
import { formatRawOutput, kindTone, progressLines, runHeadline } from "@/lib/task-logs";
import type { Task } from "@/lib/rbac-types";
import type { TaskResults, TaskToolRun } from "@/lib/tasks-api";
import { EmptyState, ErrorBanner, Eyebrow, Panel } from "@/components/sd/primitives";
import { useTaskClock } from "@/components/tasks/TaskRunProgress";

function ToolRunRow({ tool }: { tool: TaskToolRun }) {
  const [open, setOpen] = useState(false);
  const raw = formatRawOutput(tool.raw_output);
  const failed = tool.exit_code != null && tool.exit_code !== 0;
  const ran =
    tool.started_at && tool.finished_at ? duration(tool.started_at, tool.finished_at) : null;

  return (
    <li className="border-b last:border-b-0" style={{ borderColor: "var(--border-hairline)" }}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full flex-wrap items-start gap-3 px-4 py-3 text-left"
      >
        {open ? (
          <ChevronDown size={14} strokeWidth={1.5} style={{ color: "var(--text-muted)" }} />
        ) : (
          <ChevronRight size={14} strokeWidth={1.5} style={{ color: "var(--text-muted)" }} />
        )}
        <div className="min-w-0 flex-1">
          <div className="text-sm">{tool.tool_name}</div>
          <div className="mono micro mt-1" style={{ color: "var(--text-muted)" }}>
            {tool.command_summary || "No command summary"}
            {tool.started_at ? ` · ${relTime(tool.started_at)}` : ""}
            {ran ? ` · ${ran}` : ""}
          </div>
        </div>
        <span
          className="mono micro"
          style={{ color: failed ? "var(--accent-ember)" : "var(--text-secondary)" }}
        >
          {tool.exit_code == null ? "running" : `exit ${tool.exit_code}`}
        </span>
      </button>
      {open && (
        <pre
          className="mono mx-4 mb-3 max-h-[280px] overflow-auto rounded-sm p-3 text-[12px] leading-5 whitespace-pre-wrap"
          style={{
            background: "var(--bg-base)",
            border: "1px solid var(--border-hairline)",
            color: "var(--text-secondary)",
          }}
        >
          {raw || "No raw output recorded for this tool."}
        </pre>
      )}
    </li>
  );
}

export function TaskLogs({
  task,
  results,
}: {
  task: Task;
  results: TaskResults | undefined;
}) {
  const job = results?.job ?? null;
  const tools = results?.tools ?? [];
  const stopped = task.status === "blocked" || job?.status === "cancelled";
  const headline = runHeadline({
    taskStatus: task.status,
    jobStatus: job?.status,
    stopped,
  });
  const lines = useMemo(
    () => progressLines(results?.progress, tools),
    [results?.progress, tools],
  );
  const started = job?.started_at ?? task.started_at;
  const finished = job?.finished_at ?? task.completed_at;
  const estimate =
    job?.estimated_duration_seconds && job.estimated_duration_seconds > 0
      ? job.estimated_duration_seconds
      : 900;
  const clock = useTaskClock(started, estimate, headline.live, finished);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = logRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [lines.length, headline.live]);

  if (!job && lines.length === 0 && tools.length === 0) {
    return (
      <EmptyState
        icon={<ScrollText size={20} strokeWidth={1.5} />}
        label="No run logs yet. Start the task to capture HexStrike output here."
      />
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <Panel className="p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            {headline.live && (
              <span className="live-dot size-2 rounded-full" style={{ background: "var(--accent-ember)" }} />
            )}
            <span className="text-sm">{headline.label}</span>
          </div>
          {started && (
            <span className="mono micro" style={{ color: "var(--text-muted)" }}>
              {absTime(started)}
              {finished && !headline.live ? ` → ${absTime(finished)}` : ""}
              {` · ${clock.elapsedLabel}`}
            </span>
          )}
        </div>

        <div className="mt-4 grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
          <div>
            <Eyebrow>Job</Eyebrow>
            <div className="mono mt-1">{job?.status ?? "—"}</div>
          </div>
          <div>
            <Eyebrow>Started</Eyebrow>
            <div className="mono mt-1">{relTime(started)}</div>
          </div>
          <div>
            <Eyebrow>{headline.live ? "Elapsed" : "Finished"}</Eyebrow>
            <div className="mono mt-1">{headline.live ? clock.elapsedLabel : relTime(finished)}</div>
          </div>
          <div>
            <Eyebrow>Tools</Eyebrow>
            <div className="mono mt-1">{tools.length}</div>
          </div>
        </div>

        {job?.error && (
          <div className="mt-4">
            <ErrorBanner message={job.error} />
          </div>
        )}

        <div
          ref={logRef}
          className="mono mt-4 max-h-[420px] min-h-[200px] overflow-y-auto rounded-sm p-3 text-[12px] leading-5"
          style={{
            background: "var(--bg-base)",
            border: "1px solid var(--border-hairline)",
            color: "var(--text-secondary)",
          }}
          aria-live={headline.live ? "polite" : "off"}
        >
          {lines.length === 0 ? (
            <div style={{ color: "var(--text-muted)" }}>
              {headline.live
                ? "Waiting for HexStrike tools to report…"
                : "No progress events were recorded for this run."}
            </div>
          ) : (
            lines.map((line, i) => (
              <div key={line.id ?? `${line.kind}-${i}`} className="flex gap-2">
                {line.created_at && (
                  <span className="shrink-0" style={{ color: "var(--text-muted)" }}>
                    {new Date(line.created_at).toISOString().slice(11, 19)}
                  </span>
                )}
                <span>
                  <span style={{ color: kindTone(line.kind) }}>[{line.kind}] </span>
                  {line.message}
                </span>
              </div>
            ))
          )}
        </div>
      </Panel>

      <Panel>
        <div
          className="border-b px-4 py-3"
          style={{ borderColor: "var(--border-hairline)" }}
        >
          <Eyebrow>Tool output</Eyebrow>
        </div>
        {tools.length === 0 ? (
          <EmptyState
            icon={<ScrollText size={20} strokeWidth={1.5} />}
            label={
              headline.live
                ? "Tool results appear here as each HexStrike call finishes."
                : "This run did not record individual tool output."
            }
          />
        ) : (
          <ul>
            {tools.map((tool) => (
              <ToolRunRow key={tool.id} tool={tool} />
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}
