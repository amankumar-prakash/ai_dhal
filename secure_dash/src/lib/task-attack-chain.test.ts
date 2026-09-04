/**
 * Attack-chain grouping and detail helpers — run with:
 *   bun run src/lib/task-attack-chain.test.ts
 */
import {
  categoryOf,
  detailsForCategory,
  findingsForTool,
  formatEvidence,
  stepsFromResults,
} from "./task-attack-chain";
import type { TaskResults, TaskToolRun } from "./tasks-api";

let assertions = 0;
function check(message: string, condition: unknown): void {
  assertions += 1;
  if (!condition) {
    throw new Error(`FAIL: ${message}`);
  }
}

const tool: TaskToolRun = {
  id: "tool-1",
  job_id: "job-1",
  team: "red",
  tool_name: "nmap_scan",
  command_summary: "nmap -sV http://127.0.0.1:10200/",
  exit_code: 0,
  raw_output: { stdout: "80/tcp open http" },
  started_at: "2026-09-04T10:00:00Z",
  finished_at: "2026-09-04T10:01:12Z",
};

const results: TaskResults = {
  task: { id: "t1" } as TaskResults["task"],
  job: null,
  tools: [tool],
  findings: [
    {
      id: "f1",
      title: "Open HTTP port",
      severity: "medium",
      source_tool: "nmap_scan",
      evidence: "80/tcp open http",
      remediation: "Restrict bind address",
    },
  ],
  chain: {
    id: "c1",
    steps: [
      {
        id: "s1",
        stage: "recon",
        sequence: 1,
        title: "nmap_scan on target",
        severity: "info",
        category: "tools",
        source_tool: "nmap_scan",
        evidence: "80/tcp open http",
      },
      {
        id: "s2",
        stage: "recon",
        sequence: 2,
        title: "Open HTTP port",
        severity: "medium",
        category: "findings",
        source_tool: "nmap_scan",
        finding_id: "f1",
        evidence: "80/tcp open http",
      },
    ],
  },
  patches: [],
};

check("tools category from step", categoryOf(results.chain!.steps[0]!) === "tools");
check("findings category from step", categoryOf(results.chain!.steps[1]!) === "findings");
check("missing category falls back to stage", categoryOf({
  id: "x",
  stage: "execution",
  sequence: 3,
  title: "rce",
  severity: "critical",
}) === "execution");

check("chain steps win over tools fallback", stepsFromResults(results).length === 2);

const noChain = { ...results, chain: null };
check("fallback uses tools + findings", stepsFromResults(noChain).length === 2);
check("fallback first step is the tool", stepsFromResults(noChain)[0]?.category === "tools");

check("format string evidence", formatEvidence("80/tcp open http") === "80/tcp open http");
check("format array evidence", formatEvidence([{ output: "dir found" }]).includes("dir found"));
check("empty evidence is blank", formatEvidence(null) === "");

check("findings match tool name", findingsForTool("nmap_scan", results.findings).length === 1);
check("findings ignore other tools", findingsForTool("gobuster", results.findings).length === 0);

const toolDetails = detailsForCategory("tools", results.chain!.steps.slice(0, 1), results);
check("tools details use tool run name", toolDetails[0]?.title === "nmap_scan");
check("tools details include command", toolDetails[0]?.command === tool.command_summary);
check("tools details include started_at", toolDetails[0]?.startedAt === tool.started_at);
check("tools details include related findings", toolDetails[0]?.findings[0]?.title === "Open HTTP port");

const findingDetails = detailsForCategory("findings", results.chain!.steps.slice(1), results);
check("findings details use finding title", findingDetails[0]?.title === "Open HTTP port");
check("findings details include remediation", findingDetails[0]?.remediation === "Restrict bind address");

console.log(`task-attack-chain.test.ts: ${assertions} assertions passed`);
