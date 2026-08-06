/**
 * Platform API client — business data only (not Supabase Auth/Realtime).
 */
import { supabase } from "@/integrations/supabase/client";
import type { MeResponse } from "@/lib/rbac-types";

const DEFAULT_BASE = "http://localhost:8000/api/v1";

export function apiBaseUrl(): string {
  return (
    (typeof import.meta !== "undefined" &&
      (import.meta as { env?: Record<string, string> }).env?.VITE_API_BASE_URL) ||
    (typeof process !== "undefined" && process.env?.VITE_API_BASE_URL) ||
    (typeof process !== "undefined" && process.env?.API_BASE_URL) ||
    DEFAULT_BASE
  ).replace(/\/$/, "");
}

export async function getAccessToken(): Promise<string | null> {
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}

export type ApiFetchOptions = RequestInit & { token?: string | null };

export async function apiFetch<T = unknown>(
  path: string,
  options: ApiFetchOptions = {},
): Promise<T> {
  const { token: tokenOpt, headers: initHeaders, ...rest } = options;
  const token = tokenOpt === undefined ? await getAccessToken() : tokenOpt;
  const headers = new Headers(initHeaders);
  if (!headers.has("content-type") && rest.body) {
    headers.set("content-type", "application/json");
  }
  if (token) headers.set("authorization", `Bearer ${token}`);

  const url = `${apiBaseUrl()}/${path.replace(/^\//, "")}`;
  const res = await fetch(url, { ...rest, headers });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${detail || res.statusText}`);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

/** Current principal: role, profile flags (must_change_password) and tool_unlock. */
export function fetchMe(): Promise<MeResponse> {
  return apiFetch<MeResponse>("/me");
}

export function fetchNotifications() {
  return apiFetch<
    Array<{ id: string; title: string; body: string | null; read_at: string | null; created_at: string | null }>
  >("/me/notifications");
}

export type JobCreateBody = {
  team: "red" | "blue";
  profile: string;
  asset_ids: string[];
  tools?: string[] | null;
};

export function createJob(body: JobCreateBody, token?: string | null) {
  return apiFetch<{ id: string; status: string }>("/jobs", {
    method: "POST",
    body: JSON.stringify(body),
    token,
  });
}
