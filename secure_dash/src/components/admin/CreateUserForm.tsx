import { useState, type FormEvent } from "react";
import { useMutation } from "@tanstack/react-query";
import { Copy, UserPlus } from "lucide-react";
import { createAdminUser, type OneTimeCredentials } from "@/lib/admin-provision";
import { APP_ROLES, ROLE_LABELS } from "@/lib/roles";
import type { AppRole } from "@/lib/rbac-types";
import { ErrorBanner, Eyebrow, Panel } from "@/components/sd/primitives";

const inputStyle = {
  background: "var(--surface-raised)",
  border: "1px solid var(--border-hairline)",
  color: "var(--text-primary)",
} as const;

export function CreateUserForm({ onCreated }: { onCreated?: () => void }) {
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [role, setRole] = useState<AppRole>("security_analyst");
  const [issued, setIssued] = useState<OneTimeCredentials | null>(null);
  const [copied, setCopied] = useState(false);

  const mutation = useMutation({
    mutationFn: () => createAdminUser({ email, role, display_name: displayName || undefined }),
    onSuccess: (creds) => {
      setIssued(creds);
      setEmail("");
      setDisplayName("");
      setRole("security_analyst");
      onCreated?.();
    },
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    mutation.reset();
    mutation.mutate();
  }

  function copyCreds() {
    if (!issued) return;
    navigator.clipboard?.writeText(`${issued.email}\n${issued.temporary_password}`).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  return (
    <Panel className="p-4">
      <Eyebrow>Create user</Eyebrow>

      {issued ? (
        <div className="mt-3 flex flex-col gap-3">
          <div
            className="rounded-sm p-3"
            style={{
              background: "var(--surface-raised)",
              border: "1px solid var(--border-hairline)",
            }}
          >
            <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
              One-time credential for <span className="mono">{issued.email}</span> — shown once, not
              retrievable again. Share it out of band.
            </p>
            <div
              className="mono mt-2 rounded-sm px-2 py-1.5 text-sm"
              style={{ background: "var(--bg-base)" }}
            >
              {issued.temporary_password}
            </div>
            <div className="mt-2 flex items-center justify-between">
              <span className="micro" style={{ color: "var(--text-muted)" }}>
                Expires {new Date(issued.invite_expires_at).toLocaleString()}
              </span>
              <button
                onClick={copyCreds}
                className="micro inline-flex items-center gap-1"
                style={{ color: "var(--text-secondary)" }}
              >
                <Copy size={12} strokeWidth={1.5} /> {copied ? "Copied" : "Copy"}
              </button>
            </div>
          </div>
          <button
            onClick={() => setIssued(null)}
            className="rounded-sm px-3 py-2 text-sm font-medium"
            style={{ background: "var(--accent-ember)", color: "var(--bg-base)" }}
          >
            Create another
          </button>
        </div>
      ) : (
        <form onSubmit={submit} className="mt-3 flex flex-col gap-3">
          {mutation.isError && (
            <ErrorBanner
              message={
                mutation.error instanceof Error ? mutation.error.message : "Could not create user"
              }
            />
          )}
          <label className="flex flex-col gap-1">
            <span className="eyebrow">Email</span>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mono rounded-sm px-3 py-2 text-sm"
              style={inputStyle}
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="eyebrow">Display name (optional)</span>
            <input
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              className="rounded-sm px-3 py-2 text-sm"
              style={inputStyle}
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="eyebrow">Role</span>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value as AppRole)}
              className="rounded-sm px-3 py-2 text-sm"
              style={inputStyle}
            >
              {APP_ROLES.map((r) => (
                <option key={r} value={r}>
                  {ROLE_LABELS[r]}
                </option>
              ))}
            </select>
          </label>
          <button
            type="submit"
            disabled={mutation.isPending}
            className="mt-1 inline-flex items-center justify-center gap-2 rounded-sm px-3 py-2 text-sm font-medium disabled:opacity-60"
            style={{ background: "var(--accent-ember)", color: "var(--bg-base)" }}
          >
            <UserPlus size={16} strokeWidth={1.5} />
            {mutation.isPending ? "Creating…" : "Create user"}
          </button>
        </form>
      )}
    </Panel>
  );
}
