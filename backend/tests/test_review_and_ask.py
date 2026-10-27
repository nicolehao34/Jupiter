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

    assert client.post(f"/api/projects/{pid}/recommend").status_code == 200
    after = client.get(f"/api/projects/{pid}/review").json()
    assert after["n_batches"] >= 1
    assert after["batches"][0]["strategy"] == "expected_improvement"


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
