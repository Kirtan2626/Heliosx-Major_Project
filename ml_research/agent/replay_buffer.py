"""
Experience replay buffer for DQN training.

Stores (state, action, reward, next_state, done) transitions
and provides random batch sampling for decorrelated training.
"""

import random
from collections import deque

import numpy as np
import torch


class ReplayBuffer:
    """
    Fixed-capacity circular buffer for experience replay.

    Stores transitions and returns random batches as PyTorch tensors.
    """

    def __init__(self, capacity: int = 50000):
        """
        Args:
            capacity: Maximum number of transitions to store
        """
        if capacity <= 0:
            raise ValueError("ReplayBuffer capacity must be positive")
        self.buffer = deque(maxlen=capacity)

    def push(
        self,
        state: np.ndarray,
        action: int,
        reward: float,
        next_state: np.ndarray,
        done: bool,
    ):
        """Store a single transition."""
        state_arr = np.asarray(state, dtype=np.float32)
        next_state_arr = np.asarray(next_state, dtype=np.float32)
        if state_arr.shape != next_state_arr.shape:
            raise ValueError(
                f"state/next_state shape mismatch: {state_arr.shape} vs {next_state_arr.shape}"
            )
        if not np.all(np.isfinite(state_arr)) or not np.all(np.isfinite(next_state_arr)):
            raise ValueError("ReplayBuffer received non-finite state values")
        if not np.isfinite(reward):
            raise ValueError("ReplayBuffer received a non-finite reward")
        self.buffer.append((
            state_arr.copy(),
            int(action),
            float(reward),
            next_state_arr.copy(),
            bool(done),
        ))

    def sample(
        self,
        batch_size: int,
        device: str = "cpu",
    ) -> tuple[torch.Tensor, ...]:
        """
        Sample a random batch of transitions.

        Args:
            batch_size: Number of transitions to sample
            device: PyTorch device for tensors

        Returns:
            (states, actions, rewards, next_states, dones) as tensors
        """
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        if batch_size > len(self.buffer):
            raise ValueError(
                f"cannot sample batch_size={batch_size} from replay size={len(self.buffer)}"
            )
        batch = random.sample(self.buffer, batch_size)

        states, actions, rewards, next_states, dones = zip(*batch)

        return (
            torch.FloatTensor(np.array(states)).to(device),
            torch.LongTensor(actions).to(device),
            torch.FloatTensor(rewards).to(device),
            torch.FloatTensor(np.array(next_states)).to(device),
            torch.FloatTensor(dones).to(device),
        )

    def __len__(self) -> int:
        return len(self.buffer)
