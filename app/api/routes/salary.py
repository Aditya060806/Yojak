# app/api/routes/salary.py

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.schemas.yojak import SalaryEstimateResponse
from app.api.services import yojak

router = APIRouter(prefix="/salary", tags=["salary"])


@router.get("/estimate", response_model=SalaryEstimateResponse)
def estimate(
    occupation_uri: str | None = None,
    isco_code: str | None = None,
    state: str | None = None,
    tier: int | None = Query(None, ge=1, le=3),
    exp_min: float | None = Query(None, ge=0, le=40),
    skills: list[str] = Query(default_factory=list),
) -> dict:
    """Always a P10-P50-P90 range with its support; never a single number."""
    return yojak.salary_estimate(occupation_uri, isco_code, state, tier, exp_min, skills)
