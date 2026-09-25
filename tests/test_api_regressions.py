"""
API regression tests for the bugs found in the Phase 0 audit
(reports/phase0_audit.md). All run against FakeNeo4j.
"""

from __future__ import annotations

from urllib.parse import quote

import pytest

OCC = "http://data.europa.eu/esco/occupation/d3edb8f8"
ADMIN = {"X-Admin-Token": "test-admin-token"}


# --- health / diagnostics (audit bug #9) ---------------------------------------

def test_health_reports_live_neo4j(client, fake_neo4j):
    fake_neo4j.on(r"RETURN 1 AS ok", [{"ok": 1}])
    body = client.get("/health").json()
    assert body["app"] == "Yojak"
    assert body["neo4j"]["connected"] is True
    assert "password" not in str(body["neo4j"]).replace("password_configured", "")


def test_diagnostics_endpoints_lists_real_routes(client):
    r = client.get("/admin/diagnostics/endpoints")
    assert r.status_code == 200
    paths = {(e["method"], e["path"]) for e in r.json()["endpoints"]}
    assert ("POST", "/recommendations") in paths
    assert ("GET", "/admin/diagnostics/metrics") in paths


def test_diagnostics_metrics_records_route_templates(client, fake_neo4j):
    fake_neo4j.on(r"MATCH \(o:Occupation \{uri: \$uri\}\)", [])
    client.get(f"/occupations/{quote(OCC, safe='')}/skill-gap")
    metrics = client.get("/admin/diagnostics/metrics").json()["metrics"]
    keys = {m["endpoint"] for m in metrics}
    assert "GET /occupations/{occupationUri:path}/skill-gap" in keys
    assert not any(OCC in k for k in keys)  # aggregated by template, not raw URI


# --- skill gap (audit bug #8) --------------------------------------------------

def test_skill_gap_unknown_occupation_is_404(client, fake_neo4j):
    fake_neo4j.on(r"MATCH \(o:Occupation \{uri: \$uri\}\)", [])
    r = client.get(f"/occupations/{quote('http://x/nope', safe='')}/skill-gap")
    assert r.status_code == 404


def test_skill_gap_keeps_label_when_filters_remove_all_skills(client, fake_neo4j):
    fake_neo4j.on(
        r"MATCH \(o:Occupation \{uri: \$uri\}\)",
        [{"uri": OCC, "label": "data analyst", "description": "", "iscoCode": "2511"}],
    )
    fake_neo4j.on(r"REQUIRES", [])  # filters removed everything
    body = client.get(f"/occupations/{quote(OCC, safe='')}/skill-gap?schemes=http://nope").json()
    assert body["occupationLabel"] == "data analyst"
    assert body["iscoCode"] == "2511"
    assert body["essentialSkills"] == [] and body["optionalSkills"] == []


def test_skill_gap_splits_essential_and_optional(client, fake_neo4j):
    fake_neo4j.on(
        r"MATCH \(o:Occupation \{uri: \$uri\}\)",
        [{"uri": OCC, "label": "data analyst", "description": "", "iscoCode": "2511"}],
    )
    fake_neo4j.on(
        r"REQUIRES",
        [
            {
                "occupationUri": OCC,
                "occupationLabel": "data analyst",
                "iscoCode": "2511",
                "requiredSkills": [
                    {"skillUri": "s1", "skillLabel": "SQL", "skillType": "knowledge", "relationType": "essential"},
                    {"skillUri": "s2", "skillLabel": "R", "skillType": "knowledge", "relationType": "optional"},
                    {"skillUri": None},
                ],
            }
        ],
    )
    body = client.get(f"/occupations/{quote(OCC, safe='')}/skill-gap").json()
    assert [s["label"] for s in body["essentialSkills"]] == ["SQL"]
    assert [s["label"] for s in body["optionalSkills"]] == ["R"]


# --- notes (audit bug #11) + admin guard ----------------------------------------

def _note_row(**over):
    row = {
        "occupationUri": OCC,
        "occupationLabel": "data analyst",
        "noteId": "n1",
        "text": "hello",
        "createdAt": "2026-09-25T10:00:00Z",
        "updatedAt": "2026-09-25T10:00:00Z",
    }
    row.update(over)
    return row


