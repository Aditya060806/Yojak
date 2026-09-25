# ml_pipeline/salary/evaluate.py

"""
Train the salary model and write reports/salary_eval.json.

    python -m ml_pipeline.salary.evaluate

Reports, on held-out disclosed postings:
  * P50 accuracy: MAE and median absolute % error in INR; pinball loss per quantile
  * P10-P90 coverage before and after conformal calibration (target 80%) and width
  * the same broken down by city tier and experience band
  * a baseline: median salary of the same ISCO sub-major group x tier (train data)
Selection bias (disclosed vs undisclosed postings):
  * chi-square + Cramer's V for tier, state, ISCO major group, work mode
  * standardised mean difference + KS for experience and company rating
  * a disclosure-propensity classifier (AUC; 0.5 would mean disclosure is random)
  * inverse-propensity-weighted refit: how much predictions for undisclosed jobs move
"""

from __future__ import annotations

import sys
import time

import lightgbm as lgb
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.metrics import roc_auc_score

from ml_pipeline.common import provenance, write_report
from ml_pipeline.salary.model import (
    CATEGORICAL,
    MIN_SUPPORT,
    QUANTILES,
    SEED,
    TARGET_COVERAGE,
    FeatureBuilder,
    SalaryModel,
    cqr_margin,
    fit_quantiles,
    load_jobs,
    pinball,
    predict_quantiles,
    split_of,
)


def interval_metrics(y_log: np.ndarray, q: np.ndarray, margin: float) -> dict:
    y = np.exp(y_log)
    p50 = np.exp(q[:, 1])
    raw_cov = (y_log >= q[:, 0]) & (y_log <= q[:, 2])
    lo, hi = q[:, 0] - margin, q[:, 2] + margin
    cqr_cov = (y_log >= lo) & (y_log <= hi)
    return {
        "n": int(len(y)),
        "mae_inr": round(float(np.mean(np.abs(p50 - y))), 0),
        "mdape_pct": round(float(np.median(np.abs(p50 - y) / y) * 100), 2),
        "coverage_raw": round(float(raw_cov.mean()), 4),
        "coverage_cqr": round(float(cqr_cov.mean()), 4),
        "median_width_inr_cqr": round(float(np.median(np.exp(hi) - np.exp(lo))), 0),
        "median_width_ratio_cqr": round(float(np.median(np.exp(hi) / np.exp(lo))), 3),
    }


def cramers_v(table: pd.DataFrame) -> float:
    chi2 = stats.chi2_contingency(table)[0]
    n = table.values.sum()
    r, k = table.shape
    return float(np.sqrt(chi2 / (n * (min(r, k) - 1)))) if min(r, k) > 1 else 0.0


