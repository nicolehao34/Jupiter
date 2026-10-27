import { useEffect, useState } from "react";
import { BaselineCompare, BudgetBar, ParityChart } from "../components/Charts";
import { api } from "../api";
import { useProject } from "../context";
import type { CampaignReview } from "../types";
import { formatNum } from "../util";

export function Review() {
  const { project, wrap } = useProject();
  const [review, setReview] = useState<CampaignReview | null>(null);

  useEffect(() => {
    if (!project) return;
    void wrap("Loading campaign review…", async () => {
      const next = await api.review(project.id);
      setReview(next);
      return next;
    });
  }, [project, wrap]);

  if (!project) return <p className="hint">Waiting for the shared campaign…</p>;
  if (!review) return <p className="hint">Loading review…</p>;

  const unit = review.unit || "";
  const origin = review.data_origin || "unspecified";

  return (
    <div className="review">
      <section className="card">
        <h2>Campaign review</h2>
        <p className="hint">
          This view does not propose new experiments. It reads the same SQLite campaign the planner
          writes: measured or synthetic-demo rows, budget, and in-sample surrogate residuals.
        </p>
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
            <p className="meta">{review.best_observed?.source || "—"}</p>
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
        </section>
      </div>

      <section className="card" style={{ marginTop: 14 }}>
        <h2>Batch timeline</h2>
        {!review.batches.length && (
          <p className="hint">No recommendation batches yet. Generate one on the Plan tab.</p>
        )}
        <div className="table-wrap" style={{ maxHeight: 360 }}>
          <table>
            <thead>
              <tr>
                <th>When</th>
                <th>Id</th>
                <th>Strategy</th>
                <th>n at fit</th>
                <th>Mean μ</th>
                <th>Mean σ</th>
                <th>EI lift</th>
                <th>Tradeoffs</th>
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
