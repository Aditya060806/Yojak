# app/api/routes/extract.py

from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.api.schemas.yojak import ExtractRequest, ExtractResponse
from app.api.services import yojak
from app.core.extract import read_upload

router = APIRouter(prefix="/extract", tags=["extraction"])


@router.post("/skills", response_model=ExtractResponse)
def extract_skills(body: ExtractRequest) -> dict:
    """Free text (English, Hindi, Punjabi or romanised Hindi) -> linked ESCO skills with the span each came from."""
    return yojak.extract(body.text, body.language)


@router.post("/file", response_model=ExtractResponse)
async def extract_file(file: UploadFile = File(...), language: str | None = Form(None)) -> dict:
    """A resume, job description or syllabus (PDF, DOCX or text, <= 5 MB). Processed in memory, never stored."""
    try:
        text = read_upload(file.filename or "", await file.read())
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    if not text.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No readable text in the file (scanned PDFs need OCR).")
    return yojak.extract(text, language)
