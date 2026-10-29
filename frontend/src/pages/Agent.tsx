import { useEffect, useMemo, useState } from "react";
import { BaselineCompare } from "../components/Charts";
import {
  BudgetProgress,
  DataOriginLegend,
  NextActionCard,
  OriginChip,
} from "../components/CampaignStatus";
import { AskPanel } from "../components/Copilot";
import { RobotMotionSim, type RobotMotionPlan } from "../components/RobotMotionSim";
import { api } from "../api";
import {
  inferenceHeadline,
  normalizePlanSteps,
  planStepStatusText,
  stopReasonLabel,
  toolProvenance,
} from "../campaign";
import { useProject } from "../context";
import type { AgentRun, AgentStep, BaselineComparison, CampaignBrief } from "../types";
import { formatNum } from "../util";

const DEFAULT_GOAL =
  "Load the NMC811 demo if needed, rank the next calcination and slurry batch to maximize discharge capacity, produce a furnace run sheet, and brief the PI. Do not invent lab results.";

/** Mirrors public agent UIs: ChemCrow tool sidebar, Coscientist/Open Coscientist workflow, AlabOS task status. */
const AVAILABLE_TOOLS = [
  { id: "inspect_campaign", label: "Inspect campaign", note: "Read SQLite state, budget, batches." },
  { id: "load_demo_dataset", label: "Load demo table", note: "Labeled synthetic NMC811 if empty." },
  { id: "propose_config", label: "Propose config", note: "Nemotron drafts a reviewable goal→columns map." },
  { id: "generate_batch", label: "Rank batch", note: "GP + EI only — not the LLM." },
  { id: "get_run_sheet", label: "Furnace run sheet", note: "Setpoints + what to measure." },
  {
    id: "plan_robot_motion",
    label: "Simulated arm motion",
    note: "RRT-Connect-style bench plan + IK playback (not hardware).",
  },
  { id: "write_pi_brief", label: "PI brief", note: "Grounded summary from stored facts." },
];

const WORKFLOW_PHASES = [
  { id: "observe", label: "Observe", tools: ["inspect_campaign", "load_demo_dataset"] },
  { id: "configure", label: "Plan", tools: ["propose_config", "save_config"] },
  { id: "rank", label: "Propose runs", tools: ["generate_batch"] },
  { id: "handoff", label: "Lab handoff", tools: ["get_run_sheet", "plan_robot_motion"] },
  { id: "checkpoint", label: "Human checkpoint", tools: [] as string[] },
];

const STEP_LABELS: Record<string, string> = {
  inspect_campaign: "Inspect campaign",
  load_demo_dataset: "Load demonstration table",
  propose_config: "Propose config",
  save_config: "Save config",
  generate_batch: "Rank batch (GP + EI)",
  get_run_sheet: "Write furnace run sheet",
  plan_robot_motion: "Plan simulated arm motion",
  write_pi_brief: "Brief the PI",
};

function stepOf(run: AgentRun, name: string): AgentStep | undefined {
  return [...run.transcript].reverse().find((step) => step.tool === name && step.ok);
}

function phaseStatus(
  phase: (typeof WORKFLOW_PHASES)[number],
  run: AgentRun | null,
  busy: boolean,
): "pending" | "running" | "done" | "error" {
  if (phase.id === "checkpoint") {
    if (run?.stop_reason === "awaiting_lab_results") return "running";
    if (run?.stop_reason === "human_checkpoint" && !busy) return "done";
    return "pending";
  }
  if (!run) return busy && phase.id === "observe" ? "running" : "pending";
  const tools = phase.tools;
  const steps = run.transcript.filter((s) => s.tool && tools.includes(s.tool));
  if (steps.some((s) => !s.ok)) return "error";
  if (steps.length >= tools.length && tools.every((t) => steps.some((s) => s.tool === t && s.ok))) {
    return "done";
  }
  const anyDone = steps.some((s) => s.ok);
  const last = run.transcript[run.transcript.length - 1];
  if (busy && last?.tool && tools.includes(last.tool)) return "running";
  return anyDone ? "running" : "pending";
}

