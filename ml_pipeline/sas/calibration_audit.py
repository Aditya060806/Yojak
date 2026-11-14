"""Read-only subgroup audit of frozen test predictions; never recalibrates."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .data import PRIVATE, write_json
from .model import band_sets


def align_predictions(prepared: pd.DataFrame, predictions: pd.DataFrame, radius: int) -> pd.DataFrame:
    test = prepared[prepared.split == "test"].copy()
    if not test.row_key.is_unique or not predictions.row_key.is_unique:
        raise ValueError("Duplicate evaluation row keys")
    if set(test.row_key) != set(predictions.row_key):
        raise ValueError("Predictions must cover exactly the frozen test partition")
    joined = test.merge(predictions, on="row_key", suffixes=("", "_saved"), validate="one_to_one")
    for column in ("group_id", "band", "role_family"):
        if not joined[column].equals(joined[column + "_saved"]):
            raise ValueError(f"Saved predictions disagree with prepared {column}")
    for column in ("band", "prediction", "set_low", "set_high"):
        values = joined[column].to_numpy()
        if not np.isfinite(values).all() or not ((values >= 0) & (values <= 5) & (values == np.floor(values))).all():
            raise ValueError(f"Invalid ordinal values in {column}")
    lo, hi = band_sets(joined.prediction, radius)
    if not np.array_equal(lo, joined.set_low) or not np.array_equal(hi, joined.set_high):
        raise ValueError("Saved prediction sets disagree with frozen calibration radius")
    joined["covered"] = (joined.band >= joined.set_low) & (joined.band <= joined.set_high)
    joined["width"] = joined.set_high - joined.set_low + 1
    return joined.sort_values("row_key").reset_index(drop=True)


def summarize(frame: pd.DataFrame, *, min_rows=30, min_groups=20, repeats=500) -> dict:
    groups = frame.groupby("group_id", sort=True).agg(n=("covered", "size"), covered=("covered", "sum"), width=("width", "sum"))
    result = {"rows": len(frame), "groups": len(groups), "supported": len(frame) >= min_rows and len(groups) >= min_groups}
    if not result["supported"]:
        return {**result, "reason": "Insufficient rows or independent group identifiers for reporting",
                "coverage": None, "mean_width": None, "coverage_ci95": None, "width_ci95": None}
    rng = np.random.default_rng(31)
    counts, hits, widths = groups.n.to_numpy(), groups.covered.to_numpy(), groups.width.to_numpy()
    draws = rng.integers(0, len(groups), size=(repeats, len(groups)))
    denominators = counts[draws].sum(axis=1)
    coverage = hits[draws].sum(axis=1) / denominators
    width = widths[draws].sum(axis=1) / denominators
    return {**result, "coverage": float(frame.covered.mean()), "mean_width": float(frame.width.mean()),
            "coverage_ci95": np.quantile(coverage, [.025, .975]).tolist(),
            "width_ci95": np.quantile(width, [.025, .975]).tolist(),
            "interval_degenerate": bool(np.ptp(coverage) == 0)}


def audit(out: Path = PRIVATE) -> dict:
    manifest = json.loads((out / "manifest.json").read_text())
    salary = json.loads((out / "salary_report.json").read_text())
    if any(salary.get(key) != manifest[key] for key in ("source_version", "preparation_code_hash")):
        raise ValueError("Salary report is not from the current prepared source")
    frame = align_predictions(pd.read_parquet(out / "analytics.parquet"), pd.read_csv(out / "test_predictions.csv"), salary["calibration"]["radius"])
    if len(frame) != salary["test"]["n"] or not np.isclose(frame.covered.mean(), salary["calibration"]["test_coverage"]):
        raise ValueError("Saved evaluation does not reproduce the salary report")
    experience = (frame.exp_min + frame.exp_max) / 2
    frame["experience_slice"] = pd.cut(experience, [-np.inf, 2, 5, 8, np.inf], labels=["up to 2", "above 2 to 5", "above 5 to 8", "above 8"])
    slices = {}
    for dimension in ("role_family", "experience_slice", "skills_truncated", "quality_flag"):
        slices[dimension] = {str(label): summarize(part) for label, part in frame.groupby(dimension, observed=True, sort=True)}
    report = {"source_version": manifest["source_version"], "model_id": salary["champion"],
              "prediction_sha256": hashlib.sha256((out / "test_predictions.csv").read_bytes()).hexdigest(),
              "audit_code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "config": {"minimum_rows": 30, "minimum_groups": 20, "bootstrap_repeats": 500, "seed": 31},
              "overall": summarize(frame), "slices": slices,
              "limitations": ["Descriptive audit of a previously examined test set; no model selection or recalibration.",
                               "Intervals resample test groups with the fitted model and radius held fixed; not full training uncertainty.",
                               "Dependence between groups and lack of exchangeability can weaken coverage claims.",
                               "A degenerate bootstrap interval, especially at perfect observed coverage, is not certainty.",
                               "Slices overlap; intervals are pointwise and not simultaneous guarantees.",
                               "Truncation and heuristic-quality comparisons change the sample, not a causal intervention.",
                               "Observed posting bands are not exact pay or hypothetical user-profile coverage."]}
    write_json(out / "calibration_audit.json", report)
    lines = ["# Private salary calibration audit", "", f"Frozen model: `{report['model_id']}`; source: `{report['source_version']}`.", "",
             "| Slice | Rows | Groups | Coverage | Mean band-set width | Group-bootstrap 95% coverage interval |",
             "|---|---:|---:|---:|---:|---|"]
    records = [("Overall", report["overall"])] + [(f"{dim}: {label}", values) for dim, parts in slices.items() for label, values in parts.items()]
    for label, values in records:
        if values["supported"]:
            low, high = values["coverage_ci95"]
            lines.append(f"| {label} | {values['rows']} | {values['groups']} | {values['coverage']:.1%} | {values['mean_width']:.2f} | {low:.1%} to {high:.1%} |")
        else:
            lines.append(f"| {label} | {values['rows']} | {values['groups']} | Suppressed | Suppressed | Insufficient support |")
    lines += ["", "## Limitations", ""] + [f"- {item}" for item in report["limitations"]]
    (out / "calibration_audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(audit()["overall"], indent=2))
