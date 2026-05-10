# MATLAB Export and Simulation Safety Upgrades Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enhance MATLAB export with faults/obstacles, implement Pydantic validation for simulation results, and remove hardcoded AQI.

**Architecture:** Use Pydantic models in `src/models.py` for full simulation data validation. Update `src/heliosx_sim_server.py` to include obstacles in results and use a constant for AQI. Update `src/services/matlab_export_service.py` to include the new fields.

**Tech Stack:** Python, FastAPI, Pydantic, Pytest.

---

### Task 1: Update Data Models

**Files:**
- Modify: `src/models.py`

- [ ] **Step 1: Add new Pydantic models for simulation results**

```python
class TimeSeriesEntry(BaseModel):
    time: str
    sun_alt: float
    shadow: float
    action: str
    energy_ai: float
    energy_tracker: float
    temp_c: float
    dni: float
    aqi: float
    wind_speed: float

class DailyTotals(BaseModel):
    fixed_wh: float
    tracker_wh: float
    ai_wh: float

class CommercialImpact(BaseModel):
    kwh_loss: float
    financial_loss_usd: float
    urgency: str

class FaultEntry(BaseModel):
    type: str
    severity: str
    message: str

class ObstacleEntry(BaseModel):
    type: str
    z_height: float
    polygon: Optional[list[tuple[float, float]]] = None
    point: Optional[tuple[float, float]] = None
    radius: Optional[float] = None

class SimulationResult(BaseModel):
    lat: float
    lon: float
    daily_totals: DailyTotals
    timeseries: list[TimeSeriesEntry]
    faults: list[FaultEntry]
    commercial_impact: CommercialImpact
    obstacles: list[ObstacleEntry]
```

- [ ] **Step 2: Verify models are syntactically correct**
Run: `python -c "from src.models import SimulationResult; print('OK')"`

### Task 2: Update Simulation Server

**Files:**
- Modify: `src/heliosx_sim_server.py`

- [ ] **Step 1: Define DEFAULT_AQI constant and update build_cartesian_context to handle trees**

```python
DEFAULT_AQI = 50.0

def build_cartesian_context(base_lat: float, base_lon: float, context_data: dict) -> list:
    obstacles = []
    for b in context_data.get("buildings", []):
        # ... existing logic ...
        
    for t in context_data.get("trees", []):
        lat, lon = t.get("lat"), t.get("lon")
        if lat and lon:
            x, y = project_coordinates(base_lat, base_lon, lat, lon)
            obstacles.append({
                "type": "tree",
                "point": (x, y),
                "radius": 2.0,
                "z_height": 5.0
            })
    return obstacles
```

- [ ] **Step 2: Update run_simulation to use DEFAULT_AQI and return obstacles**

```python
def run_simulation(..., **kwargs) -> dict:
    # ...
    aqi = kwargs.get("aqi", DEFAULT_AQI)
    # ...
    results_dict = {
        "lat": lat, "lon": lon,
        "daily_totals": totals,
        "timeseries": results,
        "obstacles": obstacles
    }
    # ...
```

- [ ] **Step 3: Run existing simulation tests**
Run: `pytest tests/test_simulation.py tests/test_api.py`

### Task 3: Update MATLAB Export Service

**Files:**
- Modify: `src/services/matlab_export_service.py`

- [ ] **Step 1: Update format_for_matlab with type hints and new fields**

```python
from src.models import SimulationResult

def format_for_matlab(full_sim_data: SimulationResult) -> dict:
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
```

### Task 4: Update API Gateway

**Files:**
- Modify: `src/serve_dashboard.py`

- [ ] **Step 1: Update export_matlab endpoint to use SimulationResult**

```python
@app.post("/export-matlab")
async def export_matlab(sim_payload: SimulationResult):
    return format_for_matlab(sim_payload)
```

- [ ] **Step 2: Run all tests and verify export structure**
Run: `pytest tests/test_api.py`

### Task 5: Final Cleanup and Commit

- [ ] **Step 1: Ensure no linting errors**
Run: `flake8 src/` (if available) or just manual check.

- [ ] **Step 2: Commit changes**
```bash
git add src/models.py src/heliosx_sim_server.py src/services/matlab_export_service.py src/serve_dashboard.py
git commit -m "feat: enhance matlab export and add simulation result validation"
```
