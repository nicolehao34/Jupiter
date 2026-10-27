from __future__ import annotations

from io import StringIO
from typing import Any

import pandas as pd

from . import nebius
from .db import Batch, Dataset, Observation, Project, dump, load, new_id, sample_csv_path, session
from .optimizer import recommend as run_recommend
from .schemas import OptimizationConfig
from .synthetic import sample_metadata
from .validation import json_rows, modeling_matrix, preview_frame, read_csv_text, round_key


def create_project(name: str = "NMC811 processing campaign") -> dict[str, Any]:
    db = session()
    try:
        project = Project(id=new_id(), name=name)
        db.add(project)
        db.commit()
        return project_payload(project.id)
    finally:
        db.close()


def project_payload(project_id: str) -> dict[str, Any]:
    db = session()
    try:
        project = db.get(Project, project_id)
        if project is None:
            raise KeyError("Project not found.")
        dataset = db.get(Dataset, project.dataset_id) if project.dataset_id else None
        preview = None
        config = load(project.config_json)
        cfg_model = OptimizationConfig.model_validate(config) if config else None
        if dataset is not None:
            frame = read_csv_text(dataset.csv_text)
            preview = preview_frame(
                frame,
                dataset_id=dataset.id,
                version=dataset.version,
                name=dataset.name,
                data_origin=dataset.data_origin,
                config=cfg_model,
            )
        observations = [
            {
                "id": row.id,
                "experiment_id": row.experiment_id,
                "parameters": load(row.parameters_json, {}),
                "observed": float(row.observed),
                "source": row.source,
                "created_at": row.created_at.isoformat(),
            }
            for row in db.query(Observation)
            .filter(Observation.project_id == project_id)
            .order_by(Observation.created_at.asc())
            .all()
        ]
        batches = []
        for batch in (
            db.query(Batch).filter(Batch.project_id == project_id).order_by(Batch.created_at.desc()).all()
        ):
            batches.append(
                {
                    "id": batch.id,
                    "dataset_version": batch.dataset_version,
                    "strategy": batch.strategy,
                    "created_at": batch.created_at.isoformat(),
                    **load(batch.payload_json, {}),
                }
            )
        return {
            "id": project.id,
            "name": project.name,
            "created_at": project.created_at.isoformat(),
            "config": config,
            "dataset": preview,
            "sample_metadata": sample_metadata(),
            "observations": observations,
            "batches": batches,
            "inference": nebius.inference_status(),
        }
    finally:
        db.close()


def load_sample_dataset(project_id: str) -> dict[str, Any]:
    path = sample_csv_path()
    if not path.exists():
        from .synthetic import write_sample

        write_sample(path)
    csv_text = path.read_text(encoding="utf-8")
    meta = sample_metadata()
    _attach_dataset(project_id, csv_text, name=meta["name"], data_origin=meta["data_origin"])
    _seed_config_from_sample(project_id, csv_text)
    return project_payload(project_id)


def upload_dataset(project_id: str, csv_text: str, name: str = "uploaded.csv") -> dict[str, Any]:
    _attach_dataset(project_id, csv_text, name=name, data_origin="user_upload")
    return project_payload(project_id)


def save_config(project_id: str, config: OptimizationConfig) -> dict[str, Any]:
    db = session()
    try:
        project = _require_project(db, project_id)
        project.config_json = config.model_dump_json()
        db.commit()
        return project_payload(project_id)
    finally:
        db.close()


