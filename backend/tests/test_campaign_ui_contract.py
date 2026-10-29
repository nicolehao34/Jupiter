"""Fields the campaign HUD / origin chips consume. No GP numerics are changed here."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

GOAL = "Maximize NMC811 discharge capacity by tuning calcination and slurry."


def test_project_payload_exposes_session_and_origins_for_hud():
    pid = client.post("/api/projects").json()["id"]
    loaded = client.post(f"/api/projects/{pid}/dataset/sample").json()
    assert loaded["dataset"]["data_origin"] == "synthetic_demonstration"
    assert loaded["observations"]
    assert all(row["source"] == "synthetic_demonstration" for row in loaded["observations"])
    assert loaded["inference"]["mode"] != "live"
    assert "NEBIUS" in loaded["inference"]["message"] or "unconfigured" in loaded["inference"]["mode"]

    run = client.post(
        f"/api/projects/{pid}/agent/run",
        json={"goal_text": GOAL, "reset_session": True},
    ).json()
    assert run["stop_reason"] == "human_checkpoint"
    assert run["can_continue"] is True
    assert run["continue_hint"]
    assert run["controller"] == "playbook"
    assert run["inference"]["mode"] != "live"
    checkpoint = next(step for step in run["running_plan"] if step["id"] == "checkpoint")
    assert checkpoint["status"] in {"done", "running"}

    generate = next(step for step in run["transcript"] if step["tool"] == "generate_batch" and step["ok"])
    assert "Gaussian" in (generate["result"].get("note") or "") or generate["result"].get("strategy")
    inspect = next(step for step in run["transcript"] if step["tool"] == "inspect_campaign" and step["ok"])
    assert inspect["result"]["data_origin"] in {"synthetic_demonstration", None} or "data_origin" in inspect["result"]

    project = client.get(f"/api/projects/{pid}").json()
    session = project["agent_session"]
    assert session["phase"] == "human_checkpoint"
    assert session["stop_reason"] == "human_checkpoint"
    assert session["can_continue"] is True
    assert session["running_plan"]

    batch = project["batches"][0]
    assert batch["rows"][0]["source"] == "surrogate_prediction"
    review = client.get(f"/api/projects/{pid}/review").json()
    assert review["data_origin"] == "synthetic_demonstration"
    assert review["best_observed"]["source"] == "synthetic_demonstration"


def test_continue_without_results_is_awaiting_for_next_action():
    pid = client.post("/api/projects").json()["id"]
    client.post(f"/api/projects/{pid}/agent/run", json={"goal_text": GOAL, "reset_session": True})
    second = client.post(
        f"/api/projects/{pid}/agent/run",
        json={"goal_text": GOAL, "continue_campaign": True},
    ).json()
    assert second["stop_reason"] == "awaiting_lab_results"
    assert second["can_continue"] is True
    project = client.get(f"/api/projects/{pid}").json()
    assert project["agent_session"]["phase"] == "awaiting_lab_results"
