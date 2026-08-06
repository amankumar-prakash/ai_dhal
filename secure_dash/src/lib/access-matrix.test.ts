/**
 * Assertion-based logic checks for the Access Matrix — no test framework is
 * declared in package.json (no vitest/jest), so this is a plain, dependency
 * free script rather than a `describe`/`it` suite. It exits non-zero on the
 * first failed assertion and can be run with any TS-capable runtime, e.g.:
 *   bun run src/lib/access-matrix.test.ts
 * (the repo ships a bun.lock; bun runs .ts files directly with no build step)
 */
import {
  canAccessAdminPanel,
  canAccessOpsDashboard,
  canAssignAdminRole,
  canReviewOrClose,
  capabilityFor,
  roleInList,
} from "./access-matrix";
import type { AppRole } from "./rbac-types";

let assertions = 0;
function check(message: string, condition: unknown): void {
  assertions += 1;
  if (!condition) {
    throw new Error(`FAIL: ${message}`);
  }
}

const ROLES: AppRole[] = ["user", "security_analyst", "security_manager", "admin"];

// --- Admin: provisioning-only, denied every ops surface (US1) ---
check("admin can access admin panel", canAccessAdminPanel("admin") === true);
check("admin cannot access ops dashboard", canAccessOpsDashboard("admin") === false);
check("admin can assign the admin role", canAssignAdminRole("admin") === true);
check(
  "admin is denied threat detection",
  capabilityFor("view_threat_detection", "admin") === false,
);
check("admin is denied scan reports", capabilityFor("view_scan_reports", "admin") === false);
check("admin is denied red team tools", capabilityFor("red_team_tools", "admin") === false);
check("admin is denied blue team tools", capabilityFor("blue_team_tools", "admin") === false);
for (const role of ROLES) {
  if (role === "admin") continue;
  check(`${role} cannot access admin panel`, canAccessAdminPanel(role) === false);
  check(`${role} cannot assign the admin role`, canAssignAdminRole(role) === false);
}

// --- User: read-only ops, denied tasks/tools/admin (US2) ---
check("user can access ops dashboard (read-only)", canAccessOpsDashboard("user") === true);
check(
  "user has read_only_org threat detection",
  capabilityFor("view_threat_detection", "user") === "read_only_org",
);
check(
  "user has read_only_org scan reports",
  capabilityFor("view_scan_reports", "user") === "read_only_org",
);
check("user is denied task visibility", capabilityFor("view_tasks", "user") === false);
check("user is denied red team tools", capabilityFor("red_team_tools", "user") === false);
check("user is denied blue team tools", capabilityFor("blue_team_tools", "user") === false);
check("user cannot create tasks", roleInList("create_task", "user") === false);

// --- Security Manager: full task + tool control (US3) ---
check("manager can access ops dashboard", canAccessOpsDashboard("security_manager") === true);
check(
  "manager sees all threats",
  capabilityFor("view_threat_detection", "security_manager") === "all",
);
check("manager can create tasks", roleInList("create_task", "security_manager") === true);
check("manager can assign tasks", roleInList("assign_task", "security_manager") === true);
check(
  "manager start_task is unconditional",
  capabilityFor("start_task", "security_manager") === "any",
);
check("manager can review or close tasks", canReviewOrClose("security_manager") === true);
check(
  "manager always gets red team tools",
  capabilityFor("red_team_tools", "security_manager") === "always",
);
check(
  "manager always gets blue team tools",
  capabilityFor("blue_team_tools", "security_manager") === "always",
);

// --- Security Analyst: own-scope execution (US4/US5) ---
check(
  "analyst sees assigned-scope threats",
  capabilityFor("view_threat_detection", "security_analyst") === "assigned_scope",
);
check(
  "analyst view_tasks is own_only",
  capabilityFor("view_tasks", "security_analyst") === "own_only",
);
check("analyst cannot create tasks", roleInList("create_task", "security_analyst") === false);
check(
  "analyst start_task requires being the assignee",
  capabilityFor("start_task", "security_analyst") === "if_assignee",
);
check("analyst cannot review or close tasks", canReviewOrClose("security_analyst") === false);
check(
  "analyst red team tools require an in-progress red task",
  capabilityFor("red_team_tools", "security_analyst") === "if_any_in_progress_red",
);
check(
  "analyst blue team tools require an in-progress blue task",
  capabilityFor("blue_team_tools", "security_analyst") === "if_any_in_progress_blue",
);

console.log(`access-matrix.test.ts: ${assertions} assertions passed`);
