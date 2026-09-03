import { useEffect, useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useServerFn } from "@tanstack/react-start";
import { ChevronDown, ChevronRight, ExternalLink, ScanLine } from "lucide-react";
import {
  absTime,
  assetsQuery,
  duration,
  findingsQuery,
  relTime,
  scansQuery,
  severityColor,
  severityLabel,
  SEVERITIES,
  type Finding,
  type Scan,
} from "@/lib/security";
import { runScan } from "@/lib/scan.functions";
import { useRealtime } from "@/hooks/use-realtime";
import {
  EmptyState,
  ErrorBanner,
  Eyebrow,
  PageHeader,
  Panel,
  SeverityChip,
  SkeletonRows,
} from "@/components/sd/primitives";

export const Route = createFileRoute("/_authenticated/scans")({
  head: () => ({
    meta: [
      { title: "Scan Report — SecureDash" },
      {
        name: "description",
        content:
          "Scan runs, live progress and validated findings with CVSS scoring, remediation guidance and raw tool evidence.",
      },
      { property: "og:title", content: "Scan Report — SecureDash" },
      {
        property: "og:description",
        content: "Scan runs and validated findings with CVSS scoring and evidence.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Scans,
});

function useTicker(active: boolean) {
  const [, setT] = useState(0);
  useEffect(() => {
    if (!active) return;
    const id = setInterval(() => setT((v) => v + 1), 1000);
    return () => clearInterval(id);
  }, [active]);
}

function CvssBar({ finding }: { finding: Finding }) {
  const pct = (Number(finding.cvss) / 10) * 100;
  return (
    <div className="flex items-center gap-2">
      <div
        className="h-1.5 w-24 overflow-hidden rounded-sm"
        style={{ background: "var(--surface-raised)" }}
      >
        <div
          style={{ width: `${pct}%`, background: severityColor(finding.severity), height: "100%" }}
        />
      </div>
      <span className="mono micro" style={{ color: "var(--text-secondary)" }}>
        {Number(finding.cvss).toFixed(1)}
      </span>
    </div>
  );
}

function FindingRow({ finding, assetName }: { finding: Finding; assetName: string }) {
  const [open, setOpen] = useState(false);
  const [expandRemediation, setExpandRemediation] = useState(false);
  const evidence = Array.isArray(finding.evidence) ? finding.evidence : [];

  return (
    <li className="border-b last:border-b-0" style={{ borderColor: "var(--border-hairline)" }}>
      <div className="flex flex-wrap items-start gap-3 px-4 py-3">
        <SeverityChip severity={finding.severity} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            {finding.cve ? (
              <a
                href={`https://nvd.nist.gov/vuln/detail/${finding.cve}`}
                target="_blank"
                rel="noreferrer"
                className="mono micro inline-flex items-center gap-1 underline underline-offset-2"
                style={{ color: "var(--text-secondary)" }}
              >
                {finding.cve}
                <ExternalLink size={11} strokeWidth={1.5} />
              </a>
            ) : (
              <span className="mono micro" style={{ color: "var(--text-muted)" }}>
                no CVE
              </span>
            )}
            <span className="text-sm">{finding.title}</span>
          </div>
          <div className="mono micro mt-1" style={{ color: "var(--text-muted)" }}>
            {assetName}
          </div>
          {finding.remediation && (
            <p
              className="mt-2 max-w-[70ch] text-sm"
              style={{
                color: "var(--text-secondary)",
                display: expandRemediation ? "block" : "-webkit-box",
                WebkitLineClamp: expandRemediation ? "unset" : 2,
                WebkitBoxOrient: "vertical",
                overflow: expandRemediation ? "visible" : "hidden",
              }}
            >
              {finding.remediation}
            </p>
          )}
          {finding.remediation && finding.remediation.length > 90 && (
            <button
              className="micro mt-1"
              style={{ color: "var(--text-muted)" }}
              onClick={() => setExpandRemediation((v) => !v)}
            >
              {expandRemediation ? "Show less" : "Show more"}
            </button>
          )}
        </div>
        <CvssBar finding={finding} />
        {evidence.length > 0 && (
          <button
            onClick={() => setOpen((v) => !v)}
            className="micro inline-flex items-center gap-1"
            style={{ color: "var(--text-secondary)" }}
          >
            {open ? (
              <ChevronDown size={12} strokeWidth={1.5} />
            ) : (
              <ChevronRight size={12} strokeWidth={1.5} />
            )}
            Evidence ({evidence.length})
          </button>
        )}
      </div>
      {open &&
        evidence.map((ev, i) => (
          <div
            key={i}
            className="mx-4 mb-3 rounded-sm p-3"
            style={{
              background: "var(--surface-raised)",
              border: "1px solid var(--border-hairline)",
            }}
          >
            <div className="mono micro" style={{ color: "var(--text-muted)" }}>
              {ev.tool}
            </div>
            <pre
              className="mono mt-1 text-[12px] leading-[18px] whitespace-pre-wrap"
              style={{ color: "var(--text-secondary)" }}
            >
              {ev.output}
            </pre>
          </div>
        ))}
    </li>
  );
}

function RunScanPanel({ onClose }: { onClose: () => void }) {
  const { data: assets = [] } = useQuery(assetsQuery);
  const qc = useQueryClient();
  const call = useServerFn(runScan);
  const [selected, setSelected] = useState<string[]>([]);
  const [profile, setProfile] = useState<
    "surface-recon" | "defensive-validation" | "deep-emulation" | "vuln-scan" | "monitor"
  >("surface-recon");
  const [team, setTeam] = useState<"red" | "blue">("red");
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () => call({ data: { assetIds: selected, profile, team } }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["scans"] });
      onClose();
    },
    onError: (e) => setError(e instanceof Error ? e.message : "Could not start scan"),
  });

  return (
    <Panel raised className="mb-4 p-4">
      <Eyebrow>New validation run</Eyebrow>
      {error && (
        <div className="mt-3">
          <ErrorBanner message={error} />
        </div>
      )}
      <div className="mt-3 flex flex-wrap gap-2">
        {assets.map((a) => {
          const on = selected.includes(a.id);
          return (
            <button
              key={a.id}
              onClick={() => setSelected((p) => (on ? p.filter((x) => x !== a.id) : [...p, a.id]))}
              className="micro rounded-sm px-2 py-1"
              style={{
                border: `1px solid ${on ? "var(--text-primary)" : "var(--border-hairline)"}`,
                color: on ? "var(--text-primary)" : "var(--text-secondary)",
                background: on ? "var(--surface)" : "transparent",
              }}
              aria-pressed={on}
            >
              {a.name}
            </button>
          );
        })}
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <select
          value={team}
          onChange={(e) => {
            const t = e.target.value as "red" | "blue";
            setTeam(t);
            setProfile(t === "blue" ? "vuln-scan" : "surface-recon");
          }}
          className="micro rounded-sm px-2 py-1"
          style={{
            background: "var(--surface)",
            border: "1px solid var(--border-hairline)",
            color: "var(--text-secondary)",
          }}
        >
          <option value="red">Red team</option>
          <option value="blue">Blue team</option>
        </select>
        <select
          value={profile}
          onChange={(e) => setProfile(e.target.value as typeof profile)}
          className="micro rounded-sm px-2 py-1"
          style={{
            background: "var(--surface)",
            border: "1px solid var(--border-hairline)",
            color: "var(--text-secondary)",
          }}
        >
          {team === "red" ? (
            <>
              <option value="surface-recon">Surface recon</option>
              <option value="defensive-validation">Defensive validation</option>
              <option value="deep-emulation">Deep emulation</option>
            </>
          ) : (
            <>
              <option value="vuln-scan">Vuln scan</option>
              <option value="monitor">Monitor tick</option>
            </>
          )}
        </select>
        <button
          disabled={!selected.length || mutation.isPending}
          onClick={() => mutation.mutate()}
          className="rounded-sm px-3 py-1.5 text-sm font-medium disabled:opacity-50"
          style={{ background: "var(--accent-ember)", color: "var(--bg-base)" }}
        >
          {mutation.isPending ? "Dispatching…" : "Start run"}
        </button>
        <button className="micro" style={{ color: "var(--text-muted)" }} onClick={onClose}>
          Cancel
        </button>
      </div>
    </Panel>
  );
}

