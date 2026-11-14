"""Auditable source preparation and label-independent connected-group partitions."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = ROOT / "SAS Data Problem Statement"
PRIVATE = ROOT / "private_sas"
BANDS = ["0to3", "3to6", "6to10", "10to15", "15to25", "25to50"]
BOUNDS = np.array([[0, 3], [3, 6], [6, 10], [10, 15], [15, 25], [25, 50]], dtype=float)
FILES = {"analytics": "Analytics Jobs.csv", "company": "DataScience Jobs.csv",
         "jds": "JDS Skill Traits.xlsx", "sds": "SDS Personality Traits.xlsx"}
ALIASES = {"machine learning": "machine learning", "ml": "machine learning",
           "python programming": "python", "ms excel": "excel", "microsoft excel": "excel",
           "powerbi": "power bi", "statistics": "statistics", "statistical modeling": "statistical modelling"}
ROLE_RULES = [("Data architect", r"data\s*architect"), ("Data engineer", r"data\s*engineer|etl|big\s*data"),
              ("Data scientist", r"data\s*scientist|machine\s*learning|\bml\s*engineer"),
              ("Business analyst", r"business\s*analyst"), ("Data analyst", r"data\s*analyst|analytics|business intelligence|\bbi\b"),
              ("Software", r"developer|software|programmer"), ("Operations", r"operations|data entry|back office")]


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def normalize(value: object) -> str:
    return re.sub(r"\s+", " ", str(value).strip().lower()) if pd.notna(value) else ""


def role_family(title: str) -> str:
    return next((label for label, pattern in ROLE_RULES if re.search(pattern, normalize(title))), "Other")


def skills_of(value: object, conservative: bool = True) -> list[str]:
    raw = normalize(value)
    truncated = raw.endswith("...")
    raw = raw.removesuffix("...")
    tokens = re.split(r"[,;|]", raw)
    # Ellipses do not tell us whether the final token is whole. Preserve it in a sensitivity view.
    if truncated and conservative:
        tokens = tokens[:-1]
    return sorted({ALIASES.get(t.strip(), t.strip()) for t in tokens if t.strip() and t.strip() != "..."})


def connected_groups(frame: pd.DataFrame, keys: list[list[str]]) -> pd.Series:
    """Transitive closure prevents shared IDs/profiles from crossing partitions."""
    parent = list(range(len(frame)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for columns in keys:
        seen = {}
        for i, row in enumerate(frame[columns].itertuples(index=False, name=None)):
            key = tuple(normalize(v) for v in row)
            if not any(key):
                continue
            if key in seen:
                a, b = find(i), find(seen[key])
                parent[max(a, b)] = min(a, b)
            else:
                seen[key] = i
    members: dict[int, list[str]] = {}
    for i, key in enumerate(frame.row_key):
        members.setdefault(find(i), []).append(key)
    hashes = {k: digest("|".join(sorted(v)))[:20] for k, v in members.items()}
    return pd.Series([hashes[find(i)] for i in range(len(frame))], index=frame.index)


def partition(group: str) -> str:
    value = int(digest("sas-v3-seed31:" + group)[:8], 16) % 10000
    return "train" if value < 6000 else "validation" if value < 7500 else "calibration" if value < 8500 else "test"


def prepare_analytics(raw: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in raw if c != "s_no"]
    frame = raw.copy()
    frame["multiplicity"] = frame.groupby(cols, dropna=False)["s_no"].transform("size")
    frame = frame.drop_duplicates(cols).reset_index(drop=True)
    frame["row_key"] = ["analytics:" + digest(json.dumps([None if pd.isna(v) else str(v) for v in row]))[:24]
                        for row in frame[cols].itertuples(index=False, name=None)]
    frame["band"] = frame.salary.map({v: i for i, v in enumerate(BANDS)})
    if frame.band.isna().any():
        raise ValueError("Unrecognized salary band; inspect source before training")
    frame["skills"] = frame.key_skills.map(skills_of)
    frame["skills_permissive"] = frame.key_skills.map(lambda v: skills_of(v, False))
    frame["skills_truncated"] = frame.key_skills.fillna("").str.endswith("...")
    frame["description_missing"] = frame.job_description.isna()
    frame["description_truncated"] = frame.job_description.fillna("").str.endswith("...")
    parsed = frame.experience.astype(str).str.extract(r"^\s*(\d+)\s*-\s*(\d+)\s*yrs?\s*$")
    if parsed.isna().any().any():
        raise ValueError("Unparsed experience; inspect source before training")
    frame["exp_min"], frame["exp_max"] = parsed[0].astype(float), parsed[1].astype(float)
    if (frame.exp_min > frame.exp_max).any():
        raise ValueError("Reversed experience range")
    frame["exp_mid"] = (frame.exp_min + frame.exp_max) / 2
    frame["exp_width"] = frame.exp_max - frame.exp_min
    frame["role_family"] = frame.job_desig.map(role_family)
    frame["locations"] = frame.location.map(lambda v: sorted(set(filter(None, re.split(r"[,;/]", normalize(v))))))
    text = frame.key_skills.fillna("").str.lower() + " " + frame.job_desig.fillna("").str.lower()
    # No target, remote-work or part-time indicator is sufficient by itself.
    frame["quality_flag"] = text.str.contains(r"data entry|typing") & text.str.contains(r"earn|present job|freelanc|home based")
    frame["feature_signature"] = [digest("|".join(normalize(v) for v in row)) for row in
                                  frame[["job_desig", "key_skills", "location", "experience"]].itertuples(index=False, name=None)]
    frame["near_signature"] = [digest(re.sub(r"[^a-z0-9 ]", "", normalize(t)) + "|" + "|".join(s) + "|" + normalize(loc))
                               for t, s, loc in zip(frame.job_desig, frame.skills, frame.location, strict=True)]
    frame["group_id"] = connected_groups(frame, [["feature_signature"], ["near_signature"]])
    frame["split"] = frame.group_id.map(partition)
    return frame


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False, default=lambda x: x.item() if isinstance(x, np.generic) else str(x)), encoding="utf-8")


def write_role_review(frame: pd.DataFrame, path: Path) -> str:
    review = frame.sample(min(100, len(frame)), random_state=31)[["row_key", "job_desig", "role_family"]].copy()
    review["reviewed_family"] = ""
    if path.exists():
        existing = pd.read_csv(path, keep_default_na=False)
        required = {"row_key", "job_desig", "role_family", "reviewed_family"}
        if not required.issubset(existing.columns) or existing.row_key.duplicated().any():
            raise ValueError("Invalid existing role review; preserve and repair it before preparation")
        # Keep the frozen sample and reviewer-added columns, even after source changes.
        review = pd.concat([existing, review.loc[~review.row_key.isin(existing.row_key)]], ignore_index=True)
    review.to_csv(path, index=False)
    current = review.loc[review.row_key.isin(frame.row_key)]
    return "complete" if len(current) and current.reviewed_family.str.strip().ne("").all() else "pending"


def prepare(source: Path, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    reports = {}
    fingerprints = {}
    for name, filename in FILES.items():
        path = source / filename
        fingerprints[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        raw = pd.read_csv(path) if path.suffix == ".csv" else pd.read_excel(path)
        raw.columns = [re.sub(r"\s+", "_", c.strip()) for c in raw.columns]
        info = {"raw_rows": len(raw), "columns": list(raw), "missing": raw.isna().sum().to_dict()}
        if name == "analytics":
            frame = prepare_analytics(raw)
            counts = frame.groupby(["feature_signature", "band"]).size().unstack(fill_value=0)
            conflict = counts.gt(0).sum(axis=1) > 1
            info.update({"prepared_rows": len(frame), "exact_duplicates_removed": len(raw) - len(frame),
                         "conflicting_feature_groups": int(conflict.sum()),
                         "rows_in_conflicting_groups": int(counts.loc[conflict].sum().sum()),
                         "empirical_feature_agreement_bound": float(counts.max(axis=1).sum() / len(frame)),
                         "bound_scope": "In-sample identical-feature deterministic label agreement, not generalization ceiling",
                         "skills_truncated": int(frame.skills_truncated.sum()), "quality_flagged": int(frame.quality_flag.sum()),
                         "bands": frame.salary.value_counts().to_dict()})
            role_review_status = write_role_review(frame, out / "role_review.csv")
        else:
            frame = raw.copy()
            frame["row_key"] = [f"{name}:{i}" for i in range(len(frame))]
            if name == "company":
                frame["company_key"] = frame.company_name.map(normalize)
                frame["group_id"] = frame.company_key.map(lambda x: digest(x)[:20])
                for field in ["avg_salary", "min_salary", "max_salary"]:
                    frame[field + "_native"] = pd.to_numeric(frame[field].astype(str).str.replace("L", "", regex=False).str.strip(), errors="raise")
                frame["role_family"] = frame.job_title.map(role_family)
            else:
                features = [c for c in raw if c != "id"][:-1]
                frame["group_id"] = connected_groups(frame, [["id"], features])
                info["features"] = features
                info["target"] = raw.columns[-1]
            frame["split"] = frame.group_id.map(partition)
            info["prepared_rows"] = len(frame)
        info["groups"] = frame.group_id.nunique()
        info["partitions"] = frame.split.value_counts().to_dict()
        assert frame.groupby("group_id").split.nunique().max() == 1
        frame.to_parquet(out / f"{name}.parquet", index=False)
        frame[["row_key", "group_id", "split"]].to_csv(out / f"{name}_partitions.csv", index=False)
        reports[name] = info
    code_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    manifest = {"schema_version": 1, "source_hashes": fingerprints, "preparation_code_hash": code_hash,
                "source_version": digest(json.dumps(fingerprints, sort_keys=True))[:16],
                "unit_status": "unverified", "sas_execution": "not executed", "role_review": role_review_status,
                "audit": reports}
    write_json(out / "manifest.json", manifest)
    return manifest