def bias_analysis(jobs: pd.DataFrame, X: pd.DataFrame) -> dict:
    disclosed = jobs["salary_disclosed"].astype(bool)
    out: dict = {"disclosed_share": round(float(disclosed.mean()), 4), "categorical": {}, "numeric": {}}
    cats = {
        "city_tier": jobs["primary_tier"].fillna(0).astype(int).astype(str),
        "state": jobs["primary_state"].fillna("NA"),
        "isco_major_group": jobs["isco_code"].fillna("NA").astype(str).str[:1],
        "work_mode": jobs["work_mode"].fillna("NA"),
    }
    for name, col in cats.items():
        table = pd.crosstab(col, disclosed)
        chi2, pval, dof, _ = stats.chi2_contingency(table)
        share = disclosed.groupby(col).mean().round(4)
        out["categorical"][name] = {
            "chi2": round(float(chi2), 1), "dof": int(dof), "p_value": float(pval), "cramers_v": round(cramers_v(table), 4),
            "disclosure_rate_by_level": share[table.sum(axis=1) >= 200].sort_values().to_dict(),
        }
    for name in ["exp_min", "company_rating"]:
        a, b = jobs.loc[disclosed, name].dropna().astype(float), jobs.loc[~disclosed, name].dropna().astype(float)
        smd = (a.mean() - b.mean()) / np.sqrt((a.var() + b.var()) / 2)
        ks = stats.ks_2samp(a, b)
        out["numeric"][name] = {"mean_disclosed": round(float(a.mean()), 3), "mean_undisclosed": round(float(b.mean()), 3),
                                "smd": round(float(smd), 4), "ks_stat": round(float(ks.statistic), 4),
                                "ks_p_value": float(ks.pvalue)}
    # Propensity of disclosure from the same features the salary model uses (5-fold, grouped by near-duplicates).
    folds = jobs["dup_group_id"].map(lambda g: int(g[:8], 16) % 5).to_numpy()
    p = np.zeros(len(jobs))
    for f in range(5):
        tr, te = folds != f, folds == f
        clf = lgb.LGBMClassifier(n_estimators=300, learning_rate=0.05, num_leaves=31, verbose=-1, random_state=SEED)
        clf.fit(X[tr], disclosed[tr], categorical_feature=CATEGORICAL)
        p[te] = clf.predict_proba(X[te])[:, 1]
    auc = roc_auc_score(disclosed, p)
    out["propensity"] = {"model": "LightGBM, 5-fold grouped cross-fitting", "auc": round(float(auc), 4),
                         "interpretation": ("Disclosure is predictable from job features (AUC well above 0.5), so "
                                            "disclosed salaries are NOT a random sample of all postings."
                                            if auc > 0.6 else "Disclosure is only weakly predictable from job features.")}
    out["_propensity"] = p
    return out


