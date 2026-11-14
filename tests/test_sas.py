"""Synthetic-only fixtures: no confidential rows in the repository or CI."""
import numpy as np
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.sas import router
from ml_pipeline.sas.data import (
    BANDS,
    connected_groups,
    partition,
    prepare_analytics,
    skills_of,
    write_role_review,
)
from ml_pipeline.sas.model import band_sets, calibrate, documents, metrics


def sample():
    return pd.DataFrame([
        dict(s_no=i, experience="0 - 3 yrs", job_description=None, job_desig="Data Analyst",
             job_type="Analytics", key_skills="Python, SQL, Excel", location="Example City", salary=band)
        for i, band in enumerate(["0to3", "0to3", "3to6"])
    ])


def test_dedup_conflicts_group_and_multiplicity():
    result = prepare_analytics(sample())
    assert len(result) == 2
    assert result.multiplicity.tolist() == [2, 1]
    assert result.group_id.nunique() == result.split.nunique() == 1
    assert result.band.tolist() == [0, 1]


def test_transitive_groups():
    frame = pd.DataFrame({"row_key": ["a", "b", "c", "d"], "id": [1, 1, 2, 3], "profile": [0, 1, 1, 2]})
    groups = connected_groups(frame, [["id"], ["profile"]])
    assert groups.iloc[:3].nunique() == 1
    assert groups.iloc[3] != groups.iloc[0]


def test_role_review_survives_preparation_rerun(tmp_path):
    frame = prepare_analytics(sample())
    path = tmp_path / "role_review.csv"
    assert write_role_review(frame, path) == "pending"
    reviewed = pd.read_csv(path).fillna("")
    reviewed["reviewed_family"] = "Data analyst"
    reviewed["reviewer_notes"] = "Manually checked"
    reviewed.to_csv(path, index=False)
    assert write_role_review(frame, path) == "complete"
    pd.testing.assert_frame_equal(pd.read_csv(path), reviewed)
    path.write_text("bad,header\n1,2\n")
    with pytest.raises(ValueError, match="Invalid existing role review"):
        write_role_review(frame, path)
    assert path.read_text() == "bad,header\n1,2\n"


def test_groups_stable_under_reordering():
    frame = sample()
    first, second = prepare_analytics(frame), prepare_analytics(frame.iloc[::-1])
    assert first.set_index("row_key").group_id.to_dict() == second.set_index("row_key").group_id.to_dict()


def test_truncated_token_views_and_missing():
    assert skills_of("Python, SQL, Mach...") == ["python", "sql"]
    assert skills_of("Python, SQL, Mach...", False) == ["mach", "python", "sql"]
    assert skills_of(np.nan) == []


def test_no_remote_work_only_quality_exclusion():
    frame = sample()
    frame["key_skills"] = "Python, work from home, part time"
    assert not prepare_analytics(frame).quality_flag.any()


def test_unknown_band_and_reversed_experience_rejected():
    frame = sample()
    frame.loc[0, "salary"] = "unknown"
    with pytest.raises(ValueError, match="salary band"):
        prepare_analytics(frame)
    frame = sample()
    frame.loc[0, "experience"] = "5 - 2 yrs"
    with pytest.raises(ValueError, match="Reversed"):
        prepare_analytics(frame)


def test_features_do_not_read_salary_or_description():
    frame = prepare_analytics(sample())
    first = documents(frame)
    frame["salary"] = "secret label"
    frame["job_description"] = "salary secret"
    assert documents(frame) == first


def test_calibration_finite_sample_and_boundaries():
    assert calibrate([0], [0]) == 5
    assert calibrate([0] * 20, [0] * 20) == 0
    lo, hi = band_sets([0, 5], 2)
    assert lo.tolist() == [0, 3]
    assert hi.tolist() == [2, 5]
    with pytest.raises(ValueError):
        calibrate([], [])
    assert np.searchsorted([3, 6, 10, 15, 25], [0, 3, 6, 50], side="right").tolist() == [0, 1, 2, 5]
    assert len(BANDS) == 6


def test_metrics_and_partition_repeatability():
    assert metrics([0, 1, 2], [0, 1, 2])["qwk"] == 1
    assert partition("example") == partition("example")


def test_private_api_disabled_and_validation(monkeypatch):
    monkeypatch.delenv("YOJAK_SAS_LOCAL", raising=False)
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    for endpoint in ["match", "plan", "pay-range"]:
        assert client.post(f"/sas/{endpoint}", json={}).status_code == 503


def test_enabled_api_validation_and_dispatch():
    from app.api.routes.sas import service

    class Stub:
        def match(self, family, experience, skills, complete_only):
            if family == "invalid":
                raise ValueError("Unknown role family")
            return {"support": 0, "source": "synthetic test", "skills": skills}

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[service] = Stub
    client = TestClient(app)
    assert client.post("/sas/match", json={"experience": -1}).status_code == 422
    assert client.post("/sas/match", json={"skills": ["x" * 121]}).status_code == 422
    assert client.post("/sas/match", json={"role_family": "invalid"}).status_code == 422
    assert client.post("/sas/match", json={}).json()["source"] == "synthetic test"


def test_public_export_does_not_reference_private_source():
    from pathlib import Path
    script = Path("scripts/export_static.py").read_text(encoding="utf-8")
    assert "private_sas" not in script and "ml_pipeline.sas" not in script
    ignore = Path(".gitignore").read_text()
    assert "/private_sas/" in ignore and "/SAS Data Problem Statement/" in ignore


def test_vocabulary_evidence_does_not_invent_recognition():
    from ml_pipeline.sas.service import vocabulary_evidence
    evidence = vocabulary_evidence({"sql", "unknown tool"}, [["sql", "python"], ["sql"]])
    assert evidence["observed_count"] == 1
    assert evidence["fraction"] == .5
    assert evidence["unobserved"] == ["unknown tool"]
    assert vocabulary_evidence(set(), [])["fraction"] is None
    assert vocabulary_evidence({"python"}, [])["observed_count"] == 0
