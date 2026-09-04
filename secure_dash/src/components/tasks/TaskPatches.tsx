import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link } from "@tanstack/react-router";
import { Check, Copy, Info, ShieldCheck, Sparkles } from "lucide-react";
import { relTime, type Patch } from "@/lib/security";
import { formatEvidence } from "@/lib/task-attack-chain";
import {
  ASSIST_STACKS,
  defaultAssistStack,
  findingForPatch,
  guidanceForPatch,
  tailorFix,
  type AssistStack,
  type ExampleFix,
  type PatchFinding,
} from "@/lib/patch-guidance";
import { EmptyState, Eyebrow, Panel } from "@/components/sd/primitives";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

const fieldStyle = {
  background: "var(--surface-raised)",
  border: "1px solid var(--border-hairline)",
  color: "var(--text-primary)",
} as const;

function CopyCode({ code, label = "Copy" }: { code: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      className="micro inline-flex items-center gap-1 rounded-sm px-2 py-1"
      style={{
        border: "1px solid var(--border-hairline)",
        color: copied ? "var(--text-primary)" : "var(--text-secondary)",
      }}
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(code);
          setCopied(true);
          window.setTimeout(() => setCopied(false), 1600);
        } catch {
          setCopied(false);
        }
      }}
    >
      {copied ? <Check size={12} strokeWidth={1.5} /> : <Copy size={12} strokeWidth={1.5} />}
      {copied ? "Copied" : label}
    </button>
  );
}

function CodeBlock({ example }: { example: ExampleFix }) {
  return (
    <div
      className="overflow-hidden rounded-sm"
      style={{ border: "1px solid var(--border-hairline)", background: "var(--bg-base)" }}
    >
      <div
        className="flex items-center justify-between gap-2 px-3 py-1.5"
        style={{ borderBottom: "1px solid var(--border-hairline)" }}
      >
        <span className="mono micro" style={{ color: "var(--text-muted)" }}>
          {example.filename}
          {example.language ? ` · ${example.language}` : ""}
        </span>
        <CopyCode code={example.code} />
      </div>
      <pre
        className="mono overflow-x-auto p-3 text-[12px] leading-[18px] whitespace-pre-wrap"
        style={{ color: "var(--text-secondary)" }}
      >
        {example.code}
      </pre>
    </div>
  );
}

function ReadField({ label, value }: { label: string; value: string }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="eyebrow">{label}</span>
      <div className="rounded-sm px-3 py-2 text-sm" style={fieldStyle}>
        {value}
      </div>
    </label>
  );
}

