import { useCallback } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  applyTaskPatch,
  createTask,
  tasksQuery,
  transitionTask,
  type TaskCreateBody,
} from "@/lib/tasks-api";
import type { Task } from "@/lib/rbac-types";

export type { TaskCreateBody as DummyCreateInput } from "@/lib/tasks-api";

/** Live Task Runner — `/tasks` API + start dispatch. */
export function useTaskRunner() {
  const qc = useQueryClient();
  const list = useQuery(tasksQuery());

  const createMut = useMutation({
    mutationFn: (input: TaskCreateBody) =>
      createTask({
        ...input,
        task_type: input.task_type === "both" ? "red" : input.task_type,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tasks"] });
    },
  });

  const startMut = useMutation({
    mutationFn: (id: string) => transitionTask(id, "start"),
    onSuccess: (task) => {
      qc.invalidateQueries({ queryKey: ["tasks"] });
      qc.invalidateQueries({ queryKey: ["tasks", "detail", task.id] });
      qc.invalidateQueries({ queryKey: ["tasks", "results", task.id] });
    },
  });

  const applyPatchMut = useMutation({
    mutationFn: ({ taskId, patchId }: { taskId: string; patchId: string }) =>
      applyTaskPatch(patchId).then(() => taskId),
    onSuccess: (taskId) => {
      qc.invalidateQueries({ queryKey: ["tasks", "results", taskId] });
      qc.invalidateQueries({ queryKey: ["patches"] });
    },
  });

  const create = useCallback(
    (input: TaskCreateBody) => createMut.mutateAsync(input),
    [createMut],
  );
  const start = useCallback((id: string) => startMut.mutateAsync(id), [startMut]);
  const applyPatch = useCallback(
    (taskId: string, patchId: string) => applyPatchMut.mutateAsync({ taskId, patchId }),
    [applyPatchMut],
  );
  const getTask = useCallback(
    (id: string): Task | undefined => (list.data ?? []).find((t) => t.id === id),
    [list.data],
  );

  return {
    tasks: list.data ?? [],
    isLoading: list.isLoading,
    error: list.error,
    getTask,
    create,
    start,
    applyPatch,
    starting: startMut.isPending,
  };
}
