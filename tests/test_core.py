"""Unit tests for app.core: settings, ML scoring, metrics, admin guard."""

from __future__ import annotations

import math
from pathlib import Path

import faiss
import numpy as np
import pandas as pd
import pytest

from app.core.metrics_middleware import LatencyStore
from app.core.ml import MLEngine, l2_to_cosine
from app.core.settings import PROJECT_ROOT, Settings

# --- settings -----------------------------------------------------------------

def test_relative_paths_resolve_to_project_root():
    s = Settings(ESCO_DATA_DIR="data/raw/esco")
    assert s.esco_data_dir == (PROJECT_ROOT / "data/raw/esco").resolve()
    assert s.occupation_metadata_path.name == "occupation_metadata.csv"


def test_cors_origins_parsed():
    s = Settings(CORS_ORIGINS="http://a.test, http://b.test ,")
    assert s.cors_origin_list == ["http://a.test", "http://b.test"]


# --- FAISS distance -> cosine (regression: audit bug #6) -----------------------

@pytest.mark.parametrize("cos", [1.0, 0.9, 0.5, 0.2, 0.0])
def test_l2_to_cosine_inverts_squared_distance(cos):
    # For unit vectors IndexFlatL2 returns ||a-b||^2 = 2 - 2cos.
    assert l2_to_cosine(2 - 2 * cos) == pytest.approx(cos)


def test_l2_to_cosine_clips():
    assert l2_to_cosine(3.5) == 0.0
    assert l2_to_cosine(-0.1) == 1.0


def test_search_returns_true_cosine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    rng = np.random.default_rng(0)
    vecs = rng.normal(size=(5, 8)).astype(np.float32)
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
    index = faiss.IndexIDMap(faiss.IndexFlatL2(8))
    index.add_with_ids(vecs, np.arange(5, dtype=np.int64))
    faiss.write_index(index, str(tmp_path / "occupation.index"))
    pd.DataFrame({"occupation_uri": [f"occ{i}" for i in range(5)]}).to_csv(
        tmp_path / "occupation_metadata.csv", index=False
    )

    import app.core.ml as ml

    monkeypatch.setattr(ml, "get_settings", lambda: Settings(FAISS_INDEX_PATH=str(tmp_path / "occupation.index")))
    engine = MLEngine.__new__(MLEngine)  # singleton; reset its index for this test
    monkeypatch.setattr(engine, "faiss_index", None)
    monkeypatch.setattr(engine, "occupation_uris", None)

    results = engine.search(vecs[2], top_k=5)
    assert results[0] == ("occ2", pytest.approx(1.0, abs=1e-5))
    for uri, score in results:
        i = int(uri[3:])
        assert score == pytest.approx(max(0.0, float(vecs[2] @ vecs[i])), abs=1e-5)


def test_missing_index_does_not_reload_model(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Regression (audit bug #10): a missing index must not reload the model."""
    import app.core.ml as ml

    loads = {"n": 0}

    class DummyModel:
        def get_sentence_embedding_dimension(self):
            return 8

    def fake_st(_name):
        loads["n"] += 1
        return DummyModel()

    monkeypatch.setattr(ml, "SentenceTransformer", fake_st)
    monkeypatch.setattr(ml, "get_settings", lambda: Settings(FAISS_INDEX_PATH=str(tmp_path / "missing.index")))
    engine = MLEngine.__new__(MLEngine)
    monkeypatch.setattr(engine, "model", None)
    monkeypatch.setattr(engine, "faiss_index", None)
    monkeypatch.setattr(engine, "occupation_uris", None)

    for _ in range(3):
        assert engine.is_ready() is False
        engine._load_model()
    assert loads["n"] == 1


# --- latency store -------------------------------------------------------------

def test_latency_store_percentiles():
    store = LatencyStore(window=100)
    for ms in range(1, 101):
        store.record("GET /x", float(ms))
    (m,) = store.snapshot()
    assert m["count"] == 100 and m["window"] == 100
    assert m["min_ms"] == 1 and m["max_ms"] == 100
    assert math.isclose(m["p50_ms"], 50.5, abs_tol=0.1)


def test_latency_store_window_is_bounded():
    store = LatencyStore(window=10)
    for ms in range(100):
        store.record("GET /x", float(ms))
    (m,) = store.snapshot()
    assert m["count"] == 100 and m["window"] == 10 and m["min_ms"] == 90
