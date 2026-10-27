"""Seeded synthetic NMC811 cathode-processing demonstration data.

The response surface is a smooth, invented function used only to drive the
demo. It is not a physics model of calcination, sintering, or electrochemistry.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

DEMO_NAME = "NMC811 cathode processing (synthetic demonstration)"
DEMO_COMPOSITION = "LiNi0.8Mn0.1Co0.1O2 (fixed composition)"
DATA_ORIGIN = "synthetic_demonstration"

INPUTS = [
    {
        "name": "calcination_temp_C",
        "unit": "°C",
        "low": 720.0,
        "high": 940.0,
        "description": "Hold temperature of the calcination / sintering step",
    },
    {
        "name": "hold_time_h",
        "unit": "h",
        "low": 4.0,
        "high": 16.0,
        "description": "Isothermal hold duration",
    },
    {
        "name": "heating_rate_C_min",
        "unit": "°C/min",
        "low": 1.0,
        "high": 8.0,
        "description": "Ramp rate to the hold temperature",
    },
    {
        "name": "carbon_black_wt_pct",
        "unit": "wt%",
        "low": 2.0,
        "high": 8.0,
        "description": "Conductive carbon loading in the electrode slurry",
    },
]

TARGET = {
    "name": "discharge_capacity_mAh_g",
    "unit": "mAh/g",
    "direction": "maximize",
    "description": "First-cycle discharge specific capacity (demonstration metric)",
}

# Peak of the invented surface (not a literature optimum).
PEAK = {
    "calcination_temp_C": 850.0,
    "hold_time_h": 10.0,
    "heating_rate_C_min": 3.2,
    "carbon_black_wt_pct": 4.6,
}

SCALES = {
    "calcination_temp_C": 70.0,
    "hold_time_h": 3.5,
    "heating_rate_C_min": 2.0,
    "carbon_black_wt_pct": 1.4,
}


def demonstration_capacity(row: dict[str, float]) -> float:
    """Invented unimodal surface plus a weak interaction. Demonstration only."""
    z = 0.0
    for name, peak in PEAK.items():
        z += ((row[name] - peak) / SCALES[name]) ** 2
    interaction = (
        0.15
        * ((row["calcination_temp_C"] - 850.0) / 70.0)
        * ((row["hold_time_h"] - 10.0) / 3.5)
    )
    return float(198.0 - 26.0 * z - 8.0 * interaction)


def generate_frame(n: int = 24, seed: int = 42, noise_std: float = 2.4) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows: list[dict[str, object]] = []
    # Space-filling-ish Sobol-style scramble via independent stratified draws.
    strata = int(np.ceil(n ** (1 / len(INPUTS))))
    grids = []
    for spec in INPUTS:
        edges = np.linspace(spec["low"], spec["high"], strata + 1)
        centers = 0.5 * (edges[:-1] + edges[1:])
        grids.append(centers)
    mesh = np.array(np.meshgrid(*grids, indexing="ij")).reshape(len(INPUTS), -1).T
    rng.shuffle(mesh)
    chosen = mesh[:n]
    for i, point in enumerate(chosen, start=1):
        row = {spec["name"]: float(point[j]) for j, spec in enumerate(INPUTS)}
        # Jitter inside the originating cell so points are not on a lattice.
        for j, spec in enumerate(INPUTS):
            span = (spec["high"] - spec["low"]) / (2 * strata)
            row[spec["name"]] = float(
                np.clip(row[spec["name"]] + rng.uniform(-span, span), spec["low"], spec["high"])
            )
        truth = demonstration_capacity(row)
        observed = float(truth + rng.normal(0.0, noise_std))
        rows.append(
            {
                "experiment_id": f"SYN-{i:03d}",
                **{k: round(v, 4) for k, v in row.items()},
                TARGET["name"]: round(observed, 3),
                "data_origin": DATA_ORIGIN,
            }
        )
    return pd.DataFrame(rows)


def sample_metadata() -> dict:
    return {
        "name": DEMO_NAME,
        "composition": DEMO_COMPOSITION,
        "data_origin": DATA_ORIGIN,
        "disclaimer": (
            "This dataset is generated from an invented response surface so the "
            "demo can run without a lab file. It does not represent real battery "
            "physics, measured cells, or a claim that the planner reduces lab experiments."
        ),
        "inputs": INPUTS,
        "target": TARGET,
        "peak_of_invented_surface": PEAK,
        "suggested_bounds": {
            spec["name"]: {"min": spec["low"], "max": spec["high"], "unit": spec["unit"]}
            for spec in INPUTS
        },
        "suggested_batch_size": 4,
        "suggested_budget": 40,
    }


def write_sample(path: Path, n: int = 24, seed: int = 42) -> pd.DataFrame:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = generate_frame(n=n, seed=seed)
    frame.to_csv(path, index=False)
    meta_path = path.with_suffix(".meta.json")
    meta_path.write_text(json.dumps(sample_metadata(), indent=2), encoding="utf-8")
    return frame
