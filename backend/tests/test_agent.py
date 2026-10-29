from fastapi.testclient import TestClient

from app import agent, nebius
from app.main import app

client = TestClient(app)


def test_unknown_tool_is_forbidden():
    pid = client.post("/api/projects").json()["id"]
    outcome = agent.execute_tool(pid, "record_fake_results", {"observed": 200})
    assert outcome["ok"] is False
    assert "forbidden" in outcome["error"].lower() or "unknown" in outcome["error"].lower()


def test_playbook_runs_without_api_key():
    pid = client.post("/api/projects").json()["id"]
    body = client.post(
        f"/api/projects/{pid}/agent/run",
        json={
            "goal_text": "Maximize NMC811 discharge capacity by tuning calcination and slurry.",
            "reset_session": True,
        },
    )
    assert body.status_code == 200, body.text
    payload = body.json()
    assert payload["controller"] == "playbook"
    assert payload["inference"]["mode"] in {"unconfigured", "offline_demo"}
    assert payload["inference"]["mode"] != "live"
    assert payload["stop_reason"] == "human_checkpoint"
    assert payload["can_continue"] is True
    assert payload.get("live_enable_hint")
    names = [step["tool"] for step in payload["transcript"] if step["ok"]]
    assert "load_demo_dataset" in names
    assert "save_config" in names
    assert "generate_batch" in names
    assert "get_run_sheet" in names
    generate = next(step for step in payload["transcript"] if step["tool"] == "generate_batch")
    rows = generate["result"]["rows"]
    assert rows
    assert "predicted_mean" in rows[0]
    session = client.get(f"/api/projects/{pid}/agent/session").json()
    assert session["session"]["phase"] == "human_checkpoint"


def test_playbook_skips_reload_when_dataset_exists():
    pid = client.post("/api/projects").json()["id"]
    assert client.post(f"/api/projects/{pid}/dataset/sample").status_code == 200
    payload = client.post(
        f"/api/projects/{pid}/agent/run",
        json={"goal_text": "Maximize discharge capacity within the existing bounds.", "reset_session": True},
    ).json()
    names = [step["tool"] for step in payload["transcript"]]
    assert "load_demo_dataset" not in names
    assert "generate_batch" in names


def test_continue_without_new_results_awaits_lab():
    pid = client.post("/api/projects").json()["id"]
    first = client.post(
        f"/api/projects/{pid}/agent/run",
        json={"goal_text": "Maximize discharge capacity for NMC811 processing.", "reset_session": True},
    ).json()
    assert first["stop_reason"] == "human_checkpoint"
    second = client.post(
        f"/api/projects/{pid}/agent/run",
        json={"goal_text": first["goal_text"], "continue_campaign": True},
    ).json()
    assert second["stop_reason"] == "awaiting_lab_results"
    assert second["turn"] == 2


def test_continue_after_result_reranks():
    pid = client.post("/api/projects").json()["id"]
    client.post(
        f"/api/projects/{pid}/agent/run",
        json={"goal_text": "Maximize discharge capacity for NMC811 processing.", "reset_session": True},
    )
    batch = client.post(f"/api/projects/{pid}/recommend").json()
    row = batch["rows"][0]
    client.post(
        f"/api/projects/{pid}/results",
        json={
            "rows": [
                {
                    "parameters": row["parameters"],
                    "observed": 165.0,
                    "experiment_id": "AGENT-TEST-1",
                }
            ]
        },
    )
    cont = client.post(
        f"/api/projects/{pid}/agent/run",
        json={"goal_text": "Maximize discharge capacity for NMC811 processing.", "continue_campaign": True},
    ).json()
    assert cont["stop_reason"] == "human_checkpoint"
    turn_tools = [s["tool"] for s in cont["turn_transcript"] if s.get("ok")]
    assert "generate_batch" in turn_tools
    assert "get_run_sheet" in turn_tools


def test_live_tool_loop_executes_returned_calls(monkeypatch):
    pid = client.post("/api/projects").json()["id"]
    monkeypatch.setenv("NEBIUS_API_KEY", "test-key")
    monkeypatch.setenv("NEBIUS_OFFLINE_DEMO", "false")
    from app.config import get_settings

    get_settings.cache_clear()

    calls = {"n": 0}

    def fake_complete_with_tools(messages, tools, project_id=None):
        calls["n"] += 1
        from app.schemas import InferenceMeta

        meta = InferenceMeta(mode="live", model="nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B", note="fake")
        if calls["n"] == 1:
            return {
                "content": "",
                "tool_calls": [
                    {
                        "id": "call-inspect",
                        "type": "function",
                        "function": {"name": "inspect_campaign", "arguments": "{}"},
                    }
                ],
            }, meta
        return {"content": "Inspected the campaign. Ready for a human to record furnace results.", "tool_calls": []}, meta

    monkeypatch.setattr(nebius, "complete_with_tools", fake_complete_with_tools)
    payload = agent.run_campaign_agent(pid, "Maximize discharge capacity of NMC811.", reset_session=True)
    get_settings.cache_clear()
    assert payload["controller"] == "live"
    assert payload["transcript"][0]["tool"] == "inspect_campaign"
    assert payload["transcript"][0]["ok"] is True
    assert "furnace" in payload["final_text"].lower() or "Inspected" in payload["final_text"]


def test_generate_batch_tool_uses_gp_not_llm_numbers():
    pid = client.post("/api/projects").json()["id"]
    client.post(f"/api/projects/{pid}/dataset/sample")
    outcome = agent.execute_tool(pid, "generate_batch", {})
    assert outcome["ok"] is True
    assert outcome["result"]["strategy"] in {"expected_improvement", "initial_design"}
    assert outcome["result"]["rows"][0]["parameters"]
