# app/core/ml.py

"""
ML Core Module
Loads and queries the FAISS occupation index and the SentenceTransformer model.

The model and the index are loaded independently and each exactly once, so a
missing index no longer forces the model to be reloaded on every request.
"""

from __future__ import annotations

import os

# sentence-transformers pulls in `transformers`, which imports TensorFlow if it is
# installed. We only use PyTorch, so skip TF (saves seconds and memory at startup).
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("TRANSFORMERS_NO_TF", "1")

import logging  # noqa: E402
import threading  # noqa: E402
from typing import List, Optional, Tuple  # noqa: E402

import faiss  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sentence_transformers import SentenceTransformer  # noqa: E402

from app.core.settings import get_settings  # noqa: E402

logger = logging.getLogger(__name__)


def l2_to_cosine(squared_l2: float) -> float:
    """
    Convert a FAISS IndexFlatL2 distance to cosine similarity.

    IndexFlatL2 returns the *squared* L2 distance. For unit vectors,
    ||a - b||^2 = 2 - 2cos(a, b), so cos = 1 - d/2 (clipped to [0, 1]).
    """
    return float(min(1.0, max(0.0, 1.0 - squared_l2 / 2.0)))


class MLEngine:
    """
    Singleton ML engine for FAISS-based occupation recommendations.
    Resources are loaded lazily on first use.
    """

    _instance: Optional[MLEngine] = None

    def __new__(cls) -> MLEngine:
        if cls._instance is None:
            inst = super().__new__(cls)
            inst.model = None
            inst.faiss_index = None
            inst.occupation_uris = None
            inst._lock = threading.Lock()
            cls._instance = inst
        return cls._instance

    model: Optional[SentenceTransformer]
    faiss_index: Optional[faiss.Index]
    occupation_uris: Optional[List[str]]

    def _load_model(self) -> SentenceTransformer:
        if self.model is None:
            with self._lock:
                if self.model is None:
                    name = get_settings().model_name
                    logger.info("Loading SentenceTransformer model '%s'", name)
                    self.model = SentenceTransformer(name)
        return self.model

    def _load_index(self) -> None:
        if self.faiss_index is not None and self.occupation_uris is not None:
            return
        with self._lock:
            if self.faiss_index is not None and self.occupation_uris is not None:
                return
            settings = get_settings()
            index_path = settings.faiss_index_path
            meta_path = settings.occupation_metadata_path
            if not index_path.exists():
                raise RuntimeError(
                    f"FAISS index not found at {index_path}. Run the ML pipeline first."
                )
            if not meta_path.exists():
                raise RuntimeError(
                    f"Occupation metadata not found at {meta_path}. Run the ML pipeline first."
                )
            index = faiss.read_index(str(index_path))
            meta = pd.read_csv(meta_path)
            if "occupation_uri" not in meta.columns:
                raise RuntimeError("occupation_metadata.csv must contain 'occupation_uri'")
            uris = meta["occupation_uri"].tolist()
            if len(uris) != index.ntotal:
                raise RuntimeError(
                    f"Metadata rows ({len(uris)}) != FAISS vectors ({index.ntotal}); rebuild the index."
                )
            self.faiss_index, self.occupation_uris = index, uris
            logger.info("FAISS index loaded: %d vectors, dim %d", index.ntotal, index.d)

    def encode(self, texts: List[str]) -> np.ndarray:
        """Encode texts into L2-normalised embeddings, shape (n, dim)."""
        model = self._load_model()
        return model.encode(
            texts, convert_to_numpy=True, show_progress_bar=False, normalize_embeddings=True
        ).astype(np.float32)

    def search(self, query_embedding: np.ndarray, top_k: int = 20) -> List[Tuple[str, float]]:
        """Return (occupation_uri, cosine_similarity) pairs, best first."""
        self._load_index()
        assert self.faiss_index is not None and self.occupation_uris is not None
        q = np.asarray(query_embedding, dtype=np.float32)
        if q.ndim == 1:
            q = q.reshape(1, -1)
        if q.shape[1] != self.faiss_index.d:
            raise RuntimeError(
                f"Query dimension {q.shape[1]} != index dimension {self.faiss_index.d}"
            )
        distances, indices = self.faiss_index.search(q, top_k)
        results: List[Tuple[str, float]] = []
        for idx, dist in zip(indices[0], distances[0], strict=True):
            if 0 <= idx < len(self.occupation_uris):
                results.append((self.occupation_uris[idx], l2_to_cosine(float(dist))))
        return results

    def is_ready(self) -> bool:
        """True when both the model and the index can be loaded."""
        try:
            self._load_index()
            model = self._load_model()
            if model.get_sentence_embedding_dimension() != self.faiss_index.d:  # type: ignore[union-attr]
                logger.error("Model and FAISS index dimensions differ; rebuild the index.")
                return False
            return True
        except Exception as e:  # noqa: BLE001 - readiness probe must not raise
            logger.error("ML engine not ready: %s", e)
            return False


ml_engine = MLEngine()
