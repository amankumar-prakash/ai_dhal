/**
 * Tool-unlock predicates — all roles are unlocked. Run with:
 *   bun run src/lib/tasks.test.ts
 */
import { canOpenBlueTools, canOpenRedTools, resultsUnlocked, unlockForType } from "./tasks";
import type { Task } from "./rbac-types";

let assertions = 0;
function check(message: string, condition: unknown): void {
  assertions += 1;
  if (!condition) {
    throw new Error(`FAIL: ${message}`);
  }
}

const ANALYST = "11111111-1111-1111-1111-111111111111";
type MiniTask = Pick<Task, "assignee_id" | "status" | "task_type">;
const noTasks: MiniTask[] = [];

check("manager can open red tools", canOpenRedTools("security_manager", noTasks, ANALYST) === true);
check("manager can open blue tools", canOpenBlueTools("security_manager", noTasks, ANALYST) === true);
check("user can open red tools", canOpenRedTools("user", noTasks, ANALYST) === true);
check("admin can open red tools", canOpenRedTools("admin", noTasks, ANALYST) === true);
check("analyst can open red tools with no tasks", canOpenRedTools("security_analyst", noTasks, ANALYST) === true);
check("analyst can open blue tools with no tasks", canOpenBlueTools("security_analyst", noTasks, ANALYST) === true);
check("unlockForType('red') is true", unlockForType("user", noTasks, ANALYST, "red") === true);
check("unlockForType('blue') is true", unlockForType("admin", noTasks, ANALYST, "blue") === true);
check("unlockForType('both') is true", unlockForType("user", noTasks, ANALYST, "both") === true);
check("assigned is locked", resultsUnlocked("assigned") === false);
check("completed unlocks", resultsUnlocked("completed") === true);
check("reviewed unlocks", resultsUnlocked("reviewed") === true);

console.log(`tasks.test.ts: ${assertions} assertions passed`);
