"""Disabled by default: private, local SAS source endpoints."""
from __future__ import annotations

import os
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

router = APIRouter(prefix="/sas", tags=["Private SAS career ladder"])


class Profile(BaseModel):
    role_family: str = Field(default="Data analyst", min_length=1, max_length=80)
    experience: float = Field(default=2, ge=0, le=40, allow_inf_nan=False)
    skills: list[str] = Field(default_factory=list, max_length=100)
    complete_only: bool = False


@lru_cache(maxsize=1)
def _load():
    from ml_pipeline.sas.service import SasService
    return SasService()


def service():
    if os.environ.get("YOJAK_SAS_LOCAL") != "1":
        raise HTTPException(503, "Private SAS workspace is disabled. Run locally with YOJAK_SAS_LOCAL=1.")
    try:
        return _load()
    except FileNotFoundError:
        raise HTTPException(503, "SAS artifacts are unavailable. Run the private pipeline first.") from None
    except ValueError:
        raise HTTPException(503, "SAS artifacts are stale or incompatible. Rebuild the private pipeline.") from None


def invoke(svc, name, profile):
    if any(len(s) > 120 for s in profile.skills):
        raise HTTPException(422, "Skill names must be at most 120 characters")
    try:
        return getattr(svc, name)(profile.role_family, profile.experience, profile.skills, profile.complete_only)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None


@router.post("/match")
def match(profile: Profile, svc=Depends(service)):
    return invoke(svc, "match", profile)


@router.post("/plan")
def plan(profile: Profile, svc=Depends(service)):
    return invoke(svc, "plan", profile)


@router.post("/pay-range")
def pay_range(profile: Profile, svc=Depends(service)):
    return invoke(svc, "pay", profile)


@router.get("/performance")
def performance(response: Response):
    response.headers["Cache-Control"] = "no-store"
    if os.environ.get("YOJAK_SAS_LOCAL") != "1":
        raise HTTPException(503, "Private SAS workspace is disabled. Performance evidence is local-only.")
    from ml_pipeline.sas.performance import performance_report
    try:
        return performance_report()
    except (FileNotFoundError, ValueError, KeyError):
        raise HTTPException(503, "Evaluation artifacts are missing or incompatible. Rebuild the private evaluation reports.") from None
