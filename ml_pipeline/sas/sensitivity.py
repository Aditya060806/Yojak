"""Paired token-handling refits, separate from champion selection and artifacts."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone

from .data import BOUNDS, write_json
from .model import NUMERIC, BandModel, band_sets, calibrate, documents, metrics

PROTECTED = ("manifest.json", "analytics.parquet", "salary_report.json", "band_model.joblib", "test_predictions.csv")


def evidence_hashes(out: Path) -> dict:
    return {name: hashlib.sha256((out / name).read_bytes()).hexdigest() for name in PROTECTED}


def token_variant(frame: pd.DataFrame, permissive: bool) -> pd.DataFrame:
    result = frame.copy()
    if permissive:
        result["skills"] = result["skills_permissive"]
    return result


def fixed_parameters(model: BandModel, gpu: bool) -> dict:
    if model.kind != "aft":
        raise ValueError("This paired experiment requires an AFT champion")
    config = json.loads(model.estimator.save_config())["learner"]
    booster = config["gradient_booster"]
    if booster["name"] != "gbtree" or config["objective"]["name"] != "survival:aft":
        raise ValueError("Unsupported champion configuration")
    params = dict(booster["tree_train_param"])
    params.update(config["objective"]["aft_loss_param"])
    params.update(objective="survival:aft", eval_metric="aft-nloglik", tree_method="hist",
                  device="cuda" if gpu else "cpu", seed=config["generic_param"]["seed"],
                  base_score=config["learner_model_param"]["base_score"])
    return params


def paired_error_interval(y, reference, alternative, groups, repeats=1000) -> dict:
    # Resample clusters once per replicate, preserving pairing and multiplicity.
    delta = np.abs(np.asarray(y) - alternative) - np.abs(np.asarray(y) - reference)
    grouped = pd.DataFrame({"group": groups, "delta": delta}).groupby("group").delta.agg(["sum", "count"])
    if len(grouped) < 2:
        return {"delta": float(delta.mean()), "ci95": None, "groups": len(grouped)}
    sums, counts = grouped["sum"].to_numpy(), grouped["count"].to_numpy()
    rng = np.random.default_rng(31)
    samples = []
    for _ in range(repeats):
        index = rng.integers(0, len(grouped), len(grouped))
        samples.append(float(sums[index].sum() / counts[index].sum()))
    return {"delta": float(delta.mean()), "ci95": np.quantile(samples, [.025, .975]).tolist(),
            "groups": len(grouped), "repeats": repeats}


def run_sensitivity(out: Path, gpu: bool = True) -> dict:
    import xgboost as xgb

    before = evidence_hashes(out)
    manifest = json.loads((out / "manifest.json").read_text())
    salary = json.loads((out / "salary_report.json").read_text())
    if any(manifest[k] != salary.get(k) for k in ("source_version", "preparation_code_hash")):
        raise ValueError("Champion report and prepared source do not match")
    frame = pd.read_parquet(out / "analytics.parquet")
    if frame.row_key.duplicated().any() or frame.groupby("group_id").split.nunique().max() != 1:
        raise ValueError("Frozen partitions are not group-disjoint with unique rows")
    if set(frame.split) != {"train", "validation", "calibration", "test"}:
        raise ValueError("Four nonempty partitions are required")
    champion = joblib.load(out / "band_model.joblib")
    parameters = fixed_parameters(champion, gpu)
    rounds = champion.estimator.num_boosted_rounds()
    selected = next(item for item in salary["experiments"] if item["name"] == salary["champion"])
    if selected.get("rounds") != rounds:
        raise ValueError("Champion rounds do not match selection record")
    if gpu and not xgb.build_info().get("USE_CUDA", False):
        raise RuntimeError("CUDA build unavailable")
    results, predictions = {}, {}
    directory = out / "sensitivity"
    directory.mkdir(exist_ok=True)
    started = time.perf_counter()
    for name, permissive in (("conservative", False), ("permissive", True)):
        variant = token_variant(frame, permissive)
        training = variant[variant.split == "train"]
        calibration = variant[variant.split == "calibration"]
        test = variant[variant.split == "test"]
        t0 = time.perf_counter()
        vectorizer = clone(champion.vectorizer).fit(documents(training))
        scaler = clone(champion.scaler).fit(training[NUMERIC].astype(float))
        model = BandModel(vectorizer, scaler, None, "aft")
        matrix = xgb.DMatrix(model.features(training))
        matrix.set_float_info("label_lower_bound", BOUNDS[training.band.to_numpy(), 0])
        matrix.set_float_info("label_upper_bound", BOUNDS[training.band.to_numpy(), 1])
        model.estimator = xgb.train(parameters, matrix, num_boost_round=rounds)
        device = json.loads(model.estimator.save_config())["learner"]["generic_param"]["device"]
        if gpu and not device.startswith("cuda"):
            raise RuntimeError("CUDA silently fell back; experiment not accepted")
        model.radius = calibrate(calibration.band, model.predict(calibration))
        prediction = model.predict(test)
        lo, hi = band_sets(prediction, model.radius)
        result = {"test": metrics(test.band, prediction), "radius": model.radius,
                  "coverage": float(((test.band >= lo) & (test.band <= hi)).mean()),
                  "mean_width": float((hi - lo + 1).mean()), "seconds": time.perf_counter() - t0,
                  "device": device, "vocabulary_size": len(vectorizer.vocabulary_), "slices": {}}
        for label, mask in (("complete", ~test.skills_truncated), ("truncated", test.skills_truncated)):
            result["slices"][label] = metrics(test.band[mask], prediction[mask]) if mask.any() else None
        results[name], predictions[name] = result, prediction
        saved = test[["row_key", "group_id", "band"]].copy()
        saved["prediction"], saved["set_low"], saved["set_high"] = prediction, lo, hi
        saved.to_csv(directory / f"{name}_predictions.csv", index=False)
    test = frame[frame.split == "test"]
    report = {"source_version": manifest["source_version"], "preparation_code_hash": manifest["preparation_code_hash"],
              "evidence_hashes": before, "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "champion": salary["champion"], "rounds": rounds, "parameters": parameters,
              "variants": results, "paired_mean_band_error": paired_error_interval(test.band.to_numpy(), predictions["conservative"], predictions["permissive"], test.group_id.to_numpy()),
              "changed_token_rows": sum(list(a) != list(b) for a, b in zip(frame.skills, frame.skills_permissive, strict=True)),
              "seconds": time.perf_counter() - started,
              "versions": {k: importlib.metadata.version(k) for k in ("numpy", "scikit-learn", "xgboost")},
              "limitations": ["Post-hoc sensitivity, not a new champion search or independent external validation.",
                              "Only skill token handling changes; partitions, training settings and boosting rounds stay fixed. Preprocessing is fitted on training rows only.",
                              "Intervals resample paired test groups conditional on fitted models; they exclude retraining uncertainty.",
                              "Negative mean-band-error difference favors permissive handling. Calibration targets observed labels, not exact salaries; units remain unverified."]}
    if evidence_hashes(out) != before:
        raise RuntimeError("Protected evidence changed during the experiment; report not published")
    write_json(out / "truncation_sensitivity.json", report)
    return report
