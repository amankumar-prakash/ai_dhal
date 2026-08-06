import type { AppRole, Task, TaskType } from "./rbac-types";

/** Analyst: any own in_progress task of matching type unlocks that team tools page. Manager: always. */
export function canOpenRedTools(
  role: AppRole,
  tasks: Pick<Task, "assignee_id" | "status" | "task_type">[],
  userId: string,
): boolean {
  if (role === "security_manager") return true;
  if (role !== "security_analyst") return false;
  return tasks.some(
    (t) => t.assignee_id === userId && t.status === "in_progress" && t.task_type === "red",
  );
}

export function canOpenBlueTools(
  role: AppRole,
  tasks: Pick<Task, "assignee_id" | "status" | "task_type">[],
  userId: string,
): boolean {
  if (role === "security_manager") return true;
  if (role !== "security_analyst") return false;
  return tasks.some(
    (t) => t.assignee_id === userId && t.status === "in_progress" && t.task_type === "blue",
  );
}

export function unlockForType(
  role: AppRole,
  tasks: Pick<Task, "assignee_id" | "status" | "task_type">[],
  userId: string,
  type: TaskType,
): boolean {
  return type === "red"
    ? canOpenRedTools(role, tasks, userId)
    : canOpenBlueTools(role, tasks, userId);
}
