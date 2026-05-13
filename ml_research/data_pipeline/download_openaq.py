"""
Download hourly PM2.5 data from OpenAQ v3 API.

Requires OpenAQ API key. Downloads data for all 6 cities,
month-by-month to handle API pagination.
"""

import csv
import time
from datetime import datetime
from pathlib import Path

import requests


OPENAQ_BASE = "https://api.openaq.org/v3"


def _find_pm25_sensor(
    api_key: str,
    lat: float,
    lon: float,
    radius_m: int = 25000,
) -> tuple[int | None, int | None]:
    """Find nearest PM2.5 sensor. Returns (location_id, sensor_id)."""
    headers = {"X-API-Key": api_key}

    # Step 1: Find nearby locations
    params = {
        "coordinates": f"{lat},{lon}",
        "radius": radius_m,
        "limit": 10,
    }

    try:
        resp = requests.get(
            f"{OPENAQ_BASE}/locations",
            params=params,
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        results = data.get("results", [])
        for loc in results:
            sensors = loc.get("sensors", [])
            for sensor in sensors:
                param = sensor.get("parameter", {})
                if param.get("name") == "pm25" or param.get("id") == 2:
                    return loc["id"], sensor["id"]

    except requests.RequestException as e:
        print(f"    Station search failed: {e}")

    return None, None


def _download_sensor_measurements(
    api_key: str,
    sensor_id: int,
    start_date: str,
    end_date: str,
) -> list[dict]:
    """Download measurements for a sensor and date range."""
    headers = {"X-API-Key": api_key}
    all_measurements = []
    page = 1

    while True:
        params = {
            "date_from": start_date,
            "date_to": end_date,
            "limit": 1000,
            "page": page,
        }

        try:
            resp = requests.get(
                f"{OPENAQ_BASE}/sensors/{sensor_id}/measurements",
                params=params,
                headers=headers,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

            results = data.get("results", [])
            if not results:
                break

            all_measurements.extend(results)

            meta = data.get("meta", {})
            found = meta.get("found", "0")
            # found can be ">N" string or int
            if isinstance(found, str) and found.startswith(">"):
                total = int(found[1:]) + 1
            else:
                total = int(found)

            if page * 1000 >= total:
                break

            page += 1
            time.sleep(0.5)

        except requests.RequestException as e:
            print(f"    Measurement download failed (page {page}): {e}")
            break

    return all_measurements


def download_city(
    city_name: str,
    lat: float,
    lon: float,
    api_key: str,
    years: list[int],
    output_dir: str | Path,
) -> Path | None:
    """Download PM2.5 data for a single city."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"  [{city_name}] Finding nearest PM2.5 sensor...")
    location_id, sensor_id = _find_pm25_sensor(api_key, lat, lon)

    if sensor_id is None:
        print(f"  [{city_name}] No PM2.5 sensor found, skipping")
        return None

    print(f"  [{city_name}] Location ID: {location_id}, Sensor ID: {sensor_id}")

    all_records = []

    for year in years:
        for month in range(1, 13):
            start = f"{year}-{month:02d}-01"
            if month == 12:
                end = f"{year + 1}-01-01"
            else:
                end = f"{year}-{month + 1:02d}-01"

            measurements = _download_sensor_measurements(api_key, sensor_id, start, end)

            for m in measurements:
                period = m.get("period", {})
                dt_from = period.get("datetimeFrom", {})
                dt_local = dt_from.get("local", "") if isinstance(dt_from, dict) else ""
                value = m.get("value")
                if dt_local and value is not None:
                    all_records.append({
                        "datetime": dt_local,
                        "pm25": value,
                    })

            time.sleep(0.5)

        print(f"  [{city_name}] {year}: {len(all_records)} total records")

    if not all_records:
        print(f"  [{city_name}] No data retrieved")
        return None

    # Save to CSV
    year_range = f"{min(years)}_{max(years)}"
    output_path = output_dir / f"{city_name}_pm25_{year_range}.csv"

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["datetime", "pm25"])
        writer.writeheader()
        writer.writerows(all_records)

    print(f"  [{city_name}] Saved {len(all_records)} records to {output_path}")
    return output_path


def download_all(config: dict) -> list[Path]:
    """Download OpenAQ PM2.5 data for all cities."""
    api_key = config.get("secrets", {}).get("openaq_api_key", "")
    if not api_key:
        print("  [openaq] WARNING: No OpenAQ API key found, skipping")
        return []

    cities = config["cities"]
    years = config.get("data", {}).get("years", [2020, 2021, 2022, 2023, 2024])
    output_dir = Path(config["paths"]["raw_dir"]) / "openaq"

    paths = []
    for city_key, city_info in cities.items():
        path = download_city(
            city_name=city_key,
            lat=city_info["lat"],
            lon=city_info["lon"],
            api_key=api_key,
            years=years,
            output_dir=output_dir,
        )
        if path:
            paths.append(path)

    return paths


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from config import get_config
    config = get_config()
    download_all(config)
