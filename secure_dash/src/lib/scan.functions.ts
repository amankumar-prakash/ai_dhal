import { createServerFn } from "@tanstack/react-start";
import { getRequest } from "@tanstack/react-start/server";
import { z } from "zod";
import { requireSupabaseAuth } from "@/integrations/supabase/auth-middleware";
import { apiBaseUrl } from "@/lib/api-client";

const RunScanInput = z.object({
  assetIds: z.array(z.string().uuid()).min(1).max(20),
  profile: z.enum([
    "surface-recon",
    "defensive-validation",
    "deep-emulation",
    "vuln-scan",
    "monitor",
    "patch",
  ]),
  team: z.enum(["red", "blue"]).default("red"),
});

/**
 * Creates a platform job via api_service (JWT). Workers report findings through
 * the API — never via this client-authenticated Supabase boundary.
 */
export const runScan = createServerFn({ method: "POST" })
  .middleware([requireSupabaseAuth])
  .inputValidator((input: unknown) => RunScanInput.parse(input))
  .handler(async ({ data }) => {
    const request = getRequest();
    const authHeader = request?.headers?.get("authorization");
    if (!authHeader) throw new Error("Unauthorized: missing bearer token");

    const team =
      data.team ??
      (data.profile === "vuln-scan" || data.profile === "monitor" || data.profile === "patch"
        ? "blue"
        : "red");

    const res = await fetch(`${apiBaseUrl()}/jobs`, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        authorization: authHeader,
      },
      body: JSON.stringify({
        team,
        profile: data.profile,
        asset_ids: data.assetIds,
      }),
    });

    if (!res.ok) {
      const detail = await res.text().catch(() => "");
      throw new Error(detail || `Job create failed (${res.status})`);
    }

    const job = (await res.json()) as { id: string };
    return { jobId: job.id, scanIds: [] as string[], dispatched: true };
  });
