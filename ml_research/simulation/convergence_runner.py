"""
Self-Learning Convergence Simulator.

Produces the data for the paper's "cascading knowledge transfer" figure:
for each target city we plot the daily oracle fraction trajectory under
two warm-start conditions:

    (a) physics-only   -- alpha = 0, slow exponential climb
    (b) enriched       -- alpha in {0.3, 0.5} via regime-matched bank

The simulator operates at the scalar oracle-fraction level using the
analytical convergence model in training.enriched_warmstart. This matches
the implementation plan's own "predicted convergence day" table (Section
3.3) rather than claiming empirical hardware-validated results.

For each simulated city we write per-day curves to
results/simulation/convergence_curves.json so the figure generator can
rebuild the plot deterministically.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from deployment.experience_bank import ExperienceBank, ExperienceTuple
from deployment.regime_vector_classifier import RegimeVectorClassifier
from deployment.regime_vectors import load_regime_table
from training.enriched_warmstart import (
    build_warm_start,
    convergence_curve,
    convergence_day,
    physics_only_policy,
    rolling_mean,
)


# ------------------------------------------------------------------ #
# Target deployments (plan Section 3 — cascading chain)
# ------------------------------------------------------------------ #

TARGET_CITIES = {
    "Ahmedabad": {
        "lat": 23.02,
        "lon": 72.57,
        "koppen": "BSh",
        "regime_label": "monsoon_aerosol",
        # Soft membership derived from 5-year NASA POWER fingerprint;
        # matches the plan's worked example (Section 3.1).
        "regime_blend": {
            "monsoon_aerosol": 0.55,
            "arid_high_irradiance": 0.30,
            "humid_subtropical": 0.10,
            "mediterranean": 0.05,
        },
    },
    "Vadodara": {
        "lat": 22.31,
        "lon": 73.19,
        "koppen": "BSh",
        "regime_label": "monsoon_aerosol",
        "regime_blend": {
            "monsoon_aerosol": 0.58,
            "arid_high_irradiance": 0.28,
            "humid_subtropical": 0.08,
            "mediterranean": 0.06,
        },
    },
    "Beijing": {
        "lat": 39.90,
        "lon": 116.40,
        "koppen": "Dwa",
        "regime_label": "temperate_continental",
        "regime_blend": {
            "temperate_continental": 0.30,
            "humid_subtropical": 0.30,
            "monsoon_aerosol": 0.25,
            "arid_high_irradiance": 0.05,
            "mediterranean": 0.05,
            "subpolar_oceanic": 0.05,
        },
    },
}


# Training cities as initial seed sources for the bank
TRAINING_SOURCES = {
    "delhi":    {"regime_label": "monsoon_aerosol",        "n_quality": 15000, "mean_energy": 1005.6},
    "dubai":    {"regime_label": "arid_high_irradiance",   "n_quality": 8000,  "mean_energy": 976.4},
    "tokyo":    {"regime_label": "humid_subtropical",      "n_quality": 2000,  "mean_energy": 471.3},
    "new_york": {"regime_label": "temperate_continental",  "n_quality": 3500,  "mean_energy": 392.6},
    "london":   {"regime_label": "maritime_low_irradiance", "n_quality": 2500, "mean_energy": 879.5},
    "sydney":   {"regime_label": "southern_temperate",     "n_quality": 2000,  "mean_energy": 910.9},
}


def _blend_to_vector(blend: dict[str, float], regimes: list[str]) -> np.ndarray:
    vec = np.zeros(len(regimes), dtype=float)
    for label, p in blend.items():
        if label in regimes:
            vec[regimes.index(label)] = p
    s = vec.sum()
    if s > 0:
        vec = vec / s
    return vec


def _build_seed_bank(
    regimes: list[str],
    path: Path,
) -> ExperienceBank:
    """Seed an ExperienceBank with synthetic quality tuples per training city."""
    bank = ExperienceBank(path=path)
    rng = np.random.default_rng(0)

    # Clear any pre-existing contents to keep the simulation deterministic.
    bank.sources.clear()
    bank.tuples.clear()

    for src_id, meta in TRAINING_SOURCES.items():
        rv = np.zeros(len(regimes), dtype=float)
        if meta["regime_label"] in regimes:
            rv[regimes.index(meta["regime_label"])] = 1.0

        # Synthesize a small representative set of quality tuples.
        # (The true deployment would upload real telemetry; for the
        # figure we need the bank to know "this source exists with
        # n_quality representative tuples".)
        tuples = []
        n_repr = min(200, meta["n_quality"])
        for _ in range(n_repr):
            det_e = meta["mean_energy"] / 30.0 * rng.uniform(0.6, 1.4)
            phys_e = det_e * rng.uniform(1.02, 1.25)  # guaranteed to pass quality gate
            tuples.append(
                ExperienceTuple(
                    state_14dim=[0.0] * 14,
                    action=int(rng.integers(0, 13)),
                    physical_energy=float(phys_e),
                    det_energy=float(det_e),
                    regime_vector=rv.tolist(),
                    source_id=src_id,
                    timestamp_frac=float(rng.uniform(0.25, 0.85)),
                    season_idx=int(rng.integers(0, 4)),
                )
            )

        bank.add_source(src_id, rv, tuples)
        # Patch the public tuple count so similarity queries weight by
        # the real operational bank size, not the synthesized mini-set.
        bank.sources[src_id].n_quality_tuples = meta["n_quality"]

    return bank


def simulate_convergence(
    n_days: int = 30,
    seed: int = 42,
    out_path: str | Path = "results/simulation/convergence_curves.json",
) -> dict:
    """
    Simulate convergence for Ahmedabad -> Vadodara -> Beijing and dump JSON.

    The Ahmedabad deployment is run first, then ingested into the bank
    before Vadodara is simulated -- so Vadodara sees the compounding
    effect described in the implementation plan.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    regimes, _ = load_regime_table()
    bank_path = out_path.parent / "experience_bank.json"
    bank = _build_seed_bank(regimes, bank_path)

    # Mahalanobis classifier in regime-vector space with the default
    # isotropic covariance (sigma=0.15) that MATCH/SOFT thresholds are
    # calibrated against. The `from_training_vectors` factory is available
    # for future deployments with more training samples, but with just
    # the 6 one-hot training regimes here the empirical variance would
    # perturb the calibrated thresholds.
    classifier = RegimeVectorClassifier(regime_labels=regimes)

    rng = np.random.default_rng(seed)

    results: dict[str, dict] = {
        "config": {"n_days": n_days, "seed": seed, "regimes": regimes},
        "cities": {},
    }

    for city_name, meta in TARGET_CITIES.items():
        rv = _blend_to_vector(meta["regime_blend"], regimes)

        # (a) physics-only -- ignore the bank entirely
        p_phys = physics_only_policy()
        curve_phys = convergence_curve(p_phys, n_days=n_days, rng=np.random.default_rng(rng.integers(0, 2**31)))

        # (b) enriched -- query current bank state
        p_enriched = build_warm_start(rv, bank, classifier=classifier)
        curve_enriched = convergence_curve(p_enriched, n_days=n_days, rng=np.random.default_rng(rng.integers(0, 2**31)))

        results["cities"][city_name] = {
            "lat": meta["lat"],
            "lon": meta["lon"],
            "koppen": meta["koppen"],
            "regime_vector": rv.tolist(),
            "physics_only": {
                "policy": asdict(p_phys),
                "curve_daily": curve_phys.tolist(),
                "curve_rolling7": rolling_mean(curve_phys, 7).tolist(),
                "convergence_day": convergence_day(curve_phys),
            },
            "enriched": {
                "policy": asdict(p_enriched),
                "curve_daily": curve_enriched.tolist(),
                "curve_rolling7": rolling_mean(curve_enriched, 7).tolist(),
                "convergence_day": convergence_day(curve_enriched),
                "top_sources": p_enriched.top_sources,
            },
        }

        # After Ahmedabad deploys, its operational telemetry joins the
        # bank -- so Vadodara (next in the chain) sees a stronger match.
        if city_name == "Ahmedabad":
            ahm_tuples = []
            n_repr = 200
            for _ in range(n_repr):
                det_e = 30.0 * rng.uniform(0.6, 1.4)
                phys_e = det_e * rng.uniform(1.04, 1.22)
                ahm_tuples.append(
                    ExperienceTuple(
                        state_14dim=[0.0] * 14,
                        action=int(rng.integers(0, 13)),
                        physical_energy=float(phys_e),
                        det_energy=float(det_e),
                        regime_vector=rv.tolist(),
                        source_id="ahmedabad",
                        timestamp_frac=float(rng.uniform(0.25, 0.85)),
                        season_idx=int(rng.integers(0, 4)),
                    )
                )
            bank.add_source("ahmedabad", rv, ahm_tuples)
            # Target ~8000 quality-gated tuples after the 30-day stint,
            # matching the plan's Section 3.1 figures.
            bank.sources["ahmedabad"].n_quality_tuples = 8000

    bank.save()
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Self-Learning Convergence simulator")
    parser.add_argument("--n-days", type=int, default=30)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=str, default="results/simulation/convergence_curves.json")
    args = parser.parse_args()

    r = simulate_convergence(n_days=args.n_days, seed=args.seed, out_path=args.output)
    for city, data in r["cities"].items():
        p_enr = data["enriched"]["policy"]
        p_phys = data["physics_only"]["policy"]
        print(f"{city:12s} decision={p_enr['decision']:8s} alpha={p_enr['alpha']:.2f}  "
              f"sim={p_enr['similarity']:.3f}  "
              f"conv_phys={data['physics_only']['convergence_day']:3d}  "
              f"conv_enr={data['enriched']['convergence_day']:3d}  "
              f"sources={p_enr['top_sources'][:3]}")
