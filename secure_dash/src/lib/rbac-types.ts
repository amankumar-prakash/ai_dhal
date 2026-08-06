export type AppRole = "user" | "security_analyst" | "security_manager" | "admin";

export type UserAccountStatus = "pending" | "active" | "disabled";

export type TaskType = "red" | "blue";

export type TaskStatus =
  "draft" | "assigned" | "in_progress" | "blocked" | "completed" | "reviewed" | "closed";

export type TaskAuditAction =
  | "created"
  | "assigned"
  | "started"
  | "started_on_behalf"
  | "blocked"
  | "unblocked"
  | "completed"
  | "reviewed"
  | "closed"
  | "reassigned"
  | "note_added"
  | "link_added";

export type TaskLinkKind = "finding" | "scan";

export type NotificationType =
  "task_assigned" | "task_reassigned" | "task_completed_for_review" | "generic";

export type Profile = {
  id: string;
  email: string | null;
  display_name: string | null;
  status: UserAccountStatus;
  must_change_password: boolean;
  invite_expires_at: string | null;
  invite_consumed_at: string | null;
  last_login_at: string | null;
  created_at: string | null;
  updated_at: string | null;
};

export type Task = {
  id: string;
  target: string;
  description: string;
  patch_scope: string;
  asset_id: string | null;
  task_type: TaskType;
  status: TaskStatus;
  created_by: string | null;
  assignee_id: string | null;
  assigning_manager_id: string | null;
  linked_job_id: string | null;
  started_at: string | null;
  completed_at: string | null;
  closed_at: string | null;
  created_at: string | null;
  updated_at: string | null;
};

export type TaskNote = {
  id: string;
  task_id: string;
  author_id: string;
  body: string;
  created_at: string | null;
};

export type TaskLink = {
  id: string;
  task_id: string;
  author_id: string;
  kind: TaskLinkKind;
  ref_id: string;
  created_at: string | null;
};

export type TaskAuditEvent = {
  id: string;
  task_id: string;
  actor_id: string | null;
  action: TaskAuditAction;
  from_status: TaskStatus | null;
  to_status: TaskStatus | null;
  from_assignee: string | null;
  to_assignee: string | null;
  message: string | null;
  created_at: string | null;
};

export type Notification = {
  id: string;
  user_id: string;
  type: NotificationType;
  task_id: string | null;
  title: string;
  body: string | null;
  read_at: string | null;
  created_at: string | null;
};

export type MeResponse = {
  user_id: string;
  email: string | null;
  role: AppRole;
  profile: Profile | null;
  tool_unlock: { red: boolean; blue: boolean };
};
