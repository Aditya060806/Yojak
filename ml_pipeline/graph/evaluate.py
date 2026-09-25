# ml_pipeline/graph/evaluate.py

"""
Run every model on the same splits and write reports/model_comparison.json.

    python -m ml_pipeline.graph.evaluate                 # full benchmark
    python -m ml_pipeline.graph.evaluate --quick         # smaller query sets (smoke test)

Protocol (identical for every model):
  T1  test jobs, known half -> rank all skills except the known ones; targets = hidden half
  T2  every ESCO occupation, known 80% -> rank the rest; targets = hidden 20%
  T3  2,000 pseudo-candidates -> rank the ~9.5K pool jobs; source job grade 2,
      same-occupation jobs grade 1. recall@10 here = source job in the top 10.
Metrics: recall@10, NDCG@10, MRR (rank among all items), each with a 95% bootstrap CI;
paired bootstrap differences against the best baseline; p50/p95 online latency; memory.
Stochastic models run with 3 seeds; the table reports the mean over seeds.
"""

from __future__ import annotations

import argparse
import gc
import os
import sys
import time

import numpy as np
import psutil

from ml_pipeline.common import provenance, write_report
from ml_pipeline.graph.data import SPLIT_SEED, GraphData, leakage_report, load_or_build
from ml_pipeline.graph.metrics import (
    evaluate_rankings,
    full_rank_of,
    paired_difference,
    summarise,
    top_k_from_scores,
)

K = 10
TOP = 100


def _chunks(arr, size):
    for s in range(0, len(arr), size):
        yield arr[s:s + size]


def run_t1(model, data: GraphData, split: str = "test", limit: int | None = None, chunk: int = 1000) -> dict:
    jobs = data.eval_jobs(split)
    if limit:
        jobs = jobs[:limit]
    per_query = []
    for block in _chunks(jobs, chunk):
        scores = model.score_t1(block)
        for r, j in enumerate(block):
            known = data.known[j].indices
            hidden = data.hidden[int(j)]
            ranked = top_k_from_scores(scores[r], TOP, exclude=known)
            first = int(full_rank_of(scores[r], hidden, exclude=known).min())
            per_query.append({"ranked": ranked, "relevant": {int(h): 1 for h in hidden}, "first_rank": first})
    return evaluate_rankings(per_query, K)


def run_t2(model, data: GraphData, limit: int | None = None, chunk: int = 1000) -> dict | None:
    if not model.supports_t2 or data.occ_known is None:
        return None
    occs = np.array(sorted(data.occ_hidden), dtype=np.int64)
    if limit:
        occs = occs[:limit]
    per_query = []
    for block in _chunks(occs, chunk):
        scores = model.score_t2(block)
        for r, o in enumerate(block):
            known = data.occ_known[o].indices
            hidden = data.occ_hidden[int(o)]
            ranked = top_k_from_scores(scores[r], TOP, exclude=known)
            first = int(full_rank_of(scores[r], hidden, exclude=known).min())
            per_query.append({"ranked": ranked, "relevant": {int(h): 1 for h in hidden}, "first_rank": first})
    return evaluate_rankings(per_query, K)


def run_t3(model, data: GraphData, limit: int | None = None, chunk: int = 500, dev: bool = False) -> dict:
    """T3 on the test pool, or on the train-job dev pool when choosing settings (dev=True)."""
    source = data.t3_dev_queries if dev else data.t3_queries
    queries = source[:limit] if limit else source
    pool = data.t3_dev_pool if dev else data.job_ids("pool")
    pos = {int(j): i for i, j in enumerate(pool)}
    per_query = []
    for block in _chunks(queries, chunk):
        scores = model.score_t3([q["skills"] for q in block], pool)
        for r, q in enumerate(block):
            rel = {pos[j]: g for j, g in q["relevance"].items() if j in pos}
            src = pos[q["source_job"]]
            ranked = top_k_from_scores(scores[r], TOP)
            first = int(full_rank_of(scores[r], np.array([src]))[0])
            per_query.append({"ranked": ranked, "relevant": rel, "source": src, "first_rank": first})
    raw = evaluate_rankings(per_query, K)
    # Recall@10 for T3 = the source job is in the top 10 (the same-occupation set can be
    # hundreds of jobs, so a share-of-set recall would be meaningless).
    raw[f"recall@{K}"] = np.array([1.0 if q["source"] in set(q["ranked"][:K].tolist()) else 0.0
                                   for q in per_query])
    return raw


def measure_latency(model, data: GraphData, n: int = 200, seed: int = 0) -> dict:
    """Online latency for one request: score all skills for a profile, and rank all pool jobs."""
    rng = np.random.default_rng(seed)
    pool = data.job_ids("pool")
    sets = [data.t3_queries[i % len(data.t3_queries)]["skills"] for i in rng.permutation(n)]
    out = {}
    for name, fn in [("skills_for_profile", lambda s: model.score_skill_set(s)),
                     ("jobs_for_profile", lambda s: model.score_t3([s], pool))]:
        for s in sets[:5]:
            fn(s)  # warm-up
        t = []
        for s in sets:
            t0 = time.perf_counter()
            fn(s)
            t.append((time.perf_counter() - t0) * 1000)
        out[name] = {"p50_ms": round(float(np.percentile(t, 50)), 2), "p95_ms": round(float(np.percentile(t, 95)), 2)}
    return out


