-- Live task-run progress events + stop audit action

ALTER TYPE public.task_audit_action ADD VALUE IF NOT EXISTS 'stopped';

CREATE TABLE IF NOT EXISTS public.job_progress_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  job_id uuid NOT NULL REFERENCES public.jobs(id) ON DELETE CASCADE,
  kind text NOT NULL CHECK (kind IN ('thinking', 'tool', 'process', 'status')),
  message text NOT NULL,
  meta jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS job_progress_events_job_id_created_at_idx
  ON public.job_progress_events (job_id, created_at);

GRANT SELECT ON public.job_progress_events TO authenticated;
GRANT ALL ON public.job_progress_events TO service_role;
ALTER TABLE public.job_progress_events ENABLE ROW LEVEL SECURITY;

CREATE POLICY "analysts read job progress" ON public.job_progress_events
  FOR SELECT TO authenticated USING (true);
