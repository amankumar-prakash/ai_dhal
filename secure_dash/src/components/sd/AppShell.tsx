import { useEffect, useState, type ComponentType, type ReactNode } from "react";
import { getRouteApi, Link, useNavigate, useRouterState } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  ClipboardList,
  LayoutDashboard,
  LogOut,
  PanelLeftClose,
  PanelLeftOpen,
  ShieldAlert,
  Swords,
  UserCog,
  X,
} from "lucide-react";
import { supabase } from "@/integrations/supabase/client";
import { eventsQuery, relTime, scansQuery } from "@/lib/security";
import { consumeDeniedMessage } from "@/lib/route-guards";
import { fetchNotifications } from "@/lib/api-client";
import type { MeResponse } from "@/lib/rbac-types";
import { clearLabSession } from "@/lib/session";

const authenticatedRouteApi = getRouteApi("/_authenticated");

type NavPath = "/" | "/tasks" | "/tools/red" | "/tools/blue" | "/admin";

type NavItem = {
  to: NavPath;
  label: string;
  icon: ComponentType<{ size?: number; strokeWidth?: number; className?: string }>;
  key: string | null;
};

function buildNav(_me: MeResponse): NavItem[] {
  return [
    { to: "/", label: "Dashboard", icon: LayoutDashboard, key: null },
    { to: "/tasks", label: "Task Runner", icon: ClipboardList, key: null },
    { to: "/tools/red", label: "Red Tools", icon: Swords, key: null },
    { to: "/tools/blue", label: "Blue Tools", icon: ShieldAlert, key: null },
    { to: "/admin", label: "Admin", icon: UserCog, key: null },
  ];
}

function navActive(pathname: string, to: NavPath): boolean {
  if (to === "/") return pathname === "/";
  return pathname === to || pathname.startsWith(`${to}/`);
}

