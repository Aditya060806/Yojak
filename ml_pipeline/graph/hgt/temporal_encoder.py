# Copied verbatim from Vyuha (our team's repo): ml/graph/model/temporal_encoder.py
# https://github.com/TrombokenduShiv/Vyuha/blob/cef4a130bdd66e6499df27ab43f9eaa8357dfa76/ml/graph/model/temporal_encoder.py
# Vyuha has no licence file; this is our own code, reused by its authors. See CREDITS.md.
# Do not edit: Yojak-specific changes live in ml_pipeline/graph/hgt/model.py.
"""
Vyuha 2.0 — Temporal Position Encoder
=======================================
Time2Vec-style sinusoidal encoding of edge timestamps.
Encodes absolute timestamps and relative time deltas into
a fixed-dimensional vector for the HGT message passing layers.

Architecture ref: ADR-003, ARCHITECTURE_FREEZE_V1 §5 D5.
"""
import torch
import torch.nn as nn
import numpy as np


class TemporalEncoder(nn.Module):
    """
    Sinusoidal temporal encoding inspired by Time2Vec.

    Maps a scalar timestamp t to a d-dimensional vector:
        TE(t) = [sin(w1*t + b1), cos(w1*t + b1), sin(w2*t + b2), ..., t_linear]

    The first element is a learned linear projection; the rest are
    periodic activations at learned frequencies.
    """

    def __init__(self, d_model: int = 16):
        super().__init__()
        self.d_model = d_model

        # Learned linear component
        self.linear_weight = nn.Linear(1, 1)

        # Learned periodic components (d_model - 1 frequencies)
        self.periodic_weight = nn.Linear(1, d_model - 1)

    def forward(self, t: torch.Tensor) -> torch.Tensor:
        """
        Args:
            t: Tensor of shape (...,) or (..., 1) — normalized timestamps [0, 1].

        Returns:
            Tensor of shape (..., d_model) — temporal embeddings.
        """
        if t.dim() == 1:
            t = t.unsqueeze(-1)

        # Linear component
        linear = self.linear_weight(t)  # (..., 1)

        # Periodic components
        periodic = torch.sin(self.periodic_weight(t))  # (..., d_model - 1)

        return torch.cat([linear, periodic], dim=-1)  # (..., d_model)


class RelativeTemporalEncoder(nn.Module):
    """
    Encodes relative time deltas between connected nodes.
    Useful for capturing transaction velocity and burst patterns.
    """

    def __init__(self, d_model: int = 16, num_frequencies: int = 8):
        super().__init__()
        self.d_model = d_model

        # Fixed sinusoidal frequencies (like Transformer positional encoding)
        freqs = torch.exp(torch.arange(0, num_frequencies, dtype=torch.float32) *
                          -(np.log(10000.0) / num_frequencies))
        self.register_buffer("freqs", freqs)

        # Projection to d_model
        self.proj = nn.Linear(num_frequencies * 2, d_model)

    def forward(self, delta_t: torch.Tensor) -> torch.Tensor:
        """
        Args:
            delta_t: Tensor of shape (...,) — time deltas (seconds, normalized).

        Returns:
            Tensor of shape (..., d_model).
        """
        if delta_t.dim() == 1:
            delta_t = delta_t.unsqueeze(-1)

        # Apply sinusoidal encoding at multiple frequencies
        angles = delta_t * self.freqs  # (..., num_frequencies)
        encoding = torch.cat([torch.sin(angles), torch.cos(angles)], dim=-1)

        return self.proj(encoding)


if __name__ == "__main__":
    print("Testing TemporalEncoder...")
    enc = TemporalEncoder(d_model=16)
    t = torch.tensor([0.0, 0.25, 0.5, 0.75, 1.0])
    out = enc(t)
    print(f"  Input shape: {t.shape}")
    print(f"  Output shape: {out.shape}")
    assert out.shape == (5, 16), f"Expected (5, 16), got {out.shape}"

    print("\nTesting RelativeTemporalEncoder...")
    rel_enc = RelativeTemporalEncoder(d_model=16)
    dt = torch.tensor([0.0, 0.01, 0.1, 1.0, 10.0])
    out_rel = rel_enc(dt)
    print(f"  Input shape: {dt.shape}")
    print(f"  Output shape: {out_rel.shape}")
    assert out_rel.shape == (5, 16), f"Expected (5, 16), got {out_rel.shape}"

    print("\n[PASS] All temporal encoder tests passed.")
