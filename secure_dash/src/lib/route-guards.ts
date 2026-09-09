/**
 * Route helpers. Feature surfaces are no longer role-gated; these remain as
 * no-ops so existing `beforeLoad` call sites stay valid. Denied-banner helpers
 * are still used when a page wants to show a one-shot message.
 */
import type { AppRole, MeResponse } from "@/lib/rbac-types";
import { ROLE_LABELS } from "@/lib/roles";

export type ToolTeam = "red" | "blue";

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

export function requireOpsRole(_me: MeResponse): void {
  return;
}

export function requireAdminRole(_me: MeResponse): void {
  return;
}

export function requireToolAccess(_me: MeResponse, _team: ToolTeam): void {
  return;
}

export function roleLabel(role: AppRole): string {
  return ROLE_LABELS[role];
}
