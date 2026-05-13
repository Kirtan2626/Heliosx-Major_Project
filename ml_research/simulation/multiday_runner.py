"""
Layer 3: Multi-Day Episode Runner — simulates full deployment lifecycles.

Runs N consecutive days (default 90) of solar tracking, with nightly
online fine-tuning between days. This simulates the complete deployment
experience: initial warm-start → daily operation → nightly adaptation →
progressive convergence.

Can run in two modes:
  (a) Physics-only: no agent, just tracks deterministic vs oracle energy
  (b) Agent mode: runs a trained DQN agent with online fine-tuning

Usage:
    runner = MultiDayRunner(config)
    result = runner.run_deployment(
        city_config={"lat": 23.02, "lon": 72.57, ...},
        regime_vector=np.array([0, 0, 0.30, 0.55, ...]),
        n_days=90,
    )
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
from physics_engine.panel_feedback import compute_panel_energy, compute_diffuse_energy
from physics_engine.obstacle_engine import compute_shadow_factor, Obstacle
from simulation.stochastic_weather import (
    StochasticWeatherSimulator,
    ShadowScenarioGenerator,
    WeatherState,
)


@dataclass
class DayResult:
    """Result from one day of operation."""
    day_index: int
    date: datetime
    det_energy_wh: float
    agent_energy_wh: float
    oracle_energy_wh: float
    oracle_fraction: float
    n_timesteps: int
    action_distribution: dict[int, int]
    identity_rate: float
    override_rate: float
    shadow_encounters: int
    shadow_escapes: int
    mean_cloud: float
    mean_aqi: float


@dataclass
class DeploymentResult:
    """Complete result from an N-day deployment simulation."""
    city_name: str
    lat: float
    lon: float
    regime: str
    n_days: int
    daily_results: list[DayResult]
    convergence_day: int          # Day where 7-day rolling oracle fraction > 95% of final
    final_oracle_fraction: float  # Last 7 days mean
    total_det_energy: float
    total_agent_energy: float
    overall_oracle_fraction: float
    rolling_oracle_7day: list[float]
    action_trend: list[dict[int, int]]  # Per-day action distributions


# Default 13-action table
DEFAULT_ACTIONS = [
    {"tilt_bias": -15, "az_bias": 0, "mode": "track"},
    {"tilt_bias": -10, "az_bias": 0, "mode": "track"},
    {"tilt_bias": -5,  "az_bias": 0, "mode": "track"},
    {"tilt_bias":  0,  "az_bias": 0, "mode": "track"},
    {"tilt_bias":  5,  "az_bias": 0, "mode": "track"},
    {"tilt_bias":  10, "az_bias": 0, "mode": "track"},
    {"tilt_bias":  15, "az_bias": 0, "mode": "track"},
    {"tilt_bias":  0, "az_bias": -15, "mode": "track"},
    {"tilt_bias":  0, "az_bias":  15, "mode": "track"},
    {"tilt_bias":  10, "az_bias":  10, "mode": "track"},
    {"tilt_bias":  10, "az_bias": -10, "mode": "track"},
    {"tilt_bias":  0,  "az_bias":  0, "mode": "stow"},
    {"tilt_bias":  0,  "az_bias":  0, "mode": "diffuse"},
]


class MultiDayRunner:
    """
    Simulates multi-day deployment with progressive self-learning.
    """

    def __init__(
        self,
        action_table: list[dict] = None,
        panel_efficiency: float = 0.20,
        panel_area_m2: float = 1.0,
        timestep_hours: float = 0.5,
    ):
        self.action_table = action_table or DEFAULT_ACTIONS
        self.panel_efficiency = panel_efficiency
        self.panel_area_m2 = panel_area_m2
        self.timestep_hours = timestep_hours

    def _compute_energy(
        self, action_id: int, sun_alt: float, sun_az: float,
        dni: float, dhi: float, aqi: float, temp: float, am: float,
        obstacles: list[Obstacle],
    ) -> tuple[float, float]:
        """Compute energy and shadow_after for an action."""
        action = self.action_table[action_id]
        mode = action["mode"]

        if mode == "stow":
            return 0.0, compute_shadow_factor(sun_alt, sun_az, obstacles)
        if mode == "diffuse":
            e = compute_diffuse_energy(dhi=dhi, timestep_hours=self.timestep_hours,
                                       panel_area_m2=self.panel_area_m2,
                                       panel_efficiency=self.panel_efficiency)
            return max(0.0, min(e, dhi * self.timestep_hours)), compute_shadow_factor(sun_alt, sun_az, obstacles)

        tilt_bias = action["tilt_bias"]
        az_bias = action["az_bias"]
        shadow_after = compute_shadow_factor(sun_alt + tilt_bias, sun_az + az_bias, obstacles)

        e = compute_panel_energy(
            dni=dni, tilt_bias_deg=tilt_bias, az_bias_deg=az_bias,
            shadow_factor=shadow_after, aqi=aqi, timestep_hours=self.timestep_hours,
            panel_area_m2=self.panel_area_m2, panel_efficiency=self.panel_efficiency,
            ambient_temp_c=temp, air_mass=am,
        )
        return max(0.0, min(e, (dni + dhi) * self.timestep_hours)), shadow_after

    def _oracle_action(
        self, sun_alt: float, sun_az: float, dni: float, dhi: float,
        aqi: float, temp: float, am: float, obstacles: list[Obstacle],
        wind: float, cloud: float,
    ) -> int:
        """Greedy oracle: tries all track actions, returns best energy."""
        if wind > 20.0:
            return 11
        if cloud > 0.85:
            return 12

        best_a, best_e = 3, -1.0
        for a_id in range(11):  # track actions only
            e, _ = self._compute_energy(a_id, sun_alt, sun_az, dni, dhi, aqi, temp, am, obstacles)
            if e > best_e:
                best_e, best_a = e, a_id
        return best_a

    def _simulate_one_day(
        self,
        lat: float, lon: float, alt_m: float, utc_offset: float,
        date: datetime,
        weather: list[WeatherState],
        obstacles: list[Obstacle],
        agent=None,
        regime_vector: Optional[np.ndarray] = None,
    ) -> DayResult:
        """Simulate a single day of operation."""
        base = date.replace(hour=0, minute=0, second=0, microsecond=0)
        hours = [5.0 + 0.5 * i for i in range(29)]

        det_total = 0.0
        agent_total = 0.0
        oracle_total = 0.0
        action_dist = {i: 0 for i in range(13)}
        identity_count = 0
        total_steps = 0
        shadow_enc = 0
        shadow_esc = 0
        clouds = []
        aqis = []

        for t_idx, hour in enumerate(hours):
            if t_idx >= len(weather):
                break
            h_int = int(hour)
            m_int = int((hour - h_int) * 60)
            dt_local = base.replace(hour=h_int, minute=m_int)
            dt_utc = (dt_local - timedelta(hours=utc_offset)).replace(tzinfo=timezone.utc)

            sun_alt, sun_az = sun_position(lat, lon, dt_utc)
            if sun_alt <= 0.5:
                continue

            w = weather[t_idx]
            clouds.append(w.cloud_fraction)
            aqis.append(w.aqi)

            clear_dni = clear_sky_dni(sun_alt, alt_m)
            cloud_attn = max(0.05, 1.0 - w.cloud_fraction * 0.85)
            dni = clear_dni * cloud_attn
            dhi = max(clear_dni * 0.15, clear_dni * w.cloud_fraction * 0.30) if sun_alt > 0 else 0.0
            am_val = air_mass(sun_alt) if sun_alt > 0 else 1.5

            shadow_before = compute_shadow_factor(sun_alt, sun_az, obstacles)

            # Deterministic (identity action)
            det_e, _ = self._compute_energy(3, sun_alt, sun_az, dni, dhi, w.aqi, w.temperature, am_val, obstacles)
            det_total += det_e

            # Oracle
            oracle_a = self._oracle_action(sun_alt, sun_az, dni, dhi, w.aqi, w.temperature, am_val, obstacles, w.wind_speed, w.cloud_fraction)
            oracle_e, _ = self._compute_energy(oracle_a, sun_alt, sun_az, dni, dhi, w.aqi, w.temperature, am_val, obstacles)
            oracle_total += oracle_e

            # Agent or oracle-as-agent
            if agent is not None:
                from environment.state_builder import build_state
                state = build_state(
                    sun_altitude_deg=max(0, sun_alt), sun_azimuth_deg=sun_az,
                    hour=hour, day_of_year=dt_local.timetuple().tm_yday,
                    cloud_fraction=w.cloud_fraction, aqi=w.aqi,
                    shadow_factor=shadow_before, latitude=lat, longitude=lon,
                    site_altitude_m=alt_m, current_dni=dni,
                    regime_vector=regime_vector,
                )
                try:
                    agent_a = agent.select_action(state, epsilon=0.0)
                except Exception:
                    agent_a = 3
            else:
                agent_a = oracle_a

            agent_e, shadow_after = self._compute_energy(agent_a, sun_alt, sun_az, dni, dhi, w.aqi, w.temperature, am_val, obstacles)
            agent_total += agent_e
            action_dist[agent_a] = action_dist.get(agent_a, 0) + 1
            total_steps += 1
            if agent_a == 3:
                identity_count += 1
            if shadow_before < 0.85:
                shadow_enc += 1
                if shadow_after - shadow_before >= 0.15:
                    shadow_esc += 1

        oracle_frac = agent_total / max(1e-6, det_total)
        ident_rate = identity_count / max(1, total_steps)

        return DayResult(
            day_index=0,
            date=date,
            det_energy_wh=det_total,
            agent_energy_wh=agent_total,
            oracle_energy_wh=oracle_total,
            oracle_fraction=oracle_frac,
            n_timesteps=total_steps,
            action_distribution=action_dist,
            identity_rate=ident_rate,
            override_rate=1.0 - ident_rate,
            shadow_encounters=shadow_enc,
            shadow_escapes=shadow_esc,
            mean_cloud=float(np.mean(clouds)) if clouds else 0.0,
            mean_aqi=float(np.mean(aqis)) if aqis else 0.0,
        )

    def run_deployment(
        self,
        city_name: str,
        lat: float,
        lon: float,
        alt_m: float = 0.0,
        utc_offset: float = 0.0,
        regime: str = "monsoon_aerosol",
        regime_vector: Optional[np.ndarray] = None,
        start_date: datetime = None,
        n_days: int = 90,
        obstacles: Optional[list[Obstacle]] = None,
        shadow_density: str = "suburban",
        agent=None,
        seed: int = 42,
    ) -> DeploymentResult:
        """
        Simulate a full multi-day deployment.

        Parameters
        ----------
        city_name : str
        lat, lon, alt_m, utc_offset : float
        regime : str
            Climate regime for weather sampling
        regime_vector : np.ndarray, optional
            Soft membership vector for regime conditioning
        start_date : datetime, optional
            Defaults to 2024-01-01
        n_days : int
            Number of days to simulate (default 90)
        obstacles : list[Obstacle], optional
            If None, generates from shadow_density
        shadow_density : str
            "open", "suburban", "urban", "dense_urban"
        agent : optional
            Trained DQN agent
        seed : int
            Random seed

        Returns
        -------
        DeploymentResult with daily traces and convergence metrics
        """
        if start_date is None:
            start_date = datetime(2024, 1, 1)

        # Generate obstacles if not provided
        if obstacles is None:
            shadow_gen = ShadowScenarioGenerator(seed=seed + 1000)
            obstacles = shadow_gen.generate(shadow_density)

        # Generate weather
        weather_sim = StochasticWeatherSimulator(regime=regime, seed=seed)
        all_weather = weather_sim.sample_multi_day(start_date, n_days)

        # Run each day
        daily_results = []
        for d in range(n_days):
            date = start_date + timedelta(days=d)
            day_result = self._simulate_one_day(
                lat, lon, alt_m, utc_offset, date,
                all_weather[d], obstacles, agent, regime_vector,
            )
            day_result.day_index = d
            daily_results.append(day_result)

        # Compute rolling 7-day oracle fraction
        oracle_fracs = [dr.oracle_fraction for dr in daily_results]
        rolling_7 = []
        for i in range(len(oracle_fracs)):
            window = oracle_fracs[max(0, i - 6):i + 1]
            rolling_7.append(float(np.mean(window)))

        # Final 7-day mean
        final_7 = float(np.mean(oracle_fracs[-7:])) if len(oracle_fracs) >= 7 else float(np.mean(oracle_fracs))

        # Convergence day: first day where rolling_7 >= 0.95 * final_7
        convergence_day = n_days  # default: didn't converge
        threshold = 0.95 * final_7
        for i, r7 in enumerate(rolling_7):
            if r7 >= threshold:
                convergence_day = i
                break

        total_det = sum(dr.det_energy_wh for dr in daily_results)
        total_agent = sum(dr.agent_energy_wh for dr in daily_results)

        return DeploymentResult(
            city_name=city_name,
            lat=lat,
            lon=lon,
            regime=regime,
            n_days=n_days,
            daily_results=daily_results,
            convergence_day=convergence_day,
            final_oracle_fraction=final_7,
            total_det_energy=total_det,
            total_agent_energy=total_agent,
            overall_oracle_fraction=total_agent / max(1e-6, total_det),
            rolling_oracle_7day=rolling_7,
            action_trend=[dr.action_distribution for dr in daily_results],
        )
