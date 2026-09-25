# ml_pipeline/india/run.py

"""
India data layer pipeline.

    python -m ml_pipeline.india.run                  # everything
    python -m ml_pipeline.india.run --skip-neo4j     # files + report only

Outputs
  data/processed/india/*.parquet      cleaned jobs, cities, tag links, title links
  reports/data_quality.json           row counts, missingness, linking coverage,
                                      gold precision (once team labels exist),
                                      temporal verdict
Neo4j                                 Job / Company / City / State / Tag layer

Linking thresholds come from artifacts/linking_thresholds.json when the gold
evaluation has tuned them; otherwise provisional defaults are used and the
report says so.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

from app.core.settings import get_settings
from ml_pipeline.common import provenance, stage, write_report
from ml_pipeline.india.clean import clean_postings, temporal_evidence
from ml_pipeline.india.geo import Gazetteer, geocode_jobs
from ml_pipeline.india.link import (
    ConceptLinker,
    EmbeddingModel,
    clean_title,
    esco_concepts,
    rerank_by_skills,
)
from ml_pipeline.india.nco import map_occupations

NAUKRI_FILE = "indian-job-market-dataset-2025.xlsx"

# Provisional values, replaced by gold-tuned ones (artifacts/linking_thresholds.json).
DEFAULT_THRESHOLDS = {
    "skill_link_threshold": 0.70,
    "title_link_threshold": 0.60,
    "title_skill_alpha": 0.70,
    "title_rerank_margin": 0.08,
    # Ambiguity guard for one-word tags linked by embedding (see ConceptLinker.link).
    "single_token_threshold": 0.80,
    "status": "provisional (not yet tuned on team-labelled gold data)",
}


def load_thresholds() -> dict:
    path = get_settings().artifacts_dir / "linking_thresholds.json"
    if path.exists():
        tuned = json.loads(path.read_text(encoding="utf-8"))
        return {**DEFAULT_THRESHOLDS, **tuned}
    return dict(DEFAULT_THRESHOLDS)


def india_dir() -> Path:
    d = get_settings().processed_data_dir / "india"
    d.mkdir(parents=True, exist_ok=True)
    return d


def read_raw() -> tuple[pd.DataFrame, Path]:
    """Read the Kaggle xlsx once and cache it as parquet (keyed by file size+mtime)."""
    src = get_settings().naukri_data_dir / NAUKRI_FILE
    if not src.exists():
        raise FileNotFoundError(f"{src} not found. Run: scripts/run.ps1 data")
    stamp = f"{src.stat().st_size}_{int(src.stat().st_mtime)}"
    cache = india_dir() / f"raw_{stamp}.parquet"
    if cache.exists():
        return pd.read_parquet(cache), src
    df = pd.read_excel(src, dtype=str)
    for old in india_dir().glob("raw_*.parquet"):
        old.unlink()
    df.to_parquet(cache, index=False)
    return df, src


def occupation_skill_weights(esco_dir: Path) -> dict[str, dict[str, float]]:
    """occupation uri -> {skill uri: 1.0 essential | 0.5 optional}."""
    rel = pd.read_csv(esco_dir / "occupationSkillRelations_en.csv", dtype=str, keep_default_na=False)
    out: dict[str, dict[str, float]] = {}
    for occ, skill, kind in zip(rel["occupationUri"], rel["skillUri"], rel["relationType"], strict=True):
        out.setdefault(occ, {})[skill] = 1.0 if kind == "essential" else 0.5
    return out


def missingness(df: pd.DataFrame, cols: list[str]) -> dict[str, float]:
    return {c: round(float(df[c].isna().mean()), 4) for c in cols if c in df}


def run(skip_neo4j: bool = False, model_name: str | None = None) -> dict:
    settings = get_settings()
    thresholds = load_thresholds()
    timings: dict[str, float] = {}
    out_dir = india_dir()
    model_name = model_name or settings.model_name

    with stage("acquire", timings):
        raw, src = read_raw()
        temporal = temporal_evidence(raw)
        print(f"  {len(raw):,} rows; posting dates available: {temporal['posting_dates_available']}")

    with stage("clean", timings):
        jobs, steplog, salary_stats = clean_postings(raw, usd_policy="exclude")
        print(f"  {len(jobs):,} jobs after cleaning; salary disclosed {salary_stats['disclosed_share']:.1%}")

    with stage("geo", timings):
        ext = settings.external_data_dir
        gaz = Gazetteer(
            ext / "geonames" / "IN.txt", ext / "geonames" / "admin1CodesASCII.txt",
            settings.reference_data_dir / "city_tiers.csv", settings.reference_data_dir / "city_aliases.csv",
        )
        jobs, job_cities, geo_stats = geocode_jobs(jobs, gaz)
        print(f"  city resolution (excl. remote): {geo_stats['city_resolution_rate_excl_remote']:.1%}")

    encoder = EmbeddingModel(model_name)
    cache = settings.artifacts_dir / "cache" / "emb"
    slug = model_name.rsplit("/", 1)[-1]

    with stage("link_skills", timings):
        tag_freq = Counter(t for ts in jobs["tags"] for t in ts)
        skills = esco_concepts(settings.esco_data_dir, "skill")
        skill_linker = ConceptLinker(skills, encoder, cache, f"esco_skill_{slug}")
        tag_links = skill_linker.link(list(tag_freq), threshold=thresholds["skill_link_threshold"],
                                      single_token_threshold=thresholds["single_token_threshold"])
        tag_links = tag_links.rename(columns={"text": "tag"})
        tag_links["freq"] = tag_links["tag"].map(tag_freq).astype(int)
        tag_links["n_words"] = tag_links["tag"].str.split().map(len)
        tag_uri = dict(zip(tag_links.loc[tag_links["accepted"], "tag"], tag_links.loc[tag_links["accepted"], "uri"], strict=True))
        job_tags = jobs[["jobId", "tags"]].explode("tags").dropna().rename(columns={"tags": "tag"})
        job_tags["skill_uri"] = job_tags["tag"].map(tag_uri)
        jobs["skill_uris"] = jobs["tags"].map(lambda ts: sorted({tag_uri[t] for t in ts if t in tag_uri}))
        jobs["n_linked_skills"] = jobs["skill_uris"].map(len)
        mention_cov = float(tag_links.loc[tag_links["accepted"], "freq"].sum() / tag_links["freq"].sum())
        print(f"  {len(tag_links):,} unique tags; {tag_links['accepted'].mean():.1%} linked; mentions covered {mention_cov:.1%}")

    with stage("link_titles", timings):
        jobs["title_clean"] = jobs["title"].map(clean_title)
        occs = esco_concepts(settings.esco_data_dir, "occupation")
        occ_linker = ConceptLinker(occs, encoder, cache, f"esco_occ_{slug}")
        uniq = pd.Series(jobs["title_clean"].unique())
        cand_df = occ_linker.link(uniq.tolist(), threshold=thresholds["title_link_threshold"], top_k=10)
        cands_by_title = dict(zip(cand_df["text"], cand_df["candidates"].map(json.loads), strict=True))
        occ_skills = occupation_skill_weights(settings.esco_data_dir)
        alpha = thresholds["title_skill_alpha"]
        chosen = []
        for title, skill_uris in zip(jobs["title_clean"], jobs["skill_uris"], strict=True):
            cands = cands_by_title.get(title, [])
            best, combined, overlap = rerank_by_skills(
                cands, set(skill_uris), occ_skills, alpha, thresholds["title_rerank_margin"])
            if best is None:
                chosen.append((None, None, np.nan, np.nan, False))
                continue
            # Skills may re-rank candidates, but a title must itself be similar enough.
            accepted = best["score"] >= thresholds["title_link_threshold"]
            chosen.append((best["uri"], best["label"], best["score"], overlap, accepted))
        jobs["occupation_uri"] = [c[0] if c[4] else None for c in chosen]
        jobs["occupation_label"] = [c[1] if c[4] else None for c in chosen]
        jobs["title_sim"] = [c[2] for c in chosen]
        jobs["skill_overlap"] = [c[3] for c in chosen]
        title_links = cand_df.rename(columns={"text": "title_clean"})
        title_links["freq"] = title_links["title_clean"].map(jobs["title_clean"].value_counts())
        rerank_changed = float(np.mean([
            bool(cands_by_title.get(t)) and c[0] is not None and c[0] != cands_by_title[t][0]["uri"]
            for t, c in zip(jobs["title_clean"], chosen, strict=True)
        ]))
        print(f"  {jobs['occupation_uri'].notna().mean():.1%} of jobs linked to an ESCO occupation; "
              f"skill re-ranking changed the top pick for {rerank_changed:.1%}")

    with stage("nco", timings):
        nco, nco_stats = map_occupations(occs, settings.reference_data_dir / "nco2015_families.csv")
        jobs["nco_family"] = jobs["occupation_uri"].map(dict(zip(nco["uri"], nco["nco_family"], strict=True)))
        jobs["isco_code"] = jobs["occupation_uri"].map(dict(zip(nco["uri"], nco["isco_code"], strict=True)))

    with stage("save", timings):
        keep = [c for c in jobs.columns if c not in {"jobDescription", "tagsAndSkills", "salary", "experience"}]
        jobs[keep].to_parquet(out_dir / "jobs.parquet", index=False)
        jobs[["jobId", "jobDescription"]].to_parquet(out_dir / "job_descriptions.parquet", index=False)
        job_cities.to_parquet(out_dir / "job_cities.parquet", index=False)
        job_tags.to_parquet(out_dir / "job_tags.parquet", index=False)
        tag_links.to_parquet(out_dir / "tag_links.parquet", index=False)
        title_links.to_parquet(out_dir / "title_links.parquet", index=False)
        nco.to_parquet(out_dir / "nco.parquet", index=False)

    neo4j_counts = None
    if not skip_neo4j:
        with stage("neo4j", timings):
            from app.core.neo4j import Neo4jClient
            from ml_pipeline.india.load_neo4j import load_india_layer

            db = Neo4jClient(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
            db.connect()
            try:
                neo4j_counts = load_india_layer(db, jobs, job_cities, job_tags, tag_links, nco,
                                                log=lambda m: print(m, flush=True))
            finally:
                db.close()
            print(f"  {neo4j_counts}")

    with stage("report", timings):
        report = build_report(raw, jobs, steplog, salary_stats, temporal, geo_stats, tag_links, title_links,
                              nco_stats, thresholds, model_name, neo4j_counts, timings,
                              title_extra={"rerank_changed_share": rerank_changed})
        from ml_pipeline.india.gold import gold_linking_metrics

        report["gold_evaluation"] = gold_linking_metrics(tag_links, title_links, jobs)
        prov = provenance(
            "ml_pipeline/india/run.py",
            inputs=[src, settings.reference_data_dir / "city_tiers.csv", settings.reference_data_dir / "city_aliases.csv",
                    settings.esco_data_dir / "skills_en.csv", settings.esco_data_dir / "occupations_en.csv"],
            embedding_model=model_name,
        )
        path = write_report("data_quality", report, prov)
        print(f"  wrote {path}")
    return report


def build_report(raw, jobs, steplog, salary_stats, temporal, geo_stats, tag_links, title_links,
                 nco_stats, thresholds, model_name, neo4j_counts, timings, title_extra) -> dict:
    accepted = tag_links["accepted"]
    w = tag_links["freq"]
    unlinked = tag_links[~accepted].sort_values("freq", ascending=False)
    disclosed = jobs["salary_disclosed"]
    tier = jobs["primary_tier"]
    by_tier = {
        str(int(t)) if pd.notna(t) else "unknown": {
            "jobs": int((tier == t).sum()) if pd.notna(t) else int(tier.isna().sum()),
            "salary_disclosed_share": round(float(disclosed[(tier == t) if pd.notna(t) else tier.isna()].mean()), 4),
        }
        for t in [1, 2, 3, np.nan]
    }
    return {
        "dataset": {
            "name": "Indian Job Market Dataset 2025 (Naukri.com)",
            "source": "kaggle:shivamshrivastava21/indian-job-market-dataset-2025-2026",
            "licence": "CC BY-NC-SA 4.0",
            "raw_rows": len(raw),
            "raw_columns": list(raw.columns),
        },
        "row_counts": steplog.steps,
        "final_jobs": len(jobs),
        "missingness_raw": missingness(raw.replace({"": np.nan}), list(raw.columns)),
        "missingness_clean": missingness(
            jobs, ["salary_mid_inr", "exp_min", "exp_band", "company_rating", "primary_city", "primary_tier",
                   "occupation_uri", "posted_date"]),
        "temporal": temporal,
        "salary": {**salary_stats, "by_tier": by_tier,
                   "usd_note": ("All USD-labelled salaries in this dataset are Indian roles quoting rupee "
                                "amounts (e.g. a Nagpur trainee at '10,000-15,000 USD PA'); converting them "
                                "would invent salaries, so they are flagged currency_suspect and excluded.")},
        "geography": geo_stats,
        "skill_linking": {
            "model": model_name,
            "threshold": thresholds["skill_link_threshold"],
            "single_token_threshold": thresholds["single_token_threshold"],
            "single_token_guard": ("One-word tags linked by embedding (not an exact ESCO label) need a higher "
                                   "cosine; e.g. 'development' -> 'developmental psychology' (0.745) is rejected."),
            "tags_rejected_by_guard": int(((tag_links["method"] == "embedding") & (tag_links["n_words"] == 1)
                                           & (tag_links["score"] >= thresholds["skill_link_threshold"])
                                           & (tag_links["score"] < thresholds["single_token_threshold"])).sum()),
            "threshold_status": thresholds["status"],
            "unique_tags": len(tag_links),
            "tag_mentions": int(w.sum()),
            "unique_tags_linked": int(accepted.sum()),
            "unique_tag_coverage": round(float(accepted.mean()), 4),
            "mention_coverage": round(float(w[accepted].sum() / w.sum()), 4),
            "method_counts": tag_links.loc[accepted, "method"].value_counts().to_dict(),
            "distinct_esco_skills_used": int(tag_links.loc[accepted, "uri"].nunique()),
            "jobs_with_any_linked_skill": int((jobs["n_linked_skills"] > 0).sum()),
            "linked_skills_per_job": {
                "mean": round(float(jobs["n_linked_skills"].mean()), 2),
                "median": float(jobs["n_linked_skills"].median()),
            },
            "coverage_by_threshold": {
                str(t): {
                    "unique": round(float(((tag_links["method"] == "exact") | (tag_links["score"] >= t)).mean()), 4),
                    "mentions": round(float(w[(tag_links["method"] == "exact") | (tag_links["score"] >= t)].sum() / w.sum()), 4),
                }
                for t in [0.6, 0.65, 0.7, 0.75, 0.8, 0.85]
            },
            "top_unlinked_tags": [
                {"tag": r.tag, "freq": int(r.freq), "best_candidate": r.label, "score": round(float(r.score), 3)}
                for r in unlinked.head(50).itertuples()
            ],
            "unlinked_note": ("Unlinked tags stay in the graph as :Tag nodes. Many frequent ones are modern "
                              "tools with no ESCO concept (a taxonomy gap), not noise."),
        },
        "title_linking": {
            "model": model_name,
            "threshold": thresholds["title_link_threshold"],
            "skill_rerank_alpha": thresholds["title_skill_alpha"],
            "skill_rerank_margin": thresholds["title_rerank_margin"],
            "rerank_changed_share": round(title_extra["rerank_changed_share"], 4),
            "threshold_status": thresholds["status"],
            "unique_clean_titles": len(title_links),
            "jobs_linked_to_occupation": int(jobs["occupation_uri"].notna().sum()),
            "job_coverage": round(float(jobs["occupation_uri"].notna().mean()), 4),
            "distinct_occupations_used": int(jobs["occupation_uri"].nunique()),
            "top_occupations": jobs["occupation_label"].value_counts().head(25).to_dict(),
        },
        "nco2015": nco_stats,
        "jobs_with_nco_family": int(jobs["nco_family"].notna().sum()),
        "neo4j": neo4j_counts,
        "timings_seconds": timings,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--skip-neo4j", action="store_true", help="Build files and report without loading Neo4j")
    parser.add_argument("--model", default=None, help="Embedding model (default: settings.model_name)")
    args = parser.parse_args(argv)
    try:
        run(skip_neo4j=args.skip_neo4j, model_name=args.model)
    except FileNotFoundError as e:
        print(f"FATAL: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
