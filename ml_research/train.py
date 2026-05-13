"""
Helios-X v2 Training Entry Point.

Usage:
    python train.py --config config/default.yaml
    python train.py --config config/default.yaml --city delhi --episodes 1000
    python train.py --config config/ablation_no_warmstart.yaml
    python train.py --resume checkpoints/dqn_ep1000.pt
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import get_config
from training.trainer import Trainer


def main():
    parser = argparse.ArgumentParser(description="Train Helios-X v2 DQN agent")
    parser.add_argument("--config", default=None, help="Config YAML path")
    parser.add_argument("--city", default=None, help="Train on single city only")
    parser.add_argument("--episodes", type=int, default=None, help="Override total episodes")
    parser.add_argument("--resume", default=None, help="Resume from checkpoint path")
    args = parser.parse_args()

    # Build config with overrides
    overrides = {}
    if args.city:
        overrides["budget"] = {"train_cities": [args.city]}
    if args.episodes:
        overrides["budget"] = overrides.get("budget", {})
        overrides["budget"]["total_episodes"] = args.episodes

    config = get_config(args.config, overrides=overrides if overrides else None)

    # Set random seeds
    seed = config["experiment"]["seed"]
    import random
    import numpy as np
    import torch
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

    print("=" * 60)
    print("Helios-X v2 — Training")
    print(f"Config: {args.config or 'default'}")
    print(f"Experiment: {config['experiment']['name']}")
    print(f"Device: {config['experiment']['device']}")
    print(f"Episodes: {config['budget']['total_episodes']}")
    print("=" * 60)

    trainer = Trainer(config)
    trainer.train(resume_from=args.resume)


if __name__ == "__main__":
    main()
