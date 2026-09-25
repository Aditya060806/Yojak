# ml_pipeline/graph/hgt/model.py

"""
M: Heterogeneous Graph Transformer for Yojak, built on Vyuha's HGTAttentionLayer
(ml_pipeline/graph/hgt/hgt.py, unchanged).

Rewritten from Vyuha's HGTModel as the team specified:
  NODE_TYPES  job, skill, company, city, occupation, exp_band
  BASE_EDGES  (job,requires,skill) (company,posts,job) (job,located_in,city)
              (occupation,requires,skill) (job,maps_to,occupation) (job,needs_exp,exp_band)
              + automatic rev_ edges
  amount_encoder removed; the account-risk classifier is replaced by link heads:
    (job, skill)        DistMult + per-skill bias, BPR loss
    (occupation, skill) DistMult + per-skill bias, BPR loss
    (candidate, job)    projection + cosine, InfoNCE over in-batch jobs
  TemporalEncoder only when use_time=True (posting dates are real in this data,
  so time is an ablation, not the default).

Training (adapted from Vyuha train_hgt.py): AdamW + cosine LR, early stopping.
Each epoch re-splits the known train edges into message-passing (80%) and
supervision (20%) so the model never learns to spot an edge it is passed.
"Context dropout" hides title/company/city/occupation/experience for 30% of jobs
per epoch so skills-only nodes (a new candidate) look like jobs the model saw.

Candidates are encoded inductively: a new job-type node linked only to its skills,
passed through the same layers using the full graph's cached skill states.

Readout (jumping knowledge, Xu et al. 2018): every job/occupation/candidate is
represented as [h_L ; mean of a learned projection of its skills' input features],
and every skill as [h_L ; projection of its own features]. Without it, two layers of
attention averaged over up to five relation types washed out the skill set
(dev T3 NDCG 0.015 vs 0.45 for a plain mean of skill text embeddings).
"""

from __future__ import annotations

import math
import time

import numpy as np
import torch
from torch import nn

from ml_pipeline.graph.baselines import Recommender
from ml_pipeline.graph.data import GraphData
from ml_pipeline.graph.hgt.hgt import HGTAttentionLayer
from ml_pipeline.graph.hgt.temporal_encoder import TemporalEncoder
from ml_pipeline.graph.metrics import ndcg_at_k, recall_at_k, top_k_from_scores

ALL_NODE_TYPES = ["job", "skill", "company", "city", "occupation", "exp_band"]
ALL_BASE_EDGES = [
    ("job", "requires", "skill"),
    ("company", "posts", "job"),
    ("job", "located_in", "city"),
    ("occupation", "requires", "skill"),
    ("job", "maps_to", "occupation"),
    ("job", "needs_exp", "exp_band"),
]
EXP_BANDS = ["0-1", "1-3", "3-6", "6-10", "10+"]
QUERY_REL = ("skill", "rev_requires", "job")


def _rev(edges):
    return edges + [(d, "rev_" + r, s) for s, r, d in edges]


