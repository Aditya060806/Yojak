# app/api/routes/jobs.py

from __future__ import annotations

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, Query, status

from app.core.deps import Neo4jDep
from app.core.serving import Serving

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _row(i: int) -> dict:
    srv = Serving.get()
    m = srv.market
    j = m.jobs.iloc[i]
    return {
        "job_id": j["jobId"], "title": j["title"], "company": j["companyName"], "city": j["primary_city"],
        "state": j["primary_state"], "tier": None if pd.isna(j["primary_tier"]) else int(j["primary_tier"]),
        "exp_band": j["exp_band"], "occupation_uri": j["occupation_uri"], "occupation_label": j["occupation_label"],
        "nco_family": j["nco_family"], "posted_date": None if pd.isna(j["posted_date"]) else str(j["posted_date"])[:10],
        "skills": [{"uri": m.skills[s], "label": srv.skill_labels.get(m.skills[s], m.skills[s])} for s in m.R[i].indices],
        "salary": srv.salary_range_for_rows(np.array([i]))[0],
        "salary_disclosed": bool(j["salary_disclosed"]),
    }


@router.get("")
def search(q: str = Query("", max_length=100), tier: int | None = Query(None, ge=1, le=3),
           state: str | None = None, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)) -> dict:
    m = Serving.get().market
    mask = np.ones(len(m.jobs), dtype=bool)
    if q:
        mask &= m.jobs["title"].str.contains(q, case=False, regex=False).to_numpy()
    if tier:
        mask &= (m.jobs["primary_tier"] == tier).to_numpy()
    if state:
        mask &= (m.jobs["primary_state"] == state).to_numpy()
    idx = np.where(mask)[0]
    return {"total": int(len(idx)), "jobs": [_row(int(i)) for i in idx[offset:offset + limit]]}


@router.get("/{job_id}")
def get_job(job_id: str) -> dict:
    m = Serving.get().market
    hits = np.where(m.jobs["jobId"].to_numpy() == job_id)[0]
    if not len(hits):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Posting not found")
    return _row(int(hits[0]))


@router.get("/{job_id}/path")
def graph_path(job_id: str, neo4j: Neo4jDep, skill_uri: str = Query(...)) -> dict:
    """The actual Neo4j path Tag -SAME_AS-> Skill <-REQUIRES- Job -MAPS_TO-> Occupation, for 'why' panels."""
    rows = neo4j.run_query(
        """
        MATCH (s:Skill {uri: $skill})<-[:REQUIRES]-(j:Job {id: $job})
        OPTIONAL MATCH (j)-[:MAPS_TO]->(o:Occupation)
        OPTIONAL MATCH (j)-[:LOCATED_IN]->(c:City)-[:IN_STATE]->(st:State)
        OPTIONAL MATCH (j)-[:TAGGED]->(t:Tag)-[l:SAME_AS]->(s)
        RETURN s.preferredLabel AS skill, j.title AS job, o.preferredLabel AS occupation,
               o.ncoFamily AS nco, c.name AS city, st.name AS state, t.name AS tag,
               l.score AS link_score, l.method AS link_method
        LIMIT 1
        """,
        {"skill": skill_uri, "job": job_id},
    )
    if not rows:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such skill-posting edge in the graph")
    r = rows[0]
    path = []
    if r["tag"]:
        path.append({"kind": "Naukri tag", "label": r["tag"],
                     "edge": f"SAME_AS ({r['link_method']}, cosine {float(r['link_score'] or 0):.2f})"})
    path.append({"kind": "ESCO skill", "label": r["skill"], "edge": "REQUIRED BY"})
    path.append({"kind": "posting", "label": r["job"], "edge": "MAPS_TO" if r["occupation"] else None})
    if r["occupation"]:
        path.append({"kind": "ESCO occupation", "label": r["occupation"], "nco_family": r["nco"]})
    return {"path": path, "city": r["city"], "state": r["state"]}
