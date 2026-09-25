# ml_pipeline/india/geo.py

"""
Location parsing: Naukri location strings -> canonical city, state, tier.

  "Hybrid - Bengaluru"                -> [Bengaluru]            (work_mode=hybrid)
  "Kolkata(Chinar Park)"             -> [Kolkata]
  "Hyderabad, Chennai, Bengaluru"    -> [Hyderabad, Chennai, Bengaluru]
  "Remote"                           -> []                     (work_mode=remote)

City -> state comes from GeoNames (CC BY 4.0). Tier comes from the 7th CPC HRA
classification in data/reference/city_tiers.csv (X=1, Y=2, everything else=3).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz, process

# Metro regions are reported alongside tiers because the HRA list classifies
# satellite cities (Gurugram, Noida, Navi Mumbai, Thane ...) separately from the
# core metro. Membership follows the NCR / MMR planning regions.
METRO_REGIONS: dict[str, set[str]] = {
    "Delhi NCR": {"Delhi", "Gurugram", "Noida", "Greater Noida", "Ghaziabad", "Faridabad", "Sonipat", "Manesar"},
    "Mumbai MMR": {"Mumbai", "Thane", "Navi Mumbai", "Kalyan-Dombivli", "Vasai-Virar", "Bhiwandi", "Mira-Bhayandar", "Panvel"},
    "Pune": {"Pune", "Pimpri-Chinchwad"},
    "Bengaluru": {"Bengaluru"},
    "Hyderabad": {"Hyderabad"},
    "Chennai": {"Chennai"},
    "Kolkata": {"Kolkata", "Howrah"},
    "Ahmedabad": {"Ahmedabad", "Gandhinagar"},
}

REMOTE_WORDS = {"remote", "work from home", "wfh", "anywhere in india", "pan india", "india"}

# Locations outside India that appear in the postings; kept as "foreign", not dropped.
FOREIGN_WORDS = {
    "united arab emirates", "uae", "dubai", "abu dhabi", "sharjah", "saudi arabia", "riyadh", "jeddah",
    "qatar", "doha", "oman", "muscat", "kuwait", "bahrain", "singapore", "malaysia", "usa",
    "united states", "united states of america", "uk", "united kingdom", "london", "canada", "australia",
    "germany", "japan", "nepal", "sri lanka", "bangladesh", "philippines", "indonesia", "africa",
}

# State / district-level tokens -> GeoNames admin-1 name (city unknown).
STATE_ALIASES = {
    "dadra nagar haveli": "Dadra and Nagar Haveli and Daman and Diu",
    "dadra and nagar haveli": "Dadra and Nagar Haveli and Daman and Diu",
    "daman diu": "Dadra and Nagar Haveli and Daman and Diu",
    "daman and diu": "Dadra and Nagar Haveli and Daman and Diu",
    "silvassa": "Dadra and Nagar Haveli and Daman and Diu",
    "north goa": "Goa",
    "south goa": "Goa",
    "gautam buddha nagar": "Uttar Pradesh",
    "orissa": "Odisha",
    "pondicherry": "Puducherry",
    "j k": "Jammu and Kashmir",
    "jammu kashmir": "Jammu and Kashmir",
    "andaman nicobar": "Andaman and Nicobar",
}
_PAREN = re.compile(r"\([^)]*\)")
_SPLIT = re.compile(r"[,/;|]| and ")
_HYBRID = re.compile(r"^\s*hybrid\s*[-:]\s*", re.I)
_WS = re.compile(r"\s+")


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return _WS.sub(" ", re.sub(r"[^a-z0-9 \-]", " ", s.lower())).strip()


@dataclass
class ParsedLocation:
    tokens: list[str]
    work_mode: str  # onsite | hybrid | remote


def parse_location(raw: object) -> ParsedLocation:
    """Split a Naukri location string into city tokens and a work mode."""
    s = "" if raw is None or (isinstance(raw, float) and pd.isna(raw)) else str(raw)
    mode = "onsite"
    tokens: list[str] = []
    for part in _SPLIT.split(s):
        part = part.strip()
        if not part:
            continue
        if _HYBRID.match(part):
            mode = "hybrid"
            part = _HYBRID.sub("", part)
        part = _PAREN.sub(" ", part).strip(" -")
        n = _norm(part)
        if not n:
            continue
        if n in REMOTE_WORDS or n.startswith("remote"):
            if mode == "onsite":
                mode = "remote"
            continue
        tokens.append(part)
    if not tokens and mode == "onsite" and _norm(s) in REMOTE_WORDS:
        mode = "remote"
    return ParsedLocation(tokens=tokens, work_mode=mode)


class Gazetteer:
    """Canonical Indian city resolver built from GeoNames + curated aliases + tier list."""

    def __init__(self, geonames_txt: Path, admin1_txt: Path, tiers_csv: Path, aliases_csv: Path):
        alias_df = self._read_ref(aliases_csv)
        self.aliases = {_norm(r.alias): r.city for r in alias_df.itertuples(index=False)}
        # Where the canonical name isn't a GeoNames place (e.g. "Vasai-Virar"), resolve via `lookup`.
        self.alias_lookup = {_norm(r.alias): (r.lookup or r.city) for r in alias_df.itertuples(index=False)}

        admin = pd.read_csv(admin1_txt, sep="\t", header=None, names=["code", "name", "ascii", "gid"], dtype=str)
        admin = admin[admin["code"].str.startswith("IN.")]
        state_by_code = dict(zip(admin["code"].str[3:], admin["name"], strict=True))

        cols = ["gid", "name", "ascii", "alt", "lat", "lon", "fclass", "fcode", "cc", "cc2", "admin1",
                "admin2", "admin3", "admin4", "population", "elev", "dem", "tz", "mod"]
        gn = pd.read_csv(geonames_txt, sep="\t", header=None, names=cols, dtype=str,
                         usecols=["name", "ascii", "alt", "lat", "lon", "fclass", "fcode", "admin1", "population"],
                         quoting=3, keep_default_na=False)
        gn = gn[gn["fclass"].eq("P")].copy()
        gn["population"] = pd.to_numeric(gn["population"], errors="coerce").fillna(0).astype(int)
        gn["state"] = gn["admin1"].map(state_by_code)
        gn = gn[gn["state"].notna()]

        # name -> (canonical name, state, population, lat, lon); most populous wins on clashes.
        index: dict[str, tuple[str, str, int, float, float]] = {}
        gn = gn.sort_values("population", ascending=False)
        for row in gn.itertuples(index=False):
            entry = (row.ascii or row.name, row.state, int(row.population), float(row.lat), float(row.lon))
            names = {row.name, row.ascii}
            if row.population >= 50_000 and row.alt:
                names |= {a for a in row.alt.split(",") if a and a.isascii()}
            for n in names:
                key = _norm(n)
                if key and key not in index:
                    index[key] = entry
        self.index = index
        self.states = {_norm(n): n for n in state_by_code.values()}
        self.states.update({_norm(k.replace("&", " ")): v for k, v in STATE_ALIASES.items()})
        # Fuzzy matching only against reasonably large places, to avoid silly matches.
        self._fuzzy_keys = [k for k, v in index.items() if v[2] >= 20_000]

        tiers = self._read_ref(tiers_csv)
        self.tier_by_city: dict[str, tuple[int, str]] = {}
        for row in tiers.itertuples(index=False):
            self.tier_by_city[self.canonical_name(row.city)] = (int(row.tier), row.state or "")

    @staticmethod
    def _read_ref(path: Path) -> pd.DataFrame:
        return pd.read_csv(path, comment="#", dtype=str, keep_default_na=False)

    def canonical_name(self, name: str) -> str:
        return self.aliases.get(_norm(name), name.strip())

    def resolve(self, token: str) -> dict | None:
        """
        token -> {city, state, population, lat, lon, matched_by} or None.
        matched_by is exact | alias | fuzzy | state_only | foreign.
        """
        key = _norm(token.replace("&", " "))
        if not key:
            return None
        if key in FOREIGN_WORDS:
            return {"city": None, "state": None, "population": 0, "lat": None, "lon": None, "matched_by": "foreign"}

        method = "exact"
        if key in self.aliases:
            method = "alias"
            hit = self.index.get(_norm(self.alias_lookup[key])) or self.index.get(_norm(self.aliases[key]))
        else:
            hit = self.index.get(key)
        if hit is None and key in self.states:
            return {"city": None, "state": self.states[key], "population": 0, "lat": None, "lon": None,
                    "matched_by": "state_only"}
        if hit is None:
            match = process.extractOne(key, self._fuzzy_keys, scorer=fuzz.ratio, score_cutoff=92)
            if match is None:
                return None
            hit, method = self.index[match[0]], "fuzzy"
        name = self.aliases[key] if key in self.aliases else self.canonical_name(hit[0])
        return {"city": name, "state": hit[1], "population": hit[2], "lat": hit[3], "lon": hit[4], "matched_by": method}

    def tier(self, city: str, state: str | None = None) -> int:
        """HRA-based tier; a state-qualified entry applies only in that state."""
        tier, tier_state = self.tier_by_city.get(self.canonical_name(city), (3, ""))
        if tier_state and state and tier_state != state:
            return 3
        return tier


def metro_region(city: str) -> str | None:
    for region, members in METRO_REGIONS.items():
        if city in members:
            return region
    return None


def geocode_jobs(df: pd.DataFrame, gaz: Gazetteer) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """
    Returns (jobs with work_mode/primary city fields, job-city long table, stats).
    A job listing several cities gets one row per resolved city in the long table.
    """
    cache: dict[str, dict | None] = {}
    rows = []
    modes = []
    unresolved: dict[str, int] = {}
    for job_id, raw in zip(df["jobId"], df["location"], strict=True):
        parsed = parse_location(raw)
        modes.append(parsed.work_mode)
        for rank, tok in enumerate(parsed.tokens):
            if tok not in cache:
                cache[tok] = gaz.resolve(tok)
            hit = cache[tok]
            if hit is None:
                unresolved[tok] = unresolved.get(tok, 0) + 1
                continue
            city = hit["city"]
            rows.append({"jobId": job_id, "rank": rank, **hit,
                         "tier": gaz.tier(city, hit["state"]) if city else None,
                         "metro_region": metro_region(city) if city else None})
    job_city = pd.DataFrame(rows).drop_duplicates(["jobId", "city", "state", "matched_by"]) if rows else pd.DataFrame(
        columns=["jobId", "rank", "city", "state", "population", "lat", "lon", "matched_by", "tier", "metro_region"])

    out = df.copy()
    out["work_mode"] = modes
    out["has_foreign_location"] = out["jobId"].isin(job_city.loc[job_city["matched_by"] == "foreign", "jobId"])
    # The job-city table keeps only Indian places; state-only rows keep state, no city.
    job_city = job_city[job_city["matched_by"] != "foreign"]
    # Primary place = first listed *city*; a state-only token is used only if no city resolved.
    primary = (
        job_city.assign(_no_city=job_city["city"].isna())
        .sort_values(["_no_city", "rank"])
        .drop_duplicates("jobId")
        .set_index("jobId")
    )
    for col in ["city", "state", "tier", "metro_region"]:
        out[f"primary_{col}"] = out["jobId"].map(primary[col]) if len(primary) else None
    out["n_cities"] = out["jobId"].map(job_city[job_city["city"].notna()].groupby("jobId").size()).fillna(0).astype(int)
    out["n_places"] = out["jobId"].map(job_city.groupby("jobId").size()).fillna(0).astype(int)

    has_place = out["n_places"] > 0
    has_city = out["primary_city"].notna()
    stats = {
        "jobs": len(out),
        "jobs_with_resolved_place": int(has_place.sum()),
        "jobs_with_resolved_city": int(has_city.sum()),
        "jobs_state_only": int((has_place & ~has_city).sum()),
        "jobs_foreign_only": int((out["has_foreign_location"] & ~has_place).sum()),
        "jobs_remote_only": int(((out["work_mode"] == "remote") & ~has_place).sum()),
        "jobs_unresolved": int((~has_place & (out["work_mode"] != "remote") & ~out["has_foreign_location"]).sum()),
        "city_resolution_rate_excl_remote": round(
            float(has_place.sum() / max(1, (has_place | (out["work_mode"] != "remote")).sum())), 4),
        "multi_city_jobs": int((out["n_cities"] > 1).sum()),
        "work_mode_counts": out["work_mode"].value_counts().to_dict(),
        "match_method_counts": job_city["matched_by"].value_counts().to_dict() if len(job_city) else {},
        "distinct_cities": int(job_city["city"].nunique()) if len(job_city) else 0,
        "distinct_states": int(job_city["state"].nunique()) if len(job_city) else 0,
        "top_unresolved_tokens": sorted(unresolved.items(), key=lambda kv: -kv[1])[:30],
        "jobs_by_primary_tier": out["primary_tier"].value_counts(dropna=False).to_dict(),
    }
    return out, job_city.reset_index(drop=True), stats
