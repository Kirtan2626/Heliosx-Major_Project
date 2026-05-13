"""
Online fine-tuning at the edge.

When the install-time regime classifier (deployment/regime_classifier.py)
flags a site as 'soft' or 'fallback', this module performs small-step
gradient updates on the locally-collected (state, action, measured-energy)
tuples to adapt the agent to the local microclimate.

Design rules
------------
* Same Double-DQN loss as the main training run (see training/trainer.py)
  but with learning rate 1e-5 (≈ 30× smaller) and an L2 anchor penalty
  to the pre-trained weights to prevent catastrophic forgetting.
* Action space and safety filter are unchanged, so the worst case is
  still the analytical tracker by construction.
* Telemetry is buffered to a rolling 30-day SQLite store on the laptop
  SSD; no cloud or remote logging.
* Convergence target: match or beat the regime baseline within 2–4 weeks
  on the local site.

This file is intentionally a thin wrapper around the existing trainer
so that the main code path is shared and unit tests apply unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

try:
    import torch
    import torch.nn.functional as F
except Exception:  # pragma: no cover
    torch = None  # type: ignore


@dataclass
class FineTuneConfig:
    learning_rate: float = 1e-5
    anchor_lambda: float = 1e-3        # L2 pull-back to pre-trained weights
    batch_size: int = 32
    updates_per_day: int = 200
    buffer_path: str = "deployment/online_buffer.sqlite"
    max_buffer_days: int = 30
    seeds: tuple[int, ...] = (42,)
    enabled_decisions: tuple[str, ...] = ("soft", "fallback")


class OnlineFineTuner:
    """
    Wraps an already-trained DQN agent and runs anchored fine-tuning
    against an online telemetry buffer.

    Usage:
        ft = OnlineFineTuner(agent, cfg)
        ft.snapshot_anchor()           # called once on startup
        for batch in nightly_batches:
            ft.step(batch)
        ft.save("checkpoints/finetuned.pt")
    """

    def __init__(self, agent, cfg: FineTuneConfig | None = None):
        if torch is None:
            raise RuntimeError("PyTorch is required for online fine-tuning")
        self.agent = agent
        self.cfg = cfg or FineTuneConfig()
        self._anchor_state: dict[str, torch.Tensor] = {}
        self.optim = torch.optim.Adam(
            self.agent.q_network.parameters(), lr=self.cfg.learning_rate
        )

    # ----------------------------------------------------------------- #
    def snapshot_anchor(self) -> None:
        """Cache the pre-trained weights as the L2 anchor target."""
        self._anchor_state = {
            k: v.detach().clone() for k, v in self.agent.q_network.state_dict().items()
        }

    def _anchor_penalty(self) -> torch.Tensor:
        if not self._anchor_state:
            return torch.tensor(0.0, device=next(self.agent.q_network.parameters()).device)
        penalty = torch.tensor(0.0, device=next(self.agent.q_network.parameters()).device)
        for k, v in self.agent.q_network.named_parameters():
            penalty = penalty + ((v - self._anchor_state[k]) ** 2).sum()
        return self.cfg.anchor_lambda * penalty

    # ----------------------------------------------------------------- #
    def step(self, batch: dict) -> dict:
        """
        One optimisation step on a (s, a, r, s', done) batch.

        The Double-DQN target is computed exactly as in the main trainer.
        The only addition is the anchor penalty.
        """
        s = batch["state"]
        a = batch["action"]
        r = batch["reward"]
        s_next = batch["next_state"]
        done = batch["done"]

        with torch.no_grad():
            next_actions = self.agent.q_network(s_next).argmax(dim=1, keepdim=True)
            next_q = self.agent.target_network(s_next).gather(1, next_actions).squeeze(1)
            target = r + (1.0 - done) * self.agent.gamma * next_q

        q = self.agent.q_network(s).gather(1, a.unsqueeze(1)).squeeze(1)
        td_loss = F.smooth_l1_loss(q, target)
        anchor = self._anchor_penalty()
        loss = td_loss + anchor

        self.optim.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(self.agent.q_network.parameters(), 1.0)
        self.optim.step()
        self.agent.soft_update_target()

        return {
            "td_loss": float(td_loss.item()),
            "anchor": float(anchor.item()),
            "loss": float(loss.item()),
        }

    # ----------------------------------------------------------------- #
    def run_nightly(self, buffer_iter: Iterable[dict]) -> list[dict]:
        """Iterate `updates_per_day` mini-batches from the buffer."""
        logs = []
        n = 0
        for batch in buffer_iter:
            logs.append(self.step(batch))
            n += 1
            if n >= self.cfg.updates_per_day:
                break
        return logs

    def save(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        torch.save(
            {
                "q_network": self.agent.q_network.state_dict(),
                "target_network": self.agent.target_network.state_dict(),
                "config": self.cfg.__dict__,
            },
            path,
        )
