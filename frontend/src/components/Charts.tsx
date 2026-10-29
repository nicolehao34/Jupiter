import { useMemo } from "react";
import type { BaselineComparison, CampaignReview, PlotData, RecommendResponse } from "../types";
import { formatNum } from "../util";

export function Scatter({ plot }: { plot: PlotData | null }) {
  const { xs, ys, kinds } = useMemo(() => {
    const pts = plot?.points || [];
    const observed = pts.filter((p) => p.observed != null);
    return {
      xs: observed.map((_, i) => i + 1),
      ys: observed.map((p) => p.observed as number),
      kinds: observed.map((p) => p.kind),
    };
  }, [plot]);
  const preds = (plot?.points || []).filter((p) => p.predicted_mean != null);
  const allY = [...ys, ...preds.map((p) => p.predicted_mean as number)];
  const minY = allY.length ? Math.min(...allY) : 0;
  const maxY = allY.length ? Math.max(...allY) : 1;
  const pad = (maxY - minY) * 0.12 || 1;
  const y0 = minY - pad;
  const y1 = maxY + pad;
  const w = 640;
  const h = 220;
  const left = 44;
  const mapX = (i: number, n: number) => left + ((w - 60) * (i - 1)) / Math.max(n - 1, 1);
  const mapY = (y: number) => 16 + ((h - 36) * (y1 - y)) / (y1 - y0 || 1);
  return (
    <svg className="chart" viewBox={`0 0 ${w} ${h}`} role="img" aria-labelledby="scatter-title">
      <title id="scatter-title">
        Index plot of {plot?.target || "target"}: loaded measurements and GP predictions with uncertainty
      </title>
      <text x="8" y="14" fontSize="10" fill="#5c6b7a">
        {plot?.target || "target"}
      </text>
      {xs.map((x, i) => (
        <circle
          key={i}
          cx={mapX(x, Math.max(xs.length, preds.length + xs.length))}
          cy={mapY(ys[i])}
          r={4}
          fill={kinds[i] === "synthetic_demonstration" ? "#6b5b95" : "#1d4e89"}
        />
      ))}
      {preds.map((p, i) => {
        const x = mapX(xs.length + i + 1, Math.max(xs.length + preds.length, 2));
        const y = mapY(p.predicted_mean as number);
        const std = p.predicted_std || 0;
        return (
          <g key={`p${i}`}>
            <line
              x1={x}
              x2={x}
              y1={mapY((p.predicted_mean as number) - std)}
              y2={mapY((p.predicted_mean as number) + std)}
              stroke="#c45c26"
            />
            <circle cx={x} cy={y} r={4} fill="#c45c26" />
          </g>
        );
      })}
      {!xs.length && !preds.length && (
        <text x={left} y={h / 2} fontSize="12" fill="#5c6b7a">
          Load data to plot observations.
        </text>
      )}
      <text x={left} y={h - 6} fontSize="10" fill="#5c6b7a">
        index (loaded points left, new predictions right)
      </text>
    </svg>
  );
}

export function UncertaintyBars({ latest, unit }: { latest: RecommendResponse | null; unit: string }) {
  if (!latest?.rows.length) return null;
  const rows = latest.rows;
  const max = Math.max(...rows.map((r) => (r.predicted_mean || 0) + (r.predicted_std || 0)), 1);
  const min = Math.min(...rows.map((r) => (r.predicted_mean || 0) - (r.predicted_std || 0)), 0);
  const span = max - min || 1;
  return (
    <div style={{ marginTop: 10 }}>
      {rows.map((row) => {
        const mu = row.predicted_mean ?? 0;
        const std = row.predicted_std ?? 0;
        const left = ((mu - std - min) / span) * 100;
        const width = ((2 * std) / span) * 100;
        const mid = ((mu - min) / span) * 100;
        return (
          <div
            key={row.rank}
            style={{
              display: "grid",
              gridTemplateColumns: "28px 1fr 90px",
              gap: 8,
              alignItems: "center",
              marginBottom: 6,
            }}
          >
            <span className="mono">#{row.rank}</span>
            <div style={{ position: "relative", height: 10, background: "#efece3", borderRadius: 99 }}>
              <div
                style={{
                  position: "absolute",
                  left: `${left}%`,
                  width: `${Math.max(width, 2)}%`,
                  top: 0,
                  bottom: 0,
                  background: "#f3c4a6",
                  borderRadius: 99,
                }}
              />
              <div
                style={{
                  position: "absolute",
                  left: `${mid}%`,
                  width: 2,
                  top: -2,
                  bottom: -2,
                  background: "#c45c26",
                }}
              />
            </div>
            <span className="mono">
              {formatNum(mu, 1)}±{formatNum(std, 1)} {unit}
            </span>
          </div>
        );
      })}
    </div>
  );
}

