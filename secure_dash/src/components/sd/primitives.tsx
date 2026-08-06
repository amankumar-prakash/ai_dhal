import type { ReactNode } from "react";
import { AlertTriangle, ShieldOff } from "lucide-react";
import {
  severityColor,
  severityLabel,
  threatStatusLabel,
  type Severity,
  type ThreatStatus,
} from "@/lib/security";

export function Eyebrow({ children }: { children: ReactNode }) {
  return <div className="eyebrow">{children}</div>;
}

export function Panel({
  children,
  className = "",
  raised = false,
}: {
  children: ReactNode;
  className?: string;
  raised?: boolean;
}) {
  return <div className={`${raised ? "panel-raised" : "panel"} ${className}`}>{children}</div>;
}

export function SeverityChip({
  severity,
  variant = "filled",
  count,
}: {
  severity: Severity;
  variant?: "filled" | "outline";
  count?: number;
}) {
  const c = severityColor(severity);
  const style =
    variant === "filled"
      ? { backgroundColor: c, color: "var(--bg-base)" }
      : { border: `1px solid ${c}`, color: c };
  return (
    <span
      className="micro inline-flex items-center gap-1 rounded-sm px-1.5 py-0.5 font-medium uppercase tracking-[0.04em]"
      style={style}
    >
      {severityLabel[severity]}
      {count !== undefined && <span className="mono">{count}</span>}
    </span>
  );
}

export function SeverityDot({ severity }: { severity: Severity }) {
  return (
    <span
      aria-hidden
      className="inline-block size-2 shrink-0 rounded-full"
      style={{ backgroundColor: severityColor(severity) }}
    />
  );
}

export function StatusBadge({ status }: { status: ThreatStatus }) {
  const guardrail = status === "blocked_by_guardrail";
  return (
    <span
      className="micro inline-flex items-center gap-1 rounded-sm px-1.5 py-0.5"
      style={{
        border: "1px solid var(--border-hairline)",
        color: guardrail ? "var(--text-muted)" : "var(--text-secondary)",
        background: guardrail ? "var(--surface-raised)" : "transparent",
      }}
    >
      {guardrail && <ShieldOff size={11} strokeWidth={1.5} />}
      {threatStatusLabel[status]}
    </span>
  );
}

export function TrendDelta({ delta, unit = "" }: { delta: number; unit?: string }) {
  const glyph = delta > 0 ? "▲" : delta < 0 ? "▼" : "–";
  const weak = delta === 0;
  return (
    <span
      className="mono micro inline-flex items-center gap-1"
      style={{
        color: "var(--text-secondary)",
        opacity: weak ? 0.6 : 1,
        fontWeight: weak ? 400 : 600,
      }}
    >
      <span aria-hidden>{glyph}</span>
      <span>
        {delta > 0 ? "+" : ""}
        {delta}
        {unit}
      </span>
      <span className="sr-only">
        {delta > 0 ? "increase" : delta < 0 ? "decrease" : "no change"}
      </span>
    </span>
  );
}

export function EmptyState({
  icon,
  label,
  action,
}: {
  icon?: ReactNode;
  label: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 px-6 py-12 text-center">
      <div style={{ color: "var(--text-muted)" }}>{icon}</div>
      <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
        {label}
      </p>
      {action}
    </div>
  );
}

export function ErrorBanner({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div
      className="flex items-start gap-3 rounded-sm p-3"
      style={{
        background: "var(--surface)",
        border: "1px solid var(--severity-critical)",
        color: "var(--severity-critical)",
      }}
      role="alert"
    >
      <AlertTriangle size={16} strokeWidth={1.5} className="mt-0.5 shrink-0" />
      <div className="flex-1 text-sm">{message}</div>
      {onRetry && (
        <button onClick={onRetry} className="micro underline underline-offset-2">
          Retry
        </button>
      )}
    </div>
  );
}

export function SkeletonRows({ rows = 5, height = 40 }: { rows?: number; height?: number }) {
  return (
    <div className="flex flex-col gap-2 p-3">
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="skeleton-pulse w-full"
          style={{ height, animationDelay: `${i * 120}ms` }}
        />
      ))}
    </div>
  );
}

export function PageHeader({
  title,
  subtitle,
  right,
}: {
  title: string;
  subtitle?: string;
  right?: ReactNode;
}) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-4 pb-6">
      <div>
        <h1 className="text-[22px] leading-7 font-semibold">{title}</h1>
        {subtitle && (
          <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
            {subtitle}
          </p>
        )}
      </div>
      {right}
    </header>
  );
}
