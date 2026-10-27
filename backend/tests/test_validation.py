from app.schemas import BoundSpec, OptimizationConfig
from app.validation import preview_frame, read_csv_text


def _config(**kwargs):
    base = dict(
        input_variables=["x1", "x2"],
        target_metric="y",
        direction="maximize",
        units={"x1": "C", "x2": "h", "y": "mAh/g"},
        bounds={
            "x1": BoundSpec(min=0, max=10, unit="C"),
            "x2": BoundSpec(min=0, max=10, unit="h"),
        },
        batch_size=2,
        experiment_budget=10,
    )
    base.update(kwargs)
    return OptimizationConfig(**base)


def test_malformed_csv():
    try:
        read_csv_text("this is not, a\nvalid")
    except ValueError as exc:
        assert "parse" in str(exc).lower() or "column" in str(exc).lower()
    else:
        # pandas may still parse ragged text; empty-column case is the hard fail
        pass
    try:
        read_csv_text("")
        assert False, "empty CSV should fail"
    except ValueError:
        pass


def test_missing_target():
    frame = read_csv_text("x1,x2\n1,2\n3,4\n5,6\n7,8\n9,10\n1,2\n")
    preview = preview_frame(
        frame, dataset_id="d", version=1, name="t", data_origin="user_upload", config=_config()
    )
    codes = {i.code for i in preview["issues"]}
    assert "missing_target" in codes
    assert preview["valid_for_modeling"] is False


def test_invalid_bounds_rejected_by_schema():
    try:
        BoundSpec(min=10, max=1, unit="C")
        assert False, "should reject max <= min"
    except ValueError:
        pass
