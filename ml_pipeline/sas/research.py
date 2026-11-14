"""Aggregate analyses, never employee-level hiring or promotion scores."""
from __future__ import annotations

from collections import Counter
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import pointbiserialr, spearmanr
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, mean_absolute_error, roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier
from statsmodels.stats.multitest import multipletests

from .data import BOUNDS, normalize, write_json
from .explanation import ordinal_analysis


def cohort(frame: pd.DataFrame, name: str, repeats=200) -> dict:
    original = [c for c in frame if c not in {"row_key", "group_id", "split"}]
    target = original[-1]
    features = [c for c in original[:-1] if c != "id"]
    x, y, groups = frame[features].astype(float), frame[target].astype(int).to_numpy(), frame.group_id.to_numpy()
    split_count = min(5, min(len(set(groups[y == c])) for c in [0, 1]))
    if split_count < 2:
        raise ValueError(f"Insufficient grouped class support for {name}")
    estimates, trees = np.zeros(len(y)), np.zeros(len(y))
    fold_metrics = []
    for a, b in StratifiedGroupKFold(split_count, shuffle=True, random_state=31).split(x, y, groups):
        inner_n = min(3, min(len(set(groups[a][y[a] == c])) for c in [0, 1]))
        candidates = []
        for c in [.1, 1, 10]:
            scores = []
            if inner_n >= 2:
                for ia, ib in StratifiedGroupKFold(inner_n, shuffle=True, random_state=32).split(x.iloc[a], y[a], groups[a]):
                    if len(np.unique(y[a][ia])) < 2 or len(np.unique(y[a][ib])) < 2:
                        continue
                    model = make_pipeline(StandardScaler(), LogisticRegression(C=c, max_iter=1000))
                    model.fit(x.iloc[a[ia]], y[a][ia])
                    scores.append(roc_auc_score(y[a][ib], model.predict_proba(x.iloc[a[ib]])[:, 1]))
            candidates.append((float(np.mean(scores)) if scores else 0, -c))
        selected = -max(candidates)[1]
        model = make_pipeline(StandardScaler(), LogisticRegression(C=selected, max_iter=1000)).fit(x.iloc[a], y[a])
        estimates[b] = model.predict_proba(x.iloc[b])[:, 1]
        tree = DecisionTreeClassifier(max_depth=2, min_samples_leaf=10, random_state=31).fit(x.iloc[a], y[a])
        trees[b] = tree.predict_proba(x.iloc[b])[:, 1]
        fold_metrics.append({"train": len(a), "test": len(b), "selected_C": selected})
    rng = np.random.default_rng(31)
    unique = np.unique(groups)
    indices = {g: np.flatnonzero(groups == g) for g in unique}
    coeff, aucs = [], []
    for _ in range(repeats):
        idx = np.concatenate([indices[g] for g in rng.choice(unique, len(unique), replace=True)])
        if len(np.unique(y[idx])) < 2:
            continue
        # Native-score odds ratios; fixed penalization for descriptive stability, not unpenalized inference.
        fit = LogisticRegression(C=1, max_iter=1000).fit(x.iloc[idx], y[idx])
        coeff.append(fit.coef_[0])
        aucs.append(roc_auc_score(y[idx], estimates[idx]))
    fit = LogisticRegression(C=1, max_iter=1000).fit(x, y)
    association = [pointbiserialr(y, x[c]) for c in features]
    adjusted = multipletests([r.pvalue for r in association], method="fdr_bh")[1]
    ci = np.exp(np.quantile(np.asarray(coeff), [.025, .975], axis=0))
    rows = [{"feature": f, "correlation": float(association[i].statistic), "p_fdr": float(adjusted[i]),
             "odds_ratio_native_unit": float(np.exp(fit.coef_[0, i])), "or_ci95": ci[:, i].tolist()}
            for i, f in enumerate(features)]
    return {"cohort": name, "n": len(frame), "groups": len(unique), "class_counts": np.bincount(y).tolist(),
            "features": rows, "oof_auc": float(roc_auc_score(y, estimates)),
            "oof_auc_ci95": np.quantile(aucs, [.025, .975]).tolist(),
            "oof_balanced_accuracy": float(balanced_accuracy_score(y, estimates >= .5)),
            "tree_oof_auc": float(roc_auc_score(y, trees)), "folds": fold_metrics,
            "interpretation": "Exploratory cohort associations, not causal effects or individual employment predictions. Bootstrap intervals condition on this model family; OOF interval is not full nested resampling."}


