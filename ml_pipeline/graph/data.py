# ml_pipeline/graph/data.py

"""
Graph data and leakage-safe evaluation splits.

Split unit = near-duplicate group (`dup_group_id`), hashed with a seed:
  train 70% | val 10% | test 10% | pool 10%

Edges are either KNOWN (usable by every model for training and message passing)
or HIDDEN (evaluation targets, never seen by any model):
  * train and pool jobs: all job->skill edges known
  * val and test jobs:   half of each job's skills known, half hidden (T1 targets)
  * ESCO occupations:    20% of each occupation's skills hidden (T2 targets)

Tasks
  T1  job skill completion      rank skills for a val/test job given its known skills
  T2  occupation skill recovery rank skills for an occupation given 80% of its ESCO skills
  T3  candidate -> job fit      a pseudo-candidate (40-70% of a pool job's skills + 2
                                random noise skills) ranks all pool jobs; the source job
                                is grade 2, pool jobs of the same ESCO occupation grade 1.
                                A PROXY: there is no real application or hire data.

`vocab="esco"` uses linked ESCO skills; `vocab="tags"` uses raw Naukri tags (the
"without skill linking" ablation). Both use the same job split and the same T3
query jobs, so T3 is comparable across vocabularies.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp

from app.core.settings import get_settings

SPLIT_SEED = 17
T3_QUERIES = 2000
T3_NOISE = 2
MIN_TAG_FREQ = 3  # raw-tag vocabulary for the no-linking ablation


def split_of(group: str, seed: int = SPLIT_SEED) -> str:
    h = int(hashlib.sha256(f"{seed}:{group}".encode()).hexdigest()[:8], 16) % 100
    return "train" if h < 70 else "val" if h < 80 else "test" if h < 90 else "pool"


@dataclass
class GraphData:
    vocab: str
    skills: list[str]                       # skill ids (ESCO uri or raw tag)
    skill_index: dict[str, int]
    skill_text: list[str]                   # label text for text-based models
    jobs: pd.DataFrame                      # one row per job, with `split` and `jidx`
    known: sp.csr_matrix                    # jobs x skills, 1 = known edge
    hidden: dict[int, np.ndarray]           # jidx -> hidden skill indices (val/test)
    occupations: list[str] = field(default_factory=list)
    occ_index: dict[str, int] = field(default_factory=dict)
    occ_text: list[str] = field(default_factory=list)
    occ_known: sp.csr_matrix | None = None  # occupations x skills
    occ_hidden: dict[int, np.ndarray] = field(default_factory=dict)
    occ_weight: sp.csr_matrix | None = None  # 1.0 essential / 0.5 optional (known edges only)
    t3_queries: list[dict] = field(default_factory=list)
    # Model selection only (scoring rules, hyper-parameters): same construction as T3
    # but the pool and queries are TRAIN jobs, so the test pool is never used to choose.
    t3_dev_pool: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.int64))
    t3_dev_queries: list[dict] = field(default_factory=list)

    @property
    def n_jobs(self) -> int:
        return len(self.jobs)

    @property
    def n_skills(self) -> int:
        return len(self.skills)

    def job_ids(self, split: str) -> np.ndarray:
        return self.jobs.loc[self.jobs["split"] == split, "jidx"].to_numpy()

    def eval_jobs(self, split: str) -> np.ndarray:
        return np.array([j for j in self.job_ids(split) if j in self.hidden], dtype=np.int64)


def _load_jobs() -> pd.DataFrame:
    d = get_settings().processed_data_dir / "india"
    cols = ["jobId", "dup_group_id", "title", "title_clean", "tags", "skill_uris", "occupation_uri",
            "companyName", "primary_city", "primary_state", "primary_tier", "exp_band", "exp_min",
            "posted_date", "days_ago", "salary_mid_inr", "salary_disclosed", "work_mode"]
    return pd.read_parquet(d / "jobs.parquet", columns=cols)


def _esco_skill_labels() -> dict[str, str]:
    esco = get_settings().esco_data_dir
    df = pd.read_csv(esco / "skills_en.csv", dtype=str, keep_default_na=False, usecols=["conceptUri", "preferredLabel"])
    return dict(zip(df["conceptUri"], df["preferredLabel"], strict=True))


def _esco_occupations() -> tuple[pd.DataFrame, pd.DataFrame]:
    esco = get_settings().esco_data_dir
    occ = pd.read_csv(esco / "occupations_en.csv", dtype=str, keep_default_na=False,
                      usecols=["conceptUri", "preferredLabel", "iscoGroup"])
    rel = pd.read_csv(esco / "occupationSkillRelations_en.csv", dtype=str, keep_default_na=False,
                      usecols=["occupationUri", "skillUri", "relationType"])
    return occ, rel


def build(vocab: str = "esco", seed: int = SPLIT_SEED, jobs: pd.DataFrame | None = None) -> GraphData:
    if vocab not in {"esco", "tags"}:
        raise ValueError("vocab must be 'esco' or 'tags'")
    rng = np.random.default_rng(seed)
    jobs = (_load_jobs() if jobs is None else jobs).copy().reset_index(drop=True)
    jobs["split"] = jobs["dup_group_id"].map(lambda g: split_of(g, seed))
    items_col = "skill_uris" if vocab == "esco" else "tags"
    jobs["items"] = jobs[items_col].map(lambda xs: list(dict.fromkeys(xs)) if xs is not None else [])

    if vocab == "tags":
        # Only tags seen MIN_TAG_FREQ+ times in non-held-out jobs, so rare noise doesn't dominate.
        freq: dict[str, int] = {}
        for xs in jobs["items"]:
            for t in xs:
                freq[t] = freq.get(t, 0) + 1
        keep = {t for t, c in freq.items() if c >= MIN_TAG_FREQ}
        jobs["items"] = jobs["items"].map(lambda xs: [t for t in xs if t in keep])

    occ_df, rel = _esco_occupations()
    esco_labels = _esco_skill_labels()
    if vocab == "esco":
        skill_ids = sorted(set(u for xs in jobs["items"] for u in xs) | set(rel["skillUri"]))
        skill_text = [esco_labels.get(u, u) for u in skill_ids]
    else:
        skill_ids = sorted(set(t for xs in jobs["items"] for t in xs))
        skill_text = list(skill_ids)
    sidx = {s: i for i, s in enumerate(skill_ids)}

    jobs = jobs[jobs["items"].map(len) > 0].reset_index(drop=True)
    jobs["jidx"] = np.arange(len(jobs))

    rows, cols, hidden = [], [], {}
    for j, split, items in zip(jobs["jidx"], jobs["split"], jobs["items"], strict=True):
        ids = np.array([sidx[s] for s in items], dtype=np.int64)
        if split in {"val", "test"} and len(ids) >= 2:
            perm = rng.permutation(len(ids))
            n_known = math.ceil(len(ids) / 2)
            known_ids, hidden_ids = ids[perm[:n_known]], ids[perm[n_known:]]
            hidden[int(j)] = hidden_ids
        else:
            known_ids = ids
        rows.extend([j] * len(known_ids))
        cols.extend(known_ids.tolist())
    known = sp.csr_matrix((np.ones(len(rows), dtype=np.float32), (rows, cols)), shape=(len(jobs), len(skill_ids)))

    data = GraphData(vocab=vocab, skills=skill_ids, skill_index=sidx, skill_text=skill_text,
                     jobs=jobs, known=known, hidden=hidden)

    if vocab == "esco":
        occ_ids = occ_df["conceptUri"].tolist()
        oidx = {o: i for i, o in enumerate(occ_ids)}
        rel = rel[rel["occupationUri"].isin(oidx) & rel["skillUri"].isin(sidx)]
        o_rows, o_cols, o_w, occ_hidden = [], [], [], {}
        for occ, g in rel.groupby("occupationUri"):
            o = oidx[occ]
            s_ids = g["skillUri"].map(sidx).to_numpy()
            w = np.where(g["relationType"].to_numpy() == "essential", 1.0, 0.5)
            if len(s_ids) >= 5:
                perm = rng.permutation(len(s_ids))
                n_hidden = max(1, int(round(0.2 * len(s_ids))))
                occ_hidden[o] = s_ids[perm[:n_hidden]]
                keep = perm[n_hidden:]
                s_ids, w = s_ids[keep], w[keep]
            o_rows.extend([o] * len(s_ids))
            o_cols.extend(s_ids.tolist())
            o_w.extend(w.tolist())
        shape = (len(occ_ids), len(skill_ids))
        data.occupations = occ_ids
        data.occ_index = oidx
        data.occ_text = occ_df["preferredLabel"].tolist()
        data.occ_known = sp.csr_matrix((np.ones(len(o_rows), dtype=np.float32), (o_rows, o_cols)), shape=shape)
        data.occ_weight = sp.csr_matrix((np.array(o_w, dtype=np.float32), (o_rows, o_cols)), shape=shape)
        data.occ_hidden = occ_hidden

    data.t3_queries = make_t3_queries(data, seed)
    train = data.jobs[data.jobs["split"] == "train"]
    dev_ids = sorted(train["jobId"], key=lambda x: hashlib.sha256(f"dev{seed}:{x}".encode()).hexdigest())[:9500]
    dev_mask = data.jobs["jobId"].isin(set(dev_ids))
    data.t3_dev_pool = data.jobs.loc[dev_mask, "jidx"].to_numpy()
    data.t3_dev_queries = make_t3_queries(data, seed + 100, pool_mask=dev_mask, n=1000)
    return data


def make_t3_queries(data: GraphData, seed: int, pool_mask: pd.Series | None = None,
                    n: int = T3_QUERIES) -> list[dict]:
    """Pseudo-candidates drawn from pool jobs (same jobs for both vocabularies)."""
    rng = np.random.default_rng(seed + 1)
    pool = data.jobs[data.jobs["split"] == "pool"] if pool_mask is None else data.jobs[pool_mask]
    eligible = pool[pool["items"].map(len) >= 4]
    # Choose query jobs by jobId (vocab-independent) so both vocabularies use the same ones.
    ids = sorted(eligible["jobId"].tolist(), key=lambda x: hashlib.sha256(f"{seed}:{x}".encode()).hexdigest())
    chosen = set(ids[:n])
    pop = np.asarray(data.known.sum(axis=0)).ravel()
    pop = pop / pop.sum()
    occ_of = dict(zip(pool["jidx"], pool["occupation_uri"], strict=True))
    by_occ: dict[str, list[int]] = {}
    for j, o in occ_of.items():
        if o:
            by_occ.setdefault(o, []).append(int(j))
    queries = []
    for row in eligible[eligible["jobId"].isin(chosen)].itertuples(index=False):
        own = np.array([data.skill_index[s] for s in row.items], dtype=np.int64)
        frac = rng.uniform(0.4, 0.7)
        k = max(2, int(round(frac * len(own))))
        subset = rng.choice(own, size=k, replace=False)
        noise = []
        while len(noise) < T3_NOISE:
            s = int(rng.choice(len(pop), p=pop))
            if s not in own and s not in noise:
                noise.append(s)
        rel = {int(j): 1 for j in by_occ.get(row.occupation_uri, [])} if row.occupation_uri else {}
        rel[int(row.jidx)] = 2
        queries.append({"source_job": int(row.jidx), "jobId": row.jobId,
                        "skills": np.concatenate([subset, np.array(noise, dtype=np.int64)]),
                        "relevance": rel})
    return queries


def leakage_report(data: GraphData) -> dict:
    """Checks every model relies on: no hidden edge is known; splits are group-disjoint."""
    hidden_known = 0
    for j, hs in data.hidden.items():
        row = data.known[j].indices
        hidden_known += int(np.isin(hs, row).sum())
    occ_hidden_known = 0
    if data.occ_known is not None:
        for o, hs in data.occ_hidden.items():
            occ_hidden_known += int(np.isin(hs, data.occ_known[o].indices).sum())
    groups = data.jobs.groupby("dup_group_id")["split"].nunique()
    t3_sources_in_pool = all(data.jobs.at[q["source_job"], "split"] == "pool" for q in data.t3_queries)
    return {
        "hidden_edges_in_known": hidden_known,
        "occ_hidden_edges_in_known": occ_hidden_known,
        "groups_spanning_splits": int((groups > 1).sum()),
        "t3_sources_all_in_pool": bool(t3_sources_in_pool),
        "split_sizes": data.jobs["split"].value_counts().to_dict(),
        "t1_eval_jobs": {"val": len(data.eval_jobs("val")), "test": len(data.eval_jobs("test"))},
        "t2_eval_occupations": len(data.occ_hidden),
        "t3_queries": len(data.t3_queries),
        "t3_dev_queries_from_train": len(data.t3_dev_queries),
        "t3_dev_pool_all_train": bool((data.jobs.loc[data.t3_dev_pool, "split"] == "train").all()),
        "n_skills": data.n_skills,
        "known_job_skill_edges": int(data.known.nnz),
        "hidden_job_skill_edges": int(sum(len(h) for h in data.hidden.values())),
    }


def cache_path(vocab: str, seed: int) -> Path:
    d = get_settings().artifacts_dir / "graph"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"data_{vocab}_seed{seed}.pkl"


def load_or_build(vocab: str = "esco", seed: int = SPLIT_SEED, rebuild: bool = False) -> GraphData:
    import pickle

    path = cache_path(vocab, seed)
    src = get_settings().processed_data_dir / "india" / "jobs.parquet"
    if path.exists() and not rebuild and path.stat().st_mtime > src.stat().st_mtime:
        with open(path, "rb") as f:
            return pickle.load(f)
    data = build(vocab, seed)
    with open(path, "wb") as f:
        pickle.dump(data, f)
    return data
