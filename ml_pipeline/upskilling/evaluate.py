# ml_pipeline/upskilling/evaluate.py

"""
Evaluate the upskilling engine and write reports/upskilling_eval.json.

    python -m ml_pipeline.upskilling.evaluate [--instances 300]

Instances: pseudo-users built from held-out (graph test split) postings. The person
knows a random half of the posting's ESCO skills; the target pool is every other
posting in the same ISCO sub-major group and experience band (at most 3,000, sampled
by hash). Strata: fresher (0-1 yrs), mid (1-6), senior (6+).

For k in {1, 3, 5} and tau in {0.4, 0.6, 0.8}, compare on the true objective F
(number of newly eligible postings):
  lazy greedy on G | plain greedy on F | top-k by frequency | exact optimum (CP-SAT ILP)
Report optimality gap (mean, p95), share of instances where each method is optimal,
gain over frequency, runtimes, and how often the ILP proved optimality.
Also: salary-weighted objective (v_j = predicted median salary), the effort-aware
budgeted variant, and a brute-force cross-check of the ILP on small instances.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import time

import numpy as np

from ml_pipeline.common import provenance, write_report
from ml_pipeline.graph.data import split_of as graph_split
from ml_pipeline.upskilling.effort import EffortModel
from ml_pipeline.upskilling.engine import (
    brute_force,
    budgeted_greedy,
    budgeted_partial,
    exact_ilp,
    frequency,
    greedy_F,
    lazy_greedy_G,
)
from ml_pipeline.upskilling.market import load_market

KS = (1, 3, 5)
TAUS = (0.4, 0.6, 0.8)
STRATA = {"fresher": ["0-1"], "mid": ["1-3", "3-6"], "senior": ["6-10", "10+"]}
POOL_CAP = 2000
ILP_SECONDS = 5
SEED = 11


def _h(x: str) -> str:
    return hashlib.sha256(f"up{SEED}:{x}".encode()).hexdigest()


def make_instances(market, n: int) -> list[dict]:
    rng = np.random.default_rng(SEED)
    jobs = market.jobs
    test = jobs[(jobs["dup_group_id"].map(graph_split) == "test") & jobs["isco_code"].notna()
                & (jobs["skill_uris"].map(len) >= 4)]
    out = []
    per = n // len(STRATA)
    for stratum, bands in STRATA.items():
        cand = test[test["exp_band"].isin(bands)]
        cand = cand.loc[sorted(cand.index, key=lambda i: _h(str(jobs.at[i, "jobId"])))]
        for i in cand.index:
            if sum(1 for o in out if o["stratum"] == stratum) >= per:
                break
            row = jobs.loc[i]
            own = np.array([market.skill_index[u] for u in row["skill_uris"]])
            have = rng.choice(own, size=max(2, len(own) // 2), replace=False)
            pool = market.pool(isco2=str(row["isco_code"])[:2], exp_bands=[row["exp_band"]],
                               exclude_group=row["dup_group_id"])
            if len(pool) < 30:
                continue
            if len(pool) > POOL_CAP:
                pool = np.array(sorted(pool, key=lambda r: _h(str(jobs.at[r, "jobId"])))[:POOL_CAP])
            out.append({"stratum": stratum, "jobId": row["jobId"], "have": have, "pool": pool,
                        "tier": row["primary_tier"]})
    return out


def _record(row: dict, plans: dict) -> None:
    for name, plan in plans.items():
        row[name], row[f"{name}_s"] = plan.F, plan.seconds
    ilp = plans["exact_ilp"]
    row["ilp_optimal"] = bool(ilp.optimal)
    row["ilp_bound"] = ilp.bound if ilp.bound is not None else ilp.F


def summarise(rows: list[dict], methods: list[str]) -> dict:
    opt = np.array([r["opt"] for r in rows])
    out = {"instances": len(rows), "mean_optimum": round(float(opt.mean()), 3),
           "ilp_proven_optimal_share": round(float(np.mean([r["ilp_optimal"] for r in rows])), 4)}
    pos = opt > 0
    bound = np.array([max(r.get("ilp_bound", r["opt"]), r["opt"]) for r in rows])
    for m in methods:
        f = np.array([r[m] for r in rows])
        gap = np.where(pos, (opt - f) / np.where(pos, opt, 1), 0.0)
        # Against the solver's proven upper bound: a guaranteed upper bound on the true gap.
        gap_ub = np.where(bound > 0, (bound - f) / np.where(bound > 0, bound, 1), 0.0)
        t = np.array([r[f"{m}_s"] for r in rows]) * 1000
        out[m] = {
            "mean_F": round(float(f.mean()), 3),
            "mean_gap_pct": round(float(gap[pos].mean() * 100), 2) if pos.any() else 0.0,
            "p95_gap_pct": round(float(np.percentile(gap[pos], 95) * 100), 2) if pos.any() else 0.0,
            "share_optimal": round(float(np.mean(np.isclose(f, opt))), 4),
            "mean_gap_upper_bound_pct": round(float(gap_ub[bound > 0].mean() * 100), 2) if (bound > 0).any() else 0.0,
            "runtime_ms_p50": round(float(np.percentile(t, 50)), 2),
            "runtime_ms_p95": round(float(np.percentile(t, 95)), 2),
        }
    freq = np.array([r["frequency"] for r in rows])
    for m in methods:
        if m != "frequency":
            f = np.array([r[m] for r in rows])
            out[m]["mean_extra_jobs_vs_frequency"] = round(float((f - freq).mean()), 3)
            out[m]["share_better_than_frequency"] = round(float(np.mean(f > freq)), 4)
    return out


def run_grid(market, instances) -> dict:
    methods = ["lazy_greedy_G", "greedy_F", "frequency", "exact_ilp"]
    grid = {}
    for tau in TAUS:
        for k in KS:
            rows = []
            for inst in instances:
                p = market.problem(inst["pool"], inst["have"], tau)
                cands = p.candidates()
                r = {"stratum": inst["stratum"]}
                gf = greedy_F(p, k, cands)
                plans = {"lazy_greedy_G": lazy_greedy_G(p, k, cands), "greedy_F": gf, "frequency": frequency(p, k),
                         "exact_ilp": exact_ilp(p, k, cands=cands, time_limit=ILP_SECONDS, hint=gf.skills)}
                _record(r, plans)
                r["opt"] = max(r["exact_ilp"], r["lazy_greedy_G"], r["greedy_F"], r["frequency"])
                rows.append(r)
            key = f"k={k},tau={tau}"
            grid[key] = summarise(rows, methods)
            grid[key]["by_stratum"] = {s: summarise([r for r in rows if r["stratum"] == s], methods)
                                       for s in STRATA if any(r["stratum"] == s for r in rows)}
            print(f"  {key}: optimum {grid[key]['mean_optimum']}, greedyG gap "
                  f"{grid[key]['lazy_greedy_G']['mean_gap_pct']}%, frequency gap {grid[key]['frequency']['mean_gap_pct']}%",
                  flush=True)
    return grid


def run_salary_weighted(market, instances, k=3, tau=0.6) -> dict:
    rows = []
    for inst in instances:
        p = market.problem(inst["pool"], inst["have"], tau, value="salary")
        cands = p.candidates()
        r = {}
        gf = greedy_F(p, k, cands)
        _record(r, {"greedy_F": gf, "lazy_greedy_G": lazy_greedy_G(p, k, cands), "frequency": frequency(p, k),
                    "exact_ilp": exact_ilp(p, k, cands=cands, time_limit=ILP_SECONDS, hint=gf.skills)})
        r["opt"] = max(r["exact_ilp"], r["greedy_F"], r["lazy_greedy_G"], r["frequency"])
        rows.append(r)
    s = summarise(rows, ["greedy_F", "lazy_greedy_G", "frequency", "exact_ilp"])
    s["value"] = "sum of predicted median annual salary (INR) of newly eligible postings"
    return s


def run_budgeted(market, instances, effort: EffortModel, budget=3.0, tau=0.6) -> dict:
    rows = []
    for inst in instances:
        p = market.problem(inst["pool"], inst["have"], tau)
        cands = p.candidates()
        costs = effort.costs(inst["have"])
        r = {}
        bp = budgeted_partial(p, costs, budget, cands, max_seeds=400)
        _record(r, {"budgeted_greedy": budgeted_greedy(p, costs, budget, cands), "budgeted_partial": bp,
                    "frequency_within_budget": _freq_budget(p, costs, budget),
                    "exact_ilp": exact_ilp(p, None, costs=costs, budget=budget, cands=cands,
                                           time_limit=ILP_SECONDS, hint=bp.skills)})
        r["frequency"] = r["frequency_within_budget"]
        r["frequency_s"] = r["frequency_within_budget_s"]
        r["opt"] = max(r[m] for m in ("exact_ilp", "budgeted_greedy", "budgeted_partial", "frequency"))
        rows.append(r)
    s = summarise(rows, ["budgeted_greedy", "budgeted_partial", "frequency", "exact_ilp"])
    s["budget"] = budget
    s["effort_note"] = "effort weights are a documented heuristic (ml_pipeline/upskilling/effort.py)"
    return s


def _freq_budget(p, costs, budget):
    from ml_pipeline.upskilling.engine import Plan

    t0 = time.perf_counter()
    order = frequency(p, p.R.shape[1]).skills
    chosen, spent = [], 0.0
    for s in order:
        if spent + costs[s] <= budget:
            chosen.append(s)
            spent += costs[s]
    return Plan(chosen, p.F(chosen), p.G(chosen), time.perf_counter() - t0, cost=spent)


def brute_force_check(market, instances, n=40) -> dict:
    agree, checked = 0, 0
    for inst in instances:
        p = market.problem(inst["pool"], inst["have"], 0.6)
        cands = p.candidates()
        if len(cands) > 22:
            continue
        for k in (1, 2):
            checked += 1
            agree += int(np.isclose(brute_force(p, k, cands).F, exact_ilp(p, k, cands=cands).F))
        if checked >= n:
            break
    return {"instances_checked": checked, "ilp_equals_brute_force": agree}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--instances", type=int, default=150)
    args = ap.parse_args(argv)
    t0 = time.time()
    market = load_market()
    instances = make_instances(market, args.instances)
    print(f"{len(instances)} instances; mean pool size {np.mean([len(i['pool']) for i in instances]):.0f}", flush=True)
    grid = run_grid(market, instances)
    salary = run_salary_weighted(market, instances)
    from app.core.settings import get_settings

    effort = EffortModel(get_settings().esco_data_dir, market.skills)
    budgeted = run_budgeted(market, instances, effort)
    body = {
        "question": "Which k skills should a person learn to become eligible for the most postings?",
        "objective": ("F(A) = number (or salary value) of postings with fit(S u A, j) >= tau, where fit is the "
                      "IDF-weighted share of a posting's ESCO skills the person has. F is not submodular; "
                      "G(A) = sum min(1, fit/tau) is, and lazy greedy on G carries the (1-1/e) guarantee on G."),
        "instances": {"n": len(instances), "by_stratum": {s: sum(i["stratum"] == s for i in instances) for s in STRATA},
                      "pool": "same ISCO sub-major group and experience band, <= 3000 postings",
                      "person": "random half of a held-out posting's ESCO skills"},
        "grid": grid,
        "salary_weighted_k3_tau0.6": salary,
        "effort_aware_budget3_tau0.6": budgeted,
        "ilp_vs_brute_force": brute_force_check(market, instances),
        "seconds": round(time.time() - t0, 1),
    }
    prov = provenance("ml_pipeline/upskilling/evaluate.py", seed=SEED)
    print(write_report("upskilling_eval", body, prov))
    return 0


if __name__ == "__main__":
    sys.exit(main())