class YojakHGT(nn.Module):
    def __init__(self, feat_dims: dict[str, int], n_company: int, n_city: int, hidden: int = 64, heads: int = 4,
                 layers: int = 2, dropout: float = 0.1, use_context: bool = True, use_time: bool = False,
                 n_skills: int = 0):
        super().__init__()
        self.node_types = ALL_NODE_TYPES if use_context else ["job", "skill", "occupation", "exp_band"]
        base = [e for e in ALL_BASE_EDGES if e[0] in self.node_types and e[2] in self.node_types]
        self.edge_types = _rev(base)
        self.use_time = use_time
        self.company_emb = nn.Embedding(max(n_company, 1), 32)
        self.city_emb = nn.Embedding(max(n_city, 1), 16)
        self.exp_emb = nn.Embedding(len(EXP_BANDS), 8)
        in_dims = {"job": feat_dims["job"], "skill": feat_dims["skill"], "occupation": feat_dims["occupation"],
                   "company": 32, "city": 16 + 4, "exp_band": 8}
        in_dims = {n: in_dims[n] for n in self.node_types}
        self.layers = nn.ModuleList([
            HGTAttentionLayer(in_dims if i == 0 else {n: hidden for n in self.node_types},
                              hidden, heads, self.node_types, self.edge_types)
            for i in range(layers)
        ])
        self.dropout = nn.Dropout(dropout)
        self.temporal = TemporalEncoder(hidden) if use_time else None
        self.bag = nn.Linear(feat_dims["skill"], hidden)
        self.r_js = nn.Parameter(torch.ones(2 * hidden))
        self.r_os = nn.Parameter(torch.ones(2 * hidden))
        self.b_skill = nn.Parameter(torch.zeros(max(n_skills, 1)))
        self.proj = nn.Sequential(nn.Linear(2 * hidden, 2 * hidden), nn.GELU(), nn.Linear(2 * hidden, hidden))
        # Weight of the learned (candidate, job) correction on top of the fixed text prior.
        self.cj_weight = nn.Parameter(torch.zeros(()))
        self.register_buffer("temperature", torch.tensor(1.0))  # calibration (fit after training)

    def input_features(self, x: dict[str, torch.Tensor], city_tier: torch.Tensor) -> dict[str, torch.Tensor]:
        feats = {"job": x["job"].float(), "skill": x["skill"].float(), "occupation": x["occupation"].float(),
                 "exp_band": self.exp_emb.weight}
        if "company" in self.node_types:
            feats["company"] = self.company_emb.weight
            feats["city"] = torch.cat([self.city_emb.weight, city_tier], dim=1)
        return feats

    def forward(self, feats: dict[str, torch.Tensor], edge_index: dict, edge_time: dict | None = None):
        """Returns per-layer node states: [inputs, layer1, ..., layerL]."""
        temporal = None
        if self.temporal is not None and edge_time:
            temporal = {r: self.temporal(torch.log1p(t.clamp_min(0))) for r, t in edge_time.items() if len(t)}
        states = [feats]
        h = feats
        for layer in self.layers:
            h = {n: self.dropout(v) for n, v in layer(h, edge_index, temporal).items()}
            states.append(h)
        return states

    def encode_new_jobs(self, states: list[dict], skill_lists: list[torch.Tensor]) -> torch.Tensor:
        """Inductive encoding of skills-only job nodes (candidates) against cached skill states."""
        device = states[0]["skill"].device
        uniq, inverse = torch.unique(torch.cat(skill_lists), return_inverse=True)
        dst = torch.cat([torch.full((len(s),), i, device=device, dtype=torch.long) for i, s in enumerate(skill_lists)])
        edges = {QUERY_REL: torch.stack([inverse, dst])}
        times = {QUERY_REL: torch.zeros(len(dst), device=device)} if self.temporal is not None else None
        temporal = {r: self.temporal(t) for r, t in times.items()} if times else None
        q = torch.zeros(len(skill_lists), states[0]["job"].shape[1], device=device)
        for li, layer in enumerate(self.layers):
            prev = states[li]
            feats = {n: prev[n][:0] for n in self.node_types}
            feats["job"] = q
            feats["skill"] = prev["skill"][uniq]
            q = self.dropout(layer(feats, edges, temporal)["job"])
        return q

    def skill_bag(self, x_skill: torch.Tensor) -> torch.Tensor:
        return self.bag(x_skill.float())

    def score_job_skill(self, h_job, h_skill):
        return (h_job * self.r_js) @ h_skill.T + self.b_skill

    def score_occ_skill(self, h_occ, h_skill):
        return (h_occ * self.r_os) @ h_skill.T + self.b_skill

    def score_candidate_job(self, q, h_job):
        zq = nn.functional.normalize(self.proj(q), dim=-1)
        zj = nn.functional.normalize(self.proj(h_job), dim=-1)
        return zq @ zj.T


