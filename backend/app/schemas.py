from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

Direction = Literal["maximize", "minimize"]
InferenceMode = Literal["live", "offline_demo", "unconfigured", "failed"]
PointSource = Literal["measured", "surrogate_prediction", "synthetic_demonstration", "simulated"]


class BoundSpec(BaseModel):
    min: float
    max: float
    unit: str = ""

    @field_validator("max")
    @classmethod
    def max_gt_min(cls, value: float, info) -> float:
        min_value = info.data.get("min")
        if min_value is not None and value <= min_value:
            raise ValueError("bound max must be greater than min")
        return value


class OptimizationConfig(BaseModel):
    input_variables: list[str] = Field(min_length=1, max_length=6)
    target_metric: str
    direction: Direction = "maximize"
    units: dict[str, str] = Field(default_factory=dict)
    bounds: dict[str, BoundSpec]
    batch_size: int = Field(default=4, ge=1, le=12)
    experiment_budget: int = Field(default=12, ge=1, le=200)
    candidate_pool: int = Field(default=1600, ge=100, le=8000)

    @field_validator("input_variables")
    @classmethod
    def unique_inputs(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("input variables must be unique")
        return value


class ValidationIssue(BaseModel):
    code: str
    severity: Literal["error", "warning", "info"]
    message: str
    column: str | None = None
    count: int | None = None


class DatasetPreview(BaseModel):
    dataset_id: str
    version: int
    name: str
    n_rows: int
    n_columns: int
    columns: list[str]
    numeric_columns: list[str]
    dtypes: dict[str, str]
    preview_rows: list[dict[str, Any]]
    missing_counts: dict[str, int]
    duplicate_row_count: int
    data_origin: str | None = None
    issues: list[ValidationIssue]
    valid_for_modeling: bool
    initial_design_recommended: bool


class GoalRequest(BaseModel):
    goal_text: str = Field(min_length=8, max_length=4000)
    available_columns: list[str] = Field(default_factory=list)


class InferenceMeta(BaseModel):
    mode: InferenceMode
    model: str | None = None
    latency_ms: int | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    request_id: str | None = None
    error: str | None = None
    note: str | None = None


class GoalProposal(BaseModel):
    proposed_config: dict[str, Any]
    summary: str
    caveats: list[str] = Field(default_factory=list)
    inference: InferenceMeta


class RecommendationRow(BaseModel):
    rank: int
    parameters: dict[str, float]
    predicted_mean: float | None = None
    predicted_std: float | None = None
    acquisition: float
    tradeoff: Literal["exploit", "explore", "balanced", "initial_design"]
    explanation: str
    uncertainty_label: str
    source: PointSource = "surrogate_prediction"


class RecommendResponse(BaseModel):
    batch_id: str
    strategy: Literal["expected_improvement", "initial_design"]
    dataset_version: int
    n_observed: int
    n_excluded: int
    remaining_budget: int
    rows: list[RecommendationRow]
    model_config_snapshot: dict[str, Any]
    warnings: list[str] = Field(default_factory=list)
    inference: InferenceMeta | None = None
    change_summary: str | None = None


class ResultRow(BaseModel):
    parameters: dict[str, float]
    observed: float
    experiment_id: str | None = None


class PlotPoint(BaseModel):
    experiment_id: str | None = None
    parameters: dict[str, float]
    observed: float | None = None
    predicted_mean: float | None = None
    predicted_std: float | None = None
    kind: PointSource
    batch_id: str | None = None


class AskRequest(BaseModel):
    question: str = Field(min_length=4, max_length=2000)


class AgentRunRequest(BaseModel):
    goal_text: str = Field(min_length=8, max_length=4000)
    max_steps: int = Field(default=10, ge=1, le=10)


class SimulationRequest(BaseModel):
    c_rate: float = Field(default=1.0, gt=0.05, le=5.0)
    temperature_C: float = Field(default=25.0, ge=0.0, le=60.0)


class MaterialsLookupRequest(BaseModel):
    formula: str = Field(default="LiNi0.8Mn0.1Co0.1O2", min_length=2, max_length=80)
