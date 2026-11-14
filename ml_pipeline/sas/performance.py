"""Aggregate evaluation evidence for the private performance page; no fitting."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .calibration_audit import align_predictions
from .data import BANDS, PRIVATE


def performance_report(out: Path = PRIVATE) -> dict:
    def read(name):
        return json.loads((out / name).read_text())

    manifest, salary = read("manifest.json"), read("salary_report.json")
    if any(salary.get(key) != manifest[key] for key in ("source_version", "preparation_code_hash")):
        raise ValueError("Salary evaluation belongs to another prepared source")
    frame = align_predictions(pd.read_parquet(out / "analytics.parquet"), pd.read_csv(out / "test_predictions.csv"), salary["calibration"]["radius"])
    if len(frame) != salary["test"]["n"] or not len(frame):
        raise ValueError("Test support does not match saved evaluation")
    matrix = np.zeros((6, 6), dtype=int)
    np.add.at(matrix, (frame.band.to_numpy(dtype=int), frame.prediction.to_numpy(dtype=int)), 1)
    optional, unavailable = {}, []
    for name in ("calibration_audit", "planner_benchmark"):
        path = out / f"{name}.json"
        if not path.exists():
            unavailable.append(name)
            continue
        report = read(path.name)
        current = report.get("source_version") == manifest["source_version"]
        if name == "calibration_audit":
            current = current and report.get("prediction_sha256") == hashlib.sha256((out / "test_predictions.csv").read_bytes()).hexdigest()
        else:
            current = current and report.get("preparation_code_hash") == manifest["preparation_code_hash"]
        if not current:
            unavailable.append(f"{name} (stale)")
            continue
        optional[name] = ({"overall": report["overall"], "slices": report["slices"], "limitations": report["limitations"]}
                          if name == "calibration_audit" else {"summary": report["summary"], "limitations": report["limitations"]})
    # Legacy research reports lack their own source hash. Serve only if the
    # evidence build links that exact report to the current source manifest.
    cohorts = {}
    research_path, build_path = out / "research_report.json", out / "submission/note_build_manifest.json"
    if research_path.exists() and build_path.exists():
        build = json.loads(build_path.read_text())
        hashes = build.get("evidence_hashes", {})
        linked = all(hashes.get(name) == hashlib.sha256((out / name).read_bytes()).hexdigest()
                     for name in ("manifest.json", "research_report.json"))
        if linked:
            research = read("research_report.json")
            for name in ("jds", "sds"):
                item = research[name]
                cohorts[name] = {key: item[key] for key in ("n", "groups", "oof_auc", "oof_auc_ci95", "oof_balanced_accuracy", "tree_oof_auc", "interpretation")}
    if not cohorts:
        unavailable.append("cohort research (missing verified source linkage)")
    sensitivity_path = out / "truncation_sensitivity.json"
    if sensitivity_path.exists():
        from .sensitivity import PROTECTED, evidence_hashes
        sensitivity = read(sensitivity_path.name)
        if all((out / name).exists() for name in PROTECTED) and sensitivity.get("evidence_hashes") == evidence_hashes(out):
            optional["truncation_sensitivity"] = {key: sensitivity[key] for key in
                                                 ("variants", "paired_mean_band_error", "rounds", "limitations")}
        else:
            unavailable.append("truncation_sensitivity (stale)")
    else:
        unavailable.append("truncation_sensitivity")
    return {"source": "Private SAS supplied datasets", "source_version": manifest["source_version"],
            "champion": salary["champion"], "unit_status": salary["unit_status"],
            "test": {**salary["test"], "exact_accuracy": float((frame.band == frame.prediction).mean()),
                     "groups": int(frame.group_id.nunique()), "qwk_ci95": salary["qwk_ci95_group_bootstrap"]},
            "bands": BANDS, "confusion": matrix.tolist(), "experiments": salary["experiments"],
            "selection": salary["selection"], "calibration": salary["calibration"],
            "training_seconds": salary["total_seconds"], "hardware": salary["hardware"],
            "versions": salary["versions"], "evaluation_history": salary.get("evaluation_history"),
            "cohorts": cohorts, "unavailable": unavailable, **optional}
