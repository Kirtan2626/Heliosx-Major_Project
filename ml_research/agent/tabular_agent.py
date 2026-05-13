"""
Tabular Q-Learning agent (Baseline B3).

Discretizes the 14-dim continuous state into bins and uses a Q-table.
This is the v1-style approach, included to demonstrate that DQN
outperforms tabular methods on the same data.
"""

import json
import random
from pathlib import Path

import numpy as np


class TabularAgent:
    """
    Q-Learning agent with discretized state space.

    Deliberately coarse discretization to show the curse of dimensionality
    and justify the DQN approach.
    """

    # Bins per state dimension (coarse to avoid memory explosion)
    BINS_PER_DIM = [
        4,   # sun altitude: [0, 0.25, 0.5, 0.75, 1.0]
        3,   # sun azimuth sin: [-1, -0.33, 0.33, 1]
        3,   # sun azimuth cos
        3,   # hour sin
        3,   # hour cos
        3,   # day sin
        3,   # day cos
        3,   # cloud fraction: [0, 0.33, 0.66, 1]
        3,   # AQI: [0, 0.33, 0.66, 1]
        3,   # shadow factor
        3,   # latitude
        3,   # longitude
        2,   # site altitude
        4,   # DNI
    ]

    def __init__(self, config: dict):
        self.config = config
        self.action_dim = config["actions"]["dim"]
        self.lr = config["training"]["learning_rate"]
        self.gamma = config["training"]["gamma"]

        self.epsilon_start = config["exploration"]["epsilon_start"]
        self.epsilon_end = config["exploration"]["epsilon_end"]
        self.epsilon_decay_steps = config["exploration"]["epsilon_decay_steps"]

        # Q-table as dict of state_key -> action_values
        self.q_table: dict[tuple, np.ndarray] = {}
        self.total_steps = 0

    def _discretize(self, state: np.ndarray) -> tuple:
        """Convert continuous state to discrete bin indices."""
        bins = []
        for i, n_bins in enumerate(self.BINS_PER_DIM):
            val = float(state[i])
            # Map from [-1, 1] to [0, n_bins-1]
            normalized = (val + 1.0) / 2.0  # -> [0, 1]
            bin_idx = min(int(normalized * n_bins), n_bins - 1)
            bins.append(bin_idx)
        return tuple(bins)

    def _get_q_values(self, state_key: tuple) -> np.ndarray:
        """Get or initialize Q-values for a state."""
        if state_key not in self.q_table:
            self.q_table[state_key] = np.zeros(self.action_dim)
        return self.q_table[state_key]

    def get_epsilon(self, step: int = None) -> float:
        if step is None:
            step = self.total_steps
        if step >= self.epsilon_decay_steps:
            return self.epsilon_end
        fraction = step / self.epsilon_decay_steps
        return self.epsilon_start + fraction * (self.epsilon_end - self.epsilon_start)

    def select_action(self, state: np.ndarray, epsilon: float = None) -> int:
        if epsilon is None:
            epsilon = self.get_epsilon()

        if random.random() < epsilon:
            return random.randint(0, self.action_dim - 1)

        state_key = self._discretize(state)
        q_values = self._get_q_values(state_key)
        return int(np.argmax(q_values))

    def update_q(
        self,
        state: np.ndarray,
        action: int,
        reward: float,
        next_state: np.ndarray,
        done: bool,
    ) -> float:
        """
        Q-Learning update: Q(s,a) += α[r + γ·max_a' Q(s',a') - Q(s,a)]

        Returns:
            TD error
        """
        state_key = self._discretize(state)
        next_key = self._discretize(next_state)

        q_values = self._get_q_values(state_key)
        next_q = self._get_q_values(next_key)

        target = reward + (1 - done) * self.gamma * np.max(next_q)
        td_error = target - q_values[action]
        q_values[action] += self.lr * td_error

        self.total_steps += 1
        return abs(td_error)

    def save(self, path: str | Path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Convert tuple keys to strings for JSON
        serializable = {
            "q_table": {str(k): v.tolist() for k, v in self.q_table.items()},
            "total_steps": self.total_steps,
        }
        with open(path, "w") as f:
            json.dump(serializable, f)

    def load(self, path: str | Path):
        with open(path, "r") as f:
            data = json.load(f)

        self.q_table = {
            eval(k): np.array(v) for k, v in data["q_table"].items()
        }
        self.total_steps = data["total_steps"]
