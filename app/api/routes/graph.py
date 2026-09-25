# app/api/routes/graph.py

"""The skill-occupation graph as seen through Indian postings, for the landing-page visual."""

from __future__ import annotations

from functools import lru_cache

import numpy as np
from fastapi import APIRouter, Query

from app.core.serving import Serving

router = APIRouter(prefix="/graph", tags=["graph"])


@lru_cache(maxsize=4)
def _constellation(n_skills: int, n_occupations: int, n_edges: int) -> dict:
    srv = Serving.get()
    m = srv.market
    R = m.R.tocsc().astype(np.float32)
    demand = np.asarray(R.sum(axis=0)).ravel()
    top = np.argsort(-demand)[:n_skills]
    sub = R[:, top]
    co = (sub.T @ sub).toarray()
    np.fill_diagonal(co, 0)
    n = R.shape[0]
    expected = np.outer(demand[top], demand[top]) / n
    lift = np.divide(co, expected, out=np.zeros_like(co), where=expected > 0)
    iu = np.triu_indices(len(top), 1)
    score = np.where(co[iu] >= 30, np.log(lift[iu] + 1e-9), -np.inf)  # at least 30 shared postings
    order = np.argsort(-score)[:n_edges]
    edges = [{"source": f"s{top[iu[0][k]]}", "target": f"s{top[iu[1][k]]}", "weight": round(float(score[k]), 3),
              "postings": int(co[iu[0][k], iu[1][k]]), "kind": "co-listed"}
             for k in order if np.isfinite(score[k]) and score[k] > 0]

    occ = m.jobs["occupation_uri"].fillna("").to_numpy()
    occ_counts = {o: c for o, c in zip(*np.unique(occ[occ != ""], return_counts=True), strict=True)}
    top_occ = sorted(occ_counts, key=occ_counts.get, reverse=True)[:n_occupations]
    labels = dict(zip(m.jobs["occupation_uri"], m.jobs["occupation_label"], strict=False))
    top_set = {int(s): i for i, s in enumerate(top)}
    for o in top_occ:
        rows = np.where(occ == o)[0]
        counts = np.asarray(m.R[rows].sum(axis=0)).ravel()
        share = counts / max(len(rows), 1)
        lift_o = np.divide(share, demand / n, out=np.zeros_like(share), where=demand > 0)
        best = [int(s) for s in np.argsort(-(lift_o * (counts >= 10)))[:4] if int(s) in top_set and counts[s] >= 10]
        edges += [{"source": f"o{o}", "target": f"s{s}", "weight": round(float(np.log(lift_o[s])), 3),
                   "postings": int(counts[s]), "kind": "characteristic of"} for s in best]
    nodes = [{"id": f"s{int(s)}", "label": srv.skill_labels.get(m.skills[s], m.skills[s]), "kind": "skill",
              "uri": m.skills[s], "postings": int(demand[s])} for s in top]
    nodes += [{"id": f"o{o}", "label": labels.get(o, o), "kind": "occupation", "uri": o, "postings": int(occ_counts[o])}
              for o in top_occ]
    return {"nodes": nodes, "edges": edges,
            "source": "ESCO skills and occupations as listed in Naukri postings (edge = skills co-listed far more "
                      "often than chance, or skills characteristic of an occupation's postings)",
            "postings": int(n)}


@router.get("/constellation")
def constellation(skills: int = Query(140, ge=20, le=300), occupations: int = Query(30, ge=0, le=80),
                  edges: int = Query(360, ge=20, le=1500)) -> dict:
    return _constellation(skills, occupations, edges)
