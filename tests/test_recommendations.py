"""Recommendation repo regressions (audit bugs #4, #5, #7) and gap maths."""

from __future__ import annotations

import numpy as np
import pytest

from app.api.repos import recommendations as rec_repo
from app.api.repos.recommendations import RecommendationsRepo, compute_skill_gap, isco_code_from_uri


def test_isco_code_from_uri():
    assert isco_code_from_uri("http://data.europa.eu/esco/isco/C2511") == "2511"
    assert isco_code_from_uri("http://data.europa.eu/esco/isco/C0110") == "0110"


def test_compute_skill_gap():
    req = [{"uri": "a"}, {"uri": "b"}, {"uri": "c"}, {"uri": "d"}]
    out = compute_skill_gap(req, ["a", "c", "zzz"])
    assert [s["uri"] for s in out["matched_skills"]] == ["a", "c"]
    assert [s["uri"] for s in out["missing_skills"]] == ["b", "d"]
    assert out["match_percentage"] == pytest.approx(50.0)
    assert compute_skill_gap([], ["a"])["match_percentage"] == 0.0


@pytest.fixture
def repo(fake_neo4j, monkeypatch):
    class FakeEngine:
        def encode(self, texts):
            return np.zeros((len(texts), 4), dtype=np.float32)

        def search(self, _q, top_k=20):
            return [("o1", 0.9), ("o2", 0.4)][:top_k]

    monkeypatch.setattr(rec_repo, "ml_engine", FakeEngine())
    fake_neo4j.on(r"RETURN s.uri AS uri, s.preferredLabel", [{"uri": "s1", "label": "SQL"}])
    fake_neo4j.on(
        r"o.uri IN \$occupation_uris",
        [
            {
                "uri": "o2", "label": "B", "description": "", "isco_code": "",
                "required_skills": [{"uri": "s1", "label": "SQL", "relation_type": "optional", "skill_type": "knowledge"}],
                "groups": ["Database designers"], "schemes": [],
            },
            {
                "uri": "o1", "label": "A", "description": "d", "isco_code": "2511",
                "required_skills": [
                    {"uri": "s1", "label": "SQL", "relation_type": "essential", "skill_type": "knowledge"},
                    {"uri": "s2", "label": "R", "relation_type": "optional", "skill_type": "knowledge"},
                    None,
                ],
                "groups": ["Systems analysts", None], "schemes": [],
            },
        ],
    )
    return RecommendationsRepo(fake_neo4j)


def test_reads_correct_graph_properties(repo, fake_neo4j):
    repo.get_recommendations(["s1"], occupation_groups=["http://data.europa.eu/esco/isco/C25"], limit=5)
    cypher, params = fake_neo4j.last_query("o.uri IN $occupation_uris")
    assert "r.relation" in cypher and "r.relationType" not in cypher  # bug #4
    assert "g.label" in cypher and "g.preferredLabel" not in cypher  # bug #5
    assert "BROADER_THAN_OCC_GROUP" in cypher and "broaderTransitive" not in cypher  # bug #7
    assert params["occupation_group_codes"] == ["25"]


def test_sorted_by_similarity_with_gap(repo):
    out = repo.get_recommendations(["s1"], limit=5)
    assert [o["uri"] for o in out] == ["o1", "o2"]
    o1 = out[0]
    assert o1["similarity_score"] == 0.9
    assert o1["match_percentage"] == pytest.approx(50.0)
    assert [s["relation_type"] for s in o1["matched_skills"]] == ["essential"]
    assert o1["groups"] == ["Systems analysts"]
    assert out[1]["isco_code"] is None  # empty string normalised


def test_recommendation_endpoint(client, fake_neo4j, monkeypatch):
    import app.api.routes.recommendations as route

    monkeypatch.setattr(route.ml_engine, "is_ready", lambda: True)

    class FakeEngine:
        def encode(self, texts):
            return np.zeros((len(texts), 4), dtype=np.float32)

        def search(self, _q, top_k=20):
            return [("o1", 0.7)]

    monkeypatch.setattr(rec_repo, "ml_engine", FakeEngine())
    fake_neo4j.on(r"RETURN s.uri AS uri, s.preferredLabel", [{"uri": "s1", "label": "SQL"}])
    fake_neo4j.on(
        r"o.uri IN \$occupation_uris",
        [{"uri": "o1", "label": "A", "description": None, "isco_code": "2511",
          "required_skills": [{"uri": "s1", "label": "SQL", "relation_type": None, "skill_type": None}],
          "groups": [], "schemes": []}],
    )
    body = client.post("/recommendations", json={"skills": ["s1"], "limit": 3}).json()
    rec = body["recommendations"][0]
    assert rec["similarity_score"] == 0.7
    assert rec["matched_skills"][0]["relation_type"] == "unspecified"  # never guessed


def test_recommendation_503_when_engine_not_ready(client, monkeypatch):
    import app.api.routes.recommendations as route

    monkeypatch.setattr(route.ml_engine, "is_ready", lambda: False)
    assert client.post("/recommendations", json={"skills": ["s1"]}).status_code == 503
