"""Gaussian-process surrogate + expected-improvement batch selector.

Predictions and uncertainty are surrogate-model estimates, not experimentally
verified confidence intervals. Ranking is numerical; the LLM never invents values.
"""

from __future__ import annotations

from typing import Any, Literal

import numpy as np
from scipy.stats import norm, qmc
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, Matern, WhiteKernel
from sklearn.preprocessing import StandardScaler

from .schemas import BoundSpec, OptimizationConfig, RecommendationRow
from .validation import MIN_POINTS_FOR_GP, parameter_in_bounds, round_key

UNCERTAINTY_LABEL = (
    "Surrogate-model estimate (Gaussian process posterior standard deviation). "
    "Not an experimentally verified confidence interval."
)


def predict_observed(
    x_obs: np.ndarray,
    y_obs: np.ndarray,
    config: OptimizationConfig,
    *,
    seed: int = 42,
) -> dict[str, Any] | None:
    """In-sample GP predictions for a parity plot. Training residuals, not held-out error."""
    if len(y_obs) < MIN_POINTS_FOR_GP:
        return None
    y_fit = y_obs.copy()
    if config.direction == "minimize":
        y_fit = -y_fit
    x_scaler = StandardScaler()
    y_scaler = StandardScaler()
    x_s = x_scaler.fit_transform(x_obs)
    y_s = y_scaler.fit_transform(y_fit.reshape(-1, 1)).ravel()
    kernel = (
        ConstantKernel(1.0, constant_value_bounds=(1e-3, 1e3))
        * Matern(length_scale=np.ones(x_obs.shape[1]), nu=2.5, length_scale_bounds=(0.05, 20.0))
        + WhiteKernel(noise_level=0.08, noise_level_bounds=(1e-5, 1.0))
    )
    gpr = GaussianProcessRegressor(
        kernel=kernel,
        normalize_y=False,
        n_restarts_optimizer=1,
        random_state=seed,
        alpha=1e-8,
    )
    gpr.fit(x_s, y_s)
    mu_s, std_s = gpr.predict(x_s, return_std=True)
    mu_fit = y_scaler.inverse_transform(mu_s.reshape(-1, 1)).ravel()
    std_fit = std_s * float(y_scaler.scale_[0])
    mu_orig = -mu_fit if config.direction == "minimize" else mu_fit
    residual = y_obs - mu_orig
    rmse = float(np.sqrt(np.mean(residual**2)))
    return {
        "predicted_mean": [round(float(v), 4) for v in mu_orig],
        "predicted_std": [round(float(v), 4) for v in std_fit],
        "residual": [round(float(v), 4) for v in residual],
        "rmse": round(rmse, 4),
        "note": (
            "These are in-sample Gaussian-process residuals on the same rows used to fit the "
            "surrogate — not a held-out or experimentally verified error."
        ),
    }


