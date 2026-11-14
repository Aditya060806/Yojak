"""Refresh private exchange data and readiness, never overwrite reviewed documents."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .data import write_json
from .handoff import export_bundle


def readiness(out: Path) -> dict:
    manifest = json.loads((out / "manifest.json").read_text())
    sub = out / "submission"
    build_path = sub / "note_build_manifest.json"
    build = json.loads(build_path.read_text()) if build_path.exists() else {}
    evidence = {}
    for name in ("manifest.json", "salary_report.json", "research_report.json", "verification.json",
                 "planner_benchmark.json", "calibration_audit.json", "truncation_sensitivity.json"):
        path = out / name
        if not path.exists():
            evidence[name] = {"status": "missing"}
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        recorded = build.get("evidence_hashes", {}).get(name)
        evidence[name] = {"sha256": digest, "status": "unchanged" if digest == recorded else
                          "changed_since_note_build" if recorded else "not_recorded_in_note_build"}
    docx = sub / "Yojak_Approach_Note.docx"
    docx_hash = hashlib.sha256(docx.read_bytes()).hexdigest() if docx.exists() else None
    blockers = [f"{name}: {value['status']}" for name, value in evidence.items() if value["status"] != "unchanged"]
    if not build or build.get("source_version") != manifest["source_version"]:
        blockers.append("Note build manifest is absent or from another source version")
    if not docx_hash or docx_hash != build.get("docx_sha256"):
        blockers.append("Word document is absent or differs from its recorded build")
    pdf = sub / "Yojak_Approach_Note.pdf"
    if not pdf.exists():
        blockers.append("PDF is missing")
    return {"source_version": manifest["source_version"], "status": "review_required",
            "evidence": evidence, "document_exists": docx.exists(), "pdf_exists": pdf.exists(),
            "document_sha256": docx_hash, "refresh_reasons": blockers,
            "human_gates": ["Verify rendered pagination and document content after any rebuild.",
                            "SAS execution, independent role review and salary-unit clarification remain human gates.",
                            "Confirm permission before distributing confidential reports or screenshots."],
            "note": "File existence and matching hashes do not certify scientific validity or visual review."}


def package(out: Path):
    export_bundle(out)
    sub = out / "submission"
    sub.mkdir(parents=True, exist_ok=True)
    report = readiness(out)
    write_json(sub / "submission_readiness.json", report)
    lines = ["# Private submission readiness", "", "Status: review required. Existing documents were preserved.", "",
             "## Evidence refresh reasons", ""]
    lines += [f"- {reason}" for reason in report["refresh_reasons"]] or ["- Recorded evidence hashes match; human review is still required."]
    lines += ["", "## Human gates", ""] + [f"- {gate}" for gate in report["human_gates"]]
    lines += ["", "Document authoring is explicit: run scripts/sas/build_note_v4.py with the artifact runtime,",
              "then scripts/sas/render_note_windows.py and inspect the rendered pages. Packaging never calls the legacy note generator.", ""]
    (sub / "submission_readiness.md").write_text("\n".join(lines), encoding="utf-8")
    return sub / "submission_readiness.json"
