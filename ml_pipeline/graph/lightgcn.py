# ml_pipeline/graph/lightgcn.py

"""
B3b LightGCN (He et al., 2020) in plain PyTorch.

Bipartite graph: "users" = jobs + ESCO occupations, "items" = skills, KNOWN edges
only. Symmetric-normalised propagation, mean over layers, BPR loss with uniform
negative sampling, early stopping on validation T1 recall@10 (val hidden edges).

T3 candidates are new users, folded in the way LightGCN propagates: each skill's
final embedding weighted by 1/sqrt(d_user * d_skill); jobs are then ranked by cosine.
That rule was chosen on the train-job T3 dev set (data.t3_dev_queries), not on test.
"""

from __future__ import annotations

import time

import numpy as np
import scipy.sparse as sp
import torch

from ml_pipeline.graph.baselines import Recommender, _docs
from ml_pipeline.graph.data import GraphData
from ml_pipeline.graph.metrics import recall_at_k, top_k_from_scores


def _sparse_tensor(m: sp.coo_matrix, device) -> torch.Tensor:
    idx = torch.tensor(np.vstack([m.row, m.col]), dtype=torch.long)
    return torch.sparse_coo_tensor(idx, torch.tensor(m.data, dtype=torch.float32), m.shape, device=device).coalesce()


class LightGCN(Recommender):
    name = "B3b LightGCN"

    def __init__(self, dim: int = 64, layers: int = 3, lr: float = 5e-3, epochs: int = 150, batch: int = 16384,
                 reg: float = 1e-4, patience: int = 8, val_queries: int = 2000, device: str | None = None):
        self.dim, self.layers, self.lr, self.epochs = dim, layers, lr, epochs
        self.batch, self.reg, self.patience, self.val_queries = batch, reg, patience, val_queries
        self.device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
        self.history: list[dict] = []

    def fit(self, data: GraphData, seed: int = 0) -> None:
        torch.manual_seed(seed)
        np.random.seed(seed)
        self.data = data
        R = _docs(data).tocoo()
        self.n_users, self.n_items = R.shape
        n = self.n_users + self.n_items
        A = sp.bmat([[None, R], [R.T, None]], format="coo").astype(np.float32)
        deg = np.asarray(A.sum(axis=1)).ravel()
        d_inv = np.power(np.maximum(deg, 1e-9), -0.5)
        d_inv[deg == 0] = 0.0
        A_hat = (sp.diags(d_inv) @ A @ sp.diags(d_inv)).tocoo()
        self.adj = _sparse_tensor(A_hat, self.device)
        self.emb = torch.nn.Parameter(torch.empty(n, self.dim, device=self.device))
        torch.nn.init.normal_(self.emb, std=0.1)
        opt = torch.optim.Adam([self.emb], lr=self.lr)

        users, items = R.row.astype(np.int64), R.col.astype(np.int64)
        user_items = R.tocsr()
        val_jobs = data.eval_jobs("val")
        rng = np.random.default_rng(seed)
        if len(val_jobs) > self.val_queries:
            val_jobs = rng.choice(val_jobs, self.val_queries, replace=False)

        best, best_state, bad = -1.0, None, 0
        for epoch in range(self.epochs):
            t0 = time.time()
            perm = rng.permutation(len(users))
            total = 0.0
            for s in range(0, len(perm), self.batch):
                b = perm[s:s + self.batch]
                u = torch.tensor(users[b], device=self.device)
                i = torch.tensor(items[b], device=self.device)
                j = torch.tensor(rng.integers(0, self.n_items, len(b)), device=self.device)
                out = self._propagate()
                eu, ei, ej = out[u], out[self.n_users + i], out[self.n_users + j]
                x = (eu * ei).sum(-1) - (eu * ej).sum(-1)
                reg = (self.emb[u].pow(2).sum() + self.emb[self.n_users + i].pow(2).sum()
                       + self.emb[self.n_users + j].pow(2).sum()) / len(b)
                loss = torch.nn.functional.softplus(-x).mean() + self.reg * reg
                opt.zero_grad()
                loss.backward()
                opt.step()
                total += float(loss) * len(b)
            val = self._val_recall(val_jobs, user_items)
            self.history.append({"epoch": epoch, "loss": total / len(perm), "val_recall@10": val,
                                 "seconds": round(time.time() - t0, 1)})
            if val > best:
                best, bad = val, 0
                best_state = self.emb.detach().clone()
            else:
                bad += 1
                if bad >= self.patience:
                    break
        with torch.no_grad():
            self.emb.copy_(best_state)
            self.final = self._propagate().detach()
        self.best_val = best
        self.item_deg = torch.tensor(np.asarray(R.tocsr().sum(axis=0)).ravel(), device=self.device,
                                     dtype=torch.float32).clamp(min=1.0)

    def _propagate(self) -> torch.Tensor:
        h = self.emb
        acc = h
        for _ in range(self.layers):
            h = torch.sparse.mm(self.adj, h)
            acc = acc + h
        return acc / (self.layers + 1)

    @torch.no_grad()
    def _val_recall(self, val_jobs: np.ndarray, user_items: sp.csr_matrix) -> float:
        out = self._propagate()
        scores = (out[torch.tensor(val_jobs, device=self.device)] @ out[self.n_users:].T).cpu().numpy()
        rec = []
        for r, j in enumerate(val_jobs):
            ranked = top_k_from_scores(scores[r], 10, exclude=user_items[j].indices)
            rec.append(recall_at_k(ranked, {int(h): 1 for h in self.data.hidden[int(j)]}, 10))
        return float(np.mean(rec))

    @torch.no_grad()
    def _users(self, rows: np.ndarray) -> np.ndarray:
        u = self.final[torch.tensor(rows, device=self.device)]
        return (u @ self.final[self.n_users:].T).cpu().numpy()

    def score_t1(self, jobs):
        return self._users(jobs)

    def score_t2(self, occs):
        return self._users(occs + self.data.n_jobs)

    @torch.no_grad()
    def _fold_in(self, queries: list[np.ndarray]) -> torch.Tensor:
        items = self.final[self.n_users:]
        out = []
        for q in queries:
            idx = torch.tensor(q, device=self.device)
            w = 1.0 / torch.sqrt(len(q) * self.item_deg[idx])
            out.append((items[idx] * w[:, None]).sum(0))
        return torch.stack(out)

    @torch.no_grad()
    def score_t3(self, queries, pool):
        q = torch.nn.functional.normalize(self._fold_in(queries), dim=1)
        jobs = torch.nn.functional.normalize(self.final[torch.tensor(pool, device=self.device)], dim=1)
        return (q @ jobs.T).cpu().numpy()

    @torch.no_grad()
    def score_skill_set(self, skills):
        q = self._fold_in([skills])
        return (q @ self.final[self.n_users:].T).cpu().numpy()[0]
