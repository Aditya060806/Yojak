# app/api/routes/student.py

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.api.schemas.yojak import PlanRequest, ProfileRequest, StudentMatchResponse, StudentPlanResponse
from app.api.services import yojak

router = APIRouter(prefix="/student", tags=["student"])


@router.post("/match", response_model=StudentMatchResponse)
def match(req: ProfileRequest) -> dict:
    """Roles and postings that fit a skill profile, each with a 'why' panel and a salary range."""
    if not req.skills and not (req.text or "").strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Give at least one skill or some text describing your skills.")
    return yojak.student_match(req)


@router.post("/plan", response_model=StudentPlanResponse)
def plan(req: PlanRequest) -> dict:
    """The k skills that unlock the most postings (exact or near-optimal), compared with frequency advice."""
    try:
        return yojak.student_plan(req)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
