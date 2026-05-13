"""
Download historical hourly weather data from Open-Meteo.

No API key required, no rate limit. Downloads temperature, wind speed,
precipitation, cloud cover for all 6 cities. Used for gap-filling
NASA POWER data and extreme weather signals.
"""

import time
from pathlib import Path

import pandas as pd
import requests


OPEN_METEO_BASE = "https://archive-api.open-meteo.com/v1/archive"


def download_city(
    city_name: str,
    lat: float,
    lon: float,
    start_date: str = "2020-01-01",
    end_date: str = "2024-12-31",
    output_dir: str | Path = None,
) -> Path | None:
    """
    Download Open-Meteo historical weather for a city.

    Args:
        city_name: City identifier
        lat: Latitude
        lon: Longitude
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        output_dir: Output directory

    Returns:
        Path to output CSV file
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"  [{city_name}] Downloading Open-Meteo weather...")

    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": ",".join([
            "temperature_2m",
            "wind_speed_10m",
            "precipitation",
            "cloud_cover",
            "relative_humidity_2m",
            "direct_normal_irradiance",
            "diffuse_radiation",
        ]),
        "timezone": "UTC",
    }

    for attempt in range(3):
        try:
            resp = requests.get(OPEN_METEO_BASE, params=params, timeout=120)
            resp.raise_for_status()
            data = resp.json()

            hourly = data.get("hourly", {})
            if not hourly or "time" not in hourly:
                print(f"  [{city_name}] No hourly data in response")
                return None

            df = pd.DataFrame(hourly)
            df.rename(columns={"time": "datetime"}, inplace=True)

            output_path = output_dir / f"{city_name}_weather.csv"
            df.to_csv(output_path, index=False)

            print(f"  [{city_name}] Saved {len(df)} rows to {output_path}")
            return output_path

        except requests.RequestException as e:
            print(f"    Attempt {attempt + 1} failed: {e}")
            if attempt < 2:
                time.sleep(3 * (attempt + 1))

    print(f"  [{city_name}] FAILED after 3 attempts")
    return None


def download_all(config: dict) -> list[Path]:
    """Download Open-Meteo weather for all cities."""
    cities = config["cities"]
    years = config.get("data", {}).get("years", [2020, 2021, 2022, 2023, 2024])
    start_date = f"{min(years)}-01-01"
    end_date = f"{max(years)}-12-31"
    output_dir = Path(config["paths"]["raw_dir"]) / "open_meteo"

    paths = []
    for city_key, city_info in cities.items():
        path = download_city(
            city_name=city_key,
            lat=city_info["lat"],
            lon=city_info["lon"],
            start_date=start_date,
            end_date=end_date,
            output_dir=output_dir,
        )
        if path:
            paths.append(path)
        time.sleep(1)

    return paths


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from config import get_config
    config = get_config()
    download_all(config)
