"""
Download building footprints and heights from OpenStreetMap via Overpass API.

No API key required. Queries buildings within 200m of each panel installation
site and extracts height data for shadow profile generation.
"""

import json
import math
import time
from pathlib import Path

import requests


OVERPASS_URL = "https://overpass-api.de/api/interpreter"


def _build_query(lat: float, lon: float, radius_m: int = 200) -> str:
    """Build Overpass QL query for buildings near a point."""
    return f"""
    [out:json][timeout:60];
    (
      way["building"](around:{radius_m},{lat},{lon});
      relation["building"](around:{radius_m},{lat},{lon});
    );
    out body;
    >;
    out skel qt;
    """


def _extract_height(tags: dict) -> float | None:
    """Extract building height from OSM tags."""
    # Try direct height tag
    if "height" in tags:
        try:
            h = tags["height"].replace("m", "").strip()
            return float(h)
        except (ValueError, AttributeError):
            pass

    if "building:height" in tags:
        try:
            return float(tags["building:height"].replace("m", "").strip())
        except (ValueError, AttributeError):
            pass

    # Fallback: building:levels × 3.0m
    if "building:levels" in tags:
        try:
            levels = float(tags["building:levels"])
            return levels * 3.0
        except (ValueError, AttributeError):
            pass

    return None


def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute haversine distance in meters between two points."""
    R = 6371000  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def _compute_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute bearing in degrees from point 1 to point 2."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dlam = math.radians(lon2 - lon1)

    x = math.sin(dlam) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlam)

    bearing = math.degrees(math.atan2(x, y))
    return bearing % 360


def download_city(
    city_name: str,
    panel_lat: float,
    panel_lon: float,
    search_radius_m: int = 200,
    output_dir: str | Path = None,
) -> Path | None:
    """
    Download OSM building data for a city's panel installation site.

    Args:
        city_name: City identifier
        panel_lat: Panel installation latitude
        panel_lon: Panel installation longitude
        search_radius_m: Search radius in meters
        output_dir: Output directory

    Returns:
        Path to output GeoJSON file
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"  [{city_name}] Querying OSM buildings within {search_radius_m}m...")

    query = _build_query(panel_lat, panel_lon, search_radius_m)

    for attempt in range(3):
        try:
            resp = requests.post(
                OVERPASS_URL,
                data={"data": query},
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
            break

        except requests.RequestException as e:
            print(f"    Attempt {attempt + 1} failed: {e}")
            if attempt < 2:
                time.sleep(10 * (attempt + 1))
            else:
                print(f"  [{city_name}] FAILED after 3 attempts")
                return None

    elements = data.get("elements", [])

    # Separate nodes and ways
    nodes = {}
    ways = []

    for elem in elements:
        if elem["type"] == "node":
            nodes[elem["id"]] = (elem["lat"], elem["lon"])
        elif elem["type"] == "way" and "tags" in elem:
            ways.append(elem)

    # Process buildings
    buildings = []
    for way in ways:
        tags = way.get("tags", {})
        if "building" not in tags:
            continue

        height = _extract_height(tags)
        if height is None:
            height = 9.0  # Default: 3 floors × 3m

        # Compute centroid from nodes
        way_nodes = way.get("nodes", [])
        lats = [nodes[n][0] for n in way_nodes if n in nodes]
        lons = [nodes[n][1] for n in way_nodes if n in nodes]

        if not lats:
            continue

        centroid_lat = sum(lats) / len(lats)
        centroid_lon = sum(lons) / len(lons)

        # Compute distance and bearing from panel
        distance = _haversine_distance(panel_lat, panel_lon, centroid_lat, centroid_lon)
        bearing = _compute_bearing(panel_lat, panel_lon, centroid_lat, centroid_lon)

        # Estimate building width from node spread
        if len(lats) >= 2:
            max_spread = 0
            for i in range(len(lats)):
                for j in range(i + 1, len(lats)):
                    spread = _haversine_distance(lats[i], lons[i], lats[j], lons[j])
                    max_spread = max(max_spread, spread)
            width = max_spread
        else:
            width = 10.0  # Default width

        buildings.append({
            "id": way["id"],
            "name": tags.get("name", f"Building_{way['id']}"),
            "type": tags.get("building", "yes"),
            "height_m": height,
            "centroid_lat": centroid_lat,
            "centroid_lon": centroid_lon,
            "distance_m": distance,
            "bearing_deg": bearing,
            "width_m": width,
            "height_source": "height" if "height" in tags else (
                "building:height" if "building:height" in tags else (
                    "levels" if "building:levels" in tags else "default"
                )
            ),
        })

    # Save as GeoJSON
    geojson = {
        "type": "FeatureCollection",
        "panel_location": {"lat": panel_lat, "lon": panel_lon},
        "search_radius_m": search_radius_m,
        "features": [
            {
                "type": "Feature",
                "properties": b,
                "geometry": {
                    "type": "Point",
                    "coordinates": [b["centroid_lon"], b["centroid_lat"]],
                },
            }
            for b in buildings
        ],
    }

    output_path = output_dir / f"{city_name}_buildings.geojson"
    with open(output_path, "w") as f:
        json.dump(geojson, f, indent=2)

    print(f"  [{city_name}] Found {len(buildings)} buildings, saved to {output_path}")
    return output_path


def download_all(config: dict) -> list[Path]:
    """Download OSM building data for all cities."""
    cities = config["cities"]
    search_radius = config.get("data", {}).get("osm_search_radius_m", 200)
    output_dir = Path(config["paths"]["raw_dir"]) / "osm_buildings"

    paths = []
    for city_key, city_info in cities.items():
        path = download_city(
            city_name=city_key,
            panel_lat=city_info["panel_lat"],
            panel_lon=city_info["panel_lon"],
            search_radius_m=search_radius,
            output_dir=output_dir,
        )
        if path:
            paths.append(path)
        time.sleep(5)  # Be polite to Overpass API

    return paths


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from config import get_config
    config = get_config()
    download_all(config)
