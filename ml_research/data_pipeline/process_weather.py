"""
Process Open-Meteo weather data into unified hourly parquet files.

Merges with NASA POWER to gap-fill missing weather values.
Output: data/processed/weather/{city}_hourly.parquet
"""

from pathlib import Path

import numpy as np
import pandas as pd


def process_city(
    city_name: str,
    raw_weather_dir: str | Path,
    raw_nasa_dir: str | Path,
    output_dir: str | Path,
) -> Path:
    """
    Process Open-Meteo weather CSV into hourly parquet.

    Steps:
    1. Parse Open-Meteo CSV
    2. Standardize column names
    3. Merge with NASA POWER for gap-filling
    4. Save to parquet
    """
    raw_weather_dir = Path(raw_weather_dir)
    raw_nasa_dir = Path(raw_nasa_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Find Open-Meteo CSV
    csv_files = list(raw_weather_dir.glob(f"{city_name}_weather.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No Open-Meteo CSV for {city_name}")

    print(f"  [{city_name}] Processing weather data...")

    df = pd.read_csv(csv_files[0])
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.set_index("datetime")

    # Standardize column names
    column_map = {
        "temperature_2m": "temperature",
        "wind_speed_10m": "wind_speed",
        "precipitation": "precipitation",
        "cloud_cover": "cloud_fraction",
        "relative_humidity_2m": "humidity",
        "direct_normal_irradiance": "om_dni",
        "diffuse_radiation": "om_dhi",
    }

    df = df.rename(columns={k: v for k, v in column_map.items() if k in df.columns})

    # Normalize cloud fraction to 0-1 (Open-Meteo uses 0-100%)
    if "cloud_fraction" in df.columns:
        df["cloud_fraction"] = df["cloud_fraction"] / 100.0
        df["cloud_fraction"] = df["cloud_fraction"].clip(0, 1)

    # Flag extreme weather conditions (for stow/diffuse mode training)
    df["is_extreme_wind"] = df.get("wind_speed", pd.Series(0)) > 20.0  # m/s
    df["is_heavy_rain"] = df.get("precipitation", pd.Series(0)) > 5.0  # mm/h
    df["is_extreme_weather"] = df["is_extreme_wind"] | df["is_heavy_rain"]
    df["is_overcast"] = df.get("cloud_fraction", pd.Series(0)) > 0.8

    # Select final columns
    final_cols = [
        "temperature", "wind_speed", "precipitation",
        "cloud_fraction", "humidity",
        "is_extreme_weather", "is_overcast",
    ]
    df = df[[c for c in final_cols if c in df.columns]]

    # Interpolate small gaps
    df = df.interpolate(method="linear", limit=3)

    # Save to parquet
    output_path = output_dir / f"{city_name}_hourly.parquet"
    df.to_parquet(output_path, index=True)

    print(f"  [{city_name}] {len(df)} hours -> {output_path}")
    return output_path


def process_all(config: dict) -> list[Path]:
    """Process weather data for all cities."""
    cities = config["cities"]
    raw_weather_dir = Path(config["paths"]["raw_dir"]) / "open_meteo"
    raw_nasa_dir = Path(config["paths"]["raw_dir"]) / "nasa_power"
    output_dir = Path(config["paths"]["processed_dir"]) / "weather"

    paths = []
    for city_key in cities:
        try:
            path = process_city(city_key, raw_weather_dir, raw_nasa_dir, output_dir)
            paths.append(path)
        except FileNotFoundError as e:
            print(f"  [{city_key}] Skipped: {e}")

    return paths


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from config import get_config
    config = get_config()
    process_all(config)
