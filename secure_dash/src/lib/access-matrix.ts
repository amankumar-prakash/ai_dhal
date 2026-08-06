/**
 * Access Matrix from specs/002-rbac-user-journeys/contracts/access-matrix.json
 */
import type { AppRole } from "./rbac-types";

export const ACCESS_MATRIX = {
  version: "1.1.0",
  roles: ["user", "security_analyst", "security_manager", "admin"] as const,
  capabilities: {
    login: ["user", "security_analyst", "security_manager", "admin"],
    view_ops_dashboard: ["user", "security_analyst", "security_manager"],
    view_threat_detection: {
      user: "read_only_org",
      security_analyst: "assigned_scope",
      security_manager: "all",
      admin: "deny",
    },
    view_scan_reports: {
      user: "read_only_org",
      security_analyst: "assigned_scope",
      security_manager: "all",
      admin: "deny",
    },
    view_tasks: {
      user: "deny",
      security_analyst: "own_only",
      security_manager: "all",
      admin: "deny",
    },
    create_task: ["security_manager"],
    edit_task_metadata: ["security_manager"],
    assign_task: ["security_manager"],
    start_task: {
      security_analyst: "if_assignee",
      security_manager: "any",
    },
    complete_task: {
      security_analyst: "if_assignee",
      security_manager: "any",
    },
    block_task: {
      security_analyst: "if_assignee",
      security_manager: "any",
    },
    review_or_close_task: {
      security_analyst: "deny",
      security_manager: "any",
    },
    task_notes_and_links: {
      security_analyst: "own_tasks",
      security_manager: "any_task",
    },
    red_team_tools: {
      security_analyst: "if_any_in_progress_red",
      security_manager: "always",
      user: "deny",
      admin: "deny",
    },
    blue_team_tools: {
      security_analyst: "if_any_in_progress_blue",
      security_manager: "always",
      user: "deny",
      admin: "deny",
    },
    admin_panel: ["admin"],
    create_user_assign_role: ["admin"],
    assign_admin_role: ["admin"],
    demote_or_disable_admin: ["admin"],
    issue_one_time_credentials: ["admin"],
  },
  bootstrap: {
    first_admin: "out_of_band_only",
    last_admin_protection: false,
  },
} as const;

type CapList = readonly AppRole[];
type CapMap = Record<string, string | CapList>;

function asList(v: unknown): AppRole[] | null {
  return Array.isArray(v) ? (v as AppRole[]) : null;
}

/** True if role is allowed for a list-style capability. */
export function roleInList(
  capability: keyof typeof ACCESS_MATRIX.capabilities,
  role: AppRole,
): boolean {
  const raw = ACCESS_MATRIX.capabilities[capability] as CapList | CapMap;
  const list = asList(raw);
  if (list) return list.includes(role);
  return false;
}

/** Resolve map-style capability cell for a role (string predicate or deny). */
export function capabilityFor(
  capability: keyof typeof ACCESS_MATRIX.capabilities,
  role: AppRole,
): string | boolean {
  const raw = ACCESS_MATRIX.capabilities[capability] as CapList | CapMap;
  const list = asList(raw);
  if (list) return list.includes(role);
  const map = raw as CapMap;
  const cell = map[role];
  if (cell === undefined) return false;
  if (cell === "deny") return false;
  // Map-style cells are always predicate strings (e.g. "any", "if_assignee") —
  // never role lists — so this narrows the CapList branch out safely.
  return cell as string;
}

export function canAccessAdminPanel(role: AppRole): boolean {
  return roleInList("admin_panel", role);
}

export function canAccessOpsDashboard(role: AppRole): boolean {
  return roleInList("view_ops_dashboard", role);
}

export function canAssignAdminRole(role: AppRole): boolean {
  return roleInList("assign_admin_role", role);
}

export function canReviewOrClose(role: AppRole): boolean {
  const v = capabilityFor("review_or_close_task", role);
  return v === "any" || v === true;
}
