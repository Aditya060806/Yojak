# ml_pipeline/india/multilingual.py

"""
Does skill linking work for Hindi, Punjabi and romanised Hindi?

Compares two embedding models on the same data:
  english   the team-labelled English tag sample (precision / recall, test half)
  cross     team-written phrases for 60 common ESCO skills, per language:
            top-1 accuracy and recall@5 of linking the phrase to its ESCO skill

    python -m ml_pipeline.india.multilingual  ->  reports/multilingual_eval.json

Results are "pending" until the team has labelled data/gold/*; nothing is
estimated without labels.
"""

from __future__ import annotations

import io
import sys

import pandas as pd

from app.core.settings import get_settings
from ml_pipeline.common import provenance, wilson_interval, write_report
from ml_pipeline.india.gold import _weighted_pr, gold_dir, load_skill_labels
from ml_pipeline.india.link import ConceptLinker, EmbeddingModel, esco_concepts

LANGS = {"hi": "Hindi (Devanagari)", "pa": "Punjabi (Gurmukhi)", "hi-Latn": "Hindi (romanised)"}


def _read_gold(name: str) -> pd.DataFrame | None:
    path = gold_dir() / name
    if not path.exists():
        return None
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if not ln.startswith("#")]
    return pd.read_csv(io.StringIO("\n".join(lines)), dtype=str, keep_default_na=False)


def evaluate_model(model_name: str, threshold: float) -> dict:
    settings = get_settings()
    enc = EmbeddingModel(model_name)
    slug = model_name.rsplit("/", 1)[-1]
    linker = ConceptLinker(esco_concepts(settings.esco_data_dir, "skill"), enc,
                           settings.artifacts_dir / "cache" / "emb", f"esco_skill_{slug}")
    out: dict = {"model": model_name}

    sample = _read_gold("skill_link_sample.csv")
    labelled = load_skill_labels(sample) if sample is not None else None
    if labelled is None:
        out["english"] = {"status": "pending team labels"}
    else:
        from ml_pipeline.india.gold import _guard

        relinked = linker.link(labelled["tag"].tolist(), threshold=threshold, single_token_threshold=_guard())
        df = labelled.drop(columns=["uri", "score", "method"]).assign(
            uri=relinked["uri"].values, score=relinked["score"].values, method=relinked["method"].values)
        test = df[df["split"] == "test"]
        p, r, f = _weighted_pr(test, threshold, "w_mentions", _guard())
        out["english"] = {"status": "evaluated", "n_test": len(test), "threshold": threshold,
                          "precision_mention_weighted": p, "recall_mention_weighted": r, "f1": f}

    phrases = _read_gold("multilingual_phrases.csv")
    if phrases is None or phrases.empty:
        out["cross_lingual"] = {"status": "pending team phrases"}
        return out
    phrases = phrases.drop_duplicates(["skill_uri", "language"], keep="last")
    idx, _ = linker.search(phrases["phrase"].tolist(), top_k=5)
    uris = linker.concepts["uri"].to_numpy()
    top = [[uris[i] for i in row if i >= 0] for row in idx]
    phrases = phrases.assign(top1=[t[0] if t else None for t in top], top5=top)
    per_lang = {}
    for lang, g in phrases.groupby("language"):
        hit1 = int((g["top1"] == g["skill_uri"]).sum())
        hit5 = int(sum(u in t for u, t in zip(g["skill_uri"], g["top5"], strict=True)))
        per_lang[lang] = {
            "language": LANGS.get(lang, lang),
            "n": len(g),
            "top1_accuracy": hit1 / len(g),
            "top1_ci95": wilson_interval(hit1, len(g)),
            "recall_at_5": hit5 / len(g),
            "recall_at_5_ci95": wilson_interval(hit5, len(g)),
        }
    out["cross_lingual"] = {"status": "evaluated", "per_language": per_lang}
    return out


def main() -> int:
    settings = get_settings()
    from ml_pipeline.india.run import load_thresholds

    th = load_thresholds()["skill_link_threshold"]
    results = [evaluate_model(m, th) for m in [settings.model_name, settings.multilingual_model_name]]
    body = {
        "question": "Can users enter skills in Hindi, Punjabi or romanised Hindi and still get correct ESCO links?",
        "models": results,
        "decision_rule": ("Use the multilingual model for non-English input always; use it for English too "
                          "only if its English precision is within the CI of the English model."),
        "gold": "team-written phrases (data/gold/multilingual_phrases.csv) for 60 common ESCO skills",
    }
    prov = provenance("ml_pipeline/india/multilingual.py",
                      inputs=[gold_dir() / "multilingual_phrases.csv", gold_dir() / "skill_link_labels.csv"])
    print(write_report("multilingual_eval", body, prov))
    return 0


if __name__ == "__main__":
    sys.exit(main())
