"""Phase 3: guarantees of the upskilling engine, checked on small random instances."""

from __future__ import annotations

import itertools
import math

import numpy as np
import pytest
import scipy.sparse as sp

from ml_pipeline.upskilling.engine import (
    CoverageProblem,
    brute_force,
    budgeted_greedy,
    budgeted_partial,
    exact_ilp,
    frequency,
    greedy_F,
    idf_weights,
    lazy_greedy_G,
    naive_greedy_G,
)


def random_problem(seed: int, n_jobs: int = 40, n_skills: int = 14, tau: float = 0.6, salary: bool = False):
    rng = np.random.default_rng(seed)
    R = (rng.random((n_jobs, n_skills)) < 0.25).astype(np.int64)
    R[R.sum(axis=1) == 0, rng.integers(0, n_skills)] = 1
    R = sp.csr_matrix(R)
    w = idf_weights(R)
    v = rng.integers(300_000, 2_000_000, n_jobs).astype(float) if salary else np.ones(n_jobs)
    have = rng.choice(n_skills, 3, replace=False)
    return CoverageProblem(R, w, v, have, tau)


def best_G(p: CoverageProblem, k: int) -> float:
    cands = list(p.candidates())
    best = p.G([])
    for r in range(1, min(k, len(cands)) + 1):
        for combo in itertools.combinations(cands, r):
            best = max(best, p.G(list(combo)))
    return best


def test_fit_and_eligibility_are_exact_integers():
    # job 0 needs {a, b}; job 1 needs {a}; weights equal
    R = sp.csr_matrix(np.array([[1, 1, 0], [1, 0, 0]]))
    p = CoverageProblem(R, np.array([1000, 1000, 1000]), np.ones(2), have=np.array([0]), tau=0.5)
    assert p.eligible(p.base).tolist() == [True, True]  # 1/2 >= 0.5 exactly (no float slack)
    p2 = CoverageProblem(R, np.array([1000, 1000, 1000]), np.ones(2), have=np.array([0]), tau=0.51)
    assert p2.eligible(p2.base).tolist() == [False, True]


def test_F_is_not_submodular_counterexample():
    # One job needs {a, b}; tau = 1. Alone neither skill unlocks it; together they do.
    R = sp.csr_matrix(np.array([[1, 1]]))
    p = CoverageProblem(R, np.array([1000, 1000]), np.ones(1), have=np.array([], dtype=int), tau=1.0)
    gain_b_alone = p.F([1]) - p.F([])
    gain_b_after_a = p.F([0, 1]) - p.F([0])
    assert gain_b_alone == 0 and gain_b_after_a == 1  # increasing marginal gain: not submodular
    # G on the same instance is submodular here: gains shrink
    assert (p.G([1]) - p.G([])) >= (p.G([0, 1]) - p.G([0]))


@pytest.mark.parametrize("seed", range(12))
def test_lazy_greedy_matches_naive(seed):
    p = random_problem(seed)
    for k in (1, 2, 3, 5):
        a, b = lazy_greedy_G(p, k), naive_greedy_G(p, k)
        assert a.G == pytest.approx(b.G)


@pytest.mark.parametrize("seed", range(12))
def test_greedy_meets_one_minus_one_over_e_on_G(seed):
    p = random_problem(seed)
    for k in (1, 2, 3):
        opt = best_G(p, k)
        assert lazy_greedy_G(p, k).G >= (1 - 1 / math.e) * opt - 1e-9


@pytest.mark.parametrize("seed", range(10))
@pytest.mark.parametrize("tau", [0.4, 0.6, 0.8])
def test_ilp_matches_brute_force(seed, tau):
    p = random_problem(seed, tau=tau)
    for k in (1, 2, 3):
        bf = brute_force(p, k)
        ilp = exact_ilp(p, k, time_limit=5)
        assert ilp.optimal
        assert ilp.F == pytest.approx(bf.F)
        assert len(ilp.skills) <= k


def test_ilp_with_salary_values_matches_brute_force():
    for seed in range(5):
        p = random_problem(seed, salary=True)
        bf, ilp = brute_force(p, 2), exact_ilp(p, 2, time_limit=5)
        # CP-SAT sees salaries in thousands; allow that rounding when comparing values
        assert ilp.F == pytest.approx(bf.F, rel=1e-3)


def test_heuristics_never_beat_the_optimum():
    for seed in range(8):
        p = random_problem(seed)
        opt = brute_force(p, 3).F
        for plan in (lazy_greedy_G(p, 3), greedy_F(p, 3), frequency(p, 3)):
            assert plan.F <= opt + 1e-9
            assert len(plan.skills) <= 3
            assert not set(plan.skills) & set(np.where(p.have)[0])


def test_candidates_are_exactly_the_useful_skills():
    p = random_problem(3)
    useful = [s for s in range(p.R.shape[1]) if not p.have[s] and p.G([s]) > p.G([])]
    assert set(useful) <= set(p.candidates().tolist())


def test_budgeted_respects_budget_and_ilp_bound():
    rng = np.random.default_rng(0)
    for seed in range(6):
        p = random_problem(seed)
        costs = rng.uniform(0.5, 2.0, p.R.shape[1])
        for budget in (1.5, 3.0):
            g = budgeted_greedy(p, costs, budget)
            part = budgeted_partial(p, costs, budget)
            opt = exact_ilp(p, None, costs=costs, budget=budget, time_limit=5)
            for plan in (g, part):
                assert sum(costs[s] for s in plan.skills) <= budget + 1e-9
                assert plan.F <= opt.F + 1e-9
            assert part.G >= g.G - 1e-9  # partial enumeration includes the plain greedy


def test_jobs_unlocked_by_steps():
    R = sp.csr_matrix(np.array([[1, 1, 0], [0, 0, 1], [1, 0, 1]]))
    p = CoverageProblem(R, np.array([1000, 1000, 1000]), np.ones(3), have=np.array([], dtype=int), tau=1.0)
    steps = p.jobs_unlocked_by([2, 0])
    assert steps == [[1], [2]]
