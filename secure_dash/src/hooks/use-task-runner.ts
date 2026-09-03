import { useCallback, useEffect, useState } from "react";
import {
  applyDummyPatch,
  completeDummyTask,
  createDummyTask,
  getDummyResults,
  getDummyTask,
  listDummyTasks,
  startDummyTask,
  TASK_RUNNER_EVENT,
  type DummyCreateInput,
  type TaskResults,
} from "@/lib/task-runner-dummy";
import type { Task } from "@/lib/rbac-types";

function snapshot() {
  return {
    tasks: listDummyTasks(),
    version: Date.now(),
  };
}

/** Subscribes to the local Task Runner store (dummy data). */
export function useTaskRunner() {
  const [state, setState] = useState(snapshot);

  useEffect(() => {
    const refresh = () => setState(snapshot());
    window.addEventListener(TASK_RUNNER_EVENT, refresh);
    window.addEventListener("storage", refresh);
    return () => {
      window.removeEventListener(TASK_RUNNER_EVENT, refresh);
      window.removeEventListener("storage", refresh);
    };
  }, []);

  const create = useCallback((input: DummyCreateInput) => createDummyTask(input), []);
  const start = useCallback((id: string) => startDummyTask(id), []);
  const complete = useCallback((id: string) => completeDummyTask(id), []);
  const applyPatch = useCallback(
    (taskId: string, patchId: string) => applyDummyPatch(taskId, patchId),
    [],
  );
  const getTask = useCallback((id: string): Task | undefined => getDummyTask(id), [state.version]);
  const getResults = useCallback(
    (id: string): TaskResults | undefined => getDummyResults(id),
    [state.version],
  );

  return {
    tasks: state.tasks,
    getTask,
    getResults,
    create,
    start,
    complete,
    applyPatch,
  };
}
