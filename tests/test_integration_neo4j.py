"""
Integration tests against a live, disposable Neo4j (CI starts one from the tarball).

Run locally only against a throwaway database:
    NEO4J_TEST_URI=neo4j://127.0.0.1:7688 NEO4J_TEST_PASSWORD=... pytest -m neo4j

Safety: the test wipes the database, so it refuses to run unless the database is
empty or carries the :YojakTestDB marker it creates itself.
"""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote

import pytest

pytestmark = pytest.mark.neo4j

FIXTURE_ESCO = Path(__file__).parent / "fixtures" / "esco_mini"


@pytest.fixture(scope="module")
def loaded_graph():
    from app.core import settings as settings_mod
    from app.core.neo4j import Neo4jClient

    env = {
        "NEO4J_URI": os.environ["NEO4J_TEST_URI"],
        "NEO4J_USER": os.environ.get("NEO4J_TEST_USER", "neo4j"),
        "NEO4J_PASSWORD": os.environ["NEO4J_TEST_PASSWORD"],
        "ESCO_DATA_DIR": str(FIXTURE_ESCO),
    }
    old = {k: os.environ.get(k) for k in env}
    os.environ.update(env)
    settings_mod.get_settings.cache_clear()

    client = Neo4jClient(env["NEO4J_URI"], env["NEO4J_USER"], env["NEO4J_PASSWORD"])
    client.connect()
    total = client.run_query("MATCH (n) RETURN count(n) AS c")[0]["c"]
    marked = client.run_query("MATCH (m:YojakTestDB) RETURN count(m) AS c")[0]["c"]
    if total and not marked:
        pytest.exit("NEO4J_TEST_URI points at a non-empty database without the test marker; refusing to wipe it.")
    client.run_query("MATCH (n) DETACH DELETE n")
    client.run_query("CREATE (:YojakTestDB)")

    from ml_pipeline.data_ingestion import ingest_all_data
    from ml_pipeline.neo4j_etl import load_rich_esco_to_neo4j

    load_rich_esco_to_neo4j(ingest_all_data())
    yield client

    client.close()
    for k, v in old.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    settings_mod.get_settings.cache_clear()


def test_every_occupation_has_an_isco_group(loaded_graph):
    rows = loaded_graph.run_query(
        "MATCH (o:Occupation) RETURN count(o) AS total, "
        "sum(CASE WHEN (o)-[:IN_OCC_GROUP]->() THEN 1 ELSE 0 END) AS grouped"
    )
    assert rows[0]["total"] == 12
    assert rows[0]["grouped"] == rows[0]["total"]


def test_requires_uses_relation_property(loaded_graph):
    rows = loaded_graph.run_query(
        "MATCH ()-[r:REQUIRES]->() RETURN collect(DISTINCT r.relation) AS rels, count(r.relationType) AS legacy"
    )
    assert set(rows[0]["rels"]) == {"essential", "optional"}
    assert rows[0]["legacy"] == 0


def test_alt_labels_and_codes(loaded_graph):
    alt = loaded_graph.run_query(
        "MATCH (o:Occupation {preferredLabel: 'data analyst'}) RETURN o.altLabels AS alt, o.iscoCode AS code"
    )[0]
    assert isinstance(alt["alt"], list) and len(alt["alt"]) > 0
    assert alt["code"] == "2511"
    codes = loaded_graph.run_query("MATCH (g:OccupationGroup) RETURN collect(g.code) AS codes")[0]["codes"]
    assert all(isinstance(c, str) for c in codes)


def test_etl_is_idempotent(loaded_graph):
    from ml_pipeline.data_ingestion import ingest_all_data
    from ml_pipeline.neo4j_etl import load_rich_esco_to_neo4j

    before = loaded_graph.run_query("MATCH ()-[r]->() RETURN count(r) AS c")[0]["c"]
    load_rich_esco_to_neo4j(ingest_all_data())
    after = loaded_graph.run_query("MATCH ()-[r]->() RETURN count(r) AS c")[0]["c"]
    assert before == after


