/**
 * Patch guidance helpers — run with:
 *   bun run src/lib/patch-guidance.test.ts
 */
import type { Patch } from "./security";
import {
  defaultAssistStack,
  findingForPatch,
  guidanceForPatch,
  normalizePlaybook,
  tailorFix,
} from "./patch-guidance";

let assertions = 0;
function check(message: string, condition: unknown): void {
  assertions += 1;
  if (!condition) {
    throw new Error(`FAIL: ${message}`);
  }
}

const patch: Patch = {
  id: "p1",
  finding_id: "f1",
  asset_id: null,
  title: "Restrict bind address and close unused ports",
  playbook: "network-hardening",
  status: "proposed",
  evidence: ["80/tcp open http"],
  applied_at: null,
};

check("known playbook stays", normalizePlaybook("api-hardening") === "api-hardening");
check("unknown playbook falls back", normalizePlaybook("not-a-book") === "general-hardening");
check("empty playbook falls back", normalizePlaybook("") === "general-hardening");

const net = guidanceForPatch(patch, undefined, "http://127.0.0.1:10200/");
check("network summary mentions bind", /bind|listen/i.test(net.summary));
check("network recommendations mention unused", net.recommendations.some((r) => /unused|bind|firewall/i.test(r)));
check("network example is compose or listen", /127\.0\.0\.1|ports:/i.test(net.example.code));
check("assist prompt is defensive", /defensive fix/i.test(net.assistPrompt) && !/exploit/i.test(net.assistPrompt.split("Return")[0] || ""));

const finding = {
  id: "f1",
  title: "Open port 80/tcp (http)",
  severity: "medium",
  source_tool: "nmap",
  evidence: "80/tcp open http",
  remediation: "Bind the shop to loopback only",
};
const withFinding = guidanceForPatch(patch, finding, "http://127.0.0.1:10200/");
check("finding remediation is first recommendation", withFinding.recommendations[0] === "Bind the shop to loopback only");
check("assist prompt includes evidence", withFinding.assistPrompt.includes("80/tcp open http"));

check("findingForPatch matches id", findingForPatch(patch, [finding])?.id === "f1");
check("findingForPatch misses unknown", findingForPatch(patch, [{ ...finding, id: "other" }]) === undefined);

check("default stack for network is linux", defaultAssistStack("network-hardening") === "linux");
check("default stack for api is express", defaultAssistStack("api-hardening") === "express");
check("default stack for gobuster playbook is nginx", defaultAssistStack("content-discovery-hardening") === "nginx");

const linux = tailorFix(patch, "linux", "Juice Shop lab", finding, "http://127.0.0.1:10200/");
check("linux tailor includes ufw", /ufw/i.test(linux.code));
check("linux tailor includes notes", /Juice Shop lab/.test(linux.code));

const apiPatch: Patch = { ...patch, playbook: "api-hardening", title: "Add authentication and rate limits on API/REST surfaces" };
const express = tailorFix(apiPatch, "express", "", undefined, "http://127.0.0.1:10200/");
check("express api fix rate-limits", /rateLimit|limiter/.test(express.code));
check("express api fix binds loopback", /127\.0\.0\.1/.test(express.code));

console.log(`patch-guidance.test.ts: ${assertions} assertions passed`);
