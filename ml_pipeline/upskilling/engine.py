# ml_pipeline/upskilling/engine.py

"""
Upskilling as weighted maximum coverage.

A person has skills S and targets a pool of jobs J. Each job j requires skills R_j,
each skill s has an integer weight w_s (IDF x 1000, so rare skills count more).

  fit(S, j) = sum(w_s for s in R_j & S) / sum(w_s for s in R_j)
  job j is ELIGIBLE when fit(S, j) >= tau

Choose A (|A| <= k, or cost(A) <= budget) to maximise

  F(A) = sum_j v_j * [fit(S u A, j) >= tau]           true objective  (NOT submodular)
  G(A) = sum_j v_j * min(1, fit(S u A, j) / tau)       surrogate       (monotone submodular)

v_j = 1 counts jobs; v_j = predicted median salary weights them by pay.
All arithmetic is integer, so every algorithm and the exact ILP agree on F exactly.

Algorithms
  lazy_greedy_G     lazy greedy on G: (1 - 1/e) approximation of max G (Nemhauser et al. 1978)
  greedy_F          plain greedy on F (no guarantee; ties broken by G gain)
  frequency         top-k skills by how many pool jobs list them (what most tools do)
  exact_ilp         OR-Tools CP-SAT optimum of F (also budgeted)
  brute_force       enumeration, for tiny instances / cross-checking
  budgeted_greedy   cost-benefit greedy + best singleton ((1 - 1/e)/2 on G, Khuller et al. 1999)
  budgeted_partial  partial enumeration (all feasible sets of size <= 2 extended greedily);
                    Sviridenko (2004) needs size 3 for the full (1 - 1/e); size 2 is the
                    practical variant and its gap to the ILP optimum is measured, not assumed.
"""

from __future__ import annotations

import heapq
import itertools
import time
from dataclasses import dataclass

import numpy as np
import scipy.sparse as sp

WEIGHT_SCALE = 1000
TAU_SCALE = 100  # tau as an integer percentage


@dataclass
class Plan:
    skills: list[int]
    F: float
    G: float
    seconds: float
    optimal: bool | None = None  # ILP only: proven optimal within the time limit
    cost: float | None = None
    bound: float | None = None   # ILP only: proven upper bound on the optimum of F


