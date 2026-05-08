# Helios-X Backend Architecture & Data Flow Documentation

This document provides a comprehensive, deep-dive architectural map of the Helios-X Software Digital Twin backend. It details the exact execution flow from the moment an HTTP request is received, through the geospatial and weather data pipelines, into the deterministic Physics Engine, the Reinforcement Learning (RL) inference, and finally out to the diagnostic and MATLAB export layers.

---

## 1. High-Level Architecture Block Diagram

```text
[ Frontend Dashboard ]
        │
        ▼ (HTTP GET /simulate, /weather, /site-context)
[ API Gateway: serve_dashboard.py ]
        │
        ├─► [ Weather Service ] ──► Open-Meteo / OpenWeatherMap (Normalized)
        │
        └─► [ Simulation Server: heliosx_sim_server.py ] (The Core Loop)
                  │
                  ├─► 1. [ Geospatial Context ] ──► OpenStreetMap / Procedural Engine
                  │
                  ├─► 2. [ Physics Engine ] ──────► Solar Geometry, DNI, Shadow Ray-Tracing, Panel Losses
                  │
                  ├─► 3. [ AI / RL Engine ] ──────► Double DQN Inference (checkpoints/*.pt)
                  │
                  ├─► 4. [ Diagnostics Layer ] ───► Fault Diagnosis, Climate Similarity, Commercial Impact
                  │
                  └─► 5. [ Export Layer ] ────────► MATLAB/Simulink JSON formatting
```

---

## 2. The Complete Execution Flow (Step-by-Step)

When a user clicks **"Analyse Location"** on the dashboard, the following sequence strictly executes:

### Phase 1: Pre-Simulation Data Gathering
1. **Weather Fetch (`/weather`):** The frontend requests live weather data for the selected coordinates. `weather_service.py` checks its local cache. If stale, it pings the Open-Meteo API (with an automated fallback to OpenWeatherMap). It normalizes the payload to guarantee `temperatureC`, `windSpeed`, `humidity`, and `cloudCover` exist safely without `undefined` values.
2. **Simulation Dispatch (`/simulate`):** The frontend fires a request to `serve_dashboard.py` with coordinates, mounting type, manual obstacles, and fallback weather parameters.
3. **Geospatial Fetch (`fetch_site_context`):** `heliosx_sim_server.py` queries `site_context.py`.
    * It builds a bounding box around the coordinates.
    * It queries the **OpenStreetMap Overpass API** for `building` footprints and `tree` nodes.
    * If OSM data is missing, it injects the user's **Manual Obstacles** from the frontend.
    * If both are empty, it falls back to **Procedural Generation** (using deterministic RNG based on coordinate seeds) to ensure the simulation always has shadow-casting geometry.
4. **Rooftop Detection:** If the user selected `rooftop` mounting, the backend calculates the physical intersection between the panel's coordinates (`X=50, Y=50`) and nearby building footprints. It extracts the height of the intersecting building to elevate the Z-axis of the solar panel.

### Phase 2: The 48-Step Physics-AI Simulation Loop
The server initializes a 48-step loop (representing 30-minute intervals over a 24-hour day). For every timestep `k`:

1. **Solar Astronomy (`solar_core.py`):**
    * Calculates Solar Declination.
    * Calculates Hour Angle (using Longitude timezone offset correction for local solar noon).
    * Calculates exact Sun Altitude and Sun Azimuth.
2. **Clear-Sky Irradiance:**
    * Calculates Air Mass (Kasten-Young model).
    * Calculates Direct Normal Irradiance (DNI) using the Hottel Clear-Sky model.
3. **Shadow Ray-Tracing (`obstacle_engine.py` / inline logic):**
    * Fires a vector towards the Sun Azimuth/Altitude.
    * Checks intersections against all loaded OSM/Manual 3D obstacles.
    * Returns a `shadow_factor` (0.0 = fully lit, 1.0 = fully shaded), splitting into Hard Shadows (buildings), Soft Shadows (penumbra), and Diffuse Shadows (clouds).
4. **AI Policy Inference (`heliosx_ai_policy.py`):**
    * The raw physical state (Sun angles, DNI, temp, cloud cover, shadow factor) is passed to the AI wrapper.
    * **State Construction:** Variables are normalized into a continuous 14-dimensional PyTorch tensor.
    * **Regime Vectors:** Uses `climate_similarity.py` logic to calculate the Euclidean distance to 6 known climate clusters, embedding this into the state.
    * **Double DQN Forward Pass:** The model (`checkpoints/dqn_final_helios_x_v2_regime_conditioned.pt`) evaluates the state and outputs a discrete action ID (0-12).
5. **Action Translation & Safety Filters:**
    * The Action ID is decoded into mechanical commands: `tilt_bias` (e.g., +15°), `azimuth_bias`, `stow` (flat), or `diffuse` (flat to catch scattered light).
    * `safety_filter()` clamps mechanical rotation if wind limits are exceeded or the requested angle violates structural bounds relative to the sun.
6. **Energy Calculation (`panel_feedback.py`):**
    * **Baseline Fixed:** Calculates energy for a panel fixed at 30° South/North.
    * **Deterministic Tracker:** Calculates energy for perfect 2-axis tracking pointing directly at the sun.
    * **DQN RL Tracker:** Calculates energy using the AI's offset (which may purposely look *away* from the sun to dodge a building's shadow).
    * Applies Thermal Derating (King model), Spectral Correction, and AQI attenuation.

### Phase 3: Post-Simulation Analytics & Diagnostics
Once the 48-timestep loop completes, the aggregated data undergoes software-level diagnosis:

