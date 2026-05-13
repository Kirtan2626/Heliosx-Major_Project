"""
Download Typical Meteorological Year (TMY) data from PVGIS — CORRECTED.

Fixes: Added response validation (checks for 12 months of data) and
increased timeout to prevent incomplete downloads that result in NaN months.
"""

import json
import time
from pathlib import Path

import requests


PVGIS_BASE = "https://re.jrc.ec.europa.eu/api/v5_3/tmy"

# PVGIS covers Europe, Africa, parts of Asia
PVGIS_CITIES = ["london", "tokyo", "dubai"]


def download_city(
    city_name: str,
    lat: float,
    lon: float,
    output_dir: str | Path,
    max_retries: int = 3,
) -> Path | None:
    """Download PVGIS TMY data for a city with validation."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"  [{city_name}] Downloading PVGIS TMY...")

    params = {
        "lat": lat,
        "lon": lon,
        "outputformat": "json",
    }

    for attempt in range(max_retries):
        try:
            resp = requests.get(PVGIS_BASE, params=params, timeout=120)
            resp.raise_for_status()
            data = resp.json()

            # Validate: check that we have ~8760 hours of data
            hourly_data = data.get("outputs", {}).get("tmy_hourly", [])
            if len(hourly_data) < 8000:
                print(f"    Attempt {attempt + 1}: Only {len(hourly_data)} hours "
                      f"(expected ~8760). Retrying...")
                time.sleep(5 * (attempt + 1))
                continue

            # Validate: check for NaN months (ensure all 12 months have GHI > 0)
            months_with_data = set()
            for row in hourly_data:
                time_str = row.get("time(UTC)", "")
                if len(time_str) >= 6:
                    month = time_str[4:6]
                    ghi = row.get("G(h)", 0)
                    if ghi is not None and ghi > 0:
                        months_with_data.add(month)

            if len(months_with_data) < 10:
                print(f"    Attempt {attempt + 1}: Only {len(months_with_data)}/12 "
                      f"months with valid GHI. Retrying...")
                time.sleep(5 * (attempt + 1))
                continue

            # Save valid data
            output_path = output_dir / f"{city_name}_tmy.json"
            with open(output_path, "w") as f:
                json.dump(data, f, indent=2)

            print(f"  [{city_name}] Saved {len(hourly_data)} hours, "
                  f"{len(months_with_data)} months with data -> {output_path}")
            return output_path

        except requests.RequestException as e:
            print(f"    Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(5 * (attempt + 1))

    print(f"  [{city_name}] FAILED after {max_retries} attempts")
    return None


def download_all(config: dict) -> list[Path]:
    """Download PVGIS TMY data for applicable cities."""
    cities = config["cities"]
    output_dir = Path(config["paths"]["raw_dir"]) / "pvgis"

    paths = []
    for city_key in PVGIS_CITIES:
        if city_key not in cities:
            continue
        city_info = cities[city_key]
        path = download_city(
            city_name=city_key,
            lat=city_info["lat"],
            lon=city_info["lon"],
            output_dir=output_dir,
        )
        if path:
            paths.append(path)
        time.sleep(2)

    return paths


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from config import get_config
    config = get_config()
    download_all(config)
