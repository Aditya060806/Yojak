import hashlib
import json

from ml_pipeline.sas.package import package, readiness


def test_packaging_preserves_reviewed_documents(tmp_path, monkeypatch):
    (tmp_path / "manifest.json").write_text(json.dumps({"source_version": "fixture"}))
    sub = tmp_path / "submission"
    sub.mkdir()
    for suffix in ("docx", "pdf"):
        (sub / f"Yojak_Approach_Note.{suffix}").write_bytes(b"reviewed original")
    monkeypatch.setattr("ml_pipeline.sas.package.export_bundle", lambda out: None)
    result = package(tmp_path)
    assert result.exists()
    for suffix in ("docx", "pdf"):
        assert (sub / f"Yojak_Approach_Note.{suffix}").read_bytes() == b"reviewed original"
    assert json.loads(result.read_text())["status"] == "review_required"


def test_readiness_distinguishes_changed_new_and_missing_evidence(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"source_version": "fixture"}))
    sub = tmp_path / "submission"
    sub.mkdir()
    (tmp_path / "salary_report.json").write_text("{}")
    (tmp_path / "planner_benchmark.json").write_text("{}")
    (tmp_path / "truncation_sensitivity.json").write_text("{}")
    (sub / "note_build_manifest.json").write_text(json.dumps({"source_version": "fixture", "evidence_hashes": {
        "manifest.json": hashlib.sha256(manifest.read_bytes()).hexdigest(), "salary_report.json": "old"}}))
    report = readiness(tmp_path)
    assert report["evidence"]["manifest.json"]["status"] == "unchanged"
    assert report["evidence"]["salary_report.json"]["status"] == "changed_since_note_build"
    assert report["evidence"]["planner_benchmark.json"]["status"] == "not_recorded_in_note_build"
    assert report["evidence"]["calibration_audit.json"]["status"] == "missing"
    assert report["evidence"]["truncation_sensitivity.json"]["status"] == "not_recorded_in_note_build"
    assert not report["document_exists"]
