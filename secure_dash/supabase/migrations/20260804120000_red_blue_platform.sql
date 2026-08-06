-- Red/Blue platform extensions (001-red-blue-platform)
-- Adds team_side, jobs, patches, tool_runs; revokes browser writes on business tables

CREATE TYPE public.team_side AS ENUM ('red', 'blue');
CREATE TYPE public.job_status AS ENUM (
  'queued', 'dispatched', 'running', 'completed', 'failed', 'cancelled'
);
CREATE TYPE public.patch_status AS ENUM (
  'proposed', 'approved', 'applied', 'failed', 'rolled_back'
);

ALTER TABLE public.scans
  ADD COLUMN IF NOT EXISTS team public.team_side NOT NULL DEFAULT 'red',
  ADD COLUMN IF NOT EXISTS job_id uuid,
  ADD COLUMN IF NOT EXISTS source_service text;

ALTER TABLE public.findings
  ADD COLUMN IF NOT EXISTS team public.team_side,
  ADD COLUMN IF NOT EXISTS source_tool text;

ALTER TABLE public.threat_events
  ADD COLUMN IF NOT EXISTS team public.team_side;

ALTER TABLE public.attack_chains
  ADD COLUMN IF NOT EXISTS team public.team_side NOT NULL DEFAULT 'red';

CREATE TABLE public.jobs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  team public.team_side NOT NULL,
  profile text NOT NULL,
  status public.job_status NOT NULL DEFAULT 'queued',
  asset_ids uuid[] NOT NULL,
  requested_by uuid,
  dispatcher_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  error text,
  started_at timestamptz,
  finished_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT jobs_asset_ids_nonempty CHECK (cardinality(asset_ids) >= 1)
);
GRANT SELECT ON public.jobs TO authenticated;
GRANT ALL ON public.jobs TO service_role;
ALTER TABLE public.jobs ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.scans
  ADD CONSTRAINT scans_job_id_fkey
  FOREIGN KEY (job_id) REFERENCES public.jobs(id) ON DELETE SET NULL;

CREATE TABLE public.patches (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  finding_id uuid NOT NULL REFERENCES public.findings(id) ON DELETE CASCADE,
  asset_id uuid REFERENCES public.assets(id) ON DELETE SET NULL,
  title text NOT NULL,
  playbook text NOT NULL,
  status public.patch_status NOT NULL DEFAULT 'proposed',
  evidence jsonb NOT NULL DEFAULT '[]'::jsonb,
  created_by uuid,
  applied_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);
GRANT SELECT ON public.patches TO authenticated;
GRANT ALL ON public.patches TO service_role;
ALTER TABLE public.patches ENABLE ROW LEVEL SECURITY;

CREATE TABLE public.tool_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  job_id uuid NOT NULL REFERENCES public.jobs(id) ON DELETE CASCADE,
  team public.team_side,
  tool_name text NOT NULL,
  command_summary text,
  exit_code integer,
  raw_output jsonb,
  started_at timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz
);
GRANT SELECT ON public.tool_runs TO authenticated;
GRANT ALL ON public.tool_runs TO service_role;
ALTER TABLE public.tool_runs ENABLE ROW LEVEL SECURITY;

-- Revoke browser mutations on operational tables (API service_role only)
DROP POLICY IF EXISTS "analysts write assets" ON public.assets;
DROP POLICY IF EXISTS "analysts update assets" ON public.assets;
DROP POLICY IF EXISTS "analysts create scans" ON public.scans;
DROP POLICY IF EXISTS "analysts update scans" ON public.scans;
DROP POLICY IF EXISTS "admins delete scans" ON public.scans;
DROP POLICY IF EXISTS "analysts write findings" ON public.findings;
DROP POLICY IF EXISTS "analysts update findings" ON public.findings;
DROP POLICY IF EXISTS "analysts write events" ON public.threat_events;
DROP POLICY IF EXISTS "analysts update events" ON public.threat_events;

REVOKE INSERT, UPDATE, DELETE ON public.assets FROM authenticated;
REVOKE INSERT, UPDATE, DELETE ON public.scans FROM authenticated;
REVOKE INSERT, UPDATE, DELETE ON public.findings FROM authenticated;
REVOKE INSERT, UPDATE, DELETE ON public.threat_events FROM authenticated;
REVOKE INSERT, UPDATE, DELETE ON public.attack_chains FROM authenticated;
REVOKE INSERT, UPDATE, DELETE ON public.attack_chain_steps FROM authenticated;

CREATE POLICY "analysts read jobs" ON public.jobs FOR SELECT TO authenticated USING (true);
CREATE POLICY "analysts read patches" ON public.patches FOR SELECT TO authenticated USING (true);
CREATE POLICY "analysts read tool_runs" ON public.tool_runs FOR SELECT TO authenticated USING (true);

ALTER PUBLICATION supabase_realtime ADD TABLE public.jobs;
ALTER PUBLICATION supabase_realtime ADD TABLE public.patches;
