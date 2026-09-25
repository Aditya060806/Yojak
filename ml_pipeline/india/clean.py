# ml_pipeline/india/clean.py

"""
Cleaning for the Naukri "Indian Job Market Dataset 2025".

Pure functions over DataFrames so each step is unit-tested and its row counts
can be reported. Nothing here touches the network or Neo4j.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

# --- constants --------------------------------------------------------------------

# Annual INR bounds for a plausible posted salary. Below ~Rs 50,000/yr (about
# Rs 4,200/month) the value is almost certainly a monthly figure or a typo; above
# Rs 5 crore it is almost certainly a data-entry error. Out-of-range values are
# flagged and treated as undisclosed rather than silently "fixed".
SALARY_MIN_PLAUSIBLE_INR = 50_000
SALARY_MAX_PLAUSIBLE_INR = 50_000_000

EXPERIENCE_BANDS = [
    ("0-1", 0, 1),
    ("1-3", 1, 3),
    ("3-6", 3, 6),
    ("6-10", 6, 10),
    ("10+", 10, 99),
]

_WS = re.compile(r"\s+")
_EDGE_PUNCT = re.compile(r"^[\s\-_.,;:/|]+|[\s\-_.,;:/|]+$")
_NON_ALNUM = re.compile(r"[^0-9a-z+#]+")


@dataclass
class StepLog:
    """Row counts per cleaning step, for reports/data_quality.json."""

    steps: list[dict] = field(default_factory=list)

    def add(self, step: str, rows: int, note: str = "", **extra) -> None:
        self.steps.append({"step": step, "rows": int(rows), "note": note, **extra})


# --- text normalisation -------------------------------------------------------------

def normalize_tag(tag: str) -> str:
    """'  Python ' -> 'python'; keeps symbols that matter in tech (c++, c#, .net)."""
    t = _WS.sub(" ", str(tag).strip().lower())
    t = _EDGE_PUNCT.sub("", t) if not t.startswith(".") else t.rstrip(" -_,;:/|")
    return t


def split_tags(raw: object) -> list[str]:
    """Split the comma-separated tagsAndSkills field into unique normalised tags (order kept)."""
    if not isinstance(raw, str) or not raw.strip():
        return []
    seen: dict[str, None] = {}
    for part in raw.split(","):
        t = normalize_tag(part)
        if t and len(t) <= 80:
            seen.setdefault(t, None)
    return list(seen)


def normalize_title(title: object) -> str:
    return _WS.sub(" ", _NON_ALNUM.sub(" ", str(title).lower())).strip()


# --- dates ------------------------------------------------------------------------------

_DAYS = re.compile(r"^(\d+)\+?\s*days?\s+ago$")


def days_ago(value: object) -> float:
    """'4 Days Ago' -> 4, 'Few Hours Ago'/'Just Now'/'Today' -> 0, 'Starts ...' -> NaN."""
    s = str(value).strip().lower()
    if s in {"just now", "today", "few hours ago"} or s.endswith("hours ago") or s.endswith("hour ago"):
        return 0.0
    m = _DAYS.match(s)
    return float(m.group(1)) if m else np.nan


def posting_date_from_job_id(job_id: pd.Series) -> pd.Series:
    """
    Naukri job IDs start with the posting date as DDMMYY (e.g. 270925008041 -> 2025-09-27).
    This is an *inferred* encoding; `temporal_evidence` measures how well it agrees
    with the relative "N Days Ago" field before we rely on it.
    """
    return pd.to_datetime(job_id.astype(str).str[:6], format="%d%m%y", errors="coerce")


def temporal_evidence(df: pd.DataFrame) -> dict:
    """
    Test whether jobId dates are real posting dates.

    If they are, posting_date + days_ago should land on one common scrape date for
    most rows. Reports that date, the share of rows consistent with it, and the
    posting-date span, so the "can we forecast?" question is answered with data.
    """
    posted = posting_date_from_job_id(df["jobId"])
    ago = df["jobUploaded"].map(days_ago)
    implied = posted + pd.to_timedelta(ago, unit="D")
    usable = implied.notna()
    if not usable.any():
        return {"posting_dates_available": False, "reason": "jobId did not parse as DDMMYY"}
    scrape = implied[usable].mode().iloc[0]
    consistent = (implied[usable] - scrape).abs() <= pd.Timedelta(days=1)
    dated = posted.dropna()
    core = dated[dated >= scrape - pd.Timedelta(days=30)]
    weekday_counts = core.dt.day_name().value_counts().to_dict()
    share = float(consistent.mean())
    return {
        "posting_dates_available": share >= 0.8,
        "method": "jobId prefix parsed as DDMMYY, checked against 'N Days Ago' relative to one scrape date",
        "inferred_scrape_date": scrape.date().isoformat(),
        "rows_with_relative_age": int(usable.sum()),
        "share_consistent_within_1_day": round(share, 4),
        "jobid_parse_rate": round(float(posted.notna().mean()), 4),
        "posting_date_min": dated.min().date().isoformat(),
        "posting_date_max": dated.max().date().isoformat(),
        "share_posted_within_14_days_of_scrape": round(
            float((dated >= scrape - pd.Timedelta(days=14)).mean()), 4
        ),
        "weekday_counts_last_30_days": weekday_counts,
        "forecasting_supported": False,
        "forecasting_note": (
            "Posting dates are real but almost all fall within ~2 weeks of the scrape. "
            "That supports a time-based hold-out test and a with/without-time ablation, "
            "but not demand forecasting or 'emerging skill' trend claims."
        ),
    }


# --- salary -------------------------------------------------------------------------------

def clean_salary(
    df: pd.DataFrame, usd_policy: str = "exclude", usd_inr_rate: float | None = None
) -> tuple[pd.DataFrame, dict]:
    """
    Numeric annual INR min/max salary with explicit flags.

    0 -> missing (Naukri uses 0 for 'Not disclosed'); min>max swapped; implausible
    values flagged and set missing.

    USD rows: in this dataset every USD-labelled salary is an Indian role whose
    figures are rupee amounts (e.g. a Nagpur trainee at "10,000-15,000 USD PA"),
    so converting them would invent salaries. The default policy is "exclude"
    (flag `currency_suspect`, treat as undisclosed). "convert" multiplies by
    `usd_inr_rate` for datasets where the label can be trusted.
    """
    if usd_policy not in {"exclude", "convert"}:
        raise ValueError("usd_policy must be 'exclude' or 'convert'")
    if usd_policy == "convert" and not usd_inr_rate:
        raise ValueError("usd_inr_rate is required when usd_policy='convert'")
    out = df.copy()
    lo = pd.to_numeric(out["minimumSalary"], errors="coerce")
    hi = pd.to_numeric(out["maximumSalary"], errors="coerce")
    lo = lo.where(lo > 0)
    hi = hi.where(hi > 0)
    # One side only: use it for both.
    lo = lo.fillna(hi)
    hi = hi.fillna(lo)

    is_usd = out["currency"].astype(str).str.upper().eq("USD")
    usd_with_salary = is_usd & lo.notna()
    if usd_policy == "convert":
        lo = lo.where(~is_usd, lo * usd_inr_rate)
        hi = hi.where(~is_usd, hi * usd_inr_rate)
    else:
        lo = lo.where(~is_usd)
        hi = hi.where(~is_usd)

    swapped = lo > hi
    lo, hi = lo.where(~swapped, hi), hi.where(~swapped, lo)

    implausible = lo.notna() & ((lo < SALARY_MIN_PLAUSIBLE_INR) | (hi > SALARY_MAX_PLAUSIBLE_INR))
    out["salary_min_inr"] = lo.where(~implausible)
    out["salary_max_inr"] = hi.where(~implausible)
    out["salary_mid_inr"] = (out["salary_min_inr"] + out["salary_max_inr"]) / 2
    out["salary_disclosed"] = out["salary_mid_inr"].notna()
    out["salary_flag"] = np.select(
        [implausible, usd_with_salary & (usd_policy == "exclude"), usd_with_salary, out["salary_disclosed"]],
        ["implausible", "currency_suspect", "converted_from_usd", "ok"],
        default="not_disclosed",
    )
    stats = {
        "usd_rows": int(is_usd.sum()),
        "usd_rows_with_salary": int(usd_with_salary.sum()),
        "usd_policy": usd_policy,
        "usd_inr_rate": usd_inr_rate,
        "swapped_min_max": int(swapped.sum()),
        "implausible_salary_rows": int(implausible.sum()),
        "disclosed_rows": int(out["salary_disclosed"].sum()),
        "disclosed_share": round(float(out["salary_disclosed"].mean()), 4),
        "plausible_range_inr": [SALARY_MIN_PLAUSIBLE_INR, SALARY_MAX_PLAUSIBLE_INR],
    }
    return out, stats


# --- experience -----------------------------------------------------------------------------

def experience_band(min_years: float) -> str | None:
    if pd.isna(min_years):
        return None
    for name, lo, hi in EXPERIENCE_BANDS:
        if lo <= min_years < hi or (name == "0-1" and min_years <= 1):
            return name
    return "10+"


def clean_experience(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    lo = pd.to_numeric(out["minimumExperience"], errors="coerce")
    hi = pd.to_numeric(out["maximumExperience"], errors="coerce")
    swapped = lo > hi
    lo, hi = lo.where(~swapped, hi), hi.where(~swapped, lo)
    out["exp_min"] = lo
    out["exp_max"] = hi
    out["exp_band"] = lo.map(experience_band)
    return out


# --- dedupe --------------------------------------------------------------------------------

def dedupe(df: pd.DataFrame, log: StepLog) -> pd.DataFrame:
    """
    1) Drop exact duplicate jobIds.
    2) Assign `dup_group_id` to near-duplicates: same company + normalised title +
       same tag set. They stay as separate rows (often the same role in different
       cities) but are always split together, so train/test never share a posting.
    """
    out = df.drop_duplicates(subset=["jobId"], keep="first").copy()
    log.add("drop_duplicate_jobId", len(out), f"removed {len(df) - len(out)} repeated jobIds")

    key = (
        out["companyName"].astype(str).str.lower().str.strip()
        + "|" + out["title"].map(normalize_title)
        + "|" + out["tags"].map(lambda ts: ",".join(sorted(ts)))
    )
    out["dup_group_id"] = key.map(lambda k: hashlib.sha1(k.encode("utf-8")).hexdigest()[:16])
    n_groups = out["dup_group_id"].nunique()
    log.add(
        "near_duplicate_groups",
        len(out),
        f"{len(out) - n_groups} rows share a (company, title, tag-set) group with another row",
        groups=n_groups,
    )
    return out


def clean_postings(
    raw: pd.DataFrame, usd_policy: str = "exclude", usd_inr_rate: float | None = None
) -> tuple[pd.DataFrame, StepLog, dict]:
    """Run every cleaning step; return jobs, step log and salary stats."""
    log = StepLog()
    log.add("raw", len(raw))
    df = raw.copy()
    df["jobId"] = df["jobId"].astype(str).str.strip()
    df["title"] = df["title"].astype(str).str.strip()
    df["companyName"] = df["companyName"].fillna("").astype(str).str.strip()
    df["tags"] = df["tagsAndSkills"].map(split_tags)

    df = dedupe(df, log)

    no_title = df["title"].eq("") | df["title"].str.lower().eq("nan")
    df = df[~no_title]
    log.add("drop_missing_title", len(df), f"removed {int(no_title.sum())} rows without a title")

    df["posted_date"] = posting_date_from_job_id(df["jobId"])
    df["days_ago"] = df["jobUploaded"].map(days_ago)
    df["future_start"] = df["jobUploaded"].astype(str).str.lower().str.startswith("starts")

    df = clean_experience(df)
    df, salary_stats = clean_salary(df, usd_policy=usd_policy, usd_inr_rate=usd_inr_rate)

    rating = pd.to_numeric(df["AggregateRating"], errors="coerce")
    df["company_rating"] = rating.where((rating >= 0) & (rating <= 5))
    df["company_reviews"] = pd.to_numeric(df["ReviewsCount"], errors="coerce")

    df["n_tags"] = df["tags"].map(len)
    log.add("jobs_with_tags", int((df["n_tags"] > 0).sum()), "jobs with at least one skill tag")
    return df.reset_index(drop=True), log, salary_stats
