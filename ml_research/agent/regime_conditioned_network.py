"""
Regime-conditioned DQN backbone (Section 11.6).

Drop-in replacement for agent/dqn_network.py that takes a 20-dimensional
input state (the original 14-dim state + 6-dim soft regime membership
vector from the bootstrap classifier) instead of 14.

The architecture is otherwise identical to the existing Helios-X
backbone so that warm-start, target network, replay buffer and the
training loop all remain unchanged.

Why a single conditioned model and not one model per regime?
------------------------------------------------------------
See implementation plan, Sections 11.6 and 11.8. In short:
shared physics representation, smooth interpolation across regimes,
no hard-switch brittleness at borderline sites, single artifact to
train and ship, and a strong novelty story for the IEEE manuscript.
"""

from __future__ import annotations

from typing import Sequence

try:
    import torch
    import torch.nn as nn
except Exception:  # pragma: no cover
    torch = None  # type: ignore


class RegimeConditionedQNetwork(nn.Module if torch is not None else object):
    """
    14 base state features + R-dim soft regime membership -> 13 Q-values.

    Default R = number of training-time regimes (10 in the expanded
    11-city training set; one regime per city minus duplicate arid).
    """

    def __init__(
        self,
        base_state_dim: int = 14,
        n_regimes: int = 10,
        action_dim: int = 13,
        hidden_layers: Sequence[int] = (128, 128, 64),
        activation: str = "relu",
    ):
        super().__init__()  # type: ignore[misc]
        self.base_state_dim = base_state_dim
        self.n_regimes = n_regimes
        self.action_dim = action_dim
        in_dim = base_state_dim + n_regimes

        act_cls = {"relu": nn.ReLU, "gelu": nn.GELU, "tanh": nn.Tanh}[activation]
        layers: list[nn.Module] = []
        prev = in_dim
        for h in hidden_layers:
            layers.append(nn.Linear(prev, h))
            layers.append(act_cls())
            prev = h
        layers.append(nn.Linear(prev, action_dim))
        self.net = nn.Sequential(*layers)

        # Conservative init: small last-layer weights so the agent starts
        # close to the analytical-tracker action (action index 3) rather
        # than to a random Q-value spread. Mirrors the warm-start prior.
        with torch.no_grad():
            self.net[-1].weight.mul_(0.1)
            self.net[-1].bias.zero_()
            self.net[-1].bias[3] += 0.05  # nudge identity action up

    def forward(self, x: "torch.Tensor") -> "torch.Tensor":
        # Defensive check: callers must concatenate state + regime vector
        # before passing in. We do not want to silently broadcast.
        if x.shape[-1] != self.base_state_dim + self.n_regimes:
            raise ValueError(
                f"expected input dim {self.base_state_dim + self.n_regimes}, "
                f"got {x.shape[-1]}. Did you forget to concatenate the regime vector?"
            )
        return self.net(x)


def build_conditioned_state(
    base_state: "torch.Tensor",
    regime_vector: "torch.Tensor",
) -> "torch.Tensor":
    """
    Concatenate the 14-dim base state with the R-dim soft regime
    membership vector. Both must have matching batch dimensions.
    """
    if base_state.dim() == 1:
        base_state = base_state.unsqueeze(0)
    if regime_vector.dim() == 1:
        regime_vector = regime_vector.unsqueeze(0)
    if regime_vector.shape[0] == 1 and base_state.shape[0] > 1:
        regime_vector = regime_vector.expand(base_state.shape[0], -1)
    return torch.cat([base_state, regime_vector], dim=-1)
