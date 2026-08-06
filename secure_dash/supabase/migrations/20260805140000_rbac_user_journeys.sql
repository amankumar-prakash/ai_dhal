-- 002 RBAC user journeys: extend app_role, profiles, tasks, notifications
-- Date: 2026-08-05

-- Rename legacy analyst → security_analyst; add user + security_manager
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_enum e
    JOIN pg_type t ON e.enumtypid = t.oid
    WHERE t.typname = 'app_role' AND e.enumlabel = 'analyst'
  ) THEN
    ALTER TYPE public.app_role RENAME VALUE 'analyst' TO 'security_analyst';
  END IF;
END $$;

ALTER TYPE public.app_role ADD VALUE IF NOT EXISTS 'user';
ALTER TYPE public.app_role ADD VALUE IF NOT EXISTS 'security_manager';
-- admin and security_analyst already present after rename

CREATE TYPE public.user_account_status AS ENUM ('pending', 'active', 'disabled');
CREATE TYPE public.task_type AS ENUM ('red', 'blue');
CREATE TYPE public.task_status AS ENUM (
  'draft', 'assigned', 'in_progress', 'blocked', 'completed', 'reviewed', 'closed'
);
CREATE TYPE public.task_audit_action AS ENUM (
  'created', 'assigned', 'started', 'started_on_behalf', 'blocked', 'unblocked',
  'completed', 'reviewed', 'closed', 'reassigned', 'note_added', 'link_added'
);
CREATE TYPE public.task_link_kind AS ENUM ('finding', 'scan');
CREATE TYPE public.notification_type AS ENUM (
  'task_assigned', 'task_reassigned', 'task_completed_for_review', 'generic'
);

-- One role per user (v1)
ALTER TABLE public.user_roles DROP CONSTRAINT IF EXISTS user_roles_user_id_role_key;
CREATE UNIQUE INDEX IF NOT EXISTS user_roles_user_id_uidx ON public.user_roles (user_id);

CREATE TABLE IF NOT EXISTS public.profiles (
  id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  email TEXT,
  display_name TEXT,
  status public.user_account_status NOT NULL DEFAULT 'pending',
  must_change_password BOOLEAN NOT NULL DEFAULT false,
  invite_expires_at TIMESTAMPTZ,
  invite_consumed_at TIMESTAMPTZ,
  last_login_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.tasks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  target TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  patch_scope TEXT NOT NULL DEFAULT '',
  asset_id UUID REFERENCES public.assets(id) ON DELETE SET NULL,
  task_type public.task_type NOT NULL,
  status public.task_status NOT NULL DEFAULT 'draft',
  created_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
  assignee_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
  assigning_manager_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
  linked_job_id UUID REFERENCES public.jobs(id) ON DELETE SET NULL,
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  closed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS tasks_assignee_idx ON public.tasks (assignee_id);
CREATE INDEX IF NOT EXISTS tasks_status_idx ON public.tasks (status);
CREATE INDEX IF NOT EXISTS tasks_type_idx ON public.tasks (task_type);

CREATE TABLE IF NOT EXISTS public.task_notes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  task_id UUID NOT NULL REFERENCES public.tasks(id) ON DELETE CASCADE,
  author_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  body TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.task_links (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  task_id UUID NOT NULL REFERENCES public.tasks(id) ON DELETE CASCADE,
  author_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  kind public.task_link_kind NOT NULL,
  ref_id UUID NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.task_audit_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  task_id UUID NOT NULL REFERENCES public.tasks(id) ON DELETE CASCADE,
  actor_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
  action public.task_audit_action NOT NULL,
  from_status public.task_status,
  to_status public.task_status,
  from_assignee UUID,
  to_assignee UUID,
  message TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.notifications (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  type public.notification_type NOT NULL DEFAULT 'generic',
  task_id UUID REFERENCES public.tasks(id) ON DELETE SET NULL,
  title TEXT NOT NULL,
  body TEXT,
  read_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS notifications_user_idx ON public.notifications (user_id);

ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.task_notes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.task_links ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.task_audit_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.notifications ENABLE ROW LEVEL SECURITY;

-- Defense-in-depth: authenticated can read own profile / own notifications;
-- ops writes go through API (service role). Managers/analysts SELECT tasks via has_role.

DROP POLICY IF EXISTS "users read own profile" ON public.profiles;
CREATE POLICY "users read own profile" ON public.profiles
  FOR SELECT TO authenticated
  USING (id = auth.uid());

DROP POLICY IF EXISTS "users update own profile password flag" ON public.profiles;
CREATE POLICY "users update own profile password flag" ON public.profiles
  FOR UPDATE TO authenticated
  USING (id = auth.uid())
  WITH CHECK (id = auth.uid());

DROP POLICY IF EXISTS "managers and analysts read tasks" ON public.tasks;
CREATE POLICY "managers and analysts read tasks" ON public.tasks
  FOR SELECT TO authenticated
  USING (
    public.has_role(auth.uid(), 'security_manager'::public.app_role)
    OR (
      public.has_role(auth.uid(), 'security_analyst'::public.app_role)
      AND assignee_id = auth.uid()
    )
  );

DROP POLICY IF EXISTS "users read own notifications" ON public.notifications;
CREATE POLICY "users read own notifications" ON public.notifications
  FOR SELECT TO authenticated
  USING (user_id = auth.uid());

DROP POLICY IF EXISTS "task notes readable with task access" ON public.task_notes;
CREATE POLICY "task notes readable with task access" ON public.task_notes
  FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.tasks t
      WHERE t.id = task_id
        AND (
          public.has_role(auth.uid(), 'security_manager'::public.app_role)
          OR (public.has_role(auth.uid(), 'security_analyst'::public.app_role) AND t.assignee_id = auth.uid())
        )
    )
  );

DROP POLICY IF EXISTS "task links readable with task access" ON public.task_links;
CREATE POLICY "task links readable with task access" ON public.task_links
  FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.tasks t
      WHERE t.id = task_id
        AND (
          public.has_role(auth.uid(), 'security_manager'::public.app_role)
          OR (public.has_role(auth.uid(), 'security_analyst'::public.app_role) AND t.assignee_id = auth.uid())
        )
    )
  );

DROP POLICY IF EXISTS "task audit readable with task access" ON public.task_audit_events;
CREATE POLICY "task audit readable with task access" ON public.task_audit_events
  FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.tasks t
      WHERE t.id = task_id
        AND (
          public.has_role(auth.uid(), 'security_manager'::public.app_role)
          OR (public.has_role(auth.uid(), 'security_analyst'::public.app_role) AND t.assignee_id = auth.uid())
        )
    )
  );

GRANT SELECT ON public.profiles, public.tasks, public.task_notes, public.task_links,
  public.task_audit_events, public.notifications TO authenticated;
-- Writes: service_role / API only (default revoke for authenticated insert/update/delete)
