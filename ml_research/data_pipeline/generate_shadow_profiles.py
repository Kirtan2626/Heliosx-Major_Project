"""
Generate shadow profile CSVs from OSM building GeoJSON data.

Converts building footprints with heights into obstacle definitions
compatible with the obstacle_engine.
Output: data/processed/shadow_profiles/{city}_shadows.csv
"""

import csv
import json
import math
from pathlib import Path


def _blocking_angle(height_m: float, distance_m: float) -> float:
    """Compute blocking angle: arctan(height/distance) in degrees."""
    if distance_m <= 0:
        return 90.0
    return math.degrees(math.atan(height_m / distance_m))


def _azimuth_span(width_m: float, distance_m: float, bearing_deg: float) -> tuple[float, float]:
    """Compute azimuth min/max from building width and distance."""
    if distance_m <= 0:
        return 0.0, 360.0
    half_angle = math.degrees(math.atan(width_m / (2.0 * distance_m)))
    az_min = (bearing_deg - half_angle) % 360
    az_max = (bearing_deg + half_angle) % 360
    return az_min, az_max


# Per-city fallback heights (meters) for cities where OSM height/levels tags
# are missing. Reflects typical urban building heights for the target
# neighborhood. Used only when the GeoJSON feature has no height_m set.
CITY_DEFAULT_HEIGHT_M = {
    "delhi": 20.0,      # Connaught Place area: 5-8 story concrete buildings
    "dubai": 30.0,      # Downtown: mid/high-rise
    "new_york": 25.0,   # Midtown/Downtown: 6-10 story fallback
    "tokyo": 20.0,      # Mixed mid-rise
    "london": 18.0,     # 4-6 story Victorian/Edwardian
    "sydney": 18.0,     # CBD fallback
}

# Per-city minimum blocking angle override. Lower for sparse-OSM cities
# so that medium-distance buildings still register.
CITY_MIN_BLOCKING_ANGLE = {
    "delhi": 1.5,
    "dubai": 2.0,
}


def _efficiency_penalty(height_m: float, distance_m: float) -> float:
    """
    Estimate efficiency penalty based on building size relative to distance.

    Closer and taller buildings block more light. When an obstacle is actually
    in the sun's path, it should produce a meaningful shadow (not a token dip),
    otherwise the agent gets no learning signal from shadow events.
    """
    if distance_m <= 0:
        return 1.0
    ratio = height_m / distance_m
    # Stronger sigmoid: base 0.5, saturates near 0.95, with a 10x slope so
    # even far/short buildings (ratio ~0.04) give penalty ~0.65.
    penalty = min(0.95, 0.5 + 0.45 * (1 - math.exp(-10.0 * ratio)))
    return round(penalty, 3)


def generate_city(
    city_name: str,
    raw_dir: str | Path,
    output_dir: str | Path,
    min_blocking_angle: float = 3.0,
) -> Path:
    """
    Generate shadow profile CSV from OSM building GeoJSON.

    Args:
        city_name: City identifier
        raw_dir: Directory containing GeoJSON files
        output_dir: Output directory for shadow CSV
        min_blocking_angle: Minimum blocking angle to include (degrees)

    Returns:
        Path to output CSV file
    """
    raw_dir = Path(raw_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    geojson_files = list(raw_dir.glob(f"{city_name}_buildings.geojson"))
    if not geojson_files:
        raise FileNotFoundError(f"No OSM GeoJSON for {city_name}")

    print(f"  [{city_name}] Generating shadow profile...")

    with open(geojson_files[0], "r") as f:
        data = json.load(f)

    features = data.get("features", [])
    obstacles = []

    # Per-city overrides
    city_default_height = CITY_DEFAULT_HEIGHT_M.get(city_name, 9.0)
    effective_min_angle = CITY_MIN_BLOCKING_ANGLE.get(city_name, min_blocking_angle)

    for feature in features:
        props = feature.get("properties", {})
        height = props.get("height_m")
        height_source = props.get("height_source", "default")
        # Override missing or placeholder-default heights with the per-city
        # fallback. Real measured heights (height_source == 'height' or 'levels')
        # are preserved as-is.
        if height is None or height <= 0 or height_source == "default":
            height = city_default_height
        distance = props.get("distance_m", 100.0)
        bearing = props.get("bearing_deg", 180.0)
        width = props.get("width_m", 10.0)

        # Compute shadow parameters
        block_angle = _blocking_angle(height, distance)
        if block_angle < effective_min_angle:
            continue  # Too far/short to matter

        az_min, az_max = _azimuth_span(width, distance, bearing)
        penalty = _efficiency_penalty(height, distance)

        obstacles.append({
            "obstacle_id": f"osm_{props.get('id', 'unknown')}",
            "obstacle_name": props.get("name", f"Building"),
            "obstacle_type": props.get("type", "building"),
            "az_min_deg": round(az_min, 2),
            "az_max_deg": round(az_max, 2),
            "alt_blocking_deg": round(block_angle, 2),
            "efficiency_penalty": penalty,
            "source": f"osm_{props.get('height_source', 'default')}",
        })

    # Sort by blocking angle (most significant first)
    obstacles.sort(key=lambda x: x["alt_blocking_deg"], reverse=True)

    # Save CSV
    output_path = output_dir / f"{city_name}_shadows.csv"
    fieldnames = [
        "obstacle_id", "obstacle_name", "obstacle_type",
        "az_min_deg", "az_max_deg", "alt_blocking_deg",
        "efficiency_penalty", "source",
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(obstacles)

    print(f"  [{city_name}] {len(obstacles)} obstacles -> {output_path}")
    return output_path


def generate_all(config: dict) -> list[Path]:
    """Generate shadow profiles for all cities."""
    cities = config["cities"]
    raw_dir = Path(config["paths"]["raw_dir"]) / "osm_buildings"
    output_dir = Path(config["paths"]["processed_dir"]) / "shadow_profiles"

    paths = []
    for city_key in cities:
        try:
            path = generate_city(city_key, raw_dir, output_dir)
            paths.append(path)
        except FileNotFoundError as e:
            print(f"  [{city_key}] Skipped: {e}")

    return paths


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from config import get_config
    config = get_config()
    generate_all(config)
