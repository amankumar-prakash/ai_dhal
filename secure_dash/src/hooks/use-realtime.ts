import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { supabase } from "@/integrations/supabase/client";

/**
 * Supabase Realtime drives every live surface: the backend writes rows, we
 * invalidate the matching caches. No polling, no custom socket plumbing.
 */
export function useRealtime(tables: string[], extraKeys: string[][] = []) {
  const qc = useQueryClient();
  useEffect(() => {
    const channel = supabase.channel(`securedash-${tables.join("-")}`);
    for (const table of tables) {
      channel.on("postgres_changes", { event: "*", schema: "public", table }, () => {
        qc.invalidateQueries({ queryKey: [table] });
        for (const key of extraKeys) qc.invalidateQueries({ queryKey: key });
      });
    }
    channel.subscribe();
    return () => {
      supabase.removeChannel(channel);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tables.join("|"), qc]);
}
