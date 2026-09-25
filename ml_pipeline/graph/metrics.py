# ml_pipeline/graph/metrics.py

"""
Ranking metrics with bootstrap confidence intervals.

  recall@k  share of a query's relevant items found in the top k
  ndcg@k    graded: gain = 2^grade - 1, ideal = sort of the query's own grades
  mrr       1 / rank of the first relevant item (0 if none in the ranking)

Every function takes one query at a time (ranked item ids + relevance dict) so the
same code scores skills, occupations and jobs.
"""

from __future__ import annotations

import numpy as np


def recall_at_k(ranked: np.ndarray, relevant: dict[int, int], k: int = 10) -> float:
    if not relevant:
        return 0.0
    top = set(ranked[:k].tolist())
    return sum(1 for r in relevant if r in top) / len(relevant)


def ndcg_at_k(ranked: np.ndarray, relevant: dict[int, int], k: int = 10) -> float:
    if not relevant:
        return 0.0
    gains = np.array([2.0 ** relevant.get(int(i), 0) - 1.0 for i in ranked[:k]])
    discounts = 1.0 / np.log2(np.arange(2, len(gains) + 2))
    dcg = float((gains * discounts).sum())
    ideal = np.sort(np.array([2.0 ** g - 1.0 for g in relevant.values()]))[::-1][:k]
    idcg = float((ideal * (1.0 / np.log2(np.arange(2, len(ideal) + 2)))).sum())
    return dcg / idcg if idcg > 0 else 0.0


def reciprocal_rank(ranked: np.ndarray, relevant: dict[int, int], min_grade: int = 1) -> float:
    for pos, item in enumerate(ranked, start=1):
        if relevant.get(int(item), 0) >= min_grade:
            return 1.0 / pos
    return 0.0


def top_k_from_scores(scores: np.ndarray, k: int, exclude: np.ndarray | None = None) -> np.ndarray:
    """Indices of the k highest scores (descending), optionally excluding some items."""
    s = scores.astype(np.float64, copy=True)
    if exclude is not None and len(exclude):
        s[exclude] = -np.inf
    k = min(k, len(s))
    part = np.argpartition(-s, k - 1)[:k]
    return part[np.argsort(-s[part], kind="stable")]


def full_rank_of(scores: np.ndarray, targets: np.ndarray, exclude: np.ndarray | None = None) -> np.ndarray:
    """1-based rank of each target among all non-excluded items (ties broken pessimistically)."""
    s = scores.astype(np.float64, copy=True)
    if exclude is not None and len(exclude):
        s[exclude] = -np.inf
    return np.array([int((s > s[t]).sum() + (s == s[t]).sum()) for t in targets])


def evaluate_rankings(per_query: list[dict], k: int = 10) -> dict:
    """
    per_query: [{"ranked": top-K item ids, "relevant": {item: grade}, "first_rank": optional int}]
    MRR uses `first_rank` (rank among ALL items) when given, else the truncated ranking.
    """
    rec = np.array([recall_at_k(q["ranked"], q["relevant"], k) for q in per_query])
    ndcg = np.array([ndcg_at_k(q["ranked"], q["relevant"], k) for q in per_query])
    mrr = np.array([
        (1.0 / q["first_rank"]) if q.get("first_rank") else reciprocal_rank(q["ranked"], q["relevant"])
        for q in per_query
    ])
    return {"n": len(per_query), f"recall@{k}": rec, f"ndcg@{k}": ndcg, "mrr": mrr}


def bootstrap_ci(values: np.ndarray, n_boot: int = 1000, seed: int = 0, alpha: float = 0.05) -> list[float]:
    rng = np.random.default_rng(seed)
    n = len(values)
    if n == 0:
        return [float("nan"), float("nan")]
    means = values[rng.integers(0, n, size=(n_boot, n))].mean(axis=1)
    return [float(np.percentile(means, 100 * alpha / 2)), float(np.percentile(means, 100 * (1 - alpha / 2)))]


def summarise(raw: dict, k: int = 10) -> dict:
    out = {"n": raw["n"]}
    for key in (f"recall@{k}", f"ndcg@{k}", "mrr"):
        vals = raw[key]
        out[key] = round(float(vals.mean()), 4)
        out[f"{key}_ci95"] = [round(x, 4) for x in bootstrap_ci(vals)]
    return out


def paired_difference(a: np.ndarray, b: np.ndarray, n_boot: int = 2000, seed: int = 0) -> dict:
    """Mean of a-b per query with a paired bootstrap CI (same queries for both models)."""
    d = a - b
    ci = bootstrap_ci(d, n_boot=n_boot, seed=seed)
    return {"mean_diff": round(float(d.mean()), 4), "ci95": [round(ci[0], 4), round(ci[1], 4)],
            "significant": bool(ci[0] > 0 or ci[1] < 0)}