def test_api_against_live_graph(loaded_graph, monkeypatch):
    from fastapi.testclient import TestClient

    import app.api.main as main
    from app.core import deps

    monkeypatch.setattr(main, "init_neo4j_client", lambda: None)
    monkeypatch.setattr(main, "close_neo4j_client", lambda: None)
    main.app.dependency_overrides[deps.get_neo4j_client] = lambda: loaded_graph
    try:
        with TestClient(main.app) as c:
            occ = c.get("/catalog/occupations?q=data%20analyst").json()
            assert occ and occ[0]["label"] == "data analyst"
            gap = c.get(f"/occupations/{quote(occ[0]['uri'], safe='')}/skill-gap").json()
            assert gap["occupationLabel"] == "data analyst"
            assert gap["essentialSkills"], "data analyst should have essential skills"
            assert c.get(f"/occupations/{quote('http://x/none', safe='')}/skill-gap").status_code == 404
            groups = c.get("/catalog/occupation-groups?all=true").json()
            assert any(g["code"] == "2511" for g in groups)
    finally:
        main.app.dependency_overrides.clear()


def test_india_layer_load(loaded_graph):
    import pandas as pd

    from ml_pipeline.india.load_neo4j import load_india_layer

    occ = loaded_graph.run_query("MATCH (o:Occupation {preferredLabel: 'data analyst'}) RETURN o.uri AS uri")[0]["uri"]
    skill = loaded_graph.run_query(
        "MATCH (:Occupation {uri: $u})-[:REQUIRES]->(s:Skill) RETURN s.uri AS uri LIMIT 1", {"u": occ})[0]["uri"]
    jobs = pd.DataFrame({
        "jobId": ["j1", "j2"], "title": ["Data Analyst", "Analyst"], "title_clean": ["data analyst", "analyst"],
        "companyName": ["Acme", "acme "], "posted_date": pd.to_datetime(["2025-09-29", None]),
        "days_ago": [4.0, None], "work_mode": ["onsite", "remote"], "salary_min_inr": [300000.0, None],
        "salary_max_inr": [500000.0, None], "salary_mid_inr": [400000.0, None], "salary_disclosed": [True, False],
        "salary_flag": ["ok", "not_disclosed"], "exp_min": [1.0, 0.0], "exp_max": [3.0, 1.0], "exp_band": ["0-1", "0-1"],
        "company_rating": [3.9, None], "primary_city": ["Pune", None], "primary_state": ["Maharashtra", None],
        "primary_tier": [1.0, None], "primary_metro_region": ["Pune", None], "dup_group_id": ["g1", "g2"],
        "n_tags": [2, 1], "n_cities": [1, 0], "occupation_uri": [occ, None], "title_sim": [1.0, None],
        "skill_overlap": [0.5, None],
    })
    job_cities = pd.DataFrame({"jobId": ["j1"], "rank": [0], "city": ["Pune"], "state": ["Maharashtra"],
                               "population": [3124458], "lat": [18.5], "lon": [73.8], "matched_by": ["exact"],
                               "tier": [1], "metro_region": ["Pune"]})
    job_tags = pd.DataFrame({"jobId": ["j1", "j1", "j2"], "tag": ["sql", "excelx", "sql"],
                             "skill_uri": [skill, None, skill]})
    tag_links = pd.DataFrame({"tag": ["sql", "excelx"], "freq": [2, 1], "uri": [skill, None],
                              "score": [1.0, 0.3], "method": ["exact", "embedding"], "accepted": [True, False]})
    nco = pd.DataFrame({"uri": [occ], "nco_family": ["2511"]})

    counts = load_india_layer(loaded_graph, jobs, job_cities, job_tags, tag_links, nco, log=lambda _m: None)
    assert counts["jobs"] == 2 and counts["companies"] == 1  # "Acme" / "acme " share a key
    assert counts["job_requires_skill"] == 2 and counts["job_maps_to_occupation"] == 1
    assert counts["tags"] == 2 and counts["job_tagged"] == 3
    row = loaded_graph.run_query(
        "MATCH (j:Job {id:'j1'})-[:LOCATED_IN]->(c:City)-[:IN_STATE]->(s:State) "
        "RETURN c.tier AS tier, s.name AS state, j.postedDate AS d")[0]
    assert row["tier"] == 1 and row["state"] == "Maharashtra" and str(row["d"]) == "2025-09-29"
    assert loaded_graph.run_query("MATCH (o:Occupation {uri:$u}) RETURN o.ncoFamily AS f", {"u": occ})[0]["f"] == "2511"
    # refresh semantics: loading again replaces, never duplicates
    counts2 = load_india_layer(loaded_graph, jobs, job_cities, job_tags, tag_links, nco, log=lambda _m: None)
    assert counts2 == counts
