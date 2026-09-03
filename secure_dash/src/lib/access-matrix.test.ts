/**
 * Assertion-based logic checks for the Access Matrix. Run with:
 *   bun run src/lib/access-matrix.test.ts
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

for (const role of ROLES) {
  check(`${role} can access admin panel`, canAccessAdminPanel(role) === true);
  check(`${role} can access ops dashboard`, canAccessOpsDashboard(role) === true);
  check(`${role} can assign the admin role`, canAssignAdminRole(role) === true);
  check(`${role} can create tasks`, roleInList("create_task", role) === true);
  check(`${role} can review or close tasks`, canReviewOrClose(role) === true);
  check(`${role} sees all threats`, capabilityFor("view_threat_detection", role) === "all");
  check(`${role} sees all scan reports`, capabilityFor("view_scan_reports", role) === "all");
  check(`${role} sees all tasks`, capabilityFor("view_tasks", role) === "all");
  check(`${role} always gets red team tools`, capabilityFor("red_team_tools", role) === "always");
  check(`${role} always gets blue team tools`, capabilityFor("blue_team_tools", role) === "always");
}

console.log(`access-matrix.test.ts: ${assertions} assertions passed`);
