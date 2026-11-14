"""Ordinal evaluation, finite-sample band calibration, and bounded CUDA experiments."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import subprocess
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, cohen_kappa_score, f1_score
from sklearn.preprocessing import StandardScaler

from .data import BOUNDS, write_json

NUMERIC = ["exp_min", "exp_max", "exp_width", "skills_truncated", "description_missing"]


def documents(frame: pd.DataFrame) -> list[str]:
    # Exclude salary and descriptions (which may explicitly disclose target salary).
    return [f"{t} {' '.join(s)} {loc}" for t, s, loc in
            zip(frame.job_desig, frame.skills, frame.location, strict=True)]


def metrics(y, prediction, weights=None) -> dict:
    y, prediction = np.asarray(y), np.asarray(prediction)
    qwk = cohen_kappa_score(y, prediction, labels=list(range(6)), weights="quadratic", sample_weight=weights)
    return {"qwk": float(qwk) if np.isfinite(qwk) else None,
            "macro_f1": float(f1_score(y, prediction, labels=list(range(6)), average="macro", zero_division=0, sample_weight=weights)),
            "balanced_accuracy": float(balanced_accuracy_score(y, prediction, sample_weight=weights)),
            "mean_band_error": float(np.average(abs(y - prediction), weights=weights)),
            "within_one_band": float(np.average(abs(y - prediction) <= 1, weights=weights)), "n": len(y)}


def calibrate(y, prediction, coverage: float = .9) -> int:
    scores = np.sort(np.abs(np.asarray(y, dtype=int) - np.asarray(prediction, dtype=int)))
    if not len(scores):
        raise ValueError("Calibration set is empty")
    rank = math.ceil((len(scores) + 1) * coverage)
    return int(scores[rank - 1]) if rank <= len(scores) else 5


def band_sets(prediction, radius: int) -> tuple[np.ndarray, np.ndarray]:
    p = np.asarray(prediction, dtype=int)
    return np.maximum(0, p - radius), np.minimum(5, p + radius)


def bootstrap_qwk(frame: pd.DataFrame, prediction, repeats=200) -> list[float] | None:
    rng = np.random.default_rng(31)
    ids = frame.group_id.unique()
    positions = {g: np.flatnonzero(frame.group_id.to_numpy() == g) for g in ids}
    scores = []
    for _ in range(repeats):
        idx = np.concatenate([positions[g] for g in rng.choice(ids, len(ids), replace=True)])
        score = metrics(frame.band.to_numpy()[idx], np.asarray(prediction)[idx])["qwk"]
        if score is not None:
            scores.append(score)
    return np.quantile(scores, [.025, .975]).tolist() if scores else None


class BandModel:
    def __init__(self, vectorizer, scaler, estimator, kind, radius=5):
        self.vectorizer, self.scaler, self.estimator = vectorizer, scaler, estimator
        self.kind, self.radius = kind, radius

    def features(self, frame):
        from scipy.sparse import csr_matrix, hstack
        return hstack([self.vectorizer.transform(documents(frame)),
                       csr_matrix(self.scaler.transform(frame[NUMERIC].astype(float)))], format="csr")

    def predict(self, frame):
        x = self.features(frame)
        if self.kind == "aft":
            import xgboost as xgb
            continuous = self.estimator.predict(xgb.DMatrix(x))
            return np.searchsorted(BOUNDS[:-1, 1], continuous, side="right").clip(0, 5)
        if self.kind == "soft_target":
            import xgboost as xgb
            return self.estimator.predict(xgb.DMatrix(x)).argmax(axis=1)
        return np.asarray(self.estimator.predict(x)).ravel().astype(int)


def train(out: Path, gpu: bool = True) -> dict:
    frame = pd.read_parquet(out / "analytics.parquet")
    train_set = frame[frame.split == "train"]
    valid = frame[frame.split == "validation"]
    cal = frame[frame.split == "calibration"]
    test = frame[frame.split == "test"]
    for label, part in [("train", train_set), ("validation", valid), ("calibration", cal), ("test", test)]:
        if len(part) == 0 or (label == "train" and part.band.nunique() != 6):
            raise ValueError(f"Insufficient class support in {label}; do not train")
    vectorizer = TfidfVectorizer(min_df=3, max_features=12000, ngram_range=(1, 2), sublinear_tf=True)
    vectorizer.fit(documents(train_set))
    scaler = StandardScaler().fit(train_set[NUMERIC].astype(float))
    template = BandModel(vectorizer, scaler, None, "classifier")
    x, xv = template.features(train_set), template.features(valid)
    started = time.perf_counter()
    lr = LogisticRegression(C=1, max_iter=600, random_state=31).fit(x, train_set.band)
    champion = BandModel(vectorizer, scaler, lr, "classifier")
    score = metrics(valid.band, champion.predict(valid))
    records = [{"name": "tfidf_logistic", "validation": score, "seconds": time.perf_counter() - started}]
    champion_name = "tfidf_logistic"
    best = score["qwk"]
    prior = int(train_set.band.mode().iloc[0])
    records.insert(0, {"name": "majority", "validation": metrics(valid.band, np.full(len(valid), prior))})
    hardware = {"gpu_requested": gpu}
    try:
        hardware["nvidia_smi"] = subprocess.check_output(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        hardware["nvidia_smi"] = "unavailable"
    if gpu:
        import xgboost as xgb
        # Verify a CUDA-enabled build before accepting a GPU-labelled experiment.
        if not xgb.build_info().get("USE_CUDA", False) or hardware["nvidia_smi"] == "unavailable":
            raise RuntimeError("CUDA requested but not verified; use --cpu explicitly for a CPU baseline")
        dtrain, dvalid = xgb.DMatrix(x), xgb.DMatrix(xv)
        for matrix, part in [(dtrain, train_set), (dvalid, valid)]:
            matrix.set_float_info("label_lower_bound", BOUNDS[part.band.to_numpy(), 0])
            matrix.set_float_info("label_upper_bound", BOUNDS[part.band.to_numpy(), 1])
        for depth in (3, 5):
            for scale in (.5, 1.0):
                t0 = time.perf_counter()
                params = {"objective": "survival:aft", "eval_metric": "aft-nloglik", "tree_method": "hist",
                          "device": "cuda", "max_depth": depth, "eta": .06, "seed": 31,
                          "aft_loss_distribution": "normal", "aft_loss_distribution_scale": scale}
                booster = xgb.train(params, dtrain, num_boost_round=400, evals=[(dvalid, "validation")],
                                    early_stopping_rounds=35, verbose_eval=False)
                booster = booster[:booster.best_iteration + 1]
                model = BandModel(vectorizer, scaler, booster, "aft")
                result = metrics(valid.band, model.predict(valid))
                name = f"aft_d{depth}_s{scale}"
                records.append({"name": name, "validation": result, "seconds": time.perf_counter() - t0,
                                "rounds": booster.num_boosted_rounds(), "device": "cuda"})
                if result["qwk"] is not None and result["qwk"] > best + .005:
                    champion, champion_name, best = model, name, result["qwk"]
        # Fractional cross-entropy target per TRAINING feature group, distinct from interval likelihood.
        target_table = pd.crosstab(train_set.feature_signature, train_set.band).reindex(columns=range(6), fill_value=0)
        distribution = target_table.div(target_table.sum(axis=1), axis=0)
        unique = train_set.drop_duplicates("feature_signature")
        soft_targets = distribution.loc[unique.feature_signature].to_numpy()
        ds = xgb.DMatrix(template.features(unique), label=np.zeros(len(unique)), weight=target_table.sum(axis=1).loc[unique.feature_signature])

        def soft_loss(pred, matrix):
            probability = np.exp(pred - pred.max(axis=1, keepdims=True))
            probability /= probability.sum(axis=1, keepdims=True)
            weight = matrix.get_weight()[:, None]
            return ((probability - soft_targets) * weight).ravel(), (np.maximum(2 * probability * (1 - probability), 1e-6) * weight).ravel()

        dv = xgb.DMatrix(xv, label=valid.band)
        t0 = time.perf_counter()
        soft = xgb.train({"objective": "multi:softprob", "num_class": 6, "device": "cuda", "tree_method": "hist",
                          "max_depth": 3, "eta": .06, "seed": 31, "eval_metric": "mlogloss"},
                         ds, 250, obj=soft_loss, evals=[(dv, "validation")], early_stopping_rounds=35, verbose_eval=False)
        soft = soft[:soft.best_iteration + 1]
        model = BandModel(vectorizer, scaler, soft, "soft_target")
        result = metrics(valid.band, model.predict(valid))
        records.append({"name": "soft_target", "validation": result, "device": "cuda", "seconds": time.perf_counter() - t0})
        if result["qwk"] is not None and result["qwk"] > best + .005:
            champion, champion_name, best = model, "soft_target", result["qwk"]
    champion.radius = calibrate(cal.band, champion.predict(cal))
    prediction = champion.predict(test)
    lo, hi = band_sets(prediction, champion.radius)
    covered = (test.band.to_numpy() >= lo) & (test.band.to_numpy() <= hi)
    groups = {}
    for family in sorted(test.role_family.unique()):
        mask = test.role_family.to_numpy() == family
        if mask.sum() >= 30:
            groups[family] = {"n": int(mask.sum()), "coverage": float(covered[mask].mean()), "set_width": float((hi - lo + 1)[mask].mean())}
    report = {"champion": champion_name, "selection": "validation QWK; challenger requires >0.005 gain",
              "experiments": records, "test": metrics(test.band, prediction), "qwk_ci95_group_bootstrap": bootstrap_qwk(test, prediction),
              "test_multiplicity_weighted": metrics(test.band, prediction, test.multiplicity),
              "test_complete_skills": metrics(test.band[~test.skills_truncated], prediction[~test.skills_truncated]) if (~test.skills_truncated).any() else None,
              "calibration": {"n": len(cal), "target": .9, "radius": champion.radius, "test_coverage": float(covered.mean()),
                              "mean_set_width": float((hi - lo + 1).mean()), "by_family": groups,
                              "limitation": "Marginal band-label coverage under exchangeability; not latent salary or subgroup guarantees. Correlated rows can weaken validity."},
              "hardware": hardware, "versions": {k: importlib.metadata.version(k) for k in ["numpy", "scikit-learn", "xgboost"]},
              "unit_status": "unverified", "total_seconds": time.perf_counter() - started}
    manifest = json.loads((out / "manifest.json").read_text())
    report["source_version"] = manifest["source_version"]
    report["preparation_code_hash"] = manifest["preparation_code_hash"]
    report["training_code_hash"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    report["evaluation_history"] = "Exploratory source inspection preceded this run. Test metrics are final for this fitted candidate set, not an untouched external validation."
    joblib.dump(champion, out / "band_model.joblib")
    scored = test[["row_key", "group_id", "band", "role_family"]].copy()
    scored["prediction"], scored["set_low"], scored["set_high"] = prediction, lo, hi
    scored.to_csv(out / "test_predictions.csv", index=False)
    write_json(out / "salary_report.json", report)
    return report
