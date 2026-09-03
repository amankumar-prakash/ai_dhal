/**
 * Local Task Runner store — dummy tasks, attack chains, and patches.
 * Swap this for the live tasks API when the backend is ready.
 */
import type { Task, TaskStatus, TaskType } from "./rbac-types";
import type { Patch, Severity, Stage } from "./security";

export const TASK_RUNNER_EVENT = "sd-task-runner-changed";
const STORAGE_KEY = "sd-task-runner-v1";

export type DummyChainRecord = {
  id: string;
  chain_id: string;
  stage: Stage;
  sequence: number;
  title: string;
  severity: Severity;
  technique: string;
  source_ip: string;
  occurred_at: string;
  cve?: string;
  cvss?: number;
};

export type TaskResults = {
  chain: DummyChainRecord[];
  patches: Patch[];
};

export type TaskRunnerStore = {
  tasks: Task[];
  results: Record<string, TaskResults>;
};

export const DUMMY_ASSETS = [
  { id: "asset-shop", name: "Customer storefront", hostname: "shop.internal.lab" },
  { id: "asset-payments", name: "Payments API", hostname: "api.payments.lab" },
  { id: "asset-db", name: "Primary database", hostname: "db-primary.lab" },
  { id: "asset-vpn", name: "VPN edge", hostname: "vpn-edge.lab" },
] as const;

export const DUMMY_ASSIGNEES = [
  { user_id: "usr-alex", label: "Alex Chen — Analyst" },
  { user_id: "usr-priya", label: "Priya Shah — Analyst" },
  { user_id: "usr-morgan", label: "Morgan Lee — Manager" },
] as const;

const COMPLETED: TaskStatus[] = ["completed", "reviewed", "closed"];

export function resultsUnlocked(status: TaskStatus): boolean {
  return COMPLETED.includes(status);
}

function hoursAgo(hours: number): string {
  return new Date(Date.now() - hours * 3_600_000).toISOString();
}

function uid(prefix: string): string {
  return `${prefix}-${Math.random().toString(36).slice(2, 10)}`;
}

function seedTasks(): Task[] {
  return [
    {
      id: "dummy-recon-storefront",
      target: "shop.internal.lab",
      description: "Surface recon of the customer storefront before the weekend release.",
      patch_scope: "edge + WAF",
      asset_id: "asset-shop",
      task_type: "red",
      status: "assigned",
      created_by: "usr-morgan",
      assignee_id: "usr-alex",
      assigning_manager_id: "usr-morgan",
      linked_job_id: null,
      started_at: null,
      completed_at: null,
      closed_at: null,
      created_at: hoursAgo(8),
      updated_at: hoursAgo(8),
    },
    {
      id: "dummy-payments-api",
      target: "api.payments.lab",
      description: "Authenticate and probe the payments API for IDOR and injection.",
      patch_scope: "API gateway",
      asset_id: "asset-payments",
      task_type: "red",
      status: "in_progress",
      created_by: "usr-morgan",
      assignee_id: "usr-priya",
      assigning_manager_id: "usr-morgan",
      linked_job_id: null,
      started_at: hoursAgo(0.6),
      completed_at: null,
      closed_at: null,
      created_at: hoursAgo(5),
      updated_at: hoursAgo(0.6),
    },
    {
      id: "dummy-db-hardening",
      target: "db-primary.lab",
      description: "Validate CVE exposure on the primary database and propose patches.",
      patch_scope: "postgres 15 cluster",
      asset_id: "asset-db",
      task_type: "blue",
      status: "completed",
      created_by: "usr-morgan",
      assignee_id: "usr-alex",
      assigning_manager_id: "usr-morgan",
      linked_job_id: null,
      started_at: hoursAgo(6),
      completed_at: hoursAgo(2),
      closed_at: null,
      created_at: hoursAgo(12),
      updated_at: hoursAgo(2),
    },
  ];
}

function chainStep(
  chainId: string,
  sequence: number,
  stage: Stage,
  title: string,
  severity: Severity,
  extra: Partial<DummyChainRecord> = {},
): DummyChainRecord {
  return {
    id: `${chainId}-s${sequence}`,
    chain_id: chainId,
    stage,
    sequence,
    title,
    severity,
    technique: extra.technique ?? "T1595",
    source_ip: extra.source_ip ?? "10.8.0.14",
    occurred_at: extra.occurred_at ?? hoursAgo(3),
    cve: extra.cve,
    cvss: extra.cvss,
  };
}

