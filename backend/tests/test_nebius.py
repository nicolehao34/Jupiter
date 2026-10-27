import json

from app import nebius
from app.nebius import GoalPayload, TextPayload, _coerce_json


class FakeResponse:
    def __init__(self, status_code, payload, headers=None):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


def test_invalid_json_is_rejected():
    try:
        _coerce_json("this is not json")
        assert False
    except ValueError:
        pass


def test_goal_schema_validation():
    GoalPayload.model_validate(
        {
            "target_metric": "y",
            "direction": "maximize",
            "input_variables": ["x"],
            "units": {"x": "C"},
            "rationale": "from user text",
            "caveats": [],
        }
    )
    try:
        GoalPayload.model_validate({"target_metric": "y"})
        assert False
    except Exception:
        pass


def test_live_http_error_does_not_look_successful(monkeypatch):
    monkeypatch.setenv("NEBIUS_API_KEY", "test-key")
    monkeypatch.setenv("NEBIUS_OFFLINE_DEMO", "false")
    from app.config import get_settings

    get_settings.cache_clear()

    def fake_post(*args, **kwargs):
        return FakeResponse(503, {"error": {"message": "unavailable"}})

    class FakeClient:
        def __init__(self, timeout=None):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, *args, **kwargs):
            return fake_post()

    monkeypatch.setattr(nebius.httpx, "Client", FakeClient)
    text, meta = nebius.complete("validation_summary", {"issues": []}, project_id=None)
    assert text == ""
    assert meta.mode == "failed"
    assert meta.error and "503" in meta.error
    get_settings.cache_clear()


def test_offline_demo_is_labeled(monkeypatch):
    monkeypatch.setenv("NEBIUS_OFFLINE_DEMO", "true")
    monkeypatch.setenv("NEBIUS_API_KEY", "")
    from app.config import get_settings

    get_settings.cache_clear()
    result = nebius.propose_goal("maximize capacity of NMC811", ["calcination_temp_C", "discharge_capacity_mAh_g"])
    assert result["inference"].mode == "offline_demo"
    assert "OFFLINE DEMO" in result["summary"]
    get_settings.cache_clear()


def test_unconfigured_mode(monkeypatch):
    monkeypatch.setenv("NEBIUS_OFFLINE_DEMO", "false")
    monkeypatch.setenv("NEBIUS_API_KEY", "")
    from app.config import get_settings

    get_settings.cache_clear()
    status = nebius.inference_status()
    assert status["mode"] == "unconfigured"
    text, meta = nebius.complete("batch_explanations", {"batch": {"rows": []}})
    assert meta.mode == "unconfigured"
    assert text == ""
    get_settings.cache_clear()


def test_text_payload_schema():
    TextPayload.model_validate({"summary": "ok", "bullets": ["a"]})
