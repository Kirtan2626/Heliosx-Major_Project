# Helios-X: Software Digital Twin for Solar Asset Diagnosis and Optimization

## 1. Project Goal
The primary goal of **Helios-X** is to provide an industry-grade, strictly software-based **Physics-Informed Reinforcement Learning Digital Twin** for solar energy systems. It moves beyond traditional, static solar dashboards by proactively diagnosing performance drops, predicting environmental failures, optimizing panel tracking to evade shadows, and providing commercial impact analytics—all without requiring immediate physical hardware integration.

## 2. Project Aim
Large commercial solar installations often suffer from yield degradation due to complex, overlapping factors: thermal stress, dust accumulation (soiling), partial shading from urban geometry, and inverter or panel faults. 

Helios-X aims to solve this by creating a **hybrid intelligence layer**:
*   **The Physics Engine** calculates the exact theoretical performance of a solar asset given perfect clear-sky conditions and exact astronomical geometry.
*   **The AI Engine (Double DQN & Q-Tables)** learns to adapt to real-world deviations, dynamically adjusting panel orientation to dodge shadows or entering safe-modes during extreme weather.
*   **The Diagnostic Layer** compares the Physics Engine's theoretical output against the AI's simulated reality to intelligently isolate and explain *why* energy loss is occurring (e.g., separating a drop caused by a passing cloud from a drop caused by an electrical inverter fault).

## 3. Scope
The scope of Helios-X is bound strictly to the **Software Simulation and Visualization Layer**. 
It is designed to be a defensible, presentation-ready platform suitable for patent discussions, hackathons, and commercial investor demonstrations.

### In-Scope:
*   **Global Location Integration:** Users can select any coordinate on Earth via a MapLibre GL / Google Maps interface.
*   **Real-Time Data Pipelines:** Integration with live APIs (Open-Meteo, OpenWeatherMap) to fetch real-world temperature, humidity, wind, and cloud cover.
*   **Geospatial Context (3D City/Terrain):** Integration with OpenStreetMap (OSM) Overpass API to fetch real building footprints and tree data to construct accurate 3D shadow-casting geometry.
*   **Software Digital Twin Tracking:** A 3D WebGL visualization (Three.js) that renders the sun path, shadow movements, and the solar panel's tracking behavior in real-time.
*   **Explainable AI & Diagnostics:** Clear UI panels explaining *what* fault was detected, *why* the AI chose a specific tracking action, and *how much* financial loss is projected.
*   **MATLAB/Simulink Readiness:** Exporting the digital twin's physical and RL parameters into a structured JSON payload ready for ingestion by MATLAB Simscape Electrical workflows.

### Out-of-Scope (Future Expansion):
*   Direct hardware control (IoT actuator telemetry).
*   Live SCADA data ingestion from physical inverters.

## 4. Core Features

*   **Zero-Shot Climate Generalization:** A built-in *Climate Similarity Engine* evaluates the temperature, humidity, and cloud profile of a novel location, mapping it to known climate clusters (e.g., Hot-Dry, Coastal) to warm-start the AI model safely.
*   **Rooftop vs. Ground Mounting Logic:** Automatically detects if a selected coordinate intersects a building footprint and dynamically elevates the 3D solar panel to rest on the rooftop.
*   **Manual Obstacle Editor:** If OSM data is missing, users can manually construct buildings, water tanks, and trees in the dashboard to instantly cast simulated shadows on the panel.
*   **Commercial Impact Analytics:** Translates raw physics wattage drops into actionable business metrics: Estimated Daily kWh Loss, Financial USD Loss, and Maintenance Urgency.
*   **Defensive Rendering:** Rigorous software safeguards ensure the dashboard and physics engine never crash due to API rate limits or missing fields, gracefully falling back to deterministic procedural models and labeling data transparency.

## 5. Technology Stack

*   **Frontend UI:** Vanilla ES6 JavaScript, HTML5, Tailwind CSS, Chart.js.
*   **3D / Mapping:** MapLibre GL JS (Geospatial mapping), Three.js (Digital Twin rendering).
*   **Backend Server:** Python 3 (Custom lightweight HTTP handlers in `serve_dashboard.py`).
*   **Physics Engine:** Pure Python (Astronomical geometry, Hottel DNI models, Shadow ray-tracing).
*   **AI / Machine Learning:** PyTorch (Double Deep Q-Network), Gym (Environment modeling).
*   **External APIs:** Open-Meteo (Weather), OpenWeatherMap (Weather Fallback), OpenStreetMap Overpass (3D Buildings/Trees).

## 6. The Hybrid Learning Loop

1.  **Select:** User inputs coordinates or clicks the map.
2.  **Contextualize:** The backend fetches live weather and queries OSM for nearby 3D buildings.
3.  **Baseline:** The deterministic Physics Engine runs a clear-sky, unshaded mathematical baseline.
4.  **Inference:** The PyTorch Double DQN evaluates the complex 3D environment and commands the tracking servos to minimize shadow coverage while maximizing irradiance.
5.  **Diagnose:** The gap between the mathematical baseline and the AI's actual yield is analyzed by heuristic algorithms to classify the current fault state.
6.  **Visualize & Export:** Results are painted onto the frontend graphs, simulated in the 3D canvas, and packaged for MATLAB export.