def memory_snapshot() -> dict:
    snap = {"rss_mb": round(psutil.Process(os.getpid()).memory_info().rss / 2**20, 1)}
    try:
        import torch

        if torch.cuda.is_available():
            snap["gpu_peak_mb"] = round(torch.cuda.max_memory_allocated() / 2**20, 1)
    except Exception:  # noqa: BLE001
        pass
    return snap


def evaluate_model(factory, data: GraphData, seeds: list[int], quick: bool = False, tasks=("t1", "t2", "t3")) -> dict:
    limit = 500 if quick else None
    runs = []
    raw_last = {}
    for seed in seeds:
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.reset_peak_memory_stats()
        except Exception:  # noqa: BLE001
            pass
        model = factory()
        t0 = time.time()
        model.fit(data, seed=seed)
        fit_s = time.time() - t0
        res = {"seed": seed, "fit_seconds": round(fit_s, 1)}
        raw = {}
        if "t1" in tasks:
            raw["t1"] = run_t1(model, data, limit=limit)
        if "t2" in tasks:
            r2 = run_t2(model, data, limit=limit)
            if r2 is not None:
                raw["t2"] = r2
        if "t3" in tasks:
            raw["t3"] = run_t3(model, data, limit=limit)
        res.update({t: summarise(v, K) for t, v in raw.items()})
        res["latency"] = measure_latency(model, data, n=50 if quick else 200)
        res["memory"] = memory_snapshot()
        if hasattr(model, "history"):
            res["training_history"] = model.history
        for attr in ("tuning", "calibration", "best_val"):
            if hasattr(model, attr):
                res[attr] = getattr(model, attr)
        if hasattr(model, "k"):
            res["k"] = model.k
        if hasattr(model, "model") and hasattr(model.model, "cj_weight"):
            res["cand_job_graph_weight"] = round(float(model.model.cj_weight), 4)
        runs.append(res)
        raw_last = raw
        print(f"    seed {seed}: " + ", ".join(f"{t} ndcg@10={res[t]['ndcg@10']:.4f}" for t in raw), flush=True)
        del model
        gc.collect()
        try:
            import torch

            torch.cuda.empty_cache()
        except Exception:  # noqa: BLE001
            pass
    return {"name": factory().name if not hasattr(factory, "label") else factory.label,
            "runs": runs, "mean": _mean_over_seeds(runs), "_raw": raw_last}


def _mean_over_seeds(runs: list[dict]) -> dict:
    out = {}
    for task in ("t1", "t2", "t3"):
        vals = [r[task] for r in runs if task in r]
        if not vals:
            continue
        out[task] = {}
        for key in (f"recall@{K}", f"ndcg@{K}", "mrr"):
            xs = np.array([v[key] for v in vals])
            out[task][key] = round(float(xs.mean()), 4)
            out[task][f"{key}_seed_std"] = round(float(xs.std()), 4) if len(xs) > 1 else 0.0
            out[task][f"{key}_ci95"] = vals[-1][f"{key}_ci95"]
    out["latency"] = runs[-1]["latency"]
    out["memory"] = runs[-1]["memory"]
    out["fit_seconds"] = round(float(np.mean([r["fit_seconds"] for r in runs])), 1)
    return out


class Factory:
    """Named zero-arg constructor so reports carry readable labels."""

    def __init__(self, label: str, ctor, **kwargs):
        self.label, self.ctor, self.kwargs = label, ctor, kwargs

    def __call__(self):
        m = self.ctor(**self.kwargs)
        m.name = self.label
        return m


