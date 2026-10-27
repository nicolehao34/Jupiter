from fastapi.testclient import TestClient

from app.main import app
from app.synthetic import demonstration_capacity, generate_frame


client = TestClient(app)


def test_full_feedback_loop():
    created = client.post("/api/projects", json={"name": "demo"}).json()
    pid = created["id"]

    loaded = client.post(f"/api/projects/{pid}/dataset/sample")
    assert loaded.status_code == 200, loaded.text
    body = loaded.json()
    assert body["dataset"]["n_rows"] == 24
    assert body["dataset"]["data_origin"] == "synthetic_demonstration"
    assert body["dataset"]["valid_for_modeling"] is True
    assert body["config"]["target_metric"] == "discharge_capacity_mAh_g"

    rec = client.post(f"/api/projects/{pid}/recommend")
    assert rec.status_code == 200, rec.text
    batch = rec.json()
    assert batch["strategy"] == "expected_improvement"
    assert len(batch["rows"]) == 4
    for row in batch["rows"]:
        assert row["predicted_mean"] is not None
        assert row["predicted_std"] is not None
        assert row["uncertainty_label"]
        assert row["explanation"]

    export = client.get(f"/api/projects/{pid}/export")
    assert export.status_code == 200
    assert "predicted_mean" in export.text
    assert export.text.count("\n") >= 5

    top = batch["rows"][0]["parameters"]
    observed = demonstration_capacity(top)
    added = client.post(
        f"/api/projects/{pid}/results",
        json={
            "rows": [
                {
                    "parameters": top,
                    "observed": observed,
                    "experiment_id": "MANUAL-1",
                }
            ]
        },
    )
    assert added.status_code == 200, added.text

    rec2 = client.post(f"/api/projects/{pid}/recommend")
    assert rec2.status_code == 200, rec2.text
    batch2 = rec2.json()
    assert batch2["n_observed"] >= batch["n_observed"]
    keys1 = {tuple(sorted(r["parameters"].items())) for r in batch["rows"]}
    keys2 = {tuple(sorted(r["parameters"].items())) for r in batch2["rows"]}
    # Completed proposal may re-enter only if not still proposed; others stay excluded.
    incomplete = keys1 - {tuple(sorted(top.items()))}
    assert incomplete.isdisjoint(keys2)


def test_upload_malformed_and_missing_target():
    pid = client.post("/api/projects").json()["id"]
    bad = client.post(
        f"/api/projects/{pid}/dataset/upload",
        files={"file": ("bad.csv", b"\xff\xfe\x00not-utf8", "text/csv")},
    )
    assert bad.status_code == 400

    pid2 = client.post("/api/projects").json()["id"]
    uploaded = client.post(
        f"/api/projects/{pid2}/dataset/upload",
        files={"file": ("ok.csv", "a,b\n1,2\n3,4\n5,6\n", "text/csv")},
    )
    assert uploaded.status_code == 200
    cfg = {
        "input_variables": ["a"],
        "target_metric": "missing_y",
        "direction": "maximize",
        "units": {"a": "u", "missing_y": "u"},
        "bounds": {"a": {"min": 0, "max": 10, "unit": "u"}},
        "batch_size": 2,
        "experiment_budget": 8,
    }
    saved = client.put(f"/api/projects/{pid2}/config", json=cfg)
    assert saved.status_code == 200
    rec = client.post(f"/api/projects/{pid2}/recommend")
    assert rec.status_code == 400
    assert "missing_y" in rec.json()["detail"]


def test_health_and_inference_status():
    health = client.get("/api/health")
    assert health.status_code == 200
    status = client.get("/api/inference/status").json()
    assert status["mode"] in {"live", "offline_demo", "unconfigured"}
    assert "tokenfactory" in status["base_url"]


def test_results_csv_roundtrip():
    pid = client.post("/api/projects").json()["id"]
    assert client.post(f"/api/projects/{pid}/dataset/sample").status_code == 200
    frame = generate_frame(n=2, seed=99)
    csv = frame.to_csv(index=False)
    uploaded = client.post(
        f"/api/projects/{pid}/results/upload",
        files={"file": ("results.csv", csv, "text/csv")},
    )
    assert uploaded.status_code == 200, uploaded.text
    rec = client.post(f"/api/projects/{pid}/recommend")
    assert rec.status_code == 200
