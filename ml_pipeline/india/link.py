# ml_pipeline/india/link.py

"""
Link free text (Naukri skill tags, job titles, resume phrases) to ESCO concepts.

Two passes:
  1. exact:     normalised text equals an ESCO preferred/alternative label
                (also the preferred label without its parenthetical, so
                "python" matches "Python (computer programming)").
  2. embedding: cosine similarity between the text and every ESCO label
                (preferred + alternatives), max-pooled per concept, top-k kept.

A link is accepted when its score >= threshold. Everything else goes to the
unlinked table; nothing is forced onto the taxonomy.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

import faiss
import numpy as np
import pandas as pd

from ml_pipeline.india.clean import normalize_tag

_PAREN = re.compile(r"\s*\([^)]*\)\s*")


def label_variants(preferred: str, alt_labels: list[str]) -> list[tuple[str, str]]:
    """(label, kind) pairs for one concept; kind is preferred | preferred_short | alt."""
    out = [(preferred, "preferred")]
    short = _PAREN.sub(" ", preferred).strip()
    if short and short.lower() != preferred.lower():
        out.append((short, "preferred_short"))
    out += [(a, "alt") for a in alt_labels if a]
    return out


def split_alt(value: object) -> list[str]:
    if not isinstance(value, str):
        return []
    return [p.strip() for p in value.splitlines() if p.strip()]


@dataclass
class Concept:
    uri: str
    label: str
    kind: str  # "skill" | "occupation"
    extra: dict


class ConceptLinker:
    """Exact + embedding linker over a set of ESCO concepts."""

    KIND_PRIORITY = {"preferred": 0, "preferred_short": 1, "alt": 2}

    def __init__(self, concepts: pd.DataFrame, encoder, cache_dir: Path | None = None, name: str = "concepts"):
        """
        concepts: columns uri, preferredLabel, altLabels (list[str]) and optional extras.
        encoder:  object with .encode(list[str]) -> L2-normalised float32 array (e.g. EmbeddingModel).
        """
        self.encoder = encoder
        self.concepts = concepts.reset_index(drop=True)
        self.uri_to_idx = {u: i for i, u in enumerate(self.concepts["uri"])}

        rows: list[tuple[str, int, str]] = []  # (label text, concept idx, kind)
        for i, row in enumerate(self.concepts.itertuples(index=False)):
            for text, kind in label_variants(row.preferredLabel, list(row.altLabels)):
                rows.append((text, i, kind))
        self.label_text = [r[0] for r in rows]
        self.label_concept = np.array([r[1] for r in rows], dtype=np.int64)

        # Exact dictionary: best (most preferred) label kind wins; ties -> ambiguous list.
        self.exact: dict[str, list[tuple[int, int]]] = {}
        for text, idx, kind in rows:
            key = normalize_tag(text)
            self.exact.setdefault(key, []).append((self.KIND_PRIORITY[kind], idx))

        self.label_emb = self._embed_cached(self.label_text, cache_dir, f"{name}_labels")
        self.index = faiss.IndexFlatIP(self.label_emb.shape[1])
        self.index.add(self.label_emb)

    def _embed_cached(self, texts: list[str], cache_dir: Path | None, name: str) -> np.ndarray:
        if cache_dir is None:
            return self.encoder.encode(texts)
        cache_dir.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha1(("\n".join(texts) + self.encoder.model_name).encode("utf-8")).hexdigest()[:12]
        path = cache_dir / f"{name}_{digest}.npy"
        if path.exists():
            return np.load(path)
        emb = self.encoder.encode(texts)
        np.save(path, emb)
        return emb

    def exact_match(self, text: str) -> int | None:
        hits = self.exact.get(normalize_tag(text))
        if not hits:
            return None
        best = min(p for p, _ in hits)
        cands = {idx for p, idx in hits if p == best}
        return next(iter(cands)) if len(cands) == 1 else None  # ambiguous -> let embeddings decide

    def search(self, queries: list[str], top_k: int = 5, label_k: int = 40) -> tuple[np.ndarray, np.ndarray]:
        """Top-k concepts per query by max label cosine. Returns (concept_idx, scores), shape (n, k)."""
        if not queries:
            return np.zeros((0, top_k), dtype=np.int64), np.zeros((0, top_k), dtype=np.float32)
        q = self.encoder.encode(queries)
        scores, lab = self.index.search(q, label_k)
        concept = self.label_concept[lab]
        out_idx = np.full((len(queries), top_k), -1, dtype=np.int64)
        out_score = np.zeros((len(queries), top_k), dtype=np.float32)
        for r in range(len(queries)):
            best: dict[int, float] = {}
            for c, s in zip(concept[r], scores[r], strict=True):
                if c not in best:  # FAISS returns labels best-first, so first hit is the max
                    best[c] = float(s)
                if len(best) == top_k:
                    break
            items = list(best.items())
            out_idx[r, : len(items)] = [c for c, _ in items]
            out_score[r, : len(items)] = [s for _, s in items]
        return out_idx, out_score

    def link(self, texts: list[str], threshold: float, top_k: int = 5,
             single_token_threshold: float | None = None) -> pd.DataFrame:
        """
        One row per input text: best concept, score, method, accepted flag and the
        top-k candidate list (JSON) for audit and labelling.

        Ambiguity guard: a one-word text linked by embedding (not an exact label match)
        must reach `single_token_threshold` (if given). Generic single words such as
        "development" or "training" otherwise land on unrelated concepts
        ("developmental psychology", "military drill") above the normal threshold.
        """
        texts = list(texts)
        exact_idx = [self.exact_match(t) for t in texts]
        idx, score = self.search(texts, top_k=top_k)
        rows = []
        for i, t in enumerate(texts):
            cands = [
                {"uri": self.concepts.at[int(c), "uri"], "label": self.concepts.at[int(c), "preferredLabel"],
                 "score": round(float(s), 4)}
                for c, s in zip(idx[i], score[i], strict=True) if c >= 0
            ]
            if exact_idx[i] is not None:
                c = exact_idx[i]
                best_uri, best_label, best_score, method = (
                    self.concepts.at[c, "uri"], self.concepts.at[c, "preferredLabel"], 1.0, "exact")
                # The exact concept always heads the candidate list (score 1.0).
                cands = [{"uri": best_uri, "label": best_label, "score": 1.0}] + [
                    x for x in cands if x["uri"] != best_uri][: top_k - 1]
            elif cands:
                best_uri, best_label, best_score, method = cands[0]["uri"], cands[0]["label"], cands[0]["score"], "embedding"
            else:
                best_uri, best_label, best_score, method = None, None, 0.0, "none"
            rows.append({
                "text": t,
                "uri": best_uri,
                "label": best_label,
                "score": best_score,
                "method": method,
                "accepted": bool(best_uri) and (method == "exact" or best_score >= (
                    max(threshold, single_token_threshold)
                    if single_token_threshold is not None and len(t.split()) == 1 else threshold)),
                "candidates": json.dumps(cands, ensure_ascii=False),
            })
        return pd.DataFrame(rows)


class EmbeddingModel:
    """
    Thin wrapper around SentenceTransformer that returns L2-normalised float32.

    Texts here are short (tags, titles, labels), so the sequence length is capped,
    which cuts GPU memory a lot. On CUDA out-of-memory the batch is halved and
    retried, down to a batch of 8, before giving up.
    """

    def __init__(self, model_name: str, device: str | None = None, batch_size: int = 128, max_seq_length: int = 64):
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name
        self.batch_size = batch_size
        self.model = SentenceTransformer(model_name, device=device)
        self.model.max_seq_length = min(self.model.max_seq_length or max_seq_length, max_seq_length)

    def encode(self, texts: list[str]) -> np.ndarray:
        import torch

        batch = self.batch_size
        while True:
            try:
                return self.model.encode(
                    list(texts), batch_size=batch, convert_to_numpy=True,
                    normalize_embeddings=True, show_progress_bar=len(texts) > 5000,
                ).astype(np.float32)
            except torch.cuda.OutOfMemoryError:
                torch.cuda.empty_cache()
                if batch <= 8:
                    raise
                batch //= 2
            except RuntimeError as e:  # older torch raises a plain RuntimeError
                if "out of memory" not in str(e) or batch <= 8:
                    raise
                torch.cuda.empty_cache()
                batch //= 2


def esco_concepts(esco_dir: Path, kind: str) -> pd.DataFrame:
    """ESCO skills or occupations as uri / preferredLabel / altLabels (+ type info)."""
    if kind == "skill":
        df = pd.read_csv(esco_dir / "skills_en.csv", dtype=str, keep_default_na=False, encoding="utf-8-sig")
        df = df.drop_duplicates("conceptUri")  # ESCO v1.2 ships 21 repeated skill rows
        extra = ["skillType", "reuseLevel"]
    elif kind == "occupation":
        df = pd.read_csv(esco_dir / "occupations_en.csv", dtype=str, keep_default_na=False, encoding="utf-8-sig")
        extra = ["iscoGroup"]
    else:
        raise ValueError(kind)
    df = df[df["conceptUri"].str.len() > 0].drop_duplicates("conceptUri")
    out = pd.DataFrame({
        "uri": df["conceptUri"].str.strip(),
        "preferredLabel": df["preferredLabel"].str.strip(),
        "altLabels": df["altLabels"].map(split_alt),
    })
    for col in extra:
        out[col] = df[col].values
    return out.reset_index(drop=True)


# --- job titles --------------------------------------------------------------------------

_TITLE_NOISE = re.compile(
    r"\b(?:senior|sr|jr|junior|trainee|fresher|freshers|intern|urgent(?:ly)?|hiring|opening|openings|"
    r"vacancy|immediate(?:ly)?|joiners?|walk[\s-]?in|wfh|work from home|remote|hybrid|required|"
    r"l[1-5]|level\s*[1-5]|grade\s*[a-z0-9]+|ii|iii|iv)\b"
)
_TITLE_EXPAND = [
    (re.compile(r"\bai\s*/\s*ml\b|\baiml\b"), "artificial intelligence machine learning"),
    (re.compile(r"\bml\b"), "machine learning"),
    (re.compile(r"\bai\b"), "artificial intelligence"),
    (re.compile(r"\bhr\b"), "human resources"),
    (re.compile(r"\bqa\b"), "quality assurance"),
    (re.compile(r"\bui\s*/\s*ux\b|\bux\s*/\s*ui\b"), "ui ux"),
    (re.compile(r"\bbde\b"), "business development executive"),
    (re.compile(r"\bbdm\b"), "business development manager"),
    (re.compile(r"\bmis\b"), "management information systems"),
    (re.compile(r"\bsde\b"), "software development engineer"),
    (re.compile(r"\bdev\s*ops\b"), "devops"),
]


def clean_title(title: str) -> str:
    """'Sr. AI/ML Engineer - L3 (Urgent Hiring)' -> 'artificial intelligence machine learning engineer'."""
    t = str(title).lower()
    t = re.sub(r"[\(\[][^\)\]]*[\)\]]", " ", t)
    for pat, rep in _TITLE_EXPAND:
        t = pat.sub(rep, t)
    t = re.sub(r"[^a-z0-9+#/&\. ]+", " ", t)
    t = _TITLE_NOISE.sub(" ", t)
    t = re.sub(r"\b(?:sr|jr)\.", " ", t)
    t = re.sub(r"\s+", " ", t).strip(" -/.&")
    return t or str(title).strip().lower()


def rerank_by_skills(
    title_candidates: list[dict],
    job_skill_uris: set[str],
    occupation_skills: dict[str, dict[str, float]],
    alpha: float,
    margin: float = 0.08,
) -> tuple[dict | None, float, float]:
    """
    Re-rank title candidates with the job's own skills.

    Only candidates whose title similarity is within `margin` of the best one
    are eligible, and an exact title match (score 1.0) is never overridden:
    skills break near-ties between plausible titles, they don't replace the title.

      combined = alpha * title_similarity + (1 - alpha) * skill_overlap

    skill_overlap = weighted share of the job's linked skills that the candidate
    occupation requires (1.0 essential, 0.5 optional). Returns (best, combined, overlap).
    """
    if not title_candidates:
        return None, -1.0, 0.0
    top_score = title_candidates[0]["score"]
    if top_score >= 1.0 or not job_skill_uris:
        first = title_candidates[0]
        req = occupation_skills.get(first["uri"], {})
        overlap = sum(req.get(u, 0.0) for u in job_skill_uris) / len(job_skill_uris) if job_skill_uris else 0.0
        return first, first["score"], overlap
    best, best_score, best_overlap = None, -1.0, 0.0
    for cand in title_candidates:
        if cand["score"] < top_score - margin:
            continue
        req = occupation_skills.get(cand["uri"], {})
        overlap = sum(req.get(u, 0.0) for u in job_skill_uris) / len(job_skill_uris) if req else 0.0
        score = alpha * cand["score"] + (1 - alpha) * overlap
        if score > best_score:
            best, best_score, best_overlap = cand, score, overlap
    return best, best_score, best_overlap
