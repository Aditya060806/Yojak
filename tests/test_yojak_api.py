"""
Stakeholder API routes (student, recruiter, institution, salary, workforce, jobs, graph,
extract, reports) against a tiny in-memory market. The real service code runs; only
the loaded artifacts (market, salary model, extractor, workforce tables) are replaced.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest
import scipy.sparse as sp

SKILLS = ["u:python", "u:sql", "u:excel", "u:java", "u:tally", "u:comm", "u:stats"]
LABELS = {"u:python": "Python", "u:sql": "SQL", "u:excel": "use spreadsheets software", "u:java": "Java",
          "u:tally": "accounting software", "u:comm": "communication", "u:stats": "statistics"}
WORDS = {"python": "u:python", "sql": "u:sql", "excel": "u:excel", "java": "u:java", "tally": "u:tally",
         "communication": "u:comm", "statistics": "u:stats"}


def _market():
    from ml_pipeline.upskilling.engine import idf_weights
    from ml_pipeline.upskilling.market import Market

    rng = np.random.default_rng(0)
    rows, jobs = [], []
    templates = [
        ("Python Developer", "o:dev", "software developer", "2512", ["u:python", "u:sql", "u:java"]),
        ("Data Analyst", "o:ana", "data analyst", "2511", ["u:python", "u:sql", "u:excel", "u:stats"]),
        ("Accountant", "o:acc", "accountant", "2411", ["u:excel", "u:tally", "u:comm"]),
    ]
    states = [("Karnataka", "Bengaluru", 1), ("Uttar Pradesh", "Lucknow", 2), ("Uttar Pradesh", "Gorakhpur", 3)]
    for i in range(90):
        title, occ, occ_label, isco, skills = templates[i % 3]
        chosen = [s for s in skills if rng.random() < 0.85] or skills[:1]
        state, city, tier = states[(i // 3) % 3]
        jobs.append({"jobId": f"J{i:03d}", "title": title, "companyName": f"Co{i % 7}", "dup_group_id": f"g{i}",
                     "occupation_uri": occ, "occupation_label": occ_label, "isco_code": isco, "primary_city": city,
                     "primary_state": state, "primary_tier": float(tier), "primary_metro_region": None,
                     "exp_band": ["0-1", "1-3", "3-6"][i % 3], "exp_min": float(i % 5), "work_mode": "onsite",
                     "salary_disclosed": bool(i % 2), "salary_min_inr": 300000.0, "salary_max_inr": 500000.0,
                     "skill_uris": chosen, "nco_family": isco, "posted_date": pd.Timestamp("2025-10-01")})
        rows.append([SKILLS.index(s) for s in chosen])
    r = np.repeat(np.arange(len(rows)), [len(x) for x in rows])
    c = np.concatenate(rows)
    R = sp.csr_matrix((np.ones(len(c), dtype=np.int64), (r, c)), shape=(len(rows), len(SKILLS)))
    n = len(rows)
    return Market(jobs=pd.DataFrame(jobs), skills=SKILLS, skill_index={u: i for i, u in enumerate(SKILLS)}, R=R,
                  w=idf_weights(R), p10=np.full(n, 250000.0), p50=np.full(n, 400000.0), p90=np.full(n, 650000.0),
                  salary_n_support=np.full(n, 25))


class FakeExtractor:
    def extract(self, text, language=None, use_embeddings=True):
        found = []
        for w in dict.fromkeys(t.strip(".,;:").lower() for t in text.split()):
            if w in WORDS:
                found.append({"uri": WORDS[w], "label": LABELS[WORDS[w]], "score": 1.0, "method": "exact",
                              "source_text": w})
        return {"language": language or "en", "skills": found, "unlinked_phrases": [], "threshold": 0.7,
                "threshold_status": "provisional"}


class FakeEffort:
    def costs(self, have):
        return np.ones(len(SKILLS))

    def explain(self, s, have):
        return {"effort": 1.0, "basis": "test"}


class FakeSalaryModel:
    support = {"2512|1": 15, "2512|2": 10}

    @staticmethod
    def support_key(isco_code, tier):
        from ml_pipeline.salary.model import SalaryModel

        return SalaryModel.support_key(isco_code, tier)

    def predict(self, df):
        return pd.DataFrame({"p10": [250000.0] * len(df), "p50": [400000.0] * len(df), "p90": [650000.0] * len(df),
                             "n_support": [42] * len(df), "sufficient": [True] * len(df)})


class FakeServing:
    def __init__(self):
        from app.core.serving import JobRanker

        self.market = _market()
        self.ranker = JobRanker(self.market.R, "b1")
        self.model_choice = {"benchmark_winner": "b1", "served": "b1", "served_name": "B1 TF-IDF kNN", "note": None}
        self.salary_caveat = {"what": "posted salary", "note": "test"}
        self.salary = FakeSalaryModel()
        self.skill_labels = LABELS
        self.occupation_profiles = {"o:dev": {"u:python": "essential", "u:java": "optional"}}
        self.effort = FakeEffort()
        self.candidates = pd.DataFrame([
            {"candidate_id": "SC-0001", "occupation_label": "software developer", "city": "Pune", "tier": 1.0,
             "exp_band": "1-3", "skill_uris": ["u:python", "u:sql", "u:java"]},
            {"candidate_id": "SC-0002", "occupation_label": "accountant", "city": "Kanpur", "tier": 2.0,
             "exp_band": "0-1", "skill_uris": ["u:excel", "u:tally"]},
        ])
        self.job_field = {j: ("icts" if j.endswith(("0", "3", "6", "9")) else "business")
                          for j in self.market.jobs["jobId"]}
        states = ["Karnataka", "Uttar Pradesh"]
        self._tables = {
            "state": pd.DataFrame({"state": states, "postings": [30, 60], "demand_share": [0.33, 0.67],
                                   "graduate_share": [0.4, 0.6], "shortage_index": [0.83, np.inf],
                                   "youth_ur_pct": [8.1, None], "outturn_total": [100, 150],
                                   "postings_per_1000_graduates": [300.0, 400.0], "salary_p50_median": [5e5, 4e5]}),
            "state_field": pd.DataFrame({"state": states * 2, "field": ["icts", "icts", "business", "business"],
                                         "postings": [20, 10, 10, 50], "demand_share_of_field": [0.67, 0.33, 0.17, 0.83],
                                         "graduate_share": [0.4, 0.6, 0.4, 0.6],
                                         "shortage_index": [1.67, 0.55, 0.42, 1.38]}),
            "tier": pd.DataFrame({"tier_label": ["Tier 1", "Tier 2"], "postings": [30, 60]}),
            "top_skills_state": pd.DataFrame({"state": states, "skill_uris": ["u:python", "u:excel"],
                                              "label": ["Python", "use spreadsheets software"], "postings": [20, 40]}),
            "top_skills_tier": pd.DataFrame({"tier": [1, 2], "skill_uris": ["u:python", "u:excel"],
                                             "label": ["Python", "use spreadsheets software"], "postings": [20, 40]}),
        }

    def workforce_table(self, name):
        return self._tables[name]

    def skill_indices(self, uris):
        return [self.market.skill_index[u] for u in uris if u in self.market.skill_index]

    def salary_range_for_rows(self, rows):
        return [{"p10": 250000.0, "p50": 400000.0, "p90": 650000.0, "n_support": 25, "sufficient": True} for _ in rows]


@pytest.fixture
def yojak_client(client, monkeypatch):
    from app.api.routes import graph
    from app.core.extract import SkillExtractor
    from app.core.serving import Serving

    fake = FakeServing()
    monkeypatch.setattr(Serving, "get", classmethod(lambda cls: fake))
    monkeypatch.setattr(SkillExtractor, "get", classmethod(lambda cls: FakeExtractor()))
    graph._constellation.cache_clear()
    yield client
    graph._constellation.cache_clear()


# --- student -------------------------------------------------------------------------------------

def test_student_match_returns_roles_jobs_and_why(yojak_client):
    r = yojak_client.post("/student/match", json={"text": "I know Python and SQL", "limit": 5})
    assert r.status_code == 200, r.text
    body = r.json()
    assert {s["uri"] for s in body["skills"]} == {"u:python", "u:sql"}
    assert len(body["jobs"]) == 5
    top = body["jobs"][0]
    assert top["occupation_uri"] in {"o:dev", "o:ana"}
    assert top["salary"]["p10"] <= top["salary"]["p50"] <= top["salary"]["p90"]
    assert top["why"]["matched_skills"] and top["why"]["paths"]
    assert body["roles"][0]["occupation_uri"] in {"o:dev", "o:ana"}
    assert body["model"]["served"] == "b1"


def test_student_match_filters_by_tier(yojak_client):
    r = yojak_client.post("/student/match", json={"skills": ["u:excel"], "tiers": [3], "limit": 50})
    assert r.status_code == 200
    body = r.json()
    assert body["pool_size"] == 30
    assert all(j["tier"] == 3 for j in body["jobs"])


def test_student_plan_optimal_never_worse_than_frequency(yojak_client):
    r = yojak_client.post("/student/plan", json={"skills": ["u:excel"], "target_isco2": "25", "k": 2, "tau": 0.6,
                                                  "budget": 2.0})
    assert r.status_code == 200, r.text
    body = r.json()
    opt, freq = body["optimal_plan"], body["frequency_plan"]
    assert opt["eligible_after"] >= freq["eligible_after"]
    assert len(opt["steps"]) <= 2
    assert body["effort_plan"] is not None
    assert body["pool"]["isco2"] == "25"
    for step in opt["steps"]:
        assert step["effort"]["effort"] == 1.0


def test_student_plan_empty_pool_is_400(yojak_client):
    r = yojak_client.post("/student/plan", json={"skills": ["u:excel"], "target_isco2": "99"})
    assert r.status_code == 400


def test_student_plan_validates_k(yojak_client):
    assert yojak_client.post("/student/plan", json={"skills": [], "k": 50}).status_code == 422


# --- recruiter -----------------------------------------------------------------------------------

def test_recruiter_rank_labels_synthetic_and_uploads(yojak_client):
    files = [("resumes", ("cv.txt", b"Experienced in Python, SQL and Java", "text/plain"))]
    r = yojak_client.post("/recruiter/rank", data={"jd_text": "Need Python and SQL", "jd_skills": "[]"}, files=files)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["pool"] == {"synthetic": 2, "uploaded": 1}
    ids = [c["candidate_id"] for c in body["candidates"]]
    assert ids.index("SC-0002") > ids.index("SC-0001")
    by_id = {c["candidate_id"]: c for c in body["candidates"]}
    assert by_id["SC-0001"]["synthetic"] is True
    assert by_id["UP-01"]["synthetic"] is False and by_id["UP-01"]["coverage"] == 1.0
    assert any("SYNTHETIC" in n for n in body["notes"])


def test_recruiter_rank_rejects_bad_skill_json_and_empty_jd(yojak_client):
    assert yojak_client.post("/recruiter/rank", data={"jd_skills": "not json"}).status_code == 400
    assert yojak_client.post("/recruiter/rank", data={"jd_text": "nothing relevant"}).status_code == 400


# --- institution ---------------------------------------------------------------------------------

def test_institution_coverage(yojak_client):
    r = yojak_client.post("/institution/coverage", data={"syllabus_text": "Python; SQL; statistics", "isco2": "25",
                                                         "tiers": "[1, 2, 3]"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert 0 < body["coverage"] <= 1
    covered = {c["skill"]["uri"] for c in body["covered"]}
    missing = {c["skill"]["uri"] for c in body["missing_high_demand"]}
    assert {"u:python", "u:sql"} <= covered
    assert not covered & missing


def test_institution_coverage_file_upload(yojak_client):
    files = {"syllabus": ("syllabus.txt", b"Unit 1: Excel. Unit 2: Tally. Unit 3: communication", "text/plain")}
    r = yojak_client.post("/institution/coverage", files=files, data={"isco2": "24"})
    assert r.status_code == 200, r.text
    assert r.json()["coverage"] > 0.5


def test_institution_coverage_bad_file_type(yojak_client):
    files = {"syllabus": ("syllabus.exe", b"MZ....", "application/octet-stream")}
    assert yojak_client.post("/institution/coverage", files=files).status_code == 400


# --- salary, extract ---------------------------------------------------------------------------------

def test_salary_estimate_always_has_interval(yojak_client):
    r = yojak_client.get("/salary/estimate", params={"occupation_uri": "o:dev", "tier": 2, "exp_min": 1})
    assert r.status_code == 200, r.text
    s = r.json()["salary"]
    assert s["p10"] <= s["p50"] <= s["p90"] and s["n_support"] == 42
    assert r.json()["basis"]["isco_code"] == "2512"


def test_salary_estimate_without_tier_pools_support_over_tiers(yojak_client):
    s = yojak_client.get("/salary/estimate", params={"occupation_uri": "o:dev"}).json()["salary"]
    assert s["n_support"] == 25 and s["sufficient"] is True


def test_extract_skills_and_file(yojak_client):
    r = yojak_client.post("/extract/skills", json={"text": "python, excel"})
    assert r.status_code == 200
    assert {s["uri"] for s in r.json()["skills"]} == {"u:python", "u:excel"}
    r = yojak_client.post("/extract/file", files={"file": ("cv.txt", b"java and sql", "text/plain")})
    assert r.status_code == 200
    assert {s["uri"] for s in r.json()["skills"]} == {"u:java", "u:sql"}


# --- workforce -------------------------------------------------------------------------------------

def test_workforce_fields_demand_shortage(yojak_client):
    f = yojak_client.get("/workforce/fields").json()
    assert f["fields"][0] == {"field": "business", "postings": 60}
    d = yojak_client.get("/workforce/demand", params={"field": "icts"}).json()
    assert d["total_postings"] == 30
    assert abs(sum(s["share"] for s in d["by_state"]) - 1) < 1e-9
    s = yojak_client.get("/workforce/shortage").json()
    assert s["proxy"] is True and s["caveats"]
    # inf is not valid JSON: it must come back as null, sorted last
    assert s["states"][-1]["shortage_index"] is None


# --- jobs, graph, reports --------------------------------------------------------------------------

def test_jobs_search_and_get(yojak_client):
    r = yojak_client.get("/jobs", params={"q": "accountant", "tier": 3})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 10 and all(j["tier"] == 3 for j in body["jobs"])
    one = yojak_client.get(f"/jobs/{body['jobs'][0]['job_id']}").json()
    assert one["skills"] and one["salary"]["sufficient"] is True
    assert yojak_client.get("/jobs/NOPE").status_code == 404


def test_job_graph_path_uses_neo4j(yojak_client, fake_neo4j):
    fake_neo4j.on(r"MATCH \(s:Skill", [{"skill": "Python", "job": "Python Developer", "occupation": "software developer",
                                         "nco": "2512", "city": "Pune", "state": "Maharashtra", "tag": "python",
                                         "link_score": 1.0, "link_method": "exact"}])
    r = yojak_client.get("/jobs/J000/path", params={"skill_uri": "u:python"})
    assert r.status_code == 200, r.text
    kinds = [p["kind"] for p in r.json()["path"]]
    assert kinds[0] == "Naukri tag" and "ESCO occupation" in kinds


def test_graph_constellation_shape(yojak_client):
    r = yojak_client.get("/graph/constellation", params={"skills": 20, "occupations": 3, "edges": 20})
    assert r.status_code == 200
    body = r.json()
    ids = {n["id"] for n in body["nodes"]}
    assert {n["kind"] for n in body["nodes"]} == {"skill", "occupation"}
    assert all(e["source"] in ids and e["target"] in ids for e in body["edges"])
    assert body["postings"] == 90


def test_reports_list_and_unknown(yojak_client):
    r = yojak_client.get("/reports")
    assert r.status_code == 200
    assert yojak_client.get("/reports/../../etc/passwd").status_code in (404, 422)
    assert yojak_client.get("/reports/not_a_report").status_code == 404


def test_recruiter_candidates_json_is_valid(yojak_client):
    r = yojak_client.post("/recruiter/rank", data={"jd_skills": json.dumps(["u:excel", "u:tally"]), "limit": 1})
    assert r.status_code == 200
    assert [c["candidate_id"] for c in r.json()["candidates"]] == ["SC-0002"]
