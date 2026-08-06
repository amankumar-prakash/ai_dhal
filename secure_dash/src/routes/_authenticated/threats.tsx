import { useEffect, useMemo, useRef, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Copy, Radar, X } from "lucide-react";
import {
  absTime,
  eventsQueryOptions,
  relTime,
  severityColor,
  severityLabel,
  SEVERITIES,
  threatStatusLabel,
  type Severity,
  type TeamSide,
  type ThreatEvent,
  type ThreatStatus,
} from "@/lib/security";
import { useRealtime } from "@/hooks/use-realtime";
import { LiveIndicator } from "@/components/sd/AppShell";
import {
  EmptyState,
  ErrorBanner,
  Eyebrow,
  PageHeader,
  Panel,
  SeverityChip,
  SkeletonRows,
  StatusBadge,
} from "@/components/sd/primitives";

export const Route = createFileRoute("/_authenticated/threats")({
  head: () => ({
    meta: [
      { title: "Threat Detection — SecureDash" },
      {
        name: "description",
        content:
          "Live stream of validated threat events, MITRE technique mapping and guardrail-intercepted activity.",
      },
      { property: "og:title", content: "Threat Detection — SecureDash" },
      {
        property: "og:description",
        content: "Live threat event stream with MITRE technique mapping.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Threats,
});

const WINDOWS = [
  { id: "1h", label: "1h", ms: 3600_000 },
  { id: "24h", label: "24h", ms: 86_400_000 },
  { id: "7d", label: "7d", ms: 7 * 86_400_000 },
  { id: "all", label: "Custom", ms: Infinity },
] as const;

const STATUSES: ThreatStatus[] = [
  "new",
  "investigating",
  "resolved",
  "blocked",
  "blocked_by_guardrail",
];

function payloadLine(key: string, value: unknown, severity: Severity) {
  const severityKey = ["severity", "cve", "reason", "guardrail", "confirmed"].includes(key);
  return (
    <div key={key} className="mono whitespace-pre-wrap">
      <span style={{ color: "var(--text-muted)" }}>{`  "${key}": `}</span>
      <span
        style={{
          color: severityKey ? severityColor(severity) : "var(--text-secondary)",
        }}
      >
        {JSON.stringify(value)}
      </span>
    </div>
  );
}

function DetailDrawer({ event, onClose }: { event: ThreatEvent; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal="true">
      <button
        aria-label="Close detail"
        onClick={onClose}
        className="flex-1"
        style={{ background: "oklch(0 0 0 / 0.5)" }}
      />
      <div
        className="flex h-full w-[420px] max-w-full flex-col border-l transition-transform duration-[280ms] ease-out"
        style={{ background: "var(--surface)", borderColor: "var(--border-hairline)" }}
      >
        <div
          className="flex items-start justify-between gap-3 border-b p-4"
          style={{ borderColor: "var(--border-hairline)" }}
        >
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <SeverityChip severity={event.severity} />
              <span
                className="mono micro rounded-sm px-1.5 py-0.5"
                style={{
                  border: "1px solid var(--border-hairline)",
                  color: "var(--text-secondary)",
                }}
              >
                {event.technique}
              </span>
            </div>
            <h2 className="mt-2 text-base leading-6">{event.description}</h2>
            <div className="mono micro mt-1" style={{ color: "var(--text-muted)" }}>
              {absTime(event.occurred_at)} · {event.source_ip}
            </div>
          </div>
          <button onClick={onClose} aria-label="Close" style={{ color: "var(--text-secondary)" }}>
            <X size={16} strokeWidth={1.5} />
          </button>
        </div>

        <div className="flex-1 overflow-auto p-4">
          <div className="flex items-center justify-between">
            <Eyebrow>Raw event payload</Eyebrow>
            <button
              className="micro inline-flex items-center gap-1"
              style={{ color: "var(--text-secondary)" }}
              onClick={() =>
                navigator.clipboard?.writeText(JSON.stringify(event.raw_payload, null, 2))
              }
            >
              <Copy size={12} strokeWidth={1.5} /> Copy
            </button>
          </div>
          <div
            className="mt-2 rounded-sm p-3 text-[12px] leading-[18px]"
            style={{
              background: "var(--surface-raised)",
              border: "1px solid var(--border-hairline)",
            }}
          >
            <div className="mono" style={{ color: "var(--text-muted)" }}>
              {"{"}
            </div>
            {Object.entries(event.raw_payload ?? {}).map(([k, v]) =>
              payloadLine(k, v, event.severity),
            )}
            <div className="mono" style={{ color: "var(--text-muted)" }}>
              {"}"}
            </div>
          </div>
        </div>

        <div className="border-t p-4" style={{ borderColor: "var(--border-hairline)" }}>
          <Eyebrow>Linked records</Eyebrow>
          <div className="mono micro mt-2" style={{ color: "var(--text-secondary)" }}>
            finding: {event.finding_id ?? "—"}
          </div>
          <div className="mono micro" style={{ color: "var(--text-secondary)" }}>
            scan: {event.scan_id ?? "—"}
          </div>
        </div>
      </div>
    </div>
  );
}

function Threats() {
  useRealtime(["threat_events"]);
  const [teamFilter, setTeamFilter] = useState<TeamSide | "all">("all");
  const { data, isLoading, isError, refetch } = useQuery(eventsQueryOptions(teamFilter));
  const events = useMemo(() => data ?? [], [data]);

  const [sevFilter, setSevFilter] = useState<Severity[]>([]);
  const [statusFilter, setStatusFilter] = useState<ThreatStatus | "all">("all");
  const [win, setWin] = useState<(typeof WINDOWS)[number]["id"]>("7d");
  const [selected, setSelected] = useState<ThreatEvent | null>(null);

  const [paused, setPaused] = useState(false);
  const [shown, setShown] = useState<ThreatEvent[]>([]);
  const listRef = useRef<HTMLDivElement>(null);

  const filtered = useMemo(() => {
    const ms = WINDOWS.find((w) => w.id === win)!.ms;
    return events.filter((e) => {
      if (sevFilter.length && !sevFilter.includes(e.severity)) return false;
      if (statusFilter !== "all" && e.status !== statusFilter) return false;
      if (ms !== Infinity && Date.now() - new Date(e.occurred_at).getTime() > ms) return false;
      return true;
    });
  }, [events, sevFilter, statusFilter, win]);

  useEffect(() => {
    if (!paused) setShown(filtered);
  }, [filtered, paused]);

  const queued = paused ? filtered.filter((e) => !shown.some((s) => s.id === e.id)).length : 0;

  return (
    <div className="mx-auto max-w-[1400px]">
      <PageHeader
        title="Threat Detection"
        subtitle="Every CAI reasoning step and tool call, written straight to the event stream."
        right={<LiveIndicator paused={paused} />}
      />

      <div
        className="sticky top-0 z-10 -mx-6 mb-4 flex flex-wrap items-center gap-3 border-b px-6 py-3"
        style={{ background: "var(--bg-base)", borderColor: "var(--border-hairline)" }}
      >
        <select
          value={teamFilter}
          onChange={(ev) => setTeamFilter(ev.target.value as TeamSide | "all")}
          className="micro rounded-sm px-2 py-1"
          style={{
            background: "var(--surface-raised)",
            border: "1px solid var(--border-hairline)",
            color: "var(--text-secondary)",
          }}
        >
          <option value="all">All teams</option>
          <option value="red">Red</option>
          <option value="blue">Blue</option>
        </select>

        <div className="flex flex-wrap gap-1">
          {SEVERITIES.map((s) => {
            const on = sevFilter.includes(s);
            return (
              <button
                key={s}
                onClick={() =>
                  setSevFilter((prev) =>
                    prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s],
                  )
                }
                className="micro rounded-sm px-2 py-1 transition-colors duration-150 ease-out"
                style={{
                  border: `1px solid ${on ? severityColor(s) : "var(--border-hairline)"}`,
                  color: on ? severityColor(s) : "var(--text-secondary)",
                  background: on ? "var(--surface-raised)" : "transparent",
                }}
                aria-pressed={on}
              >
                {severityLabel[s]}
              </button>
            );
          })}
        </div>

        <select
          value={statusFilter}
          onChange={(ev) => setStatusFilter(ev.target.value as ThreatStatus | "all")}
          className="micro rounded-sm px-2 py-1"
          style={{
            background: "var(--surface-raised)",
            border: "1px solid var(--border-hairline)",
            color: "var(--text-secondary)",
          }}
        >
          <option value="all">All statuses</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {threatStatusLabel[s]}
            </option>
          ))}
        </select>

        <div
          className="flex overflow-hidden rounded-sm"
          style={{ border: "1px solid var(--border-hairline)" }}
        >
          {WINDOWS.map((w) => (
            <button
              key={w.id}
              onClick={() => setWin(w.id)}
              className="micro px-2 py-1 transition-colors duration-150 ease-out"
              style={{
                background: win === w.id ? "var(--surface-raised)" : "transparent",
                color: win === w.id ? "var(--text-primary)" : "var(--text-muted)",
              }}
            >
              {w.label}
            </button>
          ))}
        </div>

        <button
          onClick={() => setPaused((p) => !p)}
          className="micro ml-auto rounded-sm px-2 py-1"
          style={{
            border: "1px solid var(--border-hairline)",
            color: "var(--text-secondary)",
          }}
        >
          {paused ? "Resume stream" : "Pause stream"}
        </button>
      </div>

      {queued > 0 && (
        <button
          onClick={() => {
            setShown(filtered);
            listRef.current?.scrollTo({ top: 0 });
          }}
          className="micro mb-3 rounded-full px-3 py-1"
          style={{ background: "var(--accent-ember)", color: "var(--bg-base)" }}
        >
          {queued} new events ↑
        </button>
      )}

      {isError ? (
        <ErrorBanner message="Threat stream unavailable." onRetry={() => refetch()} />
      ) : (
        <Panel>
          {isLoading ? (
            <SkeletonRows rows={8} height={44} />
          ) : shown.length === 0 ? (
            <EmptyState
              icon={<Radar size={20} strokeWidth={1.5} />}
              label="No events match the current filters."
            />
          ) : (
            <div
              ref={listRef}
              onMouseEnter={() => setPaused(true)}
              onMouseLeave={() => setPaused(false)}
              className="max-h-[calc(100vh-260px)] overflow-y-auto"
            >
              {shown.map((e, i) => (
                <button
                  key={e.id}
                  onClick={() => setSelected(e)}
                  className={`flex w-full items-center gap-3 border-b px-4 py-2.5 text-left transition-colors duration-150 ease-out ${i === 0 ? "row-flash" : ""}`}
                  style={{ borderColor: "var(--border-hairline)" }}
                >
                  <SeverityChip severity={e.severity} />
                  <span
                    className="mono micro w-[110px] shrink-0"
                    style={{ color: "var(--text-secondary)" }}
                  >
                    {e.source_ip}
                  </span>
                  <span
                    className="mono micro shrink-0 rounded-sm px-1.5 py-0.5"
                    style={{
                      border: "1px solid var(--border-hairline)",
                      color: "var(--text-secondary)",
                    }}
                    title={e.technique_name ?? undefined}
                  >
                    {e.technique}
                  </span>
                  <span className="min-w-0 flex-1 truncate text-sm">{e.description}</span>
                  <StatusBadge status={e.status} />
                  <span
                    className="mono micro w-[70px] shrink-0 text-right"
                    style={{ color: "var(--text-muted)" }}
                    title={absTime(e.occurred_at)}
                  >
                    {relTime(e.occurred_at)}
                  </span>
                </button>
              ))}
            </div>
          )}
        </Panel>
      )}

      {selected && <DetailDrawer event={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}
