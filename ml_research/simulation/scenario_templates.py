"""
Layer 1: Scenario Template Engine — 10 pre-defined test scenarios.

Each scenario defines time-varying weather profiles (cloud, AQI, wind,
temperature) as callable functions of hour-of-day, plus obstacle
configurations and expected agent behaviors. Scenarios are designed to
stress-test specific capabilities: safety (stow in storms), adaptation
(mode switching), shadow avoidance, seasonal behavior, etc.

Usage:
    from simulation.scenario_templates import SCENARIO_CATALOG, get_scenario
    scenario = get_scenario("S01_CLEAR")
    for hour in scenario.hours:
        cloud = scenario.cloud_profile(hour)
        aqi = scenario.aqi_profile(hour)
        ...
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from physics_engine.obstacle_engine import Obstacle


# ────────────────────────────────────────────────────────────────
# Scenario dataclass
# ────────────────────────────────────────────────────────────────
@dataclass
class ScenarioTemplate:
    """
    A single test scenario for the simulation framework.

    Attributes
    ----------
    scenario_id : str
        Unique identifier (e.g. "S01_CLEAR")
    name : str
        Human-readable scenario name
    description : str
        What this scenario tests and why
    lat, lon : float
        Coordinate for sun position computation
    alt_m : float
        Site altitude in meters
    utc_offset : float
        Hours offset from UTC
    date : datetime
        Specific date for this scenario
    cloud_profile : Callable[[float], float]
        Maps hour (6.0–18.0) → cloud_fraction (0.0–1.0)
    aqi_profile : Callable[[float], float]
        Maps hour → AQI (0–500)
    wind_profile : Callable[[float], float]
        Maps hour → wind speed (m/s)
    temp_profile : Callable[[float], float]
        Maps hour → ambient temperature (°C)
    obstacles : list[Obstacle]
        Shadow geometry for this scenario
    expected_actions : dict[str, list[int]]
        Maps time-range description → list of acceptable action IDs
    pass_criteria : dict[str, float]
        Metric name → threshold for pass/fail
    category : str
        Test category: "safety", "physics", "adaptation", "shadow", "transfer"
    difficulty : str
        "easy", "medium", "hard"
    """
    scenario_id: str
    name: str
    description: str
    lat: float
    lon: float
    alt_m: float = 0.0
    utc_offset: float = 0.0
    date: datetime = field(default_factory=lambda: datetime(2024, 6, 21))
    cloud_profile: Callable[[float], float] = field(default_factory=lambda: lambda h: 0.0)
    aqi_profile: Callable[[float], float] = field(default_factory=lambda: lambda h: 30.0)
    wind_profile: Callable[[float], float] = field(default_factory=lambda: lambda h: 3.0)
    temp_profile: Callable[[float], float] = field(default_factory=lambda: lambda h: 25.0)
    obstacles: list[Obstacle] = field(default_factory=list)
    expected_actions: dict[str, list[int]] = field(default_factory=dict)
    pass_criteria: dict[str, float] = field(default_factory=dict)
    category: str = "physics"
    difficulty: str = "easy"

    @property
    def hours(self) -> list[float]:
        """Timestep hours from 5.0 to 19.0 in 0.5 increments."""
        return [5.0 + 0.5 * i for i in range(29)]  # 5.0 to 19.0


# ────────────────────────────────────────────────────────────────
# Profile helper functions
# ────────────────────────────────────────────────────────────────
def _constant(value: float) -> Callable[[float], float]:
    """Returns a constant-value profile."""
    return lambda h: value


def _step(before: float, after: float, switch_hour: float) -> Callable[[float], float]:
    """Step function: returns `before` until switch_hour, then `after`."""
    return lambda h: before if h < switch_hour else after


def _ramp(start_val: float, end_val: float, start_hour: float, end_hour: float,
          baseline: float = 0.0) -> Callable[[float], float]:
    """Linear ramp from start_val to end_val between start_hour and end_hour."""
    def fn(h):
        if h < start_hour:
            return baseline
        if h > end_hour:
            return baseline
        frac = (h - start_hour) / max(0.01, end_hour - start_hour)
        return start_val + (end_val - start_val) * frac
    return fn


def _pulse(center_hour: float, width_hours: float, peak: float,
           baseline: float = 0.0) -> Callable[[float], float]:
    """Gaussian pulse centered at center_hour."""
    sigma = width_hours / 2.35  # FWHM to sigma
    def fn(h):
        return baseline + (peak - baseline) * math.exp(-0.5 * ((h - center_hour) / sigma) ** 2)
    return fn


def _alternating(period_hours: float, low: float, high: float) -> Callable[[float], float]:
    """Alternating square wave between low and high."""
    def fn(h):
        phase = (h % period_hours) / period_hours
        return high if phase < 0.5 else low
    return fn


def _diurnal(min_val: float, max_val: float, peak_hour: float = 14.0) -> Callable[[float], float]:
    """Smooth diurnal cycle (sinusoidal) peaking at peak_hour."""
    def fn(h):
        phase = 2.0 * math.pi * (h - peak_hour + 6) / 24.0
        return min_val + (max_val - min_val) * 0.5 * (1.0 + math.sin(phase))
    return fn


# ────────────────────────────────────────────────────────────────
# Shadow configuration helpers
# ────────────────────────────────────────────────────────────────
def _make_building_obstacle(
    obs_id: str, center_az: float, width_m: float, height_m: float,
    distance_m: float, penalty: float = 0.7
) -> Obstacle:
    """Create a building obstacle from physical parameters."""
    half_angle = math.degrees(math.atan(width_m / (2.0 * distance_m)))
    blocking_angle = math.degrees(math.atan(height_m / distance_m))
    return Obstacle(
        obstacle_id=obs_id,
        obstacle_name=f"building_{obs_id}",
        obstacle_type="building",
        az_min_deg=(center_az - half_angle) % 360,
        az_max_deg=(center_az + half_angle) % 360,
        alt_blocking_deg=blocking_angle,
        efficiency_penalty=penalty,
        source="simulation",
    )


# ────────────────────────────────────────────────────────────────
# THE 10 SCENARIOS
# ────────────────────────────────────────────────────────────────

S01_CLEAR = ScenarioTemplate(
    scenario_id="S01_CLEAR",
    name="Perfect Clear Sky",
    description=(
        "Baseline scenario: perfect clear sky, no obstacles, no AQI, moderate "
        "temperature. The agent should match the deterministic physics tracker "
        "exactly — any deviation from identity action (a3) wastes energy."
    ),
    lat=28.6139, lon=77.209, alt_m=216, utc_offset=5.5,
    date=datetime(2024, 3, 21),  # Equinox — balanced day
    cloud_profile=_constant(0.0),
    aqi_profile=_constant(20.0),
    wind_profile=_constant(3.0),
    temp_profile=_diurnal(18.0, 32.0),
    obstacles=[],
    expected_actions={
        "all_day": [3],  # Identity action throughout
    },
    pass_criteria={
        "oracle_fraction_min": 0.995,  # Must match physics within 0.5%
        "identity_action_rate_min": 0.90,  # Should use a3 ≥ 90% of time
    },
    category="physics",
    difficulty="easy",
)

S02_CLOUD_BURST = ScenarioTemplate(
    scenario_id="S02_CLOUD_BURST",
    name="Sudden Cloud Burst",
    description=(
        "Clear morning → sudden thick overcast at 11:00 → clears by 14:00. "
        "Tests mode switching: agent should switch to diffuse mode (a12) during "
        "overcast, then back to tracking after clearing."
    ),
    lat=51.5074, lon=-0.1278, alt_m=11, utc_offset=0.0,
    date=datetime(2024, 7, 15),
    cloud_profile=lambda h: 0.05 if h < 11.0 else (0.92 if h < 14.0 else 0.10),
    aqi_profile=_constant(35.0),
    wind_profile=_constant(4.0),
    temp_profile=_diurnal(14.0, 22.0),
    obstacles=[],
    expected_actions={
        "before_11": [3],      # Track normally
        "11_to_14": [12],      # Diffuse mode during overcast
        "after_14": [3],       # Resume tracking
    },
    pass_criteria={
        "mode_switch_count_max": 4,  # Should switch track→diffuse→track (2-4 switches)
        "oracle_fraction_min": 0.90,
    },
    category="adaptation",
    difficulty="medium",
)

S03_MONSOON = ScenarioTemplate(
    scenario_id="S03_MONSOON",
    name="Monsoon Day (Heavy Cloud + High AQI)",
    description=(
        "Delhi-like monsoon conditions: persistent 70% cloud cover, AQI "
        "fluctuating between 200-350, humid. Tests agent's ability to "
        "maximize energy under combined cloud + aerosol attenuation."
    ),
    lat=28.6139, lon=77.209, alt_m=216, utc_offset=5.5,
    date=datetime(2024, 8, 10),
    cloud_profile=lambda h: 0.65 + 0.15 * math.sin(2 * math.pi * h / 6),
    aqi_profile=lambda h: 250 + 80 * math.sin(2 * math.pi * (h - 8) / 12),
    wind_profile=_constant(5.0),
    temp_profile=_diurnal(26.0, 34.0),
    obstacles=[
        _make_building_obstacle("monsoon_b1", 120, 30, 20, 40, 0.65),
    ],
    expected_actions={
        "all_day": [3, 4, 5, 6],  # Identity or moderate positive tilt bias
    },
    pass_criteria={
        "oracle_fraction_min": 0.85,
        "energy_positive": True,  # Must generate some energy even in monsoon
    },
    category="adaptation",
    difficulty="hard",
)

S04_DUST_STORM = ScenarioTemplate(
    scenario_id="S04_DUST_STORM",
    name="Dust Storm Arrival & Clearing",
    description=(
        "AQI rises from 50 to 420 between 09:00–12:00 (dust storm arrival), "
        "peaks at noon, then clears by 16:00. Agent should consider stowing "
        "during peak dust, then resume tracking as AQI drops."
    ),
    lat=25.2048, lon=55.2708, alt_m=5, utc_offset=4.0,
    date=datetime(2024, 4, 15),
    cloud_profile=_constant(0.1),
    aqi_profile=lambda h: (
        50 + 370 * max(0, min(1, (h - 9) / 3)) if h < 12
        else 420 - 370 * max(0, min(1, (h - 12) / 4)) if h < 16
        else 50
    ),
    wind_profile=lambda h: (
        3.0 + 17.0 * max(0, min(1, (h - 9) / 3)) if h < 12
        else 20.0 - 17.0 * max(0, min(1, (h - 12) / 4))
    ),
    temp_profile=_diurnal(28.0, 42.0),
    obstacles=[],
    expected_actions={
        "before_10": [3, 2],    # Normal tracking
        "10_to_14": [11],       # Stow during peak (wind > 15 m/s)
        "after_15": [3, 2],     # Resume tracking
    },
    pass_criteria={
        "stow_rate_during_storm": 0.50,  # Should stow ≥ 50% during extreme wind
        "oracle_fraction_min": 0.70,
    },
    category="safety",
    difficulty="hard",
)

S05_SHADOW_OBSTACLE = ScenarioTemplate(
    scenario_id="S05_SHADOW_OBSTACLE",
    name="Building Shadow Sweep",
    description=(
        "A tall building to the east casts shadow from 07:00–10:30 as the sun "
        "rises. The agent should use tilt/azimuth bias to escape the shadow "
        "cone. After 10:30, shadow clears and agent should revert to identity."
    ),
    lat=40.7128, lon=-74.006, alt_m=10, utc_offset=-5.0,
    date=datetime(2024, 9, 15),
    cloud_profile=_constant(0.05),
    aqi_profile=_constant(40.0),
    wind_profile=_constant(3.0),
    temp_profile=_diurnal(16.0, 26.0),
    obstacles=[
        Obstacle(
            obstacle_id="tower_east",
            obstacle_name="East Office Tower",
            obstacle_type="building",
            az_min_deg=75,
            az_max_deg=135,
            alt_blocking_deg=28.0,
            efficiency_penalty=0.75,
            source="simulation",
        ),
    ],
    expected_actions={
        "07_to_10": [4, 5, 6, 9, 10],  # Positive tilt/azimuth bias to escape shadow
        "after_11": [3],                 # Identity once shadow clears
    },
    pass_criteria={
        "shadow_escape_rate_min": 0.40,
        "oracle_fraction_min": 0.90,
    },
    category="shadow",
    difficulty="medium",
)

S06_WINTER_LOW_SUN = ScenarioTemplate(
    scenario_id="S06_WINTER_LOW_SUN",
    name="Winter Solstice at High Latitude",
    description=(
        "December 21 at 50°N: short day (~8 hours of sun), maximum solar "
        "altitude only ~16°. Agent must use aggressive positive tilt bias "
        "throughout the day to capture energy at extreme low angles."
    ),
    lat=50.0, lon=14.0, alt_m=200, utc_offset=1.0,
    date=datetime(2024, 12, 21),
    cloud_profile=_constant(0.15),
    aqi_profile=_constant(30.0),
    wind_profile=_constant(5.0),
    temp_profile=_constant(-2.0),
    obstacles=[],
    expected_actions={
        "all_day": [3, 4, 5, 6, 9, 10],  # Identity or positive tilt; physics tracker already optimal at low angles
    },
    pass_criteria={
        "oracle_fraction_min": 0.95,  # Must capture ≥ 95% of deterministic tracker energy
        "energy_positive": True,       # Must generate energy even in winter
    },
    category="adaptation",
    difficulty="medium",
)

S07_TROPICAL_NOON = ScenarioTemplate(
    scenario_id="S07_TROPICAL_NOON",
    name="Tropical High-Noon (Sun Near Zenith)",
    description=(
        "June 21 at the equator: sun reaches ~88° altitude at noon. "
        "Panel should be nearly horizontal. Any tilt bias is actively "
        "harmful. Agent must use identity action exclusively."
    ),
    lat=1.35, lon=103.82, alt_m=15, utc_offset=8.0,
    date=datetime(2024, 6, 21),
    cloud_profile=_constant(0.1),
    aqi_profile=_constant(50.0),
    wind_profile=_constant(2.0),
    temp_profile=_diurnal(26.0, 33.0),
    obstacles=[],
    expected_actions={
        "10_to_14": [3],  # Identity action at high sun
    },
    pass_criteria={
        "identity_action_rate_min": 0.85,
        "oracle_fraction_min": 0.98,
    },
    category="physics",
    difficulty="easy",
)

S08_EXTREME_WEATHER = ScenarioTemplate(
    scenario_id="S08_EXTREME_WEATHER",
    name="Extreme Storm Conditions",
    description=(
        "Sustained windspeed > 20 m/s all day with heavy rain. "
        "Agent MUST stow the panel (a11) for safety. Generating energy "
        "is secondary to panel protection."
    ),
    lat=35.6762, lon=139.6503, alt_m=40, utc_offset=9.0,
    date=datetime(2024, 10, 12),
    cloud_profile=_constant(0.95),
    aqi_profile=_constant(25.0),
    wind_profile=_constant(25.0),
    temp_profile=_constant(15.0),
    obstacles=[],
    expected_actions={
        "all_day": [11],  # STOW — safety critical
    },
    pass_criteria={
        "stow_rate_during_storm_min": 0.90,  # Must stow ≥ 90% during extreme wind
    },
    category="safety",
    difficulty="easy",
)

S09_INTERMITTENT = ScenarioTemplate(
    scenario_id="S09_INTERMITTENT",
    name="Rapidly Alternating Cloud/Clear",
    description=(
        "Cloud fraction alternates between 0.1 and 0.9 every 30 minutes. "
        "Tests whether the agent can react quickly without oscillating "
        "between track and diffuse modes excessively."
    ),
    lat=-33.8688, lon=151.2093, alt_m=58, utc_offset=10.0,
    date=datetime(2024, 3, 15),
    cloud_profile=_alternating(1.0, 0.10, 0.90),  # 1-hour period, 30 min each
    aqi_profile=_constant(30.0),
    wind_profile=_constant(4.0),
    temp_profile=_diurnal(18.0, 28.0),
    obstacles=[],
    expected_actions={
        "clear_windows": [3],    # Track during clear
        "cloudy_windows": [12],  # Diffuse during overcast
    },
    pass_criteria={
        "oracle_fraction_min": 0.80,
        "mode_switch_count_max": 30,  # Alternating cloud naturally causes many switches
    },
    category="adaptation",
    difficulty="hard",
)

S10_SEASONAL_TRANSITION = ScenarioTemplate(
    scenario_id="S10_SEASONAL_TRANSITION",
    name="Summer → Autumn Transition (30-day)",
    description=(
        "Multi-day scenario: 30 days transitioning from summer to autumn. "
        "Day length shortens, sun altitude drops, temperature falls. "
        "Agent should progressively increase tilt bias over weeks. "
        "This scenario is run via the multi-day runner, not single-day."
    ),
    lat=40.7128, lon=-74.006, alt_m=10, utc_offset=-5.0,
    date=datetime(2024, 9, 1),  # Start of transition
    cloud_profile=lambda h: 0.15 + 0.03 * (h - 12) ** 2 / 36,
    aqi_profile=_constant(45.0),
    wind_profile=_constant(4.0),
    temp_profile=_diurnal(12.0, 24.0),
    obstacles=[
        _make_building_obstacle("autumn_b1", 150, 20, 15, 35, 0.5),
    ],
    expected_actions={
        "early_days": [3, 4],       # Minimal bias in early September
        "late_days": [5, 6, 9, 10], # Larger bias by late September
    },
    pass_criteria={
        "oracle_fraction_min": 0.88,
        "tilt_increase_trend": True,  # Verify progressive strategy shift
    },
    category="transfer",
    difficulty="hard",
)


# ────────────────────────────────────────────────────────────────
# Scenario catalog
# ────────────────────────────────────────────────────────────────
SCENARIO_CATALOG: dict[str, ScenarioTemplate] = {
    "S01_CLEAR": S01_CLEAR,
    "S02_CLOUD_BURST": S02_CLOUD_BURST,
    "S03_MONSOON": S03_MONSOON,
    "S04_DUST_STORM": S04_DUST_STORM,
    "S05_SHADOW_OBSTACLE": S05_SHADOW_OBSTACLE,
    "S06_WINTER_LOW_SUN": S06_WINTER_LOW_SUN,
    "S07_TROPICAL_NOON": S07_TROPICAL_NOON,
    "S08_EXTREME_WEATHER": S08_EXTREME_WEATHER,
    "S09_INTERMITTENT": S09_INTERMITTENT,
    "S10_SEASONAL_TRANSITION": S10_SEASONAL_TRANSITION,
}


def get_scenario(scenario_id: str) -> ScenarioTemplate:
    """Retrieve a scenario by ID."""
    if scenario_id not in SCENARIO_CATALOG:
        raise KeyError(
            f"Unknown scenario '{scenario_id}'. Available: {list(SCENARIO_CATALOG.keys())}"
        )
    return SCENARIO_CATALOG[scenario_id]


def list_scenarios() -> list[dict]:
    """Return summary info for all scenarios."""
    return [
        {
            "id": s.scenario_id,
            "name": s.name,
            "category": s.category,
            "difficulty": s.difficulty,
            "lat": s.lat,
            "lon": s.lon,
        }
        for s in SCENARIO_CATALOG.values()
    ]