export function buildDummyResults(task: Pick<Task, "id" | "target" | "task_type">): TaskResults {
  const chainId = `chain-${task.id}`;
  const target = task.target || "unknown-host";
  const hostIp = task.task_type === "blue" ? "10.2.0.8" : "10.8.0.14";

  const chain: DummyChainRecord[] = [
    chainStep(chainId, 1, "recon", `Enumerated open ports and directories on ${target}`, "info", {
      technique: "T1595.002",
      source_ip: hostIp,
      occurred_at: hoursAgo(4),
    }),
    chainStep(chainId, 2, "recon", `Fingerprinted TLS and application stack on ${target}`, "low", {
      technique: "T1592.002",
      source_ip: hostIp,
      occurred_at: hoursAgo(3.6),
    }),
    chainStep(chainId, 3, "initial_access", `Weak credential accepted on staging vhost of ${target}`, "high", {
      technique: "T1078.001",
      source_ip: "203.0.113.44",
      occurred_at: hoursAgo(3.2),
      cve: "CVE-2024-3094",
      cvss: 7.8,
    }),
    chainStep(chainId, 4, "execution", `Command injection via export endpoint on ${target}`, "critical", {
      technique: "T1059.004",
      source_ip: "203.0.113.44",
      occurred_at: hoursAgo(2.8),
      cve: "CVE-2023-22515",
      cvss: 9.8,
    }),
    chainStep(chainId, 5, "persistence", "Cron implant written to /etc/cron.d/sys-update", "high", {
      technique: "T1053.003",
      source_ip: hostIp,
      occurred_at: hoursAgo(2.4),
    }),
    chainStep(chainId, 6, "exfiltration", "12 MB customer export staged to 198.51.100.22", "critical", {
      technique: "T1048.003",
      source_ip: hostIp,
      occurred_at: hoursAgo(2),
    }),
  ];

  const patches: Patch[] = [
    {
      id: `${task.id}-patch-1`,
      finding_id: `${chainId}-s3`,
      asset_id: null,
      title: `Rotate default/staging credentials on ${target}`,
      playbook: "identity-hardening",
      status: "proposed",
      evidence: [],
      applied_at: null,
      created_at: hoursAgo(1.8),
    },
    {
      id: `${task.id}-patch-2`,
      finding_id: `${chainId}-s4`,
      asset_id: null,
      title: `Parameterize the export endpoint and add WAF rule for ${target}`,
      playbook: "input-validation",
      status: "proposed",
      evidence: [],
      applied_at: null,
      created_at: hoursAgo(1.6),
    },
    {
      id: `${task.id}-patch-3`,
      finding_id: `${chainId}-s5`,
      asset_id: null,
      title: "Remove unauthorized cron and lock /etc/cron.d",
      playbook: "persistence-cleanup",
      status: task.task_type === "blue" ? "applied" : "proposed",
      evidence: [],
      applied_at: task.task_type === "blue" ? hoursAgo(1) : null,
      created_at: hoursAgo(1.4),
    },
  ];

  return { chain, patches };
}

function seedStore(): TaskRunnerStore {
  const tasks = seedTasks();
  const results: Record<string, TaskResults> = {};
  for (const task of tasks) {
    if (resultsUnlocked(task.status)) {
      results[task.id] = buildDummyResults(task);
    }
  }
  return { tasks, results };
}

function canUseStorage(): boolean {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

export function loadStore(): TaskRunnerStore {
  if (!canUseStorage()) return seedStore();
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      const seeded = seedStore();
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(seeded));
      return seeded;
    }
    const parsed = JSON.parse(raw) as TaskRunnerStore;
    if (!parsed?.tasks?.length) return seedStore();
    return {
      tasks: parsed.tasks,
      results: parsed.results ?? {},
    };
  } catch {
    return seedStore();
  }
}

function persist(store: TaskRunnerStore): TaskRunnerStore {
  if (canUseStorage()) {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(store));
    window.dispatchEvent(new Event(TASK_RUNNER_EVENT));
  }
  return store;
}

export function listDummyTasks(): Task[] {
  return loadStore().tasks.slice().sort((a, b) => {
    const ta = a.updated_at ?? a.created_at ?? "";
    const tb = b.updated_at ?? b.created_at ?? "";
    return tb.localeCompare(ta);
  });
}

export function getDummyTask(id: string): Task | undefined {
  return loadStore().tasks.find((t) => t.id === id);
}

export function getDummyResults(id: string): TaskResults | undefined {
  return loadStore().results[id];
}

export type DummyCreateInput = {
  target: string;
  description?: string;
  patch_scope?: string;
  task_type: TaskType;
  asset_id?: string | null;
  assignee_id?: string | null;
};

export function createDummyTask(input: DummyCreateInput): Task {
  const now = new Date().toISOString();
  const task: Task = {
    id: uid("task"),
    target: input.target.trim(),
    description: input.description?.trim() ?? "",
    patch_scope: input.patch_scope?.trim() ?? "",
    asset_id: input.asset_id || null,
    task_type: input.task_type,
    status: "assigned",
    created_by: "usr-morgan",
    assignee_id: input.assignee_id || "usr-alex",
    assigning_manager_id: "usr-morgan",
    linked_job_id: null,
    started_at: null,
    completed_at: null,
    closed_at: null,
    created_at: now,
    updated_at: now,
  };
  const store = loadStore();
  store.tasks = [task, ...store.tasks];
  persist(store);
  return task;
}

export function startDummyTask(id: string): Task {
  const store = loadStore();
  const task = store.tasks.find((t) => t.id === id);
  if (!task) throw new Error("Task not found");
  if (task.status === "completed" || task.status === "reviewed" || task.status === "closed") {
    return task;
  }
  const now = new Date().toISOString();
  task.status = "in_progress";
  task.started_at = task.started_at ?? now;
  task.updated_at = now;
  persist(store);
  return task;
}

export function completeDummyTask(id: string): Task {
  const store = loadStore();
  const task = store.tasks.find((t) => t.id === id);
  if (!task) throw new Error("Task not found");
  const now = new Date().toISOString();
  task.status = "completed";
  task.completed_at = now;
  task.updated_at = now;
  if (!store.results[task.id]) {
    store.results[task.id] = buildDummyResults(task);
  }
  persist(store);
  return task;
}

export function applyDummyPatch(taskId: string, patchId: string): Patch {
  const store = loadStore();
  const results = store.results[taskId];
  if (!results) throw new Error("No patches for this task");
  const patch = results.patches.find((p) => p.id === patchId);
  if (!patch) throw new Error("Patch not found");
  const now = new Date().toISOString();
  patch.status = "applied";
  patch.applied_at = now;
  persist(store);
  return patch;
}