function ScanRow({
  scan,
  findings,
  open,
  onToggle,
  assetName,
}: {
  scan: Scan;
  findings: Finding[];
  open: boolean;
  onToggle: () => void;
  assetName: (id: string | null) => string;
}) {
  const running = scan.status === "running";
  useTicker(running);
  const counts = SEVERITIES.map((s) => ({
    s,
    n: findings.filter((f) => f.severity === s).length,
  })).filter((c) => c.n > 0);

  return (
    <>
      <button
        onClick={onToggle}
        className="flex w-full items-center gap-4 border-b px-4 py-3 text-left"
        style={{ borderColor: "var(--border-hairline)" }}
      >
        {open ? (
          <ChevronDown size={16} strokeWidth={1.5} style={{ color: "var(--text-muted)" }} />
        ) : (
          <ChevronRight size={16} strokeWidth={1.5} style={{ color: "var(--text-muted)" }} />
        )}
        <span className="mono min-w-0 flex-1 truncate text-sm">{scan.target}</span>
        <span className="mono micro w-[190px]" style={{ color: "var(--text-muted)" }}>
          {absTime(scan.started_at)} · {relTime(scan.started_at)}
        </span>
        <span className="mono micro w-[80px]" style={{ color: "var(--text-secondary)" }}>
          {duration(scan.started_at, scan.finished_at)}
        </span>
        <span className="flex w-[180px] flex-wrap gap-1">
          {counts.map((c) => (
            <SeverityChip key={c.s} severity={c.s} variant="outline" count={c.n} />
          ))}
        </span>
        <span className="w-[120px]">
          {running ? (
            <span className="block">
              <span className="mono micro block" style={{ color: "var(--accent-ember)" }}>
                Running
              </span>
              <span
                className="mt-1 block h-0.5 w-full overflow-hidden"
                style={{ background: "var(--surface-raised)" }}
              >
                <span
                  className="indeterminate-bar block h-full w-1/3"
                  style={{ background: "var(--accent-ember)" }}
                />
              </span>
            </span>
          ) : (
            <span
              className="mono micro"
              style={{
                color: scan.status === "failed" ? "var(--accent-ember)" : "var(--text-secondary)",
              }}
            >
              {scan.status === "failed" ? "Failed" : "Completed"}
            </span>
          )}
        </span>
      </button>

      {open && (
        <div style={{ background: "var(--bg-base)" }}>
          {running && findings.length === 0 ? (
            <>
              <SkeletonRows rows={3} height={40} />
              <div className="mono micro px-4 pb-3" style={{ color: "var(--text-muted)" }}>
                0 findings so far
              </div>
            </>
          ) : findings.length === 0 ? (
            <EmptyState
              icon={<ScanLine size={20} strokeWidth={1.5} />}
              label="This run produced no findings."
            />
          ) : (
            <>
              <ul>
                {findings.map((f) => (
                  <FindingRow key={f.id} finding={f} assetName={assetName(f.asset_id)} />
                ))}
              </ul>
              {running && (
                <div className="mono micro px-4 py-2" style={{ color: "var(--text-muted)" }}>
                  {findings.length} findings so far
                </div>
              )}
            </>
          )}
        </div>
      )}
    </>
  );
}

