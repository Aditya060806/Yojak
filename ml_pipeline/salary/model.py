# ml_pipeline/salary/model.py

"""
Salary ranges for Indian postings, honestly.

Target  log(annual INR midpoint of the POSTED range), disclosed postings only.
Models  LightGBM quantile regression at alpha = 0.10, 0.50, 0.90, then
        conformalised quantile regression (CQR, Romano et al. 2019) on a calibration
        split so the P10-P90 interval reaches its 80% target coverage.
Split   by near-duplicate group: train 70 / calibration 15 / test 15.

A salary is never returned without its interval and `n_support` (disclosed postings
in the same ISCO unit group and city tier). Below MIN_SUPPORT the API says there is
not enough disclosed data instead of showing a number.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer

from app.core.settings import get_settings

QUANTILES = (0.1, 0.5, 0.9)
TARGET_COVERAGE = 0.8
MIN_SUPPORT = 20
SEED = 7
CATEGORICAL = ["isco2", "isco4", "state", "tier", "metro_region", "work_mode", "exp_band"]
NUMERIC = ["exp_min", "exp_max", "company_rating", "rating_missing", "n_tags", "n_linked_skills", "n_cities"]


def split_of(group: str) -> str:
    h = int(hashlib.sha256(f"salary{SEED}:{group}".encode()).hexdigest()[:8], 16) % 100
    return "train" if h < 70 else "cal" if h < 85 else "test"


def load_jobs() -> pd.DataFrame:
    d = get_settings().processed_data_dir / "india"
    return pd.read_parquet(d / "jobs.parquet")


@dataclass
class FeatureBuilder:
    """Fitted on training rows only; turns job rows into a numeric matrix."""

    title_vec: TfidfVectorizer | None = None
    title_svd: TruncatedSVD | None = None
    skill_vec: TfidfVectorizer | None = None
    skill_svd: TruncatedSVD | None = None
    categories: dict | None = None

    @staticmethod
    def base_frame(jobs: pd.DataFrame) -> pd.DataFrame:
        isco = jobs["isco_code"].fillna("").astype(str)
        return pd.DataFrame({
            "isco2": isco.str[:2].replace("", "NA"),
            "isco4": isco.replace("", "NA"),
            "state": jobs["primary_state"].fillna("NA"),
            "tier": jobs["primary_tier"].fillna(0).astype(int).astype(str),
            "metro_region": jobs["primary_metro_region"].fillna("none"),
            "work_mode": jobs["work_mode"].fillna("onsite"),
            "exp_band": jobs["exp_band"].fillna("NA"),
            "exp_min": jobs["exp_min"].astype(float),
            "exp_max": jobs["exp_max"].astype(float),
            "company_rating": jobs["company_rating"].astype(float),
            "rating_missing": jobs["company_rating"].isna().astype(float),
            "n_tags": jobs["n_tags"].astype(float),
            "n_linked_skills": jobs["n_linked_skills"].astype(float),
            "n_cities": jobs["n_cities"].astype(float),
        }, index=jobs.index)

    @staticmethod
    def _skill_docs(jobs: pd.DataFrame) -> list[str]:
        return [" ".join(u.rsplit("/", 1)[-1] for u in (s if s is not None else [])) + " "
                + " ".join(t.replace(" ", "_") for t in (tags if tags is not None else []))
                for s, tags in zip(jobs["skill_uris"], jobs["tags"], strict=True)]

    def fit(self, jobs: pd.DataFrame) -> FeatureBuilder:
        self.title_vec = TfidfVectorizer(ngram_range=(1, 2), min_df=3, sublinear_tf=True)
        t = self.title_vec.fit_transform(jobs["title_clean"].fillna(""))
        self.title_svd = TruncatedSVD(32, random_state=SEED).fit(t)
        self.skill_vec = TfidfVectorizer(token_pattern=r"\S+", min_df=3, sublinear_tf=True)
        s = self.skill_vec.fit_transform(self._skill_docs(jobs))
        self.skill_svd = TruncatedSVD(32, random_state=SEED).fit(s)
        base = self.base_frame(jobs)
        self.categories = {c: sorted(base[c].unique().tolist()) for c in CATEGORICAL}
        return self

    def transform(self, jobs: pd.DataFrame) -> pd.DataFrame:
        base = self.base_frame(jobs)
        for c in CATEGORICAL:
            base[c] = pd.Categorical(base[c], categories=self.categories[c])
        t = self.title_svd.transform(self.title_vec.transform(jobs["title_clean"].fillna("")))
        s = self.skill_svd.transform(self.skill_vec.transform(self._skill_docs(jobs)))
        dense = pd.DataFrame(np.hstack([t, s]), index=jobs.index,
                             columns=[f"title_{i}" for i in range(t.shape[1])] + [f"skill_{i}" for i in range(s.shape[1])])
        return pd.concat([base, dense], axis=1)


LGB_PARAMS = dict(n_estimators=600, learning_rate=0.05, num_leaves=63, min_child_samples=30,
                  subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0, verbose=-1)


def fit_quantiles(X: pd.DataFrame, y: np.ndarray, weights: np.ndarray | None = None, seed: int = SEED) -> dict:
    models = {}
    for a in QUANTILES:
        m = lgb.LGBMRegressor(objective="quantile", alpha=a, random_state=seed, **LGB_PARAMS)
        m.fit(X, y, sample_weight=weights, categorical_feature=CATEGORICAL)
        models[a] = m
    return models


def predict_quantiles(models: dict, X: pd.DataFrame) -> np.ndarray:
    """(n, 3) log-salary predictions, sorted per row so P10 <= P50 <= P90."""
    q = np.stack([models[a].predict(X) for a in QUANTILES], axis=1)
    return np.sort(q, axis=1)


def cqr_margin(q_cal: np.ndarray, y_cal: np.ndarray, coverage: float = TARGET_COVERAGE) -> float:
    """Split-conformal correction for the [P10, P90] band (Romano et al. 2019)."""
    scores = np.maximum(q_cal[:, 0] - y_cal, y_cal - q_cal[:, 2])
    n = len(scores)
    level = min(1.0, np.ceil((n + 1) * coverage) / n)
    return float(np.quantile(scores, level, method="higher"))


def pinball(y: np.ndarray, q: np.ndarray, alpha: float) -> float:
    d = y - q
    return float(np.mean(np.maximum(alpha * d, (alpha - 1) * d)))


class SalaryModel:
    """Everything the API needs: features, three quantile models, the CQR margin and support counts."""

    def __init__(self, fb: FeatureBuilder, models: dict, margin: float, support: dict[str, int], meta: dict):
        self.fb, self.models, self.margin, self.support, self.meta = fb, models, margin, support, meta

    @staticmethod
    def support_key(isco_code: object, tier: object) -> str:
        return f"{str(isco_code or 'NA')}|{int(tier) if tier == tier and tier is not None else 0}"

    def predict(self, jobs: pd.DataFrame) -> pd.DataFrame:
        q = predict_quantiles(self.models, self.fb.transform(jobs))
        lo, mid, hi = q[:, 0] - self.margin, q[:, 1], q[:, 2] + self.margin
        n = [self.support.get(self.support_key(i, t), 0) for i, t in zip(jobs["isco_code"], jobs["primary_tier"], strict=True)]
        out = pd.DataFrame({"p10": np.exp(lo), "p50": np.exp(mid), "p90": np.exp(hi), "n_support": n}, index=jobs.index)
        out["sufficient"] = out["n_support"] >= MIN_SUPPORT
        return out

    def save(self, path=None) -> None:
        path = path or get_settings().artifacts_dir / "salary" / "salary_model.joblib"
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)

    @staticmethod
    def load(path=None) -> SalaryModel:
        path = path or get_settings().artifacts_dir / "salary" / "salary_model.joblib"
        return joblib.load(path)