1. **Fault Diagnosis (`fault_diagnosis.py`):**
    * The backend compares the simulated "Expected Clear-Sky Power" against the "Actual Simulated Power".
    * Uses a heuristic tree to classify faults:
        * *High Temp + Linear Drop* = Thermal Derating.
        * *High AQI + Low Wind* = Dust/Soiling.
        * *Non-linear drop + Low Sun Alt* = Shading.
2. **Commercial Impact (`commercial_impact.py`):**
    * Converts energy loss into `kWh_loss`.
    * Multiplies by standard grid tariffs to output `financial_loss_usd`.
    * Assigns a Maintenance Urgency tag (e.g., "Schedule within 48 hours").
3. **MATLAB Payload Generation (`matlab_export_service.py`):**
    * The entire simulation payload (Time series, Geospatial Obstacles, Mounting heights, RL actions, Fault flags) is formatted into a strictly keyed JSON object perfectly compatible with MATLAB Simscape Electrical `jsondecode()`.

---

## 3. Directory & File Map

### Core API Server
*   `serve_dashboard.py`: Lightweight HTTP server. Routes UI file serving, proxies weather API calls, and exposes `/simulate` and `/export-matlab`.

### Simulation Server
*   `heliosx_sim_server.py`: The heart of the backend. Contains the 48-step physics loop, ray-tracer, baseline metric generators, and integrates the external services.

### Physics Engine
*   `physics_engine/solar_core.py`: Astronomical sun tracking and atmospheric geometry.
*   `physics_engine/panel_feedback.py`: Hardware loss modeling (Temp, Spectral, AQI).
*   `physics_engine/fault_diagnosis.py`: Software digital twin anomaly classifier.
*   `physics_engine/obstacle_engine.py`: Legacy bounding-box obstacle logic (superceded by inline raytracing in sim server).

### AI & RL Engine
*   `heliosx_ai_policy.py`: The bridge between the Python simulation loop and the PyTorch neural network. Loads the `.pt` checkpoint and handles fallback physics if Torch fails.
*   `agent/dqn_agent.py`: The PyTorch architecture for the Double Deep Q-Network.
*   `agent/tabular_agent.py`: A discretized Q-learning table used for baseline comparisons and warm-starting.
*   `environment/solar_env.py`: The OpenAI Gym environment used during the original training phase of the model.

### Microservices (`backend/services/`)
*   `climate_similarity.py`: Zero-shot generalization. Measures Euclidean distance between live weather and known climate clusters (Hot-Dry, Coastal, etc.) to set AI priors.
*   `commercial_impact.py`: Financial and downtime risk calculator.
*   `matlab_export_service.py`: Generates the `matlab_export.json` payload.

### Data Connectors
*   `weather_service.py`: Handles caching, fallback logic (Open-Meteo -> OpenWeatherMap), and strict data normalization for wind, clouds, and temperature.
*   `site_context.py`: OpenStreetMap Overpass API connector. Extracts building footprints, heights, roof shapes, and parses biological tree dimensions.

### Model Weights
*   `checkpoints/dqn_final_helios_x_v2_regime_conditioned.pt`: The final, active PyTorch model weights loaded into memory for real-time tracking inference.

---

## 4. Detailed Data Schemas

### RL State Space (14 Dimensions Continuous)
1. Sun Altitude (deg)
2. Sun Azimuth Sine
3. Sun Azimuth Cosine
4. Hour of Day Sine
5. Hour of Day Cosine
6. Day of Year Sine
7. Day of Year Cosine
8. Cloud Fraction (0.0 to 1.0)
9. AQI (Air Quality Index)
10. Shadow Factor (Lit fraction: 0.0 to 1.0)
11. Latitude (Normalized)
12. Longitude (Normalized)
13. Site Altitude (Normalized)
14. Direct Normal Irradiance (Normalized)

### RL Action Space (13 Dimensions Discrete)
*   **0-2:** Tilt Bias [-15°, -10°, -5°] *(Shadow Evasion)*
*   **3:** Identity [0°] *(Perfect Deterministic Tracking)*
*   **4-6:** Tilt Bias [+5°, +10°, +15°] *(Shadow Evasion)*
*   **7-8:** Azimuth Bias [-15°, +15°]
*   **9-10:** Compound Bias [+10°/-10° on both axes]
*   **11:** Stow Mode *(Flat, used at night or high wind)*
*   **12:** Diffuse Mode *(Flat, used during heavy cloud cover >60% to absorb isotropic sky radiation)*

### Unified Environmental Payload
```json
{
  "temperatureC": 33.8,
  "roundedTemperatureC": 34,
  "humidityPercent": 50.0,
  "windSpeed": 3.2,
  "windSpeedUnit": "m/s",
  "cloudCoverPercent": 20.0,
  "source": "Open-Meteo",
  "sourceLabel": "Open-Meteo (Live API)",
  "fetchedAt": "5/8/2026, 2:32:00 PM"
}
```

## 5. Defense Mechanisms & Reliability
*   **Weather Safe Fallbacks:** If APIs fail, `heliosx_sim_server.py` coerces `null` or `undefined` strings into safe physics assumptions (e.g., 35°C, 3.0 m/s wind) rather than crashing.
*   **PyTorch Fallback:** If `torch` is not installed on the host machine, `heliosx_ai_policy.py` detects this and automatically routes all decisions through `fallback_policy()`, a deterministic logic tree that mirrors the basic behavior of the AI without requiring neural network RAM overhead.
*   **Geospatial Fallback:** If OSM returns no footprints, the server procedurally spawns proxy geometry to ensure the shadow-evasion algorithms always have data to react to.