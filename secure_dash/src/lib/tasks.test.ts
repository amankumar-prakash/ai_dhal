/**
 * Assertion-based logic checks for tool-unlock predicates (US4). See
 * access-matrix.test.ts for why this isn't a vitest/jest suite. Run with:
 *   bun run src/lib/tasks.test.ts
 */
import { canOpenBlueTools, canOpenRedTools, unlockForType } from "./tasks";
import type { Task } from "./rbac-types";

let assertions = 0;
function check(message: string, condition: unknown): void {
  assertions += 1;
  if (!condition) {
    throw new Error(`FAIL: ${message}`);
  }
}

const ANALYST = "11111111-1111-1111-1111-111111111111";
const OTHER = "22222222-2222-2222-2222-222222222222";

type MiniTask = Pick<Task, "assignee_id" | "status" | "task_type">;

const noTasks: MiniTask[] = [];
const ownRedInProgress: MiniTask[] = [
  { assignee_id: ANALYST, status: "in_progress", task_type: "red" },
];
const ownBlueInProgress: MiniTask[] = [
  { assignee_id: ANALYST, status: "in_progress", task_type: "blue" },
];
const ownRedAssignedOnly: MiniTask[] = [
  { assignee_id: ANALYST, status: "assigned", task_type: "red" },
];
const othersRedInProgress: MiniTask[] = [
  { assignee_id: OTHER, status: "in_progress", task_type: "red" },
];
const bothInProgress: MiniTask[] = [...ownRedInProgress, ...ownBlueInProgress];

// --- Manager: always unlocked regardless of task state ---
check(
  "manager can always open red tools",
  canOpenRedTools("security_manager", noTasks, ANALYST) === true,
);
check(
  "manager can always open blue tools",
  canOpenBlueTools("security_manager", noTasks, ANALYST) === true,
);

// --- User / Admin: never unlocked ---
check("user cannot open red tools", canOpenRedTools("user", ownRedInProgress, ANALYST) === false);
check("admin cannot open red tools", canOpenRedTools("admin", ownRedInProgress, ANALYST) === false);

// --- Analyst: unlocked only by an own in-progress task of the matching type ---
check(
  "analyst with no tasks cannot open red tools",
  canOpenRedTools("security_analyst", noTasks, ANALYST) === false,
);
check(
  "analyst with own in-progress red task can open red tools",
  canOpenRedTools("security_analyst", ownRedInProgress, ANALYST) === true,
);
check(
  "analyst with own in-progress red task cannot open blue tools",
  canOpenBlueTools("security_analyst", ownRedInProgress, ANALYST) === false,
);
check(
  "analyst with only an assigned (not started) red task cannot open red tools",
  canOpenRedTools("security_analyst", ownRedAssignedOnly, ANALYST) === false,
);
check(
  "analyst is not unlocked by another analyst's in-progress task",
  canOpenRedTools("security_analyst", othersRedInProgress, ANALYST) === false,
);
check(
  "analyst with both types in progress can open both tool pages",
  canOpenRedTools("security_analyst", bothInProgress, ANALYST) === true &&
    canOpenBlueTools("security_analyst", bothInProgress, ANALYST) === true,
);

// --- unlockForType dispatches to the matching predicate ---
check(
  "unlockForType('red') matches canOpenRedTools",
  unlockForType("security_analyst", ownRedInProgress, ANALYST, "red") === true,
);
check(
  "unlockForType('blue') matches canOpenBlueTools",
  unlockForType("security_analyst", ownRedInProgress, ANALYST, "blue") === false,
);

console.log(`tasks.test.ts: ${assertions} assertions passed`);
