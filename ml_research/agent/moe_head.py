"""
Soft Mixture-of-Experts head for the regime-conditioned DQN (Section 11.6).

Stretch architecture used in the five-way ablation table (Section 11.8).
A small gating network reads the regime membership vector and produces
convex weights over N expert sub-networks that share a common trunk.

The whole module is end-to-end trainable with the same Double-DQN loss
used elsewhere in Helios-X. The only thing that changes versus the plain
regime-conditioned model is that the policy class is more flexible —
each expert can specialise on a regime cluster, and the gate learns
which expert to trust at each fingerprint.

Why this is a stretch goal and not the primary architecture
-----------------------------------------------------------
The plain regime-conditioned single model (regime_conditioned_network.py)
is simpler, has fewer parameters, and is the recommended baseline.
This MoE head is included for the IEEE ablation table to answer the
research question "does explicit gating help over implicit conditioning?"
"""

from __future__ import annotations

from typing import Sequence

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
except Exception:  # pragma: no cover
    torch = None  # type: ignore


class _MLP(nn.Module if torch is not None else object):
    def __init__(self, in_dim: int, hidden: Sequence[int], out_dim: int):
        super().__init__()  # type: ignore[misc]
        layers: list[nn.Module] = []
        prev = in_dim
        for h in hidden:
            layers += [nn.Linear(prev, h), nn.ReLU()]
            prev = h
        layers.append(nn.Linear(prev, out_dim))
        self.net = nn.Sequential(*layers)

    def forward(self, x):
        return self.net(x)


class SoftMoEQNetwork(nn.Module if torch is not None else object):
    """
    Shared trunk + N expert heads + soft gate over the regime vector.

    Forward pass:
        h    = trunk(state || regime)             # shared representation
        q_e  = expert_e(h)  for e in 1..E         # per-expert Q-values
        w    = softmax(gate(regime) / temperature) # convex weights
        q    = sum_e w_e * q_e                    # convex combination
    """

    def __init__(
        self,
        base_state_dim: int = 14,
        n_regimes: int = 10,
        action_dim: int = 13,
        n_experts: int = 4,
        trunk_hidden: Sequence[int] = (128, 128),
        expert_hidden: Sequence[int] = (64,),
        gate_hidden: Sequence[int] = (32,),
        gate_temperature: float = 1.0,
    ):
        super().__init__()  # type: ignore[misc]
        in_dim = base_state_dim + n_regimes
        self.n_regimes = n_regimes
        self.base_state_dim = base_state_dim
        self.action_dim = action_dim
        self.n_experts = n_experts
        self.gate_temperature = gate_temperature

        self.trunk = _MLP(in_dim, trunk_hidden, trunk_hidden[-1])
        self.experts = nn.ModuleList(
            [_MLP(trunk_hidden[-1], expert_hidden, action_dim) for _ in range(n_experts)]
        )
        self.gate = _MLP(n_regimes, gate_hidden, n_experts)

        # Same conservative init bias toward action 3 (analytical tracker).
        with torch.no_grad():
            for e in self.experts:
                e.net[-1].weight.mul_(0.1)
                e.net[-1].bias.zero_()
                e.net[-1].bias[3] += 0.05

    def forward(self, x):
        if x.shape[-1] != self.base_state_dim + self.n_regimes:
            raise ValueError(
                f"expected input dim {self.base_state_dim + self.n_regimes}, "
                f"got {x.shape[-1]}"
            )
        regime = x[..., -self.n_regimes :]
        h = self.trunk(x)
        # (B, E, A)
        q_per_expert = torch.stack([e(h) for e in self.experts], dim=1)
        gate_logits = self.gate(regime) / self.gate_temperature
        weights = F.softmax(gate_logits, dim=-1)         # (B, E)
        q = (weights.unsqueeze(-1) * q_per_expert).sum(dim=1)  # (B, A)
        return q

    @torch.no_grad()
    def expert_assignment(self, regime: "torch.Tensor") -> "torch.Tensor":
        """Return the gate's expert distribution for diagnostic plots."""
        return F.softmax(self.gate(regime) / self.gate_temperature, dim=-1)
