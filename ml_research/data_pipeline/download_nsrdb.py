"""
Download NREL NSRDB data for validation (New York only).

Requires NREL API key. Downloads 30-minute DNI, DHI, GHI data.
Used for cross-validation against NASA POWER, not for training.
"""

import time
from pathlib import Path

import requests


NSRDB_BASE = "https://developer.nrel.gov/api/nsrdb/v2/solar/nsrdb-GOES-aggregated-v4-0-0-download.csv"


def download_nsrdb(
    api_key: str,
    lat: float = 40.71,
    lon: float = -74.01,
    years: list[int] = None,
    output_dir: str | Path = None,
) -> list[Path]:
    """
    Download NSRDB 30-minute data for New York (validation).

    Args:
        api_key: NREL API key
        lat: Latitude (default: New York)
        lon: Longitude (default: New York)
        years: Years to download (default: 2020-2023)
        output_dir: Output directory for CSV files

    Returns:
        List of downloaded file paths
    """
    if years is None:
        years = [2020, 2021, 2022, 2023]
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    paths = []

    for year in years:
        print(f"  [nsrdb] Downloading NSRDB New York {year}...")

        params = {
            "api_key": api_key,
            "wkt": f"POINT({lon} {lat})",
            "names": str(year),
            "leap_day": "true",
            "interval": "30",
            "utc": "false",
            "attributes": "ghi,dni,dhi,solar_zenith_angle,air_temperature,wind_speed",
            "email": "helios.x.v2@research.org",
        }

        for attempt in range(3):
            try:
                resp = requests.get(NSRDB_BASE, params=params, timeout=120)
                resp.raise_for_status()

                # CSV endpoint returns CSV directly
                csv_data = resp.text
                if not csv_data or len(csv_data) < 100:
                    # Might be a JSON error response
                    try:
                        data = resp.json()
                        if "errors" in data:
                            print(f"    NSRDB API error: {data['errors']}")
                            break
                    except Exception:
                        pass

                output_path = output_dir / f"new_york_{year}.csv"
                with open(output_path, "w") as f:
                    f.write(csv_data)

                paths.append(output_path)
                print(f"    Saved {output_path}")
                break

            except requests.RequestException as e:
                print(f"    Attempt {attempt + 1} failed: {e}")
                if attempt < 2:
                    time.sleep(5 * (attempt + 1))

        time.sleep(2)

    return paths


def download_all(config: dict) -> list[Path]:
    """Download NSRDB validation data."""
    api_key = config.get("secrets", {}).get("nrel_api_key", "")
    if not api_key:
        print("  [nsrdb] WARNING: No NREL API key found, skipping NSRDB download")
        return []

    output_dir = Path(config["paths"]["raw_dir"]) / "nsrdb"
    ny = config["cities"]["new_york"]
    return download_nsrdb(
        api_key=api_key,
        lat=ny["lat"],
        lon=ny["lon"],
        output_dir=output_dir,
    )


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from config import get_config
    config = get_config()
    download_all(config)
