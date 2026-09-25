"""ESCO pipeline regressions: Windows CSV limit, ISCO codes, altLabels, batching."""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd

from ml_pipeline import data_ingestion
from ml_pipeline.neo4j_etl import split_alt_labels, write_batched


def test_csv_field_limit_is_set_without_overflow():
    # Regression (audit bug #1): sys.maxsize overflowed the C long on Windows.
    assert csv.field_size_limit() >= 2**31 - 1


def test_ingestion_keeps_isco_leading_zeros(tmp_path: Path, monkeypatch):
    (tmp_path / "ISCOGroups_en.csv").write_text(
        "conceptType,conceptUri,code,preferredLabel\n"
        "ISCOGroup,http://data.europa.eu/esco/isco/C0110,0110,Commissioned armed forces officers\n",
        encoding="utf-8",
    )

    class S:
        esco_data_dir = tmp_path

    monkeypatch.setattr(data_ingestion, "get_settings", lambda: S())
    df = data_ingestion.load_esco_data("ISCOGroups_en.csv")
    assert df.loc[0, "code"] == "0110"


def test_split_alt_labels():
    assert split_alt_labels("data scientist\nanalytics specialist\n\n  ") == [
        "data scientist",
        "analytics specialist",
    ]
    assert split_alt_labels(float("nan")) == []
    assert split_alt_labels(None) == []


def test_write_batched_chunks_rows():
    calls: list[int] = []

    class Session:
        def execute_write(self, fn, rows):
            calls.append(len(rows))

    write_batched(Session(), lambda tx, rows: None, [{}] * 12, batch_size=5)
    assert calls == [5, 5, 2]


def test_processing_builds_embedding_text():
    from ml_pipeline.data_processing import clean_and_merge_data

    raw = {
        "occupations_core": pd.DataFrame(
            {"conceptUri": ["o1"], "preferredLabel": ["Data Analyst"], "description": ["Analyses data"], "definition": [None]}
        ),
        "occupations_research": pd.DataFrame({"conceptUri": [], "preferredLabel": []}),
        "skills_core": pd.DataFrame({"conceptUri": ["s1"], "preferredLabel": ["SQL"]}),
        "occupation_skill_relations": pd.DataFrame({"occupationUri": ["o1"], "skillUri": ["s1"]}),
    }
    out = clean_and_merge_data(raw)
    assert list(out.columns) == ["occupation_uri", "occupation_label", "text_for_embedding"]
    assert out.loc[0, "text_for_embedding"].startswith("data analyst. analyses data.")
    assert out.loc[0, "text_for_embedding"].endswith("sql")