function PatchDetail({
  patch,
  finding,
  target,
  taskId,
}: {
  patch: Patch;
  finding?: PatchFinding;
  target?: string;
  taskId?: string;
}) {
  const guidance = useMemo(
    () => guidanceForPatch(patch, finding, target),
    [patch, finding, target],
  );
  const [stack, setStack] = useState<AssistStack>(() => defaultAssistStack(patch.playbook));
  const [notes, setNotes] = useState("");
  const [assisted, setAssisted] = useState<ExampleFix | null>(null);

  useEffect(() => {
    setStack(defaultAssistStack(patch.playbook));
    setNotes("");
    setAssisted(null);
  }, [patch.id, patch.playbook]);

  const evidence =
    formatEvidence(finding?.evidence) || formatEvidence(patch.evidence) || "No scanner evidence attached.";

  function generate(e: FormEvent) {
    e.preventDefault();
    setAssisted(tailorFix(patch, stack, notes, finding, target));
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="grid gap-3 sm:grid-cols-2">
        <ReadField label="Title" value={patch.title} />
        <ReadField label="Playbook" value={guidance.playbook} />
        <ReadField label="Status" value={patch.status} />
        <ReadField
          label="Linked finding"
          value={finding ? `${finding.title} (${finding.severity})` : "Not linked"}
        />
      </div>

      {finding?.source_tool && (
        <ReadField label="Source tool" value={finding.source_tool} />
      )}

      <label className="flex flex-col gap-1">
        <span className="eyebrow">Evidence</span>
        <pre
          className="mono max-h-40 overflow-auto rounded-sm px-3 py-2 text-[12px] leading-[18px] whitespace-pre-wrap"
          style={{ ...fieldStyle, color: "var(--text-secondary)" }}
        >
          {evidence}
        </pre>
      </label>

      <div>
        <Eyebrow>Why this matters</Eyebrow>
        <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
          {guidance.summary} {guidance.why}
        </p>
      </div>

      <div>
        <Eyebrow>Recommendations</Eyebrow>
        <ol className="mt-2 flex flex-col gap-2">
          {guidance.recommendations.map((item, i) => (
            <li key={i} className="flex gap-2 text-sm" style={{ color: "var(--text-secondary)" }}>
              <span className="mono micro mt-0.5" style={{ color: "var(--text-muted)" }}>
                {String(i + 1).padStart(2, "0")}
              </span>
              <span>{item}</span>
            </li>
          ))}
        </ol>
      </div>

      <div>
        <Eyebrow>Example fix</Eyebrow>
        <p className="mb-2 mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
          {guidance.example.summary}
        </p>
        <CodeBlock example={guidance.example} />
      </div>

      <form
        onSubmit={generate}
        className="flex flex-col gap-3 rounded-sm p-3"
        style={{ border: "1px solid var(--border-hairline)", background: "var(--surface)" }}
      >
        <div className="flex items-center gap-2">
          <Sparkles size={14} strokeWidth={1.5} style={{ color: "var(--accent-ember)" }} />
          <Eyebrow>Code assist</Eyebrow>
        </div>
        <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
          Pick the stack you are hardening. Optional notes (compose service name, listen port) are folded into the snippet.
        </p>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="flex flex-col gap-1">
            <span className="eyebrow">Stack</span>
            <select
              value={stack}
              onChange={(e) => setStack(e.target.value as AssistStack)}
              className="rounded-sm px-3 py-2 text-sm"
              style={fieldStyle}
            >
              {ASSIST_STACKS.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.label}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 sm:col-span-1">
            <span className="eyebrow">Environment notes</span>
            <input
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="e.g. Juice Shop on 127.0.0.1:3000"
              className="rounded-sm px-3 py-2 text-sm"
              style={fieldStyle}
            />
          </label>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="submit"
            className="rounded-sm px-3 py-1.5 text-sm font-medium"
            style={{ background: "var(--accent-ember)", color: "var(--bg-base)" }}
          >
            Generate tailored fix
          </button>
          {taskId && (
            <Link
              to="/tools/blue"
              search={{ taskId }}
              className="rounded-sm px-3 py-1.5 text-sm"
              style={{
                border: "1px solid var(--border-hairline)",
                color: "var(--text-primary)",
              }}
            >
              Ask Blue CAI
            </Link>
          )}
          <CopyCode code={guidance.assistPrompt} label="Copy CAI prompt" />
        </div>
        {assisted && (
          <div className="mt-1">
            <p className="mb-2 text-sm" style={{ color: "var(--text-secondary)" }}>
              {assisted.summary}
            </p>
            <CodeBlock example={assisted} />
          </div>
        )}
      </form>
    </div>
  );
}

export function TaskPatches({
  patches,
  findings = [],
  taskId,
  target,
}: {
  patches: Patch[];
  findings?: PatchFinding[];
  taskId?: string;
  target?: string;
}) {
  const [openId, setOpenId] = useState<string | null>(null);
  const selected = patches.find((p) => p.id === openId) ?? null;
  const selectedFinding = selected ? findingForPatch(selected, findings) : undefined;

  if (!patches.length) {
    return (
      <EmptyState
        icon={<ShieldCheck size={20} strokeWidth={1.5} />}
        label="No patches proposed for this task."
      />
    );
  }

  return (
    <>
      <Panel>
        <ul>
          {patches.map((p) => (
            <li
              key={p.id}
              className="flex flex-wrap items-center gap-3 border-b px-4 py-3 last:border-b-0"
              style={{ borderColor: "var(--border-hairline)" }}
            >
              <div className="min-w-0 flex-1">
                <div className="text-sm">{p.title}</div>
                <div className="mono micro mt-1" style={{ color: "var(--text-muted)" }}>
                  {p.playbook} · {p.status}
                  {p.created_at ? ` · ${relTime(p.created_at)}` : ""}
                  {p.applied_at ? ` · applied ${relTime(p.applied_at)}` : ""}
                </div>
              </div>
              <button
                type="button"
                className="inline-flex items-center gap-1.5 rounded-sm px-3 py-1.5 text-sm"
                style={{ background: "var(--accent-ember)", color: "var(--bg-base)" }}
                onClick={() => setOpenId(p.id)}
              >
                <Info size={14} strokeWidth={1.5} />
                Info
              </button>
            </li>
          ))}
        </ul>
      </Panel>

      <Dialog open={selected !== null} onOpenChange={(open) => !open && setOpenId(null)}>
        <DialogContent className="max-h-[90vh] w-[calc(100%-2rem)] max-w-3xl overflow-y-auto sm:max-w-3xl">
          {selected && (
            <>
              <DialogHeader>
                <DialogTitle>{selected.title}</DialogTitle>
                <DialogDescription>
                  Remediation detail, example fix, and code assist for this proposed patch.
                </DialogDescription>
              </DialogHeader>
              <PatchDetail
                patch={selected}
                finding={selectedFinding}
                target={target}
                taskId={taskId}
              />
            </>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
