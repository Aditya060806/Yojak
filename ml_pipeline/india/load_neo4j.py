# ml_pipeline/india/load_neo4j.py

"""
Load the India layer into Neo4j, linked to the ESCO nodes already there.

Nodes:  (:Job) (:Company) (:City) (:State) (:ExperienceBand) (:Tag)
Edges:  (Company)-[:POSTS]->(Job)
        (Job)-[:LOCATED_IN {rank}]->(City)-[:IN_STATE]->(State)
        (Job)-[:IN_STATE]->(State)                 only when no city was resolved
        (Job)-[:NEEDS_EXP]->(ExperienceBand)
        (Job)-[:TAGGED]->(Tag)                     every raw tag, linked or not
        (Tag)-[:SAME_AS {score, method}]->(Skill)  accepted ESCO links only
        (Job)-[:REQUIRES {source:'naukri'}]->(Skill)  derived from TAGGED + SAME_AS
        (Job)-[:MAPS_TO {title_sim, skill_overlap}]->(Occupation)
Also sets Occupation.ncoFamily.

The load is a full refresh of the India layer (ESCO nodes are untouched), so
re-running it never leaves stale jobs behind.
"""

from __future__ import annotations

from typing import Iterable

import pandas as pd

from app.core.neo4j import Neo4jClient

BATCH = 5_000


def _batches(rows: list[dict], size: int = BATCH) -> Iterable[list[dict]]:
    for i in range(0, len(rows), size):
        yield rows[i : i + size]


def _records(df: pd.DataFrame) -> list[dict]:
    """DataFrame -> list of dicts with NaN/NaT turned into None (Neo4j-safe)."""
    clean = df.astype(object).where(pd.notna(df), None)
    return clean.to_dict("records")


CONSTRAINTS = [
    "CREATE CONSTRAINT job_id IF NOT EXISTS FOR (j:Job) REQUIRE j.id IS UNIQUE",
    "CREATE CONSTRAINT company_key IF NOT EXISTS FOR (c:Company) REQUIRE c.key IS UNIQUE",
    "CREATE CONSTRAINT city_key IF NOT EXISTS FOR (c:City) REQUIRE c.key IS UNIQUE",
    "CREATE CONSTRAINT state_name IF NOT EXISTS FOR (s:State) REQUIRE s.name IS UNIQUE",
    "CREATE CONSTRAINT expband_name IF NOT EXISTS FOR (e:ExperienceBand) REQUIRE e.name IS UNIQUE",
    "CREATE CONSTRAINT tag_name IF NOT EXISTS FOR (t:Tag) REQUIRE t.name IS UNIQUE",
    "CREATE INDEX job_tier IF NOT EXISTS FOR (j:Job) ON (j.primaryTier)",
    "CREATE INDEX job_state IF NOT EXISTS FOR (j:Job) ON (j.primaryState)",
    "CREATE INDEX occupation_nco IF NOT EXISTS FOR (o:Occupation) ON (o.ncoFamily)",
]


def clear_india_layer(db: Neo4jClient) -> None:
    for label in ["Job", "Tag", "Company", "City", "State", "ExperienceBand"]:
        db.run_query(
            f"MATCH (n:{label}) CALL (n) {{ DETACH DELETE n }} IN TRANSACTIONS OF 10000 ROWS"
        )


