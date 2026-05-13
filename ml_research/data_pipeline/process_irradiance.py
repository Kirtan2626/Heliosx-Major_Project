"""
Process raw NASA POWER JSON into clean hourly parquet files.

Filters to daylight hours, gap-fills missing data, computes clear-sky index.
Output: data/processed/irradiance/{city}_hourly.parquet
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from physics_engine.solar_core import sun_position
from datetime import datetime, timezone


def _parse_nasa_power_json(json_path: Path) -> pd.DataFrame:
    """Parse NASA POWER JSON into a DataFrame with datetime index."""
    with open(json_path, "r") as f:
        data = json.load(f)

    param_data = data.get("data", {})
    if not param_data:
        raise ValueError(f"No parameter data in {json_path}")

    # Build DataFrame from parameter dict
    # Keys are like "20200101" + hour "00"-"23" -> "2020010100"
    records = {}
    for param_name, values in param_data.items():
        for time_key, value in values.items():
            if time_key not in records:
                records[time_key] = {}
            records[time_key][param_name] = value

    df = pd.DataFrame.from_dict(records, orient="index")
    df.index.name = "time_key"
    df = df.sort_index()

    # Parse datetime from keys like "2020010100" (YYYYMMDDHH)
    df["datetime"] = pd.to_datetime(df.index, format="%Y%m%d%H")
    df = df.set_index("datetime")

    # Rename columns to standard names
    column_map = {
        "ALLSKY_SFC_SW_DNI": "dni",
        "ALLSKY_SFC_SW_DWN": "ghi",
        "ALLSKY_SFC_SW_DIFF": "dhi",
        "CLRSKY_SFC_SW_DNI": "dni_clearsky",
        "T2M": "temperature",
        "RH2M": "humidity",
        "WS2M": "wind_speed",
        "CLOUD_AMT": "cloud_fraction",
    }
    df = df.rename(columns=column_map)

    # Keep only known columns
    known_cols = list(column_map.values())
    df = df[[c for c in known_cols if c in df.columns]]

    return df


def process_city(
    city_name: str,
    lat: float,
    lon: float,
    raw_dir: str | Path,
    output_dir: str | Path,
    max_gap_hours: int = 3,
) -> Path:
    """
    Process raw NASA POWER data for a single city.

    Steps:
    1. Parse JSON to DataFrame
    2. Replace fill values (-999) with NaN
    3. Filter to daylight hours (sun altitude > 0)
    4. Gap-fill missing hours (linear interpolation, max gap)
    5. Compute clear-sky index
    6. Save to parquet

    Args:
        city_name: City identifier
        lat: City latitude
        lon: City longitude
        raw_dir: Directory containing raw NASA POWER JSON
        output_dir: Output directory for parquet files
        max_gap_hours: Maximum gap to interpolate (hours)

    Returns:
        Path to output parquet file
    """
    raw_dir = Path(raw_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Find raw JSON file
    json_files = list(raw_dir.glob(f"{city_name}_*.json"))
    if not json_files:
        raise FileNotFoundError(f"No NASA POWER JSON found for {city_name} in {raw_dir}")

    print(f"  [{city_name}] Processing irradiance data...")
    df = _parse_nasa_power_json(json_files[0])

    # Replace NASA POWER fill values
    df = df.replace(-999.0, np.nan)
    df = df.replace(-999, np.nan)

    # Compute sun altitude for each hour to filter daylight
    sun_alts = []
    for dt in df.index:
        dt_utc = dt.to_pydatetime().replace(tzinfo=timezone.utc)
        alt, _ = sun_position(lat, lon, dt_utc)
        sun_alts.append(alt)

    df["sun_altitude"] = sun_alts
    df["is_daylight"] = df["sun_altitude"] > 0

    # Filter to daylight hours only
    df_daylight = df[df["is_daylight"]].copy()

    # Ensure no negative irradiance values
    for col in ["dni", "ghi", "dhi", "dni_clearsky"]:
        if col in df_daylight.columns:
            df_daylight[col] = df_daylight[col].clip(lower=0)

    # Gap-fill: linear interpolation for gaps up to max_gap_hours
    # Mark which values were gap-filled
    is_gap = df_daylight[["dni", "ghi", "dhi"]].isna()

    for col in ["dni", "ghi", "dhi", "dni_clearsky", "temperature",
                "humidity", "wind_speed", "cloud_fraction"]:
        if col in df_daylight.columns:
            df_daylight[col] = df_daylight[col].interpolate(
                method="linear", limit=max_gap_hours
            )

    df_daylight["is_gap_filled"] = is_gap.any(axis=1)

    # Compute clear-sky index
    if "ghi" in df_daylight.columns and "dni_clearsky" in df_daylight.columns:
        # Use GHI-based clear-sky index when available
        df_daylight["clear_sky_index"] = np.where(
            df_daylight["dni_clearsky"] > 10,
            df_daylight["dni"] / df_daylight["dni_clearsky"],
            np.nan,
        )
        df_daylight["clear_sky_index"] = df_daylight["clear_sky_index"].clip(0, 2)

    # Drop helper columns
    df_daylight = df_daylight.drop(columns=["is_daylight"], errors="ignore")

    # Save to parquet
    output_path = output_dir / f"{city_name}_hourly.parquet"
    df_daylight.to_parquet(output_path, index=True)

    n_rows = len(df_daylight)
    n_gaps = df_daylight["is_gap_filled"].sum()
    print(f"  [{city_name}] {n_rows} daylight hours, {n_gaps} gap-filled -> {output_path}")

    return output_path


def process_all(config: dict) -> list[Path]:
    """Process irradiance data for all cities."""
    cities = config["cities"]
    raw_dir = Path(config["paths"]["raw_dir"]) / "nasa_power"
    output_dir = Path(config["paths"]["processed_dir"]) / "irradiance"

    paths = []
    for city_key, city_info in cities.items():
        try:
            path = process_city(
                city_name=city_key,
                lat=city_info["lat"],
                lon=city_info["lon"],
                raw_dir=raw_dir,
                output_dir=output_dir,
                max_gap_hours=config.get("data", {}).get("gap_fill_max_hours", 3),
            )
            paths.append(path)
        except FileNotFoundError as e:
            print(f"  [{city_key}] Skipped: {e}")

    return paths


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from config import get_config
    config = get_config()
    process_all(config)
