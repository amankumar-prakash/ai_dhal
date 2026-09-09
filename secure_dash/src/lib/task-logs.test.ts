/**
 * Task log helpers — run with: bun run src/lib/task-logs.test.ts
 */
import { formatRawOutput, isLiveJobStatus, progressLines, runHeadline } from "./task-logs";

let assertions = 0;
function check(message: string, condition: unknown): void {
  assertions += 1;
  if (!condition) {
    throw new Error(`FAIL: ${message}`);
  }
}

check("queued is live", isLiveJobStatus("queued") === true);
check("running is live", isLiveJobStatus("running") === true);
check("completed is not live", isLiveJobStatus("completed") === false);
check("missing status is not live", isLiveJobStatus(undefined) === false);

check("stdout wins", formatRawOutput({ stdout: "80/tcp open http", extra: 1 }) === "80/tcp open http");
check("empty raw is blank", formatRawOutput({}) === "");
check("object pretty-prints", formatRawOutput({ ports: [80] }).includes("80"));

const toolRun = {
  id: "1",
  job_id: "j",
  team: "red",
  tool_name: "nmap_scan",
  command_summary: "nmap -sV target",
  exit_code: 0,
  raw_output: {},
  started_at: "2026-09-04T10:00:00Z",
  finished_at: "2026-09-04T10:01:00Z",
};
const fromTools = progressLines([], [toolRun]);
check("tools become log lines", fromTools[0]?.message === "nmap_scan — nmap -sV target");

const progressFirst = progressLines([{ kind: "thinking", message: "planning" }], [toolRun]);
check("progress events win over tools", progressFirst[0]?.message === "planning");

check("in-progress running is live", runHeadline({ taskStatus: "in_progress", jobStatus: "running" }).live === true);
check("completed headline", runHeadline({ taskStatus: "completed", jobStatus: "completed" }).label === "Last run — completed");
check("failed headline", runHeadline({ taskStatus: "in_progress", jobStatus: "failed" }).label === "Last run — failed");
check("stopped headline", runHeadline({ taskStatus: "blocked", jobStatus: "cancelled", stopped: true }).label === "Last run — stopped");
check("never started", runHeadline({ taskStatus: "assigned" }).label === "No run yet");

console.log(`task-logs.test.ts: ${assertions} assertions passed`);