class HGTRecommender(Recommender):
    name = "M HGT (Vyuha)"

    def __init__(self, hidden: int = 64, heads: int = 4, num_layers: int = 2, lr: float = 3e-3, epochs: int = 40,
                 steps_per_epoch: int = 25, js_batch: int = 32768, os_batch: int = 8192, cand_batch: int = 1024,
                 context_dropout: float = 0.3, eval_every: int = 2, patience: int = 4, use_context: bool = True,
                 use_time: bool = False, amp: bool = True, device: str | None = None):
        self.cfg = dict(hidden=hidden, heads=heads, num_layers=num_layers, lr=lr, epochs=epochs,
                        steps_per_epoch=steps_per_epoch, js_batch=js_batch, os_batch=os_batch,
                        cand_batch=cand_batch, context_dropout=context_dropout, use_context=use_context,
                        use_time=use_time)
        self.eval_every, self.patience = eval_every, patience
        # bf16 autocast for the training forward pass (activations dominate GPU memory).
        self.amp = amp and torch.cuda.is_available()
        self.device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
        self.history: list[dict] = []
        self.supports_t2 = True

    # --- graph construction ------------------------------------------------------------------

    def _build(self, data: GraphData) -> None:
        from ml_pipeline.graph.hgt.features import node_features

        dev = self.device
        jobs = data.jobs
        feats = node_features(data)
        self.x = {k: torch.tensor(v, device=dev) for k, v in feats.items()}

        if data.occupations:
            occ_ids = data.occupations
        else:
            from ml_pipeline.graph.data import _esco_occupations

            occ_ids = _esco_occupations()[0]["conceptUri"].tolist()
        occ_idx = {o: i for i, o in enumerate(occ_ids)}
        comp = jobs["companyName"].fillna("").str.lower().str.strip()
        comp_ids = {c: i for i, c in enumerate(sorted(set(comp) - {""}))}
        city_key = jobs["primary_city"].fillna("") + "|" + jobs["primary_state"].fillna("")
        city_ids = {c: i for i, c in enumerate(sorted(set(city_key[jobs["primary_city"].notna()])))}
        tier_by_city = np.zeros((max(len(city_ids), 1), 4), dtype=np.float32)
        for key, tier in zip(city_key, jobs["primary_tier"], strict=True):
            if key in city_ids:
                t = int(tier) - 1 if tier == tier and tier in (1, 2, 3) else 3
                tier_by_city[city_ids[key], t] = 1.0
        self.city_tier = torch.tensor(tier_by_city, device=dev)
        self.n_company, self.n_city = len(comp_ids), len(city_ids)

        def arr(pairs):
            return np.array(pairs, dtype=np.int64).reshape(-1, 2).T if pairs else np.zeros((2, 0), dtype=np.int64)

        jidx = jobs["jidx"].to_numpy()
        self.ctx = {
            ("company", "posts", "job"): arr([(comp_ids[c], j) for c, j in zip(comp, jidx, strict=True) if c in comp_ids]),
            ("job", "located_in", "city"): arr([(j, city_ids[k]) for j, k in zip(jidx, city_key, strict=True) if k in city_ids]),
            ("job", "maps_to", "occupation"): arr([(j, occ_idx[o]) for j, o in zip(jidx, jobs["occupation_uri"], strict=True)
                                                   if o in occ_idx]),
            ("job", "needs_exp", "exp_band"): arr([(j, EXP_BANDS.index(b)) for j, b in zip(jidx, jobs["exp_band"], strict=True)
                                                  if b in EXP_BANDS]),
        }
        k = data.known.tocoo()
        self.js_all = np.vstack([k.row, k.col]).astype(np.int64)
        train_mask = jobs["split"].to_numpy()[k.row] == "train"
        self.js_train = self.js_all[:, train_mask]
        self.js_fixed = self.js_all[:, ~train_mask]
        if data.occ_known is not None:
            o = data.occ_known.tocoo()
            self.os_all = np.vstack([o.row, o.col]).astype(np.int64)
        else:
            self.os_all = np.zeros((2, 0), dtype=np.int64)
        days = jobs["days_ago"].to_numpy(dtype=float)
        self.job_age = torch.tensor(np.nan_to_num(days, nan=15.0), dtype=torch.float32, device=dev)
        pop = np.asarray(data.known.sum(axis=0)).ravel() + 1.0
        self.neg_p = torch.tensor(pop ** 0.75 / (pop ** 0.75).sum(), dtype=torch.float32, device=dev)
        self.train_jobs = jobs.loc[jobs["split"] == "train", "jidx"].to_numpy()
        self.job_skill_lists = [data.known[j].indices for j in range(data.n_jobs)]
        xs = feats["skill"].astype(np.float32)
        prior = np.asarray(data.known.multiply(1.0 / np.maximum(data.known.sum(axis=1), 1)).tocsr() @ xs)
        prior /= np.maximum(np.linalg.norm(prior, axis=1, keepdims=True), 1e-9)
        self.job_prior = torch.tensor(prior, dtype=torch.float16, device=dev)

    def _edge_index(self, js: np.ndarray, os_: np.ndarray, drop_jobs: np.ndarray | None) -> tuple[dict, dict]:
        dev = self.device
        rels = {("job", "requires", "skill"): js, ("occupation", "requires", "skill"): os_}
        for rel, e in self.ctx.items():
            if rel[0] in self.model.node_types and rel[2] in self.model.node_types:
                if drop_jobs is not None and len(e[0]):
                    job_row = 1 if rel[2] == "job" else 0
                    e = e[:, ~np.isin(e[job_row], drop_jobs)]
                rels[rel] = e
        edge_index, edge_time = {}, {}
        for (s, r, d), e in rels.items():
            t = torch.tensor(e, device=dev)
            edge_index[(s, r, d)] = t
            edge_index[(d, "rev_" + r, s)] = t.flip(0)
            if self.cfg["use_time"] and "job" in (s, d):
                job_row = 0 if s == "job" else 1
                age = self.job_age[t[job_row]]
                edge_time[(s, r, d)] = age
                edge_time[(d, "rev_" + r, s)] = age
        return edge_index, edge_time

    def _mean_adj(self, edges: np.ndarray, n_rows: int, n_cols: int) -> torch.Tensor:
        rows, cols = edges
        deg = np.bincount(rows, minlength=n_rows).astype(np.float32)
        vals = 1.0 / np.maximum(deg[rows], 1.0)
        idx = torch.tensor(np.vstack([rows, cols]), dtype=torch.long)
        return torch.sparse_coo_tensor(idx, torch.tensor(vals), (n_rows, n_cols), device=self.device).coalesce()

    def _readout(self, states: list[dict], js: np.ndarray, os_: np.ndarray) -> dict[str, torch.Tensor]:
        """Jumping-knowledge readout: [h_L ; pooled projection of the node's skill features]."""
        h = states[-1]
        bags = self.model.skill_bag(self.x["skill"])
        n_occ = h["occupation"].shape[0]
        job_bag = torch.sparse.mm(self._mean_adj(js, self.data.n_jobs, self.data.n_skills), bags)
        occ_bag = torch.sparse.mm(self._mean_adj(os_, n_occ, self.data.n_skills), bags)
        return {"job": torch.cat([h["job"], job_bag], 1), "skill": torch.cat([h["skill"], bags], 1),
                "occupation": torch.cat([h["occupation"], occ_bag], 1)}

    def _query_readout(self, states: list[dict], sets: list[torch.Tensor]) -> torch.Tensor:
        q = self.model.encode_new_jobs(states, sets)
        bags = self.model.skill_bag(self.x["skill"])
        return torch.cat([q, torch.stack([bags[s].mean(0) for s in sets])], 1)

    def _set_prior(self, sets: list[torch.Tensor]) -> torch.Tensor:
        """Fixed prior for (candidate, job): normalised mean of pretrained skill-text embeddings."""
        x = self.x["skill"]
        return nn.functional.normalize(torch.stack([x[s].float().mean(0) for s in sets]), dim=1)

    def _cand_job_score(self, q, q_prior, jobs: torch.Tensor) -> torch.Tensor:
        """Residual scoring: fixed text prior + learned graph correction (weight starts at 0)."""
        prior = q_prior @ self.job_prior[jobs].float().T
        return prior + self.model.cj_weight * self.model.score_candidate_job(q, self.h_job_for_cj[jobs])

    def _feats(self, hide_jobs: np.ndarray | None = None) -> dict:
        x = dict(self.x)
        if hide_jobs is not None and len(hide_jobs):
            job = x["job"].clone()
            job[torch.tensor(hide_jobs, device=self.device)] = 0
            x["job"] = job
        return self.model.input_features(x, self.city_tier)

    # --- training --------------------------------------------------------------------------------

    def fit(self, data: GraphData, seed: int = 0) -> None:
        torch.manual_seed(seed)
        rng = np.random.default_rng(seed)
        self.data = data
        self._build(data)
        dims = {k: v.shape[1] for k, v in self.x.items()}
        self.model = YojakHGT(dims, self.n_company, self.n_city, hidden=self.cfg["hidden"], heads=self.cfg["heads"],
                              layers=self.cfg["num_layers"], use_context=self.cfg["use_context"],
                              use_time=self.cfg["use_time"], n_skills=data.n_skills).to(self.device)
        with torch.no_grad():  # start from the popularity prior instead of zero
            pop = np.asarray(data.known.sum(axis=0)).ravel() + 1.0
            self.model.b_skill.copy_(torch.tensor(np.log(pop) - np.log(pop).mean(), dtype=torch.float32))
        opt = torch.optim.AdamW(self.model.parameters(), lr=self.cfg["lr"], weight_decay=1e-4)
        sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=self.cfg["epochs"])
        cand_jobs = np.array([j for j in self.train_jobs if len(self.job_skill_lists[j]) >= 3])
        val_jobs = data.eval_jobs("val")
        if len(val_jobs) > 2000:
            val_jobs = rng.choice(val_jobs, 2000, replace=False)

        best, best_state, bad = -1.0, None, 0
        for epoch in range(self.cfg["epochs"]):
            t0 = time.time()
            self.model.train()
            m_js = rng.random(self.js_train.shape[1]) < 0.8
            m_os = rng.random(self.os_all.shape[1]) < 0.8
            mp_js = np.hstack([self.js_train[:, m_js], self.js_fixed])
            sup_js = self.js_train[:, ~m_js]
            sup_os = self.os_all[:, ~m_os]
            hide = rng.choice(data.n_jobs, int(self.cfg["context_dropout"] * data.n_jobs), replace=False)
            edge_index, edge_time = self._edge_index(mp_js, self.os_all[:, m_os], hide)
            losses = []
            for _ in range(self.cfg["steps_per_epoch"]):
                with torch.autocast("cuda", dtype=torch.bfloat16, enabled=self.amp):
                    states = self.model(self._feats(hide), edge_index, edge_time)
                states = [{k: v.float() for k, v in st.items()} for st in states]
                h = self._readout(states, mp_js, self.os_all[:, m_os])
                loss = self._bpr(h["job"], h["skill"], sup_js, self.cfg["js_batch"], rng, self.model.r_js)
                if sup_os.shape[1]:
                    loss = loss + 0.5 * self._bpr(h["occupation"], h["skill"], sup_os, self.cfg["os_batch"], rng,
                                                  self.model.r_os)
                with torch.autocast("cuda", dtype=torch.bfloat16, enabled=self.amp):
                    loss = loss + self._infonce(states, h, cand_jobs, rng).float()
                opt.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), 5.0)
                opt.step()
                losses.append(float(loss))
            sched.step()
            rec = {"epoch": epoch, "loss": round(float(np.mean(losses)), 4), "seconds": round(time.time() - t0, 1)}
            if (epoch + 1) % self.eval_every == 0:
                self._refresh()
                v1, v3 = self._validate(val_jobs)
                rec.update({"val_t1_recall@10": round(v1, 4), "dev_t3_ndcg@10": round(v3, 4)})
                score = (v1 + v3) / 2
                if score > best:
                    best, bad = score, 0
                    best_state = {k: v.detach().clone() for k, v in self.model.state_dict().items()}
                else:
                    bad += 1
            self.history.append(rec)
            if bad >= self.patience:
                break
        if best_state is not None:
            self.model.load_state_dict(best_state)
        self._refresh()
        self.best_val = best
        self._calibrate(data, rng)

    def _bpr(self, h_src, h_skill, pos, batch, rng, rel_vec):
        if pos.shape[1] == 0:
            return torch.zeros((), device=self.device)
        idx = rng.choice(pos.shape[1], min(batch, pos.shape[1]), replace=False)
        src = torch.tensor(pos[0, idx], device=self.device)
        dst = torch.tensor(pos[1, idx], device=self.device)
        half = len(idx) // 2
        neg = torch.cat([torch.randint(0, h_skill.shape[0], (half,), device=self.device),
                         torch.multinomial(self.neg_p, len(idx) - half, replacement=True)])
        hs = h_src[src] * rel_vec
        pos_s = (hs * h_skill[dst]).sum(-1) + self.model.b_skill[dst]
        neg_s = (hs * h_skill[neg]).sum(-1) + self.model.b_skill[neg]
        return nn.functional.softplus(neg_s - pos_s).mean()

    def _sample_candidates(self, jobs: np.ndarray, rng) -> list[np.ndarray]:
        out = []
        for j in jobs:
            own = self.job_skill_lists[j]
            k = max(2, int(round(rng.uniform(0.4, 0.7) * len(own))))
            sub = rng.choice(own, size=k, replace=False)
            noise = rng.integers(0, self.data.n_skills, 2)
            out.append(np.concatenate([sub, noise]))
        return out

    def _infonce(self, states, h, cand_jobs, rng):
        if not len(cand_jobs):
            return torch.zeros((), device=self.device)
        jobs = rng.choice(cand_jobs, min(self.cfg["cand_batch"], len(cand_jobs)), replace=False)
        sets = [torch.tensor(s, device=self.device) for s in self._sample_candidates(jobs, rng)]
        q = self._query_readout(states, sets)
        self.h_job_for_cj = h["job"]
        logits = self._cand_job_score(q, self._set_prior(sets), torch.tensor(jobs, device=self.device)) / 0.07
        return nn.functional.cross_entropy(logits, torch.arange(len(jobs), device=self.device))

    # --- inference ---------------------------------------------------------------------------------

    @torch.no_grad()
    def _refresh(self) -> None:
        """Full-graph states with ALL known edges, no dropout: used for every score."""
        self.model.eval()
        edge_index, edge_time = self._edge_index(self.js_all, self.os_all, None)
        self.states = self.model(self._feats(None), edge_index, edge_time)
        self.h = self._readout(self.states, self.js_all, self.os_all)

    @torch.no_grad()
    def _validate(self, val_jobs) -> tuple[float, float]:
        s = self.score_t1(val_jobs)
        rec = [recall_at_k(top_k_from_scores(s[i], 10, exclude=self.data.known[j].indices),
                           {int(x): 1 for x in self.data.hidden[int(j)]}) for i, j in enumerate(val_jobs)]
        pool = self.data.t3_dev_pool
        pos = {int(j): i for i, j in enumerate(pool)}
        qs = self.data.t3_dev_queries
        sc = self.score_t3([q["skills"] for q in qs], pool)
        nd = [ndcg_at_k(top_k_from_scores(sc[i], 10), {pos[j]: g for j, g in q["relevance"].items() if j in pos})
              for i, q in enumerate(qs)]
        return float(np.mean(rec)), float(np.mean(nd))

    @torch.no_grad()
    def _calibrate(self, data: GraphData, rng) -> None:
        """Temperature scaling of job-skill probabilities on val hidden edges vs sampled negatives."""
        val = [j for j in data.eval_jobs("val")][:3000]
        pos = [(j, s) for j in val for s in data.hidden[int(j)]]
        if not pos:
            return
        src = torch.tensor([p[0] for p in pos], device=self.device)
        dst = torch.tensor([p[1] for p in pos], device=self.device)
        neg = torch.randint(0, data.n_skills, (len(pos),), device=self.device)
        hs = self.h["job"][src] * self.model.r_js
        logits = torch.cat([(hs * self.h["skill"][dst]).sum(-1) + self.model.b_skill[dst],
                            (hs * self.h["skill"][neg]).sum(-1) + self.model.b_skill[neg]])
        y = torch.cat([torch.ones(len(pos)), torch.zeros(len(pos))]).to(self.device)
        best_t, best_nll = 1.0, math.inf
        for t in np.exp(np.linspace(np.log(0.01), np.log(100), 120)):
            nll = float(nn.functional.binary_cross_entropy_with_logits(logits / t, y))
            if nll < best_nll:
                best_t, best_nll = float(t), nll
        self.model.temperature.fill_(best_t)
        p = torch.sigmoid(logits / best_t).cpu().numpy()
        self.calibration = {"temperature": round(best_t, 4), "val_nll": round(best_nll, 4),
                            "val_ece": round(expected_calibration_error(p, y.cpu().numpy()), 4)}

    @torch.no_grad()
    def score_t1(self, jobs):
        h = self.h["job"][torch.tensor(jobs, device=self.device)]
        return self.model.score_job_skill(h, self.h["skill"]).cpu().numpy()

    @torch.no_grad()
    def score_t2(self, occs):
        h = self.h["occupation"][torch.tensor(occs, device=self.device)]
        return self.model.score_occ_skill(h, self.h["skill"]).cpu().numpy()

    @torch.no_grad()
    def _encode(self, queries):
        return self._query_readout(self.states, [torch.tensor(q, device=self.device) for q in queries])

    @torch.no_grad()
    def score_t3(self, queries, pool):
        sets = [torch.tensor(q, device=self.device) for q in queries]
        q = self._query_readout(self.states, sets)
        self.h_job_for_cj = self.h["job"]
        return self._cand_job_score(q, self._set_prior(sets), torch.tensor(pool, device=self.device)).float().cpu().numpy()

    @torch.no_grad()
    def score_skill_set(self, skills):
        return self.model.score_job_skill(self._encode([skills]), self.h["skill"]).cpu().numpy()[0]

    @torch.no_grad()
    def skill_probabilities(self, skills) -> np.ndarray:
        """Calibrated P(skill is required) for a free skill set (used in the API)."""
        logits = self.score_skill_set(skills)
        return 1.0 / (1.0 + np.exp(-logits / float(self.model.temperature)))


def expected_calibration_error(p: np.ndarray, y: np.ndarray, bins: int = 15) -> float:
    edges = np.linspace(0, 1, bins + 1)
    ece = 0.0
    for lo, hi in zip(edges[:-1], edges[1:], strict=True):
        m = (p >= lo) & (p < hi) if hi < 1 else (p >= lo) & (p <= hi)
        if m.any():
            ece += m.mean() * abs(p[m].mean() - y[m].mean())
    return float(ece)
