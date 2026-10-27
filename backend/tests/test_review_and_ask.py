from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_review_after_sample_and_batch():
    pid = client.post("/api/projects").json()["id"]
    empty = client.get(f"/api/projects/{pid}/review")
    assert empty.status_code == 200
    assert empty.json()["n_observed"] == 0
    assert empty.json()["parity"] == []

    assert client.post(f"/api/projects/{pid}/dataset/sample").status_code == 200
    review = client.get(f"/api/projects/{pid}/review").json()
    assert review["n_observed"] == 24
    assert review["best_observed"]["observed"] >= review["worst_observed"]["observed"]
    assert review["budget"]["used"] == 24
    assert review["parity"]
    assert review["rmse"] is not None
    assert "in-sample" in review["residual_note"].lower() or "same rows" in review["residual_note"].lower()

    rec = client.post(f"/api/projects/{pid}/recommend")
    assert rec.status_code == 200
    cmp_ = rec.json()["baseline_comparison"]
    assert cmp_["applicable"] is True
    assert cmp_["proposed_sum_ei"] >= cmp_["baseline_sum_ei"]

    after = client.get(f"/api/projects/{pid}/review").json()
    assert after["n_batches"] >= 1
    assert after["batches"][0]["strategy"] == "expected_improvement"
    review_cmp = after["batches"][0]["baseline_comparison"]
    assert review_cmp["applicable"] is True
    assert review_cmp["ei_lift"] == cmp_["ei_lift"]
    assert after["audience"]["who"]
    assert "not been shown" in after["audience"]["not_claimed"].lower()
    assert rec.json()["run_sheet"]["runs"]
    assert rec.json()["run_sheet"]["runs"][0]["record_back"]
    sheet = client.get(f"/api/projects/{pid}/run-sheet")
    assert sheet.status_code == 200
    assert sheet.json()["runs"][0]["measure"] == "discharge_capacity_mAh_g"
    csv = client.get(f"/api/projects/{pid}/run-sheet.csv")
    assert csv.status_code == 200
    assert "record_back" in csv.text
    assert csv.text.count("\n") >= 2


def test_ask_unconfigured_does_not_look_live():
    pid = client.post("/api/projects").json()["id"]
    client.post(f"/api/projects/{pid}/dataset/sample")
    reply = client.post(
        f"/api/projects/{pid}/ask",
        json={"question": "What is the best observed capacity so far?"},
    )
    assert reply.status_code == 200
    body = reply.json()
    assert body["inference"]["mode"] in {"unconfigured", "offline_demo", "failed"}
    assert body["inference"]["mode"] != "live"


def test_ask_rejects_short_question():
    pid = client.post("/api/projects").json()["id"]
    bad = client.post(f"/api/projects/{pid}/ask", json={"question": "hi"})
    assert bad.status_code == 422
