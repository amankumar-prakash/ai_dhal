/**
 * Admin user provisioning — wraps `/admin/users` (Admin-only, backed by
 * Supabase Auth Admin). See api_service/app/routers/admin_users.py.
 */
import { apiFetch } from "@/lib/api-client";
import type { AppRole, UserAccountStatus } from "@/lib/rbac-types";

export type AdminUser = {
  id: string;
  email: string | null;
  display_name: string | null;
  status: UserAccountStatus;
  role: AppRole | null;
  must_change_password?: boolean;
  invite_expires_at: string | null;
  invite_consumed_at?: string | null;
  last_login_at: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type CreateUserBody = {
  email: string;
  role: AppRole;
  display_name?: string;
  temporary_password?: string;
};

export type OneTimeCredentials = {
  user_id: string;
  email: string;
  role: AppRole;
  temporary_password: string;
  invite_expires_at: string;
  note?: string;
};

export type PatchUserBody = Partial<{
  role: AppRole;
  status: Extract<UserAccountStatus, "active" | "disabled">;
  display_name: string;
  reissue_invite: boolean;
}>;

export type PatchUserResponse = AdminUser & {
  temporary_password?: string;
  invite_expires_at?: string;
};

export function listAdminUsers(): Promise<AdminUser[]> {
  return apiFetch<AdminUser[]>("/admin/users");
}

export function createAdminUser(body: CreateUserBody): Promise<OneTimeCredentials> {
  return apiFetch<OneTimeCredentials>("/admin/users", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function patchAdminUser(id: string, body: PatchUserBody): Promise<PatchUserResponse> {
  return apiFetch<PatchUserResponse>(`/admin/users/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

/** Disable/enable is just a status patch — no last-Admin guard (per data-model bootstrap notes). */
export function setUserStatus(id: string, status: "active" | "disabled") {
  return patchAdminUser(id, { status });
}

export function setUserRole(id: string, role: AppRole) {
  return patchAdminUser(id, { role });
}

export function reissueCredentials(id: string) {
  return patchAdminUser(id, { reissue_invite: true });
}
