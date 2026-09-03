import type { AppRole, Task, TaskType } from "./rbac-types";

/** Tools are open to every authenticated role. */
export function canOpenRedTools(
  _role: AppRole,
  _tasks: Pick<Task, "assignee_id" | "status" | "task_type">[],
  _userId: string,
): boolean {
  return true;
}

export function canOpenBlueTools(
  _role: AppRole,
  _tasks: Pick<Task, "assignee_id" | "status" | "task_type">[],
  _userId: string,
): boolean {
  return true;
}

export function unlockForType(
  role: AppRole,
  tasks: Pick<Task, "assignee_id" | "status" | "task_type">[],
  userId: string,
  type: TaskType,
): boolean {
  if (type === "both") {
    return canOpenRedTools(role, tasks, userId) && canOpenBlueTools(role, tasks, userId);
  }
  return type === "red"
    ? canOpenRedTools(role, tasks, userId)
    : canOpenBlueTools(role, tasks, userId);
}
