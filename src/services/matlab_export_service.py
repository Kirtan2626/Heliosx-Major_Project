# src/services/matlab_export_service.py
from src.models import SimulationResult

def format_for_matlab(full_sim_data: SimulationResult) -> dict:
    """
    Reformats simulation data into Simscape Electrical nested format for MATLAB ingestion.
    """
    data = full_sim_data.model_dump()
    return {
        "Metadata": {
            "origin": "Helios-X Digital Twin",
            "coords": [data.get("lat", 0), data.get("lon", 0)]
        },
        "Environment": {
            "temperatures": [r.get("temp_c") for r in data.get("timeseries", [])],
            "dni": [r.get("dni") for r in data.get("timeseries", [])],
            "aqi": [r.get("aqi") for r in data.get("timeseries", [])]
        },
        "PhysicsResults": {
            "energy_fixed": data.get("daily_totals", {}).get("fixed_wh", 0),
            "energy_tracker": data.get("daily_totals", {}).get("tracker_wh", 0),
            "energy_ai": data.get("daily_totals", {}).get("ai_wh", 0)
        },
        "AILog": {
            "action_modes": [r.get("action") for r in data.get("timeseries", [])]
        },
        "Diagnostics": {
            "faults": data.get("faults", [])
        },
        "SiteGeometry": {
            "obstacles": data.get("obstacles", [])
        }
    }
