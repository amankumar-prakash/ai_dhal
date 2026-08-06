/**
 * Route guard helpers per specs/002-rbac-user-journeys/contracts/route-guards.md.
 *
 * Guards run inside a route's `beforeLoad` using the `me` (MeResponse) already
 * fetched by `/_authenticated/route.tsx` and stashed in router context. On
 * denial they `throw redirect(...)` to a safe landing route carrying a
 * `denied` search param with a human-readable permissions message.
 */
import { redirect } from "@tanstack/react-router";
import type { AppRole, MeResponse } from "@/lib/rbac-types";
import { ROLE_LABELS } from "@/lib/roles";

export type ToolTeam = "red" | "blue";

type DeniedTarget = "/" | "/admin" | "/tasks";

const DENIED_KEY = "sd-denied-message";

/** Stash a one-shot permissions message for `DeniedBanner` to pick up after landing. */
export function setDeniedMessage(message: string): void {
  if (typeof sessionStorage !== "undefined") {
    sessionStorage.setItem(DENIED_KEY, message);
  }
}

/** Read (and clear) the pending denial message. Call once per mount. */
export function consumeDeniedMessage(): string | null {
  if (typeof sessionStorage === "undefined") return null;
  const message = sessionStorage.getItem(DENIED_KEY);
  if (message) sessionStorage.removeItem(DENIED_KEY);
  return message;
}

function deniedRedirect(to: DeniedTarget, message: string): never {
  setDeniedMessage(message);
  throw redirect({ to });
}

/** Admin identity is provisioning-only: never allow ops surfaces. */
export function requireOpsRole(me: MeResponse): void {
  if (me.role === "admin") {
    deniedRedirect("/admin", "Admin accounts do not have access to operational views.");
  }
}

export function requireAdminRole(me: MeResponse): void {
  if (me.role !== "admin") {
    deniedRedirect("/", "Admin access required for that page.");
  }
}

/** Tasks are Analyst/Manager only. */
export function requireTasksRole(me: MeResponse): void {
  if (me.role === "admin") {
    deniedRedirect("/admin", "Admin accounts do not have access to Tasks.");
  }
  if (me.role !== "security_analyst" && me.role !== "security_manager") {
    deniedRedirect(
      "/",
      `Tasks are available to Security Analysts and Security Managers only. Your role is ${ROLE_LABELS[me.role]}.`,
    );
  }
}

/**
 * Manager: always. Analyst: only while assigned an in-progress task of the
 * matching type (`tool_unlock` from `/me`). Everyone else: denied.
 */
export function requireToolAccess(me: MeResponse, team: ToolTeam): void {
  if (me.role === "admin") {
    deniedRedirect("/admin", "Admin accounts do not have access to team tools.");
  }
  if (me.role === "security_manager") return;
  if (me.role === "security_analyst") {
    if (me.tool_unlock[team]) return;
    const other: ToolTeam = team === "red" ? "blue" : "red";
    const label = team === "red" ? "Red" : "Blue";
    const message = me.tool_unlock[other]
      ? `${label} team tools unlock once you have an in-progress ${team} task. You currently only have an active ${other} task.`
      : `${label} team tools unlock when you have an in-progress ${team} task assigned to you.`;
    deniedRedirect("/tasks", message);
  }
  deniedRedirect(
    "/",
    `${team === "red" ? "Red" : "Blue"} team tools are available to Security Analysts and Security Managers only.`,
  );
}

export function roleLabel(role: AppRole): string {
  return ROLE_LABELS[role];
}
