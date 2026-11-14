import json

import joblib
import numpy as np
import pandas as pd
import pytest

from ml_pipeline.sas.model import NUMERIC, BandModel, documents
from ml_pipeline.sas.sensitivity import (
    evidence_hashes,
    fixed_parameters,
    paired_error_interval,
    run_sensitivity,
    token_variant,
)


def test_variant_changes_only_skill_tokens():
    original = pd.DataFrame({"skills": [["sql"], ["python"]],
                             "skills_permissive": [["sql", "stat"], ["python"]],
                             "split": ["train", "test"], "group_id": ["a", "b"], "band": [1, 2]})
    variant = token_variant(original, True)
    assert variant.skills.iloc[0] == ["sql", "stat"]
    assert original.skills.iloc[0] == ["sql"]
    pd.testing.assert_frame_equal(original.drop(columns="skills"), variant.drop(columns="skills"))
    pd.testing.assert_frame_equal(original, token_variant(original, False))


def test_paired_error_uses_same_group_draws_and_direction():
    y = np.array([0, 1, 2, 3])
    result = paired_error_interval(y, y + 1, y, ["a", "a", "b", "c"])
    assert result["delta"] == -1
    assert result["ci95"] == [-1, -1]
    assert result["groups"] == 3
    assert paired_error_interval(y, y, y, ["a"] * 4)["ci95"] is None


def test_non_aft_champion_is_not_silently_substituted():
    with pytest.raises(ValueError, match="AFT champion"):
        fixed_parameters(BandModel(None, None, None, "classifier"), False)


def test_refits_are_training_only_and_preserve_champion(tmp_path, monkeypatch):
    xgb = pytest.importorskip("xgboost")
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.preprocessing import StandardScaler

    from ml_pipeline.sas.data import BOUNDS

    n = 36
    frame = pd.DataFrame({"row_key": [f"r{i}" for i in range(n)], "group_id": [f"g{i}" for i in range(n)],
                          "band": np.arange(n) % 6, "split": ["train"] * 18 + ["validation"] * 6 + ["calibration"] * 6 + ["test"] * 6,
                          "skills": [["sql"]] * n, "skills_permissive": [["sql", "stat"]] * n,
                          "job_desig": ["analyst"] * 18 + ["heldouttoken"] * 18, "location": ["city"] * n,
                          "exp_min": np.arange(n) % 4, "exp_max": 5, "exp_width": 3,
                          "skills_truncated": True, "description_missing": False})
    frame.to_parquet(tmp_path / "analytics.parquet")
    train = frame.iloc[:18]
    template = BandModel(TfidfVectorizer(min_df=1).fit(documents(train)),
                         StandardScaler().fit(train[NUMERIC].astype(float)), None, "aft")
    matrix = xgb.DMatrix(template.features(train))
    matrix.set_float_info("label_lower_bound", BOUNDS[train.band, 0])
    matrix.set_float_info("label_upper_bound", BOUNDS[train.band, 1])
    template.estimator = xgb.train({"objective": "survival:aft", "tree_method": "hist", "max_depth": 2}, matrix, 2)
    joblib.dump(template, tmp_path / "band_model.joblib")
    manifest = {"source_version": "synthetic", "preparation_code_hash": "fixture"}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    (tmp_path / "salary_report.json").write_text(json.dumps({**manifest, "champion": "fixture", "experiments": [{"name": "fixture", "rounds": 2}]}))
    (tmp_path / "test_predictions.csv").write_text("preserved original predictions")
    before = evidence_hashes(tmp_path)
    fitted = []
    original_fit = TfidfVectorizer.fit

    def checked_fit(self, raw_documents, y=None):
        assert len(raw_documents) == 18
        assert all("heldouttoken" not in document for document in raw_documents)
        fitted.append(raw_documents)
        return original_fit(self, raw_documents, y)

    monkeypatch.setattr(TfidfVectorizer, "fit", checked_fit)
    result = run_sensitivity(tmp_path, gpu=False)
    assert len(fitted) == 2
    assert result["rounds"] == 2
    assert result["variants"]["permissive"]["test"]["n"] == 6
    assert result["variants"]["conservative"]["device"] == "cpu"
    assert evidence_hashes(tmp_path) == before
    assert (tmp_path / "sensitivity/permissive_predictions.csv").exists()
    frame.loc[18, "group_id"] = "g0"
    frame.to_parquet(tmp_path / "analytics.parquet")
    with pytest.raises(ValueError, match="group-disjoint"):
        run_sensitivity(tmp_path, gpu=False)