function Scans() {
  useRealtime(["scans", "findings"]);
  const scans = useQuery(scansQuery);
  const findings = useQuery(findingsQuery);
  const assets = useQuery(assetsQuery);
  const [openId, setOpenId] = useState<string | null>(null);
  const [showPanel, setShowPanel] = useState(false);

  const assetName = useMemo(() => {
    const map = new Map((assets.data ?? []).map((a) => [a.id, `${a.name} · ${a.hostname}`]));
    return (id: string | null) => (id ? (map.get(id) ?? "Unassigned") : "Unassigned");
  }, [assets.data]);

  const unscoped = (findings.data ?? []).filter((f) => !f.scan_id);

  return (
    <div className="mx-auto max-w-[1400px]">
      <PageHeader
        title="Scan Report"
        subtitle="Validation runs orchestrated through the CAI defensive-validation agent."
        right={
          <button
            onClick={() => setShowPanel((v) => !v)}
            className="rounded-sm px-3 py-2 text-sm font-medium"
            style={{ background: "var(--accent-ember)", color: "var(--bg-base)" }}
          >
            Run scan
          </button>
        }
      />

      {showPanel && <RunScanPanel onClose={() => setShowPanel(false)} />}

      {scans.isError ? (
        <ErrorBanner message="Scan runs unavailable." onRetry={() => scans.refetch()} />
      ) : (
        <Panel>
          <div
            className="flex items-center gap-4 border-b px-4 py-2"
            style={{ borderColor: "var(--border-hairline)" }}
          >
            <span className="w-4" />
            <span className="eyebrow flex-1">Target</span>
            <span className="eyebrow w-[190px]">Started</span>
            <span className="eyebrow w-[80px]">Duration</span>
            <span className="eyebrow w-[180px]">Findings</span>
            <span className="eyebrow w-[120px]">Status</span>
          </div>
          {scans.isLoading ? (
            <SkeletonRows rows={5} height={44} />
          ) : (scans.data ?? []).length === 0 ? (
            <EmptyState
              icon={<ScanLine size={20} strokeWidth={1.5} />}
              label="No findings yet — run your first scan."
              action={
                <button
                  onClick={() => setShowPanel(true)}
                  className="rounded-sm px-3 py-2 text-sm font-medium"
                  style={{ background: "var(--accent-ember)", color: "var(--bg-base)" }}
                >
                  Run scan
                </button>
              }
            />
          ) : (
            (scans.data ?? []).map((s) => (
              <ScanRow
                key={s.id}
                scan={s}
                open={openId === s.id}
                onToggle={() => setOpenId(openId === s.id ? null : s.id)}
                findings={(findings.data ?? []).filter((f) => f.scan_id === s.id)}
                assetName={assetName}
              />
            ))
          )}
        </Panel>
      )}

      {unscoped.length > 0 && (
        <Panel className="mt-6">
          <div className="border-b p-4" style={{ borderColor: "var(--border-hairline)" }}>
            <Eyebrow>Findings outside a scan run</Eyebrow>
          </div>
          <ul>
            {unscoped.map((f) => (
              <FindingRow key={f.id} finding={f} assetName={assetName(f.asset_id)} />
            ))}
          </ul>
        </Panel>
      )}

      <p className="mono micro mt-4" style={{ color: "var(--text-muted)" }}>
        severity ramp: {SEVERITIES.map((s) => severityLabel[s]).join(" · ")}
      </p>
    </div>
  );
}
