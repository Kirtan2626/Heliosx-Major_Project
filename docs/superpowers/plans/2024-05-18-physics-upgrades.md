# Physics Upgrades Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement rigorous physical models (King Model, Spectral Correction, SVF-based Diffuse Radiation) in the energy calculation engine.

**Architecture:** Update `calculate_energy` in `panel_feedback.py` to include wind speed dependency and more accurate loss models. Update tests to verify behavioral changes.

**Tech Stack:** Python, Math, Pytest

---

### Task 1: Update Function Signature and King Model

**Files:**
- Modify: `src/physics_engine/panel_feedback.py`
- Test: `tests/test_panel_feedback.py`

- [ ] **Step 1: Update function signature to include `wind_speed` and implement King Model for $T_{cell}$**

```python
def calculate_energy(dni: float, temp_c: float, wind_speed: float, aqi: float, shadow_factor: float, 
                     sun_alt: float, sun_az: float, ai_action: dict) -> tuple:
    # ...
    # King Model for cell temperature
    # Tcell = Tamb + DNI * exp(a + b * WS)
    a, b = -3.47, -0.05
    cell_temp = temp_c + dni * math.exp(a + b * wind_speed)
    
    # Thermal derating using cell_temp, allows efficiency increase below 25C
    temp_derate = 1.0 + ((cell_temp - 25.0) * TEMP_COEF)
```

- [ ] **Step 2: Update existing tests to pass `wind_speed` parameter**

Update all calls in `tests/test_panel_feedback.py` to include a default `wind_speed=2.0`.

- [ ] **Step 3: Run tests to verify they still pass with baseline values**

Run: `pytest tests/test_panel_feedback.py`

### Task 2: Implement Spectral Correction (Air Mass)

**Files:**
- Modify: `src/physics_engine/panel_feedback.py`

- [ ] **Step 1: Implement Air Mass and Spectral Correction factor**

```python
    # Spectral Correction (Air Mass)
    zenith_rad = math.radians(90.0 - sun_alt)
    am = 1.0 / math.cos(zenith_rad) if sun_alt > 0 else 0
    # f1(AM) = 0.98 + 0.02 * AM - 0.001 * AM^2
    spectral_correction = 0.98 + 0.02 * am - 0.001 * (am**2)
    spectral_correction = min(1.0, spectral_correction)
```

- [ ] **Step 2: Apply spectral correction to hardware efficiency**

```python
    hardware_efficiency = EFFICIENCY * temp_derate * aqi_derate * spectral_correction
```

### Task 3: Refine Irradiance with SVF and Diffuse Radiation

**Files:**
- Modify: `src/physics_engine/panel_feedback.py`

- [ ] **Step 1: Create helper for SVF and update irradiance calculation**

```python
def get_sky_view_factor(tilt: float) -> float:
    return (1.0 + math.cos(math.radians(tilt))) / 2.0

# Inside calculate_energy:
def get_effective_irradiance(dni: float, shadow_factor: float, tilt: float) -> float:
    beam = dni * (1.0 - shadow_factor)
    diffuse = dni * 0.2 * get_sky_view_factor(tilt)
    return beam + diffuse
```

- [ ] **Step 2: Use `get_effective_irradiance` for all three energy modes (Fixed, Tracker, AI)**

Ensure each mode uses its specific tilt for SVF.

### Task 4: Final Validation and Clean-up

**Files:**
- Modify: `tests/test_panel_feedback.py`

- [ ] **Step 1: Add new test case for Wind Speed impact on yield**
- [ ] **Step 2: Add new test case for Air Mass impact**
- [ ] **Step 3: Run all tests and verify PASS**
- [ ] **Step 4: Commit all changes**
