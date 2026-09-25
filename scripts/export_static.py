"""
Export JSON snapshots for the hosted demo (Vercel has no Python API).

    python scripts/export_static.py        ->  app/frontend/public/data/

Writes, all derived from the pipeline artifacts and reports (nothing typed by hand):
  reports/<name>.json, reports/evaluation.json, reports/index.json   the evidence
  constellation.json                                                   /graph/constellation
  workforce/fields.json, demand-<field>.json, shortage-<field>.json    /workforce/*
  skills.json                                                          ESCO skills seen in postings (search)
  examples/*.json                                                      precomputed runs of the demo personas
                                                                       (scripts/personas.yaml) and one JD

Run it after `python -m ml_pipeline.evaluate_all` so the snapshot matches the reports.
Postings are aggregated; example results show a few posting titles and companies from the
Naukri dataset (CC BY-NC-SA 4.0), attributed in the site footer.
"""

import json
import math
import re
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import yaml  # noqa: E402

OUT = ROOT / "app" / "frontend" / "public" / "data"
REPORTS = ("data_quality", "model_comparison", "upskilling_eval", "salary_eval", "workforce_summary",
           "multilingual_eval", "impact")
MARKDOWN = {"evaluation": "EVALUATION.md", "phase0_audit": "phase0_audit.md"}
EXAMPLE_JD = {
    "id": "data-analyst-jd",
    "name": "Data analyst, Tier-2 city",
    "story": "A recruiter hiring a junior data analyst ranks the synthetic demo pool against the job's skills.",
    "text": "Junior data analyst. Must know SQL, Microsoft Excel and statistics. Python and data visualisation "
            "preferred. Good communication skills for presenting reports to business teams.",
}


def slug(s: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") if s else "all"


def clean(obj):
    """JSON-safe: numpy scalars to Python, NaN/inf to null."""
    if isinstance(obj, dict):
        return {str(k): clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean(v) for v in obj]
    if isinstance(obj, np.generic):
        obj = obj.item()
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    return obj


def write(rel: str, obj) -> None:
    path = OUT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean(obj), ensure_ascii=False, separators=(",", ":"), allow_nan=False), encoding="utf-8")
    print(f"  {rel:<42} {path.stat().st_size / 1024:8.1f} KB")


def export_reports() -> None:
    rep = ROOT / "reports"
    index = {"json": [], "markdown": []}
    for name in REPORTS:
        p = rep / f"{name}.json"
        index["json"].append({"name": name, "available": p.exists()})
        if p.exists():
            write(f"reports/{name}.json", json.loads(p.read_text(encoding="utf-8")))
    for name, file in MARKDOWN.items():
        p = rep / file
        index["markdown"].append({"name": name, "available": p.exists()})
        if p.exists():
            write(f"reports/{name}.json", {"name": name, "markdown": p.read_text(encoding="utf-8")})
    write("reports/index.json", index)


def export_live_views() -> None:
    from app.api.routes import graph, workforce
    from app.core.serving import Serving

    write("constellation.json", graph._constellation(140, 30, 360))
    fields = workforce.fields()
    write("workforce/fields.json", fields)
    for f in [None] + [x["field"] for x in fields["fields"] if x["field"] != "unassigned"]:
        write(f"workforce/demand-{slug(f)}.json", workforce.demand(field=f, tier=None))
        write(f"workforce/shortage-{slug(f)}.json", workforce.shortage(field=f))
    srv = Serving.get()
    skills = sorted(({"uri": u, "label": srv.skill_labels.get(u, u)} for u in srv.market.skills),
                    key=lambda s: s["label"].lower())
    write("skills.json", skills)


def export_examples() -> None:
    from app.api.schemas.yojak import PlanRequest, ProfileRequest
    from app.api.services import yojak as svc

    personas = yaml.safe_load((ROOT / "scripts" / "personas.yaml").read_text(encoding="utf-8"))
    index = {"generated_at": time.strftime("%Y-%m-%d"), "student": [], "recruiter": [], "institution": []}
    for p in personas:
        entry = {"id": p["id"], "name": p["name"], "story": p["story"].strip(), "file": f"{p['view']}-{p['id']}.json"}
        persona = {k: p[k] for k in ("id", "name", "story", "request")}
        if p["view"] == "student":
            match = svc.student_match(ProfileRequest(**p["request"]))
            plan = svc.student_plan(PlanRequest(**{**p["request"], **p.get("plan", {})}))
            write(f"examples/{entry['file']}", {"persona": persona, "match": match, "plan": plan})
        else:
            r = p["request"]
            res = svc.institution_coverage(r["text"], [], [], r.get("isco2"), None, r.get("tiers"), r.get("states"))
            write(f"examples/{entry['file']}", {"persona": {**persona, "note": p.get("syllabus_note", "").strip()}, "result": res})
        index[p["view"]].append(entry)
    rec = svc.recruiter_rank(EXAMPLE_JD["text"], [], [], 25, True)
    file = f"recruiter-{EXAMPLE_JD['id']}.json"
    write(f"examples/{file}", {"persona": EXAMPLE_JD, "result": rec})
    index["recruiter"].append({"id": EXAMPLE_JD["id"], "name": EXAMPLE_JD["name"], "story": EXAMPLE_JD["story"], "file": file})
    write("examples/index.json", index)


def main() -> int:
    if OUT.exists():
        shutil.rmtree(OUT)
    t0 = time.time()
    for label, step in (("reports", export_reports), ("live views", export_live_views), ("examples", export_examples)):
        print(label)
        step()
    total = sum(p.stat().st_size for p in OUT.rglob("*.json")) / 2**20
    print(f"wrote {OUT.relative_to(ROOT)} ({total:.1f} MB) in {time.time() - t0:.0f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