export function Agent() {
  const { project, latest, wrap, reload } = useProject();
  const [goal, setGoal] = useState(DEFAULT_GOAL);
  const [run, setRun] = useState<AgentRun | null>(null);
  const [busy, setBusy] = useState(false);
  const [liveHint, setLiveHint] = useState<string | null>(null);

  useEffect(() => {
    if (!project) return;
    void (async () => {
      try {
        const stored = await api.getAgentSession(project.id);
        if (stored.live_enable_hint) setLiveHint(stored.live_enable_hint);
        if (!stored.session?.transcript_length) return;
        if (stored.goal_text) setGoal(stored.goal_text);
        setRun({
          controller: (stored.session.controller as AgentRun["controller"]) || "playbook",
          goal_text: stored.goal_text || DEFAULT_GOAL,
          turn: stored.session.turn,
          phase: stored.session.phase || undefined,
          stop_reason: stored.session.stop_reason || undefined,
          can_continue: stored.session.can_continue,
          running_plan: stored.session.running_plan,
          inference: null,
          transcript: stored.transcript,
          final_text: "",
          disclaimer:
            "The agent does not record lab results. Ranking came from generate_batch (GP + EI), not Nemotron.",
          live_enable_hint: stored.live_enable_hint,
        });
      } catch {
        /* no session yet */
      }
    })();
  }, [project?.id]);

  async function launch(resetSession: boolean) {
    if (!project || busy) return;
    setBusy(true);
    const result = await wrap("Agent is running the campaign…", () =>
      api.runAgent(project.id, goal, { resetSession }),
    );
    setBusy(false);
    if (!result) return;
    setRun(result);
    if (result.live_enable_hint) setLiveHint(result.live_enable_hint);
    await reload();
  }

  async function continueCampaign() {
    if (!project || busy) return;
    setBusy(true);
    const result = await wrap("Agent continuing the campaign…", () =>
      api.runAgent(project.id, goal, { continueCampaign: true }),
    );
    setBusy(false);
    if (!result) return;
    setRun(result);
    if (result.live_enable_hint) setLiveHint(result.live_enable_hint);
    await reload();
  }

  const generate = run ? stepOf(run, "generate_batch") : undefined;
  const sheet = run ? stepOf(run, "get_run_sheet") : undefined;
  const robotStep = run ? stepOf(run, "plan_robot_motion") : undefined;
  const robotPlan = robotStep?.result as RobotMotionPlan | undefined;
  const briefStep = run ? stepOf(run, "write_pi_brief") : undefined;
  const batch =
    (generate?.result as {
      rows?: {
        rank: number;
        parameters: Record<string, number>;
        predicted_mean: number | null;
        predicted_std: number | null;
        acquisition: number;
        tradeoff: string;
        source?: string;
        explanation?: string;
      }[];
      strategy?: string;
      warnings?: string[];
      note?: string;
      baseline_comparison?: BaselineComparison;
    }) || undefined;
  const runs =
    (sheet?.result as {
      runs?: { run: number; setpoints: Record<string, number>; setpoint_units: Record<string, string>; record_back: string }[];
      instructions?: string;
    }) || undefined;
  const brief = briefStep?.result as CampaignBrief | undefined;
  const inputs = useMemo(
    () => Object.keys(batch?.rows?.[0]?.parameters || latest?.rows?.[0]?.parameters || {}),
    [batch, latest],
  );

  const completedSteps = run?.transcript.filter((s) => s.ok).length ?? 0;
  const progressPct = run ? Math.round((completedSteps / Math.max(run.transcript.length, 1)) * 100) : busy ? 8 : 0;
  const usedTools = new Set(run?.transcript.filter((s) => s.ok).map((s) => s.tool) || []);
  const failedStep = run?.transcript.find((s) => !s.ok);
  const planSteps = normalizePlanSteps(
    run?.running_plan?.length
      ? run.running_plan.map((step) => ({
          id: step.id,
          label: step.label,
          status: step.status,
        }))
      : WORKFLOW_PHASES.map((phase) => ({
          id: phase.id,
          label: phase.label,
          status: phaseStatus(phase, run, busy),
        })),
    run?.stop_reason,
  );

  return (
    <div className="agent-page">
      <div className="agent-grid">
        <div className="agent-main">
          <section className="card agent-hero">
            <h2>Campaign agent</h2>
            <p className="hint">
              Goal in, tool loop out — like ChemCrow’s tool-augmented agent and Coscientist’s
              planner, but scoped to battery <em>processing</em> campaigns. Ranking stays a
              Gaussian process; Nemotron selects tools and explains stored facts only.
            </p>
            <div className="field">
              <label htmlFor="agent-goal">Campaign goal</label>
              <textarea
                id="agent-goal"
                value={goal}
                onChange={(event) => setGoal(event.target.value)}
              />
            </div>
            <div className="actions">
              <button disabled={!project || busy} onClick={() => void launch(true)}>
                {busy ? "Running…" : "Run campaign"}
              </button>
              <button
                className="secondary"
                disabled={!project || busy || !run?.can_continue}
                onClick={() => void continueCampaign()}
              >
                Continue campaign
              </button>
              <a className="tab" href="#/plan">
                Human: record results
              </a>
            </div>
            {run?.stop_reason && !busy && (
              <p className="meta stop-reason">
                <strong>Stop reason:</strong> {stopReasonLabel(run.stop_reason)}
                {run.turn != null ? ` · Turn ${run.turn}` : ""}
              </p>
            )}
            {liveHint && project?.inference?.mode !== "live" && (
              <p className="hint live-enable-hint">{liveHint}</p>
            )}
            {(busy || run) && (
              <BudgetProgress
                used={progressPct}
                total={100}
                errored={Boolean(failedStep)}
                label={
                  busy
                    ? "Workflow running"
                    : `${completedSteps} tool step(s) · ${run?.controller === "live" ? "live Nemotron" : "labeled playbook"}`
                }
              />
            )}
          </section>

          <section className="card" style={{ marginTop: 14 }}>
            <h2>Campaign progress</h2>
            <p className="hint">
              One plan, updated from tool outcomes (Open Coscientist / IvoryOS). The last step is a
              human checkpoint — AlabOS-style operator handoff, not a finished measurement.
            </p>
            <ol className="workflow-stepper">
              {planSteps.map((step) => {
                const statusText = planStepStatusText(step.status, step.id, run?.stop_reason);
                return (
                  <li key={step.id} className={`phase ${step.status}${step.id === "checkpoint" ? " human" : ""}`}>
                    <span className="phase-dot" aria-hidden />
                    <div>
                      <p className="agent-step-name">{step.label}</p>
                      <p className="meta">
                        <span className="visually-hidden">Status: </span>
                        {statusText}
                      </p>
                    </div>
                  </li>
                );
              })}
            </ol>
          </section>

          {(busy || run) && (
            <div style={{ marginTop: 14 }}>
              <NextActionCard busy={busy} run={run} />
            </div>
          )}

          {run && (
            <section className="card" style={{ marginTop: 14 }}>
              <h2>Agent activity</h2>
              <p
                className={`meta infer ${run.controller === "live" ? "live" : run.controller === "failed" ? "failed" : "offline_demo"}`}
              >
                {run.controller === "live"
                  ? "Live Token Factory tool loop"
                  : run.controller === "playbook"
                    ? project?.inference?.mode === "offline_demo"
                      ? "Offline demo — labeled playbook, not live Nemotron"
                      : "Unconfigured playbook — stateful tool loop, not fake live"
                    : "Agent failed"}
                {run.inference?.model ? ` · ${run.inference.model}` : ""}
                {run.inference?.latency_ms != null ? ` · ${run.inference.latency_ms} ms` : ""}
              </p>
              <ol className="agent-timeline">
                {run.transcript.map((step, index) => (
                  <li key={`${step.tool}-${index}`} className={step.ok ? "ok" : "bad"}>
                    <span className={`chip ${step.ok ? "balanced" : "exploit"}`}>
                      {step.ok ? "done" : "stop"}
                    </span>
                    <div>
                      <p className="agent-step-name">{STEP_LABELS[step.tool || ""] || step.tool || "stop"}</p>
                      <p className="meta">{toolProvenance(step)}</p>
                    </div>
                  </li>
                ))}
              </ol>
              {failedStep && (
                <div className="status error" role="alert">
                  Recoverable error at {STEP_LABELS[failedStep.tool || ""] || failedStep.tool}:{" "}
                  {failedStep.error}. Fix the campaign on Plan if needed, then run again — do not
                  invent a workaround.
                </div>
              )}
              {run.final_text && <p>{run.final_text}</p>}
              <p className="hint">{run.disclaimer}</p>
            </section>
          )}

          {batch?.rows && (
            <section className="card" style={{ marginTop: 14 }}>
              <h2>Proposed experiments</h2>
              <p className="meta">
                From generate_batch — {batch.note || "GP estimates, not Nemotron inventions."}
              </p>
              <DataOriginLegend extra="These rows are predicted until you type a furnace measurement on Plan." />
              <BaselineCompare comparison={batch.baseline_comparison} />
              {(batch.warnings || []).map((warning) => (
                <p key={warning} className="issue warning">
                  {warning}
                </p>
              ))}
              <div className="table-wrap">
                <table>
                  <caption className="visually-hidden">
                    Ranked processing runs with predicted capacity from the Gaussian process
                  </caption>
                  <thead>
                    <tr>
                      <th scope="col">#</th>
                      {inputs.map((name) => (
                        <th scope="col" key={name}>
                          {name}
                        </th>
                      ))}
                      <th scope="col">Predicted</th>
                      <th scope="col">± std</th>
                      <th scope="col">EI</th>
                      <th scope="col">Tradeoff</th>
                      <th scope="col">Origin</th>
                    </tr>
                  </thead>
                  <tbody>
                    {batch.rows.map((row) => (
                      <tr key={row.rank}>
                        <td>{row.rank}</td>
                        {inputs.map((name) => (
                          <td key={name} className="mono">
                            {formatNum(row.parameters[name], 3)}
                          </td>
                        ))}
                        <td className="mono">{formatNum(row.predicted_mean, 2)}</td>
                        <td className="mono">{formatNum(row.predicted_std, 2)}</td>
                        <td className="mono">{formatNum(row.acquisition, 4)}</td>
                        <td>
                          <span className={`chip ${row.tradeoff}`}>{row.tradeoff}</span>
                        </td>
                        <td>
                          <OriginChip kind={row.source || "surrogate_prediction"} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          {runs?.runs && (
            <section className="card" style={{ marginTop: 14 }}>
              <h2>Furnace run sheet</h2>
              <p className="hint">{runs.instructions}</p>
              <ol className="run-sheet">
                {runs.runs.map((item) => (
                  <li key={item.run}>
                    <span className="mono">
                      {Object.entries(item.setpoints)
                        .map(
                          ([name, value]) =>
                            `${name}=${formatNum(value, 3)} ${item.setpoint_units?.[name] || ""}`.trim(),
                        )
                        .join(" · ")}
                    </span>
                    <p className="meta">{item.record_back}</p>
                  </li>
                ))}
              </ol>
            </section>
          )}

          {robotPlan?.frames?.length ? (
            <section className="card robot-handoff" style={{ marginTop: 14 }}>
              <h2>Simulated bench robot motion</h2>
              <p className="hint">
                Task-and-motion style playback for crucible pick, furnace insert, and slurry handoff —{" "}
                <strong>simulation only</strong>, inspired by self-driving lab arms (see{" "}
                <a href="https://github.com/nicolehao34/Jupiter/blob/main/docs/robot-lab-simulation.md" target="_blank" rel="noreferrer">
                  robot-lab-simulation.md
                </a>
                ). The agent stops here for a human to run furnaces and type results on Plan.
              </p>
              <RobotMotionSim plan={robotPlan} autoPlay={!busy} />
            </section>
          ) : null}

          {brief && (
            <section className="card" style={{ marginTop: 14 }}>
              <h2>PI brief</h2>
              <p>{brief.headline}</p>
              <ul>
                {(brief.bullets || []).map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </section>
          )}

          <div style={{ marginTop: 14 }}>
            <AskPanel />
          </div>
        </div>

        <aside className="card agent-rail">
          <h2>Tools</h2>
          <p className="hint">ChemCrow-style capability list — the model picks from these; GP ranks.</p>
          <ul className="tool-list">
            {AVAILABLE_TOOLS.map((tool) => (
              <li key={tool.id} className={usedTools.has(tool.id) ? "used" : ""}>
                <p className="agent-step-name">
                  {usedTools.has(tool.id) ? "Used · " : "Available · "}
                  {tool.label}
                </p>
                <p className="meta">{tool.note}</p>
              </li>
            ))}
          </ul>
          <h3 className="meta" style={{ marginTop: 16, textTransform: "uppercase", letterSpacing: "0.04em" }}>
            Campaign snapshot
          </h3>
          <p className="meta">Observed: {project?.observations?.length ?? "—"}</p>
          <p className="meta">Batches: {project?.batches?.length ?? "—"}</p>
          <p className="meta">
            Inference: {inferenceHeadline(project?.inference?.mode)} ({project?.inference?.mode ?? "—"})
          </p>
          <p className="meta">
            Dataset origin: {project?.dataset?.data_origin || "unspecified"}
          </p>
          {project?.agent_session?.phase && (
            <p className="meta">Session: {stopReasonLabel(project.agent_session.stop_reason)}</p>
          )}
          <p className="meta" style={{ marginTop: 12 }}>
            UI references:{" "}
            <a href="https://huggingface.co/spaces/doncamilom/ChemCrow" target="_blank" rel="noreferrer">
              ChemCrow
            </a>
            ,{" "}
            <a href="https://github.com/jataware/open-coscientist-viewer" target="_blank" rel="noreferrer">
              Open Coscientist Viewer
            </a>
            ,{" "}
            <a href="https://platform.futurehouse.org" target="_blank" rel="noreferrer">
              FutureHouse
            </a>
            , AlabOS / IvoryOS lab dashboards.
          </p>
          <p className="meta">
            Deep dive:{" "}
            <a
              href="https://github.com/nicolehao34/Jupiter/blob/main/docs/agent-ui-references.md"
              target="_blank"
              rel="noreferrer"
            >
              agent UI references (repo doc)
            </a>
          </p>
        </aside>
      </div>
    </div>
  );
}
