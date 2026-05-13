"""
Process raw OpenAQ PM2.5 data into hourly AQI parquet files.

Converts PM2.5 concentrations to US EPA AQI using official breakpoint formula.
Output: data/processed/air_quality/{city}_hourly.parquet
"""

from pathlib import Path

import numpy as np
import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from physics_engine.panel_feedback import pm25_to_aqi, aqi_attenuation


def process_city(
    city_name: str,
    raw_dir: str | Path,
    output_dir: str | Path,
) -> Path:
    """
    Process raw PM2.5 CSV into hourly AQI parquet.

    Steps:
    1. Parse CSV with datetime and PM2.5 columns
    2. Resample to hourly (mean)
    3. Convert PM2.5 to US EPA AQI
    4. Compute AQI attenuation factor
    5. Forward-fill gaps up to 6 hours, then daily median
    6. Save to parquet
    """
    raw_dir = Path(raw_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Find raw CSV
    csv_files = list(raw_dir.glob(f"{city_name}_pm25_*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No OpenAQ CSV found for {city_name} in {raw_dir}")

    print(f"  [{city_name}] Processing air quality data...")

    df = pd.read_csv(csv_files[0])
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
    df = df.set_index("datetime")
    df = df.sort_index()

    # Remove negative PM2.5 values
    df["pm25"] = df["pm25"].clip(lower=0)

    # Resample to hourly mean
    df_hourly = df.resample("1h").mean()

    # Convert PM2.5 to AQI
    df_hourly["aqi"] = df_hourly["pm25"].apply(
        lambda x: pm25_to_aqi(x) if pd.notna(x) else np.nan
    )

    # Forward-fill gaps up to 6 hours
    df_hourly["aqi"] = df_hourly["aqi"].ffill(limit=6)
    df_hourly["pm25"] = df_hourly["pm25"].ffill(limit=6)

    # Fill remaining gaps with daily median
    daily_median = df_hourly["aqi"].resample("1D").median()
    for idx in df_hourly.index[df_hourly["aqi"].isna()]:
        day = idx.normalize()
        if day in daily_median.index and pd.notna(daily_median[day]):
            df_hourly.loc[idx, "aqi"] = daily_median[day]

    # Compute attenuation factor
    df_hourly["aqi_attenuation"] = df_hourly["aqi"].apply(
        lambda x: aqi_attenuation(x) if pd.notna(x) else 1.0
    )

    # Drop rows where AQI is still NaN
    df_hourly = df_hourly.dropna(subset=["aqi"])

    # Save to parquet
    output_path = output_dir / f"{city_name}_hourly.parquet"
    df_hourly.to_parquet(output_path, index=True)

    mean_aqi = df_hourly["aqi"].mean()
    print(f"  [{city_name}] {len(df_hourly)} hours, mean AQI={mean_aqi:.0f} -> {output_path}")

    return output_path


def process_all(config: dict) -> list[Path]:
    """Process air quality data for all cities."""
    cities = config["cities"]
    raw_dir = Path(config["paths"]["raw_dir"]) / "openaq"
    output_dir = Path(config["paths"]["processed_dir"]) / "air_quality"

    paths = []
    for city_key in cities:
        try:
            path = process_city(city_key, raw_dir, output_dir)
            paths.append(path)
        except FileNotFoundError as e:
            print(f"  [{city_key}] Skipped: {e}")

    return paths


if __name__ == "__main__":
    from config import get_config
    config = get_config()
    process_all(config)
