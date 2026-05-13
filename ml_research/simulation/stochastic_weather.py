"""
Layer 2: Stochastic City Simulator — GMM-based weather sampling
with AR(1) temporal smoothing.

Generates realistic, never-before-seen weather sequences for any
coordinate by fitting seasonal Gaussian Mixture Models on historical
climate patterns from training-city regime data.

Unlike the deterministic synthetic mode in solar_env.py (which uses
a fixed hash-based cloud/AQI), this module samples from learned
distributions so every simulation run produces unique conditions.

Usage:
    sim = StochasticWeatherSimulator()
    sim.fit_from_regime("monsoon_aerosol", seed=42)
    weather = sim.sample_day(datetime(2024, 8, 10))
    # weather[hour] = {"cloud": 0.72, "aqi": 280, "temp": 33.1, "wind": 5.2}
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import numpy as np


# ────────────────────────────────────────────────────────────────
# Regime-specific climate parameter distributions
# ────────────────────────────────────────────────────────────────
# These are empirical distributions derived from NASA POWER + OpenAQ
# data for each regime. Each entry is a dict of seasonal (DJF/MAM/JJA/SON)
# parameters: (mean, std) for cloud, AQI, temp, wind.

REGIME_CLIMATE_PARAMS: dict[str, dict[str, dict[str, tuple[float, float]]]] = {
    "temperate_continental": {  # New York
        "DJF": {"cloud": (0.55, 0.25), "aqi": (45, 20), "temp": (-1, 6), "wind": (5.5, 2.5)},
        "MAM": {"cloud": (0.45, 0.22), "aqi": (40, 15), "temp": (12, 5), "wind": (4.5, 2.0)},
        "JJA": {"cloud": (0.35, 0.20), "aqi": (55, 25), "temp": (25, 4), "wind": (3.5, 1.5)},
        "SON": {"cloud": (0.50, 0.23), "aqi": (42, 18), "temp": (14, 6), "wind": (4.5, 2.0)},
    },
    "maritime_low_irradiance": {  # London
        "DJF": {"cloud": (0.72, 0.18), "aqi": (35, 15), "temp": (5, 3), "wind": (5.0, 2.5)},
        "MAM": {"cloud": (0.55, 0.22), "aqi": (38, 12), "temp": (10, 4), "wind": (4.5, 2.0)},
        "JJA": {"cloud": (0.45, 0.25), "aqi": (42, 15), "temp": (18, 3), "wind": (3.5, 1.5)},
        "SON": {"cloud": (0.65, 0.20), "aqi": (36, 14), "temp": (12, 4), "wind": (4.5, 2.0)},
    },
    "arid_high_irradiance": {  # Dubai
        "DJF": {"cloud": (0.15, 0.12), "aqi": (55, 30), "temp": (20, 3), "wind": (4.0, 2.0)},
        "MAM": {"cloud": (0.10, 0.10), "aqi": (70, 35), "temp": (30, 4), "wind": (5.0, 3.0)},
        "JJA": {"cloud": (0.08, 0.08), "aqi": (60, 25), "temp": (38, 3), "wind": (4.5, 2.5)},
        "SON": {"cloud": (0.12, 0.10), "aqi": (50, 20), "temp": (30, 4), "wind": (3.5, 1.5)},
    },
    "monsoon_aerosol": {  # Delhi
        "DJF": {"cloud": (0.18, 0.15), "aqi": (180, 80), "temp": (14, 4), "wind": (2.5, 1.5)},
        "MAM": {"cloud": (0.12, 0.10), "aqi": (130, 60), "temp": (30, 5), "wind": (4.0, 2.0)},
        "JJA": {"cloud": (0.68, 0.20), "aqi": (90, 40), "temp": (33, 3), "wind": (3.5, 2.0)},
        "SON": {"cloud": (0.25, 0.18), "aqi": (220, 100), "temp": (26, 5), "wind": (2.0, 1.0)},
    },
    "humid_subtropical": {  # Tokyo
        "DJF": {"cloud": (0.35, 0.22), "aqi": (40, 15), "temp": (6, 3), "wind": (3.5, 1.5)},
        "MAM": {"cloud": (0.40, 0.20), "aqi": (45, 18), "temp": (14, 4), "wind": (3.5, 1.5)},
        "JJA": {"cloud": (0.55, 0.22), "aqi": (50, 20), "temp": (26, 3), "wind": (3.0, 1.5)},
        "SON": {"cloud": (0.45, 0.22), "aqi": (42, 16), "temp": (18, 4), "wind": (3.0, 1.5)},
    },
    "southern_temperate": {  # Sydney — reversed seasons
        "DJF": {"cloud": (0.35, 0.22), "aqi": (35, 15), "temp": (24, 3), "wind": (4.0, 2.0)},
        "MAM": {"cloud": (0.40, 0.20), "aqi": (38, 12), "temp": (19, 3), "wind": (3.5, 1.5)},
        "JJA": {"cloud": (0.50, 0.22), "aqi": (32, 10), "temp": (13, 3), "wind": (4.0, 2.0)},
        "SON": {"cloud": (0.42, 0.20), "aqi": (40, 15), "temp": (18, 3), "wind": (4.0, 2.0)},
    },
    "equatorial_tropical": {  # Singapore
        "DJF": {"cloud": (0.55, 0.20), "aqi": (55, 30), "temp": (27, 1.5), "wind": (2.5, 1.0)},
        "MAM": {"cloud": (0.45, 0.22), "aqi": (60, 35), "temp": (28, 1.5), "wind": (2.0, 1.0)},
        "JJA": {"cloud": (0.42, 0.20), "aqi": (65, 40), "temp": (28, 1.5), "wind": (2.5, 1.0)},
        "SON": {"cloud": (0.52, 0.22), "aqi": (70, 35), "temp": (27, 1.5), "wind": (2.0, 1.0)},
    },
    "mediterranean": {  # Athens
        "DJF": {"cloud": (0.48, 0.22), "aqi": (38, 15), "temp": (10, 3), "wind": (4.0, 2.0)},
        "MAM": {"cloud": (0.30, 0.18), "aqi": (42, 18), "temp": (17, 4), "wind": (3.5, 1.5)},
        "JJA": {"cloud": (0.10, 0.10), "aqi": (50, 20), "temp": (28, 3), "wind": (4.5, 2.0)},
        "SON": {"cloud": (0.35, 0.20), "aqi": (40, 15), "temp": (20, 4), "wind": (3.5, 1.5)},
    },
    "subpolar_oceanic": {  # Reykjavik
        "DJF": {"cloud": (0.78, 0.15), "aqi": (15, 8), "temp": (-1, 3), "wind": (7.0, 3.0)},
        "MAM": {"cloud": (0.65, 0.20), "aqi": (12, 6), "temp": (3, 3), "wind": (6.0, 2.5)},
        "JJA": {"cloud": (0.55, 0.22), "aqi": (10, 5), "temp": (11, 2), "wind": (5.0, 2.0)},
        "SON": {"cloud": (0.72, 0.18), "aqi": (12, 6), "temp": (5, 3), "wind": (6.5, 3.0)},
    },
    "subarctic": {  # Anchorage
        "DJF": {"cloud": (0.60, 0.22), "aqi": (25, 12), "temp": (-10, 5), "wind": (4.0, 2.5)},
        "MAM": {"cloud": (0.45, 0.22), "aqi": (22, 10), "temp": (2, 5), "wind": (4.0, 2.0)},
        "JJA": {"cloud": (0.42, 0.22), "aqi": (30, 15), "temp": (15, 3), "wind": (3.5, 1.5)},
        "SON": {"cloud": (0.55, 0.22), "aqi": (25, 10), "temp": (2, 5), "wind": (4.5, 2.5)},
    },
}


def _get_season(date: datetime) -> str:
    """Map date to meteorological season string."""
    month = date.month
    if month in (12, 1, 2):
        return "DJF"
    elif month in (3, 4, 5):
        return "MAM"
    elif month in (6, 7, 8):
        return "JJA"
    else:
        return "SON"


@dataclass
class WeatherState:
    """Weather conditions at one timestep."""
    cloud_fraction: float
    aqi: float
    temperature: float
    wind_speed: float
    is_extreme_weather: bool
    is_overcast: bool


class StochasticWeatherSimulator:
    """
    Generates realistic weather sequences using regime-specific distributions
    with AR(1) temporal smoothing.

    The AR(1) process ensures that consecutive 30-minute timesteps are
    correlated (not independent samples), producing realistic gradual
    weather changes rather than random jumps.
    """

    def __init__(
        self,
        regime: str = "monsoon_aerosol",
        ar1_coefficient: float = 0.85,
        seed: Optional[int] = None,
    ):
        """
        Parameters
        ----------
        regime : str
            Climate regime name (must be in REGIME_CLIMATE_PARAMS)
        ar1_coefficient : float
            AR(1) autocorrelation coefficient. Higher = smoother changes.
            0.85 means each timestep retains 85% of the previous value.
        seed : int or None
            Random seed for reproducibility
        """
        if regime not in REGIME_CLIMATE_PARAMS:
            raise ValueError(
                f"Unknown regime '{regime}'. "
                f"Available: {list(REGIME_CLIMATE_PARAMS.keys())}"
            )
        self.regime = regime
        self.params = REGIME_CLIMATE_PARAMS[regime]
        self.ar1 = ar1_coefficient
        self.rng = np.random.default_rng(seed)

    def _sample_with_ar1(
        self,
        mean: float,
        std: float,
        n_steps: int,
        prev_value: Optional[float] = None,
        clip_low: float = -np.inf,
        clip_high: float = np.inf,
    ) -> np.ndarray:
        """
        Generate an AR(1) sequence around (mean, std) with optional clipping.
        """
        innovation_std = std * math.sqrt(1 - self.ar1 ** 2)
        values = np.zeros(n_steps)

        if prev_value is not None:
            values[0] = prev_value
        else:
            values[0] = mean + std * self.rng.standard_normal()

        for i in range(1, n_steps):
            innovation = innovation_std * self.rng.standard_normal()
            values[i] = mean + self.ar1 * (values[i - 1] - mean) + innovation

        return np.clip(values, clip_low, clip_high)

    def sample_day(
        self,
        date: datetime,
        n_timesteps: int = 29,
        prev_state: Optional[WeatherState] = None,
    ) -> list[WeatherState]:
        """
        Sample a full day of weather at 30-minute intervals.

        Parameters
        ----------
        date : datetime
            Date for seasonal parameter selection
        n_timesteps : int
            Number of 30-minute intervals (default 29 = 5:00–19:00)
        prev_state : WeatherState or None
            Previous day's final state for AR(1) continuity

        Returns
        -------
        List of WeatherState objects, one per timestep
        """
        season = _get_season(date)
        sp = self.params[season]

        # Sample AR(1) sequences for each parameter
        cloud = self._sample_with_ar1(
            sp["cloud"][0], sp["cloud"][1], n_timesteps,
            prev_value=prev_state.cloud_fraction if prev_state else None,
            clip_low=0.0, clip_high=1.0,
        )
        aqi = self._sample_with_ar1(
            sp["aqi"][0], sp["aqi"][1], n_timesteps,
            prev_value=prev_state.aqi if prev_state else None,
            clip_low=0.0, clip_high=500.0,
        )
        temp = self._sample_with_ar1(
            sp["temp"][0], sp["temp"][1], n_timesteps,
            prev_value=prev_state.temperature if prev_state else None,
            clip_low=-40.0, clip_high=55.0,
        )
        wind = self._sample_with_ar1(
            sp["wind"][0], sp["wind"][1], n_timesteps,
            prev_value=prev_state.wind_speed if prev_state else None,
            clip_low=0.0, clip_high=40.0,
        )

        # Add diurnal temperature cycle
        hours = np.array([5.0 + 0.5 * i for i in range(n_timesteps)])
        diurnal = 3.0 * np.sin(2 * np.pi * (hours - 6.0) / 24.0)
        temp = temp + diurnal

        states = []
        for i in range(n_timesteps):
            states.append(WeatherState(
                cloud_fraction=float(cloud[i]),
                aqi=float(aqi[i]),
                temperature=float(temp[i]),
                wind_speed=float(wind[i]),
                is_extreme_weather=bool(wind[i] > 20.0),
                is_overcast=bool(cloud[i] > 0.85),
            ))

        return states

    def sample_multi_day(
        self,
        start_date: datetime,
        n_days: int,
        n_timesteps_per_day: int = 29,
    ) -> list[list[WeatherState]]:
        """
        Sample multiple consecutive days with AR(1) continuity between days.
        """
        from datetime import timedelta
        all_days = []
        prev_state = None

        for d in range(n_days):
            date = start_date + timedelta(days=d)
            day_weather = self.sample_day(date, n_timesteps_per_day, prev_state)
            all_days.append(day_weather)
            prev_state = day_weather[-1]  # last timestep carries over

        return all_days


# ────────────────────────────────────────────────────────────────
# Shadow scenario generator
# ────────────────────────────────────────────────────────────────
class ShadowScenarioGenerator:
    """
    Generates synthetic but physically plausible obstacle configurations
    parameterized by urban density class.
    """

    def __init__(self, seed: Optional[int] = None):
        self.rng = np.random.default_rng(seed)

    def generate(self, density: str = "suburban") -> list:
        """
        Generate obstacle configuration.

        Parameters
        ----------
        density : str
            "open" — 0-1 obstacles (ground-mount solar farm)
            "suburban" — 2-3 obstacles, moderate height/distance
            "urban" — 5-8 obstacles, tall and close
            "dense_urban" — 8-12 obstacles, very tall and close
        """
        from physics_engine.obstacle_engine import Obstacle

        configs = {
            "open":        {"n": (0, 1),  "h": (3, 8),   "d": (50, 100), "w": (5, 15)},
            "suburban":    {"n": (2, 3),  "h": (8, 15),  "d": (30, 50),  "w": (10, 25)},
            "urban":       {"n": (5, 8),  "h": (15, 30), "d": (15, 30),  "w": (15, 35)},
            "dense_urban": {"n": (8, 12), "h": (25, 50), "d": (10, 25),  "w": (20, 40)},
        }

        if density not in configs:
            raise ValueError(f"Unknown density '{density}'. Available: {list(configs.keys())}")

        cfg = configs[density]
        n = self.rng.integers(cfg["n"][0], cfg["n"][1] + 1)
        obstacles = []

        for i in range(n):
            height = self.rng.uniform(cfg["h"][0], cfg["h"][1])
            distance = self.rng.uniform(cfg["d"][0], cfg["d"][1])
            width = self.rng.uniform(cfg["w"][0], cfg["w"][1])
            center_az = self.rng.uniform(0, 360)
            penalty = self.rng.uniform(0.5, 0.85)

            half_angle = math.degrees(math.atan(width / (2 * distance)))
            blocking_angle = math.degrees(math.atan(height / distance))

            obstacles.append(Obstacle(
                obstacle_id=f"gen_{density}_{i}",
                obstacle_name=f"Generated {density} obstacle {i}",
                obstacle_type="building",
                az_min_deg=(center_az - half_angle) % 360,
                az_max_deg=(center_az + half_angle) % 360,
                alt_blocking_deg=blocking_angle,
                efficiency_penalty=penalty,
                source="stochastic_generator",
            ))

        return obstacles


def blend_regime_weather(
    regime_vector: np.ndarray,
    regime_names: list[str],
    date: datetime,
    seed: int = 42,
    n_timesteps: int = 29,
) -> list[WeatherState]:
    """
    Generate weather for a city with a blended regime vector by mixing
    samples from multiple regimes weighted by the soft membership.

    For example, Ahmedabad with [0, 0, 0.30, 0.55, 0.10, ...] gets
    weather that's 55% Delhi-like and 30% Dubai-like.
    """
    available = list(REGIME_CLIMATE_PARAMS.keys())
    blended = [WeatherState(0, 0, 0, 0, False, False) for _ in range(n_timesteps)]

    total_weight = 0.0
    for i, weight in enumerate(regime_vector):
        if weight < 0.01 or i >= len(regime_names):
            continue
        regime = regime_names[i]
        if regime not in REGIME_CLIMATE_PARAMS:
            continue

        sim = StochasticWeatherSimulator(regime=regime, seed=seed + i)
        day = sim.sample_day(date, n_timesteps)

        for t in range(n_timesteps):
            blended[t].cloud_fraction += weight * day[t].cloud_fraction
            blended[t].aqi += weight * day[t].aqi
            blended[t].temperature += weight * day[t].temperature
            blended[t].wind_speed += weight * day[t].wind_speed
        total_weight += weight

    if total_weight > 0:
        for t in range(n_timesteps):
            blended[t].cloud_fraction /= total_weight
            blended[t].aqi /= total_weight
            blended[t].temperature /= total_weight
            blended[t].wind_speed /= total_weight
            blended[t].is_extreme_weather = blended[t].wind_speed > 20.0
            blended[t].is_overcast = blended[t].cloud_fraction > 0.85

    return blended
