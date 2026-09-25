# ml_pipeline/india/gold.py

"""
Gold-standard evaluation of ESCO linking, labelled by the team.

Samples (frozen once drawn, committed under data/gold/):
  skill_link_sample.csv   200 tags, stratified by (score band x mention band)
  title_link_sample.csv   200 jobs, stratified by title-similarity band
Labels (written by the /admin/labelling page):
  skill_link_labels.csv   tag, gold_uri | NONE | NOT_A_SKILL, labeller, labelled_at
  title_link_labels.csv   jobId, gold_uri | NONE, labeller, labelled_at

Metrics use inverse-probability (stratum) weights so they estimate the precision
over *all* tag mentions, not just the sample. Thresholds are tuned on a hashed
dev half and reported on the other (test) half; 95% CIs come from a stratified
bootstrap. Everything is reported as "team-labelled, model-assisted".

    python -m ml_pipeline.india.gold sample     # draw the frozen samples
    python -m ml_pipeline.india.gold tune       # tune thresholds -> artifacts/linking_thresholds.json
    python -m ml_pipeline.india.gold evaluate   # refresh the gold block of reports/data_quality.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from app.core.settings import get_settings

SEED = 20260925
SCORE_BANDS = [("exact", None, None), ("0.80+", 0.80, 1.01), ("0.70-0.80", 0.70, 0.80),
               ("0.60-0.70", 0.60, 0.70), ("<0.60", -1.0, 0.60)]
NONE_LABELS = {"NONE", "NOT_A_SKILL"}


def gold_dir() -> Path:
    d = get_settings().gold_data_dir
    d.mkdir(parents=True, exist_ok=True)
    return d


def is_dev(key: str) -> bool:
    """Deterministic 50/50 dev/test split by hashing the item key."""
    return int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:8], 16) % 2 == 0


def score_band(method: str, score: float) -> str:
    if method == "exact":
        return "exact"
    for name, lo, hi in SCORE_BANDS[1:]:
        if lo <= score < hi:
            return name
    return "<0.60"


def mention_band(freq: pd.Series) -> pd.Series:
    """high = tags covering the top 50% of mentions, mid = next 30%, low = the rest."""
    order = freq.sort_values(ascending=False)
    cum = order.cumsum() / order.sum()
    band = pd.Series("low", index=order.index)
    band[cum <= 0.5] = "high"
    band[(cum > 0.5) & (cum <= 0.8)] = "mid"
    return band.reindex(freq.index)


# --- sampling ------------------------------------------------------------------------------

def sample_tags(tag_links: pd.DataFrame, jobs: pd.DataFrame, n: int = 200, seed: int = SEED) -> pd.DataFrame:
    tl = tag_links.copy()
    tl["score_band"] = [score_band(m, s) for m, s in zip(tl["method"], tl["score"], strict=True)]
    tl["mention_band"] = mention_band(tl["freq"])
    tl["stratum"] = tl["score_band"] + "|" + tl["mention_band"]
    strata = tl.groupby("stratum")
    per = max(1, n // strata.ngroups)
    rng = np.random.default_rng(seed)
    picks = []
    for _name, g in strata:
        k = min(per, len(g))
        idx = rng.choice(g.index.to_numpy(), size=k, replace=False)
        picks.append(tl.loc[idx].assign(stratum_size=len(g), stratum_mentions=int(g["freq"].sum()), sampled_in_stratum=k))
    s = pd.concat(picks)
    # Top up to n from the largest strata if some were small.
    if len(s) < n:
        rest = tl.drop(s.index)
        extra = rest.sample(n=min(n - len(s), len(rest)), random_state=seed)
        s = pd.concat([s, extra.assign(stratum_size=extra["stratum"].map(tl["stratum"].value_counts()),
                                       stratum_mentions=extra["stratum"].map(tl.groupby("stratum")["freq"].sum()),
                                       sampled_in_stratum=np.nan)])
        s["sampled_in_stratum"] = s.groupby("stratum")["tag"].transform("size")
    examples = (jobs[["title", "tags"]].explode("tags").dropna().groupby("tags")["title"]
                .apply(lambda t: " | ".join(t.drop_duplicates().head(3))))
    s["example_titles"] = s["tag"].map(examples).fillna("")
    s["split"] = np.where(s["tag"].map(is_dev), "dev", "test")
    cols = ["tag", "freq", "method", "score", "uri", "label", "candidates", "score_band", "mention_band", "stratum",
            "stratum_size", "stratum_mentions", "sampled_in_stratum", "example_titles", "split"]
    return s[cols].sort_values(["stratum", "tag"]).reset_index(drop=True)


def sample_titles(jobs: pd.DataFrame, title_links: pd.DataFrame, n: int = 200, seed: int = SEED) -> pd.DataFrame:
    j = jobs[jobs["title_sim"].notna()].copy()
    j["band"] = pd.cut(j["title_sim"], [-1, 0.5, 0.6, 0.7, 0.8, 1.01],
                       labels=["<0.50", "0.50-0.60", "0.60-0.70", "0.70-0.80", "0.80+"]).astype(str)
    per = n // j["band"].nunique()
    picks = []
    for _band, g in j.groupby("band"):
        k = min(per, len(g))
        picks.append(g.sample(n=k, random_state=seed).assign(stratum_size=len(g), sampled_in_stratum=k))
    s = pd.concat(picks)
    cands = dict(zip(title_links["title_clean"], title_links["candidates"], strict=True))
    s["candidates"] = s["title_clean"].map(cands)
    s["tags_preview"] = s["tags"].map(lambda ts: ", ".join(ts[:8]))
    s["split"] = np.where(s["jobId"].map(is_dev), "dev", "test")
    cols = ["jobId", "title", "title_clean", "companyName", "tags_preview", "occupation_uri", "occupation_label",
            "title_sim", "skill_overlap", "candidates", "band", "stratum_size", "sampled_in_stratum", "split"]
    return s[cols].rename(columns={"band": "stratum"}).reset_index(drop=True)


# --- metrics -------------------------------------------------------------------------------

def _weighted_pr(df: pd.DataFrame, threshold: float, weight: str,
                 single_token_threshold: float | None = None) -> tuple[float | None, float | None, float | None]:
    one_word = df["tag"].astype(str).str.split().map(len).eq(1) if "tag" in df else False
    need = threshold if single_token_threshold is None else np.where(one_word, max(threshold, single_token_threshold), threshold)
    acc = (df["method"] == "exact") | (df["score"] >= need)
    correct = acc & (df["uri"] == df["gold_uri"])
    has_valid = ~df["gold_uri"].isin(NONE_LABELS)
    w = df[weight]
    wa = float((w * acc).sum())
    precision = float((w * correct).sum() / wa) if wa > 0 else None
    wv = float((w * has_valid).sum())
    recall = float((w * correct).sum() / wv) if wv > 0 else None
    f1 = (2 * precision * recall / (precision + recall)) if precision and recall else None
    return precision, recall, f1


def _guard() -> float | None:
    from ml_pipeline.india.run import load_thresholds

    return load_thresholds().get("single_token_threshold")


def _bootstrap_ci(df: pd.DataFrame, threshold: float, weight: str, n_boot: int = 1000, seed: int = SEED):
    rng = np.random.default_rng(seed)
    vals = []
    groups = [g for _, g in df.groupby("stratum")]
    for _ in range(n_boot):
        bs = pd.concat([g.sample(n=len(g), replace=True, random_state=int(rng.integers(1 << 31))) for g in groups])
        p, _, _ = _weighted_pr(bs, threshold, weight, _guard())
        if p is not None:
            vals.append(p)
    if not vals:
        return None
    return [round(float(np.percentile(vals, 2.5)), 4), round(float(np.percentile(vals, 97.5)), 4)]


def load_skill_labels(sample: pd.DataFrame) -> pd.DataFrame | None:
    path = gold_dir() / "skill_link_labels.csv"
    if not path.exists():
        return None
    labels = pd.read_csv(path, dtype=str).drop_duplicates("tag", keep="last")
    df = sample.merge(labels[["tag", "gold_uri"]], on="tag", how="inner")
    if df.empty:
        return None
    # Weights: each sampled tag stands for (stratum mentions / sampled in stratum) mentions
    # and (stratum size / sampled in stratum) unique tags.
    df["w_mentions"] = df["stratum_mentions"] / df["sampled_in_stratum"]
    df["w_unique"] = df["stratum_size"] / df["sampled_in_stratum"]
    return df


def evaluate_skill_links(threshold: float) -> dict:
    sample_path = gold_dir() / "skill_link_sample.csv"
    if not sample_path.exists():
        return {"status": "no sample drawn yet (python -m ml_pipeline.india.gold sample)"}
    sample = pd.read_csv(sample_path, dtype={"tag": str, "uri": str})
    df = load_skill_labels(sample)
    if df is None:
        return {"status": "pending team labels", "sample_size": len(sample),
                "labelling": "Open /admin/labelling in the app to label the frozen sample."}
    test = df[df["split"] == "test"]
    guard = _guard()
    p_m, r_m, f_m = _weighted_pr(test, threshold, "w_mentions", guard)
    p_u, r_u, _ = _weighted_pr(test, threshold, "w_unique", guard)
    return {
        "status": "evaluated",
        "labelled": len(df),
        "labelled_test": len(test),
        "threshold": threshold,
        "single_token_threshold": guard,
        "precision_mention_weighted": p_m,
        "precision_mention_weighted_ci95": _bootstrap_ci(test, threshold, "w_mentions"),
        "recall_mention_weighted": r_m,
        "f1_mention_weighted": f_m,
        "precision_unique_tag_weighted": p_u,
        "recall_unique_tag_weighted": r_u,
        "share_not_a_skill": round(float(df["gold_uri"].eq("NOT_A_SKILL").mean()), 4),
        "share_no_esco_match": round(float(df["gold_uri"].eq("NONE").mean()), 4),
        "method": "team-labelled, model-assisted; stratified sample; weights = stratum mentions / sampled",
    }


def evaluate_title_links(jobs: pd.DataFrame | None = None) -> dict:
    sample_path = gold_dir() / "title_link_sample.csv"
    labels_path = gold_dir() / "title_link_labels.csv"
    if not sample_path.exists():
        return {"status": "no sample drawn yet"}
    if not labels_path.exists():
        return {"status": "pending team labels"}
    sample = pd.read_csv(sample_path, dtype={"jobId": str})
    labels = pd.read_csv(labels_path, dtype=str).drop_duplicates("jobId", keep="last")
    df = sample.merge(labels[["jobId", "gold_uri"]], on="jobId", how="inner")
    if df.empty:
        return {"status": "pending team labels"}
    if jobs is not None:
        current = dict(zip(jobs["jobId"], jobs["occupation_uri"], strict=True))
        df["occupation_uri"] = df["jobId"].map(current)
    df["w"] = df["stratum_size"] / df["sampled_in_stratum"]
    test = df[df["split"] == "test"]
    linked = test["occupation_uri"].notna()
    correct = linked & (test["occupation_uri"] == test["gold_uri"])
    valid = ~test["gold_uri"].isin(NONE_LABELS)
    w = test["w"]
    return {
        "status": "evaluated",
        "labelled": len(df),
        "labelled_test": len(test),
        "precision_weighted": float((w * correct).sum() / (w * linked).sum()) if linked.any() else None,
        "recall_weighted": float((w * correct).sum() / (w * valid).sum()) if valid.any() else None,
        "method": "team-labelled, model-assisted; job-level after skill re-ranking",
    }


def gold_linking_metrics(tag_links: pd.DataFrame, title_links: pd.DataFrame, jobs: pd.DataFrame) -> dict:
    from ml_pipeline.india.run import load_thresholds

    t = load_thresholds()
    return {
        "skills": evaluate_skill_links(t["skill_link_threshold"]),
        "titles": evaluate_title_links(jobs),
    }


def tune_thresholds() -> dict:
    """Pick the skill threshold that maximises mention-weighted F1 on the dev half."""
    sample = pd.read_csv(gold_dir() / "skill_link_sample.csv", dtype={"tag": str, "uri": str})
    df = load_skill_labels(sample)
    if df is None:
        raise SystemExit("No skill labels yet; label the sample in /admin/labelling first.")
    dev = df[df["split"] == "dev"]
    grid = np.round(np.arange(0.50, 0.951, 0.01), 2)
    scores = []
    for th in grid:
        p, r, f = _weighted_pr(dev, th, "w_mentions", _guard())
        scores.append((f or 0.0, p or 0.0, th))
    best_f, best_p, best_t = max(scores)
    out = {
        "skill_link_threshold": float(best_t),
        "status": f"tuned on {len(dev)} dev gold labels (max mention-weighted F1 = {best_f:.3f})",
        "dev_curve": [{"threshold": float(t), "f1": round(f, 4), "precision": round(p, 4)} for f, p, t in scores],
    }
    path = get_settings().artifacts_dir / "linking_thresholds.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=["sample", "tune", "evaluate"])
    parser.add_argument("--force", action="store_true", help="Redraw samples even if they exist")
    args = parser.parse_args(argv)
    d = get_settings().processed_data_dir / "india"
    if args.action == "sample":
        for name in ["skill_link_sample.csv", "title_link_sample.csv"]:
            if (gold_dir() / name).exists() and not args.force:
                print(f"{name} already exists (frozen). Use --force to redraw.")
                return 0
        jobs = pd.read_parquet(d / "jobs.parquet")
        tags = pd.read_parquet(d / "tag_links.parquet")
        titles = pd.read_parquet(d / "title_links.parquet")
        sample_tags(tags, jobs).to_csv(gold_dir() / "skill_link_sample.csv", index=False, encoding="utf-8")
        sample_titles(jobs, titles).to_csv(gold_dir() / "title_link_sample.csv", index=False, encoding="utf-8")
        print(f"Wrote samples to {gold_dir()}")
    elif args.action == "tune":
        print(json.dumps({k: v for k, v in tune_thresholds().items() if k != "dev_curve"}, indent=2))
    else:
        print(json.dumps(refresh_report_gold_block(), indent=2))
    return 0


def refresh_report_gold_block() -> dict:
    """Recompute gold metrics from current labels and write them into data_quality.json."""
    import datetime as dt

    from ml_pipeline.common import read_report, sha256_file

    report = read_report("data_quality")
    if report is None:
        raise SystemExit("reports/data_quality.json not found; run python -m ml_pipeline.india.run first.")
    d = get_settings().processed_data_dir / "india"
    jobs = pd.read_parquet(d / "jobs.parquet", columns=["jobId", "occupation_uri"])
    block = gold_linking_metrics(pd.DataFrame(), pd.DataFrame(), jobs)
    report["gold_evaluation"] = block
    labels = [p for p in gold_dir().glob("*_labels.csv")] + [gold_dir() / "multilingual_phrases.csv"]
    report["provenance"]["gold_refreshed_at_utc"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    report["provenance"]["gold_label_files"] = [
        {"path": p.name, "sha256": sha256_file(p)} for p in labels if p.exists()]
    path = get_settings().reports_dir / "data_quality.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return block


if __name__ == "__main__":
    sys.exit(main())
