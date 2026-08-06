import type { AppRole } from "./rbac-types";

export const APP_ROLES = [
  "user",
  "security_analyst",
  "security_manager",
  "admin",
] as const satisfies readonly AppRole[];

export const ROLE_LABELS: Record<AppRole, string> = {
  user: "User",
  security_analyst: "Security Analyst",
  security_manager: "Security Manager",
  admin: "Admin",
};

export function hasRole(
  current: AppRole | null | undefined,
  allowed: AppRole | AppRole[],
): boolean {
  if (!current) return false;
  const list = Array.isArray(allowed) ? allowed : [allowed];
  return list.includes(current);
}

export function isAdmin(role: AppRole | null | undefined): boolean {
  return role === "admin";
}

export function isManager(role: AppRole | null | undefined): boolean {
  return role === "security_manager";
}

export function isAnalyst(role: AppRole | null | undefined): boolean {
  return role === "security_analyst";
}

export function isOpsRole(role: AppRole | null | undefined): boolean {
  return hasRole(role, ["user", "security_analyst", "security_manager"]);
}

/** Normalize legacy JWT/DB values. */
export function normalizeRole(raw: string | null | undefined): AppRole {
  if (!raw) return "user";
  if (raw === "analyst") return "security_analyst";
  if ((APP_ROLES as readonly string[]).includes(raw)) return raw as AppRole;
  return "user";
}
