// Orchestrator API client — types and fetch helpers for the AI Red-Team Orchestrator endpoints.

import { apiFetch } from "@/lib/api-client";

// ─── Types ───────────────────────────────────────────────────────────────────

export interface ToolParam {
  name: string;
  type: string;
  required: boolean;
  description: string;
  default?: unknown;
}

export interface ToolDefinition {
  id: string;
  name: string;
  category: "recon" | "vuln_scan" | "exploitation" | "post_exploitation";
  description: string;
  params: ToolParam[];
  source: "hexstrike" | "cai" | "builtin";
}

export interface ToolRegistryResponse {
  tools: ToolDefinition[];
  discovered_at: string;
}

export interface TargetProfile {
  targets: string[];
  ports: string[];
  attack_surface_notes: string;
  compliance_flags: string[];
  out_of_scope: string[];
}

export interface EnhanceDescriptionRequest {
  raw_input: string;
  scope_notes?: string;
}

export interface EnhanceDescriptionResponse {
  enhanced_description: string;
  target_profile: TargetProfile;
  suggested_phase_count: number;
  model_used: string;
}

export interface OrchestratorPlanRequest {
  enhanced_description: string;
  target_profile: TargetProfile;
  tool_ids?: string[];
  max_stages?: number;
}

export interface ToolStep {
  step_id: string;
  tool_id: string;
  tool_name: string;
  description: string;
  params: Record<string, unknown>;
  expected_output: string;
  enabled: boolean;
}

export interface PlanStage {
  stage_id: string;
  name: string;
  label: string;
  description: string;
  steps: ToolStep[];
  depends_on: string[];
}

export interface OrchestratorPlan {
  plan_id: string;
  title: string;
  target_profile: TargetProfile;
  enhanced_description: string;
  stages: PlanStage[];
  created_at: string;
  model_used: string;
}

export interface ExecutePlanRequest {
  plan_id: string;
  stages: PlanStage[];
  target_profile: TargetProfile;
  enhanced_description: string;
  dry_run?: boolean;
}

export interface StepExecutionLog {
  step_id: string;
  tool_id: string;
  tool_name: string;
  status: "pending" | "running" | "completed" | "failed" | "skipped";
  started_at?: string;
  finished_at?: string;
  stdout: string;
  stderr: string;
  exit_code?: number;
  params_used: Record<string, unknown>;
}

export interface StageExecutionLog {
  stage_id: string;
  label: string;
  status: "pending" | "running" | "completed" | "failed" | "skipped";
  started_at?: string;
  finished_at?: string;
  steps: StepExecutionLog[];
}

export type RunStatus =
  | "pending"
  | "enhancing"
  | "planning"
  | "executing"
  | "paused"
  | "finished"
  | "failed"
  | "aborted";

export interface OrchestratorRunState {
  run_id: string;
  plan_id: string;
  status: RunStatus;
  current_stage_id?: string;
  stages: StageExecutionLog[];
  started_at?: string;
  finished_at?: string;
  error?: string;
  dry_run: boolean;
}

// ─── API functions ────────────────────────────────────────────────────────────

export function fetchOrchestratorTools(token?: string | null): Promise<ToolRegistryResponse> {
  return apiFetch<ToolRegistryResponse>("/orchestrator/tools", { token });
}

export function enhanceTargetDescription(
  req: EnhanceDescriptionRequest,
  token?: string | null,
): Promise<EnhanceDescriptionResponse> {
  return apiFetch<EnhanceDescriptionResponse>("/orchestrator/enhance", {
    method: "POST",
    body: JSON.stringify(req),
    token,
  });
}

export function generateOrchestratorPlan(
  req: OrchestratorPlanRequest,
  token?: string | null,
): Promise<OrchestratorPlan> {
  return apiFetch<OrchestratorPlan>("/orchestrator/plan", {
    method: "POST",
    body: JSON.stringify(req),
    token,
  });
}

export function executePlan(
  req: ExecutePlanRequest,
  token?: string | null,
): Promise<OrchestratorRunState> {
  return apiFetch<OrchestratorRunState>("/orchestrator/execute", {
    method: "POST",
    body: JSON.stringify(req),
    token,
  });
}

export function fetchRunState(
  runId: string,
  token?: string | null,
): Promise<OrchestratorRunState> {
  return apiFetch<OrchestratorRunState>(`/orchestrator/runs/${runId}`, { token });
}

export function controlRun(
  runId: string,
  action: "pause" | "resume" | "abort",
  token?: string | null,
): Promise<OrchestratorRunState> {
  return apiFetch<OrchestratorRunState>(`/orchestrator/runs/${runId}/control`, {
    method: "POST",
    body: JSON.stringify({ action }),
    token,
  });
}

export function downloadReport(
  runId: string,
  format: "json" | "csv" | "markdown" = "json",
  token?: string | null,
): Promise<unknown> {
  return apiFetch(`/orchestrator/reports/${runId}?format=${format}`, { token });
}