def recommend(
    x_obs: np.ndarray,
    y_obs: np.ndarray,
    observed_params: list[dict[str, float]],
    config: OptimizationConfig,
    excluded: list[dict[str, float]] | None = None,
    *,
    seed: int = 42,
) -> dict[str, Any]:
    names = config.input_variables
    bounds = config.bounds
    excluded = excluded or []
    blocked = {round_key(p) for p in [*observed_params, *excluded]}
    remaining_budget = max(config.experiment_budget - len(observed_params), 0)
    if remaining_budget <= 0:
        raise ValueError(
            f"Experiment budget is exhausted ({len(observed_params)} measured rows already, "
            f"budget={config.experiment_budget}). Increase the budget to propose additional runs."
        )
    batch_n = min(config.batch_size, remaining_budget)

    lows = np.array([bounds[n].min for n in names], dtype=float)
    highs = np.array([bounds[n].max for n in names], dtype=float)
    if np.any(highs <= lows):
        raise ValueError("One or more parameter bounds are infeasible (max must be greater than min).")

    if len(y_obs) < MIN_POINTS_FOR_GP:
        rows = _initial_design(names, lows, highs, blocked, batch_n, seed)
        return {
            "strategy": "initial_design",
            "rows": rows,
            "n_excluded": len(blocked),
            "remaining_budget": remaining_budget - len(rows),
            "warnings": [
                f"Only {len(y_obs)} complete observation(s). Using a space-filling initial design "
                "instead of expected improvement. Add measured results, then regenerate."
            ],
            "model_snapshot": {
                "kind": "none_initial_design",
                "n_observed": int(len(y_obs)),
                "min_points_for_gp": MIN_POINTS_FOR_GP,
            },
            "baseline_comparison": {
                "applicable": False,
                "method": "not_applicable_initial_design",
                "note": (
                    "No EI-vs-space-filling comparison yet: the dataset is too small to fit a "
                    "Gaussian process, so this batch is itself a Latin-hypercube initial design."
                ),
            },
        }

    y_fit = y_obs.copy()
    if config.direction == "minimize":
        y_fit = -y_fit

    x_scaler = StandardScaler()
    y_scaler = StandardScaler()
    x_s = x_scaler.fit_transform(x_obs)
    y_s = y_scaler.fit_transform(y_fit.reshape(-1, 1)).ravel()

    kernel = (
        ConstantKernel(1.0, constant_value_bounds=(1e-3, 1e3))
        * Matern(length_scale=np.ones(x_obs.shape[1]), nu=2.5, length_scale_bounds=(0.05, 20.0))
        + WhiteKernel(noise_level=0.08, noise_level_bounds=(1e-5, 1.0))
    )
    gpr = GaussianProcessRegressor(
        kernel=kernel,
        normalize_y=False,
        n_restarts_optimizer=2,
        random_state=seed,
        alpha=1e-8,
    )
    gpr.fit(x_s, y_s)

    candidates = _feasible_candidates(names, lows, highs, blocked, config.candidate_pool, seed)
    if candidates.size == 0:
        raise ValueError(
            "No feasible candidates remain inside the supplied bounds after excluding "
            "completed and already-proposed experiments. Widen bounds, increase numeric "
            "tolerance, or clear stale proposals."
        )

    cand_s = x_scaler.transform(candidates)
    mu_s, std_s = gpr.predict(cand_s, return_std=True)
    std_s = np.maximum(std_s, 1e-9)
    best = float(np.max(y_s))
    ei = _expected_improvement(mu_s, std_s, best)
    mu_fit = y_scaler.inverse_transform(mu_s.reshape(-1, 1)).ravel()
    # delta method for std in original fit units
    y_scale = float(y_scaler.scale_[0])
    std_fit = std_s * y_scale
    if config.direction == "minimize":
        mu_orig = -mu_fit
    else:
        mu_orig = mu_fit
    std_orig = std_fit

    selected = _diverse_batch(candidates, ei, std_s, batch_n)
    rows: list[RecommendationRow] = []
    for rank, idx in enumerate(selected, start=1):
        params = {name: round(float(candidates[idx, j]), 4) for j, name in enumerate(names)}
        tradeoff = _tradeoff(ei[idx], std_s[idx], ei, std_s)
        rows.append(
            RecommendationRow(
                rank=rank,
                parameters=params,
                predicted_mean=round(float(mu_orig[idx]), 4),
                predicted_std=round(float(std_orig[idx]), 4),
                acquisition=round(float(ei[idx]), 6),
                tradeoff=tradeoff,
                explanation=_numerical_explanation(
                    params, float(mu_orig[idx]), float(std_orig[idx]), float(ei[idx]), tradeoff, config
                ),
                uncertainty_label=UNCERTAINTY_LABEL,
                source="surrogate_prediction",
            )
        )

    snapshot = {
        "kind": "sklearn_gpr_matern25",
        "n_observed": int(len(y_obs)),
        "kernel": str(gpr.kernel_),
        "direction": config.direction,
        "normalized_inputs": True,
        "normalized_target": True,
        "acquisition": "expected_improvement",
        "seed": seed,
    }
    return {
        "strategy": "expected_improvement",
        "rows": rows,
        "n_excluded": len(blocked),
        "remaining_budget": remaining_budget - len(rows),
        "warnings": [
            "Predicted values and error bars come from a Gaussian-process surrogate fit to the loaded table. "
            "They are not lab measurements and not a physics simulation."
        ],
        "model_snapshot": snapshot,
        "diagnostics": {
            "ei_max": float(np.max(ei)),
            "ei_median": float(np.median(ei)),
            "std_median": float(np.median(std_orig)),
        },
        "baseline_comparison": _baseline_comparison(candidates, ei, selected, batch_n, seed),
    }


