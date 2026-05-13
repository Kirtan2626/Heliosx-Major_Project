"""
Helios-X v2 Evaluation Entry Point.

Usage:
    python evaluate.py --config config/default.yaml --checkpoint checkpoints/dqn_final.pt
    python evaluate.py --ablations
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import get_config
from evaluation.evaluator import Evaluator
from evaluation.statistical_tests import run_all_tests, run_ppo_comparison
from evaluation.ablation_runner import run_all_ablations, run_multi_seed_ablations
from evaluation.visualizations import generate_all_figures


def main():
    parser = argparse.ArgumentParser(description="Evaluate Helios-X v2")
    parser.add_argument("--config", default=None, help="Config YAML path")
    parser.add_argument("--checkpoint", default=None,
                        help="DQN checkpoint path (default: checkpoints/dqn_final.pt)")
    parser.add_argument("--tabular-checkpoint", default=None,
                        help="Tabular agent checkpoint path")
    parser.add_argument("--ablations", action="store_true",
                        help="Also run ablation evaluations")
    parser.add_argument("--figures-only", action="store_true",
                        help="Only generate figures from existing results")
    parser.add_argument("--multi-seed", action="store_true",
                        help="Run multi-seed ablation study (Section 7.4)")
    parser.add_argument("--seeds", type=int, nargs="+", default=[42, 123, 7],
                        help="Seeds for multi-seed ablation (default: 42 123 7)")
    parser.add_argument("--seed-episodes", type=int, default=2000,
                        help="Episodes per seed in multi-seed ablation (default: 2000)")
    parser.add_argument("--append-seeds", action="store_true",
                        help="Append to existing ablation_multiseed.json instead of retraining")
    args = parser.parse_args()

    config = get_config(args.config)
    results_dir = Path(config["paths"]["results_dir"])
    checkpoints_dir = Path(config["paths"]["checkpoints_dir"])

    # Default checkpoint paths
    checkpoint = args.checkpoint or str(checkpoints_dir / "dqn_final.pt")
    tabular_checkpoint = args.tabular_checkpoint or str(checkpoints_dir / "tabular_final.json")

    if args.figures_only:
        # Load existing results and generate figures
        eval_path = results_dir / "evaluation_results.json"
        ablation_path = results_dir / "ablation_results.json"
        log_path = checkpoints_dir / "training_log.jsonl"
        cold_log = checkpoints_dir / "training_log_ablation_no_warmstart.jsonl"

        eval_results = {}
        ablation_results = {}

        if eval_path.exists():
            with open(eval_path) as f:
                eval_results = json.load(f)

        if ablation_path.exists():
            with open(ablation_path) as f:
                ablation_results = json.load(f)

        generate_all_figures(
            log_path=str(log_path),
            eval_results=eval_results,
            ablation_results=ablation_results,
            cold_log_path=str(cold_log) if cold_log.exists() else None,
            episode_traces_path=str(results_dir / "episode_traces.json"),
            output_dir=results_dir / "figures",
            config=config,
            supplementary=True,
        )
        return

    print("=" * 60)
    print("Helios-X v2 — Evaluation")
    print(f"Checkpoint: {checkpoint}")
    print("=" * 60)

    # Run 4-way evaluation
    evaluator = Evaluator(
        config=config,
        dqn_checkpoint=checkpoint,
        tabular_checkpoint=tabular_checkpoint,
    )

    eval_results = evaluator.evaluate_all()
    evaluator.save_results(eval_results, results_dir / "evaluation_results.json")

    # Statistical tests
    print("\n" + "=" * 60)
    print("STATISTICAL TESTS")
    print("=" * 60)

    stats_results = run_all_tests(eval_results)

    for comparison, result in stats_results.items():
        print(f"\n  {comparison}:")
        print(f"    Improvement: {result['mean_improvement_pct']:.2f}%")
        print(f"    Cohen's d: {result['cohens_d']}")
        wilcoxon = result["wilcoxon"]
        if wilcoxon["p_value"] is not None:
            print(f"    Wilcoxon p-value: {wilcoxon['p_value']:.6f}")
            print(f"    Significant (p<0.05): {wilcoxon['significant']}")
        ci = result["confidence_interval"]
        if ci["lower"] is not None:
            print(f"    95% CI: [{ci['lower']:.2f}, {ci['upper']:.2f}]")

    # DQN vs PPO comparison (if PPO results exist)
    ppo_path = results_dir / "ppo_baseline_results.json"
    if ppo_path.exists():
        with open(ppo_path) as f:
            ppo_data = json.load(f)
        ppo_stats = run_ppo_comparison(eval_results, ppo_data)
        if "error" not in ppo_stats:
            stats_results["dqn_vs_ppo"] = ppo_stats
            print(f"\n  dqn_vs_ppo:")
            print(f"    Improvement: {ppo_stats['mean_improvement_pct']:.2f}%")
            print(f"    Cohen's d: {ppo_stats['cohens_d']}")
            wt = ppo_stats["wilcoxon"]
            if wt.get("p_value") is not None:
                print(f"    Wilcoxon p-value: {wt['p_value']:.6f}")

    # Save stats
    stats_path = results_dir / "statistical_tests.json"
    with open(stats_path, "w") as f:
        json.dump(stats_results, f, indent=2)
    print(f"\n  Stats saved to {stats_path}")

    # Ablations
    ablation_results = {}
    if args.ablations:
        ablation_results = run_all_ablations(
            checkpoint_dir=str(checkpoints_dir),
            output_dir=str(results_dir),
        )

    # Generate figures
    log_path = checkpoints_dir / "training_log.jsonl"
    cold_log = checkpoints_dir / "training_log_ablation_no_warmstart.jsonl"

    episode_traces = results_dir / "episode_traces.json"
    generate_all_figures(
        log_path=str(log_path),
        eval_results=eval_results,
        ablation_results=ablation_results,
        cold_log_path=str(cold_log) if cold_log.exists() else None,
        episode_traces_path=str(episode_traces) if episode_traces.exists() else None,
        output_dir=results_dir / "figures",
        config=config,
        supplementary=True,
    )

    # Multi-seed ablation study (Section 7.4)
    if args.multi_seed:
        run_multi_seed_ablations(
            seeds=args.seeds,
            episodes_per_seed=args.seed_episodes,
            output_dir=str(results_dir),
            append=args.append_seeds,
        )

    print("\n" + "=" * 60)
    print("EVALUATION COMPLETE")
    print(f"Results: {results_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
