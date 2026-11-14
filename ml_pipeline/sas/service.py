"""Local-only artifact service, isolated from legacy salary and snapshot serving."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import MultiLabelBinarizer

from ml_pipeline.upskilling.engine import CoverageProblem, exact_ilp, frequency, greedy_F, lazy_greedy_G

from .data import BANDS, PRIVATE, skills_of
from .model import band_sets

LIMITATIONS = ["Historical supplied snapshot, not live vacancies.", "Salary units and pay period are unverified.",
               "Observed skill coverage is not a hiring probability or causal salary gain.",
               "Most skill lists are truncated; absent skills are not proven unnecessary."]


def vocabulary_evidence(have: set[str], skill_lists) -> dict:
    vocabulary = {skill for skills in skill_lists for skill in skills}
    observed = sorted(have & vocabulary)
    return {"submitted": len(have), "observed_count": len(observed), "observed": observed,
            "unobserved": sorted(have - vocabulary),
            "fraction": len(observed) / len(have) if have else None,
            "meaning": "Presence in the selected posting pool, not proof of proficiency or skill relevance."}


class SasService:
    def __init__(self, out: Path = PRIVATE):
        self.manifest = json.loads((out / "manifest.json").read_text())
        self.frame = pd.read_parquet(out / "analytics.parquet")
        self.model = joblib.load(out / "band_model.joblib")
        # Single-row serving needs no GPU allocation; avoid CUDA context ownership
        # across ASGI worker threads and keep training hardware separate from serving.
        if self.model.kind in {"aft", "soft_target"}:
            self.model.estimator.set_param({"device": "cpu"})
        self.salary = json.loads((out / "salary_report.json").read_text())
        if self.salary.get("source_version") != self.manifest["source_version"] or self.salary.get("preparation_code_hash") != self.manifest["preparation_code_hash"]:
            raise ValueError("SAS artifacts do not match the current preparation manifest; rerun training.")
        research = out / "research_report.json"
        self.research = json.loads(research.read_text()) if research.exists() else {}

    def metadata(self):
        return {"source": "SAS supplied datasets", "source_version": self.manifest["source_version"],
                "model_id": self.salary["champion"], "unit_status": "unverified", "limitations": LIMITATIONS}

    def pool(self, family: str, experience: float, complete_only=False):
        if family not in set(self.frame.role_family) | {"All"}:
            raise ValueError("Unknown role family")
        frame = self.frame[(self.frame.exp_min <= experience) & (self.frame.exp_max >= experience) & ~self.frame.quality_flag]
        if family != "All":
            frame = frame[frame.role_family == family]
        if complete_only:
            frame = frame[~frame.skills_truncated]
        return frame

    def match(self, family: str, experience: float, skills: list[str], complete_only=False):
        frame = self.pool(family, experience, complete_only)
        have = set(skills_of(",".join(skills), False))
        rows = []
        for _, row in frame.iterrows():
            required = set(row.skills)
            overlap = sorted(required & have)
            rows.append({"row_key": row.row_key, "title": row.job_desig, "location": row.location,
                         "score": len(overlap) / len(required) if required else 0,
                         "matched": overlap, "missing": sorted(required - have), "skills_truncated": bool(row.skills_truncated)})
        rows.sort(key=lambda r: (-r["score"], r["row_key"]))
        return {**self.metadata(), "support": len(frame), "roles": sorted(self.frame.role_family.unique().tolist()),
                "matches": rows[:12], "vocabulary_evidence": vocabulary_evidence(have, frame.skills),
                "research": {k: self.research.get(k) for k in ["jds", "sds"]}}

    def plan(self, family: str, experience: float, skills: list[str], complete_only=False):
        frame = self.pool(family, experience, complete_only)
        if frame.empty:
            return {**self.metadata(), "support": 0, "before": 0, "optimized": None, "frequency": None}
        encoder = MultiLabelBinarizer(sparse_output=True)
        matrix = encoder.fit_transform(frame.skills)
        have = set(skills_of(",".join(skills), False))
        known = np.array([i for i, s in enumerate(encoder.classes_) if s in have], dtype=int)
        problem = CoverageProblem(matrix, np.ones(matrix.shape[1], dtype=int), np.ones(len(frame)), known, .6)
        freq = frequency(problem, 3)
        candidates = [greedy_F(problem, 3), lazy_greedy_G(problem, 3), freq]
        best = max(candidates, key=lambda p: (p.F, p.G))
        solver = "greedy comparison"
        if len(frame) <= 500 and len(problem.candidates()) <= 200:
            exact = exact_ilp(problem, k=3, time_limit=1.0, hint=best.skills)
            if exact.F >= best.F:
                best, solver = exact, "CP-SAT"
        def summary(plan):
            return {"skills": encoder.classes_[plan.skills].tolist(), "coverage": int(plan.F), "seconds": plan.seconds,
                    "proven_optimal": plan.optimal is True, "upper_bound": plan.bound}
        return {**self.metadata(), "support": len(frame), "before": int(problem.F([])), "threshold": .6,
                "optimized": summary(best), "frequency": summary(freq), "solver": solver,
                "meaning": "Postings reaching 60% of observed equally weighted skills, not job eligibility."}

    def pay(self, family: str, experience: float, skills: list[str], complete_only=False):
        frame = self.pool(family, experience, complete_only)
        base = {**self.metadata(), "support": len(frame), "target_coverage": .9,
                "observed_test_coverage": self.salary["calibration"]["test_coverage"]}
        if len(frame) < 20 or family in {"All", "Other"}:
            return {**base, "available": False, "reason": "Choose a specific role with at least 20 comparable records."}
        # User scenarios are not exact job postings. Keep the deployment caveat visible.
        query = pd.DataFrame([{ "job_desig": family, "skills": skills_of(",".join(skills), False), "location": "",
                               "exp_min": experience, "exp_max": experience, "exp_width": 0,
                               "skills_truncated": False, "description_missing": True}])
        point = self.model.predict(query)
        lo, hi = band_sets(point, self.model.radius)
        return {**base, "available": True, "bands": BANDS[int(lo[0]):int(hi[0]) + 1], "point_band": BANDS[int(point[0])],
                "deployment_caveat": "Illustrative profile scenario; calibration was measured on postings, not user profiles. No 90% guarantee for this scenario.",
                "observed_band_counts": Counter(frame.salary).most_common()}
