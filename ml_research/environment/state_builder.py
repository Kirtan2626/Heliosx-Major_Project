"""
State vector builder for the solar tracking environment.

Converts raw environmental data into the 14-dimensional continuous
state vector used by the DQN agent.
"""

import math

import numpy as np


def _finite_clamp(value: float, lo: float, hi: float, name: str) -> float:
    """Clamp numeric inputs before they enter the normalized observation vector."""
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite, got {value!r}")
    return max(lo, min(hi, value))


def build_state(
    sun_altitude_deg: float,
    sun_azimuth_deg: float,
    hour: float,
    day_of_year: int,
    cloud_fraction: float,
    aqi: float,
    shadow_factor: float,
    latitude: float,
    longitude: float,
    site_altitude_m: float,
    current_dni: float,
    regime_vector: np.ndarray = None,
) -> np.ndarray:
    """
    Build a 14-dimensional normalized state vector.

    All values are normalized to approximately [-1, 1] range.
    Cyclical features use sin/cos encoding.

    State vector indices:
        0:  sun altitude / 90
        1:  sin(sun azimuth)
        2:  cos(sun azimuth)
        3:  sin(hour of day)
        4:  cos(hour of day)
        5:  sin(day of year)
        6:  cos(day of year)
        7:  cloud fraction / 100 (if 0-100) or identity (if 0-1)
        8:  AQI / 500
        9:  shadow factor (identity, already 0-1)
        10: latitude / 90
        11: longitude / 180
        12: site altitude / 5000
        13: current DNI / 1200

    Args:
        sun_altitude_deg: Sun altitude (0-90 degrees)
        sun_azimuth_deg: Sun azimuth (0-360 degrees)
        hour: Hour of day (0-24)
        day_of_year: Day of year (1-365)
        cloud_fraction: Cloud cover (0-1 or 0-100)
        aqi: Air Quality Index (0-500)
        shadow_factor: Shadow factor (0-1)
        latitude: Site latitude (-90 to 90)
        longitude: Site longitude (-180 to 180)
        site_altitude_m: Site elevation (0-5000m)
        current_dni: Current DNI (0-1200 W/m²)

    Returns:
        NumPy array of shape (14,) with values in approximately [-1, 1]
    """
    sun_altitude_deg = _finite_clamp(sun_altitude_deg, 0.0, 90.0, "sun_altitude_deg")
    sun_azimuth_deg = _finite_clamp(sun_azimuth_deg, 0.0, 360.0, "sun_azimuth_deg")
    hour = _finite_clamp(hour, 0.0, 24.0, "hour")
    day_of_year = int(_finite_clamp(day_of_year, 1.0, 366.0, "day_of_year"))
    aqi = _finite_clamp(aqi, 0.0, 500.0, "aqi")
    shadow_factor = _finite_clamp(shadow_factor, 0.0, 1.0, "shadow_factor")
    latitude = _finite_clamp(latitude, -90.0, 90.0, "latitude")
    longitude = _finite_clamp(longitude, -180.0, 180.0, "longitude")
    site_altitude_m = _finite_clamp(site_altitude_m, 0.0, 5000.0, "site_altitude_m")
    current_dni = _finite_clamp(current_dni, 0.0, 1200.0, "current_dni")

    # Normalize cloud fraction to 0-1 if provided as percentage
    cloud_fraction = _finite_clamp(cloud_fraction, 0.0, 100.0, "cloud_fraction")
    if cloud_fraction > 1.0:
        cloud_fraction = cloud_fraction / 100.0

    # Cyclical encoding for azimuth (0-360 degrees)
    az_rad = 2.0 * math.pi * sun_azimuth_deg / 360.0
    az_sin = math.sin(az_rad)
    az_cos = math.cos(az_rad)

    # Cyclical encoding for hour of day (0-24)
    hour_rad = 2.0 * math.pi * hour / 24.0
    hour_sin = math.sin(hour_rad)
    hour_cos = math.cos(hour_rad)

    # Cyclical encoding for day of year (1-365)
    day_rad = 2.0 * math.pi * day_of_year / 365.0
    day_sin = math.sin(day_rad)
    day_cos = math.cos(day_rad)

    state = np.array([
        sun_altitude_deg / 90.0,          # [0, 1]
        az_sin,                            # [-1, 1]
        az_cos,                            # [-1, 1]
        hour_sin,                          # [-1, 1]
        hour_cos,                          # [-1, 1]
        day_sin,                           # [-1, 1]
        day_cos,                           # [-1, 1]
        cloud_fraction,                    # [0, 1]
        aqi / 500.0,                      # [0, 1]
        shadow_factor,                     # [0, 1]
        latitude / 90.0,                   # [-1, 1]
        longitude / 180.0,                 # [-1, 1]
        site_altitude_m / 5000.0,         # [0, 1]
        current_dni / 1200.0,             # [0, 1]
    ], dtype=np.float32)

    # Optional regime conditioning: append soft regime membership vector
    # so the network input becomes (14 + R)-dimensional. Used by the
    # RegimeConditionedQNetwork in agent/regime_conditioned_network.py.
    if regime_vector is not None:
        rv = np.asarray(regime_vector, dtype=np.float32).ravel()
        state = np.concatenate([state, rv]).astype(np.float32)

    return state
