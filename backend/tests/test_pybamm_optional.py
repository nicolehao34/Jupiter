import pytest

from app.optional_science import run_pybamm_example


def test_pybamm_chen2020_spm_example():
    out = run_pybamm_example(1.0, 25.0)
    if not out.get("ok"):
        pytest.skip(out.get("reason", "PyBaMM not installed"))
    assert out["source"] == "simulated"
    assert out["parameter_set"] == "Chen2020"
    assert out["discharge_capacity_Ah"] > 0
    assert "processing" not in out["label"].lower() or "not" in out["label"].lower()
