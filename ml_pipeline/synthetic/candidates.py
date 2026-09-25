# ml_pipeline/synthetic/candidates.py

"""
SYNTHETIC candidate pool for the recruiter view (there is no real candidate data).

Each profile:
  occupation   drawn in proportion to Naukri demand (postings per ESCO occupation)
  skills       ESCO essential skills of that occupation with p=0.5, optional with p=0.15,
               plus the skills Indian postings for that occupation list most often
               (each with p=0.5, top 12), plus 2 random skills as noise
  city, band   drawn from the postings of that occupation
  id           SC-0001 ... (no invented human names); synthetic = True always

    python -m ml_pipeline.synthetic.candidates [--n 3000]
  -> artifacts/synthetic/candidates.parquet (+ :Candidate {synthetic: true} nodes in Neo4j)
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter

import numpy as np
import pandas as pd

from app.core.settings import get_settings

SEED = 2025


def generate(n: int = 3000, seed: int = SEED) -> pd.DataFrame:
    from ml_pipeline.upskilling.market import load_market

    s = get_settings()
    rng = np.random.default_rng(seed)
    market = load_market()
    jobs = market.jobs[market.jobs["occupation_uri"].notna()]
    demand = jobs["occupation_uri"].value_counts()
    demand = demand[demand >= 5]
    probs = (demand / demand.sum()).to_numpy()

    rel = pd.read_csv(s.esco_data_dir / "occupationSkillRelations_en.csv", dtype=str, keep_default_na=False,
                      usecols=["occupationUri", "skillUri", "relationType"])
    rel = rel[rel["skillUri"].isin(market.skill_index)]
    esco_profile = {o: g for o, g in rel.groupby("occupationUri")}
    posting_skills = {o: Counter(u for us in g["skill_uris"] for u in us) for o, g in jobs.groupby("occupation_uri")}
    label = dict(zip(jobs["occupation_uri"], jobs["occupation_label"], strict=False))

    rows = []
    occ_choices = rng.choice(demand.index.to_numpy(), size=n, p=probs)
    for i, occ in enumerate(occ_choices):
        skills: set[str] = set()
        prof = esco_profile.get(occ)
        if prof is not None:
            keep = rng.random(len(prof)) < np.where(prof["relationType"] == "essential", 0.5, 0.15)
            skills |= set(prof.loc[keep, "skillUri"])
        common = [u for u, _ in posting_skills.get(occ, Counter()).most_common(12)]
        skills |= {u for u in common if rng.random() < 0.5}
        skills |= set(rng.choice(market.skills, size=2, replace=False))
        own = jobs[jobs["occupation_uri"] == occ]
        pick = own.iloc[int(rng.integers(len(own)))]
        rows.append({
            "candidate_id": f"SC-{i + 1:04d}",
            "synthetic": True,
            "occupation_uri": occ,
            "occupation_label": label.get(occ),
            "skill_uris": sorted(skills),
            "city": pick["primary_city"],
            "state": pick["primary_state"],
            "tier": pick["primary_tier"],
            "exp_band": pick["exp_band"],
        })
    return pd.DataFrame(rows)


def load_to_neo4j(df: pd.DataFrame) -> int:
    from app.core.neo4j import Neo4jClient

    s = get_settings()
    db = Neo4jClient(s.neo4j_uri, s.neo4j_user, s.neo4j_password)
    db.connect()
    try:
        db.run_query("CREATE CONSTRAINT candidate_id IF NOT EXISTS FOR (c:Candidate) REQUIRE c.id IS UNIQUE")
        db.run_query("MATCH (c:Candidate) WHERE c.synthetic = true DETACH DELETE c")
        rows = [{"id": r.candidate_id, "occ": r.occupation_uri, "skills": list(r.skill_uris), "city": r.city,
                 "state": r.state, "tier": None if pd.isna(r.tier) else int(r.tier), "exp": r.exp_band}
                for r in df.itertuples(index=False)]
        for i in range(0, len(rows), 1000):
            db.run_write(
                """
                UNWIND $rows AS row
                CREATE (c:Candidate {id: row.id, synthetic: true, city: row.city, state: row.state,
                                     tier: row.tier, expBand: row.exp})
                WITH c, row
                OPTIONAL MATCH (o:Occupation {uri: row.occ})
                FOREACH (_ IN CASE WHEN o IS NULL THEN [] ELSE [1] END | MERGE (c)-[:PROFILE_OF]->(o))
                WITH c, row
                UNWIND row.skills AS su
                MATCH (s:Skill {uri: su})
                MERGE (c)-[:HAS_SKILL]->(s)
                """,
                {"rows": rows[i:i + 1000]},
            )
        return db.run_query("MATCH (c:Candidate {synthetic: true}) RETURN count(c) AS n")[0]["n"]
    finally:
        db.close()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=3000)
    ap.add_argument("--skip-neo4j", action="store_true")
    args = ap.parse_args(argv)
    df = generate(args.n)
    out = get_settings().artifacts_dir / "synthetic"
    out.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out / "candidates.parquet", index=False)
    print(f"{len(df)} SYNTHETIC candidates; median {int(df['skill_uris'].map(len).median())} skills each")
    if not args.skip_neo4j:
        print(f"Neo4j: {load_to_neo4j(df)} :Candidate {{synthetic: true}} nodes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
