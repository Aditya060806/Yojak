"""Phase 1: Naukri cleaning, posting dates, salary rules, geography and tiers."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ml_pipeline.india.clean import (
    StepLog,
    clean_experience,
    clean_postings,
    clean_salary,
    days_ago,
    dedupe,
    experience_band,
    normalize_tag,
    posting_date_from_job_id,
    split_tags,
    temporal_evidence,
)
from ml_pipeline.india.geo import Gazetteer, geocode_jobs, metro_region, parse_location


def raw_rows(**cols) -> pd.DataFrame:
    n = max(len(v) for v in cols.values())
    base = {
        "title": ["Data Analyst"] * n, "jobId": [f"270925{i:06d}" for i in range(n)], "currency": ["INR"] * n,
        "jobUploaded": ["4 Days Ago"] * n, "companyName": ["Acme"] * n, "tagsAndSkills": ["Python,SQL"] * n,
        "experience": ["1-3 Yrs"] * n, "salary": ["Not disclosed"] * n, "location": ["Pune"] * n,
        "companyId": ["1"] * n, "ReviewsCount": [None] * n, "AggregateRating": ["3.9"] * n,
        "jobDescription": ["..."] * n, "minimumSalary": ["0"] * n, "maximumSalary": ["0"] * n,
        "minimumExperience": ["1"] * n, "maximumExperience": ["3"] * n,
    }
    base.update(cols)
    return pd.DataFrame(base)


# --- tags / text ---------------------------------------------------------------------------

def test_split_tags_normalises_and_dedupes():
    assert split_tags(" Python, python ,SQL,, C++ , .NET ,Data Analysis ") == ["python", "sql", "c++", ".net", "data analysis"]
    assert split_tags(None) == [] and split_tags("") == []


def test_normalize_tag_keeps_symbols():
    assert normalize_tag("C#") == "c#"
    assert normalize_tag("  Node.js  ") == "node.js"
    assert normalize_tag("- Excel -") == "excel"


# --- dates ------------------------------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("4 Days Ago", 4), ("1 Day Ago", 1), ("30+ Days Ago", 30), ("Just Now", 0), ("Few Hours Ago", 0),
    ("Today", 0), ("Starts in 1-3 months", np.nan),
])
def test_days_ago(raw, expected):
    got = days_ago(raw)
    assert (np.isnan(got) and np.isnan(expected)) or got == expected


def test_posting_date_from_job_id():
    d = posting_date_from_job_id(pd.Series(["270925008041", "031025000001", "badid"]))
    assert d.iloc[0] == pd.Timestamp("2025-09-27")
    assert d.iloc[1] == pd.Timestamp("2025-10-03")
    assert pd.isna(d.iloc[2])


def test_temporal_evidence_detects_consistent_scrape_date():
    # Posted on 29 Sep with "4 Days Ago" and on 1 Oct with "2 Days Ago": both imply 3 Oct.
    df = pd.DataFrame({"jobId": ["290925000001", "011025000002", "290925000003"],
                       "jobUploaded": ["4 Days Ago", "2 Days Ago", "4 Days Ago"]})
    ev = temporal_evidence(df)
    assert ev["inferred_scrape_date"] == "2025-10-03"
    assert ev["share_consistent_within_1_day"] == 1.0
    assert ev["posting_dates_available"] is True
    assert ev["forecasting_supported"] is False


# --- salary -------------------------------------------------------------------------------------

def test_salary_zero_is_missing_and_one_sided_fills():
    df = raw_rows(minimumSalary=["0", "300000", "0"], maximumSalary=["0", "0", "500000"])
    out, stats = clean_salary(df)
    assert out["salary_disclosed"].tolist() == [False, True, True]
    assert out.loc[1, "salary_mid_inr"] == 300000
    assert out.loc[2, "salary_min_inr"] == 500000


def test_salary_swaps_and_flags_implausible():
    df = raw_rows(minimumSalary=["900000", "786", "300000"], maximumSalary=["600000", "786", "90000000"])
    out, stats = clean_salary(df)
    assert (out.loc[0, "salary_min_inr"], out.loc[0, "salary_max_inr"]) == (600000, 900000)
    assert stats["swapped_min_max"] == 1
    assert out.loc[1, "salary_flag"] == "implausible" and pd.isna(out.loc[1, "salary_mid_inr"])
    assert out.loc[2, "salary_flag"] == "implausible"


def test_usd_salaries_excluded_by_default():
    df = raw_rows(currency=["USD", "INR"], minimumSalary=["10000", "300000"], maximumSalary=["15000", "400000"])
    out, stats = clean_salary(df)
    assert out.loc[0, "salary_flag"] == "currency_suspect" and not out.loc[0, "salary_disclosed"]
    assert stats["usd_rows_with_salary"] == 1 and stats["usd_policy"] == "exclude"


def test_usd_convert_needs_a_rate():
    df = raw_rows(currency=["USD"], minimumSalary=["10000"], maximumSalary=["20000"])
    with pytest.raises(ValueError):
        clean_salary(df, usd_policy="convert")
    out, _ = clean_salary(df, usd_policy="convert", usd_inr_rate=80.0)
    assert out.loc[0, "salary_mid_inr"] == 15000 * 80


# --- experience / dedupe --------------------------------------------------------------------------

@pytest.mark.parametrize("years,band", [(0, "0-1"), (1, "0-1"), (2, "1-3"), (3, "3-6"), (7, "6-10"), (12, "10+")])
def test_experience_band(years, band):
    assert experience_band(years) == band


def test_clean_experience_swaps():
    out = clean_experience(raw_rows(minimumExperience=["5"], maximumExperience=["2"]))
    assert (out.loc[0, "exp_min"], out.loc[0, "exp_max"]) == (2, 5)


def test_dedupe_groups_near_duplicates_but_keeps_rows():
    df = raw_rows(jobId=["1", "1", "2", "3"], location=["Pune", "Pune", "Mumbai", "Pune"],
                  tagsAndSkills=["Python,SQL", "Python,SQL", "SQL,Python", "Java"])
    df["tags"] = df["tagsAndSkills"].map(split_tags)
    log = StepLog()
    out = dedupe(df, log)
    assert len(out) == 3  # exact jobId duplicate dropped
    g = out.set_index("jobId")["dup_group_id"]
    assert g["1"] == g["2"]  # same company + title + tag set, different city
    assert g["3"] != g["1"]


def test_clean_postings_end_to_end():
    df = raw_rows(jobId=["270925000001", "270925000001", "280925000002"],
                  minimumSalary=["300000", "300000", "0"], maximumSalary=["500000", "500000", "0"])
    jobs, log, stats = clean_postings(df)
    assert len(jobs) == 2
    assert log.steps[0]["rows"] == 3
    assert jobs["posted_date"].notna().all()
    assert stats["disclosed_rows"] == 1


# --- geography --------------------------------------------------------------------------------------

@pytest.mark.parametrize("raw,tokens,mode", [
    ("Hybrid - Bengaluru", ["Bengaluru"], "hybrid"),
    ("Kolkata(Chinar Park)", ["Kolkata"], "onsite"),
    ("Hyderabad, Chennai / Pune", ["Hyderabad", "Chennai", "Pune"], "onsite"),
    ("Remote", [], "remote"),
    ("Remote, Pune", ["Pune"], "remote"),
    (None, [], "onsite"),
])
def test_parse_location(raw, tokens, mode):
    p = parse_location(raw)
    assert p.tokens == tokens and p.work_mode == mode


@pytest.fixture
def gazetteer(tmp_path: Path) -> Gazetteer:
    rows = [
        # name, ascii, alt, lat, lon, fclass, admin1, population
        ("Bengaluru", "Bengaluru", "Bangalore", "12.97", "77.59", "P", "19", "8443675"),
        ("Pune", "Pune", "Poona", "18.52", "73.85", "P", "16", "3124458"),
        ("Gurugram", "Gurugram", "Gurgaon", "28.46", "77.03", "P", "10", "886519"),
        ("Virār", "Virar", "", "19.46", "72.81", "P", "16", "1222390"),
        ("Vasai", "Vasai", "", "22.43", "69.93", "P", "09", "0"),
        ("Hamīrpur", "Hamirpur", "", "25.96", "80.15", "P", "36", "34144"),
        ("Nalgonda", "Nalgonda", "", "17.05", "79.27", "P", "40", "135163"),
    ]
    lines = []
    for i, (name, ascii_, alt, lat, lon, fc, a1, pop) in enumerate(rows):
        lines.append("\t".join([str(i), name, ascii_, alt, lat, lon, fc, "PPL", "IN", "", a1, "", "", "", pop, "", "", "Asia/Kolkata", "2024-01-01"]))
    (tmp_path / "IN.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (tmp_path / "admin1.txt").write_text(
        "IN.19\tKarnataka\tKarnataka\t1\nIN.16\tMaharashtra\tMaharashtra\t2\nIN.10\tHaryana\tHaryana\t3\n"
        "IN.09\tGujarat\tGujarat\t4\nIN.36\tUttar Pradesh\tUttar Pradesh\t5\nIN.40\tTelangana\tTelangana\t6\n",
        encoding="utf-8")
    (tmp_path / "tiers.csv").write_text(
        "# test\ncity,hra_class,tier,state\nBengaluru,X,1,\nPune,X,1,\nGurgaon,Y,2,\nVasai-Virar,Y,2,\n"
        "Hamirpur,Y,2,Himachal Pradesh\n", encoding="utf-8")
    (tmp_path / "aliases.csv").write_text(
        "# test\nalias,city,lookup\nbangalore,Bengaluru,\ngurgaon,Gurugram,\nvasai,Vasai-Virar,Virar\n", encoding="utf-8")
    return Gazetteer(tmp_path / "IN.txt", tmp_path / "admin1.txt", tmp_path / "tiers.csv", tmp_path / "aliases.csv")


def test_gazetteer_resolves_aliases_and_tiers(gazetteer):
    b = gazetteer.resolve("Bangalore")
    assert (b["city"], b["state"], b["matched_by"]) == ("Bengaluru", "Karnataka", "alias")
    assert gazetteer.tier("Bengaluru") == 1
    g = gazetteer.resolve("Gurgaon")
    assert g["city"] == "Gurugram" and gazetteer.tier("Gurugram") == 2  # HRA lists Gurgaon as class Y


def test_alias_lookup_avoids_wrong_homonym(gazetteer):
    # "Vasai" alone matches a village in Gujarat; the alias lookup must pick Vasai-Virar, Maharashtra.
    v = gazetteer.resolve("Vasai")
    assert (v["city"], v["state"]) == ("Vasai-Virar", "Maharashtra")


def test_state_qualified_tier(gazetteer):
    h = gazetteer.resolve("Hamirpur")  # the only Hamirpur here is in Uttar Pradesh
    assert gazetteer.tier(h["city"], h["state"]) == 3


def test_state_only_and_foreign(gazetteer):
    assert gazetteer.resolve("Telangana")["matched_by"] == "state_only"
    assert gazetteer.resolve("United Arab Emirates")["matched_by"] == "foreign"
    assert gazetteer.resolve("Atlantis") is None


def test_fuzzy_match(gazetteer):
    assert gazetteer.resolve("Nalgondaa")["city"] == "Nalgonda"  # ratio ~94 >= 92 cutoff
    assert gazetteer.resolve("Nalgonds") is None  # ratio 87.5: too far, not guessed


def test_geocode_jobs_primary_city_prefers_city_over_state(gazetteer):
    df = pd.DataFrame({"jobId": ["a", "b", "c"], "location": ["Telangana, Nalgonda", "Remote", "Hybrid - Pune"]})
    out, jc, stats = geocode_jobs(df, gazetteer)
    row = out.set_index("jobId")
    assert row.loc["a", "primary_city"] == "Nalgonda" and row.loc["a", "primary_state"] == "Telangana"
    assert row.loc["b", "work_mode"] == "remote" and pd.isna(row.loc["b", "primary_city"])
    assert row.loc["c", "work_mode"] == "hybrid" and row.loc["c", "primary_tier"] == 1
    assert stats["jobs_remote_only"] == 1


def test_metro_region():
    assert metro_region("Gurugram") == "Delhi NCR"
    assert metro_region("Thane") == "Mumbai MMR"
    assert metro_region("Nalgonda") is None
