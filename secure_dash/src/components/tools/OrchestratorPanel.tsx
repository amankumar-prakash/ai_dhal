import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  enhanceTargetDescription,
  executePlan,
  controlRun,
  fetchRunState,
  generateOrchestratorPlan,
  fetchOrchestratorTools,
  downloadReport,
  type EnhanceDescriptionResponse,
  type OrchestratorPlan,
  type OrchestratorRunState,
  type PlanStage,
  type RunStatus,
  type ToolDefinition,
} from "@/lib/orchestrator-client";
import { getAccessToken } from "@/lib/api-client";

// ─── Helpers ─────────────────────────────────────────────────────────────────

type WizardStep = 0 | 1 | 2 | 3;

const STATUS_COLOR: Record<string, string> = {
  pending: "#6b7280",
  running: "#3b82f6",
  completed: "#22c55e",
  failed: "#ef4444",
  skipped: "#9ca3af",
  paused: "#f59e0b",
  finished: "#22c55e",
  aborted: "#ef4444",
};

const SEVERITY_COLOR: Record<string, string> = {
  critical: "#dc2626",
  high: "#ea580c",
  medium: "#d97706",
  low: "#16a34a",
  info: "#6b7280",
};

function StatusBadge({ status }: { status: string }) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        padding: "2px 10px",
        borderRadius: 999,
        fontSize: 11,
        fontWeight: 600,
        letterSpacing: "0.05em",
        background: STATUS_COLOR[status] + "22",
        color: STATUS_COLOR[status] ?? "#6b7280",
        border: `1px solid ${STATUS_COLOR[status] ?? "#6b7280"}44`,
        textTransform: "uppercase",
      }}
    >
      {status === "running" && (
        <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#3b82f6", animation: "pulse 1s infinite" }} />
      )}
      {status}
    </span>
  );
}

// ─── Step 0: Target Input ────────────────────────────────────────────────────

