"""
Solar Tracking Environment — Gymnasium-compatible MDP.

One episode = one day (sunrise to sunset).
Timestep = 30 minutes.
State = 14-dim continuous from measured data.
Action = 13 discrete.
Reward = measured energy + shaping.

Supports two modes:
- Data-driven (default): uses processed parquet files
- Synthetic: generates data from physics engine (for testing)
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import gymnasium
import numpy as np
import pandas as pd
from gymnasium import spaces

sys.path.insert(0, str(Path(__file__).parent.parent))

from physics_engine.solar_core import sun_position, clear_sky_dni, air_mass
from physics_engine.obstacle_engine import load_shadow_profile, compute_shadow_factor
from environment.state_builder import build_state
from environment.reward import compute_reward


class SolarTrackingEnv(gymnasium.Env):
    """
    Solar panel tracking environment.

    Observation: 14-dim continuous vector (see state_builder.py)
    Action: 13 discrete actions (see config/default.yaml action_table)
    Reward: Energy captured + shaping bonuses
    """

    metadata = {"render_modes": []}

    def __init__(
        self,
        config: dict,
        city_name: str,
        city_config: dict = None,
        synthetic: bool = False,
        specific_date: datetime = None,
        regime_vector: np.ndarray = None,
    ):
        """
        Initialize the solar tracking environment.

        Args:
            config: Full configuration dict
            city_name: City identifier (e.g., 'delhi')
            city_config: City-specific config (lat, lon, etc.)
            synthetic: If True, generate data from physics engine
            specific_date: If set, always use this date (for evaluation)
        """
        super().__init__()

        self.config = config
        self.city_name = city_name
        self.synthetic = synthetic
        self.specific_date = specific_date

        # Get city config
        if city_config is None:
            city_config = config["cities"][city_name]
        self.city = city_config
        self.lat = city_config["lat"]
        self.lon = city_config["lon"]
        self.alt_m = city_config["alt_m"]
        self.utc_offset = city_config["utc_offset"]

        # Regime conditioning: if a regime vector is supplied, the
        # observation dim becomes base_dim + len(regime_vector).
        self.regime_vector = (
            np.asarray(regime_vector, dtype=np.float32) if regime_vector is not None else None
        )
        base_state_dim = config["state"].get("base_dim", config["state"]["dim"])
        if self.regime_vector is not None:
            self._obs_dim = base_state_dim + int(self.regime_vector.shape[0])
        else:
            self._obs_dim = config["state"]["dim"]

        # Action and observation spaces
        action_table = config["actions"]["action_table"]
        self.action_table = action_table
        self.action_space = spaces.Discrete(len(action_table))
        self.observation_space = spaces.Box(
            low=-1.0, high=1.0, shape=(self._obs_dim,), dtype=np.float32
        )

        # Environment parameters
        self.timestep_hours = config["environment"]["timestep_hours"]
        self.reward_config = config["reward"]

        # Load data if not synthetic
        self.irradiance_df = None
        self.aqi_df = None
        self.weather_df = None
        self.obstacles = []

        if not synthetic:
            self._load_data(config)

        # Shadow profiles are independent of irradiance data — always load
        # them so synthetic-mode episodes still encounter realistic obstacles.
        if not self.obstacles:
            processed_dir = Path(config["paths"]["processed_dir"])
            shadow_path = processed_dir / "shadow_profiles" / f"{self.city_name}_shadows.csv"
            if shadow_path.exists():
                self.obstacles = load_shadow_profile(shadow_path)

        # Episode state
        self.current_step = 0
        self.current_date = None
        self.timesteps = []
        self.episode_energy = 0.0
        self.prev_shadow_factor = 1.0

    def _load_data(self, config: dict):
        """Load processed data files for this city."""
        processed_dir = Path(config["paths"]["processed_dir"])

        # Irradiance
        irr_path = processed_dir / "irradiance" / f"{self.city_name}_hourly.parquet"
        if irr_path.exists():
            self.irradiance_df = pd.read_parquet(irr_path)

        # Air quality
        aqi_path = processed_dir / "air_quality" / f"{self.city_name}_hourly.parquet"
        if aqi_path.exists():
            self.aqi_df = pd.read_parquet(aqi_path)

        # Weather
        weather_path = processed_dir / "weather" / f"{self.city_name}_hourly.parquet"
        if weather_path.exists():
            self.weather_df = pd.read_parquet(weather_path)

        # Shadow profile
        shadow_path = processed_dir / "shadow_profiles" / f"{self.city_name}_shadows.csv"
        if shadow_path.exists():
            self.obstacles = load_shadow_profile(shadow_path)

    def _get_available_dates(self) -> list[datetime]:
        """Get list of dates with data available."""
        if self.irradiance_df is not None:
            dates = self.irradiance_df.index.normalize().unique()
            return [d.to_pydatetime() for d in dates]
        else:
            # Synthetic mode: generate dates
            return [datetime(2023, m, 15) for m in range(1, 13)]

    def _get_data_for_time(self, dt: datetime) -> dict:
        """Get measured data for a specific datetime."""
        if self.synthetic:
            return self._generate_synthetic_data(dt)

        data = {
            "dni": 0.0,
            "dhi": 0.0,
            "ghi": 0.0,
            "cloud_fraction": 0.0,
            "aqi": 50.0,
            "temperature": 25.0,
            "wind_speed": 3.0,
            "is_extreme_weather": False,
            "is_overcast": False,
        }

        # Look up irradiance
        if self.irradiance_df is not None:
            ts = pd.Timestamp(dt)
            if ts in self.irradiance_df.index:
                row = self.irradiance_df.loc[ts]
                data["dni"] = max(0, row.get("dni", 0))
                data["dhi"] = max(0, row.get("dhi", 0))
                data["ghi"] = max(0, row.get("ghi", 0))
                data["cloud_fraction"] = row.get("cloud_fraction", 0)
            else:
                # Find nearest hour
                idx = self.irradiance_df.index.get_indexer([ts], method="nearest")
                if idx[0] >= 0:
                    row = self.irradiance_df.iloc[idx[0]]
                    data["dni"] = max(0, row.get("dni", 0))
                    data["dhi"] = max(0, row.get("dhi", 0))
                    data["ghi"] = max(0, row.get("ghi", 0))
                    data["cloud_fraction"] = row.get("cloud_fraction", 0)

        # Look up AQI
        if self.aqi_df is not None:
            ts = pd.Timestamp(dt, tz="UTC") if self.aqi_df.index.tz else pd.Timestamp(dt)
            idx = self.aqi_df.index.get_indexer([ts], method="nearest")
            if idx[0] >= 0:
                row = self.aqi_df.iloc[idx[0]]
                data["aqi"] = row.get("aqi", 50)

        # Look up weather
        if self.weather_df is not None:
            ts = pd.Timestamp(dt)
            idx = self.weather_df.index.get_indexer([ts], method="nearest")
            if idx[0] >= 0:
                row = self.weather_df.iloc[idx[0]]
                data["is_extreme_weather"] = bool(row.get("is_extreme_weather", False))
                data["is_overcast"] = bool(row.get("is_overcast", False))
                data["wind_speed"] = row.get("wind_speed", 3.0)
                data["temperature"] = row.get("temperature", 25.0)

        return data

    def _generate_synthetic_data(self, dt: datetime) -> dict:
        """
        Generate synthetic data from physics engine.

        Uses correct UTC conversion (was missing utc_offset, corrupting DNI
        for all non-UTC cities such as Delhi, Tokyo, Dubai, Sydney).

        Adds deterministic cloud/weather variation keyed on (city, day-of-year)
        so the agent experiences the full range of conditions (overcast, extreme
        weather) and can learn when to use stow/diffuse modes.
        """
        # FIXED: apply UTC offset so sun position is computed at the correct
        # solar time, not at local-time-treated-as-UTC.
        dt_utc = (dt - timedelta(hours=self.utc_offset)).replace(tzinfo=timezone.utc)
        alt, az = sun_position(self.lat, self.lon, dt_utc)
        clear_dni = clear_sky_dni(alt, self.alt_m) if alt > 0 else 0.0

        # --- deterministic cloud model (reproducible, city + day keyed) ---
        day_of_year = dt.timetuple().tm_yday
        city_hash = sum(ord(c) for c in self.city_name)
        cloud_seed = (city_hash * 31 + day_of_year * 7) % 100

        # Assign weather category:  ~10% overcast, ~25% cloudy, ~65% clear
        if cloud_seed < 10:
            cloud_fraction = 0.9
            is_overcast = True
            is_extreme = cloud_seed < 3   # ~3% extreme-weather days
        elif cloud_seed < 35:
            cloud_fraction = 0.5
            is_overcast = False
            is_extreme = False
        else:
            cloud_fraction = float(cloud_seed % 20) / 100.0   # 0.00 – 0.19
            is_overcast = False
            is_extreme = False

        # Cloud attenuates DNI; partial compensation via increased DHI
        cloud_attenuation = max(0.05, 1.0 - cloud_fraction * 0.85)
        dni = clear_dni * cloud_attenuation
        dhi = max(clear_dni * 0.15, clear_dni * cloud_fraction * 0.30) if alt > 0 else 0.0

        # GHI uses the correct geometric formula: GHI = DNI*sin(alt) + DHI
        sin_alt = float(np.sin(np.radians(max(0.0, alt))))
        ghi = max(0.0, dni * sin_alt + dhi)

        # Seasonal temperature variation (hemisphere-aware)
        month = dt.month
        # Peak summer: July for NH, January for SH
        _base_temp = {
            "delhi": 28.0, "dubai": 32.0, "new_york": 14.0,
            "london": 11.0, "tokyo": 16.0, "sydney": 20.0,
        }.get(self.city_name, 20.0)
        hemisphere_sign = -1.0 if self.lat < 0 else 1.0
        seasonal_offset = hemisphere_sign * 10.0 * float(
            np.cos(np.radians((month - 7) * 30.0))
        )
        temperature = _base_temp + seasonal_offset

        # AQI: mild variation; worse for Delhi/Dubai
        base_aqi = {"delhi": 120.0, "dubai": 60.0}.get(self.city_name, 40.0)
        aqi = base_aqi + float(cloud_seed % 30) * 1.5

        return {
            "dni": dni,
            "dhi": dhi,
            "ghi": ghi,
            "cloud_fraction": cloud_fraction,
            "aqi": aqi,
            "temperature": temperature,
            "wind_speed": 3.0 + float(cloud_seed % 10) * 0.4,
            "is_extreme_weather": is_extreme,
            "is_overcast": is_overcast,
        }

    def reset(self, seed=None, options=None):
        """Reset environment for a new episode (one day)."""
        super().reset(seed=seed)

        # Select date
        if self.specific_date:
            self.current_date = self.specific_date
        else:
            available_dates = self._get_available_dates()
            if available_dates:
                idx = self.np_random.integers(0, len(available_dates))
                self.current_date = available_dates[idx]
            else:
                self.current_date = datetime(2023, 6, 15)

        # Build timestep schedule (sunrise to sunset, every 30 min)
        self.timesteps = []
        base_date = self.current_date.replace(hour=0, minute=0, second=0, microsecond=0)

        for half_hour in range(48):  # 0:00 to 23:30
            dt = base_date + timedelta(minutes=half_hour * 30)
            dt_utc = dt - timedelta(hours=self.utc_offset)  # Approximate local→UTC
            dt_utc = dt_utc.replace(tzinfo=timezone.utc)
            alt, _ = sun_position(self.lat, self.lon, dt_utc)
            if alt > 0.5:  # Include low-angle timesteps to capture horizon shadows
                self.timesteps.append(dt)

        if not self.timesteps:
            # Fallback: use 6 AM to 6 PM local
            for h in range(6, 19):
                self.timesteps.append(base_date + timedelta(hours=h))

        self.current_step = 0
        self.episode_energy = 0.0
        self.prev_shadow_factor = 1.0

        obs = self._get_observation()
        return obs, {"date": self.current_date, "city": self.city_name}

    def _get_observation(self) -> np.ndarray:
        """Build observation for current timestep."""
        if self.current_step >= len(self.timesteps):
            return np.zeros(self._obs_dim, dtype=np.float32)

        dt = self.timesteps[self.current_step]
        dt_utc = (dt - timedelta(hours=self.utc_offset)).replace(tzinfo=timezone.utc)

        # Sun position
        sun_alt, sun_az = sun_position(self.lat, self.lon, dt_utc)

        # Shadow factor
        shadow = compute_shadow_factor(sun_alt, sun_az, self.obstacles)

        # Measured data
        data = self._get_data_for_time(dt)

        # Day of year and hour
        day_of_year = dt.timetuple().tm_yday
        hour = dt.hour + dt.minute / 60.0

        state = build_state(
            sun_altitude_deg=max(0, sun_alt),
            sun_azimuth_deg=sun_az,
            hour=hour,
            day_of_year=day_of_year,
            cloud_fraction=data["cloud_fraction"],
            aqi=data["aqi"],
            shadow_factor=shadow,
            latitude=self.lat,
            longitude=self.lon,
            site_altitude_m=self.alt_m,
            current_dni=data["dni"],
            regime_vector=self.regime_vector,
        )

        self.prev_shadow_factor = shadow
        return state

    def step(self, action: int):
        """Execute one timestep (30 minutes)."""
        assert self.action_space.contains(action), f"Invalid action: {action}"

        dt = self.timesteps[self.current_step]
        dt_utc = (dt - timedelta(hours=self.utc_offset)).replace(tzinfo=timezone.utc)

        # Get current conditions
        sun_alt, sun_az = sun_position(self.lat, self.lon, dt_utc)
        data = self._get_data_for_time(dt)

        # Compute shadow factor (before and after action)
        shadow_before = compute_shadow_factor(sun_alt, sun_az, self.obstacles)

        # After action: model how panel orientation bias changes the effective
        # sun angle for shadow purposes.
        # A positive tilt_bias tilts the panel more upright → the panel looks
        # over lower obstacles → effective altitude INCREASES → use sun_alt + tilt_bias.
        # A positive az_bias rotates the panel clockwise → shifts effective azimuth.
        action_def = self.action_table[action]
        if action_def["mode"] == "track":
            adjusted_alt = sun_alt + action_def["tilt_bias"]   # FIX: was sun_alt - tilt_bias (inverted)
            adjusted_az = sun_az + action_def["az_bias"]
            shadow_after = compute_shadow_factor(adjusted_alt, adjusted_az, self.obstacles)
        else:
            shadow_after = shadow_before

        # Compute air mass for spectral correction
        am = air_mass(sun_alt) if sun_alt > 0 else 1.5

        # Compute reward with full physics
        env_cfg = self.config.get("environment", {})
        reward, info = compute_reward(
            action_id=action,
            action_table=self.action_table,
            dni=data["dni"],
            dhi=data["dhi"],
            shadow_factor_before=shadow_before,
            shadow_factor_after=shadow_after,
            cloud_fraction=data["cloud_fraction"],
            is_extreme_weather=data["is_extreme_weather"],
            is_overcast=data["is_overcast"],
            reward_config=self.reward_config,
            timestep_hours=self.timestep_hours,
            aqi=data["aqi"],
            ambient_temp_c=data["temperature"],
            air_mass_val=am,
            panel_efficiency=env_cfg.get("panel_efficiency", 0.20),
            panel_area_m2=env_cfg.get("panel_area_m2", 1.0),
        )

        # Track ONLY physical energy (not shaping bonuses)
        self.episode_energy += info.get("physical_energy", 0)

        # Advance timestep
        self.current_step += 1
        terminated = self.current_step >= len(self.timesteps)
        truncated = False

        # Get next observation
        if not terminated:
            obs = self._get_observation()
        else:
            obs = np.zeros(self._obs_dim, dtype=np.float32)

        info["step"] = self.current_step
        info["episode_energy"] = self.episode_energy
        info["shadow_before"] = shadow_before
        info["shadow_after"] = shadow_after
        info["measured_dni"] = data["dni"]
        info["measured_dhi"] = data["dhi"]
        info["wind_speed"] = data["wind_speed"]

        # Rich trace fields for publication figures (Section 6.3 / 6.4)
        hour = dt.hour + dt.minute / 60.0
        info["sun_alt"] = sun_alt
        info["sun_az"] = sun_az
        info["hour"] = hour
        # Panel tilt = sun_altitude + tilt_bias (tracking mode), panel az = sun_az + az_bias
        if action_def["mode"] == "track":
            info["panel_tilt"] = max(0, sun_alt + action_def["tilt_bias"])
            info["panel_az"] = sun_az + action_def["az_bias"]
        else:
            info["panel_tilt"] = 0.0  # stow/diffuse = flat
            info["panel_az"] = sun_az

        return obs, reward, terminated, truncated, info