function LogoMark({ hot }: { hot: boolean }) {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M12 2.5 20 7v6.2c0 4.4-3.3 7.6-8 8.3-4.7-.7-8-3.9-8-8.3V7l8-4.5Z"
        stroke={hot ? "var(--accent-ember)" : "var(--text-primary)"}
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      <path
        d="M12 8.6v6.8M8.6 12h6.8"
        stroke={hot ? "var(--accent-ember)" : "var(--text-secondary)"}
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

function useUnreadCritical() {
  const { data: events = [] } = useQuery(eventsQuery);
  const [seen, setSeen] = useState<Record<string, number>>({});

  useEffect(() => {
    try {
      setSeen(JSON.parse(localStorage.getItem("sd-last-visit") ?? "{}"));
    } catch {
      /* ignore */
    }
  }, []);

  const pathname = useRouterState({ select: (s) => s.location.pathname });
  useEffect(() => {
    const key = pathname === "/threats" ? "threats" : pathname === "/scans" ? "scans" : null;
    if (!key) return;
    const next = { ...seen, [key]: Date.now() };
    localStorage.setItem("sd-last-visit", JSON.stringify(next));
    setSeen(next);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname]);

  const count = (key: string) =>
    events.filter(
      (e) => e.severity === "critical" && new Date(e.occurred_at).getTime() > (seen[key] ?? 0),
    ).length;

  return { threats: count("threats"), scans: count("scans") } as Record<string, number>;
}

function LastScanFooter({ collapsed }: { collapsed: boolean }) {
  const { data: scans = [] } = useQuery(scansQuery);
  const last = scans[0];
  const running = scans.find((s) => s.status === "running");
  const active = running ?? last;
  if (!active) return null;
  const failed = active.status === "failed";
  const isRunning = active.status === "running";

  return (
    <div className="border-t px-3 py-3" style={{ borderColor: "var(--border-hairline)" }}>
      <div className="flex items-center gap-2">
        <span
          className={`size-2 shrink-0 rounded-full ${isRunning ? "live-dot" : ""}`}
          style={{
            backgroundColor: failed ? "var(--accent-ember)" : "var(--text-secondary)",
          }}
          aria-hidden
        />
        {!collapsed && (
          <div className="min-w-0">
            <div className="mono micro" style={{ color: "var(--text-secondary)" }}>
              {isRunning ? "Scan running" : `Last scan ${relTime(active.started_at)}`}
            </div>
            <div className="mono micro truncate" style={{ color: "var(--text-muted)" }}>
              {active.target}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function NotificationStrip({ collapsed }: { collapsed: boolean }) {
  const { data: notes = [] } = useQuery({
    queryKey: ["me-notifications"],
    queryFn: fetchNotifications,
    refetchInterval: 30_000,
    retry: false,
  });
  const unread = notes.filter((n) => !n.read_at).slice(0, 3);
  if (!unread.length) return null;
  return (
    <div className="border-t px-3 py-2" style={{ borderColor: "var(--border-hairline)" }}>
      {!collapsed && (
        <div className="mono micro mb-1" style={{ color: "var(--text-muted)" }}>
          Notifications
        </div>
      )}
      {unread.map((n) => (
        <div
          key={n.id}
          className="mono micro truncate py-0.5"
          style={{ color: "var(--text-secondary)" }}
          title={n.body ?? n.title}
        >
          {collapsed ? "•" : n.title}
        </div>
      ))}
    </div>
  );
}

function DeniedBanner() {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const [message, setMessage] = useState<string | null>(null);

  // Route guards stash a one-shot message (sessionStorage) before redirecting here;
  // consume it once per landing so it doesn't reappear on refresh/back-nav.

  useEffect(() => setMessage(consumeDeniedMessage()), [pathname]);

  if (!message) return null;
  return (
    <div
      role="alert"
      className="mb-4 flex items-start gap-3 rounded-sm p-3"
      style={{
        background: "var(--surface)",
        border: "1px solid var(--border-hairline)",
        color: "var(--text-secondary)",
      }}
    >
      <ShieldAlert
        size={16}
        strokeWidth={1.5}
        className="mt-0.5 shrink-0"
        style={{ color: "var(--accent-ember)" }}
      />
      <div className="flex-1 text-sm">{message}</div>
      <button
        aria-label="Dismiss"
        onClick={() => setMessage(null)}
        style={{ color: "var(--text-muted)" }}
      >
        <X size={14} strokeWidth={1.5} />
      </button>
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  const [logoHot, setLogoHot] = useState(false);
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const badges = useUnreadCritical();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { me } = authenticatedRouteApi.useRouteContext();
  const nav = buildNav(me);

  async function signOut() {
    await qc.cancelQueries();
    qc.clear();
    await supabase.auth.signOut();
    clearLabSession();
    navigate({ to: "/auth", replace: true });
  }

  return (
    <div className="flex min-h-screen w-full" style={{ background: "var(--bg-base)" }}>
      <aside
        className="sticky top-0 flex h-screen shrink-0 flex-col border-r transition-[width] duration-[180ms] ease-out"
        style={{
          width: collapsed ? 64 : 240,
          borderColor: "var(--border-hairline)",
          background: "var(--surface)",
        }}
      >
        <div className="flex items-center gap-2 px-3 py-4">
          <span
            onMouseEnter={() => setLogoHot(collapsed)}
            onMouseLeave={() => setLogoHot(false)}
            className="grid size-8 place-items-center"
          >
            <LogoMark hot={logoHot} />
          </span>
          {!collapsed && (
            <span className="text-[15px] font-semibold tracking-tight">SecureDash</span>
          )}
        </div>

        <nav className="flex flex-1 flex-col gap-0.5 px-2">
          {nav.map((item) => {
            const active = navActive(pathname, item.to);
            const badge = item.key ? badges[item.key] : 0;
            return (
              <Link
                key={item.to}
                to={item.to}
                title={collapsed ? item.label : undefined}
                className="group relative flex items-center gap-3 rounded-sm py-2 pr-2 pl-3 text-sm transition-colors duration-150 ease-out"
                style={{
                  background: active ? "var(--surface-raised)" : "transparent",
                  borderLeft: `2px solid ${active ? "var(--text-primary)" : "transparent"}`,
                  color: active ? "var(--text-primary)" : "var(--text-secondary)",
                }}
              >
                <item.icon size={22} strokeWidth={1.5} className="shrink-0" />
                {!collapsed && <span className="flex-1 truncate">{item.label}</span>}
                {badge > 0 && (
                  <span
                    className="mono micro rounded-full px-1.5 py-0.5 font-semibold"
                    style={{
                      background: "var(--accent-ember)",
                      color: "var(--bg-base)",
                    }}
                    title={`${badge} new critical`}
                  >
                    {badge}
                  </span>
                )}
              </Link>
            );
          })}
        </nav>

        <LastScanFooter collapsed={collapsed} />

        <NotificationStrip collapsed={collapsed} />

        <div className="flex items-center justify-between gap-2 px-3 py-3">
          <button
            onClick={() => setCollapsed((c) => !c)}
            className="rounded-sm p-1.5 transition-colors duration-150 ease-out"
            style={{ color: "var(--text-secondary)" }}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {collapsed ? (
              <PanelLeftOpen size={20} strokeWidth={1.5} />
            ) : (
              <PanelLeftClose size={20} strokeWidth={1.5} />
            )}
          </button>
          <button
            onClick={signOut}
            className="flex items-center gap-2 rounded-sm p-1.5 text-sm transition-colors duration-150 ease-out"
            style={{ color: "var(--text-secondary)" }}
            title="Sign out"
          >
            <LogOut size={20} strokeWidth={1.5} />
            {!collapsed && <span className="micro">Sign out</span>}
          </button>
        </div>
      </aside>

      <main className="min-w-0 flex-1 px-6 py-6">
        <DeniedBanner />
        {children}
      </main>
    </div>
  );
}

export function LiveIndicator({ paused }: { paused: boolean }) {
  return (
    <span className="inline-flex items-center gap-2">
      <span
        className={`size-2 rounded-full ${paused ? "" : "live-dot"}`}
        style={{
          background: paused ? "var(--text-muted)" : "var(--accent-ember)",
        }}
        aria-hidden
      />
      <span
        className="micro tracking-[0.08em] uppercase"
        style={{ color: paused ? "var(--text-muted)" : "var(--text-secondary)" }}
      >
        {paused ? "Paused" : "Live"}
      </span>
      <Activity size={12} strokeWidth={1.5} style={{ color: "var(--text-muted)" }} />
    </span>
  );
}
