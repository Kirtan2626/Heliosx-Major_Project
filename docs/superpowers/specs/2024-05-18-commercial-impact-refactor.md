# MATLAB Export and Simulation Safety Upgrades Design

This document describes the enhancements to the MATLAB export service, simulation data consistency, and API validation.

## Goals
- Enhance `format_for_matlab` to include `faults` and `obstacles`.
- Implement `SimulationResult` Pydantic model for robust API validation.
- Remove hardcoded AQI from simulation server and move it to a constant/parameter.
- Improve type safety across the MATLAB export pipeline.

## Proposed Changes

### 1. Data Models (`src/models.py`)
Introduce several new models to represent the full simulation output:
- `TimeSeriesEntry`: Individual step data (energy, sun position, etc.).
- `DailyTotals`: Aggregated energy metrics.
- `CommercialImpact`: Financial loss and urgency metrics.
- `FaultEntry`: Diagnostic fault info.
- `ObstacleEntry`: Cartesian geometry of buildings and trees.
- `SimulationResult`: The comprehensive payload returned by `/simulate` and consumed by `/export-matlab`.

### 2. Simulation Server (`src/heliosx_sim_server.py`)
- Define `DEFAULT_AQI = 50.0`.
- Update `build_cartesian_context` to process `trees` from context data.
- Update `run_simulation` to:
    - Include `obstacles` in the returned dictionary.
    - Use `DEFAULT_AQI` (and allow it to be overridden via `kwargs`).

### 3. MATLAB Export Service (`src/services/matlab_export_service.py`)
- Update `format_for_matlab` to accept `SimulationResult` (as a Pydantic model).
- Add `Diagnostics` section containing `faults`.
- Add `SiteGeometry` section containing `obstacles`.
- Add Python type hints to all functions.

### 4. API Gateway (`src/serve_dashboard.py`)
- Update the `/export-matlab` endpoint to use `SimulationResult` as the request body type.
- This ensures that the input dictionary is validated before being processed by the export service.

## Verification Plan
- **Automated Tests**:
    - Update `test_export_matlab_endpoint` in `tests/test_api.py` to verify the new fields (`faults`, `obstacles`).
    - Verify all existing tests pass (`pytest`).
- **Manual Verification**:
    - Check the structure of the JSON returned by `/export-matlab` to ensure it matches the Simscape Electrical requirements.
