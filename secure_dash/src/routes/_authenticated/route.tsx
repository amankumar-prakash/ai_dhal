import { createFileRoute, Outlet, redirect } from "@tanstack/react-router";
import { supabase } from "@/integrations/supabase/client";
import { fetchMe } from "@/lib/api-client";
import type { MeResponse } from "@/lib/rbac-types";
import { AppShell } from "@/components/sd/AppShell";
import { ForcePasswordChange } from "@/components/auth/ForcePasswordChange";
import { clearLabSession, getLabAccessToken } from "@/lib/session";

export const Route = createFileRoute("/_authenticated")({
  ssr: false,
  beforeLoad: async () => {
    let me: MeResponse;
    let user: { id: string; email?: string | null };

    if (getLabAccessToken()) {
      try {
        me = await fetchMe();
      } catch {
        clearLabSession();
        throw redirect({ to: "/auth" });
      }
      user = { id: String(me.user_id), email: me.email };
    } else {
      const { data, error } = await supabase.auth.getUser();
      if (error || !data.user) throw redirect({ to: "/auth" });
      try {
        me = await fetchMe();
      } catch {
        throw redirect({ to: "/auth" });
      }
      user = data.user;
    }

    return { user, me };
  },
  component: RouteComponent,
});

function RouteComponent() {
  const { me } = Route.useRouteContext();
  const mustChangePassword = me.profile?.must_change_password ?? false;

  return <AppShell>{mustChangePassword ? <ForcePasswordChange /> : <Outlet />}</AppShell>;
}
