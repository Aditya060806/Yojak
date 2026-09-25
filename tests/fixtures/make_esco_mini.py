"""
Build tests/fixtures/esco_mini/: a small, internally consistent slice of ESCO v1.2
(the same 17 files the pipeline expects) for integration tests and CI.

ESCO is CC BY 4.0 (see NOTICE). Re-run after an ESCO upgrade:
    python tests/fixtures/make_esco_mini.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

SRC = Path(__file__).resolve().parents[2] / "data" / "raw" / "esco"
DST = Path(__file__).resolve().parent / "esco_mini"

# A few ICT occupations plus neighbours from other ISCO major groups.
OCCUPATION_LABELS = [
    "data analyst", "data scientist", "software developer", "database administrator",
    "ICT business analyst", "web developer", "accountant", "nurse responsible for general care",
    "civil engineer", "sales assistant", "primary school teacher", "electrician",
]


def read(name: str) -> pd.DataFrame:
    return pd.read_csv(SRC / name, dtype=str, keep_default_na=False, encoding="utf-8-sig")


def write(df: pd.DataFrame, name: str) -> None:
    df.to_csv(DST / name, index=False, encoding="utf-8")


def main() -> None:
    DST.mkdir(parents=True, exist_ok=True)
    occ = read("occupations_en.csv")
    occ = occ[occ["preferredLabel"].isin(OCCUPATION_LABELS)]
    missing = set(OCCUPATION_LABELS) - set(occ["preferredLabel"])
    if missing:
        raise SystemExit(f"Labels not found in ESCO: {missing}")
    occ_uris = set(occ["conceptUri"])

    rel = read("occupationSkillRelations_en.csv")
    rel = rel[rel["occupationUri"].isin(occ_uris)]
    # Keep every essential link and up to 15 optional links per occupation.
    rel = pd.concat(
        [rel[rel["relationType"] == "essential"],
         rel[rel["relationType"] == "optional"].groupby("occupationUri").head(15)]
    )
    skill_uris = set(rel["skillUri"])

    skills = read("skills_en.csv")
    skills = skills[skills["conceptUri"].isin(skill_uris)]

    ssr = read("skillSkillRelations_en.csv")
    ssr = ssr[ssr["originalSkillUri"].isin(skill_uris) & ssr["relatedSkillUri"].isin(skill_uris)]

    bsp = read("broaderRelationsSkillPillar_en.csv")
    bsp_skills = bsp[bsp["conceptUri"].isin(skill_uris)]
    group_uris = set(bsp_skills["broaderUri"])
    # Walk up the group hierarchy.
    frontier = set(group_uris)
    while frontier:
        parents = bsp[bsp["conceptUri"].isin(frontier)]
        frontier = set(parents["broaderUri"]) - group_uris
        group_uris |= frontier
    bsp = bsp[bsp["conceptUri"].isin(skill_uris | group_uris)]

    groups = read("skillGroups_en.csv")
    groups = groups[groups["conceptUri"].isin(group_uris)]

    hier = read("skillsHierarchy_en.csv")
    hier = hier[hier["Level 1 URI"].isin(group_uris) | hier["Level 2 URI"].isin(group_uris)]

    codes = set(occ["iscoGroup"])
    prefixes = {c[:n] for c in codes for n in range(1, 5)}
    isco = read("ISCOGroups_en.csv")
    isco = isco[isco["code"].isin(prefixes)]
    isco_uris = set(isco["conceptUri"])

    bop = read("broaderRelationsOccPillar_en.csv")
    bop = bop[bop["conceptUri"].isin(occ_uris | isco_uris) & bop["broaderUri"].isin(occ_uris | isco_uris)]

    schemes = read("conceptSchemes_en.csv")
    schemes["hasTopConcept"] = ""  # the real column is ~1 MB of URIs

    write(occ, "occupations_en.csv")
    write(read("researchOccupationsCollection_en.csv").pipe(lambda d: d[d["conceptUri"].isin(occ_uris)]),
          "researchOccupationsCollection_en.csv")
    write(skills, "skills_en.csv")
    write(rel, "occupationSkillRelations_en.csv")
    write(ssr, "skillSkillRelations_en.csv")
    write(hier, "skillsHierarchy_en.csv")
    write(bsp, "broaderRelationsSkillPillar_en.csv")
    write(groups, "skillGroups_en.csv")
    write(isco, "ISCOGroups_en.csv")
    write(bop, "broaderRelationsOccPillar_en.csv")
    write(schemes, "conceptSchemes_en.csv")
    for name in ["digitalSkillsCollection_en.csv", "greenSkillsCollection_en.csv", "digCompSkillsCollection_en.csv",
                 "researchSkillsCollection_en.csv", "transversalSkillsCollection_en.csv",
                 "languageSkillsCollection_en.csv"]:
        df = read(name)
        write(df[df["conceptUri"].isin(skill_uris)], name)

    print(f"esco_mini: {len(occ)} occupations, {len(skills)} skills, {len(rel)} relations, "
          f"{len(groups)} skill groups, {len(isco)} ISCO groups")


if __name__ == "__main__":
    main()
