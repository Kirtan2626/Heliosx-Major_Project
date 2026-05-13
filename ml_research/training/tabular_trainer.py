"""
Tabular Q-Learning trainer for Baseline B3.

Trains the TabularAgent through the same environments and city rotation
as the DQN trainer, using Q-Learning updates instead of replay buffer.
"""

import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.tabular_agent import TabularAgent
from environment.solar_env import SolarTrackingEnv
from training.logger import TrainingLogger
from training.scheduler import CityScheduler


class TabularTrainer:
    """Trains tabular Q-learning agent on the solar tracking task."""

    def __init__(self, config: dict):
        self.config = config
        self.agent = TabularAgent(config)

        # Create environments for each city
        self.envs = {}
        train_cities = config.get("budget", {}).get(
            "train_cities", list(config["cities"].keys())
        )
        self.train_cities = train_cities

        for city_key in train_cities:
            self.envs[city_key] = SolarTrackingEnv(
                config=config,
                city_name=city_key,
                synthetic=not self._data_exists(config, city_key),
            )

        self.city_scheduler = CityScheduler(train_cities)
        self.total_episodes = config["budget"]["total_episodes"]

        # Logger with tabular prefix
        checkpoint_dir = Path(config["paths"]["checkpoints_dir"])
        self.logger = TrainingLogger(checkpoint_dir, experiment_name="tabular")

    def _data_exists(self, config: dict, city_key: str) -> bool:
        processed_dir = Path(config["paths"]["processed_dir"])
        irr_path = processed_dir / "irradiance" / f"{city_key}_hourly.parquet"
        return irr_path.exists()

    def run_episode(self, city_key: str, episode_num: int) -> dict:
        """Run a single training episode with Q-learning updates."""
        env = self.envs[city_key]
        obs, info = env.reset()

        episode_reward = 0.0
        total_td_error = 0.0
        steps = 0
        shadow_escapes = 0
        shadow_opportunities = 0

        while True:
            epsilon = self.agent.get_epsilon()
            action = self.agent.select_action(obs, epsilon)

            next_obs, reward, terminated, truncated, step_info = env.step(action)

            # Q-learning update (no replay buffer needed)
            td_error = self.agent.update_q(obs, action, reward, next_obs, terminated)
            total_td_error += td_error

            episode_reward += reward
            steps += 1

            if step_info.get("shadow_escape"):
                shadow_escapes += 1
            if step_info.get("shadow_before", 1.0) < 0.5:
                shadow_opportunities += 1

            obs = next_obs
            if terminated or truncated:
                break

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
            "mean_reward_per_step": round(episode_reward / max(steps, 1), 2),
            "epsilon": round(epsilon, 4),
            "loss": round(total_td_error / max(steps, 1), 4),
            "shadow_escape_rate": round(shadow_escape_rate, 4),
            "q_table_size": len(self.agent.q_table),
        }

    def train(self):
        """Run full tabular Q-learning training."""
        print("\n" + "=" * 60)
        print("Tabular Q-Learning Training (Baseline B3)")
        print(f"Episodes: {self.total_episodes}")
        print(f"Cities: {', '.join(self.train_cities)}")
        print("=" * 60)

        start_time = time.time()

        for episode in range(1, self.total_episodes + 1):
            city = self.city_scheduler.next_city()
            metrics = self.run_episode(city, episode)
            self.logger.log_episode(metrics)

            if episode % 50 == 0:
                elapsed = time.time() - start_time
                eps_per_sec = episode / max(elapsed, 1)
                remaining = (self.total_episodes - episode) / max(eps_per_sec, 0.01)
                print(
                    f"  Episode {episode}/{self.total_episodes} "
                    f"[{city}] reward={metrics['total_reward']:.1f} "
                    f"td={metrics['loss']:.4f} eps={metrics['epsilon']:.3f} "
                    f"Q-states={metrics['q_table_size']} "
                    f"({elapsed:.0f}s elapsed, ~{remaining:.0f}s remaining)"
                )

            if episode % 100 == 0:
                self.logger.log_summary(window=100)

        # Save trained Q-table
        ckpt_dir = Path(self.config["paths"]["checkpoints_dir"])
        save_path = ckpt_dir / "tabular_final.json"
        self.agent.save(save_path)

        total_time = time.time() - start_time
        print(f"\nTabular training complete in {total_time:.1f}s")
        print(f"Q-table states: {len(self.agent.q_table)}")
        print(f"Saved to: {save_path}")


def main():
    """Entry point for standalone tabular training."""
    import argparse

    sys.path.insert(0, str(Path(__file__).parent.parent))
    from config import get_config

    parser = argparse.ArgumentParser(description="Train tabular Q-learning agent")
    parser.add_argument("--config", default=None, help="Config YAML path")
    parser.add_argument("--episodes", type=int, default=None, help="Override episodes")
    args = parser.parse_args()

    overrides = {}
    if args.episodes:
        overrides["budget"] = {"total_episodes": args.episodes}

    config = get_config(args.config, overrides=overrides if overrides else None)

    import random
    import torch
    seed = config["experiment"]["seed"]
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

    trainer = TabularTrainer(config)
    trainer.train()


if __name__ == "__main__":
    main()
