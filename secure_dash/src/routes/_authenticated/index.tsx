import { useMemo } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Area, AreaChart, ResponsiveContainer, YAxis } from "recharts";
import { ChevronRight, Eye, ShieldCheck } from "lucide-react";
import {
  assetsQuery,
  eventsQuery,
  findingsQuery,
  mttrHours,
  relTime,
  riskScore,
  severityColor,
  severityCounts,
  severityLabel,
  SEVERITIES,
  trend30d,
  type Severity,
} from "@/lib/security";
import { useRealtime } from "@/hooks/use-realtime";
import {
  EmptyState,
  Eyebrow,
  ErrorBanner,
  PageHeader,
  Panel,
  SeverityChip,
  SeverityDot,
  SkeletonRows,
  TrendDelta,
} from "@/components/sd/primitives";

export const Route = createFileRoute("/_authenticated/")({
  head: () => ({
    meta: [
      { title: "Dashboard — SecureDash Security Console" },
      {
        name: "description",
        content:
          "Risk score, severity distribution, top vulnerable assets and live security activity across your monitored estate.",
      },
      { property: "og:title", content: "SecureDash Dashboard" },
      {
        property: "og:description",
        content: "Risk posture, severity distribution and live security activity.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Dashboard,
});

function KpiTile({
  label,
  value,
  delta,
  unit,
  accent,
}: {
  label: string;
  value: string;
  delta: number;
  unit?: string;
  accent?: string;
}) {
  return (
    <Panel className="p-4">
      <Eyebrow>{label}</Eyebrow>
      <div
        className="mono mt-2 text-[28px] leading-9 font-semibold"
        style={{ color: accent ?? "var(--text-primary)" }}
      >
        {value}
      </div>
      <div className="mt-1">
        <TrendDelta delta={delta} unit={unit} />
      </div>
    </Panel>
  );
}

function RiskGauge({ score }: { score: number }) {
  const r = 88;
  const cx = 110;
  const cy = 110;
  const segs: Severity[] = ["low", "medium", "high", "critical"];
  const arc = (from: number, to: number) => {
    const p = (t: number) => {
      const a = Math.PI * (1 - t);
      return [cx + r * Math.cos(a), cy - r * Math.sin(a)];
    };
    const [x1, y1] = p(from);
    const [x2, y2] = p(to);
    return `M ${x1} ${y1} A ${r} ${r} 0 0 1 ${x2} ${y2}`;
  };
  const t = Math.min(1, Math.max(0, score / 100));
  const ma = Math.PI * (1 - t);
  const mx = cx + r * Math.cos(ma);
  const my = cy - r * Math.sin(ma);

  return (
    <Panel className="flex flex-col items-center p-4">
      <div className="w-full">
        <Eyebrow>Risk Score</Eyebrow>
      </div>
      <svg
        width="220"
        height="130"
        viewBox="0 0 220 130"
        role="img"
        aria-label={`Risk score ${score} of 100`}
      >
        {segs.map((s, i) => (
          <path
            key={s}
            d={arc(i / segs.length + 0.006, (i + 1) / segs.length - 0.006)}
            stroke={severityColor(s)}
            strokeWidth={10}
            fill="none"
            opacity={0.85}
          />
        ))}
        <circle cx={mx} cy={my} r={6} fill="var(--text-primary)" />
        <circle cx={mx} cy={my} r={10} fill="none" stroke="var(--bg-base)" strokeWidth={2} />
        <text
          x={cx}
          y={cy - 6}
          textAnchor="middle"
          className="mono"
          fontSize="34"
          fontWeight="600"
          fill="var(--text-primary)"
        >
          {score}
        </text>
        <text
          x={cx}
          y={cy + 14}
          textAnchor="middle"
          className="mono"
          fontSize="11"
          fill="var(--text-muted)"
        >
          / 100
        </text>
      </svg>
      <div className="mono micro w-full text-center" style={{ color: "var(--text-muted)" }}>
        as of {new Date().toISOString().replace("T", " ").slice(0, 16)}Z
      </div>
    </Panel>
  );
}

function Sparkline({ data }: { data: { day: number; value: number }[] }) {
  const slope = data.length >= 8 ? data[data.length - 1].value - data[data.length - 8].value : 0;
  const worsening = slope > 0;
  const color = worsening ? "var(--accent-ember)" : "var(--text-secondary)";
  return (
    <Panel className="p-4">
      <div className="flex items-baseline justify-between">
        <Eyebrow>30-day open findings</Eyebrow>
        <TrendDelta delta={slope} />
      </div>
      <div className="mt-3 h-[92px]">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 4, right: 0, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="sd-spark" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={color} stopOpacity={0.18} />
                <stop offset="100%" stopColor={color} stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <YAxis hide domain={["dataMin - 1", "dataMax + 1"]} />
            <Area
              type="linear"
              dataKey="value"
              stroke={color}
              strokeWidth={1.5}
              fill="url(#sd-spark)"
              dot={false}
              isAnimationActive={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </Panel>
  );
}

function SeverityBar({ counts }: { counts: Record<Severity, number> }) {
  const total = SEVERITIES.reduce((a, s) => a + counts[s], 0) || 1;
  return (
    <Panel className="p-4">
      <Eyebrow>Severity distribution</Eyebrow>
      <div className="mt-3 flex h-6 w-full overflow-hidden rounded-sm">
        {SEVERITIES.map((s) =>
          counts[s] ? (
            <div
              key={s}
              title={`${severityLabel[s]}: ${counts[s]} (${Math.round((counts[s] / total) * 100)}%)`}
              style={{
                width: `${(counts[s] / total) * 100}%`,
                background: severityColor(s),
              }}
            />
          ) : null,
        )}
      </div>
      <div className="mt-3 flex flex-wrap gap-x-6 gap-y-2">
        {SEVERITIES.map((s) => (
          <div key={s} className="flex items-center gap-2">
            <SeverityDot severity={s} />
            <span className="micro" style={{ color: "var(--text-secondary)" }}>
              {severityLabel[s]}
            </span>
            <span className="mono micro" style={{ color: "var(--text-primary)" }}>
              {counts[s]}
            </span>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function ReadOnlyExplainer() {
  return (
    <Panel className="mb-6 flex items-start gap-3 p-4">
      <Eye
        size={18}
        strokeWidth={1.5}
        className="mt-0.5 shrink-0"
        style={{ color: "var(--text-secondary)" }}
      />
      <div>
        <div className="text-sm font-medium">Read-only access</div>
        <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
          Your account can view validated findings, threat events and scan reports across the
          organization, but cannot start scans, manage tasks, or open Red/Blue team tools. Ask a
          Security Manager if you need write access.
        </p>
      </div>
    </Panel>
  );
}

function Dashboard() {
  useRealtime(["findings", "threat_events", "scans"]);
  const { me } = Route.useRouteContext();
  const findings = useQuery(findingsQuery);
  const assets = useQuery(assetsQuery);
  const events = useQuery(eventsQuery);

  const f = findings.data ?? [];
  const a = assets.data ?? [];
  const e = events.data ?? [];

  const counts = useMemo(() => severityCounts(f), [f]);
  const score = useMemo(() => riskScore(f, a.length || 1), [f, a.length]);
  const mttr = mttrHours(f);
  const trend = useMemo(() => trend30d(f), [f]);

  const perAsset = useMemo(() => {
    return a
      .map((asset) => {
        const own = f.filter((x) => x.asset_id === asset.id && !x.resolved_at);
        return { asset, counts: severityCounts(own), total: own.length };
      })
      .filter((r) => r.total > 0)
      .sort((x, y) => y.counts.critical - x.counts.critical || y.total - x.total)
      .slice(0, 6);
  }, [a, f]);

  if (findings.isError) {
    return (
      <ErrorBanner
        message="Could not load findings from the security database."
        onRetry={() => findings.refetch()}
      />
    );
  }

  const loading = findings.isLoading || assets.isLoading;

  return (
    <div className="mx-auto max-w-[1400px]">
      <PageHeader title="Dashboard" subtitle="Validated posture across the monitored estate." />

      {me.role === "user" && <ReadOnlyExplainer />}

      {loading ? (
        <SkeletonRows rows={4} height={92} />
      ) : (
        <>
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <div className="grid grid-cols-2 gap-4 lg:col-span-2 xl:grid-cols-3">
              <KpiTile
                label="Critical"
                value={String(counts.critical)}
                delta={counts.critical ? 1 : 0}
                accent={severityColor("critical")}
              />
              <KpiTile label="High" value={String(counts.high)} delta={0} />
              <KpiTile label="Medium + Low" value={String(counts.medium + counts.low)} delta={-1} />
              <KpiTile label="Assets monitored" value={String(a.length)} delta={0} />
              <KpiTile label="MTTR" value={mttr === null ? "—" : `${mttr}h`} delta={-4} unit="h" />
              <KpiTile
                label="Open findings"
                value={String(f.filter((x) => !x.resolved_at).length)}
                delta={2}
              />
            </div>
            <RiskGauge score={score} />
          </div>

          <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
            <Sparkline data={trend} />
            <SeverityBar counts={counts} />
          </div>

          <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
            <Panel>
              <div className="border-b p-4" style={{ borderColor: "var(--border-hairline)" }}>
                <Eyebrow>Top vulnerable assets</Eyebrow>
              </div>
              {perAsset.length === 0 ? (
                <EmptyState
                  icon={<ShieldCheck size={20} strokeWidth={1.5} />}
                  label="No open findings on any monitored asset."
                />
              ) : (
                <ul>
                  {perAsset.map(({ asset, counts: c }) => (
                    <li
                      key={asset.id}
                      className="border-b last:border-b-0"
                      style={{ borderColor: "var(--border-hairline)" }}
                    >
                      <Link
                        to="/scans"
                        className="flex items-center gap-3 px-4 py-3 transition-colors duration-150 ease-out"
                      >
                        <div className="min-w-0 flex-1">
                          <div className="truncate text-sm">{asset.name}</div>
                          <div
                            className="mono micro truncate"
                            style={{ color: "var(--text-muted)" }}
                          >
                            {asset.hostname} · {asset.ip_address}
                          </div>
                        </div>
                        <div className="flex flex-wrap justify-end gap-1">
                          {SEVERITIES.filter((s) => c[s] > 0).map((s) => (
                            <SeverityChip key={s} severity={s} variant="outline" count={c[s]} />
                          ))}
                        </div>
                        <ChevronRight
                          size={16}
                          strokeWidth={1.5}
                          style={{ color: "var(--text-muted)" }}
                        />
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>

            <Panel>
              <div className="border-b p-4" style={{ borderColor: "var(--border-hairline)" }}>
                <Eyebrow>Recent activity</Eyebrow>
              </div>
              <ul className="max-h-[420px] overflow-y-auto">
                {e.slice(0, 12).map((ev, i) => (
                  <li key={ev.id} className={`flex gap-3 px-4 py-3 ${i === 0 ? "row-flash" : ""}`}>
                    <div className="flex flex-col items-center pt-1">
                      <SeverityDot severity={ev.severity} />
                      <span
                        className="mt-1 w-px flex-1"
                        style={{ background: "var(--border-hairline)" }}
                      />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-baseline gap-2">
                        <span
                          className="mono micro"
                          style={{ color: "var(--text-muted)" }}
                          title={ev.occurred_at}
                        >
                          {relTime(ev.occurred_at)}
                        </span>
                        <span className="micro" style={{ color: "var(--text-secondary)" }}>
                          {severityLabel[ev.severity]}
                        </span>
                      </div>
                      <div className="truncate text-sm">{ev.description}</div>
                      <div className="mono micro" style={{ color: "var(--text-muted)" }}>
                        {ev.source_tag} · {ev.technique}
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            </Panel>
          </div>
        </>
      )}
    </div>
  );
}
