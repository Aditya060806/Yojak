# app/api/routes/recruiter.py

from __future__ import annotations

import json

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.api.schemas.yojak import RecruiterResponse
from app.api.services import yojak

router = APIRouter(prefix="/recruiter", tags=["recruiter"])
MAX_RESUMES = 20


@router.post("/rank", response_model=RecruiterResponse)
async def rank(
    jd_text: str = Form("", max_length=50_000),
    jd_skills: str = Form("[]", description="JSON list of ESCO skill URIs (edited by the recruiter)"),
    limit: int = Form(25, ge=1, le=100),
    include_synthetic: bool = Form(True),
    resumes: list[UploadFile] | None = File(None),
) -> dict:
    """Rank candidates for a job description. SYNTHETIC demo candidates are labelled; uploads are not stored."""
    try:
        skills = json.loads(jd_skills or "[]")
    except json.JSONDecodeError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "jd_skills must be a JSON list")
    files = [(f.filename or "resume", await f.read()) for f in (resumes or [])][:MAX_RESUMES]
    try:
        return yojak.recruiter_rank(jd_text, skills, files, limit, include_synthetic)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