def _baseline_comparison(
    candidates: np.ndarray,
    ei: np.ndarray,
    selected: list[int],
    batch_n: int,
    seed: int,
) -> dict[str, Any]:
    """Score a same-size space-filling draw with the same EI surface.

    Lift is surrogate-only: summed expected improvement of the proposed batch minus
    that of a diverse Latin-hypercube-style draw from the leftover candidates.
    It is not a measured lab saving.
    """
    chosen = set(selected)
    remaining = [i for i in range(len(candidates)) if i not in chosen]
    if len(remaining) < batch_n:
        return {
            "applicable": False,
            "method": "insufficient_leftover_candidates",
            "note": (
                "Could not draw a same-size space-filling baseline from leftover candidates. "
                "Widen bounds or increase the candidate pool."
            ),
        }
    span = np.ptp(candidates, axis=0)
    span[span == 0] = 1.0
    rng = np.random.default_rng(seed + 99)
    leftover = set(remaining)
    baseline: list[int] = [int(rng.choice(list(leftover)))]
    leftover.remove(baseline[0])
    while leftover and len(baseline) < batch_n:
        sel = np.asarray(baseline)

        def dist_score(i: int) -> float:
            return float(np.min(np.linalg.norm((candidates[i] - candidates[sel]) / span, axis=1)))

        nxt = int(max(leftover, key=dist_score))
        baseline.append(nxt)
        leftover.remove(nxt)

    proposed_ei = [float(ei[i]) for i in selected]
    baseline_ei = [float(ei[i]) for i in baseline]
    proposed_sum = float(sum(proposed_ei))
    baseline_sum = float(sum(baseline_ei))
    return {
        "applicable": True,
        "method": "diverse_spacefilling_from_same_pool",
        "n": len(selected),
        "proposed_sum_ei": round(proposed_sum, 6),
        "baseline_sum_ei": round(baseline_sum, 6),
        "proposed_mean_ei": round(proposed_sum / len(proposed_ei), 6),
        "baseline_mean_ei": round(baseline_sum / len(baseline_ei), 6),
        "ei_lift": round(proposed_sum - baseline_sum, 6),
        "note": (
            "Lift is the difference in summed expected improvement on the current Gaussian-process "
            "surrogate between this batch and a same-size space-filling draw from the same candidate "
            "pool. It is not a measured lab saving and not a claim about real furnace runs."
        ),
    }


def _expected_improvement(mu: np.ndarray, sigma: np.ndarray, best: float, xi: float = 0.01) -> np.ndarray:
    improvement = mu - best - xi
    z = improvement / sigma
    return improvement * norm.cdf(z) + sigma * norm.pdf(z)


def _feasible_candidates(
    names: list[str],
    lows: np.ndarray,
    highs: np.ndarray,
    blocked: set[tuple],
    n: int,
    seed: int,
) -> np.ndarray:
    sampler = qmc.LatinHypercube(d=len(names), seed=seed)
    unit = sampler.random(n=n)
    raw = qmc.scale(unit, lows, highs)
    keep = []
    for row in raw:
        params = {name: float(row[i]) for i, name in enumerate(names)}
        if not parameter_in_bounds(params, {n: BoundSpec(min=float(lows[i]), max=float(highs[i])) for i, n in enumerate(names)}):
            continue
        if round_key(params) in blocked:
            continue
        keep.append(row)
    return np.asarray(keep, dtype=float)


