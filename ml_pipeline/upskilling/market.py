# ml_pipeline/upskilling/market.py

"""
The job market as the upskilling engine sees it: every posting's ESCO skills as a
sparse matrix, integer IDF weights, and a predicted median salary per posting.
Shared by the evaluation and the API (built once, cached in artifacts/upskilling/).
"""

from __future__ import annotations

from dataclasses import dataclass

import joblib
import numpy as np
import pandas as pd
import scipy.sparse as sp

from app.core.settings import get_settings
from ml_pipeline.upskilling.engine import CoverageProblem, idf_weights

JOB_COLS = ["jobId", "title", "companyName", "dup_group_id", "occupation_uri", "occupation_label", "isco_code",
            "primary_city", "primary_state", "primary_tier", "primary_metro_region", "exp_band", "exp_min",
            "work_mode", "salary_disclosed", "salary_min_inr", "salary_max_inr", "skill_uris", "nco_family",
            "posted_date"]


@dataclass
class Market:
    jobs: pd.DataFrame          # one row per posting with >= 1 linked skill (position = matrix row)
    skills: list[str]           # ESCO skill URIs (matrix columns)
    skill_index: dict[str, int]
    R: sp.csr_matrix            # postings x skills
    w: np.ndarray               # integer IDF weights
    p10: np.ndarray             # predicted salary range per posting (INR)
    p50: np.ndarray
    p90: np.ndarray
    salary_n_support: np.ndarray

    def problem(self, rows: np.ndarray, have: np.ndarray, tau: float, value: str = "count") -> CoverageProblem:
        v = np.ones(len(rows)) if value == "count" else self.p50[rows]
        return CoverageProblem(self.R[rows], self.w, v, have, tau)

    def pool(self, isco2: str | None = None, exp_bands: list[str] | None = None, tiers: list[int] | None = None,
             states: list[str] | None = None, occupation_uri: str | None = None,
             exclude_group: str | None = None) -> np.ndarray:
        m = np.ones(len(self.jobs), dtype=bool)
        j = self.jobs
        if occupation_uri:
            m &= j["occupation_uri"].eq(occupation_uri).to_numpy()
        elif isco2:
            m &= j["isco_code"].fillna("").astype(str).str[:2].eq(isco2).to_numpy()
        if exp_bands:
            m &= j["exp_band"].isin(exp_bands).to_numpy()
        if tiers:
            m &= j["primary_tier"].isin(tiers).to_numpy()
        if states:
            m &= j["primary_state"].isin(states).to_numpy()
        if exclude_group:
            m &= j["dup_group_id"].ne(exclude_group).to_numpy()
        return np.where(m)[0]


def build_market() -> Market:
    s = get_settings()
    jobs = pd.read_parquet(s.processed_data_dir / "india" / "jobs.parquet")
    jobs = jobs[jobs["skill_uris"].map(len) > 0].reset_index(drop=True)
    skills = sorted({u for us in jobs["skill_uris"] for u in us})
    sidx = {u: i for i, u in enumerate(skills)}
    rows = np.repeat(np.arange(len(jobs)), jobs["skill_uris"].map(len).to_numpy())
    cols = np.array([sidx[u] for us in jobs["skill_uris"] for u in us])
    R = sp.csr_matrix((np.ones(len(cols), dtype=np.int64), (rows, cols)), shape=(len(jobs), len(skills)))
    R.data[:] = 1
    from ml_pipeline.salary.model import SalaryModel

    sal = SalaryModel.load().predict(jobs)
    return Market(jobs=jobs[[c for c in JOB_COLS if c in jobs]].copy(), skills=skills, skill_index=sidx, R=R,
                  w=idf_weights(R), p10=sal["p10"].to_numpy(), p50=sal["p50"].to_numpy(),
                  p90=sal["p90"].to_numpy(), salary_n_support=sal["n_support"].to_numpy())


def load_market(rebuild: bool = False) -> Market:
    path = get_settings().artifacts_dir / "upskilling" / "market.joblib"
    src = get_settings().processed_data_dir / "india" / "jobs.parquet"
    sal = get_settings().artifacts_dir / "salary" / "salary_model.joblib"
    fresh = path.exists() and path.stat().st_mtime > max(src.stat().st_mtime, sal.stat().st_mtime)
    if fresh and not rebuild:
        return joblib.load(path)
    m = build_market()
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(m, path)
    return m
