"""
Double DQN neural network architecture.

Network: 14 → 128 → ReLU → 128 → ReLU → 64 → ReLU → 13
Total parameters: ~25,000 (trains in minutes on CPU)
"""

import torch
import torch.nn as nn


class DQNNetwork(nn.Module):
    """
    Q-network for the Double DQN agent.

    Maps a 14-dim state vector to Q-values for 13 actions.
    """

    def __init__(
        self,
        state_dim: int = 14,
        action_dim: int = 13,
        hidden_layers: list[int] = None,
    ):
        super().__init__()

        if hidden_layers is None:
            hidden_layers = [128, 128, 64]

        layers = []
        prev_dim = state_dim

        for hidden_dim in hidden_layers:
            layers.append(nn.Linear(prev_dim, hidden_dim))
            layers.append(nn.ReLU())
            prev_dim = hidden_dim

        layers.append(nn.Linear(prev_dim, action_dim))

        self.network = nn.Sequential(*layers)

    def forward(self, state: torch.Tensor) -> torch.Tensor:
        """
        Compute Q-values for all actions given a state.

        Args:
            state: Tensor of shape (batch_size, state_dim) or (state_dim,)

        Returns:
            Q-values tensor of shape (batch_size, action_dim) or (action_dim,)
        """
        return self.network(state)

    def count_parameters(self) -> int:
        """Return total number of trainable parameters."""
        return sum(p.numel() for p in self.parameters() if p.requires_grad)
