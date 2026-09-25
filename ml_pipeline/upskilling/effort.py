# ml_pipeline/upskilling/effort.py

"""
Learning-effort weight per skill: a DOCUMENTED HEURISTIC, not measured learning time.

  effort(s | S) = reuse_factor(s) * proximity_factor(s, S)

  reuse_factor       ESCO reuse level: transversal 0.70, cross-sector 0.85,
                     sector-specific 1.00, occupation-specific 1.15 (broader skills are
                     assumed quicker to pick up; unknown -> 1.00)
  proximity_factor   0.70 if s is an ESCO "related" skill of, or shares a skill group
                     with, something the person already knows; else 1.00

So efforts range roughly 0.5-1.15 ("about one typical skill" = 1.0). Users can
override any weight in the UI; the budgeted planner then uses their numbers.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

REUSE = {"transversal": 0.70, "cross-sector": 0.85, "sector-specific": 1.00, "occupation-specific": 1.15}
NEAR = 0.70


class EffortModel:
    def __init__(self, esco_dir: Path, skill_ids: list[str]):
        self.skill_ids = skill_ids
        idx = {u: i for i, u in enumerate(skill_ids)}
        skills = pd.read_csv(esco_dir / "skills_en.csv", dtype=str, keep_default_na=False,
                             usecols=["conceptUri", "reuseLevel"]).drop_duplicates("conceptUri")
        reuse = dict(zip(skills["conceptUri"], skills["reuseLevel"], strict=True))
        self.reuse = np.array([REUSE.get(reuse.get(u, ""), 1.0) for u in skill_ids])
        self.reuse_label = [reuse.get(u, "") or "unknown" for u in skill_ids]

        neighbours: list[set[int]] = [set() for _ in skill_ids]
        rel = pd.read_csv(esco_dir / "skillSkillRelations_en.csv", dtype=str, keep_default_na=False,
                          usecols=["originalSkillUri", "relatedSkillUri"])
        for a, b in zip(rel["originalSkillUri"], rel["relatedSkillUri"], strict=True):
            if a in idx and b in idx:
                neighbours[idx[a]].add(idx[b])
                neighbours[idx[b]].add(idx[a])
        broader = pd.read_csv(esco_dir / "broaderRelationsSkillPillar_en.csv", dtype=str, keep_default_na=False,
                              usecols=["conceptUri", "broaderUri"])
        by_group: dict[str, list[int]] = {}
        for c, g in zip(broader["conceptUri"], broader["broaderUri"], strict=True):
            if c in idx:
                by_group.setdefault(g, []).append(idx[c])
        for members in by_group.values():
            if len(members) <= 60:  # huge groups say little about closeness
                for m in members:
                    neighbours[m].update(members)
        self.neighbours = [n - {i} for i, n in enumerate(neighbours)]

    def costs(self, have: np.ndarray) -> np.ndarray:
        near = np.zeros(len(self.skill_ids), dtype=bool)
        for s in have:
            near[list(self.neighbours[int(s)])] = True
        return self.reuse * np.where(near, NEAR, 1.0)

    def explain(self, s: int, have: np.ndarray) -> dict:
        close = [int(h) for h in have if int(h) in self.neighbours[s]]
        return {"reuse_level": self.reuse_label[s], "reuse_factor": float(self.reuse[s]),
                "close_to_known_skills": close, "proximity_factor": NEAR if close else 1.0,
                "effort": float(self.reuse[s] * (NEAR if close else 1.0)),
                "note": "heuristic proxy, not measured learning time"}
