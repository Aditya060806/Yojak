import pandas as pd
import pytest

from ml_pipeline.sas.calibration_audit import align_predictions, summarize


def example():
    prepared = pd.DataFrame({"row_key": ["a", "b"], "split": ["test", "train"], "group_id": ["g", "h"], "band": [0, 5], "role_family": ["Data analyst"] * 2})
    predictions = prepared.iloc[:1].drop(columns="split").assign(prediction=0, set_low=0, set_high=2)
    return prepared, predictions


def test_alignment_rejects_missing_extra_and_duplicate_predictions():
    prepared, predictions = example()
    with pytest.raises(ValueError, match="exactly"):
        align_predictions(prepared, predictions.iloc[:0], 2)
    with pytest.raises(ValueError, match="Duplicate"):
        align_predictions(prepared, pd.concat([predictions, predictions]), 2)
    with pytest.raises(ValueError, match="exactly"):
        align_predictions(prepared, predictions.assign(row_key="b"), 2)


def test_alignment_checks_labels_and_frozen_sets():
    prepared, predictions = example()
    assert align_predictions(prepared, predictions, 2).covered.tolist() == [True]
    with pytest.raises(ValueError, match="band"):
        align_predictions(prepared, predictions.assign(band=1), 2)
    with pytest.raises(ValueError, match="radius"):
        align_predictions(prepared, predictions.assign(set_high=3), 2)
    with pytest.raises(ValueError, match="ordinal"):
        align_predictions(prepared, predictions.assign(prediction=.5), 2)


def test_support_requires_groups_not_only_rows():
    frame = pd.DataFrame({"group_id": ["same"] * 50, "covered": [True] * 50, "width": [3] * 50})
    assert summarize(frame)["coverage"] is None


def test_bootstrap_reproducible_and_degeneracy_visible():
    frame = pd.DataFrame({"group_id": [str(i) for i in range(40)], "covered": [True] * 40, "width": [3] * 40})
    first = summarize(frame)
    assert first == summarize(frame.iloc[::-1])
    assert first["coverage_ci95"] == [1, 1]
    assert first["interval_degenerate"]
