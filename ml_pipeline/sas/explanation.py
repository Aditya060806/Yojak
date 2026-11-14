"""Training-only salary associations with cluster-aware assumption diagnostics."""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.miscmodels.ordinal_model import OrderedModel
from statsmodels.stats.multitest import multipletests


def slope_contrasts(thresholds: int, predictors: int) -> np.ndarray:
    """Compare each cumulative-logit slope with its first-threshold slope."""
    contrasts = []
    for feature in range(predictors):
        for threshold in range(1, thresholds):
            row = np.zeros(thresholds * (predictors + 1))
            row[threshold * (predictors + 1) + feature + 1] = 1
            row[feature + 1] = -1
            contrasts.append(row)
    return np.asarray(contrasts)


def proportional_odds_diagnostic(x: pd.DataFrame, y: np.ndarray, groups: np.ndarray) -> dict:
    """Working-independence stacked logits, sandwich clustered by original groups.

    The sandwich retains dependence between thresholds and between observations
    in the same group. This is an asymptotic slope-equality Wald diagnostic,
    not the classical independent-observation Brant implementation.
    """
    levels = np.unique(y)
    if not np.array_equal(levels, np.arange(len(levels))) or len(levels) < 3:
        raise ValueError("Diagnostic requires at least three contiguous band labels")
    if len(np.unique(groups)) <= (len(levels) - 2) * x.shape[1]:
        raise ValueError("Insufficient independent groups for slope contrasts")
    thresholds = len(levels) - 1
    design = sm.add_constant(x, has_constant="add").to_numpy()
    stacked = np.kron(np.eye(thresholds), design)
    targets = np.concatenate([(y > threshold).astype(int) for threshold in range(thresholds)])
    fit = sm.GLM(targets, stacked, family=sm.families.Binomial()).fit(
        maxiter=100, cov_type="cluster", cov_kwds={"groups": np.tile(groups, thresholds)})
    contrasts = slope_contrasts(thresholds, x.shape[1])
    covariance = contrasts @ fit.cov_params() @ contrasts.T
    if not fit.converged or not np.isfinite(covariance).all() or np.linalg.matrix_rank(covariance) < len(contrasts):
        return {"status": "inconclusive", "reason": "Nonconvergence or rank-deficient contrast covariance"}
    joint = fit.wald_test(contrasts, scalar=True)
    feature_tests = []
    for i, feature in enumerate(x.columns):
        test = fit.wald_test(contrasts[i * (thresholds - 1):(i + 1) * (thresholds - 1)], scalar=True)
        feature_tests.append({"feature": feature, "p_value": float(test.pvalue)})
    for row, adjusted in zip(feature_tests, multipletests([r["p_value"] for r in feature_tests], method="fdr_bh")[1], strict=True):
        row["p_fdr"] = float(adjusted)
    return {"status": "rejected" if joint.pvalue < .05 else "not_rejected", "alpha": .05,
            "statistic": float(joint.statistic), "df": len(contrasts), "p_value": float(joint.pvalue),
            "feature_tests": feature_tests, "threshold_slopes": fit.params.reshape(thresholds, -1)[:, 1:].tolist(),
            "method": "Stacked cumulative logits; group-clustered sandwich Wald slope-equality test",
            "limitation": "Asymptotic, conditional on this low-dimensional specification and independent groups. Non-rejection is not proof of proportional odds."}


def ordinal_analysis(frame: pd.DataFrame) -> dict:
    train = frame.loc[frame.split == "train"]
    features = pd.DataFrame({"experience": train.exp_mid.to_numpy(), "skill_count": train.skills.map(len).to_numpy(),
                             "statistics": train.skills.map(lambda s: int(any("stat" in x for x in s))).to_numpy(),
                             "modelling": train.skills.map(lambda s: int(any("model" in x for x in s))).to_numpy()})
    y, groups = train.band.to_numpy(), train.group_id.to_numpy()
    report = {"status": "exploratory", "n": len(train), "groups": len(np.unique(groups)),
              "partition": "train", "features": list(features), "unit_status": "unverified",
              "analysis_code_hash": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "interpretation": "Conditional associations with observed salary bands, not causal pay effects or exact-salary estimates.",
              "interval_limitation": "Asymptotic group-clustered sandwich intervals assume independent groups; no protection against omitted variables or heuristic skill measurement."}
    diagnostic = proportional_odds_diagnostic(features, y, groups)
    report["proportional_odds"] = diagnostic
    fit = OrderedModel(y, features, distr="logit").fit(
        method="bfgs", maxiter=300, disp=False, cov_type="cluster", cov_kwds={"groups": groups})
    conf = fit.conf_int()
    report["coefficients"] = [{"feature": f, "odds_ratio": float(np.exp(fit.params[f])),
                               "ci95": np.exp(conf.loc[f]).tolist()} for f in features]
    report["converged"] = bool(fit.mle_retvals["converged"])
    report["assumption_status"] = diagnostic["status"]
    report["primary_model"] = "proportional_odds" if diagnostic["status"] == "not_rejected" and report["converged"] else "multinomial_logit"
    report["common_effects_status"] = "exploratory_primary" if report["primary_model"] == "proportional_odds" else "diagnostic_only_not_primary"
    if report["primary_model"] == "multinomial_logit":
        model = sm.MNLogit(y, sm.add_constant(features)).fit(
            method="newton", maxiter=200, disp=False, cov_type="cluster", cov_kwds={"groups": groups})
        coefficients, errors = np.asarray(model.params), np.asarray(model.bse)
        converged = bool(model.mle_retvals["converged"]) and np.isfinite(coefficients).all() and np.isfinite(errors).all()
        report["multinomial"] = {"converged": converged, "reference_band": 0,
                                 "interpretation": "Band-specific relative probability ratios versus band 0, per native feature unit; not common cumulative odds ratios.",
                                 "coefficients": []}
        if converged:
            for band in range(coefficients.shape[1]):
                for i, feature in enumerate(["intercept", *features]):
                    beta, se = coefficients[i, band], errors[i, band]
                    report["multinomial"]["coefficients"].append({"band": band + 1, "feature": feature,
                        "log_relative_ratio": float(beta), "log_ci95": [float(beta - 1.96 * se), float(beta + 1.96 * se)]})
        else:
            report["status"] = "inconclusive"
    return report
