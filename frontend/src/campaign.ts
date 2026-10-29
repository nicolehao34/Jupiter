import type { AgentStep, InferenceMode } from "./types";

export type ActionKind = "idle" | "running" | "checkpoint" | "error" | "continue" | "inspect";

export interface NextAction {
  title: string;
  body: string;
  href: string;
  cta: string;
  kind: ActionKind;
}

export interface OriginInfo {
  kind: string;
  label: string;
  tone: "measured" | "predicted" | "synthetic" | "simulated" | "unknown";
}

export const DATA_ORIGINS: OriginInfo[] = [
  { kind: "measured", label: "Measured (lab)", tone: "measured" },
  { kind: "surrogate_prediction", label: "Predicted (GP)", tone: "predicted" },
  { kind: "synthetic_demonstration", label: "Synthetic demo", tone: "synthetic" },
  { kind: "simulated", label: "Simulated (PyBaMM)", tone: "simulated" },
];

export function originInfo(kind?: string | null): OriginInfo {
  return DATA_ORIGINS.find((item) => item.kind === kind) || {
    kind: kind || "unspecified",
    label: kind ? `Unspecified (${kind})` : "Unspecified origin",
    tone: "unknown",
  };
}

export function stopReasonLabel(reason?: string | null): string {
  switch (reason) {
    case "human_checkpoint":
      return "Human checkpoint — lab handoff";
    case "awaiting_lab_results":
      return "Waiting for new measured results";
    case "tool_error":
      return "Stopped on tool error";
    case "max_steps":
      return "Stopped: step budget exhausted";
    case "model_stop":
      return "Model ended the turn";
    case "session_reset":
      return "Session reset";
    default:
      return reason || "No agent turn yet";
  }
}

export function inferenceHeadline(mode?: InferenceMode | string | null): string {
  if (mode === "live") return "Live Token Factory";
  if (mode === "offline_demo") return "Offline demo — not live Nebius";
  if (mode === "failed") return "Token Factory call failed";
  return "Nemotron unconfigured";
}

export function phaseLabel(phase?: string | null, stopReason?: string | null): string {
  switch (phase || stopReason) {
    case "human_checkpoint":
      return "Human checkpoint";
    case "awaiting_lab_results":
      return "Awaiting lab results";
    case "observe":
      return "Observing campaign";
    case "idle":
      return "Idle";
    default:
      return phase || stopReasonLabel(stopReason);
  }
}

export function nextCampaignAction(opts: {
  busy?: boolean;
  stopReason?: string | null;
  canContinue?: boolean;
  nBatches?: number;
  nObserved?: number;
  inferenceMode?: string | null;
}): NextAction {
  if (opts.busy) {
    return {
      title: "Campaign running",
      body: "The agent is calling tools. Ranking still comes from generate_batch (GP + EI), not from Nemotron text.",
      href: "#/agent",
      cta: "Watch tool transcript",
      kind: "running",
    };
  }
  switch (opts.stopReason) {
    case "human_checkpoint":
      return {
        title: "Human checkpoint",
        body: `The agent stopped before inventing furnace data. ${opts.nObserved ?? 0} observed row(s) are stored. Record measured capacity on Plan, then Continue campaign.`,
        href: "#/plan",
        cta: "Record measured results",
        kind: "checkpoint",
      };
    case "awaiting_lab_results":
      return {
        title: "Need new measurements",
        body: `Continue was requested without new observations (${opts.nObserved ?? 0} stored). Type or upload measured capacity on Plan, then continue.`,
        href: "#/plan",
        cta: "Enter lab results",
        kind: "checkpoint",
      };
    case "tool_error":
      return {
        title: "Recoverable tool error",
        body: "A tool failed. Inspect the transcript, fix the campaign on Plan if needed, then run the agent again. Do not treat a failed tool as a live result.",
        href: "#/agent",
        cta: "Inspect transcript",
        kind: "error",
      };
    case "max_steps":
      return {
        title: "Step budget exhausted",
        body: "The turn hit the tool-step limit. Inspect what finished, then run or continue after checking Plan.",
        href: "#/agent",
        cta: "Review agent activity",
        kind: "error",
      };
    default:
      break;
  }
  if (!opts.nBatches) {
    const live = opts.inferenceMode === "live";
    return {
      title: "Start the campaign",
      body: live
        ? "Run the agent to inspect, rank a GP batch, and emit a furnace run sheet — or generate a batch on Plan."
        : "Token Factory is not live. Run the labeled playbook of the same tools, or generate a batch on Plan. Ranking is still the Gaussian process.",
      href: "#/agent",
      cta: "Open agent",
      kind: "idle",
    };
  }
  if (opts.canContinue) {
    return {
      title: "Ready to continue",
      body: "A session is waiting. Record any new measured results, then Continue campaign on Agent.",
      href: "#/agent",
      cta: "Continue campaign",
      kind: "continue",
    };
  }
  return {
    title: "Inspect campaign",
    body: "Review ranked runs and in-sample residuals. Ranking remains a Gaussian process.",
    href: "#/review",
    cta: "Open review",
    kind: "inspect",
  };
}

