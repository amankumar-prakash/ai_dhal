export type RedTeamChatTeam = "red" | "blue";

export type RedTeamChatSessionStatus =
  | "starting"
  | "running"
  | "stopping"
  | "stopped"
  | "failed";

export type RedTeamChatChannel = "user" | "agent" | "system" | "tool";

export type RedTeamChatStreamEventType =
  | "started"
  | "status"
  | "error"
  | "ended"
  | "user_echo"
  | "agent_message"
  | "tool_call_pending"
  | "tool_call_approved"
  | "tool_call_stopped"
  | "tool_result";

export type RedTeamChatSession = {
  id: string;
  team: RedTeamChatTeam;
  status: RedTeamChatSessionStatus;
  task_id: string | null;
  busy: boolean;
  pending_call_id: string | null;
  created_at: string | null;
  updated_at: string | null;
  ended_at: string | null;
  error: string | null;
};

export type RedTeamChatStreamEvent = {
  session_id: string;
  seq: number;
  type: RedTeamChatStreamEventType;
  channel: RedTeamChatChannel;
  text: string;
  call_id?: string | null;
  tool?: string | null;
  args?: Record<string, unknown> | null;
  ts: string | null;
};
