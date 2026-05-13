"""
Cross-validate simulation irradiance against independent data sources.

Validations:
1. NASA POWER vs NSRDB (New York) — Pearson r, RMSE, MBE, nRMSE
2. NASA POWER vs PVGIS TMY (London) — monthly correlation
3. Report metrics for paper methodology section

Output: data/validation/validation_report.json
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd


def _compute_metrics(actual: np.ndarray, predicted: np.ndarray) -> dict:
    """Compute validation metrics between two arrays."""
    mask = ~(np.isnan(actual) | np.isnan(predicted))
    actual = actual[mask]
    predicted = predicted[mask]

    if len(actual) < 10:
        return {"error": "insufficient_data", "n_samples": len(actual)}

    # Pearson correlation
    r = np.corrcoef(actual, predicted)[0, 1]

    # RMSE
    rmse = np.sqrt(np.mean((predicted - actual) ** 2))

    # Mean Bias Error
    mbe = np.mean(predicted - actual)

    # Normalized RMSE (as percentage of mean actual)
    mean_actual = np.mean(actual)
    nrmse = (rmse / mean_actual * 100) if mean_actual > 0 else float("inf")

    return {
        "n_samples": int(len(actual)),
        "pearson_r": round(float(r), 4),
        "rmse": round(float(rmse), 2),
        "mbe": round(float(mbe), 2),
        "nrmse_pct": round(float(nrmse), 2),
        "mean_actual": round(float(mean_actual), 2),
        "mean_predicted": round(float(mean_actual + mbe), 2),
    }


def validate_nasa_vs_nsrdb(
    nasa_dir: str | Path,
    nsrdb_dir: str | Path,
) -> dict:
    """
    Compare NASA POWER irradiance with NSRDB for New York.

    Returns validation metrics dict.
    """
    nasa_dir = Path(nasa_dir)
    nsrdb_dir = Path(nsrdb_dir)

    # Load NASA POWER processed data
    nasa_path = nasa_dir / "new_york_hourly.parquet"
    if not nasa_path.exists():
        return {"error": "NASA POWER data not found"}

    # Load NSRDB data
    nsrdb_files = list(nsrdb_dir.glob("new_york_*.csv"))
    if not nsrdb_files:
        return {"error": "NSRDB data not found"}

    print("  Validating NASA POWER vs NSRDB (New York)...")

    nasa_df = pd.read_parquet(nasa_path)

    # Read NSRDB CSVs (may have header rows to skip)
    nsrdb_dfs = []
    for f in nsrdb_files:
        try:
            # NSRDB files often have 2 header rows
            df = pd.read_csv(f, skiprows=2)
            nsrdb_dfs.append(df)
        except Exception:
            try:
                df = pd.read_csv(f)
                nsrdb_dfs.append(df)
            except Exception:
                continue

    if not nsrdb_dfs:
        return {"error": "Could not parse NSRDB files"}

    nsrdb_df = pd.concat(nsrdb_dfs, ignore_index=True)

    # Try to align on datetime
    if "Year" in nsrdb_df.columns and "Month" in nsrdb_df.columns:
        nsrdb_df["datetime"] = pd.to_datetime(
            nsrdb_df[["Year", "Month", "Day", "Hour"]].rename(
                columns={"Year": "year", "Month": "month", "Day": "day", "Hour": "hour"}
            )
        )
        nsrdb_df = nsrdb_df.set_index("datetime")

    # Find overlapping period
    overlap_start = max(nasa_df.index.min(), nsrdb_df.index.min())
    overlap_end = min(nasa_df.index.max(), nsrdb_df.index.max())

    nasa_overlap = nasa_df[overlap_start:overlap_end]
    nsrdb_overlap = nsrdb_df[overlap_start:overlap_end]

    # Resample NSRDB to hourly if needed
    if len(nsrdb_overlap) > len(nasa_overlap) * 1.5:
        nsrdb_overlap = nsrdb_overlap.resample("1h").mean()

    # Align indices
    common_idx = nasa_overlap.index.intersection(nsrdb_overlap.index)

    results = {}

    # DNI comparison
    if "dni" in nasa_overlap.columns and "DNI" in nsrdb_overlap.columns:
        nasa_dni = nasa_overlap.loc[common_idx, "dni"].values
        nsrdb_dni = nsrdb_overlap.loc[common_idx, "DNI"].values
        results["dni"] = _compute_metrics(nsrdb_dni, nasa_dni)

    # GHI comparison
    if "ghi" in nasa_overlap.columns and "GHI" in nsrdb_overlap.columns:
        nasa_ghi = nasa_overlap.loc[common_idx, "ghi"].values
        nsrdb_ghi = nsrdb_overlap.loc[common_idx, "GHI"].values
        results["ghi"] = _compute_metrics(nsrdb_ghi, nasa_ghi)

    return results


def validate_nasa_vs_pvgis(
    nasa_dir: str | Path,
    pvgis_dir: str | Path,
) -> dict:
    """Compare NASA POWER with PVGIS TMY for London."""
    nasa_dir = Path(nasa_dir)
    pvgis_dir = Path(pvgis_dir)

    nasa_path = nasa_dir / "london_hourly.parquet"
    pvgis_path = pvgis_dir / "london_tmy.json"

    if not nasa_path.exists():
        return {"error": "NASA POWER London data not found"}
    if not pvgis_path.exists():
        return {"error": "PVGIS London data not found"}

    print("  Validating NASA POWER vs PVGIS (London)...")

    nasa_df = pd.read_parquet(nasa_path)

    with open(pvgis_path, "r") as f:
        pvgis_data = json.load(f)

    # Parse PVGIS TMY data
    outputs = pvgis_data.get("outputs", {})
    tmy_hourly = outputs.get("tmy_hourly", [])

    if not tmy_hourly:
        return {"error": "No TMY hourly data in PVGIS response"}

    pvgis_df = pd.DataFrame(tmy_hourly)
    if "time(UTC)" in pvgis_df.columns:
        pvgis_df["datetime"] = pd.to_datetime(pvgis_df["time(UTC)"], format="%Y%m%d:%H%M")
        pvgis_df = pvgis_df.set_index("datetime")

    # Monthly comparison: compute monthly mean GHI for both
    nasa_monthly = nasa_df["ghi"].resample("ME").mean() if "ghi" in nasa_df.columns else None

    pvgis_ghi_col = "G(h)" if "G(h)" in pvgis_df.columns else None
    if pvgis_ghi_col:
        pvgis_monthly = pvgis_df[pvgis_ghi_col].resample("ME").mean()
    else:
        return {"error": "No GHI column found in PVGIS data"}

    # Compare monthly patterns (12 months)
    if nasa_monthly is not None and len(nasa_monthly) >= 12:
        # Use first year of NASA data for comparison
        nasa_12 = nasa_monthly.iloc[:12].values
        pvgis_12 = pvgis_monthly.iloc[:12].values

        r = np.corrcoef(nasa_12, pvgis_12)[0, 1]
        return {
            "monthly_correlation": round(float(r), 4),
            "nasa_monthly_ghi": [round(float(v), 1) for v in nasa_12],
            "pvgis_monthly_ghi": [round(float(v), 1) for v in pvgis_12],
        }

    return {"error": "Insufficient data for monthly comparison"}


def validate_all(config: dict) -> dict:
    """Run all validation checks and save report."""
    processed_dir = Path(config["paths"]["processed_dir"])
    raw_dir = Path(config["paths"]["raw_dir"])
    validation_dir = Path(config["paths"]["validation_dir"])
    validation_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "nasa_vs_nsrdb_new_york": validate_nasa_vs_nsrdb(
            processed_dir / "irradiance",
            raw_dir / "nsrdb",
        ),
        "nasa_vs_pvgis_london": validate_nasa_vs_pvgis(
            processed_dir / "irradiance",
            raw_dir / "pvgis",
        ),
    }

    # Save report
    report_path = validation_dir / "validation_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\n  Validation report saved to {report_path}")

    # Print summary
    for check_name, result in report.items():
        if "error" in result:
            print(f"  {check_name}: {result['error']}")
        else:
            print(f"  {check_name}: {json.dumps(result, indent=4)}")

    return report


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from config import get_config
    config = get_config()
    validate_all(config)
