import { useState } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { supabase } from "@/integrations/supabase/client";
import { lovable } from "@/integrations/lovable/index";
import { fetchMe } from "@/lib/api-client";
import { ErrorBanner } from "@/components/sd/primitives";

const INVITE_EXPIRED_MESSAGE =
  "This invite or one-time credential has expired. Ask an Admin to re-issue your credentials.";

export const Route = createFileRoute("/auth")({
  head: () => ({
    meta: [
      { title: "Sign in — SecureDash Security Console" },
      {
        name: "description",
        content:
          "Sign in to SecureDash to review validated findings, live threat events and attack-chain analysis.",
      },
      { property: "og:title", content: "Sign in — SecureDash" },
      {
        property: "og:description",
        content: "Analyst access to the SecureDash security operations console.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: AuthPage,
});

function AuthPage() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      if (mode === "signup") {
        const { error } = await supabase.auth.signUp({
          email,
          password,
          options: { emailRedirectTo: window.location.origin },
        });
        if (error) throw error;
        setNotice("Account created. You can sign in now.");
        setMode("signin");
      } else {
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) throw error;

        // Reject unused invites past their TTL even though Supabase Auth itself
        // accepted the password — Admin must re-issue credentials.
        try {
          const me = await fetchMe();
          const profile = me.profile;
          const expired =
            !!profile &&
            profile.status === "pending" &&
            !profile.invite_consumed_at &&
            !!profile.invite_expires_at &&
            new Date(profile.invite_expires_at).getTime() < Date.now();
          if (expired) {
            await supabase.auth.signOut();
            setError(INVITE_EXPIRED_MESSAGE);
            return;
          }
        } catch {
          // /me unreachable — let the authenticated route guard handle it downstream.
        }

        navigate({ to: "/", replace: true });
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Authentication failed";
      const lower = message.toLowerCase();
      setError(
        lower.includes("expired") || lower.includes("invite") ? INVITE_EXPIRED_MESSAGE : message,
      );
    } finally {
      setBusy(false);
    }
  }

  async function google() {
    setError(null);
    const result = await lovable.auth.signInWithOAuth("google", {
      redirect_uri: window.location.origin,
    });
    if (result.error) {
      setError(result.error.message ?? "Google sign-in failed");
      return;
    }
    if (result.redirected) return;
    navigate({ to: "/", replace: true });
  }

  return (
    <div
      className="flex min-h-screen items-center justify-center px-4"
      style={{ background: "var(--bg-base)" }}
    >
      <div className="panel w-full max-w-[380px] p-6">
        <div className="flex items-center gap-2 pb-6">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden>
            <path
              d="M12 2.5 20 7v6.2c0 4.4-3.3 7.6-8 8.3-4.7-.7-8-3.9-8-8.3V7l8-4.5Z"
              stroke="var(--text-primary)"
              strokeWidth="1.5"
              strokeLinejoin="round"
            />
            <path
              d="M12 8.6v6.8M8.6 12h6.8"
              stroke="var(--text-secondary)"
              strokeWidth="1.5"
              strokeLinecap="round"
            />
          </svg>
          <span className="text-[15px] font-semibold tracking-tight">SecureDash</span>
        </div>

        <h1 className="text-[22px] leading-7 font-semibold">
          {mode === "signin" ? "Analyst sign in" : "Create analyst account"}
        </h1>
        <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
          Console access is restricted to authenticated analysts.
        </p>

        {error && (
          <div className="mt-4">
            <ErrorBanner message={error} />
          </div>
        )}
        {notice && (
          <p className="mt-4 text-sm" style={{ color: "var(--text-secondary)" }}>
            {notice}
          </p>
        )}

        <form onSubmit={submit} className="mt-5 flex flex-col gap-3">
          <label className="flex flex-col gap-1">
            <span className="eyebrow">Email</span>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              className="mono rounded-sm px-3 py-2 text-sm"
              style={{
                background: "var(--surface-raised)",
                border: "1px solid var(--border-hairline)",
                color: "var(--text-primary)",
              }}
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="eyebrow">Password</span>
            <input
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={mode === "signin" ? "current-password" : "new-password"}
              className="mono rounded-sm px-3 py-2 text-sm"
              style={{
                background: "var(--surface-raised)",
                border: "1px solid var(--border-hairline)",
                color: "var(--text-primary)",
              }}
            />
          </label>
          <button
            type="submit"
            disabled={busy}
            className="mt-1 rounded-sm px-3 py-2 text-sm font-medium transition-opacity duration-150 ease-out disabled:opacity-60"
            style={{ background: "var(--accent-ember)", color: "var(--bg-base)" }}
          >
            {busy ? "Working…" : mode === "signin" ? "Sign in" : "Create account"}
          </button>
        </form>

        <button
          onClick={google}
          className="mt-3 w-full rounded-sm px-3 py-2 text-sm transition-colors duration-150 ease-out"
          style={{
            background: "var(--surface-raised)",
            border: "1px solid var(--border-hairline)",
            color: "var(--text-primary)",
          }}
        >
          Continue with Google
        </button>

        <button
          onClick={() => setMode(mode === "signin" ? "signup" : "signin")}
          className="micro mt-4 w-full text-center"
          style={{ color: "var(--text-muted)" }}
        >
          {mode === "signin" ? "No account yet? Create one" : "Already have an account? Sign in"}
        </button>
      </div>
    </div>
  );
}