def generate_recommendations(project_id: str) -> dict[str, Any]:
    db = session()
    try:
        project = _require_project(db, project_id)
        dataset = db.get(Dataset, project.dataset_id) if project.dataset_id else None
        if dataset is None:
            raise ValueError("Load or upload a dataset before generating recommendations.")
        config_raw = load(project.config_json)
        if not config_raw:
            raise ValueError("Set input variables, target, units, bounds, batch size, and budget first.")
        config = OptimizationConfig.model_validate(config_raw)
        frame = _frame_with_results(db, project_id, dataset)
        preview = preview_frame(
            frame,
            dataset_id=dataset.id,
            version=dataset.version,
            name=dataset.name,
            data_origin=dataset.data_origin,
            config=config,
        )
        blocking = [i for i in preview["issues"] if i.severity == "error"]
        if blocking:
            raise ValueError("; ".join(i.message for i in blocking))
        x, y, observed_params = modeling_matrix(frame, config)
        excluded = _open_proposals(db, project_id, config)
        previous = (
            db.query(Batch)
            .filter(Batch.project_id == project_id)
            .order_by(Batch.created_at.desc())
            .first()
        )
        result = run_recommend(x, y, observed_params, config, excluded=excluded)
        rows = [row.model_dump() for row in result["rows"]]
        explain_payload = {
            "strategy": result["strategy"],
            "n_observed": int(len(y)),
            "direction": config.direction,
            "target": config.target_metric,
            "target_unit": config.units.get(config.target_metric, ""),
            "rows": [
                {
                    "rank": r["rank"],
                    "parameters": r["parameters"],
                    "predicted_mean": r["predicted_mean"],
                    "predicted_std": r["predicted_std"],
                    "acquisition": r["acquisition"],
                    "tradeoff": r["tradeoff"],
                }
                for r in rows
            ],
        }
        bullets, infer_meta = nebius.explain_batch(explain_payload, project_id=project_id)
        if infer_meta.mode == "live" and bullets:
            for i, row in enumerate(rows):
                if i < len(bullets) and bullets[i]:
                    row["explanation"] = bullets[i] + " " + row["uncertainty_label"]
        change_summary = None
        change_meta = None
        if previous is not None:
            prev_payload = load(previous.payload_json, {})
            comparison = {
                "n_observed_before": (prev_payload.get("n_observed")),
                "n_observed_after": int(len(y)),
                "previous_strategy": previous.strategy,
                "new_strategy": result["strategy"],
                "previous_means": [
                    r.get("predicted_mean") for r in (prev_payload.get("rows") or [])[:4]
                ],
                "new_means": [r.get("predicted_mean") for r in rows[:4]],
                "n_excluded": result["n_excluded"],
            }
            change_summary, change_meta = nebius.summarize_change(comparison, project_id=project_id)
            if change_meta.mode != "live" and change_meta.mode != "offline_demo":
                change_summary = None
        validation_summary, val_meta = nebius.summarize_validation(
            [i.model_dump() if hasattr(i, "model_dump") else i for i in preview["issues"]],
            project_id=project_id,
        )
        numerical_change = (
            f"Deterministic note (not Nemotron): n_observed={int(len(y))}, "
            f"excluded={result['n_excluded']}, strategy={result['strategy']}, "
            f"remaining_budget={result['remaining_budget']}."
        )
        if previous is not None:
            prev_payload = load(previous.payload_json, {})
            numerical_change = (
                f"Deterministic note (not Nemotron): observations {prev_payload.get('n_observed')} → {int(len(y))}; "
                f"strategy {previous.strategy} → {result['strategy']}; "
                f"excluded open/completed points={result['n_excluded']}."
            )
        payload = {
            "batch_id": new_id(),
            "strategy": result["strategy"],
            "dataset_version": dataset.version,
            "n_observed": int(len(y)),
            "n_excluded": result["n_excluded"],
            "remaining_budget": result["remaining_budget"],
            "rows": rows,
            "model_config_snapshot": result["model_snapshot"],
            "warnings": result["warnings"],
            "validation_summary": validation_summary if val_meta.mode in {"live", "offline_demo"} else None,
            "inference": infer_meta.model_dump(),
            "change_summary": change_summary,
            "numerical_change": numerical_change,
            "change_inference": change_meta.model_dump() if change_meta else None,
        }
        db.add(
            Batch(
                id=payload["batch_id"],
                project_id=project_id,
                dataset_version=dataset.version,
                strategy=result["strategy"],
                config_json=config.model_dump_json(),
                payload_json=dump(payload),
            )
        )
        db.commit()
        return payload
    finally:
        db.close()