def association_rules(frame: pd.DataFrame) -> list[dict]:
    rows = []
    for family, part in frame.groupby("role_family"):
        n = len(part)
        singles, pairs = Counter(), Counter()
        for skills in part.skills:
            values = sorted(set(skills))
            singles.update(values)
            pairs.update(combinations(values, 2))
        for (a, b), count in pairs.items():
            if count < max(20, int(.01 * n)):
                continue
            for left, right in [(a, b), (b, a)]:
                rows.append({"family": family, "antecedent": left, "consequent": right, "count": count,
                             "support": count / n, "confidence": count / singles[left],
                             "lift": count * n / (singles[left] * singles[right])})
    return sorted(rows, key=lambda r: (-r["lift"], -r["count"]))[:80]


def company_analysis(frame: pd.DataFrame, analytics: pd.DataFrame) -> dict:
    import statsmodels.formula.api as smf
    frame = frame.copy()
    frame["log_pay"] = np.log(frame.avg_salary_native)
    frame["experience_value"] = pd.to_numeric(frame.min_experience)
    training, test = frame[frame.split == "train"], frame[frame.split == "test"]
    baseline = test.job_title.map(training.groupby("job_title").avg_salary_native.median()).fillna(training.avg_salary_native.median())
    report = {"heldout_company_baseline_mae_native": float(mean_absolute_error(test.avg_salary_native, baseline)),
              "heldout_rows": len(test), "unit_status": "unverified"}
    try:
        fit = smf.mixedlm("log_pay ~ C(job_title) + experience_value", training, groups=training.company_key).fit(method="lbfgs", disp=False)
        prediction = np.exp(fit.predict(test))
        variance = float(fit.cov_re.iloc[0, 0])
        report.update({"converged": bool(fit.converged), "heldout_company_mae_native": float(mean_absolute_error(test.avg_salary_native, prediction)),
                       "company_residual_icc": variance / (variance + float(fit.scale)),
                       "icc_interpretation": "Company random-intercept variance / company plus residual variance, conditional on fixed effects; not causal employer contribution"})
    except (ValueError, np.linalg.LinAlgError) as exc:
        report["mixed_model_status"] = type(exc).__name__
    weighted = smf.wls("log_pay ~ C(job_title) + experience_value", training, weights=training.num_of_jobs).fit()
    report["weighted_fixed_effect_sensitivity_mae_native"] = float(mean_absolute_error(test.avg_salary_native, np.exp(weighted.predict(test))))
    def key(s):
        return normalize(s).replace(" ", "")
    analytics = analytics.copy()
    analytics["title_key"] = analytics.job_desig.map(key)
    analytics["midpoint_proxy"] = BOUNDS[analytics.band.to_numpy()].mean(axis=1)
    frame["title_key"] = frame.job_title.map(key)
    cross = frame.groupby("title_key").avg_salary_native.mean().to_frame("company_average")
    cross = cross.join(analytics.groupby("title_key").midpoint_proxy.agg(["mean", "count"])).dropna()
    report["cross_file"] = {"titles": cross.reset_index().to_dict("records"),
                            "spearman": float(spearmanr(cross.company_average, cross["mean"]).statistic) if len(cross) > 2 else None,
                            "limitation": "Ecological plausibility check using band midpoint proxies; not external validation, proof of units, or matched workers."}
    return report


def analyze(out: Path) -> dict:
    analytics = pd.read_parquet(out / "analytics.parquet")
    result = {name: cohort(pd.read_parquet(out / f"{name}.parquet"), name) for name in ["jds", "sds"]}
    result["rules_including_flagged"] = association_rules(analytics)
    result["rules_excluding_flagged"] = association_rules(analytics[~analytics.quality_flag])
    result["company"] = company_analysis(pd.read_parquet(out / "company.parquet"), analytics)
    result["ordinal"] = ordinal_analysis(analytics)
    result["role_families"] = analytics.role_family.value_counts().to_dict()
    result["manual_role_review"] = "pending; role_review.csv must be independently reviewed"
    write_json(out / "research_report.json", result)
    return result
