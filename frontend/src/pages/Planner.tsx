import { useState } from "react";
import { BaselineCompare, Scatter, UncertaintyBars } from "../components/Charts";
import { api } from "../api";
import { useProject } from "../context";
import type { OptimizationConfig } from "../types";
import { formatNum } from "../util";

const DEFAULT_GOAL =
  "Improve first-cycle discharge capacity of a fixed NMC811 cathode by adjusting calcination temperature, hold time, heating rate, and carbon-black loading. Maximize capacity in mAh/g. Stay within typical lab processing ranges.";

export function Planner() {
  const { project, plot, latest, setProject, wrap, refresh, reload } = useProject();
  const [goal, setGoal] = useState(DEFAULT_GOAL);
  const [goalNote, setGoalNote] = useState("");
  const [resultDraft, setResultDraft] = useState({ rank: 1, observed: "", experiment_id: "" });
  const [simRate, setSimRate] = useState(1);
  const [simTemp, setSimTemp] = useState(25);
  const [simOut, setSimOut] = useState<Record<string, unknown> | null>(null);
  const [mpFormula, setMpFormula] = useState("LiNi0.8Mn0.1Co0.1O2");
  const [mpOut, setMpOut] = useState<Record<string, unknown> | null>(null);

  const config = project?.config ?? null;
  const numeric = project?.dataset?.numeric_columns ?? [];

  function updateConfig(patch: Partial<OptimizationConfig>) {
    if (!project?.config) return;
    setProject({ ...project, config: { ...project.config, ...patch } });
  }

  function toggleInput(name: string) {
    if (!project?.config) return;
    const current = project.config.input_variables;
    const next = current.includes(name) ? current.filter((n) => n !== name) : [...current, name];
    const bounds = { ...project.config.bounds };
    const units = { ...project.config.units };
    if (!bounds[name]) bounds[name] = { min: 0, max: 1, unit: units[name] || "" };
    updateConfig({ input_variables: next, bounds, units });
  }

  async function saveAndRecommend() {
    if (!project?.config) return;
    const saved = await wrap("Saving configuration…", () => api.saveConfig(project.id, project.config!));
    if (!saved) return;
    await wrap("Fitting surrogate and ranking a batch…", () => api.recommend(project.id));
    await reload();
  }

  async function proposeFromGoal() {
    if (!project) return;
    const result = await wrap("Asking Nemotron to propose a configuration…", () =>
      api.proposeGoal(project.id, goal, project.dataset?.columns ?? numeric),
    );
    if (!result) return;
    setGoalNote(
      `${result.summary}${result.caveats?.length ? " Caveats: " + result.caveats.join(" ") : ""} [${result.inference?.mode}${result.inference?.latency_ms ? `, ${result.inference.latency_ms} ms` : ""}]`,
    );
    if (result.proposed_config && project.config) {
      setProject({
        ...project,
        config: {
          ...project.config,
          ...result.proposed_config,
          units: { ...project.config.units, ...(result.proposed_config.units || {}) },
          bounds: project.config.bounds,
        },
      });
    }
  }

  async function exportPlan() {
    if (!project) return;
    const blob = await wrap("Exporting CSV…", () => api.exportCsv(project.id));
    if (!blob) return;
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "jupiter-experiment-plan.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  async function addManualResult() {
    if (!project || !latest) return;
    const row = latest.rows.find((r) => r.rank === Number(resultDraft.rank)) || latest.rows[0];
    const observed = Number(resultDraft.observed);
    if (!row || Number.isNaN(observed)) return;
    const next = await wrap("Recording measured result…", () =>
      api.addResults(project.id, [
        {
          parameters: row.parameters,
          observed,
          experiment_id: resultDraft.experiment_id || `MANUAL-${row.rank}`,
        },
      ]),
    );
    if (next) await refresh(next);
  }

  return (
    <div>
      <div className="grid">
        <section className="card">
          <h2>1–2 · Dataset preview & validation</h2>
          <p className="hint">
            Load the labeled demo table or upload a CSV. This MVP uses a few continuous numeric
            inputs and one target metric.
          </p>
          <div className="actions">
            <button
              onClick={() =>
                project && wrap("Loading sample…", async () => refresh(await api.loadSample(project.id)))
              }
            >
              Load demo dataset
            </button>
            <label className="file-btn">
              Upload CSV
              <input
                type="file"
                accept=".csv,text/csv"
                onChange={async (event) => {
                  const file = event.target.files?.[0];
                  if (!file || !project) return;
                  const next = await wrap("Validating upload…", () => api.uploadDataset(project.id, file));
                  if (next) await refresh(next);
                }}
              />
            </label>
          </div>
          {project?.dataset ? (
            <>
              <p className="meta">
                {project.dataset.name} · {project.dataset.n_rows} rows · origin:{" "}
                {project.dataset.data_origin || "unspecified"} · v{project.dataset.version}
              </p>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      {project.dataset.columns.map((col) => (
                        <th key={col}>{col}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {project.dataset.preview_rows.map((row, i) => (
                      <tr key={i}>
                        {project.dataset!.columns.map((col) => (
                          <td key={col} className="mono">
                            {String(row[col] ?? "")}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {project.dataset.issues.map((issue, i) => (
                <p key={i} className={`issue ${issue.severity}`}>
                  [{issue.severity}] {issue.message}
                </p>
              ))}
            </>
          ) : (
            <p className="hint">No dataset loaded yet.</p>
          )}
        </section>

        <section className="card">
          <h2>3–4 · Goal, variables, bounds, budget</h2>
          <div className="field">
            <label>Researcher goal</label>
            <textarea value={goal} onChange={(e) => setGoal(e.target.value)} />
          </div>
          <div className="actions">
            <button className="secondary" onClick={() => void proposeFromGoal()}>
              Propose config with Nemotron
            </button>
          </div>
          {goalNote && <p className="meta">{goalNote}</p>}
          {config && (
            <>
              <div className="checks">
                {numeric.map((name) => (
                  <label key={name}>
                    <input
                      type="checkbox"
                      checked={config.input_variables.includes(name)}
                      onChange={() => toggleInput(name)}
                    />
                    {name}
                  </label>
                ))}
              </div>
              <div className="field-grid">
                <div className="field">
                  <label>Target metric</label>
                  <select
                    value={config.target_metric}
                    onChange={(e) => updateConfig({ target_metric: e.target.value })}
                  >
                    {numeric.map((name) => (
                      <option key={name}>{name}</option>
                    ))}
                  </select>
                </div>
                <div className="field">
                  <label>Direction</label>
                  <select
                    value={config.direction}
                    onChange={(e) =>
                      updateConfig({ direction: e.target.value as OptimizationConfig["direction"] })
                    }
                  >
                    <option value="maximize">Maximize</option>
                    <option value="minimize">Minimize</option>
                  </select>
                </div>
                <div className="field">
                  <label>Target unit</label>
                  <input
                    value={config.units[config.target_metric] || ""}
                    onChange={(e) =>
                      updateConfig({ units: { ...config.units, [config.target_metric]: e.target.value } })
                    }
                  />
                </div>
                <div className="field">
                  <label>Batch size</label>
                  <input
                    type="number"
                    value={config.batch_size}
                    onChange={(e) => updateConfig({ batch_size: Number(e.target.value) })}
                  />
                </div>
                <div className="field">
                  <label>Experiment budget</label>
                  <input
                    type="number"
                    value={config.experiment_budget}
                    onChange={(e) => updateConfig({ experiment_budget: Number(e.target.value) })}
                  />
                </div>
              </div>
              {config.input_variables.map((name) => (
                <div className="field-grid" key={name}>
                  <div className="field">
                    <label>Input</label>
                    <input value={name} readOnly />
                  </div>
                  <div className="field">
                    <label>Unit</label>
                    <input
                      value={config.units[name] || ""}
                      onChange={(e) =>
                        updateConfig({ units: { ...config.units, [name]: e.target.value } })
                      }
                    />
                  </div>
                  <div className="field">
                    <label>Min</label>
                    <input
                      type="number"
                      value={config.bounds[name]?.min ?? 0}
                      onChange={(e) =>
                        updateConfig({
                          bounds: {
                            ...config.bounds,
                            [name]: { ...config.bounds[name], min: Number(e.target.value) },
                          },
                        })
                      }
                    />
                  </div>
                  <div className="field">
                    <label>Max</label>
                    <input
                      type="number"
                      value={config.bounds[name]?.max ?? 1}
                      onChange={(e) =>
                        updateConfig({
                          bounds: {
                            ...config.bounds,
                            [name]: { ...config.bounds[name], max: Number(e.target.value) },
                          },
                        })
                      }
                    />
                  </div>
                  <div className="field">
                    <label> </label>
                    <span className="meta">continuous</span>
                  </div>
                </div>
              ))}
              <div className="actions">
                <button onClick={() => void saveAndRecommend()}>5 · Generate ranked batch</button>
              </div>
            </>
          )}
        </section>
      </div>

      <div className="grid-3">
        <section className="card">
          <h2>6 · Recommended experiments</h2>
          {latest ? (
            <>
              <p className="meta">
                Strategy: {latest.strategy} · n={latest.n_observed} · remaining budget{" "}
                {latest.remaining_budget}
              </p>
              {latest.inference && (
                <p
                  className={`status ${latest.inference.mode === "live" ? "ok" : latest.inference.mode === "failed" || latest.inference.mode === "unconfigured" ? "error" : "loading"}`}
                >
                  Inference: {latest.inference.mode}
                  {latest.inference.model ? ` · ${latest.inference.model}` : ""}
                  {latest.inference.error ? ` · ${latest.inference.error}` : ""}
                </p>
              )}
              {latest.numerical_change && <p className="meta">{latest.numerical_change}</p>}
              <BaselineCompare comparison={latest.baseline_comparison} />
              <div className="table-wrap" style={{ maxHeight: 420 }}>
                <table>
                  <thead>
                    <tr>
                      <th>#</th>
                      {config?.input_variables.map((name) => (
                        <th key={name}>{name}</th>
                      ))}
                      <th>Predicted</th>
                      <th>± std</th>
                      <th>EI</th>
                      <th>Tradeoff</th>
                    </tr>
                  </thead>
                  <tbody>
                    {latest.rows.map((row) => (
                      <tr key={row.rank}>
                        <td>{row.rank}</td>
                        {config?.input_variables.map((name) => (
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
              <p className="meta">{latest.rows[0]?.uncertainty_label}</p>
              <div className="actions">
                <button className="secondary" onClick={() => void exportPlan()}>
                  7 · Export plan CSV
                </button>
              </div>
            </>
          ) : (
            <p className="hint">Generate a batch to see predicted performance and uncertainty.</p>
          )}
        </section>
        <section className="card">
          <h2>Observed vs predicted</h2>
          <Scatter plot={plot} />
          <UncertaintyBars latest={latest} unit={config?.units[config.target_metric] || ""} />
        </section>
      </div>

      <section className="card" style={{ marginTop: 14 }}>
        <h2>8 · Record results and regenerate</h2>
        <div className="field-grid">
          <div className="field">
            <label>Rank</label>
            <input
              type="number"
              value={resultDraft.rank}
              onChange={(e) => setResultDraft({ ...resultDraft, rank: Number(e.target.value) })}
            />
          </div>
          <div className="field">
            <label>Observed {config?.target_metric || "target"}</label>
            <input
              value={resultDraft.observed}
              onChange={(e) => setResultDraft({ ...resultDraft, observed: e.target.value })}
            />
          </div>
          <div className="field">
            <label>Experiment id</label>
            <input
              value={resultDraft.experiment_id}
              onChange={(e) => setResultDraft({ ...resultDraft, experiment_id: e.target.value })}
            />
          </div>
          <div className="field">
            <label> </label>
            <button onClick={() => void addManualResult()}>Save result</button>
          </div>
          <div className="field">
            <label> </label>
            <label className="file-btn">
              Upload results CSV
              <input
                type="file"
                accept=".csv,text/csv"
                onChange={async (event) => {
                  const file = event.target.files?.[0];
                  if (!file || !project) return;
                  const next = await wrap("Appending results…", () => api.uploadResults(project.id, file));
                  if (next) await refresh(next);
                }}
              />
            </label>
          </div>
        </div>
        <div className="actions">
          <button onClick={() => void saveAndRecommend()}>Regenerate recommendations</button>
        </div>
        <div className="optional">
          <details>
            <summary>Optional: PyBaMM / Materials Project</summary>
            <div className="row">
              <div className="field" style={{ width: 120 }}>
                <label>C-rate</label>
                <input type="number" value={simRate} onChange={(e) => setSimRate(Number(e.target.value))} />
              </div>
              <div className="field" style={{ width: 120 }}>
                <label>°C</label>
                <input type="number" value={simTemp} onChange={(e) => setSimTemp(Number(e.target.value))} />
              </div>
              <button
                className="secondary"
                onClick={async () => {
                  const out = await wrap("Running PyBaMM…", () => api.simulate(simRate, simTemp));
                  if (out) setSimOut(out);
                }}
              >
                Simulate cell
              </button>
              <input value={mpFormula} onChange={(e) => setMpFormula(e.target.value)} />
              <button
                className="secondary"
                onClick={async () => {
                  const out = await wrap("MP lookup…", () => api.materialsLookup(mpFormula));
                  if (out) setMpOut(out);
                }}
              >
                MP lookup
              </button>
            </div>
            {simOut && <pre className="meta">{JSON.stringify(simOut, null, 2)}</pre>}
            {mpOut && <pre className="meta">{JSON.stringify(mpOut, null, 2)}</pre>}
          </details>
        </div>
      </section>
    </div>
  );
}
