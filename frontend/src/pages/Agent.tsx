import { useEffect, useMemo, useState } from "react";
import { BaselineCompare } from "../components/Charts";
import { AskPanel } from "../components/Copilot";
import { api } from "../api";
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
  { id: "write_pi_brief", label: "PI brief", note: "Grounded summary from stored facts." },
];

const WORKFLOW_PHASES = [
  { id: "observe", label: "Observe", tools: ["inspect_campaign", "load_demo_dataset"] },
  { id: "plan", label: "Plan", tools: ["propose_config"] },
  { id: "propose", label: "Propose runs", tools: ["generate_batch"] },
  { id: "handoff", label: "Lab handoff", tools: ["get_run_sheet"] },
  { id: "report", label: "Report", tools: ["write_pi_brief"] },
];

const STEP_LABELS: Record<string, string> = {
  inspect_campaign: "Inspect campaign",
  load_demo_dataset: "Load demonstration table",
  propose_config: "Propose config",
  save_config: "Save config",
  generate_batch: "Rank batch (GP + EI)",
  get_run_sheet: "Write furnace run sheet",
  write_pi_brief: "Brief the PI",
};

function stepOf(run: AgentRun, name: string): AgentStep | undefined {
  return run.transcript.find((step) => step.tool === name && step.ok);
}

function phaseStatus(
  phase: (typeof WORKFLOW_PHASES)[number],
  run: AgentRun | null,
  busy: boolean,
): "pending" | "running" | "done" | "error" {
  if (!run) return busy && phase.id === "observe" ? "running" : "pending";
  const tools = phase.tools;
  const steps = run.transcript.filter((s) => s.tool && tools.includes(s.tool));
  if (steps.some((s) => !s.ok)) return "error";
  if (steps.length === tools.length && steps.every((s) => s.ok)) return "done";
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

  useEffect(() => {
    const raw = sessionStorage.getItem("jupiter.lastAgentRun");
    if (!raw) return;
    try {
      setRun(JSON.parse(raw) as AgentRun);
    } catch {
      sessionStorage.removeItem("jupiter.lastAgentRun");
    }
  }, []);

  async function launch() {
    if (!project || busy) return;
    setBusy(true);
    const result = await wrap("Agent is running the campaign…", () => api.runAgent(project.id, goal));
    setBusy(false);
    if (!result) return;
    setRun(result);
    sessionStorage.setItem("jupiter.lastAgentRun", JSON.stringify(result));
    await reload();
  }

  const generate = run ? stepOf(run, "generate_batch") : undefined;
  const sheet = run ? stepOf(run, "get_run_sheet") : undefined;
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
      }[];
      strategy?: string;
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
  const totalSteps = run?.transcript.length ?? WORKFLOW_PHASES.reduce((n, p) => n + p.tools.length, 0);
  const progressPct = run ? Math.round((completedSteps / Math.max(run.transcript.length, 1)) * 100) : busy ? 8 : 0;

  const usedTools = new Set(run?.transcript.filter((s) => s.ok).map((s) => s.tool) || []);

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
            <textarea value={goal} onChange={(event) => setGoal(event.target.value)} />
            <div className="actions">
              <button disabled={!project || busy} onClick={() => void launch()}>
                {busy ? "Running…" : "Run campaign"}
              </button>
              <a className="tab" href="#/plan">
                Human: record results
              </a>
            </div>
            {(busy || run) && (
              <div className="agent-progress">
                <div className="budget-track">
                  <div
                    className={`budget-fill ${run?.transcript.some((s) => !s.ok) ? "error" : ""}`}
                    style={{ width: `${progressPct}%` }}
                  />
                </div>
                <p className="meta">
                  {busy
                    ? "Workflow running…"
                    : `${completedSteps} tool step(s) · ${run?.controller === "live" ? "live Nemotron" : "labeled playbook"}`}
                </p>
              </div>
            )}
          </section>

          <section className="card" style={{ marginTop: 14 }}>
            <h2>Workflow phases</h2>
            <p className="hint">
              Inspired by IvoryOS preparation / experiment / cleanup tabs and AlabOS experiment
              progress — here: observe → plan → propose → lab handoff → report, then a human
              checkpoint.
            </p>
            <ol className="workflow-stepper">
              {WORKFLOW_PHASES.map((phase) => {
                const status = phaseStatus(phase, run, busy);
                return (
                  <li key={phase.id} className={`phase ${status}`}>
                    <span className="phase-dot" aria-hidden />
                    <div>
                      <p className="agent-step-name">{phase.label}</p>
                      <p className="meta">{phase.tools.map((t) => STEP_LABELS[t] || t).join(" · ")}</p>
                    </div>
                  </li>
                );
              })}
              <li className={`phase ${run && !busy ? "done" : "pending"} human`}>
                <span className="phase-dot" aria-hidden />
                <div>
                  <p className="agent-step-name">Human checkpoint</p>
                  <p className="meta">Run the furnace, then type measured capacity on Plan.</p>
                </div>
              </li>
            </ol>
          </section>

          {run && (
            <section className="card checkpoint" style={{ marginTop: 14 }}>
              <h2>Your turn at the bench</h2>
              <p>
                The agent stops before inventing lab data (self-driving-lab dashboards treat this
                as an operator handoff). Export the run sheet, execute the furnaces, then{" "}
                <a href="#/plan">save results on Plan</a> and run the agent again or regenerate
                manually.
              </p>
            </section>
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
                    ? "Labeled playbook — same tools, not a fake live loop"
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
                      {step.error && <p className="meta">{step.error}</p>}
                      {step.ok && step.tool === "generate_batch" && (
                        <p className="meta">
                          {(step.result as { strategy?: string })?.strategy} ·{" "}
                          {((step.result as { rows?: unknown[] })?.rows || []).length} ranked runs
                        </p>
                      )}
                    </div>
                  </li>
                ))}
              </ol>
              <p>{run.final_text}</p>
              <p className="hint">{run.disclaimer}</p>
            </section>
          )}

          {batch?.rows && (
            <section className="card" style={{ marginTop: 14 }}>
              <h2>Proposed experiments</h2>
              <p className="meta">From generate_batch — GP estimates, not Nemotron inventions.</p>
              <BaselineCompare comparison={batch.baseline_comparison} />
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>#</th>
                      {inputs.map((name) => (
                        <th key={name}>{name}</th>
                      ))}
                      <th>Predicted</th>
                      <th>± std</th>
                      <th>EI</th>
                      <th>Tradeoff</th>
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
                  {usedTools.has(tool.id) ? "✓ " : ""}
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
          <p className="meta">Inference: {project?.inference?.mode ?? "—"}</p>
          <p className="meta" style={{ marginTop: 12 }}>
            UI references:{" "}
            <a href="https://huggingface.co/spaces/doncamilom/ChemCrow" target="_blank" rel="noreferrer">
              ChemCrow
            </a>
            ,{" "}
            <a href="https://github.com/jataware/open-coscientist-viewer" target="_blank" rel="noreferrer">
              Open Coscientist Viewer
            </a>
            , AlabOS / IvoryOS lab dashboards (Nat. Commun. 2025).
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
