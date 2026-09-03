/**
 * Tasks API client — `/tasks` CRUD + lifecycle transitions.
 * See api_service/app/routers/tasks.py + app/services/tasks.py.
 */
import { queryOptions } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import type {
  Task,
  TaskAuditEvent,
  TaskLink,
  TaskLinkKind,
  TaskNote,
  TaskStatus,
  TaskType,
} from "@/lib/rbac-types";

export type TaskAction =
  "assign" | "start" | "block" | "unblock" | "complete" | "review" | "close" | "reassign";

export type TaskCreateBody = {
  target: string;
  description?: string;
  patch_scope?: string;
  asset_id?: string | null;
  task_type: TaskType;
  assignee_id?: string | null;
};

export type TaskMetadataPatch = Partial<{
  target: string;
  description: string;
  patch_scope: string;
  asset_id: string | null;
  task_type: TaskType;
  assignee_id: string | null;
}>;

export type TaskFilters = Partial<{
  assignee_id: string;
  task_type: TaskType;
  status: TaskStatus;
}>;

function toQuery(filters?: TaskFilters): string {
  if (!filters) return "";
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(filters)) {
    if (v) params.set(k, v);
  }
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

export function listTasks(filters?: TaskFilters): Promise<Task[]> {
  return apiFetch<Task[]>(`/tasks${toQuery(filters)}`);
}

export function getTask(id: string): Promise<Task> {
  return apiFetch<Task>(`/tasks/${id}`);
}

export function createTask(body: TaskCreateBody): Promise<Task> {
  return apiFetch<Task>("/tasks", { method: "POST", body: JSON.stringify(body) });
}

export function patchTaskMetadata(id: string, body: TaskMetadataPatch): Promise<Task> {
  return apiFetch<Task>(`/tasks/${id}`, { method: "PATCH", body: JSON.stringify(body) });
}

/** Status transitions: start/block/unblock/complete/review/close/reassign/assign. */
export function transitionTask(
  id: string,
  action: TaskAction,
  assignee_id?: string,
): Promise<Task> {
  return apiFetch<Task>(`/tasks/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ action, ...(assignee_id ? { assignee_id } : {}) }),
  });
}

export function linkJobToTask(id: string, linked_job_id: string): Promise<Task> {
  return apiFetch<Task>(`/tasks/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ linked_job_id }),
  });
}

export function listTaskNotes(id: string): Promise<TaskNote[]> {
  return apiFetch<TaskNote[]>(`/tasks/${id}/notes`);
}

export function addTaskNote(id: string, body: string): Promise<TaskNote> {
  return apiFetch<TaskNote>(`/tasks/${id}/notes`, {
    method: "POST",
    body: JSON.stringify({ body }),
  });
}

export function listTaskLinks(id: string): Promise<TaskLink[]> {
  return apiFetch<TaskLink[]>(`/tasks/${id}/links`);
}

export function addTaskLink(id: string, kind: TaskLinkKind, ref_id: string): Promise<TaskLink> {
  return apiFetch<TaskLink>(`/tasks/${id}/links`, {
    method: "POST",
    body: JSON.stringify({ kind, ref_id }),
  });
}

export function listTaskAudit(id: string): Promise<TaskAuditEvent[]> {
  return apiFetch<TaskAuditEvent[]>(`/tasks/${id}/audit`);
}

/** Role rows from `/roles` — used for the assignee picker (any ops user). */
export function listRoleRows(): Promise<{ user_id: string; role: string }[]> {
  return apiFetch<{ user_id: string; role: string }[]>("/roles");
}

export const tasksQuery = (filters?: TaskFilters) =>
  queryOptions({
    queryKey: ["tasks", filters ?? {}],
    queryFn: () => listTasks(filters),
  });

export function taskQuery(id: string) {
  return queryOptions({
    queryKey: ["tasks", "detail", id],
    queryFn: () => getTask(id),
  });
}

export function taskNotesQuery(id: string) {
  return queryOptions({
    queryKey: ["tasks", "notes", id],
    queryFn: () => listTaskNotes(id),
  });
}

export function taskLinksQuery(id: string) {
  return queryOptions({
    queryKey: ["tasks", "links", id],
    queryFn: () => listTaskLinks(id),
  });
}

export function taskAuditQuery(id: string) {
  return queryOptions({
    queryKey: ["tasks", "audit", id],
    queryFn: () => listTaskAudit(id),
  });
}

export const assigneeRolesQuery = queryOptions({
  queryKey: ["roles", "assignees"],
  queryFn: () => listRoleRows(),
});
