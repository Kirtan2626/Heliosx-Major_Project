"""
Training loop orchestrator for Helios-X v2.

Manages the complete training pipeline:
1. Physics warm-start (optional)
2. Epsilon-greedy training with city rotation
3. Periodic checkpointing and evaluation
4. Convergence monitoring
"""

import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.dqn_agent import DQNAgent
from environment.solar_env import SolarTrackingEnv
from training.logger import TrainingLogger
from training.scheduler import CityScheduler, DateSampler, select_eval_dates
from warmstart.physics_pretrainer import generate_pretrain_dataset, pretrain

try:
    from deployment.regime_vectors import load_regime_table, one_hot_regime_vector
except Exception:  # pragma: no cover
    load_regime_table = None  # type: ignore
    one_hot_regime_vector = None  # type: ignore


def _build_trainer_regime_lookup(config: dict, train_cities: list) -> dict | None:
    """
    Return city_key -> one-hot regime vector when the active architecture
    is regime-conditioned. Mirrors warmstart/physics_pretrainer.py so the
    SolarTrackingEnv instances produce (14 + R)-dim observations.
    """
    arch_cfg = config.get("architecture", {}) or {}
    if arch_cfg.get("type") != "regime_conditioned_dqn":
        return None
    if load_regime_table is None:
        return None

    here = Path(__file__).parent.parent
    candidate = here / "config" / "cities_extended.yaml"
    if not candidate.exists():
        print(
            f"  [trainer] WARNING: regime-conditioned arch but {candidate} "
            f"not found; falling back to zero regime vectors."
        )
        n = arch_cfg.get("n_regimes", 11)
        return {k: np.zeros(n, dtype=np.float32) for k in train_cities}

    regimes, city_to_regime = load_regime_table(candidate)
    lookup: dict = {}
    for city_key in train_cities:
        if city_key in city_to_regime:
            lookup[city_key] = one_hot_regime_vector(city_to_regime[city_key], regimes)
        else:
            print(
                f"  [trainer] WARNING: city {city_key!r} has no regime label "
                f"in cities_extended.yaml; using zero vector."
            )
            lookup[city_key] = np.zeros(len(regimes), dtype=np.float32)
    print(
        f"  [trainer] regime conditioning ON: "
        f"{len(lookup)} envs -> {len(regimes)}-dim one-hot vectors"
    )
    return lookup


