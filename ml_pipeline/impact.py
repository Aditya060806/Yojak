# ml_pipeline/impact.py

"""
Impact estimate: how many more postings does the optimal plan make reachable for a
Tier-2/3 fresher than the usual "learn the most common skills" advice?

    python -m ml_pipeline.impact   (or scripts/impact.py)  ->  reports/impact.json

Population  held-out postings (graph test split) for freshers (0-1 yrs) in Tier-2/3 cities
            with at least 4 ESCO skills; the pseudo-user knows a random half of them.
Pool        fresher postings (0-1 yrs) in Tier-2/3 cities in the same ISCO sub-major group.
Plans       k = 3 skills, eligibility at tau = 0.6: best of greedy-on-F and a 3 s ILP
            (warm-started) versus top-3 by frequency.
Every assumption is written into the report. The scale-up line is arithmetic on those
assumptions, labelled as an illustration, not a forecast.
"""

from __future__ import annotations

import hashlib
import sys
import time

import numpy as np

from ml_pipeline.common import provenance, write_report
from ml_pipeline.graph.data import split_of
from ml_pipeline.upskilling.engine import exact_ilp, frequency, greedy_F
from ml_pipeline.upskilling.market import load_market

K, TAU, SEED, N_USERS = 3, 0.6, 31, 300


def main() -> int:
    t0 = time.time()
    rng = np.random.default_rng(SEED)
    m = load_market()
    j = m.jobs
    tier23 = j["primary_tier"].isin([2, 3])
    fresher = j["exp_band"].eq("0-1")
    src = j[tier23 & fresher & j["isco_code"].notna() & (j["dup_group_id"].map(split_of) == "test")
            & (j["skill_uris"].map(len) >= 4)]
    order = sorted(src.index, key=lambda i: hashlib.sha256(f"imp{SEED}:{j.at[i, 'jobId']}".encode()).hexdigest())
    rows = []
    for i in order:
        if len(rows) >= N_USERS:
            break
        own = np.array([m.skill_index[u] for u in j.at[i, "skill_uris"]])
        have = rng.choice(own, size=max(2, len(own) // 2), replace=False)
        pool = m.pool(isco2=str(j.at[i, "isco_code"])[:2], exp_bands=["0-1"], tiers=[2, 3],
                      exclude_group=j.at[i, "dup_group_id"])
        if len(pool) < 30:
            continue
        p = m.problem(pool, have, TAU)
        cands = p.candidates()
        gf = greedy_F(p, K, cands)
        ilp = exact_ilp(p, K, cands=cands, time_limit=3, hint=gf.skills)
        best = ilp if ilp.F >= gf.F else gf
        fq = frequency(p, K)
        before = float(p.v[p.eligible(p.base)].sum())
        rows.append({"pool": len(pool), "before": before, "optimal": best.F, "frequency": fq.F,
                     "tier": int(j.at[i, "primary_tier"])})
    opt = np.array([r["optimal"] for r in rows])
    fq = np.array([r["frequency"] for r in rows])
    before = np.array([r["before"] for r in rows])
    extra = opt - fq
    pools = np.array([r["pool"] for r in rows])
    q25, q50, q75 = np.percentile(extra, [25, 50, 75]) if len(extra) else (0, 0, 0)
    body = {
        "question": "For a Tier-2/3 fresher, how many more postings does Yojak's optimal 3-skill plan make reachable "
                    "than learning the 3 most common skills?",
        "users": len(rows),
        "users_by_tier": {"2": sum(r["tier"] == 2 for r in rows), "3": sum(r["tier"] == 3 for r in rows)},
        "pool_size_median": float(np.median(pools)) if len(pools) else None,
        "eligible_before_median": float(np.median(before)) if len(before) else None,
        "eligible_after_optimal_median": float(np.median(opt)) if len(opt) else None,
        "eligible_after_frequency_median": float(np.median(fq)) if len(fq) else None,
        "extra_postings_vs_frequency": {"mean": round(float(extra.mean()), 2) if len(extra) else None,
                                        "median": float(q50), "iqr": [float(q25), float(q75)]},
        "share_users_with_more_postings": round(float(np.mean(extra > 0)), 4) if len(extra) else None,
        "share_users_no_worse": round(float(np.mean(extra >= 0)), 4) if len(extra) else None,
        "relative_gain_median_pct": round(float(np.median(np.where(fq > 0, (opt - fq) / np.maximum(fq, 1), 0)) * 100), 1)
        if len(fq) else None,
        "assumptions": {
            "k": K,
            "tau": TAU,
            "eligibility": "a posting is reachable when the person covers >= 60% of its ESCO skills, weighted by rarity (IDF)",
            "eligibility_is_not_hiring": True,
            "person": "a random half of a real held-out fresher posting's skills (pseudo-user, not a real student)",
            "pool": "fresher (0-1 yrs) postings in Tier-2/3 cities in the same ISCO sub-major group",
            "data": "Naukri postings over about two weeks around 2025-10-03; formal-sector and urban-skewed",
            "learning": "each recommended skill is assumed learnable; effort and time are not modelled here",
            "no_causal_claim": "this compares advice rules on the same data; it does not measure hiring outcomes",
        },
        "illustration": {
            "per_1000_users_extra_reachable_postings": round(float(extra.mean()) * 1000, 0) if len(extra) else None,
            "label": "ILLUSTRATION ONLY: 1,000 x mean extra reachable postings per user, under the assumptions above. "
                     "Not a forecast of jobs or hires.",
        },
        "seconds": round(time.time() - t0, 1),
    }
    print(write_report("impact", body, provenance("ml_pipeline/impact.py", seed=SEED)))
    print({k: body[k] for k in ("users", "extra_postings_vs_frequency", "share_users_with_more_postings")})
    return 0


if __name__ == "__main__":
    sys.exit(main())
