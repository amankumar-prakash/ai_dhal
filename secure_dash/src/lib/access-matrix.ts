/**
 * Access Matrix — capabilities are open to every authenticated role.
 */
import type { AppRole } from "./rbac-types";

const ALL_ROLES = ["user", "security_analyst", "security_manager", "admin"] as const;

export const ACCESS_MATRIX = {
  version: "2.0.0",
  roles: ALL_ROLES,
  capabilities: {
    login: [...ALL_ROLES],
    view_ops_dashboard: [...ALL_ROLES],
    view_threat_detection: {
      user: "all",
      security_analyst: "all",
      security_manager: "all",
      admin: "all",
    },
    view_scan_reports: {
      user: "all",
      security_analyst: "all",
      security_manager: "all",
      admin: "all",
    },
    view_tasks: {
      user: "all",
      security_analyst: "all",
      security_manager: "all",
      admin: "all",
    },
    create_task: [...ALL_ROLES],
    edit_task_metadata: [...ALL_ROLES],
    assign_task: [...ALL_ROLES],
    start_task: {
      user: "any",
      security_analyst: "any",
      security_manager: "any",
      admin: "any",
    },
    complete_task: {
      user: "any",
      security_analyst: "any",
      security_manager: "any",
      admin: "any",
    },
    block_task: {
      user: "any",
      security_analyst: "any",
      security_manager: "any",
      admin: "any",
    },
    review_or_close_task: {
      user: "any",
      security_analyst: "any",
      security_manager: "any",
      admin: "any",
    },
    task_notes_and_links: {
      user: "any_task",
      security_analyst: "any_task",
      security_manager: "any_task",
      admin: "any_task",
    },
    red_team_tools: {
      user: "always",
      security_analyst: "always",
      security_manager: "always",
      admin: "always",
    },
    blue_team_tools: {
      user: "always",
      security_analyst: "always",
      security_manager: "always",
      admin: "always",
    },
    admin_panel: [...ALL_ROLES],
    create_user_assign_role: [...ALL_ROLES],
    assign_admin_role: [...ALL_ROLES],
    demote_or_disable_admin: [...ALL_ROLES],
    issue_one_time_credentials: [...ALL_ROLES],
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
