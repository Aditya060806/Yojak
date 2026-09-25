# ml_pipeline/supply/workforce.py

"""
Workforce-planner analytics: where skill demand is, by state and city tier, and a
coarse shortage indicator against graduate supply.

Skill families = ISCED-F 2013 broad fields of education. ESCO's knowledge pillar is
organised by ISCED-F, so each ESCO knowledge concept maps to one broad field by
walking up broaderRelationsSkillPillar. A posting's field is the most common field
among its linked knowledge skills ("unassigned" when it has none).

Shortage index (a PROXY, shown with its formula everywhere):
    shortage(field, state) = [postings(field, state) / postings(field, India)]
                             / [graduates(state) / graduates(India)]
  > 1: the state carries more of the national demand for this field than its share of
  graduates (AISHE 2021-22 out-turn) would suggest. Youth unemployment (PLFS 2023-24)
  is reported alongside as labour-market slack. Limits: graduates are not split by
  field (the AISHE discipline table is not machine-readable), graduates move between
  states, and postings are Naukri's formal-sector sample.

    python -m ml_pipeline.supply.workforce  ->  artifacts/workforce/*.parquet, reports/workforce_summary.json
"""

from __future__ import annotations

import sys
from collections import Counter

import numpy as np
import pandas as pd

from app.core.settings import get_settings
from ml_pipeline.common import provenance, write_report

UNASSIGNED = "unassigned"


def skill_fields(esco_dir) -> dict[str, str]:
    """ESCO skill URI -> ISCED-F broad field label (knowledge concepts only)."""
    h = pd.read_csv(esco_dir / "skillsHierarchy_en.csv", dtype=str, keep_default_na=False)
    k1 = h[(h["Level 0 code"] == "K") & (h["Level 1 URI"] != "")][["Level 1 URI", "Level 1 preferred term"]]
    field_of_group = dict(zip(k1["Level 1 URI"], k1["Level 1 preferred term"], strict=False))
    broader = pd.read_csv(esco_dir / "broaderRelationsSkillPillar_en.csv", dtype=str, keep_default_na=False,
                          usecols=["conceptUri", "broaderUri"])
    parents: dict[str, list[str]] = {}
    for c, b in zip(broader["conceptUri"], broader["broaderUri"], strict=True):
        parents.setdefault(c, []).append(b)
    skills = pd.read_csv(esco_dir / "skills_en.csv", dtype=str, keep_default_na=False,
                         usecols=["conceptUri", "skillType"])
    out = {}
    for uri in skills.loc[skills["skillType"] == "knowledge", "conceptUri"]:
        seen, frontier, found = set(), [uri], None
        while frontier and found is None:
            nxt = []
            for node in frontier:
                if node in field_of_group:
                    found = field_of_group[node]
                    break
                for p in parents.get(node, []):
                    if p not in seen:
                        seen.add(p)
                        nxt.append(p)
            frontier = nxt
        if found and found != "field unknown":
            out[uri] = found
    return out


def posting_fields(jobs: pd.DataFrame, fields: dict[str, str]) -> pd.Series:
    def one(uris):
        c = Counter(fields[u] for u in (uris if uris is not None else []) if u in fields)
        return c.most_common(1)[0][0] if c else UNASSIGNED
    return jobs["skill_uris"].map(one)


def load_supply() -> pd.DataFrame:
    ref = get_settings().reference_data_dir
    a = pd.read_csv(ref / "aishe_2021_22_state_outturn.csv", comment="#")
    p = pd.read_csv(ref / "plfs_2023_24_youth_ur.csv", comment="#")
    return a[["state", "outturn_total"]].merge(p[["state", "youth_ur_pct"]], on="state", how="outer")


