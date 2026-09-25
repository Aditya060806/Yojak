# app/api/routes/institution.py

from __future__ import annotations

import json

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.api.schemas.yojak import InstitutionResponse
from app.api.services import yojak
from app.core.extract import read_upload

router = APIRouter(prefix="/institution", tags=["institution"])


@router.post("/coverage", response_model=InstitutionResponse)
async def coverage(
    syllabus_text: str = Form("", max_length=100_000),
    syllabus: UploadFile | None = File(None),
    skills: str = Form("[]"),
    occupations: str = Form("[]", description="JSON list of ESCO occupation URIs"),
    isco2: str | None = Form(None),
    field: str | None = Form(None, description="ISCED-F broad field"),
    tiers: str = Form("[]"),
    states: str = Form("[]"),
    top_n: int = Form(40, ge=10, le=100),
) -> dict:
    """How well a syllabus covers what in-scope Indian postings ask for, with the gaps."""
    text = syllabus_text
    if syllabus is not None:
        try:
            text = (text + "\n" + read_upload(syllabus.filename or "", await syllabus.read())).strip()
        except ValueError as e:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    try:
        return yojak.institution_coverage(text, json.loads(skills), json.loads(occupations), isco2 or None,
                                          field or None, json.loads(tiers) or None, json.loads(states) or None, top_n)
    except (ValueError, json.JSONDecodeError) as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
