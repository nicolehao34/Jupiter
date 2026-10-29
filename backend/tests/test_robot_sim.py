from app import robot_sim


def test_plan_motion_returns_simulation_frames():
    sheet = {
        "runs": [
            {"run": 1, "rank": 1, "setpoints": {"calcination_temp_C": 800}},
            {"run": 2, "rank": 2, "setpoints": {"calcination_temp_C": 820}},
        ]
    }
    plan = robot_sim.plan_motion_for_run_sheet(sheet)
    assert plan["simulation_only"] is True
    assert plan["frame_count"] == len(plan["frames"])
    assert plan["frames"][0]["joints"]
    assert plan.get("references_doc")


def test_agent_loop_includes_robot_tool():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    pid = client.post("/api/projects").json()["id"]
    run = client.post(
        f"/api/projects/{pid}/agent/run",
        json={
            "goal_text": "Maximize NMC811 discharge capacity by tuning calcination and slurry.",
            "reset_session": True,
        },
    ).json()
    tools = [s["tool"] for s in run["transcript"] if s.get("ok")]
    assert "plan_robot_motion" in tools
    robot = next(s for s in run["transcript"] if s["tool"] == "plan_robot_motion")
    assert robot["result"]["simulation_only"] is True