def build() -> dict:
    s = get_settings()
    from ml_pipeline.upskilling.market import load_market

    market = load_market()
    jobs = market.jobs.copy()
    fields = skill_fields(s.esco_data_dir)
    jobs["field"] = posting_fields(jobs, fields)
    jobs["p10"], jobs["p50"], jobs["p90"] = market.p10, market.p50, market.p90
    jobs["state"] = jobs["primary_state"]
    jobs["tier"] = jobs["primary_tier"]

    supply = load_supply()
    grads = supply.set_index("state")["outturn_total"].astype(float)
    grad_share = grads / grads.sum(skipna=True)

    by_state_field = jobs.dropna(subset=["state"]).groupby(["state", "field"]).size().rename("postings").reset_index()
    field_total = by_state_field.groupby("field")["postings"].transform("sum")
    by_state_field["demand_share_of_field"] = by_state_field["postings"] / field_total
    by_state_field["graduate_share"] = by_state_field["state"].map(grad_share)
    by_state_field["shortage_index"] = by_state_field["demand_share_of_field"] / by_state_field["graduate_share"]
    by_state_field.loc[by_state_field["field"] == UNASSIGNED, "shortage_index"] = np.nan

    state = jobs.dropna(subset=["state"]).groupby("state").agg(postings=("jobId", "size"),
                                                               salary_p50_median=("p50", "median"))
    state["demand_share"] = state["postings"] / state["postings"].sum()
    state = state.join(supply.set_index("state"), how="left")
    state["graduate_share"] = state.index.map(grad_share)
    state["postings_per_1000_graduates"] = state["postings"] / state["outturn_total"] * 1000
    state["shortage_index"] = state["demand_share"] / state["graduate_share"]

    tier = jobs.groupby(jobs["tier"].fillna(0).astype(int)).agg(
        postings=("jobId", "size"), p10_median=("p10", "median"), p50_median=("p50", "median"),
        p90_median=("p90", "median"), disclosed_share=("salary_disclosed", "mean"))
    tier.index = tier.index.map(lambda t: {0: "unknown", 1: "Tier 1", 2: "Tier 2", 3: "Tier 3"}[t])

    exploded = jobs[["state", "tier", "skill_uris"]].explode("skill_uris").dropna()
    top_by_state = (exploded.groupby(["state", "skill_uris"]).size().rename("postings").reset_index()
                    .sort_values(["state", "postings"], ascending=[True, False]).groupby("state").head(15))
    top_by_tier = (exploded.dropna(subset=["tier"]).groupby(["tier", "skill_uris"]).size().rename("postings")
                   .reset_index().sort_values(["tier", "postings"], ascending=[True, False]).groupby("tier").head(15))
    labels = pd.read_csv(s.esco_data_dir / "skills_en.csv", dtype=str, keep_default_na=False,
                         usecols=["conceptUri", "preferredLabel"]).drop_duplicates("conceptUri").set_index(
        "conceptUri")["preferredLabel"]
    for t in (top_by_state, top_by_tier):
        t["label"] = t["skill_uris"].map(labels)

    out = s.artifacts_dir / "workforce"
    out.mkdir(parents=True, exist_ok=True)
    by_state_field.to_parquet(out / "state_field.parquet", index=False)
    state.reset_index().to_parquet(out / "state.parquet", index=False)
    tier.reset_index().rename(columns={"tier": "tier_label"}).to_parquet(out / "tier.parquet", index=False)
    top_by_state.to_parquet(out / "top_skills_state.parquet", index=False)
    top_by_tier.to_parquet(out / "top_skills_tier.parquet", index=False)
    jobs[["jobId", "field"]].to_parquet(out / "job_field.parquet", index=False)

    body = {
        "skill_families": "ISCED-F 2013 broad fields via the ESCO knowledge pillar",
        "postings_by_field": jobs["field"].value_counts().to_dict(),
        "share_postings_with_field": round(float((jobs["field"] != UNASSIGNED).mean()), 4),
        "states_with_graduate_supply": int(grads.notna().sum()),
        "states_missing_supply": grads[grads.isna()].index.tolist(),
        "shortage_index_formula": ("[postings(field, state) / postings(field, India)] / "
                                   "[graduates(state) / graduates(India)]"),
        "caveats": [
            "Graduate supply is not split by field: AISHE's discipline table is not machine-readable, so only state totals are used.",
            "Graduates migrate between states; the index describes where demand is relative to where graduates are produced.",
            "Demand is Naukri postings (formal, urban-skewed), not all vacancies.",
            "West Bengal's AISHE row is unreadable in the source PDF and is excluded until checked by hand.",
        ],
        "top_states_by_shortage_index": state.dropna(subset=["shortage_index"]).sort_values(
            "shortage_index", ascending=False)["shortage_index"].round(2).head(10).to_dict(),
        "tiers": tier.round({"p10_median": 0, "p50_median": 0, "p90_median": 0, "disclosed_share": 4}).to_dict(orient="index"),
    }
    prov = provenance("ml_pipeline/supply/workforce.py", inputs=[
        s.reference_data_dir / "aishe_2021_22_state_outturn.csv", s.reference_data_dir / "plfs_2023_24_youth_ur.csv"])
    write_report("workforce_summary", body, prov)
    return body


def main() -> int:
    body = build()
    print({k: body[k] for k in ("share_postings_with_field", "states_with_graduate_supply", "top_states_by_shortage_index")})
    return 0


if __name__ == "__main__":
    sys.exit(main())
