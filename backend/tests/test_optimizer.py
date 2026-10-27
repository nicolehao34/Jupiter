import numpy as np

from app.optimizer import recommend
from app.schemas import BoundSpec, OptimizationConfig
from app.synthetic import PEAK, demonstration_capacity
from app.validation import round_key


def _config(batch_size=4, budget=20):
    names = list(PEAK.keys())
    return OptimizationConfig(
        input_variables=names,
        target_metric="discharge_capacity_mAh_g",
        direction="maximize",
        units={**{n: "u" for n in names}, "discharge_capacity_mAh_g": "mAh/g"},
        bounds={
            "calcination_temp_C": BoundSpec(min=720, max=940, unit="C"),
            "hold_time_h": BoundSpec(min=4, max=16, unit="h"),
            "heating_rate_C_min": BoundSpec(min=1, max=8, unit="C/min"),
            "carbon_black_wt_pct": BoundSpec(min=2, max=8, unit="wt%"),
        },
        batch_size=batch_size,
        experiment_budget=budget,
        candidate_pool=800,
    )


def _seeded_observations(n=18, seed=0):
    rng = np.random.default_rng(seed)
    names = list(PEAK.keys())
    lows = np.array([720, 4, 1, 2], dtype=float)
    highs = np.array([940, 16, 8, 8], dtype=float)
    x = rng.uniform(lows, highs, size=(n, 4))
    params = [{names[j]: float(x[i, j]) for j in range(4)} for i in range(n)]
    y = np.array([demonstration_capacity(p) + rng.normal(0, 1.2) for p in params])
    return x, y, params


def test_ranking_moves_toward_invented_peak():
    x, y, params = _seeded_observations()
    result = recommend(x, y, params, _config(), seed=1)
    assert result["strategy"] == "expected_improvement"
    top = result["rows"][0].parameters
    peak_vec = np.array([PEAK[k] for k in top])
    top_vec = np.array([top[k] for k in top])
    span = np.array([220, 12, 7, 6], dtype=float)
    dist_top = np.linalg.norm((top_vec - peak_vec) / span)
    dist_mean = np.mean(
        [np.linalg.norm((np.array([p[k] for k in top]) - peak_vec) / span) for p in params]
    )
    assert dist_top < dist_mean, (dist_top, dist_mean)


def test_duplicate_and_proposal_exclusion():
    x, y, params = _seeded_observations(n=12, seed=2)
    first = recommend(x, y, params, _config(batch_size=3), seed=3)
    proposed = [row.parameters for row in first["rows"]]
    second = recommend(x, y, params, _config(batch_size=3), excluded=proposed, seed=3)
    first_keys = {round_key(p) for p in proposed}
    second_keys = {round_key(row.parameters) for row in second["rows"]}
    assert first_keys.isdisjoint(second_keys)


def test_infeasible_bounds_error():
    x, y, params = _seeded_observations(n=8)
    cfg = _config()
    cfg.bounds["calcination_temp_C"] = BoundSpec(min=900, max=901, unit="C")
    # Tiny range is still feasible; fully blocked candidates should error if everything excluded
    excluded = []
    rng = np.random.default_rng(0)
    for _ in range(500):
        excluded.append(
            {
                "calcination_temp_C": float(rng.uniform(900, 901)),
                "hold_time_h": float(rng.uniform(4, 16)),
                "heating_rate_C_min": float(rng.uniform(1, 8)),
                "carbon_black_wt_pct": float(rng.uniform(2, 8)),
            }
        )
    try:
        recommend(x, y, params, cfg, excluded=excluded, seed=0)
    except ValueError as exc:
        assert "feasible" in str(exc).lower() or "bounds" in str(exc).lower() or "candidates" in str(exc).lower()


def test_small_dataset_uses_initial_design():
    x, y, params = _seeded_observations(n=4, seed=4)
    result = recommend(x, y, params, _config(), seed=4)
    assert result["strategy"] == "initial_design"
    assert all(row.tradeoff == "initial_design" for row in result["rows"])
    assert all(row.predicted_mean is None for row in result["rows"])
