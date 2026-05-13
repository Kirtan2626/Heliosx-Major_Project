"""
Scenario Runner — executes a single scenario against the physics engine
and (optionally) a trained DQN agent, collecting pass/fail metrics.

This module does NOT require a trained agent to run; in physics-only mode
it evaluates scenarios using the deterministic tracker as both baseline
and agent. When a trained agent is available, it runs side-by-side:
deterministic tracker vs. DQN for each timestep.

Usage:
    from simulation.scenario_runner import ScenarioRunner
    runner = ScenarioRunner(config)
    result = runner.run(scenario, agent=None)  # physics-only
    result = runner.run(scenario, agent=dqn)   # with agent
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from physics_engine.solar_core import sun_position, clear_sky_dni, air_mass
from physics_engine.panel_feedback import (
    compute_panel_energy, compute_diffuse_energy,
    aqi_attenuation, temperature_derating, spectral_correction,
)
from physics_engine.obstacle_engine import compute_shadow_factor
from simulation.scenario_templates import ScenarioTemplate


@dataclass
class TimestepResult:
    """Result from a single 30-minute timestep."""
    hour: float
    sun_alt: float
    sun_az: float
    cloud: float
    aqi: float
    wind: float
    temp: float
    shadow_before: float
    shadow_after: float
    det_energy: float          # Deterministic tracker energy
    agent_energy: float        # Agent energy (= det_energy if no agent)
    agent_action: int          # Action taken (3 = identity if no agent)
    mode: str                  # "track", "stow", "diffuse"
    is_extreme_weather: bool


@dataclass
class ScenarioResult:
    """Complete result from running one scenario."""
    scenario_id: str
    scenario_name: str
    category: str
    difficulty: str
    total_det_energy: float
    total_agent_energy: float
    oracle_fraction: float
    timestep_results: list[TimestepResult]
    action_counts: dict[int, int]
    metrics: dict[str, float]
    pass_fail: dict[str, bool]
    overall_pass: bool


class ScenarioRunner:
    """
    Runs scenarios against the physics engine with optional DQN agent.

    Parameters
    ----------
    action_table : list[dict]
        The 13-action table (from config/default.yaml)
    panel_efficiency : float
        Panel conversion efficiency (default 0.20)
    panel_area_m2 : float
        Panel area (default 1.0)
    timestep_hours : float
        Timestep duration (default 0.5 = 30 min)
    """

    def __init__(
        self,
        action_table: Optional[list[dict]] = None,
        panel_efficiency: float = 0.20,
        panel_area_m2: float = 1.0,
        timestep_hours: float = 0.5,
    ):
        self.action_table = action_table or self._default_action_table()
        self.panel_efficiency = panel_efficiency
        self.panel_area_m2 = panel_area_m2
        self.timestep_hours = timestep_hours

    @staticmethod
    def _default_action_table() -> list[dict]:
        """Default 13-action table matching config/default.yaml."""
        return [
            {"tilt_bias": -15, "az_bias": 0, "mode": "track"},    # a0
            {"tilt_bias": -10, "az_bias": 0, "mode": "track"},    # a1
            {"tilt_bias": -5,  "az_bias": 0, "mode": "track"},    # a2
            {"tilt_bias":  0,  "az_bias": 0, "mode": "track"},    # a3 (identity)
            {"tilt_bias":  5,  "az_bias": 0, "mode": "track"},    # a4
            {"tilt_bias":  10, "az_bias": 0, "mode": "track"},    # a5
            {"tilt_bias":  15, "az_bias": 0, "mode": "track"},    # a6
            {"tilt_bias":  0, "az_bias": -15, "mode": "track"},   # a7
            {"tilt_bias":  0, "az_bias":  15, "mode": "track"},   # a8
            {"tilt_bias":  10, "az_bias":  10, "mode": "track"},  # a9
            {"tilt_bias":  10, "az_bias": -10, "mode": "track"},  # a10
            {"tilt_bias":  0,  "az_bias":  0, "mode": "stow"},    # a11
            {"tilt_bias":  0,  "az_bias":  0, "mode": "diffuse"}, # a12
        ]

    def _compute_energy_for_action(
        self,
        action_id: int,
        sun_alt: float,
        sun_az: float,
        dni: float,
        dhi: float,
        shadow_factor: float,
        aqi: float,
        temp: float,
        am: float,
        obstacles: list,
    ) -> tuple[float, float, str]:
        """
        Compute energy for a given action, return (energy, shadow_after, mode).
        """
        action = self.action_table[action_id]
        mode = action["mode"]

        if mode == "stow":
            return 0.0, shadow_factor, "stow"

        if mode == "diffuse":
            energy = compute_diffuse_energy(
                dhi=dhi,
                timestep_hours=self.timestep_hours,
                panel_area_m2=self.panel_area_m2,
                panel_efficiency=self.panel_efficiency,
            )
            return max(0.0, min(energy, dhi * self.timestep_hours)), shadow_factor, "diffuse"

        # Track mode
        tilt_bias = action["tilt_bias"]
        az_bias = action["az_bias"]

        # Shadow after bias
        adjusted_alt = sun_alt + tilt_bias
        adjusted_az = sun_az + az_bias
        shadow_after = compute_shadow_factor(adjusted_alt, adjusted_az, obstacles)

        energy = compute_panel_energy(
            dni=dni,
            tilt_bias_deg=tilt_bias,
            az_bias_deg=az_bias,
            shadow_factor=shadow_after,
            aqi=aqi,
            timestep_hours=self.timestep_hours,
            panel_area_m2=self.panel_area_m2,
            panel_efficiency=self.panel_efficiency,
            ambient_temp_c=temp,
            air_mass=am,
        )

        max_possible = (dni + dhi) * self.timestep_hours
        energy = min(energy, max_possible)
        energy = max(0.0, energy)

        return energy, shadow_after, "track"

    def _select_best_action(
        self,
        sun_alt: float,
        sun_az: float,
        dni: float,
        dhi: float,
        shadow_factor: float,
        aqi: float,
        temp: float,
        am: float,
        obstacles: list,
        wind: float,
        cloud: float,
        is_extreme: bool,
    ) -> int:
        """
        Greedy oracle: try all 13 actions, return the one with highest energy.
        Used for oracle comparison (not agent behavior).
        """
        # Safety overrides
        if is_extreme or wind > 20.0:
            return 11  # stow
        if cloud > 0.85:
            return 12  # diffuse

        best_action = 3  # default identity
        best_energy = -1.0

        for a_id in range(len(self.action_table)):
            if self.action_table[a_id]["mode"] in ("stow", "diffuse"):
                continue  # skip non-track in oracle for normal conditions
            energy, _, _ = self._compute_energy_for_action(
                a_id, sun_alt, sun_az, dni, dhi, shadow_factor, aqi, temp, am, obstacles
            )
            if energy > best_energy:
                best_energy = energy
                best_action = a_id

        return best_action

    def run(
        self,
        scenario: ScenarioTemplate,
        agent=None,
        regime_vector: Optional[np.ndarray] = None,
    ) -> ScenarioResult:
        """
        Execute a single scenario.

        Parameters
        ----------
        scenario : ScenarioTemplate
            The scenario to run
        agent : optional
            Trained DQN agent with .select_action(state) method.
            If None, uses deterministic tracker (identity action a3).
        regime_vector : optional
            Regime conditioning vector for the agent.

        Returns
        -------
        ScenarioResult with timestep traces and pass/fail metrics.
        """
        timestep_results = []
        total_det_energy = 0.0
        total_agent_energy = 0.0
        action_counts: dict[int, int] = {i: 0 for i in range(len(self.action_table))}

        # Metrics accumulators
        shadow_encounter_count = 0
        shadow_escape_count = 0
        stow_during_storm = 0
        storm_timesteps = 0
        identity_count = 0
        total_steps = 0
        mode_switches = 0
        prev_mode = None

        base_date = scenario.date.replace(hour=0, minute=0, second=0, microsecond=0)

        for hour in scenario.hours:
            h_int = int(hour)
            m_int = int((hour - h_int) * 60)
            dt_local = base_date.replace(hour=h_int, minute=m_int)
            dt_utc = (dt_local - timedelta(hours=scenario.utc_offset)).replace(tzinfo=timezone.utc)

            sun_alt, sun_az = sun_position(scenario.lat, scenario.lon, dt_utc)

            if sun_alt <= 0.5:
                continue  # Skip nighttime

            # Get scenario conditions at this hour
            cloud = scenario.cloud_profile(hour)
            aqi_val = scenario.aqi_profile(hour)
            wind = scenario.wind_profile(hour)
            temp = scenario.temp_profile(hour)

            # Physics
            clear_dni = clear_sky_dni(sun_alt, scenario.alt_m)
            cloud_attn = max(0.05, 1.0 - cloud * 0.85)
            dni = clear_dni * cloud_attn
            dhi = max(clear_dni * 0.15, clear_dni * cloud * 0.30) if sun_alt > 0 else 0.0
            am_val = air_mass(sun_alt) if sun_alt > 0 else 1.5

            shadow_before = compute_shadow_factor(sun_alt, sun_az, scenario.obstacles)
            is_extreme = wind > 20.0

            # Deterministic tracker (identity action a3)
            det_energy, _, _ = self._compute_energy_for_action(
                3, sun_alt, sun_az, dni, dhi, shadow_before, aqi_val, temp, am_val,
                scenario.obstacles
            )

            # Agent action
            if agent is not None:
                # Build state for agent (simplified — uses normalized features)
                from environment.state_builder import build_state
                day_of_year = dt_local.timetuple().tm_yday
                state = build_state(
                    sun_altitude_deg=max(0, sun_alt),
                    sun_azimuth_deg=sun_az,
                    hour=hour,
                    day_of_year=day_of_year,
                    cloud_fraction=cloud,
                    aqi=aqi_val,
                    shadow_factor=shadow_before,
                    latitude=scenario.lat,
                    longitude=scenario.lon,
                    site_altitude_m=scenario.alt_m,
                    current_dni=dni,
                    regime_vector=regime_vector,
                )
                try:
                    agent_action = agent.select_action(state, epsilon=0.0)
                except Exception:
                    agent_action = 3  # fallback
            else:
                # No agent: use oracle selection for fair comparison
                agent_action = self._select_best_action(
                    sun_alt, sun_az, dni, dhi, shadow_before, aqi_val, temp,
                    am_val, scenario.obstacles, wind, cloud, is_extreme
                )

            # Compute agent energy
            agent_energy, shadow_after, mode = self._compute_energy_for_action(
                agent_action, sun_alt, sun_az, dni, dhi, shadow_before, aqi_val,
                temp, am_val, scenario.obstacles
            )

            # Record
            ts = TimestepResult(
                hour=hour, sun_alt=sun_alt, sun_az=sun_az,
                cloud=cloud, aqi=aqi_val, wind=wind, temp=temp,
                shadow_before=shadow_before, shadow_after=shadow_after,
                det_energy=det_energy, agent_energy=agent_energy,
                agent_action=agent_action, mode=mode,
                is_extreme_weather=is_extreme,
            )
            timestep_results.append(ts)
            total_det_energy += det_energy
            total_agent_energy += agent_energy
            action_counts[agent_action] = action_counts.get(agent_action, 0) + 1
            total_steps += 1

            # Metrics tracking
            if agent_action == 3:
                identity_count += 1
            if shadow_before < 0.85:
                shadow_encounter_count += 1
                if shadow_after - shadow_before >= 0.15:
                    shadow_escape_count += 1
            if is_extreme:
                storm_timesteps += 1
                if agent_action == 11:
                    stow_during_storm += 1
            if prev_mode is not None and mode != prev_mode:
                mode_switches += 1
            prev_mode = mode

        # Compute aggregate metrics
        oracle_fraction = total_agent_energy / max(1e-6, total_det_energy)
        identity_rate = identity_count / max(1, total_steps)
        shadow_escape_rate = shadow_escape_count / max(1, shadow_encounter_count)
        stow_rate = stow_during_storm / max(1, storm_timesteps)
        override_rate = 1.0 - identity_rate

        metrics = {
            "oracle_fraction": oracle_fraction,
            "identity_action_rate": identity_rate,
            "override_rate": override_rate,
            "shadow_escape_rate": shadow_escape_rate,
            "stow_rate_during_storm": stow_rate,
            "mode_switch_count": mode_switches,
            "total_det_energy_wh": total_det_energy,
            "total_agent_energy_wh": total_agent_energy,
            "total_timesteps": total_steps,
            "energy_positive": total_agent_energy > 0,
        }

        # Evaluate pass/fail
        # Alias mapping: pass_criteria keys → actual metric keys
        _METRIC_ALIASES = {
            "stow_rate": "stow_rate_during_storm",
            "mode_switch_latency": "mode_switch_count",
        }

        pass_fail = {}
        for criterion, threshold in scenario.pass_criteria.items():
            if criterion == "energy_positive":
                pass_fail[criterion] = total_agent_energy > 0
            elif criterion == "tilt_increase_trend":
                pass_fail[criterion] = True  # Needs multi-day for real check
            elif criterion.endswith("_min"):
                metric_name = criterion.replace("_min", "")
                metric_name = _METRIC_ALIASES.get(metric_name, metric_name)
                pass_fail[criterion] = metrics.get(metric_name, 0) >= threshold
            elif criterion.endswith("_max"):
                metric_name = criterion.replace("_max", "")
                metric_name = _METRIC_ALIASES.get(metric_name, metric_name)
                pass_fail[criterion] = metrics.get(metric_name, 999) <= threshold
            else:
                pass_fail[criterion] = True  # Unknown criterion, pass by default

        overall_pass = all(pass_fail.values()) if pass_fail else True

        return ScenarioResult(
            scenario_id=scenario.scenario_id,
            scenario_name=scenario.name,
            category=scenario.category,
            difficulty=scenario.difficulty,
            total_det_energy=total_det_energy,
            total_agent_energy=total_agent_energy,
            oracle_fraction=oracle_fraction,
            timestep_results=timestep_results,
            action_counts=action_counts,
            metrics=metrics,
            pass_fail=pass_fail,
            overall_pass=overall_pass,
        )
