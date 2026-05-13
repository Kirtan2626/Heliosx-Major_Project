"""
Download hourly irradiance data from NASA POWER API.

No API key required. Downloads GHI, DNI, DHI, clear-sky DNI,
temperature, humidity, wind speed, and cloud fraction for all cities.
"""

import json
import time
from pathlib import Path

import requests


NASA_POWER_BASE = "https://power.larc.nasa.gov/api/temporal/hourly/point"

PARAMETERS = [
    "ALLSKY_SFC_SW_DNI",
    "ALLSKY_SFC_SW_DWN",
    "ALLSKY_SFC_SW_DIFF",
    "CLRSKY_SFC_SW_DNI",
    "T2M",
    "RH2M",
    "WS2M",
    "CLOUD_AMT",
]


def download_city(
    city_name: str,
    lat: float,
    lon: float,
    years: list[int],
    output_dir: str | Path,
    delay_seconds: float = 2.0,
) -> Path:
    """
    Download NASA POWER hourly data for a city, chunked by year.

    Args:
        city_name: City identifier (e.g., 'delhi')
        lat: Latitude
        lon: Longitude
        years: List of years to download
        output_dir: Directory to save raw JSON files
        delay_seconds: Delay between API requests

    Returns:
        Path to output JSON file
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    all_data = {}

    for year in years:
        print(f"  [{city_name}] Downloading NASA POWER {year}...")

        params = {
            "parameters": ",".join(PARAMETERS),
            "community": "RE",
            "longitude": lon,
            "latitude": lat,
            "start": f"{year}0101",
            "end": f"{year}1231",
            "format": "JSON",
            "time-standard": "LST",
        }

        for attempt in range(3):
            try:
                resp = requests.get(NASA_POWER_BASE, params=params, timeout=120)
                resp.raise_for_status()
                year_data = resp.json()

                # Merge parameter data
                if "properties" in year_data and "parameter" in year_data["properties"]:
                    for param_name, values in year_data["properties"]["parameter"].items():
                        if param_name not in all_data:
                            all_data[param_name] = {}
                        all_data[param_name].update(values)

                break

            except (requests.RequestException, json.JSONDecodeError) as e:
                print(f"    Attempt {attempt + 1} failed: {e}")
                if attempt < 2:
                    time.sleep(delay_seconds * (attempt + 1))
                else:
                    print(f"    FAILED for {city_name} {year} after 3 attempts")

        time.sleep(delay_seconds)

    # Save combined data
    year_range = f"{min(years)}_{max(years)}"
    output_path = output_dir / f"{city_name}_{year_range}.json"

    output_json = {
        "city": city_name,
        "latitude": lat,
        "longitude": lon,
        "years": years,
        "parameters": PARAMETERS,
        "data": all_data,
    }

    with open(output_path, "w") as f:
        json.dump(output_json, f, indent=2)

    print(f"  [{city_name}] Saved to {output_path}")
    return output_path


def download_all(config: dict) -> list[Path]:
    """Download NASA POWER data for all cities in config."""
    cities = config["cities"]
    years = config.get("data", {}).get("years", [2020, 2021, 2022, 2023, 2024])
    output_dir = Path(config["paths"]["raw_dir"]) / "nasa_power"

    paths = []
    for city_key, city_info in cities.items():
        path = download_city(
            city_name=city_key,
            lat=city_info["lat"],
            lon=city_info["lon"],
            years=years,
            output_dir=output_dir,
        )
        paths.append(path)

    return paths


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from config import get_config
    config = get_config()
    download_all(config)
