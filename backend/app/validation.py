from __future__ import annotations

from io import StringIO
from typing import Any

import numpy as np
import pandas as pd

from .schemas import BoundSpec, OptimizationConfig, ValidationIssue

MIN_POINTS_FOR_GP = 6
MAX_INPUTS = 6


def read_csv_text(csv_text: str) -> pd.DataFrame:
    if not csv_text or not csv_text.strip():
        raise ValueError("CSV is empty.")
    try:
        frame = pd.read_csv(StringIO(csv_text))
    except Exception as exc:  # noqa: BLE001 — surface parse errors to the user
        raise ValueError(f"Could not parse CSV: {exc}") from exc
    if frame.empty:
        raise ValueError("CSV parsed but contains no rows.")
    frame.columns = [str(col).strip() for col in frame.columns]
    if any(col == "" for col in frame.columns):
        raise ValueError("CSV has an empty column name.")
    if len(set(frame.columns)) != len(frame.columns):
        raise ValueError("CSV has duplicate column names.")
    return frame


def infer_numeric_columns(frame: pd.DataFrame) -> list[str]:
    numeric: list[str] = []
    for col in frame.columns:
        series = pd.to_numeric(frame[col], errors="coerce")
        if series.notna().mean() >= 0.8:
            numeric.append(col)
    return numeric


def preview_frame(
    frame: pd.DataFrame,
    *,
    dataset_id: str,
    version: int,
    name: str,
    data_origin: str | None,
    config: OptimizationConfig | None = None,
) -> dict[str, Any]:
    numeric = infer_numeric_columns(frame)
    missing = {col: int(frame[col].isna().sum()) for col in frame.columns if frame[col].isna().any()}
    duplicate_row_count = int(frame.duplicated().sum())
    issues = collect_issues(frame, numeric, config)
    n_obs = _usable_row_count(frame, config) if config else len(frame)
    initial = n_obs < MIN_POINTS_FOR_GP
    blocking = [issue for issue in issues if issue.severity == "error"]
    dtypes = {col: str(frame[col].dtype) for col in frame.columns}
    preview_rows = json_rows(frame.head(12))
    return {
        "dataset_id": dataset_id,
        "version": version,
        "name": name,
        "n_rows": int(len(frame)),
        "n_columns": int(len(frame.columns)),
        "columns": list(frame.columns),
        "numeric_columns": numeric,
        "dtypes": dtypes,
        "preview_rows": preview_rows,
        "missing_counts": missing,
        "duplicate_row_count": duplicate_row_count,
        "data_origin": data_origin,
        "issues": issues,
        "valid_for_modeling": len(blocking) == 0,
        "initial_design_recommended": initial and len(blocking) == 0,
    }


