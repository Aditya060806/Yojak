"""Private, fixed-scenario comparisons; coverage is not employment impact."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.preprocessing import MultiLabelBinarizer

from ml_pipeline.upskilling.engine import CoverageProblem, exact_ilp, frequency, greedy_F, lazy_greedy_G

from .data import PRIVATE, skills_of, write_json

PROFILES = {"starting": [], "technical": ["python", "sql"], "reporting": ["excel", "sql", "tableau"]}
EXPERIENCES = (0, 3, 7)


def evaluate_pool(frame: pd.DataFrame, skills: list[str], *, exact_limit: int = 200) -> dict:
    """Compare all methods on identical observations and the full skill vocabulary."""
    if frame.empty:
        return {"support": 0, "status": "empty_pool", "methods": {}}
    encoder = MultiLabelBinarizer(sparse_output=True)
    matrix = encoder.fit_transform(frame.skills)
    have = set(skills_of(",".join(skills), False))
    known = np.array([i for i, skill in enumerate(encoder.classes_) if skill in have], dtype=int)
    problem = CoverageProblem(matrix, np.ones(matrix.shape[1], dtype=int), np.ones(len(frame)), known, .6)
    plans = {"frequency": frequency(problem, 3), "greedy_F": greedy_F(problem, 3),
             "greedy_G": lazy_greedy_G(problem, 3)}
    best = max(plans.values(), key=lambda plan: (plan.F, plan.G))
    plans["portfolio"] = best
    exact_status = "skipped_size_limit"
    if len(frame) <= 500 and len(problem.candidates()) <= exact_limit:
        plans["exact"] = exact_ilp(problem, k=3, time_limit=1.0, hint=best.skills)
        exact_status = "proven" if plans["exact"].optimal else "not_proven"
    methods = {}
    for name, plan in plans.items():
        methods[name] = {"skills": encoder.classes_[plan.skills].tolist(), "coverage": int(plan.F),
                         "gain": int(plan.F - problem.F([])), "seconds": plan.seconds,
                         "proven_optimal": plan.optimal is True, "upper_bound": plan.bound}
    optimum = plans.get("exact")
    return {"support": len(frame), "before": int(problem.F([])), "candidate_count": len(problem.candidates()),
            "status": "evaluated", "exact_status": exact_status, "methods": methods,
            "portfolio_gap_to_proven_optimum": int(optimum.F - best.F) if optimum and optimum.optimal else None}


def scenarios(frame: pd.DataFrame):
    for family in sorted(frame.role_family.unique()):
        for experience in EXPERIENCES:
            pool = frame[(frame.role_family == family) & (frame.exp_min <= experience)
                         & (frame.exp_max >= experience) & ~frame.quality_flag]
            for name, skills in PROFILES.items():
                for complete in (False, True):
                    selected = pool[~pool.skills_truncated] if complete else pool
                    yield {"role_family": family, "experience": experience, "profile": name,
                           "skills": skills, "complete_only": complete}, selected.sort_values("row_key")


def benchmark(out: Path = PRIVATE) -> dict:
    manifest = json.loads((out / "manifest.json").read_text())
    frame = pd.read_parquet(out / "analytics.parquet")
    if len(frame) != manifest["audit"]["analytics"]["prepared_rows"] or not frame.row_key.is_unique:
        raise ValueError("Prepared Analytics observations do not match the manifest; rerun preparation.")
    records = []
    for profile, pool in scenarios(frame):
        result = evaluate_pool(pool, profile["skills"])
        # A deterministic small observation subset enables exact checks without
        # pruning the skill vocabulary or changing any posting's denominator.
        bounded = pool.assign(_order=pool.row_key.map(lambda key: hashlib.sha256(key.encode()).hexdigest()))
        bounded = bounded.sort_values("_order").head(40).drop(columns="_order")
        small = evaluate_pool(bounded, profile["skills"])
        records.append({"profile": profile, "full_pool": result, "bounded_pool": small,
                        "bounded_row_keys": bounded.row_key.tolist()})
        print(f"Planner {len(records)}: {profile['role_family']} / {profile['profile']} / {len(pool)} rows", flush=True)
    summaries = {}
    for scope in ("full_pool", "bounded_pool"):
        evaluated = [r[scope] for r in records if r[scope]["status"] == "evaluated"]
        summaries[scope] = {"evaluated": len(evaluated), "empty": len(records) - len(evaluated),
                            "proven_exact": sum(r["exact_status"] == "proven" for r in evaluated),
                            "methods": {}}
        gaps = [r["portfolio_gap_to_proven_optimum"] for r in evaluated
                if r["portfolio_gap_to_proven_optimum"] is not None]
        summaries[scope]["portfolio_exact_comparison"] = {
            "proven_cases": len(gaps), "attained_optimum": sum(gap == 0 for gap in gaps),
            "max_coverage_gap": max(gaps) if gaps else None,
            "median_coverage_gap": float(np.median(gaps)) if gaps else None}
        for method in ("greedy_F", "greedy_G", "portfolio"):
            deltas = [r["methods"][method]["coverage"] - r["methods"]["frequency"]["coverage"] for r in evaluated]
            summaries[scope]["methods"][method] = {
                "better": sum(d > 0 for d in deltas), "equal": sum(d == 0 for d in deltas),
                "worse": sum(d < 0 for d in deltas),
                "median_coverage_delta": float(np.median(deltas)) if deltas else None}
    report = {"source_version": manifest["source_version"], "preparation_code_hash": manifest["preparation_code_hash"],
              "benchmark_code_hash": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "config": {"experiences": EXPERIENCES, "profiles": PROFILES, "skill_budget": 3, "threshold": .6,
                         "bounded_rows": 40, "exact_max_rows": 500, "exact_max_candidates": 200, "exact_seconds": 1},
              "limitations": ["Fixed hypothetical profiles, not sampled people; no population confidence interval.",
                               "Overlapping pools and profiles are not independent trials.",
                               "Portfolio includes frequency, so noninferiority is guaranteed by construction.",
                               "Bounded subsets have their own objective; their optimality does not certify full pools.",
                               "Complete-only views change the population; differences are not causal truncation effects.",
                               "Solver proofs and timing can vary with runtime scheduling."],
              "summary": summaries, "scenarios": records}
    write_json(out / "planner_benchmark.json", report)
    lines = ["# Private planner benchmark", "", f"Source version: `{report['source_version']}`.", "",
             "Fixed hypothetical scenarios; observed skill coverage only, not hiring outcomes.", ""]
    for scope, summary in summaries.items():
        lines += [f"## {scope.replace('_', ' ').title()}", "",
                  f"{summary['evaluated']} nonempty scenarios; {summary['empty']} empty scenarios.", "",
                  "| Method versus frequency | Better | Equal | Worse | Median posting delta |",
                  "|---|---:|---:|---:|---:|"]
        for method, values in summary["methods"].items():
            lines.append(f"| {method} | {values['better']} | {values['equal']} | {values['worse']} | {values['median_coverage_delta']} |")
        exact = summary["portfolio_exact_comparison"]
        lines += ["", f"Portfolio attained the optimum in {exact['attained_optimum']} of "
                  f"{exact['proven_cases']} proven cases; maximum coverage gap {exact['max_coverage_gap']}.", ""]
    lines += ["## Interpretation limits", ""] + [f"- {item}" for item in report["limitations"]]
    (out / "planner_benchmark.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(benchmark()["summary"], indent=2))
