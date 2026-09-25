# app/api/routes/workforce.py

from __future__ import annotations

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, Query, status

from app.core.serving import Serving

router = APIRouter(prefix="/workforce", tags=["workforce"])

SHORTAGE_FORMULA = ("[postings(field, state) / postings(field, India)] / [graduates(state) / graduates(India)]; "
                    "graduates = AISHE 2021-22 out-turn; youth unemployment = PLFS 2023-24 (age 15-29)")
CAVEATS = [
    "Graduate supply is a state total, not split by field (AISHE's discipline table is not machine-readable).",
    "Graduates migrate; the index shows where demand sits relative to where graduates are produced.",
    "Demand is Naukri's formal-sector sample of postings, about two weeks around 2025-10-03.",
    "West Bengal's AISHE figure is unreadable in the source PDF, so it has no index.",
]


def _table(name: str) -> pd.DataFrame:
    try:
        return Serving.get().workforce_table(name)
    except FileNotFoundError as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(e))


def _clean(df: pd.DataFrame) -> list[dict]:
    return df.astype(object).where(pd.notna(df), None).to_dict(orient="records")


@router.get("/fields")
def fields() -> dict:
    sf = _table("state_field")
    tot = sf.groupby("field")["postings"].sum().sort_values(ascending=False)
    return {"fields": [{"field": f, "postings": int(n)} for f, n in tot.items()],
            "note": "Skill families are ISCED-F 2013 broad fields of education, via the ESCO knowledge pillar."}


@router.get("/demand")
def demand(field: str | None = None, tier: int | None = Query(None, ge=1, le=3)) -> dict:
    """Posting demand by state (optionally for one skill family), tier summary and top skills."""
    state = _table("state")
    sf = _table("state_field")
    by_state = sf[sf["field"] == field][["state", "postings"]] if field else state[["state", "postings"]]
    total = int(by_state["postings"].sum())
    by_state = by_state.assign(share=by_state["postings"] / max(total, 1)).sort_values("postings", ascending=False)
    top_state = _table("top_skills_state")
    top_tier = _table("top_skills_tier")
    if tier:
        top_tier = top_tier[top_tier["tier"] == tier]
    cols = {"skill_uris": "uri"}
    return {
        "field": field, "total_postings": total, "by_state": _clean(by_state), "tiers": _clean(_table("tier")),
        "top_skills_by_state": {s: _clean(g[["skill_uris", "label", "postings"]].rename(columns=cols))
                                for s, g in top_state.groupby("state")},
        "top_skills_by_tier": {int(t): _clean(g[["skill_uris", "label", "postings"]].rename(columns=cols))
                               for t, g in top_tier.groupby("tier")},
        "source": CAVEATS[2],
    }


@router.get("/shortage")
def shortage(field: str | None = None) -> dict:
    """Coarse shortage indicator per state (and per skill family). A proxy: read the caveats."""
    state = _table("state")
    if field:
        sf = _table("state_field")
        rows = sf[sf["field"] == field].merge(state[["state", "youth_ur_pct", "outturn_total"]], on="state", how="left")
        rows = rows[["state", "postings", "demand_share_of_field", "graduate_share", "shortage_index",
                     "youth_ur_pct", "outturn_total"]]
    else:
        rows = state[["state", "postings", "demand_share", "graduate_share", "shortage_index", "youth_ur_pct",
                      "outturn_total", "postings_per_1000_graduates", "salary_p50_median"]]
    # inf (a state with no graduate count) is not valid JSON: null it before sorting so it lands last.
    rows = rows.replace([np.inf, -np.inf], np.nan)
    rows = rows.sort_values("shortage_index", ascending=False, na_position="last")
    return {"field": field, "formula": SHORTAGE_FORMULA, "proxy": True, "states": _clean(rows), "caveats": CAVEATS}
