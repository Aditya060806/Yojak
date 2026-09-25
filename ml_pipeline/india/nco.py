# ml_pipeline/india/nco.py

"""
India NCO-2015 codes for ESCO occupations, at the 4-digit Family level only.

Basis (cited in reports/data_quality.json):
  NCVET, "Report on Mapping of Qualifications with NCO Codes" (22 Aug 2023),
  section 2.2.8: NCO-2015 is an 8-digit structure "mapped and aligned to ISCO-08
  with an addition of 2 digits"; "the first four digits will represent the Family
  (Unit Group in ISCO)". NCO-2015 has 9 divisions, i.e. no counterpart to ISCO
  major group 0 (armed forces).

So an ESCO occupation's ISCO-08 unit-group code is its NCO-2015 Family code,
except for division 0. The 8-digit NCO occupation level is NOT mapped: that would
need a title-level crosswalk we cannot validate.

If data/reference/nco2015_families.csv (columns: family_code, family_title) is
present, e.g. transcribed from NCO-2015 Vol I, codes are also checked against it
and family titles are attached.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

NCO_BASIS = (
    "NCVET (2023) Report on Mapping of Qualifications with NCO Codes, s.2.2.8: "
    "NCO-2015 first four digits = ISCO-08 unit group (Family); NCO has no division 0."
)


def nco_family_for_isco(isco_code: object) -> str | None:
    """'2511' -> '2511'; armed forces ('0xxx'), malformed or missing -> None."""
    code = str(isco_code or "").strip()
    if len(code) != 4 or not code.isdigit() or code.startswith("0"):
        return None
    return code


def map_occupations(occupations: pd.DataFrame, families_csv: Path | None = None) -> tuple[pd.DataFrame, dict]:
    """
    occupations: columns uri, iscoGroup. Returns (uri, isco_code, nco_family,
    nco_family_title, nco_validated) and summary stats.
    """
    out = occupations[["uri", "iscoGroup"]].rename(columns={"iscoGroup": "isco_code"}).copy()
    out["nco_family"] = out["isco_code"].map(nco_family_for_isco)
    validated = False
    titles: dict[str, str] = {}
    if families_csv is not None and families_csv.exists():
        fam = pd.read_csv(families_csv, dtype=str, comment="#")
        titles = dict(zip(fam["family_code"].str.strip(), fam["family_title"].str.strip(), strict=True))
        out["nco_family"] = out["nco_family"].astype(object).where(out["nco_family"].isin(titles), None)
        validated = True
    out["nco_family_title"] = out["nco_family"].map(titles) if titles else None
    out["nco_validated"] = validated
    stats = {
        "basis": NCO_BASIS,
        "level": "4-digit Family only (8-digit occupations not mapped)",
        "occupations": len(out),
        "with_nco_family": int(out["nco_family"].notna().sum()),
        "excluded_armed_forces": int(out["isco_code"].astype(str).str.startswith("0").sum()),
        "validated_against_nco_vol1_list": validated,
        "distinct_families": int(out["nco_family"].nunique()),
    }
    return out, stats
