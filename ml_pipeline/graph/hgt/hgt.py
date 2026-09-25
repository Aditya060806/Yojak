# Copied verbatim from Vyuha (our team's repo): ml/graph/model/hgt.py
# https://github.com/TrombokenduShiv/Vyuha/blob/cef4a130bdd66e6499df27ab43f9eaa8357dfa76/ml/graph/model/hgt.py
# Vyuha has no licence file; this is our own code, reused by its authors. See CREDITS.md.
# Do not edit: Yojak-specific changes live in ml_pipeline/graph/hgt/model.py.
"""Multi-head temporal graph attention with reverse heterogeneous relations."""
import math
import torch
from torch import nn
from .temporal_encoder import TemporalEncoder


class HGTAttentionLayer(nn.Module):
    def __init__(self, in_dims, hidden_dim, num_heads, node_types, edge_types):
        super().__init__()
        if hidden_dim % num_heads:
            raise ValueError("hidden_dim must be divisible by num_heads")
        self.hidden_dim, self.num_heads, self.d_k = hidden_dim, num_heads, hidden_dim // num_heads
        self.node_types, self.edge_types = node_types, edge_types
        self.input_proj = nn.ModuleDict({n: nn.Linear(in_dims[n], hidden_dim) for n in node_types})
        self.q_proj = nn.ModuleDict({n: nn.Linear(hidden_dim, hidden_dim) for n in node_types})
        self.k_proj = nn.ModuleDict({"__".join(r): nn.Linear(hidden_dim, hidden_dim) for r in edge_types})
        self.v_proj = nn.ModuleDict({"__".join(r): nn.Linear(hidden_dim, hidden_dim) for r in edge_types})
        self.output_proj = nn.ModuleDict({n: nn.Linear(hidden_dim, hidden_dim) for n in node_types})
        self.norm = nn.ModuleDict({n: nn.LayerNorm(hidden_dim) for n in node_types})

    def forward(self, node_features, edge_index, edge_temporal_emb=None):
        h = {n: self.input_proj[n](node_features[n]) for n in self.node_types}
        messages = {n: [] for n in self.node_types}
        for rel in self.edge_types:
            if rel not in edge_index or edge_index[rel].shape[1] == 0:
                continue
            src, _, dst = rel
            s, d = edge_index[rel]
            key = "__".join(rel)
            k, v = self.k_proj[key](h[src][s]), self.v_proj[key](h[src][s])
            if edge_temporal_emb and rel in edge_temporal_emb:
                k, v = k + edge_temporal_emb[rel], v + edge_temporal_emb[rel]
            q = self.q_proj[dst](h[dst][d]).reshape(-1, self.num_heads, self.d_k)
            logits = (q * k.reshape(-1, self.num_heads, self.d_k)).sum(-1) / math.sqrt(self.d_k)
            destination = d[:, None].expand(-1, self.num_heads)
            maxima = logits.new_full((len(h[dst]), self.num_heads), -torch.inf)
            maxima.scatter_reduce_(0, destination, logits.detach(), reduce="amax", include_self=True)
            weights = (logits - maxima[d]).exp()
            denom = weights.new_zeros(maxima.shape)
            denom.scatter_add_(0, destination, weights)
            weights = weights / denom[d].clamp_min(1e-12)
            msg = (weights[:, :, None] * v.reshape(-1, self.num_heads, self.d_k)).flatten(1)
            aggregate = msg.new_zeros((len(h[dst]), self.hidden_dim))
            aggregate.index_add_(0, d, msg)
            messages[dst].append((aggregate, denom.sum(-1, keepdim=True).gt(0).float()))
        result = {}
        for n in self.node_types:
            if messages[n]:
                aggregate = sum(m for m, _ in messages[n])
                count = sum(p for _, p in messages[n]).clamp_min(1)
                result[n] = self.norm[n](h[n] + self.output_proj[n](aggregate / count))
            else:
                result[n] = self.norm[n](h[n])
        return result


class HGTModel(nn.Module):
    NODE_TYPES = ["account", "vpa", "device", "phone"]
    BASE_EDGES = [("account", "sends_to", "account"), ("vpa", "receives_from", "vpa"),
                  ("account", "owns", "vpa"), ("device", "accesses", "account"),
                  ("phone", "associated_with", "account")]
    EDGE_TYPES = BASE_EDGES + [(d, "rev_" + r, s) for s, r, d in BASE_EDGES]

    def __init__(self, feature_dims=None, hidden_dim=32, num_heads=4, num_layers=2, dropout=0.1):
        super().__init__()
        feature_dims = feature_dims or {"account": 8, "vpa": 4, "device": 4, "phone": 4}
        self.hidden_dim, self.num_layers = hidden_dim, num_layers
        self.temporal_encoder = TemporalEncoder(hidden_dim)
        self.amount_encoder = nn.Linear(1, hidden_dim)
        self.layers = nn.ModuleList([HGTAttentionLayer(
            feature_dims if i == 0 else {n: hidden_dim for n in self.NODE_TYPES},
            hidden_dim, num_heads, self.NODE_TYPES, self.EDGE_TYPES) for i in range(num_layers)])
        self.dropout = nn.Dropout(dropout)
        self.classifier = nn.Sequential(nn.Linear(hidden_dim, hidden_dim // 2), nn.GELU(),
                                        nn.Linear(hidden_dim // 2, 1))
        self.register_buffer("temperature", torch.tensor(1.0))

    def forward(self, node_features, edge_index, edge_attr=None):
        temporal = {}
        for r, attrs in (edge_attr or {}).items():
            if len(attrs):
                temporal[r] = self.temporal_encoder(torch.log1p(attrs[:, 0].clamp_min(0))) + self.amount_encoder(attrs[:, 1:2])
        h = node_features
        for layer in self.layers:
            h = {n: self.dropout(v) for n, v in layer(h, edge_index, temporal).items()}
        logits = self.classifier(h["account"]).squeeze(-1)
        scores = torch.sigmoid(logits / self.temperature.clamp_min(0.05))
        # Certainty proxy, not a learned accuracy head or a coverage guarantee.
        return {"risk_logits": logits, "risk_scores": scores, "confidence": (2 * scores - 1).abs(),
                "embeddings": h["account"]}
