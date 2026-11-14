import json

import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.sas import router
from ml_pipeline.sas.performance import performance_report


def fixture_reports(out):
    manifest = {"source_version": "synthetic", "preparation_code_hash": "hash"}
    salary = {**manifest, "champion": "fixture", "unit_status": "unverified", "test": {"n": 2},
              "calibration": {"radius": 2}, "qwk_ci95_group_bootstrap": [0, 1], "experiments": [],
              "selection": "fixture", "total_seconds": 1, "hardware": {}, "versions": {}}
    for name, value in (("manifest", manifest), ("salary_report", salary)):
        (out / f"{name}.json").write_text(json.dumps(value))
    frame = pd.DataFrame({"row_key": ["a", "b"], "group_id": ["g", "h"], "band": [0, 2],
                          "role_family": ["Data analyst"] * 2, "split": ["test"] * 2})
    frame.to_parquet(out / "analytics.parquet")
    frame.drop(columns="split").assign(prediction=[0, 1], set_low=[0, 0], set_high=[2, 3]).to_csv(out / "test_predictions.csv", index=False)


def test_performance_uses_saved_counts_and_excludes_rows(tmp_path):
    fixture_reports(tmp_path)
    report = performance_report(tmp_path)
    assert report["test"]["exact_accuracy"] == .5
    assert report["confusion"][0][0] == report["confusion"][2][1] == 1
    assert sum(map(sum, report["confusion"])) == 2
    assert "row_key" not in json.dumps(report)
    assert report["cohorts"] == {}


def test_performance_rejects_stale_source(tmp_path):
    fixture_reports(tmp_path)
    path = tmp_path / "manifest.json"
    value = json.loads(path.read_text())
    value["source_version"] = "changed"
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError):
        performance_report(tmp_path)


def test_stale_optional_audit_is_not_served(tmp_path):
    fixture_reports(tmp_path)
    (tmp_path / "calibration_audit.json").write_text(json.dumps({"source_version": "synthetic", "prediction_sha256": "old"}))
    report = performance_report(tmp_path)
    assert "calibration_audit" not in report
    assert "calibration_audit (stale)" in report["unavailable"]


def test_performance_gate_and_no_store(monkeypatch):
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    monkeypatch.delenv("YOJAK_SAS_LOCAL", raising=False)
    assert client.get("/sas/performance").status_code == 503
    monkeypatch.setenv("YOJAK_SAS_LOCAL", "1")
    monkeypatch.setattr("ml_pipeline.sas.performance.performance_report", lambda: {"source": "synthetic"})
    result = client.get("/sas/performance")
    assert result.status_code == 200
    assert result.headers["cache-control"] == "no-store"


def test_sensitivity_is_aggregate_and_requires_all_evidence_hashes(tmp_path):
    from ml_pipeline.sas.sensitivity import evidence_hashes
    fixture_reports(tmp_path)
    (tmp_path / "band_model.joblib").write_bytes(b"not loaded by endpoint")
    value = {"evidence_hashes": evidence_hashes(tmp_path), "variants": {},
             "paired_mean_band_error": {}, "rounds": 2, "limitations": [], "private_field": "excluded"}
    (tmp_path / "truncation_sensitivity.json").write_text(json.dumps(value))
    report = performance_report(tmp_path)
    assert "truncation_sensitivity" in report
    assert "private_field" not in report["truncation_sensitivity"]
    (tmp_path / "band_model.joblib").write_bytes(b"changed")
    report = performance_report(tmp_path)
    assert "truncation_sensitivity" not in report
    assert "truncation_sensitivity (stale)" in report["unavailable"]
    (tmp_path / "band_model.joblib").unlink()
    assert "truncation_sensitivity" not in performance_report(tmp_path)
