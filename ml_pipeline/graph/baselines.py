# ml_pipeline/graph/baselines.py

"""
Baselines, all fitted only on KNOWN edges (see data.py).

  B0  Popularity           most frequent skills; jobs of the most in-demand occupations
  B1  TF-IDF kNN           cosine over IDF-weighted skill sets (item-kNN for completion)
  B2  mpnet + FAISS        SkillAlign's approach: embed the skill list, find the nearest
                           ESCO occupations, recommend their skills. For T3 (which
                           SkillAlign never did) the same encoder embeds each job's text.
  B3a Adamic-Adar          bipartite 3-hop Adamic-Adar over the job/occupation-skill graph

Every model exposes the same three scoring calls used by evaluate.py:
  score_t1(job_ids)                 -> (n, n_skills)
  score_t2(occ_ids)                 -> (n, n_skills)
  score_t3(query_skill_sets, pool)  -> (n_queries, n_pool)
and `score_skill_set` / `rank_jobs` for online (API) use.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import scipy.sparse as sp
from sklearn.preprocessing import normalize

from ml_pipeline.graph.data import GraphData


class Recommender:
    name = "base"
    supports_t2 = True

    def fit(self, data: GraphData, seed: int = 0) -> None:
        raise NotImplementedError

    def score_t1(self, jobs: np.ndarray) -> np.ndarray:
        raise NotImplementedError

    def score_t2(self, occs: np.ndarray) -> np.ndarray:
        raise NotImplementedError

    def score_t3(self, queries: list[np.ndarray], pool: np.ndarray) -> np.ndarray:
        raise NotImplementedError

    # Online helpers (defaults via T3/T1 machinery).
    def score_skill_set(self, skills: np.ndarray) -> np.ndarray:
        """Scores for every skill given a free skill set (e.g. a student's profile)."""
        raise NotImplementedError


def _docs(data: GraphData) -> sp.csr_matrix:
    """Documents = jobs (rows 0..n_jobs-1) then occupations (if any), over skills."""
    if data.occ_known is None:
        return data.known.tocsr()
    return sp.vstack([data.known, data.occ_known]).tocsr()


def _query_matrix(queries: list[np.ndarray], n_skills: int) -> sp.csr_matrix:
    rows = np.repeat(np.arange(len(queries)), [len(q) for q in queries])
    cols = np.concatenate(queries) if queries else np.array([], dtype=np.int64)
    return sp.csr_matrix((np.ones(len(cols), dtype=np.float32), (rows, cols)), shape=(len(queries), n_skills))


# --- B0 --------------------------------------------------------------------------------------

class Popularity(Recommender):
    name = "B0 Popularity"

    def fit(self, data: GraphData, seed: int = 0) -> None:
        self.data = data
        self.job_pop = np.asarray(data.known.sum(axis=0)).ravel().astype(np.float32)
        self.occ_pop = (np.asarray(data.occ_known.sum(axis=0)).ravel().astype(np.float32)
                        if data.occ_known is not None else self.job_pop)
        occ = data.jobs["occupation_uri"].fillna("")
        demand = occ.map(occ.value_counts()).to_numpy().astype(np.float32)
        demand[occ.to_numpy() == ""] = 0.0
        self.job_demand = demand

    def score_t1(self, jobs):
        return np.broadcast_to(self.job_pop, (len(jobs), len(self.job_pop))).copy()

    def score_t2(self, occs):
        return np.broadcast_to(self.occ_pop, (len(occs), len(self.occ_pop))).copy()

    def score_t3(self, queries, pool):
        return np.broadcast_to(self.job_demand[pool], (len(queries), len(pool))).copy()

    def score_skill_set(self, skills):
        return self.job_pop.copy()


# --- B1 --------------------------------------------------------------------------------------

class TfidfKNN(Recommender):
    name = "B1 TF-IDF kNN"

    K_GRID = (20, 50, 100, 200)

    def __init__(self, k: int | None = None, chunk: int = 512):
        self.k = k  # None = tune on validation T1 recall@10
        self.chunk = chunk

    def fit(self, data: GraphData, seed: int = 0) -> None:
        self.data = data
        self.docs = _docs(data)
        df = np.asarray((self.docs > 0).sum(axis=0)).ravel()
        self.idf = np.log((1 + self.docs.shape[0]) / (1 + df)).astype(np.float32) + 1.0
        self.docs_tfidf = normalize(self.docs.multiply(self.idf).tocsr())
        self.docs_bin = self.docs.tocsr()
        if self.k is None:
            self.k = self._tune_k(seed)

    def _tune_k(self, seed: int) -> int:
        from ml_pipeline.graph.metrics import recall_at_k, top_k_from_scores

        val = self.data.eval_jobs("val")
        val = np.random.default_rng(seed).choice(val, min(1000, len(val)), replace=False)
        best_k, best = self.K_GRID[0], -1.0
        self.tuning = {}
        for k in self.K_GRID:
            self.k = k
            scores = self.score_t1(val)
            rec = np.mean([recall_at_k(top_k_from_scores(scores[i], 10, exclude=self.data.known[j].indices),
                                       {int(h): 1 for h in self.data.hidden[int(j)]}) for i, j in enumerate(val)])
            self.tuning[k] = round(float(rec), 4)
            if rec > best:
                best_k, best = k, rec
        return best_k

    def _neighbour_scores(self, q_tfidf: sp.csr_matrix, exclude_rows: np.ndarray | None) -> np.ndarray:
        out = np.zeros((q_tfidf.shape[0], self.docs.shape[1]), dtype=np.float32)
        for s in range(0, q_tfidf.shape[0], self.chunk):
            sim = (q_tfidf[s:s + self.chunk] @ self.docs_tfidf.T).toarray()
            if exclude_rows is not None:
                sim[np.arange(sim.shape[0]), exclude_rows[s:s + self.chunk]] = 0.0
            k = min(self.k, sim.shape[1] - 1)
            idx = np.argpartition(-sim, k, axis=1)[:, :k]
            vals = np.take_along_axis(sim, idx, axis=1)
            w = sp.csr_matrix((vals.ravel(), (np.repeat(np.arange(sim.shape[0]), k), idx.ravel())),
                              shape=sim.shape)
            out[s:s + self.chunk] = (w @ self.docs_bin).toarray()
        return out

    def score_t1(self, jobs):
        return self._neighbour_scores(self.docs_tfidf[jobs], exclude_rows=jobs)

    def score_t2(self, occs):
        rows = occs + self.data.n_jobs
        return self._neighbour_scores(self.docs_tfidf[rows], exclude_rows=rows)

    def _query_tfidf(self, queries):
        return normalize(_query_matrix(queries, self.docs.shape[1]).multiply(self.idf).tocsr())

    def score_t3(self, queries, pool):
        q = self._query_tfidf(queries)
        return (q @ self.docs_tfidf[pool].T).toarray().astype(np.float32)

    def score_skill_set(self, skills):
        return self._neighbour_scores(self._query_tfidf([skills]), exclude_rows=None)[0]


# --- B3a -------------------------------------------------------------------------------------

class AdamicAdar(Recommender):
    name = "B3a Adamic-Adar"

    def fit(self, data: GraphData, seed: int = 0) -> None:
        self.data = data
        docs = _docs(data)
        doc_deg = np.asarray(docs.sum(axis=1)).ravel()
        skill_deg = np.asarray(docs.sum(axis=0)).ravel()
        inv_doc = 1.0 / np.log(2.0 + doc_deg)
        self.inv_skill = (1.0 / np.log(2.0 + skill_deg)).astype(np.float32)
        # skill-skill co-occurrence through documents, each shared document weighted 1/log(deg).
        self.S = (docs.T @ sp.diags(inv_doc.astype(np.float32)) @ docs).tocsr()
        self.S.setdiag(0)
        self.S.eliminate_zeros()
        self.docs = docs

    def _from_sets(self, m: sp.csr_matrix) -> np.ndarray:
        return (m.multiply(self.inv_skill).tocsr() @ self.S).toarray().astype(np.float32)

    def score_t1(self, jobs):
        return self._from_sets(self.docs[jobs])

    def score_t2(self, occs):
        return self._from_sets(self.docs[occs + self.data.n_jobs])

    def score_t3(self, queries, pool):
        q = _query_matrix(queries, self.docs.shape[1]).multiply(self.inv_skill).tocsr()
        return (q @ self.docs[pool].T).toarray().astype(np.float32)

    def score_skill_set(self, skills):
        return self._from_sets(_query_matrix([skills], self.docs.shape[1]))[0]


# --- B2 --------------------------------------------------------------------------------------

class MpnetFaiss(Recommender):
    """SkillAlign's method: sentence-embed the skill list, match it to ESCO occupation texts."""

    name = "B2 mpnet+FAISS (SkillAlign)"

    def __init__(self, model_name: str | None = None, top_occ: int = 20):
        from app.core.settings import get_settings

        self.model_name = model_name or get_settings().model_name
        self.top_occ = top_occ

    def fit(self, data: GraphData, seed: int = 0) -> None:
        import faiss

        from app.core.settings import get_settings
        from ml_pipeline.india.link import EmbeddingModel

        self.data = data
        self.enc = EmbeddingModel(self.model_name, max_seq_length=256)
        self._job_emb_cache: dict[int, np.ndarray] = {}
        if data.occ_known is None:  # raw-tag vocabulary: no occupation profiles to match
            self.index = None
            return
        occ = pd.read_csv(get_settings().esco_data_dir / "occupations_en.csv", dtype=str,
                          keep_default_na=False, usecols=["conceptUri", "preferredLabel", "description"])
        desc = dict(zip(occ["conceptUri"], occ["description"], strict=True))
        # Occupation texts use KNOWN skills only (the original SkillAlign index used all
        # of them, which would leak T2's hidden skills).
        texts = []
        for o, uri in enumerate(data.occupations):
            labels = [data.skill_text[s] for s in data.occ_known[o].indices] if data.occ_known is not None else []
            texts.append(f"{data.occ_text[o]}. {desc.get(uri, '')}. {' '.join(labels)}".lower())
        self.occ_emb = self.enc.encode(texts)
        self.index = faiss.IndexFlatIP(self.occ_emb.shape[1])
        self.index.add(self.occ_emb)
        self.occ_weight = data.occ_weight.tocsr()

    def _set_text(self, skills: np.ndarray) -> str:
        return " ".join(self.data.skill_text[s] for s in skills)

    def _from_texts(self, texts: list[str], exclude_occ: np.ndarray | None = None) -> np.ndarray:
        q = self.enc.encode(texts)
        k = self.top_occ + (1 if exclude_occ is not None else 0)
        sims, idx = self.index.search(q, k)
        out = np.zeros((len(texts), self.data.n_skills), dtype=np.float32)
        for r in range(len(texts)):
            keep = [(i, s) for i, s in zip(idx[r], sims[r], strict=True)
                    if i >= 0 and (exclude_occ is None or i != exclude_occ[r])][: self.top_occ]
            if not keep:
                continue
            w = sp.csr_matrix((np.array([s for _, s in keep], dtype=np.float32),
                               (np.zeros(len(keep), dtype=np.int64), np.array([i for i, _ in keep]))),
                              shape=(1, len(self.data.occupations)))
            out[r] = (w @ self.occ_weight).toarray()[0]
        return out

    def score_t1(self, jobs):
        texts = [self._set_text(self.data.known[j].indices) for j in jobs]
        return self._from_texts(texts)

    def score_t2(self, occs):
        texts = [self._set_text(self.data.occ_known[o].indices) for o in occs]
        # An occupation's own entry is in the index; exclude it so it can't just copy itself.
        return self._from_texts(texts, exclude_occ=occs)

    def _job_embeddings(self, jobs: np.ndarray) -> np.ndarray:
        missing = [j for j in jobs if int(j) not in self._job_emb_cache]
        if missing:
            texts = [f"{self.data.jobs.at[j, 'title_clean']}. {self._set_text(self.data.known[j].indices)}"
                     for j in missing]
            for j, e in zip(missing, self.enc.encode(texts), strict=True):
                self._job_emb_cache[int(j)] = e
        return np.stack([self._job_emb_cache[int(j)] for j in jobs])

    def score_t3(self, queries, pool):
        q = self.enc.encode([self._set_text(s) for s in queries])
        return (q @ self._job_embeddings(pool).T).astype(np.float32)

    def score_skill_set(self, skills):
        return self._from_texts([self._set_text(skills)])[0]
