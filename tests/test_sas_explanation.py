"""Synthetic proof of diagnostic contrasts, grouping and partition isolation."""
import numpy as np
import pandas as pd
import pytest

from ml_pipeline.sas.explanation import ordinal_analysis, proportional_odds_diagnostic, slope_contrasts


def test_contrasts_exclude_intercepts_and_detect_unequal_slopes():
    contrast = slope_contrasts(3, 2)
    assert contrast.shape == (4, 9)
    np.testing.assert_array_equal(contrast @ [1, 2, 3, 4, 2, 3, 7, 2, 3], np.zeros(4))
    assert np.any(contrast @ [1, 2, 3, 4, 4, 3, 7, 2, 3])


def test_diagnostic_rejects_nonparallel_synthetic_slopes():
    rng = np.random.default_rng(31)
    x = rng.uniform(-1, 1, 1800)
    # Valid ordered CDFs with opposite slopes; not a proportional-odds DGP.
    lower = 1 / (1 + np.exp(-(-1.8 + 1.5 * x)))
    upper = 1 / (1 + np.exp(-(1.8 - 1.5 * x)))
    draw = rng.random(len(x))
    y = (draw > lower).astype(int) + (draw > upper).astype(int)
    report = proportional_odds_diagnostic(pd.DataFrame({"x": x}), y, np.arange(len(x)))
    assert report["status"] == "rejected"
    assert report["p_value"] < .001
    with pytest.raises(ValueError, match="groups"):
        proportional_odds_diagnostic(pd.DataFrame({"x": x}), y, np.zeros(len(x)))


def test_explanation_never_reads_heldout_features():
    rng = np.random.default_rng(42)
    n = 450
    exp = rng.uniform(0, 10, n)
    skills = [["python"] + (["statistics"] if a else []) + (["modelling"] if b else [])
              + (["sql", "excel"] if c else []) for a, b, c in rng.integers(0, 2, (n, 3))]
    latent = .2 * exp + rng.logistic(size=n)
    frame = pd.DataFrame({"split": "train", "exp_mid": exp, "skills": skills,
                          "band": np.digitize(latent, [-1, 0, 1, 2, 3]), "group_id": np.arange(n)})
    report = ordinal_analysis(frame)
    heldout = pd.DataFrame({"split": ["test", "calibration", "validation"], "exp_mid": [None] * 3,
                            "skills": [None] * 3, "band": [99] * 3, "group_id": [-1] * 3})
    second = ordinal_analysis(pd.concat([frame, heldout], ignore_index=True))
    assert report == second
    assert report["n"] == n
    assert "group-clustered" in report["interval_limitation"]
