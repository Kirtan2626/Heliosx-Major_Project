"""
Terrain-aware horizon profile from free SRTM digital-elevation tiles.

For installations near hills or in valleys, the analytical sun position
is correct but the panel only sees the sun once it clears the local
horizon. This module pre-computes a per-azimuth horizon altitude angle
once at install time and stores it as a 360-element NumPy array. The
runtime Physics Engine then masks the sun whenever its altitude is
below the horizon altitude for the current azimuth.

Data source
-----------
NASA SRTM 1-arc-second (≈ 30 m) DEM, free, world-wide. We use the
`elevation` Python package to fetch tiles and `rasterio` to read them.
Both are optional install-time-only dependencies.

Output
------
A `(360,)` float64 array of horizon altitude angles in degrees, indexed
by integer azimuth from 0° (North) to 359°.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Iterable

import numpy as np

EARTH_RADIUS_M = 6_371_000.0


def compute_horizon_profile(
    lat: float,
    lon: float,
    dem_path: str | Path,
    radius_m: float = 10_000.0,
    n_samples: int = 200,
    azimuth_step_deg: float = 1.0,
) -> np.ndarray:
    """
    Ray-march out from (lat, lon) along every azimuth and return the
    maximum apparent altitude angle of the terrain seen along that ray.

    Parameters
    ----------
    lat, lon       : install coordinate (degrees)
    dem_path       : path to a GeoTIFF DEM tile that covers the search disk
    radius_m       : ray-march radius in metres (default 10 km)
    n_samples      : samples along each ray
    azimuth_step_deg : output angular resolution in degrees (default 1°)

    Returns
    -------
    np.ndarray of shape (int(360 / azimuth_step_deg),) with horizon
    altitude angles in degrees.
    """
    try:
        import rasterio
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            "horizon_dem requires `rasterio`. Install with `pip install rasterio`."
        ) from e

    with rasterio.open(dem_path) as src:
        dem = src.read(1).astype(np.float64)
        transform = src.transform

        def sample_elev(plat: float, plon: float) -> float:
            row, col = src.index(plon, plat)
            row = max(0, min(dem.shape[0] - 1, int(row)))
            col = max(0, min(dem.shape[1] - 1, int(col)))
            return float(dem[row, col])

        eye_elev = sample_elev(lat, lon)

        n_az = int(round(360.0 / azimuth_step_deg))
        horizon = np.zeros(n_az, dtype=np.float64)
        distances = np.linspace(radius_m / n_samples, radius_m, n_samples)

        for i in range(n_az):
            az_deg = i * azimuth_step_deg
            max_alt = 0.0
            for d in distances:
                plat, plon = _project(lat, lon, az_deg, d)
                target_elev = sample_elev(plat, plon)
                # Account for Earth curvature drop along the ray
                drop = (d * d) / (2.0 * EARTH_RADIUS_M)
                effective = target_elev - eye_elev - drop
                if effective <= 0.0:
                    continue
                alt_deg = math.degrees(math.atan2(effective, d))
                if alt_deg > max_alt:
                    max_alt = alt_deg
            horizon[i] = max_alt
        return horizon


def _project(lat: float, lon: float, az_deg: float, dist_m: float) -> tuple[float, float]:
    """Forward geodesic on a sphere — sufficient for ≤ 50 km radii."""
    lat_r = math.radians(lat)
    lon_r = math.radians(lon)
    az_r = math.radians(az_deg)
    ang = dist_m / EARTH_RADIUS_M
    sin_lat2 = math.sin(lat_r) * math.cos(ang) + math.cos(lat_r) * math.sin(ang) * math.cos(az_r)
    lat2 = math.asin(sin_lat2)
    dlon = math.atan2(
        math.sin(az_r) * math.sin(ang) * math.cos(lat_r),
        math.cos(ang) - math.sin(lat_r) * sin_lat2,
    )
    return math.degrees(lat2), math.degrees(lon_r + dlon)


def is_sun_visible(sun_alt_deg: float, sun_az_deg: float, horizon: np.ndarray) -> bool:
    """Runtime check: True if the sun is above the local terrain horizon."""
    if horizon.size == 0:
        return sun_alt_deg > 0.0
    step = 360.0 / horizon.size
    idx = int(round((sun_az_deg % 360.0) / step)) % horizon.size
    return sun_alt_deg > horizon[idx]


def save_horizon(horizon: np.ndarray, out_path: str | Path) -> None:
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    np.save(out_path, horizon)


def load_horizon(in_path: str | Path) -> np.ndarray:
    return np.load(in_path)


def fetch_dem_tile(lat: float, lon: float, out_path: str | Path, buffer_deg: float = 0.2) -> Path:
    """
    Download an SRTM tile covering a small bounding box around (lat, lon)
    using the `elevation` package. Returns the path to the GeoTIFF.
    """
    try:
        import elevation
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            "fetch_dem_tile requires `elevation`. Install with `pip install elevation`."
        ) from e
    out_path = Path(out_path).resolve()
    bounds = (lon - buffer_deg, lat - buffer_deg, lon + buffer_deg, lat + buffer_deg)
    elevation.clip(bounds=bounds, output=str(out_path), product="SRTM1")
    return out_path


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Compute terrain horizon profile from SRTM")
    p.add_argument("--lat", type=float, required=True)
    p.add_argument("--lon", type=float, required=True)
    p.add_argument("--dem", required=True, help="GeoTIFF path (use --fetch to download)")
    p.add_argument("--fetch", action="store_true", help="download SRTM tile first")
    p.add_argument("--radius-m", type=float, default=10_000.0)
    p.add_argument("--out", default="deployment/horizon_profile.npy")
    args = p.parse_args()
    if args.fetch:
        fetch_dem_tile(args.lat, args.lon, args.dem)
    h = compute_horizon_profile(args.lat, args.lon, args.dem, radius_m=args.radius_m)
    save_horizon(h, args.out)
    print(f"horizon: max={h.max():.2f}°  mean={h.mean():.2f}°  -> {args.out}")
