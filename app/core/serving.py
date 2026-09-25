# app/core/serving.py

"""
Runtime state for the Yojak stakeholder views, loaded lazily and once.

  Market           every posting's ESCO skills, IDF weights and predicted salary range
  SalaryModel      quantile models + conformal margin + support counts
  JobRanker        ranks postings for a skill profile with the model that WON the
                   Phase 2 benchmark (reports/model_comparison.json). If the winner can't be
                   served at interactive latency, the best servable model is used and the
                   response says so.
  workforce        precomputed demand / shortage tables
  candidates       the SYNTHETIC recruiter pool
"""

from __future__ import annotations

import json
import threading
from functools import cached_property

import numpy as np
import pandas as pd
import scipy.sparse as sp
from sklearn.preprocessing import normalize

from app.core.settings import get_settings

SERVABLE = {"b1": "B1 TF-IDF kNN", "b3a": "B3a Adamic-Adar"}


class JobRanker:
    """Candidate -> posting scoring on the full market (all known postings)."""

    def __init__(self, R: sp.csr_matrix, kind: str):
        self.kind = kind
        R = R.tocsr().astype(np.float32)
        df = np.asarray((R > 0).sum(axis=0)).ravel()
        n = R.shape[0]
        self.idf = (np.log((1 + n) / (1 + df)) + 1.0).astype(np.float32)
        self.inv_skill = (1.0 / np.log(2.0 + df)).astype(np.float32)
        self.R = R
        self.R_tfidf = normalize(R.multiply(self.idf).tocsr())

    def _q(self, skills: list[int]) -> sp.csr_matrix:
        q = sp.csr_matrix((np.ones(len(skills), dtype=np.float32), (np.zeros(len(skills), dtype=np.int64), skills)),
                          shape=(1, self.R.shape[1]))
        return q

    def score(self, skills: list[int], rows: np.ndarray | None = None) -> np.ndarray:
        if not skills:
            return np.zeros(self.R.shape[0] if rows is None else len(rows), dtype=np.float32)
        q = self._q(skills)
        if self.kind == "b1":
            q = normalize(q.multiply(self.idf).tocsr())
            M = self.R_tfidf if rows is None else self.R_tfidf[rows]
        else:  # b3a: Adamic-Adar common-neighbour score
            q = q.multiply(self.inv_skill).tocsr()
            M = self.R if rows is None else self.R[rows]
        return np.asarray((q @ M.T).todense()).ravel()

    def occlusion(self, skills: list[int], row: int) -> dict[int, float]:
        """Score drop for one posting when each input skill is removed ('why' panel)."""
        base = float(self.score(skills, np.array([row]))[0])
        out = {}
        for s in skills:
            rest = [x for x in skills if x != s]
            out[s] = round(base - float(self.score(rest, np.array([row]))[0]), 5)
        return out


class Serving:
    _instance: Serving | None = None
    _lock = threading.Lock()

    @classmethod
    def get(cls) -> Serving:
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @cached_property
    def market(self):
        from ml_pipeline.upskilling.market import load_market

        return load_market()

    @cached_property
    def salary(self):
        from ml_pipeline.salary.model import SalaryModel

        return SalaryModel.load()

    @cached_property
    def salary_caveat(self) -> dict:
        from ml_pipeline.common import read_report

        r = read_report("salary_eval") or {}
        auc = r.get("selection_bias", {}).get("propensity", {}).get("auc")
        cov = r.get("test", {}).get("coverage_cqr")
        return {
            "what": "posted salary midpoint (annual INR), not realised pay",
            "interval": "P10-P90, conformally calibrated",
            "held_out_coverage": cov,
            "disclosure_bias_auc": auc,
            "note": ("Only about a third of postings disclose pay and disclosure is predictable from job "
                     "features, so ranges are least reliable where few similar postings disclose salary."),
        }

    @cached_property
    def model_choice(self) -> dict:
        from ml_pipeline.common import read_report

        rep = read_report("model_comparison") or {}
        winner = rep.get("comparison", {}).get("winner")
        if winner in SERVABLE:
            served = winner
        else:
            t3 = {k: v["mean"]["t3"]["ndcg@10"] for k, v in rep.get("models", {}).items()
                  if k in SERVABLE and "t3" in v.get("mean", {})}
            served = max(t3, key=t3.get) if t3 else "b1"
        return {"benchmark_winner": winner, "served": served, "served_name": SERVABLE[served],
                "note": None if served == winner else
                ("The benchmark winner is not served at interactive latency; the best servable model is used."
                 if winner else "No benchmark report yet; TF-IDF kNN is used.")}

    @cached_property
    def ranker(self) -> JobRanker:
        return JobRanker(self.market.R, self.model_choice["served"])

    @cached_property
    def skill_labels(self) -> dict[str, str]:
        s = get_settings()
        df = pd.read_csv(s.esco_data_dir / "skills_en.csv", dtype=str, keep_default_na=False,
                         usecols=["conceptUri", "preferredLabel", "skillType"]).drop_duplicates("conceptUri")
        self._skill_type = dict(zip(df["conceptUri"], df["skillType"], strict=True))
        return dict(zip(df["conceptUri"], df["preferredLabel"], strict=True))

    def skill_type(self, uri: str) -> str | None:
        _ = self.skill_labels
        return self._skill_type.get(uri)

    @cached_property
    def occupation_profiles(self) -> dict[str, dict[str, str]]:
        s = get_settings()
        rel = pd.read_csv(s.esco_data_dir / "occupationSkillRelations_en.csv", dtype=str, keep_default_na=False,
                          usecols=["occupationUri", "skillUri", "relationType"])
        out: dict[str, dict[str, str]] = {}
        for o, sk, t in zip(rel["occupationUri"], rel["skillUri"], rel["relationType"], strict=True):
            out.setdefault(o, {})[sk] = t
        return out

    @cached_property
    def effort(self):
        from ml_pipeline.upskilling.effort import EffortModel

        return EffortModel(get_settings().esco_data_dir, self.market.skills)

    @cached_property
    def candidates(self) -> pd.DataFrame:
        path = get_settings().artifacts_dir / "synthetic" / "candidates.parquet"
        return pd.read_parquet(path) if path.exists() else pd.DataFrame()

    def workforce_table(self, name: str) -> pd.DataFrame:
        path = get_settings().artifacts_dir / "workforce" / f"{name}.parquet"
        if not path.exists():
            raise FileNotFoundError(f"{path.name} missing: run python -m ml_pipeline.supply.workforce")
        return pd.read_parquet(path)

    @cached_property
    def job_field(self) -> dict[str, str]:
        try:
            t = self.workforce_table("job_field")
            return dict(zip(t["jobId"], t["field"], strict=True))
        except FileNotFoundError:
            return {}

    def skill_indices(self, uris: list[str]) -> list[int]:
        idx = self.market.skill_index
        return [idx[u] for u in uris if u in idx]

    def salary_range_for_rows(self, rows: np.ndarray) -> list[dict]:
        m = self.market
        from ml_pipeline.salary.model import MIN_SUPPORT

        return [{"p10": round(float(m.p10[r]), -3), "p50": round(float(m.p50[r]), -3), "p90": round(float(m.p90[r]), -3),
                 "n_support": int(m.salary_n_support[r]), "sufficient": bool(m.salary_n_support[r] >= MIN_SUPPORT)}
                for r in rows]


def json_ready(obj):
    return json.loads(json.dumps(obj, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