export function planStepStatusText(
  status: string,
  stepId?: string,
  stopReason?: string | null,
): string {
  if (stepId === "checkpoint") {
    if (stopReason === "awaiting_lab_results") return "Waiting for measurements";
    if (stopReason === "human_checkpoint") return "Your turn at the bench";
    return "Pending human";
  }
  if (status === "done") return "Done";
  if (status === "running") return "Running";
  if (status === "error") return "Error";
  return "Pending";
}

export function normalizePlanSteps<T extends { id: string; status: string }>(
  steps: T[],
  stopReason?: string | null,
): T[] {
  const handedOff = stopReason === "human_checkpoint" || stopReason === "awaiting_lab_results";
  return steps.map((step, index) => {
    if (step.id === "checkpoint") return step;
    const laterDone = steps.slice(index + 1).some((other) => other.id !== "checkpoint" && other.status === "done");
    if (step.status === "running" && (handedOff || laterDone)) {
      return { ...step, status: "done" };
    }
    return step;
  });
}

export function toolProvenance(step: AgentStep): string | null {
  if (!step.ok) return step.error || "Tool failed";
  const result = (step.result || {}) as Record<string, unknown>;
  switch (step.tool) {
    case "inspect_campaign": {
      const inference = result.inference as { mode?: string } | undefined;
      return [
        `origin=${String(result.data_origin ?? "—")}`,
        `rows=${String(result.n_rows ?? "—")}`,
        `observed=${String(result.n_observations ?? "—")}`,
        `batches=${String(result.n_batches ?? "—")}`,
        inference?.mode ? `inference=${inference.mode}` : null,
      ]
        .filter(Boolean)
        .join(" · ");
    }
    case "load_demo_dataset":
      return `${String(result.note || "Loaded demo")} · origin=${String(result.data_origin ?? "—")}`;
    case "propose_config":
      return String(result.summary || "Draft config proposed for review — not saved until save_config.");
    case "save_config":
      return "Config persisted. Ranking still waits for generate_batch.";
    case "generate_batch":
      return [
        String(result.note || "Gaussian-process surrogate, not Nemotron."),
        result.strategy ? `strategy=${String(result.strategy)}` : null,
        Array.isArray(result.rows) ? `${result.rows.length} predicted runs` : null,
      ]
        .filter(Boolean)
        .join(" · ");
    case "get_run_sheet": {
      const runs = result.runs as unknown[] | undefined;
      return `${runs?.length ?? 0} furnace setpoints — measure in the lab, do not invent.`;
    }
    case "plan_robot_motion":
      return [
        "Simulated arm trajectory (not hardware).",
        result.planner ? String(result.planner) : null,
        result.frame_count != null ? `${String(result.frame_count)} frames` : null,
      ]
        .filter(Boolean)
        .join(" · ");
    case "write_pi_brief": {
      const headline = result.headline;
      return headline ? String(headline) : "Grounded PI brief from stored facts.";
    }
    default:
      return null;
  }
}