def add_results(project_id: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    db = session()
    try:
        project = _require_project(db, project_id)
        dataset = db.get(Dataset, project.dataset_id) if project.dataset_id else None
        if dataset is None:
            raise ValueError("Load a dataset first.")
        config = load(project.config_json)
        if not config:
            raise ValueError("Save an optimization config before adding results.")
        cfg = OptimizationConfig.model_validate(config)
        for row in rows:
            params = {k: float(row["parameters"][k]) for k in cfg.input_variables}
            db.add(
                Observation(
                    id=new_id(),
                    project_id=project_id,
                    dataset_id=dataset.id,
                    experiment_id=row.get("experiment_id"),
                    parameters_json=dump(params),
                    observed=str(float(row["observed"])),
                    source="measured",
                )
            )
        dataset.version += 1
        db.commit()
        return project_payload(project_id)
    finally:
        db.close()


def add_results_csv(project_id: str, csv_text: str) -> dict[str, Any]:
    db = session()
    try:
        project = _require_project(db, project_id)
        config = load(project.config_json)
        if not config:
            raise ValueError("Save an optimization config before adding results.")
        cfg = OptimizationConfig.model_validate(config)
        frame = read_csv_text(csv_text)
        missing = [c for c in cfg.input_variables + [cfg.target_metric] if c not in frame.columns]
        if missing:
            raise ValueError(f"Results CSV missing columns: {', '.join(missing)}")
        rows = []
        for rec in json_rows(frame):
            rows.append(
                {
                    "parameters": {k: rec[k] for k in cfg.input_variables},
                    "observed": rec[cfg.target_metric],
                    "experiment_id": rec.get("experiment_id"),
                }
            )
    finally:
        db.close()
    return add_results(project_id, rows)


def export_batch_csv(project_id: str, batch_id: str | None = None) -> str:
    db = session()
    try:
        query = db.query(Batch).filter(Batch.project_id == project_id)
        if batch_id:
            batch = query.filter(Batch.id == batch_id).first()
        else:
            batch = query.order_by(Batch.created_at.desc()).first()
        if batch is None:
            raise ValueError("No recommendation batch to export.")
        payload = load(batch.payload_json, {})
        rows = payload.get("rows") or []
        if not rows:
            raise ValueError("Batch has no rows.")
        records = []
        for row in rows:
            rec = {
                "batch_id": batch.id,
                "rank": row["rank"],
                **row["parameters"],
                "predicted_mean": row["predicted_mean"],
                "predicted_std": row["predicted_std"],
                "acquisition_ei": row["acquisition"],
                "tradeoff": row["tradeoff"],
                "uncertainty_label": row["uncertainty_label"],
                "source": row.get("source", "surrogate_prediction"),
            }
            records.append(rec)
        frame = pd.DataFrame.from_records(records)
        buffer = StringIO()
        frame.to_csv(buffer, index=False)
        return buffer.getvalue()
    finally:
        db.close()


def plot_data(project_id: str) -> dict[str, Any]:
    payload = project_payload(project_id)
    config = payload.get("config") or {}
    target = config.get("target_metric")
    points = []
    for obs in payload["observations"]:
        points.append(
            {
                "experiment_id": obs.get("experiment_id"),
                "parameters": obs["parameters"],
                "observed": obs["observed"],
                "predicted_mean": None,
                "predicted_std": None,
                "kind": "measured",
                "batch_id": None,
            }
        )
    origin = (payload.get("dataset") or {}).get("data_origin")
    if origin == "synthetic_demonstration":
        for point in points:
            if point["kind"] == "measured":
                point["kind"] = "synthetic_demonstration"
    latest = payload["batches"][0] if payload["batches"] else None
    if latest:
        for row in latest.get("rows") or []:
            points.append(
                {
                    "experiment_id": None,
                    "parameters": row["parameters"],
                    "observed": None,
                    "predicted_mean": row["predicted_mean"],
                    "predicted_std": row["predicted_std"],
                    "kind": "surrogate_prediction",
                    "batch_id": latest["id"],
                }
            )
    return {"target": target, "points": points, "latest_batch": latest}


def _attach_dataset(project_id: str, csv_text: str, name: str, data_origin: str) -> Dataset:
    frame = read_csv_text(csv_text)
    db = session()
    try:
        project = _require_project(db, project_id)
        version = 1
        if project.dataset_id:
            previous = db.get(Dataset, project.dataset_id)
            if previous:
                version = previous.version + 1
        dataset = Dataset(
            id=new_id(),
            project_id=project_id,
            version=version,
            name=name,
            data_origin=data_origin,
            csv_text=frame.to_csv(index=False),
        )
        db.add(dataset)
        db.flush()
        project.dataset_id = dataset.id
        # Reset observations tied to a brand-new table.
        db.query(Observation).filter(Observation.project_id == project_id).delete()
        for rec in json_rows(frame):
            # Observations are filled once a config exists; store raw rows as CSV only here.
            _ = rec
        db.commit()
        return dataset
    finally:
        db.close()


def _seed_config_from_sample(project_id: str, csv_text: str) -> None:
    meta = sample_metadata()
    frame = read_csv_text(csv_text)
    bounds = {}
    units = {spec["name"]: spec["unit"] for spec in meta["inputs"]}
    units[meta["target"]["name"]] = meta["target"]["unit"]
    for spec in meta["inputs"]:
        series = pd.to_numeric(frame[spec["name"]], errors="coerce")
        bounds[spec["name"]] = {
            "min": spec["low"],
            "max": spec["high"],
            "unit": spec["unit"],
        }
        _ = series
    config = OptimizationConfig(
        input_variables=[spec["name"] for spec in meta["inputs"]],
        target_metric=meta["target"]["name"],
        direction=meta["target"]["direction"],
        units=units,
        bounds=bounds,
        batch_size=meta["suggested_batch_size"],
        experiment_budget=meta["suggested_budget"],
    )
    save_config(project_id, config)
    _ingest_sample_observations(project_id, frame, config)


def _ingest_sample_observations(project_id: str, frame: pd.DataFrame, config: OptimizationConfig) -> None:
    db = session()
    try:
        project = _require_project(db, project_id)
        dataset = db.get(Dataset, project.dataset_id)
        assert dataset is not None
        db.query(Observation).filter(Observation.project_id == project_id).delete()
        for rec in json_rows(frame):
            params = {k: float(rec[k]) for k in config.input_variables}
            db.add(
                Observation(
                    id=new_id(),
                    project_id=project_id,
                    dataset_id=dataset.id,
                    experiment_id=str(rec.get("experiment_id") or ""),
                    parameters_json=dump(params),
                    observed=str(float(rec[config.target_metric])),
                    source="synthetic_demonstration",
                )
            )
        db.commit()
    finally:
        db.close()


def _frame_with_results(db, project_id: str, dataset: Dataset) -> pd.DataFrame:
    base = read_csv_text(dataset.csv_text)
    project = _require_project(db, project_id)
    config = load(project.config_json)
    if not config:
        return base
    cfg = OptimizationConfig.model_validate(config)
    extra_rows = []
    for obs in db.query(Observation).filter(Observation.project_id == project_id).all():
        params = load(obs.parameters_json, {})
        extra_rows.append(
            {
                **params,
                cfg.target_metric: float(obs.observed),
                "experiment_id": obs.experiment_id,
            }
        )
    if not extra_rows:
        return base
    extra = pd.DataFrame(extra_rows)
    combined = pd.concat([base, extra], ignore_index=True)
    # Drop exact duplicates on input columns + target.
    cols = cfg.input_variables + [cfg.target_metric]
    combined = combined.drop_duplicates(subset=[c for c in cols if c in combined.columns])
    return combined


def _open_proposals(db, project_id: str, config: OptimizationConfig) -> list[dict[str, float]]:
    observed_keys = {
        round_key(load(row.parameters_json, {}))
        for row in db.query(Observation).filter(Observation.project_id == project_id).all()
    }
    excluded: list[dict[str, float]] = []
    for batch in db.query(Batch).filter(Batch.project_id == project_id).all():
        payload = load(batch.payload_json, {})
        for row in payload.get("rows") or []:
            params = {k: float(row["parameters"][k]) for k in config.input_variables if k in row["parameters"]}
            if round_key(params) not in observed_keys:
                excluded.append(params)
    return excluded


def _require_project(db, project_id: str) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise KeyError("Project not found.")
    return project