def load_india_layer(
    db: Neo4jClient,
    jobs: pd.DataFrame,
    job_cities: pd.DataFrame,
    job_tags: pd.DataFrame,
    tag_links: pd.DataFrame,
    nco: pd.DataFrame,
    log=print,
) -> dict:
    """Full refresh of the India layer. Returns counts of what was written."""
    for stmt in CONSTRAINTS:
        db.run_query(stmt)
    log("  clearing previous India layer")
    clear_india_layer(db)

    job_cols = {
        "jobId": "id", "title": "title", "title_clean": "titleClean", "companyName": "company",
        "posted_date_str": "postedDate", "days_ago": "daysAgo", "work_mode": "workMode",
        "salary_min_inr": "salaryMin", "salary_max_inr": "salaryMax", "salary_mid_inr": "salaryMid",
        "salary_disclosed": "salaryDisclosed", "salary_flag": "salaryFlag",
        "exp_min": "expMin", "exp_max": "expMax", "exp_band": "expBand",
        "company_rating": "companyRating", "primary_city": "primaryCity", "primary_state": "primaryState",
        "primary_tier": "primaryTier", "primary_metro_region": "metroRegion", "dup_group_id": "dupGroup",
        "n_tags": "nTags", "n_cities": "nCities",
    }
    j = jobs.copy()
    j["posted_date_str"] = j["posted_date"].dt.strftime("%Y-%m-%d")
    j = j[list(job_cols)].rename(columns=job_cols)
    rows = _records(j)
    log(f"  jobs: {len(rows)}")
    for b in _batches(rows):
        db.run_write(
            """
            UNWIND $rows AS row
            CREATE (j:Job)
            SET j = row, j.postedDate = CASE WHEN row.postedDate IS NULL THEN NULL ELSE date(row.postedDate) END
            """,
            {"rows": b},
        )

    comp = jobs[["jobId", "companyName"]].copy()
    comp["key"] = comp["companyName"].str.lower().str.strip()
    comp = comp[comp["key"] != ""]
    for b in _batches(_records(comp)):
        db.run_write(
            """
            UNWIND $rows AS row
            MERGE (c:Company {key: row.key}) ON CREATE SET c.name = row.companyName
            WITH c, row
            MATCH (j:Job {id: row.jobId})
            MERGE (c)-[:POSTS]->(j)
            """,
            {"rows": b},
        )

    jc = job_cities[job_cities["city"].notna()].copy()
    jc["key"] = jc["city"] + "|" + jc["state"]
    cities = jc.drop_duplicates("key")[["key", "city", "state", "tier", "metro_region", "lat", "lon", "population"]]
    for b in _batches(_records(cities)):
        db.run_write(
            """
            UNWIND $rows AS row
            MERGE (s:State {name: row.state})
            MERGE (c:City {key: row.key})
            SET c.name = row.city, c.tier = toInteger(row.tier), c.metroRegion = row.metro_region,
                c.lat = row.lat, c.lon = row.lon, c.population = toInteger(row.population)
            MERGE (c)-[:IN_STATE]->(s)
            """,
            {"rows": b},
        )
    for b in _batches(_records(jc[["jobId", "key", "rank"]])):
        db.run_write(
            """
            UNWIND $rows AS row
            MATCH (j:Job {id: row.jobId}), (c:City {key: row.key})
            MERGE (j)-[r:LOCATED_IN]->(c) SET r.rank = toInteger(row.rank)
            """,
            {"rows": b},
        )
    state_only = job_cities[job_cities["city"].isna() & job_cities["state"].notna()]
    for b in _batches(_records(state_only[["jobId", "state"]])):
        db.run_write(
            """
            UNWIND $rows AS row
            MERGE (s:State {name: row.state})
            WITH s, row
            MATCH (j:Job {id: row.jobId})
            MERGE (j)-[:IN_STATE]->(s)
            """,
            {"rows": b},
        )

    exp = jobs.loc[jobs["exp_band"].notna(), ["jobId", "exp_band"]]
    for b in _batches(_records(exp)):
        db.run_write(
            """
            UNWIND $rows AS row
            MERGE (e:ExperienceBand {name: row.exp_band})
            WITH e, row
            MATCH (j:Job {id: row.jobId})
            MERGE (j)-[:NEEDS_EXP]->(e)
            """,
            {"rows": b},
        )

    tags = tag_links[["tag", "freq", "uri", "score", "method", "accepted"]].copy()
    for b in _batches(_records(tags)):
        db.run_write(
            """
            UNWIND $rows AS row
            CREATE (t:Tag {name: row.tag, freq: toInteger(row.freq), linked: row.accepted})
            WITH t, row WHERE row.accepted AND row.uri IS NOT NULL
            MATCH (s:Skill {uri: row.uri})
            MERGE (t)-[r:SAME_AS]->(s) SET r.score = row.score, r.method = row.method
            """,
            {"rows": b},
        )
    for b in _batches(_records(job_tags[["jobId", "tag"]]), 20_000):
        db.run_write(
            """
            UNWIND $rows AS row
            MATCH (j:Job {id: row.jobId}), (t:Tag {name: row.tag})
            CREATE (j)-[:TAGGED]->(t)
            """,
            {"rows": b},
        )
    # Derived Job-REQUIRES->Skill edges (one per distinct job/skill pair), computed
    # here rather than with a graph-wide MATCH so the load never reads what it writes.
    pairs = job_tags.dropna(subset=["skill_uri"]).drop_duplicates(["jobId", "skill_uri"])
    for b in _batches(_records(pairs[["jobId", "skill_uri"]]), 20_000):
        db.run_write(
            """
            UNWIND $rows AS row
            MATCH (j:Job {id: row.jobId}), (s:Skill {uri: row.skill_uri})
            CREATE (j)-[:REQUIRES {source: 'naukri'}]->(s)
            """,
            {"rows": b},
        )

    occ = jobs.loc[jobs["occupation_uri"].notna(), ["jobId", "occupation_uri", "title_sim", "skill_overlap"]]
    for b in _batches(_records(occ)):
        db.run_write(
            """
            UNWIND $rows AS row
            MATCH (j:Job {id: row.jobId}), (o:Occupation {uri: row.occupation_uri})
            MERGE (j)-[r:MAPS_TO]->(o) SET r.titleSim = row.title_sim, r.skillOverlap = row.skill_overlap
            """,
            {"rows": b},
        )

    for b in _batches(_records(nco[["uri", "nco_family"]].dropna())):
        db.run_write(
            "UNWIND $rows AS row MATCH (o:Occupation {uri: row.uri}) SET o.ncoFamily = row.nco_family",
            {"rows": b},
        )

    counts = db.run_query(
        """
        CALL () { MATCH (j:Job) RETURN count(j) AS jobs }
        CALL () { MATCH (c:Company) RETURN count(c) AS companies }
        CALL () { MATCH (c:City) RETURN count(c) AS cities }
        CALL () { MATCH (s:State) RETURN count(s) AS states }
        CALL () { MATCH (t:Tag) RETURN count(t) AS tags }
        CALL () { MATCH (:Job)-[r:REQUIRES]->(:Skill) RETURN count(r) AS job_requires_skill }
        CALL () { MATCH (:Job)-[r:MAPS_TO]->() RETURN count(r) AS job_maps_to_occupation }
        CALL () { MATCH (:Job)-[r:TAGGED]->() RETURN count(r) AS job_tagged }
        RETURN jobs, companies, cities, states, tags, job_requires_skill, job_maps_to_occupation, job_tagged
        """
    )[0]
    return counts
