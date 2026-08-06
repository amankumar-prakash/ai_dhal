import { useState, type FormEvent } from "react";
import { useNavigate, useRouter } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import { KeyRound } from "lucide-react";
import { supabase } from "@/integrations/supabase/client";
import { ErrorBanner } from "@/components/sd/primitives";

const MIN_LENGTH = 12;

/**
 * Blocks the authenticated shell until a provisioned user sets their own
 * password. Updates Supabase Auth directly, then best-effort clears
 * `profiles.must_change_password` via the Supabase client (self-update RLS
 * policy). If that write is rejected (e.g. missing table grant), the user is
 * asked to sign out and back in instead of getting stuck on this screen.
 */
export function ForcePasswordChange() {
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [needsRelogin, setNeedsRelogin] = useState(false);
  const router = useRouter();
  const navigate = useNavigate();
  const qc = useQueryClient();

  async function signOutAndReturn() {
    await qc.cancelQueries();
    qc.clear();
    await supabase.auth.signOut();
    navigate({ to: "/auth", replace: true });
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (password.length < MIN_LENGTH) {
      setError(`Password must be at least ${MIN_LENGTH} characters.`);
      return;
    }
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }

    setBusy(true);
    try {
      const { data: userData, error: updateErr } = await supabase.auth.updateUser({ password });
      if (updateErr) throw updateErr;

      const uid = userData.user?.id;
      let profileCleared = false;
      if (uid) {
        const { error: profileErr } = await supabase
          .from("profiles")
          .update({
            must_change_password: false,
            status: "active",
            invite_consumed_at: new Date().toISOString(),
          })
          .eq("id", uid);
        profileCleared = !profileErr;
      }

      if (profileCleared) {
        await router.invalidate();
      } else {
        setNeedsRelogin(true);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update password");
    } finally {
      setBusy(false);
    }
  }

  if (needsRelogin) {
    return (
      <div className="mx-auto flex max-w-[420px] flex-col items-center gap-4 py-24 text-center">
        <KeyRound size={28} strokeWidth={1.5} style={{ color: "var(--text-secondary)" }} />
        <h1 className="text-[20px] font-semibold">Password updated</h1>
        <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
          Your new password is saved, but we could not clear the one-time credential flag on your
          profile automatically. Sign out and back in with your new password to continue.
        </p>
        <button
          onClick={signOutAndReturn}
          className="rounded-sm px-4 py-2 text-sm font-medium"
          style={{ background: "var(--accent-ember)", color: "var(--bg-base)" }}
        >
          Sign out
        </button>
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-[420px] flex-col gap-4 py-24">
      <div className="text-center">
        <KeyRound
          size={28}
          strokeWidth={1.5}
          className="mx-auto"
          style={{ color: "var(--text-secondary)" }}
        />
        <h1 className="mt-3 text-[20px] font-semibold">Set a new password</h1>
        <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
          Your account was provisioned with a one-time credential. Choose a new password to continue
          into the console.
        </p>
      </div>

      {error && <ErrorBanner message={error} />}

      <form onSubmit={submit} className="flex flex-col gap-3">
        <label className="flex flex-col gap-1">
          <span className="eyebrow">New password</span>
          <input
            type="password"
            required
            minLength={MIN_LENGTH}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="new-password"
            className="mono rounded-sm px-3 py-2 text-sm"
            style={{
              background: "var(--surface-raised)",
              border: "1px solid var(--border-hairline)",
              color: "var(--text-primary)",
            }}
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="eyebrow">Confirm password</span>
          <input
            type="password"
            required
            minLength={MIN_LENGTH}
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            autoComplete="new-password"
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
          {busy ? "Updating…" : "Update password"}
        </button>
      </form>
    </div>
  );
}