def collect_issues(
    frame: pd.DataFrame,
    numeric: list[str],
    config: OptimizationConfig | None,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if frame.isna().any().any():
        for col, count in frame.isna().sum().items():
            if count:
                issues.append(
                    ValidationIssue(
                        code="missing_values",
                        severity="warning" if not config or col not in _config_columns(config) else "error",
                        message=f"{int(count)} missing value(s) in '{col}'.",
                        column=str(col),
                        count=int(count),
                    )
                )
    if int(frame.duplicated().sum()):
        issues.append(
            ValidationIssue(
                code="duplicate_rows",
                severity="warning",
                message=f"{int(frame.duplicated().sum())} fully duplicate row(s).",
                count=int(frame.duplicated().sum()),
            )
        )
    if not numeric:
        issues.append(
            ValidationIssue(
                code="no_numeric_columns",
                severity="error",
                message="No numeric columns detected. This planner only accepts continuous numeric inputs and one numeric target.",
            )
        )
    if config is None:
        return issues
    missing_cols = [col for col in _config_columns(config) if col not in frame.columns]
    for col in missing_cols:
        issues.append(
            ValidationIssue(
                code="missing_column",
                severity="error",
                message=f"Configured column '{col}' is not in the dataset.",
                column=col,
            )
        )
    if config.target_metric not in frame.columns:
        issues.append(
            ValidationIssue(
                code="missing_target",
                severity="error",
                message=f"Target metric '{config.target_metric}' is not a column in the dataset.",
                column=config.target_metric,
            )
        )
    else:
        target = pd.to_numeric(frame[config.target_metric], errors="coerce")
        if target.notna().sum() == 0:
            issues.append(
                ValidationIssue(
                    code="non_numeric_target",
                    severity="error",
                    message=f"Target '{config.target_metric}' has no numeric values.",
                    column=config.target_metric,
                )
            )
    for name in config.input_variables:
        if name not in frame.columns:
            continue
        series = pd.to_numeric(frame[name], errors="coerce")
        if series.notna().sum() == 0:
            issues.append(
                ValidationIssue(
                    code="non_numeric_input",
                    severity="error",
                    message=f"Input '{name}' has no numeric values.",
                    column=name,
                )
            )
        bound = config.bounds.get(name)
        if bound:
            if bound.max <= bound.min:
                issues.append(
                    ValidationIssue(
                        code="invalid_bounds",
                        severity="error",
                        message=f"Bounds for '{name}' are infeasible (max ≤ min).",
                        column=name,
                    )
                )
            else:
                out = ((series < bound.min) | (series > bound.max)).sum()
                if out:
                    issues.append(
                        ValidationIssue(
                            code="points_outside_bounds",
                            severity="warning",
                            message=(
                                f"{int(out)} measured row(s) for '{name}' fall outside the "
                                f"allowed range [{bound.min}, {bound.max}]. They will still be used to fit the surrogate."
                            ),
                            column=name,
                            count=int(out),
                        )
                    )
    for name in config.input_variables:
        unit = config.units.get(name, "").strip()
        if not unit:
            issues.append(
                ValidationIssue(
                    code="missing_unit",
                    severity="error",
                    message=f"Supply a unit for input '{name}'. Units are user-declared labels, not converted.",
                    column=name,
                )
            )
    if not config.units.get(config.target_metric, "").strip():
        issues.append(
            ValidationIssue(
                code="missing_unit",
                severity="error",
                message=f"Supply a unit for target '{config.target_metric}'.",
                column=config.target_metric,
            )
        )
    if len(config.input_variables) > MAX_INPUTS:
        issues.append(
            ValidationIssue(
                code="too_many_inputs",
                severity="error",
                message=f"This MVP is limited to {MAX_INPUTS} continuous numeric inputs and one target.",
            )
        )
    n_obs = _usable_row_count(frame, config)
    if n_obs < 3:
        issues.append(
            ValidationIssue(
                code="too_few_rows",
                severity="error",
                message=(
                    f"Only {n_obs} complete numeric row(s) after dropping missing values. "
                    "Need at least 3 rows. For a new campaign, load the seeded demo dataset "
                    "or upload a small initial design."
                ),
                count=n_obs,
            )
        )
    elif n_obs < MIN_POINTS_FOR_GP:
        issues.append(
            ValidationIssue(
                code="small_dataset",
                severity="warning",
                message=(
                    f"{n_obs} complete rows is small for a Gaussian-process surrogate. "
                    "The next batch will use a space-filling initial-design strategy instead of expected improvement."
                ),
                count=n_obs,
            )
        )
    return issues


def _config_columns(config: OptimizationConfig) -> list[str]:
    return [*config.input_variables, config.target_metric]


def _usable_row_count(frame: pd.DataFrame, config: OptimizationConfig) -> int:
    cols = [col for col in _config_columns(config) if col in frame.columns]
    if len(cols) != len(_config_columns(config)):
        return 0
    subset = frame[cols].apply(pd.to_numeric, errors="coerce")
    return int(subset.dropna().shape[0])


def modeling_matrix(
    frame: pd.DataFrame, config: OptimizationConfig
) -> tuple[np.ndarray, np.ndarray, list[dict[str, float]]]:
    cols = config.input_variables + [config.target_metric]
    missing = [col for col in cols if col not in frame.columns]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")
    subset = frame[cols].apply(pd.to_numeric, errors="coerce").dropna()
    if subset.empty:
        raise ValueError("No complete numeric rows remain after dropping missing values.")
    x = subset[config.input_variables].to_numpy(dtype=float)
    y = subset[config.target_metric].to_numpy(dtype=float)
    records = subset[config.input_variables].to_dict(orient="records")
    return x, y, records


def json_rows(frame: pd.DataFrame) -> list[dict[str, Any]]:
    cleaned = frame.replace({np.nan: None})
    return cleaned.to_dict(orient="records")


def round_key(params: dict[str, float], digits: int = 4) -> tuple:
    return tuple(sorted((k, round(float(v), digits)) for k, v in params.items()))


def parameter_in_bounds(params: dict[str, float], bounds: dict[str, BoundSpec]) -> bool:
    for name, bound in bounds.items():
        value = params.get(name)
        if value is None or value < bound.min or value > bound.max:
            return False
    return True
