# ml_pipeline/graph/hgt/features.py

"""
Input node features for the HGT, cached under artifacts/graph/.

  skill       sentence embedding of the ESCO label (or raw tag text)
  occupation  sentence embedding of the ESCO occupation label
  job         sentence embedding of the cleaned job title + [exp_min/30, has_exp]
Company, city and experience-band nodes use learned embeddings inside the model.
"""

from __future__ import annotations

import hashlib

import numpy as np

from app.core.settings import get_settings
from ml_pipeline.graph.data import GraphData


def _cached_encode(texts: list[str], name: str, model_name: str) -> np.ndarray:
    from ml_pipeline.india.link import EmbeddingModel

    d = get_settings().artifacts_dir / "graph" / "features"
    d.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha1(("\n".join(texts) + model_name).encode("utf-8")).hexdigest()[:12]
    path = d / f"{name}_{digest}.npy"
    if path.exists():
        return np.load(path)
    uniq = sorted(set(texts))
    enc = EmbeddingModel(model_name, max_seq_length=48)
    emb = enc.encode(uniq)
    lookup = {t: i for i, t in enumerate(uniq)}
    out = emb[[lookup[t] for t in texts]].astype(np.float16)
    np.save(path, out)
    return out


def node_features(data: GraphData, model_name: str | None = None) -> dict[str, np.ndarray]:
    model_name = model_name or get_settings().model_name
    skills = _cached_encode(list(data.skill_text), f"skill_{data.vocab}", model_name)
    occ_text = data.occ_text or []
    if not occ_text:  # tags vocabulary: occupation nodes still exist via MAPS_TO
        from ml_pipeline.graph.data import _esco_occupations

        occ_df, _ = _esco_occupations()
        occ_text = occ_df["preferredLabel"].tolist()
    occupations = _cached_encode(occ_text, "occupation", model_name)
    titles = _cached_encode(data.jobs["title_clean"].fillna("").tolist(), "job_title", model_name)
    exp = data.jobs["exp_min"].to_numpy(dtype=float)
    extra = np.stack([np.nan_to_num(exp, nan=0.0) / 30.0, (~np.isnan(exp)).astype(float)], axis=1).astype(np.float16)
    return {"skill": skills, "occupation": occupations, "job": np.concatenate([titles, extra], axis=1)}
