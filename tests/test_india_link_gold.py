"""Phase 1: ESCO linking, title re-ranking, NCO mapping, gold metrics and labelling API."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ml_pipeline.india import gold
from ml_pipeline.india.link import ConceptLinker, clean_title, label_variants, rerank_by_skills
from ml_pipeline.india.nco import map_occupations, nco_family_for_isco


class TrigramEncoder:
    """Deterministic stand-in for a sentence encoder: hashed character trigrams, L2-normalised."""

    model_name = "trigram-test"

    def encode(self, texts):
        out = np.zeros((len(texts), 256), dtype=np.float32)
        for i, t in enumerate(texts):
            s = f"  {t.lower()}  "
            for j in range(len(s) - 2):
                out[i, hash(s[j:j + 3]) % 256] += 1
        norms = np.linalg.norm(out, axis=1, keepdims=True)
        return out / np.where(norms == 0, 1, norms)


@pytest.fixture
def skills() -> pd.DataFrame:
    return pd.DataFrame({
        "uri": ["s:python", "s:sql", "s:teamwork", "s:java"],
        "preferredLabel": ["Python (computer programming)", "SQL", "manage a team", "Java (computer programming)"],
        "altLabels": [[], ["structured query language"], ["team management", "lead a team"], []],
    })


def test_label_variants_include_short_form():
    v = label_variants("Python (computer programming)", ["py"])
    assert ("Python", "preferred_short") in v and ("py", "alt") in v


def test_exact_match_via_short_and_alt_labels(skills):
    linker = ConceptLinker(skills, TrigramEncoder())
    res = linker.link(["python", "Team Management", "structured query language"], threshold=0.99)
    assert res["uri"].tolist() == ["s:python", "s:teamwork", "s:sql"]
    assert (res["method"] == "exact").all() and res["accepted"].all()
    # the exact concept heads the candidate list
    assert json.loads(res.loc[0, "candidates"])[0] == {"uri": "s:python", "label": "Python (computer programming)", "score": 1.0}


def test_threshold_controls_embedding_links(skills):
    linker = ConceptLinker(skills, TrigramEncoder())
    loose = linker.link(["pythn programming"], threshold=0.1).iloc[0]
    strict = linker.link(["pythn programming"], threshold=0.99).iloc[0]
    assert loose["method"] == "embedding" and loose["accepted"]
    assert not strict["accepted"] and strict["uri"] == loose["uri"]  # candidate kept, just not accepted


def test_embedding_cache_roundtrip(skills, tmp_path: Path):
    a = ConceptLinker(skills, TrigramEncoder(), tmp_path, "t")
    b = ConceptLinker(skills, TrigramEncoder(), tmp_path, "t")
    assert len(list(tmp_path.glob("t_labels_*.npy"))) == 1
    np.testing.assert_allclose(a.label_emb, b.label_emb)


@pytest.mark.parametrize("raw,clean", [
    ("Sr. AI/ML Engineer - L3 (Urgent Hiring)", "artificial intelligence machine learning engineer"),
    ("HR Recruiter (NON IT)", "human resources recruiter"),
    ("Senior Data Engineer", "data engineer"),
    ("QA Engineer", "quality assurance engineer"),
])
def test_clean_title(raw, clean):
    assert clean_title(raw) == clean


def test_rerank_never_overrides_exact_title():
    cands = [{"uri": "o:rep", "label": "sales rep", "score": 1.0}, {"uri": "o:mgr", "label": "sales mgr", "score": 0.97}]
    occ = {"o:mgr": {"s1": 1.0, "s2": 1.0}}
    best, _, _ = rerank_by_skills(cands, {"s1", "s2"}, occ, alpha=0.5)
    assert best["uri"] == "o:rep"


def test_rerank_uses_skills_within_margin_only():
    cands = [
        {"uri": "o:callcentre", "label": "call centre analyst", "score": 0.80},
        {"uri": "o:dataeng", "label": "data engineer", "score": 0.76},
        {"uri": "o:miner", "label": "mine engineer", "score": 0.50},
    ]
    occ = {"o:dataeng": {"sql": 1.0, "spark": 1.0}, "o:miner": {"sql": 1.0, "spark": 1.0}}
    best, _, overlap = rerank_by_skills(cands, {"sql", "spark"}, occ, alpha=0.5, margin=0.08)
    assert best["uri"] == "o:dataeng" and overlap == 1.0
    best2, _, _ = rerank_by_skills(cands, {"sql", "spark"}, occ, alpha=0.5, margin=0.01)
    assert best2["uri"] == "o:callcentre"  # data engineer outside the margin now


def test_rerank_without_skills_keeps_title_order():
    cands = [{"uri": "a", "label": "a", "score": 0.7}, {"uri": "b", "label": "b", "score": 0.69}]
    assert rerank_by_skills(cands, set(), {"b": {"x": 1.0}}, alpha=0.5)[0]["uri"] == "a"


# --- NCO ---------------------------------------------------------------------------------------

def test_nco_family_mapping():
    assert nco_family_for_isco("2511") == "2511"
    assert nco_family_for_isco("0110") is None  # armed forces: no NCO-2015 division 0
    assert nco_family_for_isco("25") is None and nco_family_for_isco(None) is None


def test_map_occupations_with_and_without_validation(tmp_path: Path):
    occ = pd.DataFrame({"uri": ["a", "b", "c"], "iscoGroup": ["2511", "0110", "9999"]})
    out, stats = map_occupations(occ, None)
    assert out["nco_family"].tolist() == ["2511", None, "9999"]
    assert stats["excluded_armed_forces"] == 1 and not stats["validated_against_nco_vol1_list"]
    fam = tmp_path / "fam.csv"
    fam.write_text("family_code,family_title\n2511,Systems Analysts\n", encoding="utf-8")
    out2, stats2 = map_occupations(occ, fam)
    assert out2["nco_family"].tolist() == ["2511", None, None]
    assert out2.loc[0, "nco_family_title"] == "Systems Analysts" and stats2["validated_against_nco_vol1_list"]


# --- gold metrics ------------------------------------------------------------------------------

def test_score_band_and_mention_band():
    assert gold.score_band("exact", 1.0) == "exact"
    assert gold.score_band("embedding", 0.82) == "0.80+"
    assert gold.score_band("embedding", 0.3) == "<0.60"
    bands = gold.mention_band(pd.Series([100, 60, 30, 5, 5]))
    assert bands.iloc[0] == "high" and bands.iloc[-1] == "low"


def test_is_dev_is_deterministic_and_balanced():
    keys = [f"tag{i}" for i in range(2000)]
    share = np.mean([gold.is_dev(k) for k in keys])
    assert 0.45 < share < 0.55
    assert gold.is_dev("python") == gold.is_dev("python")


def test_weighted_precision_recall():
    df = pd.DataFrame({
        "method": ["exact", "embedding", "embedding", "embedding"],
        "score": [1.0, 0.9, 0.65, 0.95],
        "uri": ["a", "b", "c", "d"],
        "gold_uri": ["a", "x", "c", "NONE"],
        "w": [10.0, 1.0, 1.0, 1.0],
    })
    p, r, _ = gold._weighted_pr(df, 0.7, "w")
    # accepted: a (correct, w10), b (wrong, w1), d (wrong: gold NONE, w1) -> precision 10/12
    assert p == pytest.approx(10 / 12)
    # valid gold: a, b, c -> weights 12; correct accepted: a -> recall 10/12
    assert r == pytest.approx(10 / 12)


def test_sample_tags_is_stratified_and_weighted():
    rng = np.random.default_rng(0)
    n = 3000
    tl = pd.DataFrame({
        "tag": [f"t{i}" for i in range(n)],
        "freq": rng.integers(1, 500, n),
        "method": np.where(rng.random(n) < 0.1, "exact", "embedding"),
        "score": rng.random(n),
        "uri": "u", "label": "l", "candidates": "[]",
    })
    jobs = pd.DataFrame({"title": ["x"], "tags": [["t1"]]})
    s = gold.sample_tags(tl, jobs, n=200)
    assert len(s) == 200 and s["tag"].is_unique
    assert s["stratum"].nunique() == 15
    assert (s["stratum_mentions"] >= s["freq"]).all()


# --- labelling API ------------------------------------------------------------------------------

@pytest.fixture
def gold_env(tmp_path: Path, monkeypatch):
    from app.core import settings as settings_mod

    monkeypatch.setenv("GOLD_DATA_DIR", str(tmp_path))
    settings_mod.get_settings.cache_clear()
    pd.DataFrame({"tag": ["python", "c#"], "freq": [10, 5], "candidates": ['[{"uri":"s:py","label":"Python","score":1.0}]', "[]"],
                  "split": ["dev", "test"]}).to_csv(tmp_path / "skill_link_sample.csv", index=False)
    (tmp_path / "multilingual_seed.csv").write_text(
        "# seed\nskill_uri,english_label,naukri_mentions\ns:acc,accounting,100\n", encoding="utf-8")
    yield tmp_path
    settings_mod.get_settings.cache_clear()


ADMIN = {"X-Admin-Token": "test-admin-token"}


def test_labelling_skill_flow(client, gold_env):
    items = client.get("/admin/labelling/skills/items").json()
    assert items["total"] == 2 and items["done"] == 0
    assert {i["tag"] for i in items["items"]} == {"python", "c#"}  # '#' inside a value survives
    r = client.post("/admin/labelling/skills/labels", json={"key": "python", "gold_uri": "s:py", "labeller": "asha"})
    assert r.status_code == 401
    r = client.post("/admin/labelling/skills/labels", headers=ADMIN,
                    json={"key": "python", "gold_uri": "s:py", "labeller": "asha"})
    assert r.status_code == 201
    assert client.get("/admin/labelling/skills/items").json()["done"] == 1
    bad = client.post("/admin/labelling/skills/labels", headers=ADMIN,
                      json={"key": "not-in-sample", "gold_uri": "x", "labeller": "asha"})
    assert bad.status_code == 404


def test_labelling_multilingual_flow(client, gold_env):
    r = client.post("/admin/labelling/multilingual/labels", headers=ADMIN,
                    json={"key": "s:acc", "language": "hi", "phrase": "लेखांकन", "labeller": "ravi"})
    assert r.status_code == 201
    data = client.get("/admin/labelling/multilingual/items").json()
    assert data["items"][0]["phrases"] == {"hi": "लेखांकन"}
    assert data["done"] == 1 and data["total"] == 3
    bad = client.post("/admin/labelling/multilingual/labels", headers=ADMIN,
                      json={"key": "s:acc", "language": "fr", "phrase": "x", "labeller": "ravi"})
    assert bad.status_code == 400