def test_note_upsert_requires_admin_token(client):
    r = client.put(f"/notes/admin/occupations/{quote(OCC, safe='')}/notes/n1", json={"text": "hi"})
    assert r.status_code == 401


def test_note_upsert_returns_label_and_timestamps(client, fake_neo4j):
    fake_neo4j.on(r"MERGE \(n:Note", [_note_row()])
    r = client.put(
        f"/notes/admin/occupations/{quote(OCC, safe='')}/notes/n1", json={"text": "hello"}, headers=ADMIN
    )
    assert r.status_code == 200
    body = r.json()
    assert body["occupationLabel"] == "data analyst"
    assert body["updatedAt"] is not None
    cypher, _ = fake_neo4j.last_query("MERGE (n:Note")
    assert "DELETE old" in cypher  # moving a note never leaves a second link


def test_notes_search_coalesces_updated_at(client, fake_neo4j):
    fake_neo4j.on(r"HAS_NOTE", [{"total": 1, "notes": [_note_row()]}])
    client.get("/notes")
    cypher, _ = fake_neo4j.last_query("HAS_NOTE")
    assert "coalesce(n.updatedAt, n.createdAt)" in cypher


def test_note_delete_success_and_404(client, fake_neo4j):
    url = f"/notes/admin/occupations/{quote(OCC, safe='')}/notes/n1"
    fake_neo4j.on(r"DELETE hn", [{"deleted": 1}])
    assert client.delete(url, headers=ADMIN).status_code == 200


def test_note_delete_missing_is_404(client):
    url = f"/notes/admin/occupations/{quote(OCC, safe='')}/notes/nope"
    assert client.delete(url, headers=ADMIN).status_code == 404


def test_note_blank_text_rejected(client):
    url = f"/notes/admin/occupations/{quote(OCC, safe='')}/notes/n1"
    assert client.put(url, json={"text": "   "}, headers=ADMIN).status_code == 400


# --- catalog ---------------------------------------------------------------------

def test_occupation_groups_all_ignores_limit(client, fake_neo4j):
    fake_neo4j.on(r"OccupationGroup", [])
    client.get("/catalog/occupation-groups?all=true")
    _, params = fake_neo4j.last_query("OccupationGroup")
    assert params["limit"] >= 1000


def test_concept_schemes_only_with_members(client, fake_neo4j):
    fake_neo4j.on(r"ConceptScheme", [{"uri": "u", "label": "Digital", "members": 12}])
    body = client.get("/catalog/concept-schemes").json()
    assert body == [{"uri": "u", "label": "Digital", "members": 12}]
    cypher, _ = fake_neo4j.last_query("ConceptScheme")
    assert "members > 0" in cypher


# --- errors don't leak internals ---------------------------------------------------

def test_unhandled_errors_are_generic(client, fake_neo4j, monkeypatch):
    def boom(*_a, **_k):
        raise RuntimeError("secret connection string bolt://user:pw@host")

    monkeypatch.setattr(fake_neo4j, "run_query", boom)
    with pytest.raises(RuntimeError):
        # TestClient re-raises server exceptions by default; check the handler directly.
        client.get("/catalog/skills?q=x")


def test_unhandled_errors_body(fake_neo4j, monkeypatch):
    from fastapi.testclient import TestClient

    import app.api.main as main
    from app.core import deps

    def boom(*_a, **_k):
        raise RuntimeError("secret bolt://user:pw@host")

    monkeypatch.setattr(main, "init_neo4j_client", lambda: None)
    monkeypatch.setattr(main, "close_neo4j_client", lambda: None)
    monkeypatch.setattr(fake_neo4j, "run_query", boom)
    main.app.dependency_overrides[deps.get_neo4j_client] = lambda: fake_neo4j
    try:
        with TestClient(main.app, raise_server_exceptions=False) as c:
            r = c.get("/catalog/skills?q=x")
    finally:
        main.app.dependency_overrides.clear()
    assert r.status_code == 500
    assert "secret" not in r.text
