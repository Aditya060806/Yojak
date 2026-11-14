import pandas as pd

from ml_pipeline.sas.planner_benchmark import evaluate_pool, scenarios


def test_exact_check_preserves_full_requirements():
    frame = pd.DataFrame({"skills": [["python", "sql"], ["sql", "excel"], ["python", "excel"]]})
    result = evaluate_pool(frame, [])
    assert result["exact_status"] == "proven"
    assert result["methods"]["exact"]["coverage"] == 3
    assert result["portfolio_gap_to_proven_optimum"] == 0
    assert all(len(m["skills"]) <= 3 for m in result["methods"].values())


def test_empty_and_zero_vocabulary_pools():
    assert evaluate_pool(pd.DataFrame({"skills": []}), [])["status"] == "empty_pool"
    result = evaluate_pool(pd.DataFrame({"skills": [[]]}), [])
    assert result["methods"]["portfolio"]["coverage"] == 0


def test_size_limit_does_not_claim_optimum():
    result = evaluate_pool(pd.DataFrame({"skills": [["a", "b"]]}), [], exact_limit=0)
    assert result["exact_status"] == "skipped_size_limit"
    assert result["portfolio_gap_to_proven_optimum"] is None
    assert "exact" not in result["methods"]


def test_scenarios_exclude_flagged_and_preserve_complete_sensitivity():
    frame = pd.DataFrame({"role_family": ["Data analyst"] * 3, "exp_min": [0] * 3, "exp_max": [10] * 3,
                          "quality_flag": [False, False, True], "skills_truncated": [False, True, False],
                          "row_key": ["b", "a", "c"]})
    cases = list(scenarios(frame))
    assert len(cases) == 18
    for profile, pool in cases:
        assert pool.row_key.tolist() == (["b"] if profile["complete_only"] else ["a", "b"])
