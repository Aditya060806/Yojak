# app/api/routes/reports.py

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, status

from app.core.settings import get_settings

router = APIRouter(prefix="/reports", tags=["evidence"])

JSON_REPORTS = ["data_quality", "model_comparison", "upskilling_eval", "salary_eval", "workforce_summary",
                "multilingual_eval", "impact"]
MARKDOWN_REPORTS = {"evaluation": "EVALUATION.md", "phase0_audit": "phase0_audit.md"}


@router.get("")
def list_reports() -> dict:
    d = get_settings().reports_dir
    return {"json": [{"name": n, "available": (d / f"{n}.json").exists()} for n in JSON_REPORTS],
            "markdown": [{"name": n, "available": (d / f).exists()} for n, f in MARKDOWN_REPORTS.items()]}


@router.get("/{name}")
def get_report(name: str) -> dict:
    """A generated report from reports/ (allowlisted names only). Every metric in the UI comes from here."""
    d = get_settings().reports_dir
    if name in JSON_REPORTS:
        path = d / f"{name}.json"
    elif name in MARKDOWN_REPORTS:
        path = d / MARKDOWN_REPORTS[name]
    else:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown report")
    if not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{name} has not been generated yet")
    text = path.read_text(encoding="utf-8")
    return json.loads(text) if path.suffix == ".json" else {"name": name, "markdown": text}