class Trainer:
    """Orchestrates the complete training pipeline."""

    def __init__(self, config: dict):
        self.config = config
        self.device = config["experiment"]["device"]

        # Create agent
        self.agent = DQNAgent(config)

        # Create environments for each city
        self.envs = {}
        train_cities = config.get("budget", {}).get(
            "train_cities",
            list(config["cities"].keys())
        )
        self.train_cities = train_cities

        # Regime-conditioning lookup (None unless architecture is regime_conditioned_dqn)
        self.regime_lookup = _build_trainer_regime_lookup(config, train_cities)

        for city_key in train_cities:
            rv = self.regime_lookup[city_key] if self.regime_lookup is not None else None
            self.envs[city_key] = SolarTrackingEnv(
                config=config,
                city_name=city_key,
                synthetic=not self._data_exists(config, city_key),
                regime_vector=rv,
            )

        # Scheduler
        self.city_scheduler = CityScheduler(train_cities)

        # Logger
        checkpoint_dir = Path(config["paths"]["checkpoints_dir"])
        exp_name = config["experiment"]["name"]
        self.logger = TrainingLogger(checkpoint_dir, experiment_name=exp_name)

        # Training budget
        self.total_episodes = config["budget"]["total_episodes"]
        self.checkpoint_every = config["budget"]["checkpoint_every"]
        self.eval_every = config["budget"]["eval_every"]

    def _data_exists(self, config: dict, city_key: str) -> bool:
        """Check if processed data exists for a city."""
        processed_dir = Path(config["paths"]["processed_dir"])
        irr_path = processed_dir / "irradiance" / f"{city_key}_hourly.parquet"
        return irr_path.exists()

    def run_warmstart(self):
        """Run physics warm-start pre-training."""
        if not self.config["warmstart"]["enabled"]:
            print("Warm-start disabled, skipping.")
            return

        print("\n" + "=" * 60)
        print("PHASE A: Physics Warm-Start")
        print("=" * 60)

        states, q_targets = generate_pretrain_dataset(self.config)
        losses = pretrain(self.agent, states, q_targets, self.config)

        # Log warm-start info
        self.logger.log_episode({
            "episode": 0,
            "phase": "warmstart",
            "pretrain_samples": len(states),
            "final_loss": losses[-1],
        })

    def run_episode(self, city_key: str, episode_num: int) -> dict:
        """Run a single training episode."""
        env = self.envs[city_key]
        obs, info = env.reset()

        episode_reward = 0.0
        episode_physical_energy = 0.0
        episode_shaping = 0.0
        episode_loss = 0.0
        n_updates = 0
        shadow_escapes = 0
        shadow_opportunities = 0
        stow_activations = 0
        diffuse_activations = 0
        steps = 0

        while True:
            # Select action
            epsilon = self.agent.get_epsilon()
            action = self.agent.select_action(obs, epsilon)

            # Environment step
            next_obs, reward, terminated, truncated, step_info = env.step(action)

            # Store transition
            self.agent.store_transition(obs, action, reward, next_obs, terminated)

            # Update agent
            loss = self.agent.update()
            if loss is not None:
                episode_loss += loss
                n_updates += 1

            # Soft update target network
            self.agent.soft_update_target()

            # Track metrics — separate physical energy from shaping
            episode_reward += reward
            episode_physical_energy += step_info.get("physical_energy", 0)
            episode_shaping += step_info.get("shaping_bonus", 0)
            steps += 1

            if step_info.get("shadow_escape"):
                shadow_escapes += 1
            if step_info.get("shadow_before", 1.0) < 0.5:
                shadow_opportunities += 1
            if step_info.get("mode") == "stow":
                stow_activations += 1
            if step_info.get("mode") == "diffuse":
                diffuse_activations += 1

            obs = next_obs

            if terminated or truncated:
                break

        # Compute episode metrics
        avg_loss = episode_loss / max(n_updates, 1)
        shadow_escape_rate = (
            shadow_escapes / max(shadow_opportunities, 1)
            if shadow_opportunities > 0 else 0.0
        )

        return {
            "episode": episode_num,
            "city": city_key,
            "date": str(info.get("date", "")),
            "steps": steps,
            "total_reward": round(episode_reward, 2),
            "total_physical_energy": round(episode_physical_energy, 2),
            "total_shaping_bonus": round(episode_shaping, 2),
            "mean_reward_per_step": round(episode_reward / max(steps, 1), 2),
            "mean_physical_energy_per_step": round(episode_physical_energy / max(steps, 1), 2),
            "epsilon": round(epsilon, 4),
            "loss": round(avg_loss, 4),
            "shadow_escape_rate": round(shadow_escape_rate, 4),
            "stow_activations": stow_activations,
            "diffuse_activations": diffuse_activations,
            "n_updates": n_updates,
        }

    def train(self, resume_from: str = None):
        """
        Run full training pipeline.

        Args:
            resume_from: Path to checkpoint to resume from
        """
        start_episode = 1

        if resume_from:
            print(f"Resuming from {resume_from}")
            self.agent.load(resume_from)
            self.logger.load_existing()
            # Try to infer episode number from filename
            try:
                ep_str = Path(resume_from).stem.split("_ep")[-1]
                start_episode = int(ep_str) + 1
            except (ValueError, IndexError):
                pass
        else:
            self.logger.reset()
            self.run_warmstart()

        print("\n" + "=" * 60)
        print("PHASE B: Double DQN Training")
        print(f"Episodes: {start_episode} to {self.total_episodes}")
        print(f"Cities: {', '.join(self.train_cities)}")
        print("=" * 60)

        start_time = time.time()

        for episode in range(start_episode, self.total_episodes + 1):
            # Select city (round-robin)
            city = self.city_scheduler.next_city()

            # Run episode
            metrics = self.run_episode(city, episode)

            # Log
            self.logger.log_episode(metrics)

            # Print progress
            if episode % 50 == 0:
                elapsed = time.time() - start_time
                completed = episode - start_episode + 1
                eps_per_sec = completed / max(elapsed, 1)
                remaining = (self.total_episodes - episode) / max(eps_per_sec, 0.01)
                print(
                    f"  Episode {episode}/{self.total_episodes} "
                    f"[{city}] reward={metrics['total_reward']:.1f} "
                    f"loss={metrics['loss']:.4f} eps={metrics['epsilon']:.3f} "
                    f"({elapsed:.0f}s elapsed, ~{remaining:.0f}s remaining)"
                )

            # Summary
            if episode % 100 == 0:
                self.logger.log_summary(window=100)

            # Convergence check every 50 episodes (after warmup)
            if episode >= 100 and episode % 50 == 0:
                if self.check_convergence():
                    print(f"\n  CONVERGED at episode {episode}")
                    self.logger.log_episode({
                        "episode": episode,
                        "phase": "converged",
                        "total_reward": metrics["total_reward"],
                    })
                    break

            # Checkpoint
            if episode % self.checkpoint_every == 0:
                ckpt_dir = Path(self.config["paths"]["checkpoints_dir"])
                self.agent.save(ckpt_dir / f"dqn_ep{episode:04d}.pt")

            # Mid-training evaluation
            if episode % self.eval_every == 0:
                eval_reward = self._quick_eval()
                print(f"  [Eval] Mean greedy reward: {eval_reward:.1f}")
                self.logger.log_episode({
                    "episode": episode,
                    "phase": "eval",
                    "eval_reward": round(eval_reward, 2),
                })

        # Save final checkpoint (with experiment name for ablations)
        ckpt_dir = Path(self.config["paths"]["checkpoints_dir"])
        exp_name = self.config["experiment"]["name"]
        if exp_name != "helios_x_v2_main":
            final_name = f"dqn_final_{exp_name}.pt"
        else:
            final_name = "dqn_final.pt"
        self.agent.save(ckpt_dir / final_name)

        # Save config used
        config_path = ckpt_dir / "config_used.yaml"
        config_to_save = {k: v for k, v in self.config.items()
                         if k not in ("secrets", "cities")}
        with open(config_path, "w") as f:
            yaml.dump(config_to_save, f, default_flow_style=False)

        total_time = time.time() - start_time
        print(f"\nTraining complete in {total_time:.1f}s")
        print(f"Final checkpoint: {ckpt_dir / final_name}")

    def _quick_eval(self) -> float:
        """Run greedy evaluation on 2 cities, 1 date each."""
        eval_cities = [self.train_cities[0], self.train_cities[-1]]
        eval_date = datetime(2023, 6, 15)
        total_reward = 0.0

        for city_key in eval_cities:
            rv = self.regime_lookup[city_key] if self.regime_lookup is not None else None
            env = SolarTrackingEnv(
                config=self.config,
                city_name=city_key,
                synthetic=not self._data_exists(self.config, city_key),
                specific_date=eval_date,
                regime_vector=rv,
            )
            obs, _ = env.reset()
            ep_reward = 0.0
            done = False
            while not done:
                action = self.agent.select_action(obs, epsilon=0.0)
                obs, reward, terminated, truncated, _ = env.step(action)
                ep_reward += reward
                done = terminated or truncated
            total_reward += ep_reward

        return total_reward / len(eval_cities)

    def check_convergence(self, window: int = 50) -> bool:
        """Check if training has converged based on criteria."""
        episodes = self.logger.get_all_episodes()
        if len(episodes) < window:
            return False

        recent = episodes[-window:]

        # Criteria from spec Section 12.2
        mean_loss = np.mean([e.get("loss", 999) for e in recent])
        reward_vals = [e.get("total_reward", 0) for e in recent]
        reward_var = np.var(reward_vals)
        reward_mean = np.mean(reward_vals)
        epsilon = recent[-1].get("epsilon", 1.0)
        escape_rate = np.mean([e.get("shadow_escape_rate", 0) for e in recent])

        converged = (
            mean_loss < 5.0
            and (reward_var < 0.1 * abs(reward_mean) if reward_mean != 0 else True)
            and epsilon < 0.05
            and escape_rate > 0.8
        )

        return converged
