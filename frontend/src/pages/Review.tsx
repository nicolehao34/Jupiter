import { useEffect, useState } from "react";
import { BaselineCompare, BudgetBar, ParityChart } from "../components/Charts";
import { DataOriginLegend, OriginChip } from "../components/CampaignStatus";
import { api } from "../api";
import { useProject } from "../context";
import type { CampaignBrief, CampaignReview } from "../types";
import { formatNum } from "../util";

export function Review() {
  const { project, wrap } = useProject();
  const [review, setReview] = useState<CampaignReview | null>(null);
  const [brief, setBrief] = useState<CampaignBrief | null>(null);
  const [briefError, setBriefError] = useState<string | null>(null);

  useEffect(() => {
    if (!project) return;
    void wrap("Loading campaign review…", async () => {
      const next = await api.review(project.id);
      setReview(next);
      try {
        setBrief(await api.brief(project.id));
        setBriefError(null);
      } catch (err) {
        setBrief(null);
        setBriefError(err instanceof Error ? err.message : String(err));
      }
      return next;
    });
  }, [project, wrap]);

  if (!project) return <p className="hint">Waiting for the shared campaign…</p>;
  if (!review) return <p className="hint">Loading review…</p>;

  const unit = review.unit || "";
  const origin = review.data_origin || "unspecified";

  return (
    <div className="review">
      {review.audience && (
        <section className="card impact">
          <h2>Who this is for</h2>
          <p>
            <strong>Audience.</strong> {review.audience.who}
          </p>
          <p>
            <strong>Job.</strong> {review.audience.job}
          </p>
          <p>
            <strong>Intended benefit.</strong> {review.audience.intended_benefit}
          </p>
          <p className="hint">{review.audience.not_claimed}</p>
        </section>
      )}

      {brief && (
        <section className="card">
          <h2>PI brief (Nemotron)</h2>
          <p className="hint">
            Grounded Token Factory call: restates stored best/budget/EI lift and the next run sheet.
            It does not invent predictions or lab savings.
          </p>
          <p>{brief.headline}</p>
          <ul className="run-sheet">
            {brief.bullets.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          <p className={`meta infer ${brief.inference.mode}`}>
            {brief.inference.mode}
            {brief.inference.model ? ` · ${brief.inference.model}` : ""}
            {brief.inference.latency_ms != null ? ` · ${brief.inference.latency_ms} ms` : ""}
            {brief.inference.error ? ` · ${brief.inference.error}` : ""}
            {brief.inference.note ? ` · ${brief.inference.note}` : ""}
          </p>
        </section>
      )}

      {!brief && (
        <section className="card">
          <h2>PI brief</h2>
          {briefError ? (
            <p className="issue warning" role="status">
              Brief unavailable: {briefError}. Ranking and residuals below still come from stored
              campaign facts, not from a fabricated summary.
            </p>
          ) : (
            <p className="hint">
              No brief yet. Generate a batch on Plan or run the agent, then reload Review.
            </p>
          )}
          {review.n_batches === 0 && (
            <div className="actions">
              <a className="tab active" href="#/agent">
                Run campaign
              </a>
              <a className="tab" href="#/plan">
                Generate on Plan
              </a>
            </div>
          )}
        </section>
      )}

      <section className="card">
        <h2>Campaign review</h2>
        <p className="hint">
          This view does not propose new experiments. It reads the same SQLite campaign the planner
          writes: measured or synthetic-demo rows, budget, and in-sample surrogate residuals.
        </p>
        <DataOriginLegend extra={`Dataset origin: ${origin}.`} />
        <div className="stat-grid">
          <article>
            <p className="meta">Observed rows</p>
            <p className="stat">{review.n_observed}</p>
          </article>
          <article>
            <p className="meta">Batches proposed</p>
            <p className="stat">{review.n_batches}</p>
          </article>
          <article>
            <p className="meta">Best {review.target || "target"}</p>
            <p className="stat">
              {formatNum(review.best_observed?.observed, 2)} {unit}
            </p>
            <p className="meta">
              {review.best_observed ? <OriginChip kind={review.best_observed.source} /> : "—"}
            </p>
          </article>
          <article>
            <p className="meta">In-sample RMSE</p>
            <p className="stat">{formatNum(review.rmse, 2)}</p>
          </article>
        </div>
        <BudgetBar used={review.budget.used} total={review.budget.total} />
        {review.batches[0]?.baseline_comparison && (
          <div style={{ marginTop: 12 }}>
            <h3 className="meta" style={{ textTransform: "uppercase", letterSpacing: "0.04em" }}>
              Latest batch vs space-filling baseline
            </h3>
            <BaselineCompare comparison={review.batches[0].baseline_comparison} />
          </div>
        )}
        <p className="meta">
          Origin: {origin}. Direction: {review.direction}.{" "}
          {origin === "synthetic_demonstration"
            ? "These rows are demonstration data, not lab measurements."
            : "Treat newly entered rows as measured unless labeled otherwise."}
        </p>
      </section>

      <div className="grid-3">
        <section className="card">
          <h2>Observed vs predicted (in-sample)</h2>
          <p className="hint">{review.residual_note}</p>
          <ParityChart review={review} />
          {review.parity.length > 0 && (
            <div className="table-wrap" style={{ maxHeight: 220, marginTop: 10 }}>
              <table>
                <caption className="visually-hidden">In-sample observed versus predicted values</caption>
                <thead>
                  <tr>
                    <th scope="col">Observed</th>
                    <th scope="col">Predicted</th>
                    <th scope="col">Residual</th>
                  </tr>
                </thead>
                <tbody>
                  {review.parity.slice(0, 12).map((point, index) => (
                    <tr key={index}>
                      <td className="mono">{formatNum(point.observed, 2)}</td>
                      <td className="mono">{formatNum(point.predicted_mean, 2)}</td>
                      <td className="mono">{formatNum(point.residual, 2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
        <section className="card">
          <h2>Best / worst observed</h2>
          <p className="meta">Best</p>
          <p className="mono">
            {review.best_observed
              ? `${formatNum(review.best_observed.observed, 3)} ${unit} · ${Object.entries(
                  review.best_observed.parameters,
                )
                  .map(([k, v]) => `${k}=${v}`)
                  .join(", ")}`
              : "—"}
          </p>
          {review.best_observed && <OriginChip kind={review.best_observed.source} />}
          <p className="meta" style={{ marginTop: 10 }}>
            Worst
          </p>
          <p className="mono">
            {review.worst_observed
              ? `${formatNum(review.worst_observed.observed, 3)} ${unit} · ${Object.entries(
                  review.worst_observed.parameters,
                )
                  .map(([k, v]) => `${k}=${v}`)
                  .join(", ")}`
              : "—"}
          </p>
          {review.worst_observed && <OriginChip kind={review.worst_observed.source} />}
        </section>
      </div>

      {review.run_sheet && (
        <section className="card" style={{ marginTop: 14 }}>
          <h2>{review.run_sheet.title}</h2>
          <p className="hint">{review.run_sheet.instructions}</p>
          <ol className="run-sheet">
            {review.run_sheet.runs.map((run) => (
              <li key={run.run}>
                <span className="mono">
                  {Object.entries(run.setpoints)
                    .map(
                      ([name, value]) =>
                        `${name}=${formatNum(value, 3)} ${run.setpoint_units[name] || ""}`.trim(),
                    )
                    .join(" · ")}
                </span>
                <p className="meta">
                  Measure {run.measure} ({run.unit}). {run.record_back}
                </p>
              </li>
            ))}
          </ol>
        </section>
      )}

      <section className="card" style={{ marginTop: 14 }}>
        <h2>Batch timeline</h2>
        {!review.batches.length && (
          <p className="hint">
            No recommendation batches yet.{" "}
            <a href="#/plan">Generate one on Plan</a> or <a href="#/agent">run the agent</a>.
          </p>
        )}
        <div className="table-wrap" style={{ maxHeight: 360 }}>
          <table>
            <caption className="visually-hidden">Recommendation batches in this campaign</caption>
            <thead>
              <tr>
                <th scope="col">When</th>
                <th scope="col">Id</th>
                <th scope="col">Strategy</th>
                <th scope="col">n at fit</th>
                <th scope="col">Mean μ</th>
                <th scope="col">Mean σ</th>
                <th scope="col">EI lift</th>
                <th scope="col">Tradeoffs</th>
              </tr>
            </thead>
            <tbody>
              {review.batches.map((batch) => (
                <tr key={batch.id}>
                  <td className="mono">{(batch.created_at || "").replace("T", " ").slice(0, 19)}</td>
                  <td className="mono">{batch.id}</td>
                  <td>
                    <span className="chip balanced">{batch.strategy}</span>
                  </td>
                  <td>{batch.n_observed_at_fit ?? "—"}</td>
                  <td className="mono">{formatNum(batch.mean_prediction, 2)}</td>
                  <td className="mono">{formatNum(batch.mean_std, 2)}</td>
                  <td className="mono">
                    {batch.baseline_comparison?.applicable
                      ? formatNum(batch.baseline_comparison.ei_lift, 4)
                      : "—"}
                  </td>
                  <td>{batch.tradeoffs.join(", ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