def main(argv: list[str] | None = None) -> int:
    from ml_pipeline.graph.baselines import AdamicAdar, MpnetFaiss, Popularity, TfidfKNN
    from ml_pipeline.graph.lightgcn import LightGCN

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--models", nargs="*", default=None, help="Subset of model keys to run")
    parser.add_argument("--skip-ablations", action="store_true")
    parser.add_argument("--seeds", type=int, default=3)
    args = parser.parse_args(argv)

    from ml_pipeline.graph.hgt.model import HGTRecommender

    seeds = list(range(args.seeds))
    data = load_or_build("esco", SPLIT_SEED)
    leak = leakage_report(data)
    assert leak["hidden_edges_in_known"] == 0 and leak["groups_spanning_splits"] == 0, leak

    models = {
        "b0": (Factory("B0 Popularity", Popularity), [0]),
        "b1": (Factory("B1 TF-IDF kNN", TfidfKNN), [0]),
        "b2": (Factory("B2 mpnet+FAISS (SkillAlign)", MpnetFaiss), [0]),
        "b3a": (Factory("B3a Adamic-Adar", AdamicAdar), [0]),
        "b3b": (Factory("B3b LightGCN", LightGCN), seeds),
        "hgt": (Factory("M HGT (Vyuha)", HGTRecommender), seeds),
    }
    selected = args.models or list(models)
    results: dict[str, dict] = {}
    for key in selected:
        factory, model_seeds = models[key]
        print(f"\n== {factory.label}", flush=True)
        results[key] = evaluate_model(factory, data, model_seeds, quick=args.quick)

    comparison = compare(results)
    ablations = {} if args.skip_ablations else run_ablations(data, seeds, args.quick)
    body = {
        "protocol": __doc__.strip(),
        "data": leak,
        "models": {k: {"name": v["name"], "mean": v["mean"], "runs": v["runs"]} for k, v in results.items()},
        "comparison": comparison,
        "ablations": ablations,
        "quick_mode": args.quick,
    }
    prov = provenance("ml_pipeline/graph/evaluate.py", seed=SPLIT_SEED, seeds=seeds)
    path = write_report("model_comparison" + ("_quick" if args.quick else ""), body, prov)
    print(f"\nwrote {path}")
    return 0


def compare(results: dict) -> dict:
    """Winner by T3 NDCG@10 (T1 breaks ties when CIs overlap) + paired tests vs the best baseline."""
    names = {k: v["name"] for k, v in results.items()}
    t3 = {k: v["mean"]["t3"]["ndcg@10"] for k, v in results.items() if "t3" in v["mean"]}
    ranked = sorted(t3, key=t3.get, reverse=True)
    if not ranked:
        return {}
    winner = ranked[0]
    if len(ranked) > 1:
        a, b = results[ranked[0]], results[ranked[1]]
        overlap = (a["mean"]["t3"]["ndcg@10_ci95"][0] <= b["mean"]["t3"]["ndcg@10_ci95"][1])
        if overlap and a["mean"]["t1"]["ndcg@10"] < b["mean"]["t1"]["ndcg@10"]:
            winner = ranked[1]
    baselines = [k for k in results if k != "hgt"]
    out = {"winner": winner, "winner_name": names[winner], "rule": "highest T3 NDCG@10; T1 NDCG@10 breaks CI-overlap ties",
           "t3_ranking": [names[k] for k in ranked]}
    if "hgt" in results and baselines:
        best_base = max(baselines, key=lambda k: t3.get(k, -1))
        out["hgt_vs_best_baseline"] = {"baseline": names[best_base]}
        for task in ("t1", "t2", "t3"):
            ra, rb = results["hgt"]["_raw"].get(task), results[best_base]["_raw"].get(task)
            if ra is not None and rb is not None and ra["n"] == rb["n"]:
                out["hgt_vs_best_baseline"][task] = paired_difference(ra[f"ndcg@{K}"], rb[f"ndcg@{K}"])
        out["hgt_beats_best_baseline_on_t3"] = bool(results["hgt"]["mean"]["t3"]["ndcg@10"] > t3[best_base])
    return out


def run_ablations(data: GraphData, seeds: list[int], quick: bool) -> dict:
    """Without skill linking (raw tags; T3 comparable) and HGT structure ablations."""
    from ml_pipeline.graph.baselines import AdamicAdar, TfidfKNN
    from ml_pipeline.graph.hgt.model import HGTRecommender
    from ml_pipeline.graph.lightgcn import LightGCN

    out: dict = {}
    tags = load_or_build("tags", SPLIT_SEED)
    print("\n== Ablation: raw Naukri tags instead of ESCO-linked skills (T3)", flush=True)
    out["without_skill_linking"] = {
        "note": "Same jobs, same T3 query jobs; skill nodes are raw tags (freq >= 3), no ESCO occupation edges.",
        "models": {},
    }
    for key, fac in [("b1", Factory("B1 TF-IDF kNN", TfidfKNN)), ("b3a", Factory("B3a Adamic-Adar", AdamicAdar)),
                     ("b3b", Factory("B3b LightGCN", LightGCN)), ("hgt", Factory("M HGT (Vyuha)", HGTRecommender))]:
        r = evaluate_model(fac, tags, seeds[:1], quick=quick, tasks=("t3",))
        out["without_skill_linking"]["models"][key] = {"name": r["name"], "t3": r["mean"]["t3"]}

    print("\n== Ablation: HGT structure", flush=True)
    variants = {
        "no_company_city": Factory("HGT without company/city nodes", HGTRecommender, use_context=False),
        "one_layer": Factory("HGT with 1 layer", HGTRecommender, num_layers=1),
        "with_time": Factory("HGT with posting-time encoding", HGTRecommender, use_time=True),
    }
    out["hgt_variants"] = {}
    for key, fac in variants.items():
        r = evaluate_model(fac, data, seeds[:1], quick=quick)
        out["hgt_variants"][key] = {"name": r["name"], **{t: r["mean"][t] for t in ("t1", "t2", "t3") if t in r["mean"]}}
    return out


if __name__ == "__main__":
    sys.exit(main())
