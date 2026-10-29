import { nextCampaignAction, originInfo, phaseLabel, stopReasonLabel } from "../campaign";
import { useProject } from "../context";
import type { AgentRun, Observation } from "../types";
import { formatNum } from "../util";

export function DataOriginLegend({ extra }: { extra?: string }) {
  return (
    <div className="legend" role="note">
      <span>
        <i className="swatch measured" aria-hidden />
        Measured (lab)
      </span>
      <span>
        <i className="swatch predicted" aria-hidden />
        Predicted (GP)
      </span>
      <span>
        <i className="swatch synthetic" aria-hidden />
        Synthetic demo
      </span>
      <span>
        <i className="swatch simulated" aria-hidden />
        Simulated
      </span>
      {extra ? <span className="meta">{extra}</span> : null}
    </div>
  );
}

export function OriginChip({ kind }: { kind?: string | null }) {
  const info = originInfo(kind);
  return <span className={`chip origin ${info.tone}`}>{info.label}</span>;
}

export function NextActionCard({
  busy,
  run,
  compact,
}: {
  busy?: boolean;
  run?: AgentRun | null;
  compact?: boolean;
}) {
  const { project, latest } = useProject();
  const session = project?.agent_session;
  const action = nextCampaignAction({
    busy,
    stopReason: run?.stop_reason || session?.stop_reason,
    canContinue: run?.can_continue ?? session?.can_continue,
    nBatches: project?.batches?.length ?? 0,
    nObserved: project?.observations?.length ?? 0,
    inferenceMode: project?.inference?.mode,
  });
  return (
    <section className={`next-action ${action.kind}${compact ? " compact" : ""}`}>
      <h2>{action.title}</h2>
      <p>{action.body}</p>
      <div className="actions">
        <a className="tab active" href={action.href}>
          {action.cta}
        </a>
        {latest?.run_sheet && action.kind === "checkpoint" && (
          <a className="tab" href="#/plan">
            Furnace run sheet on Plan
          </a>
        )}
      </div>
    </section>
  );
}

function originMix(observations: Observation[] | undefined, predicted: number): string {
  const counts = new Map<string, number>();
  for (const row of observations || []) {
    const key = row.source || "unspecified";
    counts.set(key, (counts.get(key) || 0) + 1);
  }
  const parts = [...counts.entries()].map(([kind, n]) => `${n} ${originInfo(kind).label.toLowerCase()}`);
  if (predicted) parts.push(`${predicted} predicted (latest GP batch)`);
  return parts.join(" · ") || "No rows yet";
}

export function CampaignStatus({ busy, run }: { busy?: boolean; run?: AgentRun | null }) {
  const { project, latest } = useProject();
  const inference = project?.inference;
  const session = project?.agent_session;
  const stopReason = run?.stop_reason || session?.stop_reason;
  const turn = run?.turn ?? session?.turn;
  const phase = run?.phase || session?.phase;
  const action = nextCampaignAction({
    busy,
    stopReason,
    canContinue: run?.can_continue ?? session?.can_continue,
    nBatches: project?.batches?.length ?? 0,
    nObserved: project?.observations?.length ?? 0,
    inferenceMode: inference?.mode,
  });
  const budgetTotal = project?.config?.experiment_budget;
  const budgetUsed = project?.observations?.length;
  const predicted = latest?.rows?.length ?? 0;

  return (
    <section className="campaign-hud" aria-label="Campaign status">
      <div className="hud-grid">
        <article>
          <p className="meta">Token Factory</p>
          <p className={`hud-value infer ${inference?.mode || "unconfigured"}`}>
            {inference?.mode === "live"
              ? `Live Nemotron · ${inference.model}`
              : inference?.mode === "offline_demo"
                ? "Offline demo — not live Nebius"
                : "Unconfigured — labeled playbook"}
          </p>
          <p className="meta">{inference?.message}</p>
          {inference?.docs && (
            <p className="meta">
              <a href={inference.docs} target="_blank" rel="noreferrer">
                Token Factory quickstart
              </a>
            </p>
          )}
        </article>
        <article>
          <p className="meta">Campaign progress</p>
          <p className="hud-value">{phaseLabel(phase, stopReason)}</p>
          <p className="meta">
            {turn != null ? `Turn ${turn}` : "No turns yet"}
            {stopReason ? ` · ${stopReasonLabel(stopReason)}` : ""}
            {session?.transcript_length ? ` · ${session.transcript_length} tool events` : ""}
          </p>
        </article>
        <article>
          <p className="meta">Data origins</p>
          <p className="hud-value">{originMix(project?.observations, predicted)}</p>
          <p className="meta">
            Dataset {project?.dataset?.data_origin || "unspecified"} · {project?.batches?.length ?? 0} batch
            {(project?.batches?.length ?? 0) === 1 ? "" : "es"}
          </p>
        </article>
        <article>
          <p className="meta">Budget / next</p>
          <p className="hud-value">
            {budgetUsed ?? "—"} / {budgetTotal ?? "—"} observed
            {latest?.remaining_budget != null ? ` · ${latest.remaining_budget} remaining` : ""}
          </p>
          <p className="meta">{action.title}</p>
        </article>
      </div>
      <div className="hud-footer">
        <DataOriginLegend extra="PyBaMM stays simulated; GP rows stay predicted; demo CSV stays synthetic until you type a measurement." />
        <a className="tab" href={action.href}>
          {action.cta}
        </a>
      </div>
    </section>
  );
}

export function BudgetProgress({
  used,
  total,
  label,
  errored,
}: {
  used: number;
  total: number;
  label: string;
  errored?: boolean;
}) {
  const pct = total ? Math.min(100, (used / total) * 100) : 0;
  return (
    <div className="agent-progress">
      <div
        className="budget-track"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(pct)}
        aria-label={label}
      >
        <div className={`budget-fill${errored ? " error" : ""}`} style={{ width: `${pct}%` }} />
      </div>
      <p className="meta">
        {label} · {formatNum(pct, 0)}%
      </p>
    </div>
  );
}