export function ParityChart({ review }: { review: CampaignReview | null }) {
  const points = review?.parity || [];
  if (!points.length) {
    return <p className="hint">Generate or load enough rows for an in-sample parity plot.</p>;
  }
  const xs = points.map((p) => p.observed);
  const ys = points.map((p) => p.predicted_mean);
  const all = [...xs, ...ys];
  const lo = Math.min(...all);
  const hi = Math.max(...all);
  const pad = (hi - lo) * 0.08 || 1;
  const a = lo - pad;
  const b = hi + pad;
  const w = 360;
  const h = 260;
  const left = 40;
  const top = 16;
  const inner = 200;
  const map = (v: number) => left + ((v - a) / (b - a)) * inner;
  const mapY = (v: number) => top + inner - ((v - a) / (b - a)) * inner;
  return (
    <svg className="chart parity" viewBox={`0 0 ${w} ${h}`} role="img" aria-labelledby="parity-title">
      <title id="parity-title">
        In-sample predicted versus observed {review?.target || "target"}
      </title>
      <line x1={map(a)} y1={mapY(a)} x2={map(b)} y2={mapY(b)} stroke="#c9c2b4" />
      {points.map((p, i) => (
        <circle key={i} cx={map(p.observed)} cy={mapY(p.predicted_mean)} r={3.5} fill="#1d4e89" />
      ))}
      <text x="8" y="12" fontSize="10" fill="#5c6b7a">
        predicted vs observed {review?.unit}
      </text>
      <text x={left} y={top + inner + 18} fontSize="10" fill="#5c6b7a">
        observed
      </text>
    </svg>
  );
}

export function BudgetBar({ used, total }: { used: number; total: number }) {
  const pct = total ? Math.min(100, (used / total) * 100) : 0;
  return (
    <div>
      <div
        className="budget-track"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={total || 100}
        aria-valuenow={used}
        aria-label="Experiment budget used"
      >
        <div className="budget-fill" style={{ width: `${pct}%` }} />
      </div>
      <p className="meta">
        {used} of {total || "—"} experiments used ({formatNum(pct, 0)}%)
      </p>
    </div>
  );
}

export function BaselineCompare({ comparison }: { comparison?: BaselineComparison | null }) {
  if (!comparison) return null;
  if (!comparison.applicable) {
    return <p className="hint">{comparison.note}</p>;
  }
  return (
    <div className="baseline">
      <p className="meta">
        Why not random? Same-size space-filling draw from the leftover candidate pool, scored on
        this surrogate&apos;s expected improvement.
      </p>
      <div className="compare">
        <article>
          <p className="meta">This batch · Σ EI</p>
          <p className="stat">{formatNum(comparison.proposed_sum_ei, 4)}</p>
        </article>
        <article>
          <p className="meta">Space-filling · Σ EI</p>
          <p className="stat">{formatNum(comparison.baseline_sum_ei, 4)}</p>
        </article>
        <article>
          <p className="meta">Surrogate lift</p>
          <p className="stat">{formatNum(comparison.ei_lift, 4)}</p>
        </article>
      </div>
      <p className="hint">{comparison.note}</p>
    </div>
  );
}