def main() -> int:
    t0 = time.time()
    jobs = load_jobs().reset_index(drop=True)
    jobs["split"] = jobs["dup_group_id"].map(split_of)
    disclosed = jobs["salary_disclosed"].astype(bool) & jobs["salary_mid_inr"].notna()
    d = jobs[disclosed].copy()
    y = np.log(d["salary_mid_inr"].to_numpy())

    fb = FeatureBuilder().fit(d[d["split"] == "train"])
    Xd = fb.transform(d)
    tr, ca, te = (d["split"] == s for s in ("train", "cal", "test"))
    models = fit_quantiles(Xd[tr.to_numpy()], y[tr.to_numpy()])
    q_cal = predict_quantiles(models, Xd[ca.to_numpy()])
    margin = cqr_margin(q_cal, y[ca.to_numpy()])
    q_test = predict_quantiles(models, Xd[te.to_numpy()])
    y_test = y[te.to_numpy()]
    test = d[te]

    overall = interval_metrics(y_test, q_test, margin)
    overall["pinball_log"] = {str(a): round(pinball(y_test, q_test[:, i], a), 5) for i, a in enumerate(QUANTILES)}

    # Baseline: median log salary per (ISCO 2-digit x tier) on train, falling back to ISCO 2-digit, then global.
    train = d[tr]
    key = lambda df: df["isco_code"].fillna("NA").astype(str).str[:2] + "|" + df["primary_tier"].fillna(0).astype(int).astype(str)  # noqa: E731
    med_k = pd.Series(np.log(train["salary_mid_inr"].to_numpy()), index=key(train).values).groupby(level=0).median()
    med_2 = pd.Series(np.log(train["salary_mid_inr"].to_numpy()),
                      index=train["isco_code"].fillna("NA").astype(str).str[:2].values).groupby(level=0).median()
    glob = float(np.median(np.log(train["salary_mid_inr"])))
    base = np.array([med_k.get(k, med_2.get(k.split("|")[0], glob)) for k in key(test)])
    y_inr = np.exp(y_test)
    baseline = {"name": "median of same ISCO sub-major group x city tier (train)",
                "mae_inr": round(float(np.mean(np.abs(np.exp(base) - y_inr))), 0),
                "mdape_pct": round(float(np.median(np.abs(np.exp(base) - y_inr) / y_inr) * 100), 2)}

    by: dict = {"tier": {}, "exp_band": {}}
    for col, name in [("primary_tier", "tier"), ("exp_band", "exp_band")]:
        for level, idx in test.groupby(test[col].fillna(0 if col == "primary_tier" else "NA")).groups.items():
            pos = test.index.get_indexer(idx)
            if len(pos) >= 50:
                label = str(int(level)) if col == "primary_tier" else str(level)
                by[name][label] = interval_metrics(y_test[pos], q_test[pos], margin)

    # Support counts for the API: disclosed postings per (ISCO unit group, tier), train+cal only.
    fit_rows = d[tr | ca]
    support = fit_rows.groupby([fit_rows["isco_code"].fillna("NA").astype(str),
                                fit_rows["primary_tier"].fillna(0).astype(int)]).size()
    support_map = {f"{i}|{t}": int(n) for (i, t), n in support.items()}

    # Selection bias on ALL postings.
    X_all = fb.transform(jobs)
    bias = bias_analysis(jobs, X_all)
    prop = bias.pop("_propensity")
    # IPW sensitivity: refit P50 with weights 1/p (clipped), compare predictions on undisclosed jobs.
    w = 1.0 / np.clip(prop[disclosed.to_numpy()], 0.05, 1.0)
    ipw_models = fit_quantiles(Xd[tr.to_numpy()], y[tr.to_numpy()], weights=w[tr.to_numpy()])
    und = ~disclosed.to_numpy()
    p50_plain = np.exp(models[0.5].predict(X_all[und]))
    p50_ipw = np.exp(ipw_models[0.5].predict(X_all[und]))
    ipw_test = np.exp(ipw_models[0.5].predict(Xd[te.to_numpy()]))
    bias["ipw_sensitivity"] = {
        "median_pct_change_on_undisclosed_jobs": round(float(np.median((p50_ipw - p50_plain) / p50_plain) * 100), 2),
        "mean_pct_change_on_undisclosed_jobs": round(float(np.mean((p50_ipw - p50_plain) / p50_plain) * 100), 2),
        "test_mae_inr_ipw": round(float(np.mean(np.abs(ipw_test - y_inr))), 0),
        "note": ("If weighting disclosed postings to look like all postings moves predictions only a little, "
                 "the bias matters less for P50; intervals are still shown with this caveat."),
    }

    SalaryModel(fb, models, margin, support_map, {"min_support": MIN_SUPPORT, "trained_rows": int(tr.sum())}).save()

    body = {
        "target": "log of the annual INR midpoint of the posted salary range (not realised pay)",
        "training_population": "postings that disclose a plausible INR salary",
        "split": {"train": int(tr.sum()), "calibration": int(ca.sum()), "test": int(te.sum()),
                  "unit": "near-duplicate group (so reposts never straddle splits)"},
        "model": {"type": "LightGBM quantile regression", "quantiles": list(QUANTILES),
                  "calibration": "conformalised quantile regression (Romano et al. 2019)",
                  "target_coverage": TARGET_COVERAGE, "cqr_margin_log": round(margin, 4),
                  "features": "ISCO group, state, city tier, metro region, work mode, experience, company rating, "
                              "title TF-IDF SVD(32), skill TF-IDF SVD(32)"},
        "test": overall,
        "baseline": baseline,
        "by_group": by,
        "selection_bias": bias,
        "display_rule": {"min_support": MIN_SUPPORT,
                         "rule": "Always P10-P50-P90 with n_support; below min_support show 'not enough disclosed data'."},
        "seconds": round(time.time() - t0, 1),
    }
    from app.core.settings import get_settings

    prov = provenance("ml_pipeline/salary/evaluate.py", seed=SEED,
                      inputs=[get_settings().processed_data_dir / "india" / "jobs.parquet"])
    print(write_report("salary_eval", body, prov))
    print({k: overall[k] for k in ("mae_inr", "mdape_pct", "coverage_raw", "coverage_cqr")}, "baseline", baseline["mae_inr"],
          "propensity AUC", bias["propensity"]["auc"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