def _diverse_batch(candidates: np.ndarray, ei: np.ndarray, std: np.ndarray, batch_n: int) -> list[int]:
    remaining = set(range(len(candidates)))
    selected: list[int] = []
    # Scale features to unit cube using observed candidate range.
    span = np.ptp(candidates, axis=0)
    span[span == 0] = 1.0
    while remaining and len(selected) < batch_n:
        if not selected:
            idx = int(max(remaining, key=lambda i: (ei[i], std[i])))
        else:
            sel = np.asarray(selected)
            def score(i: int) -> float:
                dist = np.min(np.linalg.norm((candidates[i] - candidates[sel]) / span, axis=1))
                return float(ei[i] + 0.15 * dist)
            idx = int(max(remaining, key=score))
        selected.append(idx)
        remaining.remove(idx)
        # Drop near-duplicates of the chosen point.
        close = [
            j
            for j in list(remaining)
            if np.linalg.norm((candidates[j] - candidates[idx]) / span) < 0.08
        ]
        for j in close:
            remaining.remove(j)
    if not selected:
        raise ValueError("Could not assemble a diverse batch from the feasible candidate pool.")
    return selected


def _initial_design(
    names: list[str],
    lows: np.ndarray,
    highs: np.ndarray,
    blocked: set[tuple],
    batch_n: int,
    seed: int,
) -> list[RecommendationRow]:
    sampler = qmc.LatinHypercube(d=len(names), seed=seed + 7)
    unit = sampler.random(n=max(batch_n * 8, 32))
    raw = qmc.scale(unit, lows, highs)
    rows: list[RecommendationRow] = []
    for row in raw:
        params = {name: round(float(row[i]), 4) for i, name in enumerate(names)}
        if round_key(params) in blocked:
            continue
        blocked.add(round_key(params))
        rows.append(
            RecommendationRow(
                rank=len(rows) + 1,
                parameters=params,
                predicted_mean=None,
                predicted_std=None,
                acquisition=0.0,
                tradeoff="initial_design",
                explanation=(
                    "Space-filling initial design (Latin hypercube). The dataset is too small "
                    "to fit a stable Gaussian process, so there is no predicted performance yet."
                ),
                uncertainty_label=UNCERTAINTY_LABEL,
                source="surrogate_prediction",
            )
        )
        if len(rows) >= batch_n:
            break
    if not rows:
        raise ValueError("Could not generate an initial design that avoids existing experiments.")
    return rows


def _tradeoff(
    ei_i: float, std_i: float, ei: np.ndarray, std: np.ndarray
) -> Literal["exploit", "explore", "balanced"]:
    ei_q = np.quantile(ei, 0.66)
    std_q = np.quantile(std, 0.66)
    high_ei = ei_i >= ei_q
    high_std = std_i >= std_q
    if high_std and not high_ei:
        return "explore"
    if high_ei and not high_std:
        return "exploit"
    return "balanced"


def _numerical_explanation(
    params: dict[str, float],
    mu: float,
    std: float,
    ei: float,
    tradeoff: str,
    config: OptimizationConfig,
) -> str:
    target = config.target_metric
    unit = config.units.get(target, "")
    param_txt = ", ".join(
        f"{k}={v} {config.units.get(k, '')}".strip() for k, v in params.items()
    )
    return (
        f"Ranked by expected improvement on the Gaussian-process surrogate "
        f"({config.direction} {target}). Suggested settings: {param_txt}. "
        f"Predicted {target} = {mu:.3f} {unit} with posterior std {std:.3f} {unit}. "
        f"EI={ei:.4f}; tradeoff={tradeoff}. "
        "These numbers come from the fitted surrogate, not from Nemotron and not from a lab measurement."
    )
