# app/api/routes/labelling.py

"""
Gold-label collection for evaluating ESCO linking (team-labelled, model-assisted).

Tasks
  skills        200 sampled Naukri tags  -> the correct ESCO skill, NONE or NOT_A_SKILL
  titles        200 sampled jobs         -> the correct ESCO occupation or NONE
  multilingual  60 common ESCO skills    -> Hindi, Punjabi and romanised-Hindi phrases

Samples are frozen CSVs in data/gold/ (ml_pipeline.india.gold sample); labels are
appended to CSVs next to them. Reads are open; writes need the admin token.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import json
import threading
from pathlib import Path
from typing import Literal

import pandas as pd
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.core.deps import AdminDep
from app.core.settings import get_settings

router = APIRouter(prefix="/admin/labelling", tags=["labelling"])
_lock = threading.Lock()

Task = Literal["skills", "titles", "multilingual"]
LANGUAGES = {"hi": "Hindi (Devanagari)", "pa": "Punjabi (Gurmukhi)", "hi-Latn": "Hindi (romanised)"}

FILES = {
    "skills": ("skill_link_sample.csv", "skill_link_labels.csv", "tag"),
    "titles": ("title_link_sample.csv", "title_link_labels.csv", "jobId"),
    "multilingual": ("multilingual_seed.csv", "multilingual_phrases.csv", "skill_uri"),
}


def _gold() -> Path:
    return get_settings().gold_data_dir


def _read(path: Path) -> pd.DataFrame | None:
    """Read a gold CSV, skipping leading '#' header lines (not '#' inside values, e.g. 'c#')."""
    if not path.exists():
        return None
    lines = path.read_text(encoding="utf-8").splitlines()
    start = next((i for i, line in enumerate(lines) if not line.startswith("#")), len(lines))
    body = "\n".join(lines[start:])
    return pd.read_csv(io.StringIO(body), dtype=str, keep_default_na=False)


class LabelIn(BaseModel):
    key: str = Field(..., description="tag (skills), jobId (titles) or ESCO skill URI (multilingual)")
    gold_uri: str | None = Field(None, description="ESCO URI, NONE or NOT_A_SKILL (skills/titles)")
    language: str | None = Field(None, description="hi | pa | hi-Latn (multilingual)")
    phrase: str | None = Field(None, max_length=200, description="Native phrase (multilingual)")
    labeller: str = Field(..., min_length=1, max_length=60)


@router.get("/{task}/items")
def get_items(task: Task) -> dict:
    sample_name, labels_name, key = FILES[task]
    sample = _read(_gold() / sample_name)
    if sample is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No sample yet for {task}. Run the India pipeline and "
                            "`python -m ml_pipeline.india.gold sample`.")
    labels = _read(_gold() / labels_name)
    items = sample.to_dict("records")
    if task == "multilingual":
        done: dict[str, dict[str, str]] = {}
        if labels is not None:
            for r in labels.itertuples(index=False):
                done.setdefault(r.skill_uri, {})[r.language] = r.phrase
        for it in items:
            it["phrases"] = done.get(it["skill_uri"], {})
        n_done = sum(len(v) for v in done.values())
        total = len(items) * len(LANGUAGES)
    else:
        latest = {} if labels is None else labels.drop_duplicates(key, keep="last").set_index(key).to_dict("index")
        for it in items:
            it["candidates"] = json.loads(it["candidates"]) if it.get("candidates") else []
            it["label"] = latest.get(it[key])
        n_done = sum(1 for it in items if it["label"])
        total = len(items)
    return {"task": task, "key": key, "items": items, "done": n_done, "total": total,
            "languages": LANGUAGES if task == "multilingual" else None}


@router.post("/{task}/labels", status_code=status.HTTP_201_CREATED)
def add_label(task: Task, body: LabelIn, _admin: AdminDep = None) -> dict:
    sample_name, labels_name, key = FILES[task]
    sample = _read(_gold() / sample_name)
    if sample is None or body.key not in set(sample[key]):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{body.key!r} is not in the {task} sample")
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    if task == "multilingual":
        if body.language not in LANGUAGES or not (body.phrase or "").strip():
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "language (hi | pa | hi-Latn) and phrase are required")
        row = {"skill_uri": body.key, "language": body.language, "phrase": body.phrase.strip(),
               "labeller": body.labeller.strip(), "labelled_at": now}
    else:
        if not body.gold_uri:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "gold_uri is required")
        row = {key: body.key, "gold_uri": body.gold_uri.strip(), "labeller": body.labeller.strip(), "labelled_at": now}
    path = _gold() / labels_name
    with _lock:
        new = not path.exists()
        with open(path, "a", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(row))
            if new:
                w.writeheader()
            w.writerow(row)
    return {"saved": row}


@router.get("/progress")
def progress() -> dict:
    out = {}
    for task in FILES:
        try:
            r = get_items(task)  # type: ignore[arg-type]
            out[task] = {"done": r["done"], "total": r["total"]}
        except HTTPException:
            out[task] = {"done": 0, "total": 0, "status": "no sample"}
    return out
