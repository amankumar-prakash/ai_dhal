/** Lab session — used when Supabase Auth is unreachable. */
const TOKEN_KEY = "sd_lab_access_token";

export function getLabAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setLabAccessToken(token: string): void {
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearLabSession(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(TOKEN_KEY);
}
