"""
Double DQN agent with epsilon-greedy exploration.

Uses two networks (policy and target) with soft target updates.
Supports warm-start initialization and checkpoint save/load.
"""

import random
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
import torch.optim as optim

from agent.dqn_network import DQNNetwork
from agent.replay_buffer import ReplayBuffer

try:
    from agent.regime_conditioned_network import RegimeConditionedQNetwork
except Exception:  # pragma: no cover
    RegimeConditionedQNetwork = None  # type: ignore


class DQNAgent:
    """
    Double DQN agent for solar panel tracking optimization.
    """

    def __init__(self, config: dict):
        """
        Initialize agent with policy net, target net, and replay buffer.

        Args:
            config: Full configuration dict
        """
        self.config = config
        requested_device = config["experiment"].get("device", "cpu")
        if str(requested_device).startswith("cuda") and not torch.cuda.is_available():
            requested_device = "cpu"
        self.device = torch.device(requested_device)

        action_dim = config["actions"]["dim"]
        hidden_layers = config["network"]["hidden_layers"]

        # Architecture dispatch: plain DQN vs regime-conditioned DQN
        arch_cfg = config.get("architecture", {}) or {}
        arch_type = arch_cfg.get("type", "dqn")

        if arch_type == "regime_conditioned_dqn":
            if RegimeConditionedQNetwork is None:
                raise ImportError(
                    "RegimeConditionedQNetwork not available but architecture.type="
                    "regime_conditioned_dqn was requested."
                )
            base_state_dim = arch_cfg.get(
                "base_state_dim", config["state"].get("base_dim", 14)
            )
            n_regimes = arch_cfg.get(
                "n_regimes", config["state"].get("regime_dim", 10)
            )
            self.policy_net = RegimeConditionedQNetwork(
                base_state_dim=base_state_dim,
                n_regimes=n_regimes,
                action_dim=action_dim,
                hidden_layers=hidden_layers,
            ).to(self.device)
            self.target_net = RegimeConditionedQNetwork(
                base_state_dim=base_state_dim,
                n_regimes=n_regimes,
                action_dim=action_dim,
                hidden_layers=hidden_layers,
            ).to(self.device)
            state_dim = base_state_dim + n_regimes
        else:
            state_dim = config["state"]["dim"]
            self.policy_net = DQNNetwork(state_dim, action_dim, hidden_layers).to(self.device)
            self.target_net = DQNNetwork(state_dim, action_dim, hidden_layers).to(self.device)
        self.target_net.load_state_dict(self.policy_net.state_dict())
        self.target_net.eval()

        # Optimizer
        self.optimizer = optim.Adam(
            self.policy_net.parameters(),
            lr=config["training"]["learning_rate"],
        )

        # Replay buffer
        self.replay_buffer = ReplayBuffer(config["training"]["replay_buffer_size"])

        # Hyperparameters
        self.gamma = config["training"]["gamma"]
        self.tau = config["training"]["tau"]
        self.batch_size = config["training"]["batch_size"]
        self.min_replay_size = config["training"]["min_replay_size"]
        self.max_grad_norm = config["training"]["max_grad_norm"]

        # Exploration
        self.epsilon_start = config["exploration"]["epsilon_start"]
        self.epsilon_end = config["exploration"]["epsilon_end"]
        self.epsilon_decay_steps = config["exploration"]["epsilon_decay_steps"]

        self.action_dim = action_dim
        self.total_steps = 0

    def get_epsilon(self, step: int = None) -> float:
        """Compute epsilon for a given step (linear decay)."""
        if step is None:
            step = self.total_steps

        if step >= self.epsilon_decay_steps:
            return self.epsilon_end

        fraction = step / self.epsilon_decay_steps
        return self.epsilon_start + fraction * (self.epsilon_end - self.epsilon_start)

    def select_action(self, state: np.ndarray, epsilon: float = None) -> int:
        """
        Select action using epsilon-greedy policy.

        Args:
            state: Current state vector (14-dim)
            epsilon: Exploration rate (default: computed from step)

        Returns:
            Action index (0-12)
        """
        if epsilon is None:
            epsilon = self.get_epsilon()
        epsilon = float(np.clip(epsilon, 0.0, 1.0))

        state = np.asarray(state, dtype=np.float32)
        expected_dim = getattr(self.policy_net, "base_state_dim", None)
        if expected_dim is not None and hasattr(self.policy_net, "n_regimes"):
            expected_dim = self.policy_net.base_state_dim + self.policy_net.n_regimes
        elif expected_dim is None:
            expected_dim = self.config["state"]["dim"]
        if state.shape[-1] != expected_dim:
            raise ValueError(f"expected state dim {expected_dim}, got {state.shape[-1]}")
        if not np.all(np.isfinite(state)):
            raise ValueError("state contains NaN or Inf values")

        if random.random() < epsilon:
            return random.randint(0, self.action_dim - 1)

        with torch.no_grad():
            state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
            q_values = self.policy_net(state_tensor)
            return q_values.argmax(dim=1).item()

    def store_transition(
        self,
        state: np.ndarray,
        action: int,
        reward: float,
        next_state: np.ndarray,
        done: bool,
    ):
        """Store transition in replay buffer."""
        self.replay_buffer.push(state, action, reward, next_state, done)

    def update(self) -> float | None:
        """
        Perform one Double DQN update step.

        Returns:
            Loss value, or None if buffer too small
        """
        if len(self.replay_buffer) < max(self.min_replay_size, self.batch_size):
            return None

        # Sample batch
        states, actions, rewards, next_states, dones = self.replay_buffer.sample(
            self.batch_size, self.device
        )

        # Current Q-values
        q_values = self.policy_net(states).gather(1, actions.unsqueeze(1)).squeeze(1)

        # Double DQN: policy net selects action, target net evaluates
        with torch.no_grad():
            best_actions = self.policy_net(next_states).argmax(dim=1)
            next_q = self.target_net(next_states).gather(1, best_actions.unsqueeze(1)).squeeze(1)
            targets = rewards + self.gamma * next_q * (1 - dones)

        # Huber loss (smooth L1)
        loss = F.smooth_l1_loss(q_values, targets)
        if not torch.isfinite(loss):
            raise FloatingPointError("non-finite DQN loss detected")

        # Optimize
        self.optimizer.zero_grad()
        loss.backward()

        # Gradient clipping
        grad_norm = torch.nn.utils.clip_grad_norm_(
            self.policy_net.parameters(), self.max_grad_norm
        )
        if not torch.isfinite(grad_norm):
            raise FloatingPointError("non-finite DQN gradient norm detected")

        self.optimizer.step()
        self.total_steps += 1

        return loss.item()

    def soft_update_target(self):
        """Soft update target network: target = τ*policy + (1-τ)*target."""
        with torch.no_grad():
            for target_param, policy_param in zip(
                self.target_net.parameters(), self.policy_net.parameters()
            ):
                target_param.copy_(
                    self.tau * policy_param + (1.0 - self.tau) * target_param
                )

    def save(self, path: str | Path):
        """Save agent checkpoint."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        checkpoint = {
            "policy_net": self.policy_net.state_dict(),
            "target_net": self.target_net.state_dict(),
            "optimizer": self.optimizer.state_dict(),
            "total_steps": self.total_steps,
            "config": self.config,
            "rng_state": {
                "python": random.getstate(),
                "numpy": np.random.get_state(),
                "torch": torch.get_rng_state(),
                "cuda": torch.cuda.get_rng_state_all() if torch.cuda.is_available() else None,
            },
        }
        torch.save(checkpoint, path)

    def load(self, path: str | Path):
        """Load agent from checkpoint."""
        checkpoint = torch.load(path, map_location=self.device, weights_only=False)

        self.policy_net.load_state_dict(checkpoint["policy_net"])
        self.target_net.load_state_dict(checkpoint["target_net"])
        self.optimizer.load_state_dict(checkpoint["optimizer"])
        for state in self.optimizer.state.values():
            for key, value in state.items():
                if torch.is_tensor(value):
                    state[key] = value.to(self.device)
        self.total_steps = checkpoint.get("total_steps", 0)
        rng_state = checkpoint.get("rng_state")
        if rng_state:
            random.setstate(rng_state["python"])
            np.random.set_state(rng_state["numpy"])
            torch.set_rng_state(rng_state["torch"])
            if torch.cuda.is_available() and rng_state.get("cuda") is not None:
                torch.cuda.set_rng_state_all(rng_state["cuda"])