function StepTargetInput({
  onEnhanced,
}: {
  onEnhanced: (resp: EnhanceDescriptionResponse, raw: string) => void;
}) {
  const [rawInput, setRawInput] = useState("");
  const [scopeNotes, setScopeNotes] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleEnhance = async () => {
    if (!rawInput.trim()) return;
    setLoading(true);
    setError("");
    try {
      const token = await getAccessToken();
      const resp = await enhanceTargetDescription(
        { raw_input: rawInput, scope_notes: scopeNotes || undefined },
        token,
      );
      onEnhanced(resp, rawInput);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Enhancement failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div style={fieldGroup}>
        <label style={labelStyle}>Target Description</label>
        <textarea
          id="orch-raw-input"
          value={rawInput}
          onChange={(e) => setRawInput(e.target.value)}
          placeholder="e.g. Web app at 10.0.0.5, test OWASP Top 10, also scan 192.168.1.0/24 network"
          rows={4}
          style={textareaStyle}
        />
      </div>
      <div style={fieldGroup}>
        <label style={labelStyle}>Scope Notes (optional)</label>
        <textarea
          id="orch-scope-notes"
          value={scopeNotes}
          onChange={(e) => setScopeNotes(e.target.value)}
          placeholder="e.g. Exclude 192.168.1.1, PCI-DSS compliance required, no DoS testing"
          rows={2}
          style={{ ...textareaStyle, minHeight: 60 }}
        />
      </div>
      {error && <div style={errorBox}>{error}</div>}
      <button
        id="orch-enhance-btn"
        onClick={handleEnhance}
        disabled={loading || !rawInput.trim()}
        style={primaryBtn}
      >
        {loading ? "✨ Enhancing with AI..." : "✨ Enhance Target Profile with AI"}
      </button>
    </div>
  );
}

// ─── Step 1: Plan Review ─────────────────────────────────────────────────────

function StepPlanReview({
  enhanced,
  onPlanReady,
}: {
  enhanced: EnhanceDescriptionResponse;
  onPlanReady: (plan: OrchestratorPlan, stages: PlanStage[]) => void;
}) {
  const [plan, setPlan] = useState<OrchestratorPlan | null>(null);
  const [editStages, setEditStages] = useState<PlanStage[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleGeneratePlan = async () => {
    setLoading(true);
    setError("");
    try {
      const token = await getAccessToken();
      const generated = await generateOrchestratorPlan(
        {
          enhanced_description: enhanced.enhanced_description,
          target_profile: enhanced.target_profile,
          max_stages: enhanced.suggested_phase_count,
        },
        token,
      );
      setPlan(generated);
      setEditStages(generated.stages);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Plan generation failed");
    } finally {
      setLoading(false);
    }
  };

  const toggleStep = (stageIdx: number, stepIdx: number) => {
    setEditStages((prev) =>
      prev.map((s, si) =>
        si !== stageIdx
          ? s
          : {
              ...s,
              steps: s.steps.map((st, ti) =>
                ti !== stepIdx ? st : { ...st, enabled: !st.enabled },
              ),
            },
      ),
    );
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Target Profile Summary */}
      <div style={card}>
        <div style={cardTitle}>🎯 Enhanced Target Profile</div>
        <p style={{ margin: "8px 0", color: "#94a3b8", fontSize: 13, lineHeight: 1.6 }}>
          {enhanced.enhanced_description}
        </p>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 12 }}>
          {enhanced.target_profile.targets.map((t) => (
            <span key={t} style={tagStyle("#3b82f6")}>🖥 {t}</span>
          ))}
          {enhanced.target_profile.compliance_flags.map((f) => (
            <span key={f} style={tagStyle("#a855f7")}>✓ {f}</span>
          ))}
          {enhanced.target_profile.out_of_scope.map((o) => (
            <span key={o} style={tagStyle("#ef4444")}>✗ {o}</span>
          ))}
        </div>
      </div>

      {!plan && (
        <>
          {error && <div style={errorBox}>{error}</div>}
          <button
            id="orch-generate-plan-btn"
            onClick={handleGeneratePlan}
            disabled={loading}
            style={primaryBtn}
          >
            {loading ? "🧠 Generating Plan..." : "🧠 Generate Attack Plan"}
          </button>
        </>
      )}

      {plan && (
        <>
          <div style={card}>
            <div style={cardTitle}>{plan.title}</div>
            <div style={{ fontSize: 12, color: "#64748b", marginTop: 4 }}>
              Plan ID: <code style={{ color: "#94a3b8" }}>{plan.plan_id}</code> · Model:{" "}
              <code style={{ color: "#94a3b8" }}>{plan.model_used}</code>
            </div>
          </div>

          {editStages.map((stage, si) => (
            <div key={stage.stage_id} style={{ ...card, borderColor: "#334155" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div style={cardTitle}>
                  {si + 1}. {stage.label}
                </div>
                <span style={{ fontSize: 11, color: "#64748b" }}>{stage.steps.length} steps</span>
              </div>
              <p style={{ color: "#64748b", fontSize: 12, margin: "6px 0 12px" }}>{stage.description}</p>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {stage.steps.map((step, ti) => (
                  <label
                    key={step.step_id}
                    style={{
                      display: "flex",
                      alignItems: "flex-start",
                      gap: 10,
                      cursor: "pointer",
                      padding: "8px 12px",
                      borderRadius: 8,
                      background: step.enabled ? "#1e293b" : "#0f172a",
                      border: `1px solid ${step.enabled ? "#334155" : "#1e293b"}`,
                      transition: "all 0.2s",
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={step.enabled}
                      onChange={() => toggleStep(si, ti)}
                      style={{ marginTop: 2, accentColor: "#3b82f6" }}
                    />
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 600, color: step.enabled ? "#e2e8f0" : "#475569" }}>
                        {step.tool_name}
                      </div>
                      <div style={{ fontSize: 11, color: "#64748b", marginTop: 2 }}>
                        {step.description}
                      </div>
                    </div>
                  </label>
                ))}
              </div>
            </div>
          ))}

          {error && <div style={errorBox}>{error}</div>}

          <div style={{ display: "flex", gap: 12 }}>
            <button
              id="orch-execute-btn"
              onClick={() => onPlanReady(plan, editStages)}
              style={{ ...primaryBtn, flex: 1 }}
            >
              ▶ Execute Plan
            </button>
            <button
              id="orch-dry-run-btn"
              onClick={() => onPlanReady({ ...plan, plan_id: plan.plan_id + "-dry" }, editStages)}
              style={{ ...secondaryBtn, flex: 1 }}
            >
              🔍 Dry Run (no real execution)
            </button>
          </div>
        </>
      )}
    </div>
  );
}

// ─── Step 2: Live Execution ──────────────────────────────────────────────────

function StepExecution({
  plan,
  stages,
  enhanced,
  onComplete,
}: {
  plan: OrchestratorPlan;
  stages: PlanStage[];
  enhanced: EnhanceDescriptionResponse;
  onComplete: (runState: OrchestratorRunState) => void;
}) {
  const [runState, setRunState] = useState<OrchestratorRunState | null>(null);
  const [error, setError] = useState("");
  const [polling, setPolling] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const isDryRun = plan.plan_id.endsWith("-dry");

  const startExecution = async () => {
    setError("");
    try {
      const token = await getAccessToken();
      const state = await executePlan(
        {
          plan_id: plan.plan_id.replace("-dry", ""),
          stages,
          target_profile: enhanced.target_profile,
          enhanced_description: enhanced.enhanced_description,
          dry_run: isDryRun,
        },
        token,
      );
      setRunState(state);
      setPolling(true);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Execution failed to start");
    }
  };

  useEffect(() => {
    if (!polling || !runState) return;
    pollRef.current = setInterval(async () => {
      try {
        const token = await getAccessToken();
        const updated = await fetchRunState(runState.run_id, token);
        setRunState(updated);
        if (["finished", "failed", "aborted"].includes(updated.status)) {
          setPolling(false);
          if (pollRef.current) clearInterval(pollRef.current);
          onComplete(updated);
        }
      } catch {
        /* ignore poll errors */
      }
    }, 2000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [polling, runState?.run_id]);

  const handleControl = async (action: "pause" | "resume" | "abort") => {
    if (!runState) return;
    try {
      const token = await getAccessToken();
      const updated = await controlRun(runState.run_id, action, token);
      setRunState(updated);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Control command failed");
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {isDryRun && (
        <div style={{ padding: "8px 14px", background: "#f59e0b22", border: "1px solid #f59e0b44", borderRadius: 8, color: "#fbbf24", fontSize: 12 }}>
          🔍 Dry-run mode — no real tool commands will be executed
        </div>
      )}

      {!runState && (
        <>
          {error && <div style={errorBox}>{error}</div>}
          <button id="orch-start-execute-btn" onClick={startExecution} style={primaryBtn}>
            ▶ Start Execution Now
          </button>
        </>
      )}

      {runState && (
        <>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <div style={{ fontSize: 12, color: "#64748b" }}>Run ID</div>
              <code style={{ fontSize: 12, color: "#94a3b8" }}>{runState.run_id}</code>
            </div>
            <StatusBadge status={runState.status} />
          </div>

          {/* Stage progress */}
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {runState.stages.map((stage) => (
              <div key={stage.stage_id} style={{ ...card, padding: "14px 16px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                  <span style={{ fontWeight: 600, fontSize: 13, color: "#e2e8f0" }}>{stage.label}</span>
                  <StatusBadge status={stage.status} />
                </div>
                {stage.steps.length > 0 && (
                  <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                    {stage.steps.map((step) => (
                      <div
                        key={step.step_id}
                        style={{
                          padding: "6px 10px",
                          borderRadius: 6,
                          background: "#0f172a",
                          border: `1px solid ${STATUS_COLOR[step.status] ?? "#1e293b"}33`,
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          gap: 8,
                        }}
                      >
                        <span style={{ fontSize: 12, color: "#94a3b8" }}>{step.tool_name}</span>
                        <StatusBadge status={step.status} />
                      </div>
                    ))}
                  </div>
                )}
                {/* Output preview */}
                {stage.steps.some((s) => s.stdout) && (
                  <pre
                    style={{
                      marginTop: 8,
                      padding: "8px 10px",
                      background: "#020617",
                      border: "1px solid #1e293b",
                      borderRadius: 6,
                      fontSize: 10,
                      color: "#4ade80",
                      maxHeight: 120,
                      overflow: "auto",
                      whiteSpace: "pre-wrap",
                      wordBreak: "break-word",
                    }}
                  >
                    {stage.steps
                      .filter((s) => s.stdout)
                      .map((s) => `[${s.tool_name}]\n${s.stdout}`)
                      .join("\n\n")}
                  </pre>
                )}
              </div>
            ))}
          </div>

          {/* Control buttons */}
          {["executing", "pending"].includes(runState.status) && (
            <div style={{ display: "flex", gap: 10 }}>
              <button
                id="orch-pause-btn"
                onClick={() => handleControl("pause")}
                style={{ ...secondaryBtn, flex: 1 }}
              >
                ⏸ Pause
              </button>
              <button
                id="orch-abort-btn"
                onClick={() => handleControl("abort")}
                style={{ ...dangerBtn, flex: 1 }}
              >
                ✕ Abort
              </button>
            </div>
          )}
          {runState.status === "paused" && (
            <button
              id="orch-resume-btn"
              onClick={() => handleControl("resume")}
              style={primaryBtn}
            >
              ▶ Resume
            </button>
          )}
          {error && <div style={errorBox}>{error}</div>}
        </>
      )}
    </div>
  );
}

// ─── Step 3: Report / Findings ────────────────────────────────────────────────

function StepReport({
  runState,
  enhanced,
}: {
  runState: OrchestratorRunState;
  enhanced: EnhanceDescriptionResponse;
}) {
  const [downloading, setDownloading] = useState(false);

  const totalFindings = 0; // findings counted server-side; just show run summary
  const stagesSummary = runState.stages;

  const handleDownload = async (format: "json" | "csv" | "markdown") => {
    setDownloading(true);
    try {
      const token = await getAccessToken();
      const apiBase = (
        (typeof import.meta !== "undefined" &&
          (import.meta as { env?: Record<string, string> }).env?.VITE_API_BASE_URL) ||
        "http://localhost:8000/api/v1"
      ).replace(/\/$/, "");
      const url = `${apiBase}/orchestrator/reports/${runState.run_id}?format=${format}`;
      const res = await fetch(url, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const blob = await res.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `report-${runState.run_id}.${format === "markdown" ? "md" : format}`;
      a.click();
    } catch {
      /* silent */
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Summary Card */}
      <div style={{ ...card, borderColor: runState.status === "finished" ? "#22c55e44" : "#ef444444" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={cardTitle}>
            {runState.status === "finished" ? "✅ Engagement Complete" : "⚠️ Engagement " + runState.status}
          </div>
          <StatusBadge status={runState.status} />
        </div>
        <div style={{ display: "flex", gap: 24, marginTop: 14 }}>
          {[
            ["Run ID", runState.run_id],
            ["Targets", enhanced.target_profile.targets.join(", ") || "—"],
            ["Stages Run", `${stagesSummary.filter((s) => s.status === "completed").length} / ${stagesSummary.length}`],
          ].map(([label, value]) => (
            <div key={label}>
              <div style={{ fontSize: 10, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.08em" }}>{label}</div>
              <div style={{ fontSize: 13, color: "#94a3b8", marginTop: 2 }}>{value}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Stage Summary Table */}
      <div style={card}>
        <div style={cardTitle}>Stage Summary</div>
        <table style={{ width: "100%", borderCollapse: "collapse", marginTop: 12, fontSize: 12 }}>
          <thead>
            <tr style={{ color: "#64748b", borderBottom: "1px solid #1e293b" }}>
              <th style={{ textAlign: "left", padding: "4px 8px" }}>Stage</th>
              <th style={{ textAlign: "center", padding: "4px 8px" }}>Status</th>
              <th style={{ textAlign: "center", padding: "4px 8px" }}>Steps</th>
            </tr>
          </thead>
          <tbody>
            {stagesSummary.map((s) => (
              <tr key={s.stage_id} style={{ borderBottom: "1px solid #0f172a" }}>
                <td style={{ padding: "6px 8px", color: "#e2e8f0" }}>{s.label}</td>
                <td style={{ padding: "6px 8px", textAlign: "center" }}>
                  <StatusBadge status={s.status} />
                </td>
                <td style={{ padding: "6px 8px", textAlign: "center", color: "#94a3b8" }}>
                  {s.steps.length}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Download Buttons */}
      <div style={card}>
        <div style={cardTitle}>📥 Export Report</div>
        <div style={{ display: "flex", gap: 10, marginTop: 12 }}>
          {(["json", "csv", "markdown"] as const).map((fmt) => (
            <button
              key={fmt}
              id={`orch-download-${fmt}-btn`}
              onClick={() => handleDownload(fmt)}
              disabled={downloading}
              style={{ ...secondaryBtn, flex: 1 }}
            >
              {fmt === "json" ? "📄 JSON" : fmt === "csv" ? "📊 CSV" : "📝 Markdown"}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── Main OrchestratorPanel ───────────────────────────────────────────────────

export function OrchestratorPanel({ taskId }: { taskId?: string }) {
  const [step, setStep] = useState<WizardStep>(0);
  const [enhanced, setEnhanced] = useState<EnhanceDescriptionResponse | null>(null);
  const [plan, setPlan] = useState<OrchestratorPlan | null>(null);
  const [editStages, setEditStages] = useState<PlanStage[]>([]);
  const [runState, setRunState] = useState<OrchestratorRunState | null>(null);

  const STEPS = ["1. Target & Scope", "2. Plan Review", "3. Live Execution", "4. Report & Findings"];

  return (
    <div
      style={{
        background: "linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%)",
        border: "1px solid #312e81",
        borderRadius: 16,
        padding: 24,
        marginTop: 24,
        boxShadow: "0 4px 32px rgba(99,102,241,0.12)",
      }}
    >
      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
          <span style={{ fontSize: 22 }}>🤖</span>
          <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700, color: "#e2e8f0" }}>
            AI Red-Team Orchestrator
          </h2>
          <span
            style={{
              padding: "2px 10px",
              borderRadius: 999,
              fontSize: 10,
              fontWeight: 700,
              background: "#6366f122",
              color: "#818cf8",
              border: "1px solid #6366f144",
              letterSpacing: "0.06em",
            }}
          >
            AI-POWERED
          </span>
        </div>
        <p style={{ margin: 0, fontSize: 12, color: "#64748b" }}>
          LLM-guided multi-stage red-team engagement planner and executor.
        </p>
      </div>

      {/* Wizard Progress */}
      <div style={{ display: "flex", gap: 0, marginBottom: 28, position: "relative" }}>
        {STEPS.map((label, i) => {
          const active = i === step;
          const done = i < step;
          return (
            <div
              key={i}
              style={{
                flex: 1,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: 6,
                cursor: done ? "pointer" : "default",
              }}
              onClick={() => { if (done) setStep(i as WizardStep); }}
            >
              <div
                style={{
                  width: 28,
                  height: 28,
                  borderRadius: "50%",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 12,
                  fontWeight: 700,
                  background: done ? "#6366f1" : active ? "#4f46e5" : "#1e293b",
                  color: done || active ? "#fff" : "#475569",
                  border: active ? "2px solid #818cf8" : "2px solid transparent",
                  transition: "all 0.3s",
                  zIndex: 1,
                  position: "relative",
                }}
              >
                {done ? "✓" : i + 1}
              </div>
              <span
                style={{
                  fontSize: 10,
                  color: active ? "#818cf8" : done ? "#6366f1" : "#475569",
                  fontWeight: active ? 700 : 500,
                  textAlign: "center",
                  whiteSpace: "nowrap",
                }}
              >
                {label}
              </span>
              {i < STEPS.length - 1 && (
                <div
                  style={{
                    position: "absolute",
                    top: 14,
                    left: `calc(${((i + 0.5) / STEPS.length) * 100}% + 14px)`,
                    width: `calc(${(1 / STEPS.length) * 100}% - 28px)`,
                    height: 2,
                    background: done ? "#6366f1" : "#1e293b",
                    transition: "all 0.3s",
                  }}
                />
              )}
            </div>
          );
        })}
      </div>

      {/* Wizard Content */}
      {step === 0 && (
        <StepTargetInput
          onEnhanced={(resp, raw) => {
            setEnhanced(resp);
            setStep(1);
          }}
        />
      )}
      {step === 1 && enhanced && (
        <StepPlanReview
          enhanced={enhanced}
          onPlanReady={(p, s) => {
            setPlan(p);
            setEditStages(s);
            setStep(2);
          }}
        />
      )}
      {step === 2 && plan && enhanced && (
        <StepExecution
          plan={plan}
          stages={editStages}
          enhanced={enhanced}
          onComplete={(rs) => {
            setRunState(rs);
            setStep(3);
          }}
        />
      )}
      {step === 3 && runState && enhanced && (
        <StepReport runState={runState} enhanced={enhanced} />
      )}

      {/* Reset / Back navigation */}
      {step > 0 && (
        <div style={{ display: "flex", justifyContent: "space-between", marginTop: 20 }}>
          <button
            onClick={() => setStep((step - 1) as WizardStep)}
            style={ghostBtn}
            disabled={step === 2 && runState !== null}
          >
            ← Back
          </button>
          {step !== 2 && (
            <button
              onClick={() => {
                setStep(0);
                setEnhanced(null);
                setPlan(null);
                setEditStages([]);
                setRunState(null);
              }}
              style={ghostBtn}
            >
              ↺ Start Over
            </button>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Shared Styles ────────────────────────────────────────────────────────────

const card: React.CSSProperties = {
  background: "#1e293b",
  border: "1px solid #334155",
  borderRadius: 12,
  padding: "16px 20px",
};

const cardTitle: React.CSSProperties = {
  fontWeight: 700,
  fontSize: 14,
  color: "#e2e8f0",
};

const fieldGroup: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: 6,
};

const labelStyle: React.CSSProperties = {
  fontSize: 12,
  fontWeight: 600,
  color: "#94a3b8",
  letterSpacing: "0.05em",
};

const textareaStyle: React.CSSProperties = {
  background: "#1e293b",
  border: "1px solid #334155",
  borderRadius: 10,
  padding: "10px 14px",
  color: "#e2e8f0",
  fontSize: 13,
  resize: "vertical",
  minHeight: 80,
  fontFamily: "inherit",
  outline: "none",
  lineHeight: 1.6,
};

const primaryBtn: React.CSSProperties = {
  background: "linear-gradient(135deg, #4f46e5, #7c3aed)",
  color: "#fff",
  border: "none",
  borderRadius: 10,
  padding: "11px 20px",
  fontSize: 13,
  fontWeight: 700,
  cursor: "pointer",
  transition: "opacity 0.2s",
  width: "100%",
};

const secondaryBtn: React.CSSProperties = {
  background: "#1e293b",
  color: "#94a3b8",
  border: "1px solid #334155",
  borderRadius: 10,
  padding: "10px 20px",
  fontSize: 13,
  fontWeight: 600,
  cursor: "pointer",
};

const dangerBtn: React.CSSProperties = {
  background: "#450a0a",
  color: "#fca5a5",
  border: "1px solid #7f1d1d",
  borderRadius: 10,
  padding: "10px 20px",
  fontSize: 13,
  fontWeight: 600,
  cursor: "pointer",
};

const ghostBtn: React.CSSProperties = {
  background: "transparent",
  color: "#64748b",
  border: "none",
  fontSize: 12,
  cursor: "pointer",
  padding: "6px 10px",
};

const errorBox: React.CSSProperties = {
  background: "#450a0a",
  border: "1px solid #7f1d1d",
  borderRadius: 8,
  padding: "10px 14px",
  color: "#fca5a5",
  fontSize: 12,
};

function tagStyle(color: string): React.CSSProperties {
  return {
    padding: "3px 10px",
    borderRadius: 999,
    fontSize: 11,
    fontWeight: 600,
    background: color + "22",
    color,
    border: `1px solid ${color}44`,
  };
}
