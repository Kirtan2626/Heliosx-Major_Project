# Physics Upgrades Design Spec

## Goal
Upgrade the energy calculation model in `src/physics_engine/panel_feedback.py` to include rigorous physical models for cell temperature, spectral correction, and diffuse radiation.

## 1. King Model for Cell Temperature
Replace ambient temperature with cell temperature for thermal derating.
- **Formula:** $T_{cell} = T_{air} + DNI \times e^{a + b \times WS}$
- **Constants:** $a = -3.47$, $b = -0.05$ (Open-rack typical)
- **Parameters:** $T_{air}$ (ambient temp), $DNI$ (Direct Normal Irradiance), $WS$ (Wind Speed)

## 2. Spectral Correction (Air Mass)
Implement efficiency correction based on Air Mass.
- **Air Mass (AM):** $1 / \cos(90 - sun\_alt)$
- **Correction Factor:** $f_1(AM) = 0.98 + 0.02 \times AM - 0.001 \times AM^2$
- **Constraint:** Cap at 1.0 to avoid unrealistic gains at extreme angles.

## 3. Diffuse Radiation & Sky View Factor
Refine shading and irradiance capture.
- **Sky View Factor (SVF):** $(1 + \cos(tilt)) / 2$
- **Irradiance Model:** 
  - Direct Beam: $DNI \times (1 - shadow\_factor)$
  - Diffuse: $DNI \times 0.2 \times SVF$ (Assumes 20% baseline diffuse radiation)
  - Total: $G_{total} = Beam + Diffuse$

## 4. Temperature Derate Refinement
Allow efficiency to increase when $T_{cell} < 25^\circ C$.
- **New Formula:** `temp_derate = 1.0 + (cell_temp - 25.0) * TEMP_COEF`

## 5. API Changes
- Update `calculate_energy` signature to include `wind_speed`.
- Update tests to reflect new physical dependencies.

---
Design validated. Proceeding to implementation plan.
