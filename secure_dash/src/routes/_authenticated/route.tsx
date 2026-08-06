import { createFileRoute, Outlet, redirect } from "@tanstack/react-router";
import { supabase } from "@/integrations/supabase/client";
import { fetchMe } from "@/lib/api-client";
import type { MeResponse } from "@/lib/rbac-types";
import { setDeniedMessage } from "@/lib/route-guards";
import { AppShell } from "@/components/sd/AppShell";
import { ForcePasswordChange } from "@/components/auth/ForcePasswordChange";

// Admin identity is provisioning-only — never render ops surfaces for Admin.
// See specs/002-rbac-user-journeys/contracts/route-guards.md.
const OPS_ONLY_PATHS = new Set(["/", "/threats", "/scans", "/patches", "/attack-chain"]);

export const Route = createFileRoute("/_authenticated")({
  ssr: false,
  beforeLoad: async ({ location }) => {
    const { data, error } = await supabase.auth.getUser();
    if (error || !data.user) throw redirect({ to: "/auth" });

    let me: MeResponse;
    try {
      me = await fetchMe();
    } catch {
      // Principal could not be resolved (missing role row, expired token, API down) — bounce to sign-in.
      throw redirect({ to: "/auth" });
    }

    if (me.role === "admin" && OPS_ONLY_PATHS.has(location.pathname)) {
      setDeniedMessage("Admin accounts do not have access to operational views.");
      throw redirect({ to: "/admin" });
    }

    return { user: data.user, me };
  },
  component: RouteComponent,
});

function RouteComponent() {
  const { me } = Route.useRouteContext();
  const mustChangePassword = me.profile?.must_change_password ?? false;

  return <AppShell>{mustChangePassword ? <ForcePasswordChange /> : <Outlet />}</AppShell>;
}
