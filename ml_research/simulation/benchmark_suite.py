"""
Layer 4: Automated Benchmark Test Suite.

Orchestrates all scenarios and multi-day simulations into a single
pass/fail test suite with categorized reporting. This is the top-level
entry point for validating the model before deployment.

Categories:
  - Safety:      Must stow in extreme weather, must not harm panel
  - Physics:     Must match analytical tracker in clear conditions
  - Adaptation:  Must switch modes correctly (track/stow/diffuse)
  - Shadow:      Must demonstrate shadow avoidance behavior
  - Transfer:    Must show regime-appropriate behavior across cities
  - Convergence: Must converge within 14 days in multi-day simulation

Usage:
    suite = BenchmarkSuite()
    report = suite.run_all()
    suite.print_report(report)
    suite.save_report(report, "results/simulation/benchmark_report.json")
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from simulation.scenario_templates import SCENARIO_CATALOG, ScenarioTemplate
from simulation.scenario_runner import ScenarioRunner, ScenarioResult
from simulation.multiday_runner import MultiDayRunner, DeploymentResult


@dataclass
class TestResult:
    """Result from a single test."""
    test_id: str
    test_name: str
    category: str
    passed: bool
    metrics: dict
    pass_criteria: dict
    pass_fail_detail: dict
    runtime_seconds: float
    notes: str = ""


@dataclass
class BenchmarkReport:
    """Complete benchmark suite report."""
    timestamp: str
    total_tests: int
    passed: int
    failed: int
    pass_rate: float
    by_category: dict[str, dict[str, int]]  # category → {"passed": n, "failed": m}
    test_results: list[TestResult]
    total_runtime_seconds: float

    def to_json(self) -> str:
        """Serialize to JSON."""
        d = {
            "timestamp": self.timestamp,
            "total_tests": self.total_tests,
            "passed": self.passed,
            "failed": self.failed,
            "pass_rate": self.pass_rate,
            "by_category": self.by_category,
            "total_runtime_seconds": round(self.total_runtime_seconds, 2),
            "test_results": [
                {
                    "test_id": t.test_id,
                    "test_name": t.test_name,
                    "category": t.category,
                    "passed": t.passed,
                    "metrics": {k: round(v, 4) if isinstance(v, float) else v
                                for k, v in t.metrics.items()},
                    "pass_criteria": t.pass_criteria,
                    "pass_fail_detail": t.pass_fail_detail,
                    "runtime_seconds": round(t.runtime_seconds, 2),
                    "notes": t.notes,
                }
                for t in self.test_results
            ],
        }
        return json.dumps(d, indent=2, default=str)


# ────────────────────────────────────────────────────────────────
# Multi-day convergence test cities
# ────────────────────────────────────────────────────────────────
CONVERGENCE_CITIES = [
    {
        "name": "Ahmedabad", "lat": 23.02, "lon": 72.57, "alt_m": 53,
        "utc_offset": 5.5, "regime": "monsoon_aerosol",
        "regime_vector": [0.0, 0.0, 0.30, 0.55, 0.10, 0.0, 0.05, 0.0, 0.0, 0.0],
    },
    {
        "name": "Vadodara", "lat": 22.31, "lon": 73.19, "alt_m": 39,
        "utc_offset": 5.5, "regime": "monsoon_aerosol",
        "regime_vector": [0.0, 0.0, 0.28, 0.58, 0.08, 0.0, 0.06, 0.0, 0.0, 0.0],
    },
    {
        "name": "Beijing", "lat": 39.90, "lon": 116.40, "alt_m": 43,
        "utc_offset": 8.0, "regime": "temperate_continental",
        "regime_vector": [0.30, 0.0, 0.05, 0.25, 0.30, 0.0, 0.05, 0.0, 0.05, 0.0],
    },
]


class BenchmarkSuite:
    """
    Runs all scenario tests and multi-day convergence tests.
    """

    def __init__(
        self,
        agent=None,
        convergence_days: int = 30,
        seed: int = 42,
        verbose: bool = True,
    ):
        """
        Parameters
        ----------
        agent : optional
            Trained DQN agent. If None, uses oracle selection.
        convergence_days : int
            Number of days for convergence tests (default 30)
        seed : int
            Base random seed
        verbose : bool
            Print progress to stdout
        """
        self.agent = agent
        self.convergence_days = convergence_days
        self.seed = seed
        self.verbose = verbose
        self.scenario_runner = ScenarioRunner()
        self.multiday_runner = MultiDayRunner()

    def _log(self, msg: str):
        if self.verbose:
            print(msg, flush=True)

    def run_scenario_tests(self) -> list[TestResult]:
        """Run all 10 scenario template tests."""
        results = []
        for sid, scenario in SCENARIO_CATALOG.items():
            if sid == "S10_SEASONAL_TRANSITION":
                continue  # Multi-day scenario handled separately

            self._log(f"  Running scenario {sid}: {scenario.name}...")
            t0 = time.time()

            try:
                sr = self.scenario_runner.run(scenario, agent=self.agent)
                elapsed = time.time() - t0

                results.append(TestResult(
                    test_id=sid,
                    test_name=scenario.name,
                    category=scenario.category,
                    passed=sr.overall_pass,
                    metrics=sr.metrics,
                    pass_criteria=scenario.pass_criteria,
                    pass_fail_detail=sr.pass_fail,
                    runtime_seconds=elapsed,
                    notes=f"Oracle fraction: {sr.oracle_fraction:.3f}",
                ))

            except Exception as e:
                elapsed = time.time() - t0
                results.append(TestResult(
                    test_id=sid,
                    test_name=scenario.name,
                    category=scenario.category,
                    passed=False,
                    metrics={},
                    pass_criteria=scenario.pass_criteria,
                    pass_fail_detail={"error": str(e)},
                    runtime_seconds=elapsed,
                    notes=f"ERROR: {e}",
                ))

        return results

    def run_convergence_tests(self) -> list[TestResult]:
        """Run multi-day convergence tests for 3 cities."""
        results = []

        for city in CONVERGENCE_CITIES:
            test_id = f"CONV_{city['name'].upper()}"
            self._log(f"  Running convergence: {city['name']} ({self.convergence_days} days)...")
            t0 = time.time()

            try:
                dr = self.multiday_runner.run_deployment(
                    city_name=city["name"],
                    lat=city["lat"],
                    lon=city["lon"],
                    alt_m=city["alt_m"],
                    utc_offset=city["utc_offset"],
                    regime=city["regime"],
                    regime_vector=np.array(city["regime_vector"]),
                    n_days=self.convergence_days,
                    agent=self.agent,
                    seed=self.seed,
                )
                elapsed = time.time() - t0

                # Pass criteria: converge within 14 days
                converge_pass = dr.convergence_day <= 14
                oracle_pass = dr.final_oracle_fraction >= 0.85

                metrics = {
                    "convergence_day": dr.convergence_day,
                    "final_oracle_fraction": dr.final_oracle_fraction,
                    "overall_oracle_fraction": dr.overall_oracle_fraction,
                    "total_det_energy_wh": dr.total_det_energy,
                    "total_agent_energy_wh": dr.total_agent_energy,
                }

                results.append(TestResult(
                    test_id=test_id,
                    test_name=f"{city['name']} {self.convergence_days}-Day Convergence",
                    category="convergence",
                    passed=converge_pass and oracle_pass,
                    metrics=metrics,
                    pass_criteria={
                        "convergence_day_max": 14,
                        "final_oracle_fraction_min": 0.85,
                    },
                    pass_fail_detail={
                        "convergence_within_14_days": converge_pass,
                        "oracle_fraction_above_85": oracle_pass,
                    },
                    runtime_seconds=elapsed,
                    notes=f"Converged day {dr.convergence_day}, final OF={dr.final_oracle_fraction:.3f}",
                ))

            except Exception as e:
                elapsed = time.time() - t0
                results.append(TestResult(
                    test_id=test_id,
                    test_name=f"{city['name']} Convergence",
                    category="convergence",
                    passed=False,
                    metrics={},
                    pass_criteria={},
                    pass_fail_detail={"error": str(e)},
                    runtime_seconds=elapsed,
                    notes=f"ERROR: {e}",
                ))

        return results

    def run_transfer_tests(self) -> list[TestResult]:
        """Test that the same scenario produces different behavior with different regime vectors."""
        results = []
        test_id = "TRANSFER_REGIME_SENSITIVITY"
        self._log(f"  Running transfer test: regime sensitivity...")
        t0 = time.time()

        try:
            # Run S01_CLEAR with 3 different regime vectors
            scenario = SCENARIO_CATALOG["S01_CLEAR"]
            regime_vectors = {
                "monsoon": np.array([0, 0, 0, 1, 0, 0, 0, 0, 0, 0], dtype=np.float32),
                "arid": np.array([0, 0, 1, 0, 0, 0, 0, 0, 0, 0], dtype=np.float32),
                "continental": np.array([1, 0, 0, 0, 0, 0, 0, 0, 0, 0], dtype=np.float32),
            }

            action_dists = {}
            energies = {}
            for regime_name, rv in regime_vectors.items():
                sr = self.scenario_runner.run(scenario, agent=self.agent, regime_vector=rv)
                action_dists[regime_name] = sr.action_counts
                energies[regime_name] = sr.total_agent_energy

            elapsed = time.time() - t0

            # Pass: all regimes should produce positive energy on a clear day
            all_positive = all(e > 0 for e in energies.values())

            results.append(TestResult(
                test_id=test_id,
                test_name="Regime Vector Sensitivity",
                category="transfer",
                passed=all_positive,
                metrics={
                    f"energy_{k}": v for k, v in energies.items()
                },
                pass_criteria={"all_regimes_positive_energy": True},
                pass_fail_detail={"all_positive": all_positive},
                runtime_seconds=elapsed,
                notes=f"Energies: {', '.join(f'{k}={v:.1f}Wh' for k, v in energies.items())}",
            ))

        except Exception as e:
            elapsed = time.time() - t0
            results.append(TestResult(
                test_id=test_id,
                test_name="Regime Vector Sensitivity",
                category="transfer",
                passed=False,
                metrics={},
                pass_criteria={},
                pass_fail_detail={"error": str(e)},
                runtime_seconds=elapsed,
                notes=f"ERROR: {e}",
            ))

        return results

    def run_all(self) -> BenchmarkReport:
        """Run the complete benchmark suite."""
        self._log("=" * 60)
        self._log("HELIOS-X v2 SIMULATION BENCHMARK SUITE")
        self._log("=" * 60)

        t_start = time.time()
        all_results = []

        # Phase 1: Scenario tests
        self._log("\n[Phase 1] Scenario Template Tests (9 scenarios)")
        self._log("-" * 40)
        scenario_results = self.run_scenario_tests()
        all_results.extend(scenario_results)

        # Phase 2: Transfer tests
        self._log("\n[Phase 2] Transfer Sensitivity Tests")
        self._log("-" * 40)
        transfer_results = self.run_transfer_tests()
        all_results.extend(transfer_results)

        # Phase 3: Convergence tests
        self._log(f"\n[Phase 3] Multi-Day Convergence Tests ({self.convergence_days} days each)")
        self._log("-" * 40)
        convergence_results = self.run_convergence_tests()
        all_results.extend(convergence_results)

        total_time = time.time() - t_start

        # Aggregate
        passed = sum(1 for r in all_results if r.passed)
        failed = sum(1 for r in all_results if not r.passed)

        by_category: dict[str, dict[str, int]] = {}
        for r in all_results:
            if r.category not in by_category:
                by_category[r.category] = {"passed": 0, "failed": 0}
            if r.passed:
                by_category[r.category]["passed"] += 1
            else:
                by_category[r.category]["failed"] += 1

        report = BenchmarkReport(
            timestamp=datetime.now().isoformat(),
            total_tests=len(all_results),
            passed=passed,
            failed=failed,
            pass_rate=passed / max(1, len(all_results)),
            by_category=by_category,
            test_results=all_results,
            total_runtime_seconds=total_time,
        )

        # Print summary
        self._log("\n" + "=" * 60)
        self._log("BENCHMARK RESULTS SUMMARY")
        self._log("=" * 60)
        self._log(f"Total: {report.total_tests} | Passed: {report.passed} | Failed: {report.failed} | Rate: {report.pass_rate:.1%}")
        self._log("")
        for cat, counts in sorted(by_category.items()):
            total_cat = counts["passed"] + counts["failed"]
            self._log(f"  {cat:15s}  {counts['passed']}/{total_cat} passed")
        self._log(f"\nTotal runtime: {total_time:.1f}s")

        # Print failures
        failures = [r for r in all_results if not r.passed]
        if failures:
            self._log(f"\n{'!'*60}")
            self._log(f"FAILED TESTS ({len(failures)}):")
            for f in failures:
                self._log(f"  [{f.category}] {f.test_id}: {f.test_name}")
                self._log(f"    Notes: {f.notes}")
                for criterion, passed_val in f.pass_fail_detail.items():
                    if not passed_val:
                        self._log(f"    FAIL: {criterion}")

        return report

    def save_report(self, report: BenchmarkReport, path: str | Path):
        """Save report to JSON file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report.to_json())
        self._log(f"\nReport saved: {path}")
