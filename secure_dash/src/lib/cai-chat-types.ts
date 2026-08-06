export type CaiTeam = "red" | "blue";

export type CaiSessionStatus = "starting" | "running" | "stopping" | "stopped" | "failed";

export type CaiStreamEventType =
  | "started"
  | "stdout"
  | "stderr"
  | "user_echo"
  | "status"
  | "error"
  | "ended";

export type CaiSession = {
  id: string;
  team: CaiTeam;
  status: CaiSessionStatus;
  task_id: string | null;
  created_at: string | null;
  updated_at: string | null;
  ended_at: string | null;
  error: string | null;
};

export type CaiStreamEvent = {
  session_id: string;
  seq: number;
  type: CaiStreamEventType;
  text: string;
  ts: string | null;
};
