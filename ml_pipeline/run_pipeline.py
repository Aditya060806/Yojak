# ml_pipeline/run_pipeline.py

"""
Build everything Yojak serves, in order (evaluations live in ml_pipeline.evaluate_all).

Stages
  graph      load the ESCO graph into Neo4j                          (from SkillAlign, fixed)
  index      embed ESCO occupations, build the FAISS index           (from SkillAlign)
  india      Naukri postings -> cleaned, geocoded, ESCO-linked jobs; Neo4j India layer;
             reports/data_quality.json
  salary     quantile salary models + conformal calibration; reports/salary_eval.json
  supply     AISHE / PLFS state tables, India map GeoJSON, workforce analytics;
             reports/workforce_summary.json
  synthetic  labelled SYNTHETIC candidate pool (recruiter demo)
  serving    precompute ESCO label embeddings (English + multilingual) for the API

Usage
  python -m ml_pipeline.run_pipeline                        # all stages
  python -m ml_pipeline.run_pipeline --stages india salary  # a subset, in the order above
"""

from __future__ import annotations

import argparse
import sys
import time

from app.core.settings import get_settings

ALL_STAGES = ("graph", "index", "india", "salary", "supply", "synthetic", "serving")


def run_esco(stages: tuple[str, ...]) -> None:
    from ml_pipeline.data_ingestion import ingest_all_data
    from ml_pipeline.data_processing import clean_and_merge_data

    raw_data = ingest_all_data()
    if "graph" in stages:
        from ml_pipeline.neo4j_etl import load_rich_esco_to_neo4j

        print("\n[graph] Loading ESCO graph into Neo4j", flush=True)
        load_rich_esco_to_neo4j(raw_data)
    if "index" in stages:
        from ml_pipeline.embedding_generator import generate_and_index_embeddings

        print("\n[index] Embedding occupations and building FAISS index", flush=True)
        generate_and_index_embeddings(clean_and_merge_data(raw_data))


def run_stage(stage: str) -> None:
    if stage == "india":
        from ml_pipeline.india import gold
        from ml_pipeline.india.run import run

        run()
        if not (gold.gold_dir() / "skill_link_sample.csv").exists():
            gold.main(["sample"])
    elif stage == "salary":
        from ml_pipeline.salary.evaluate import main as salary_main

        salary_main()
    elif stage == "supply":
        from ml_pipeline.supply import geo_boundaries, parse, workforce

        parse.main()
        geo_boundaries.main()
        workforce.main()
    elif stage == "synthetic":
        from ml_pipeline.synthetic.candidates import main as synth_main

        synth_main([])
    elif stage == "serving":
        from app.core.extract import SkillExtractor

        ex = SkillExtractor.get()
        for multilingual in (False, True):
            print(f"  ESCO label embeddings ({'multilingual' if multilingual else 'English'} model)", flush=True)
            ex._linker(multilingual)


def run_ml_pipeline(stages: tuple[str, ...] = ALL_STAGES) -> None:
    settings = get_settings()
    start = time.time()
    print("=" * 60)
    print("Yojak pipeline")
    print(f"Environment: {settings.environment}  |  stages: {', '.join(stages)}")
    print("=" * 60, flush=True)
    if {"graph", "index"} & set(stages):
        run_esco(stages)
    for stage in ALL_STAGES[2:]:
        if stage in stages:
            t0 = time.time()
            print(f"\n=== {stage}", flush=True)
            run_stage(stage)
            print(f"=== {stage} done in {time.time() - t0:.0f} s", flush=True)
    print(f"\nPipeline finished in {time.time() - start:.0f} s.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--stages", nargs="+", choices=ALL_STAGES, default=list(ALL_STAGES))
    args = parser.parse_args(argv)
    try:
        run_ml_pipeline(tuple(s for s in ALL_STAGES if s in args.stages))
    except FileNotFoundError as e:
        print(f"\nFATAL: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