class CoverageProblem:
    """One instance: a job pool, integer skill weights, a person's skills and a threshold."""

    def __init__(self, R: sp.csr_matrix, weights: np.ndarray, values: np.ndarray, have: np.ndarray, tau: float):
        self.R = R.tocsr().astype(np.int64)
        self.Rc = self.R.tocsc()
        self.w = np.asarray(weights, dtype=np.int64)
        self.v = np.asarray(values, dtype=np.float64)
        self.tau_pct = int(round(tau * TAU_SCALE))
        self.W = self.R @ self.w                                  # total weight per job
        self.need = self.tau_pct * self.W                         # eligibility: TAU_SCALE * covered >= need
        have_mask = np.zeros(self.R.shape[1], dtype=bool)
        have_mask[np.asarray(have, dtype=np.int64)] = True
        self.have = have_mask
        self.base = self.R @ (self.w * have_mask)                  # covered weight from S
        self.valid = self.W > 0

    # --- objectives ------------------------------------------------------------------------------

    def covered(self, add: list[int]) -> np.ndarray:
        c = self.base.copy()
        for s in add:
            if not self.have[s]:
                col = self.Rc[:, s]
                c[col.indices] += self.w[s]
        return c

    def eligible(self, c: np.ndarray) -> np.ndarray:
        return self.valid & (TAU_SCALE * c >= self.need)

    def F(self, add: list[int]) -> float:
        return float(self.v[self.eligible(self.covered(add))].sum())

    def G(self, add: list[int]) -> float:
        c = self.covered(add)
        ratio = np.where(self.need > 0, TAU_SCALE * c / np.maximum(self.need, 1), 0.0)
        return float((self.v * np.minimum(1.0, ratio))[self.valid].sum())

    def candidates(self) -> np.ndarray:
        """Skills that can change F: missing skills of jobs that could still become eligible."""
        open_jobs = np.where(self.valid & ~self.eligible(self.base))[0]
        skills = np.unique(self.R[open_jobs].indices)
        return skills[~self.have[skills]]

    def _gain_G(self, s: int, c: np.ndarray) -> float:
        col = self.Rc[:, s]
        j = col.indices
        need = np.maximum(self.need[j], 1)
        before = np.minimum(1.0, TAU_SCALE * c[j] / need)
        after = np.minimum(1.0, TAU_SCALE * (c[j] + self.w[s]) / need)
        return float((self.v[j] * (after - before) * self.valid[j]).sum())

    def _gain_F(self, s: int, c: np.ndarray) -> float:
        col = self.Rc[:, s]
        j = col.indices
        before = TAU_SCALE * c[j] >= self.need[j]
        after = TAU_SCALE * (c[j] + self.w[s]) >= self.need[j]
        return float((self.v[j] * (after & ~before) * self.valid[j]).sum())

    def gains(self, c: np.ndarray, cands: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """
        Marginal gains (F, G) of adding each candidate to the current coverage `c`, all at once:
        one pass over the candidate columns' non-zeros instead of a Python loop per skill.
        """
        cands = np.asarray(cands, dtype=np.int64)
        if len(cands) == 0:
            return np.zeros(0), np.zeros(0)
        sub = self.Rc[:, cands]
        rows = sub.indices
        col = np.repeat(np.arange(len(cands)), np.diff(sub.indptr))
        ws = self.w[cands][col]
        need = self.need[rows]
        cj = c[rows]
        v = self.v[rows] * self.valid[rows]
        before_ok = TAU_SCALE * cj >= need
        after_ok = TAU_SCALE * (cj + ws) >= need
        gf = np.bincount(col, weights=v * (after_ok & ~before_ok), minlength=len(cands))
        denom = np.maximum(need, 1)
        gg_pair = v * (np.minimum(1.0, TAU_SCALE * (cj + ws) / denom) - np.minimum(1.0, TAU_SCALE * cj / denom))
        gg = np.bincount(col, weights=gg_pair, minlength=len(cands))
        return gf, gg

    def jobs_unlocked_by(self, add: list[int]) -> list[list[int]]:
        """For each step of a plan: the jobs that become eligible at that step (for 'why' panels)."""
        out, prev = [], self.eligible(self.base)
        for i in range(len(add)):
            now = self.eligible(self.covered(add[: i + 1]))
            out.append(np.where(now & ~prev)[0].tolist())
            prev = now
        return out


# --- cardinality-constrained algorithms --------------------------------------------------------------

def lazy_greedy_G(p: CoverageProblem, k: int, cands: np.ndarray | None = None) -> Plan:
    t0 = time.perf_counter()
    cands = p.candidates() if cands is None else cands
    c = p.base.copy()
    _, g0 = p.gains(c, cands)
    heap = [(-float(g), int(s), 0) for s, g in zip(cands, g0, strict=True)]
    heapq.heapify(heap)
    chosen: list[int] = []
    while heap and len(chosen) < k:
        neg, s, stamp = heapq.heappop(heap)
        if stamp == len(chosen):  # gain is up to date: take it
            if -neg <= 0:
                break
            chosen.append(s)
            c[p.Rc[:, s].indices] += p.w[s]
        else:  # stale: recompute and push back (gains only shrink, by submodularity)
            heapq.heappush(heap, (-p._gain_G(s, c), s, len(chosen)))
    return Plan(chosen, p.F(chosen), p.G(chosen), time.perf_counter() - t0)


def naive_greedy_G(p: CoverageProblem, k: int, cands: np.ndarray | None = None) -> Plan:
    """Reference implementation (for tests): recompute every gain every round."""
    t0 = time.perf_counter()
    cands = list(p.candidates() if cands is None else cands)
    chosen: list[int] = []
    c = p.base.copy()
    for _ in range(k):
        gains = [(p._gain_G(s, c), -s) for s in cands if s not in chosen]
        if not gains:
            break
        g, neg_s = max(gains)
        if g <= 0:
            break
        chosen.append(-neg_s)
        c[p.Rc[:, -neg_s].indices] += p.w[-neg_s]
    return Plan(chosen, p.F(chosen), p.G(chosen), time.perf_counter() - t0)


def greedy_F(p: CoverageProblem, k: int, cands: np.ndarray | None = None) -> Plan:
    """Greedy on the true objective F; ties (common when no single skill completes a job) broken by G gain."""
    t0 = time.perf_counter()
    cands = np.asarray(p.candidates() if cands is None else cands, dtype=np.int64)
    chosen: list[int] = []
    c = p.base.copy()
    alive = np.ones(len(cands), dtype=bool)
    for _ in range(k):
        if not alive.any():
            break
        gf, gg = p.gains(c, cands)
        gf, gg = np.where(alive, gf, -1.0), np.where(alive, gg, -1.0)
        best = int(np.lexsort((gg, gf))[-1])  # max F gain, then max G gain
        if gg[best] <= 0 and gf[best] <= 0:
            break
        s_ = int(cands[best])
        chosen.append(s_)
        alive[best] = False
        c[p.Rc[:, s_].indices] += p.w[s_]
    return Plan(chosen, p.F(chosen), p.G(chosen), time.perf_counter() - t0)


def frequency(p: CoverageProblem, k: int) -> Plan:
    """The usual advice: the k skills listed by the most jobs in the pool that you don't have."""
    t0 = time.perf_counter()
    counts = np.asarray((p.R.multiply(p.v[:, None])).sum(axis=0)).ravel()
    counts[p.have] = -1
    order = np.argsort(-counts, kind="stable")
    chosen = [int(s) for s in order[:k] if counts[s] > 0]
    return Plan(chosen, p.F(chosen), p.G(chosen), time.perf_counter() - t0)


def brute_force(p: CoverageProblem, k: int, cands: np.ndarray | None = None) -> Plan:
    t0 = time.perf_counter()
    cands = list(p.candidates() if cands is None else cands)
    best, best_f = [], p.F([])
    for r in range(1, min(k, len(cands)) + 1):
        for combo in itertools.combinations(cands, r):
            f = p.F(list(combo))
            if f > best_f:
                best, best_f = list(combo), f
    return Plan(best, best_f, p.G(best), time.perf_counter() - t0, optimal=True)


def exact_ilp(p: CoverageProblem, k: int | None = None, costs: np.ndarray | None = None,
              budget: float | None = None, time_limit: float = 10.0, cands: np.ndarray | None = None,
              hint: list[int] | None = None) -> Plan:
    """
    max  sum_j v_j y_j
    s.t. TAU_SCALE * (base_j + sum_{s in R_j, s missing} w_s x_s) >= need_j * y_j   for every job j
         sum_s x_s <= k            (or sum_s cost_s x_s <= budget)
    x, y binary. Only jobs that are not yet eligible but could become so are modelled.
    """
    from ortools.sat.python import cp_model

    t0 = time.perf_counter()
    cands = p.candidates() if cands is None else cands
    already = p.eligible(p.base)
    m = cp_model.CpModel()
    x = {int(s): m.NewBoolVar(f"x{s}") for s in cands}
    obj = []
    # CP-SAT needs integer coefficients: counts stay as they are, rupee values go to thousands.
    scale_v = 1.0 if np.allclose(p.v, np.round(p.v)) else 1e-3
    for j in np.where(p.valid & ~already)[0]:
        row = p.R[j].indices
        terms = [(int(TAU_SCALE * p.w[s]), x[int(s)]) for s in row if int(s) in x]
        best_possible = TAU_SCALE * p.base[j] + sum(c for c, _ in terms)
        if not terms or best_possible < p.need[j]:
            continue
        y = m.NewBoolVar(f"y{j}")
        m.Add(int(TAU_SCALE * p.base[j]) + sum(c * v for c, v in terms) >= int(p.need[j]) * y)
        obj.append((int(round(p.v[j] * scale_v)), y))
    if k is not None:
        m.Add(sum(x.values()) <= k)
    if budget is not None and costs is not None:
        cs = {s: int(round(costs[s] * 100)) for s in x}
        m.Add(sum(cs[s] * x[s] for s in x) <= int(round(budget * 100)))
    m.Maximize(sum(c * y for c, y in obj))
    for s_, var in x.items():  # warm start (e.g. the greedy plan): the solver never returns worse
        m.AddHint(var, 1 if hint and s_ in hint else 0)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_workers = 8
    status = solver.Solve(m)
    chosen = [s for s, var in x.items() if status in (cp_model.OPTIMAL, cp_model.FEASIBLE) and solver.Value(var)]
    if hint is not None and p.F(list(hint)) > p.F(chosen):  # the hint is itself a feasible plan
        chosen = list(hint)
    already_v = float(p.v[already].sum())
    bound = (already_v + solver.BestObjectiveBound() / scale_v) if status in (cp_model.OPTIMAL, cp_model.FEASIBLE) else None
    return Plan(chosen, p.F(chosen), p.G(chosen), time.perf_counter() - t0, optimal=status == cp_model.OPTIMAL,
                cost=float(sum(costs[s] for s in chosen)) if costs is not None else None, bound=bound)


# --- budgeted (effort-aware) ---------------------------------------------------------------------------

def budgeted_greedy(p: CoverageProblem, costs: np.ndarray, budget: float, cands: np.ndarray | None = None,
                    start: list[int] | None = None) -> Plan:
    """Cost-benefit greedy on G, then compared with the best single affordable skill."""
    t0 = time.perf_counter()
    cands = np.asarray(p.candidates() if cands is None else cands, dtype=np.int64)
    chosen = list(start or [])
    spent = float(sum(costs[s] for s in chosen))
    c = p.covered(chosen)
    alive = ~np.isin(cands, chosen)
    cc = np.maximum(costs[cands], 1e-9)
    while True:
        affordable = alive & (spent + costs[cands] <= budget + 1e-9)
        if not affordable.any():
            break
        _, gg = p.gains(c, cands)
        ratio = np.where(affordable, gg / cc, -1.0)
        best = int(np.argmax(ratio))
        if ratio[best] <= 0:
            break
        s_ = int(cands[best])
        chosen.append(s_)
        alive[best] = False
        spent += float(costs[s_])
        c[p.Rc[:, s_].indices] += p.w[s_]
    if start is None and len(cands):
        _, g1 = p.gains(p.base.copy(), cands)
        g1 = np.where(costs[cands] <= budget, g1, -1.0)
        b = int(np.argmax(g1))
        if g1[b] > p.G(chosen):
            chosen, spent = [int(cands[b])], float(costs[cands[b]])
    return Plan(chosen, p.F(chosen), p.G(chosen), time.perf_counter() - t0, cost=spent)


def budgeted_partial(p: CoverageProblem, costs: np.ndarray, budget: float, cands: np.ndarray | None = None,
                     seed_size: int = 2, max_seeds: int = 3000, seed_pool: int = 40) -> Plan:
    """
    Partial enumeration: affordable seed sets of size <= seed_size, each extended greedily; best G wins.
    Seeds are drawn from the `seed_pool` best single skills (by G gain) to keep it interactive.
    """
    t0 = time.perf_counter()
    cands = np.asarray(p.candidates() if cands is None else cands, dtype=np.int64)
    best = budgeted_greedy(p, costs, budget, cands)
    if len(cands):
        _, g1 = p.gains(p.base.copy(), cands)
        pool = [int(s) for s in cands[np.argsort(-g1)[:seed_pool]]]
        n_seeds = 0
        for r in range(1, seed_size + 1):
            for seed in itertools.combinations(pool, r):
                if sum(costs[s] for s in seed) > budget + 1e-9:
                    continue
                n_seeds += 1
                if n_seeds > max_seeds:
                    break
                plan = budgeted_greedy(p, costs, budget, cands, start=list(seed))
                if plan.G > best.G:
                    best = plan
    best.seconds = time.perf_counter() - t0
    return best


def idf_weights(R: sp.csr_matrix) -> np.ndarray:
    """Integer skill weights: round(1000 * (log((1 + N) / (1 + df)) + 1))."""
    df = np.asarray((R > 0).sum(axis=0)).ravel()
    idf = np.log((1 + R.shape[0]) / (1 + df)) + 1.0
    return np.round(WEIGHT_SCALE * idf).astype(np.int64)
