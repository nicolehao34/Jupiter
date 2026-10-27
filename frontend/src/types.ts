export type InferenceMode = "live" | "offline_demo" | "unconfigured" | "failed";

export interface InferenceStatus {
  mode: InferenceMode;
  configured: boolean;
  offline_demo: boolean;
  model: string;
  base_url: string;
  message: string;
  docs: string;
}

export interface InferenceMeta {
  mode: InferenceMode;
  model: string | null;
  latency_ms: number | null;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  total_tokens: number | null;
  request_id: string | null;
  error: string | null;
  note: string | null;
}

export interface ValidationIssue {
  code: string;
  severity: "error" | "warning" | "info";
  message: string;
  column?: string | null;
  count?: number | null;
}

export interface BoundSpec {
  min: number;
  max: number;
  unit: string;
}

export interface OptimizationConfig {
  input_variables: string[];
  target_metric: string;
  direction: "maximize" | "minimize";
  units: Record<string, string>;
  bounds: Record<string, BoundSpec>;
  batch_size: number;
  experiment_budget: number;
  candidate_pool?: number;
}

export interface DatasetPreview {
  dataset_id: string;
  version: number;
  name: string;
  n_rows: number;
  n_columns: number;
  columns: string[];
  numeric_columns: string[];
  dtypes: Record<string, string>;
  preview_rows: Record<string, unknown>[];
  missing_counts: Record<string, number>;
  duplicate_row_count: number;
  data_origin?: string | null;
  issues: ValidationIssue[];
  valid_for_modeling: boolean;
  initial_design_recommended: boolean;
}

export interface RecommendationRow {
  rank: number;
  parameters: Record<string, number>;
  predicted_mean: number | null;
  predicted_std: number | null;
  acquisition: number;
  tradeoff: "exploit" | "explore" | "balanced" | "initial_design";
  explanation: string;
  uncertainty_label: string;
  source: string;
}

export interface BaselineComparison {
  applicable: boolean;
  method: string;
  n?: number;
  proposed_sum_ei?: number;
  baseline_sum_ei?: number;
  proposed_mean_ei?: number;
  baseline_mean_ei?: number;
  ei_lift?: number;
  note: string;
}

export interface AudienceCase {
  who: string;
  job: string;
  intended_benefit: string;
  not_claimed: string;
}

export interface RunSheet {
  batch_id: string;
  title: string;
  measure: string;
  unit: string;
  direction: string;
  instructions: string;
  audience?: AudienceCase;
  runs: {
    run: number;
    rank: number;
    setpoints: Record<string, number>;
    setpoint_units: Record<string, string>;
    measure: string;
    unit: string;
    predicted_mean: number | null;
    predicted_std: number | null;
    acquisition: number | null;
    tradeoff: string;
    uncertainty_label?: string;
    record_back: string;
  }[];
}

export interface RecommendResponse {
  batch_id: string;
  strategy: "expected_improvement" | "initial_design";
  dataset_version: number;
  n_observed: number;
  n_excluded: number;
  remaining_budget: number;
  rows: RecommendationRow[];
  model_config_snapshot: Record<string, unknown>;
  warnings: string[];
  inference: InferenceMeta | null;
  change_summary?: string | null;
  numerical_change?: string | null;
  validation_summary?: string | null;
  baseline_comparison?: BaselineComparison | null;
  run_sheet?: RunSheet | null;
}

export interface Observation {
  id: string;
  experiment_id?: string | null;
  parameters: Record<string, number>;
  observed: number;
  source: string;
  created_at: string;
}

export interface ProjectState {
  id: string;
  name: string;
  created_at: string;
  config: OptimizationConfig | null;
  dataset: DatasetPreview | null;
  sample_metadata: {
    name: string;
    composition: string;
    disclaimer: string;
    inputs: { name: string; unit: string; low: number; high: number; description: string }[];
    target: { name: string; unit: string; direction: string; description: string };
  };
  observations: Observation[];
  batches: RecommendResponse[];
  inference: InferenceStatus;
}

export interface CampaignReview {
  project_id: string;
  name: string;
  target: string | null;
  direction: "maximize" | "minimize";
  unit: string;
  n_observed: number;
  n_batches: number;
  best_observed: Observation | null;
  worst_observed: Observation | null;
  budget: { used: number; total: number; remaining: number };
  batches: {
    id: string;
    strategy: string;
    created_at?: string;
    n_rows: number;
    n_observed_at_fit?: number;
    mean_prediction: number | null;
    mean_std: number | null;
    tradeoffs: string[];
    baseline_comparison?: BaselineComparison | null;
  }[];
  parity: {
    parameters: Record<string, number>;
    observed: number;
    predicted_mean: number;
    predicted_std: number;
    residual: number;
  }[];
  rmse: number | null;
  residual_note: string;
  data_origin?: string | null;
  inference: InferenceStatus;
  audience?: AudienceCase;
  run_sheet?: RunSheet | null;
}

export interface AskReply {
  answer: string;
  bullets: string[];
  inference: InferenceMeta;
}

export interface CampaignBrief {
  headline: string;
  bullets: string[];
  inference: InferenceMeta;
}

export interface PlotData {
  target: string | null;
  points: {
    experiment_id?: string | null;
    parameters: Record<string, number>;
    observed: number | null;
    predicted_mean: number | null;
    predicted_std: number | null;
    kind: string;
    batch_id?: string | null;
  }[];
  latest_batch: RecommendResponse | null;
}
