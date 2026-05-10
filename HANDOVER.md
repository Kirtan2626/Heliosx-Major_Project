# Helios-X Project Handover

Welcome to the Helios-X Digital Twin project. This document serves as the primary entry point for developers taking over the project.

## Project Overview
Helios-X is a high-fidelity solar simulation microservice and visualization dashboard. It acts as a "Digital Twin" for solar panel arrays, utilizing real-world weather data, exact 3D geospatial geometry (extruded building footprints and trees), and an AI policy (Double DQN) to optimize panel tracking and diagnose physical faults.

## Core Architecture
The system is divided into a robust Backend and a modern Frontend, fully containerized via Docker.

1.  **Backend (FastAPI, Python):**
    *   **API Gateway:** High-performance async endpoints (`src/serve_dashboard.py`).
    *   **Data Connectors:** Fetches live weather from Open-Meteo (`src/weather_service.py`) and 3D environment footprints from OpenStreetMap (`src/site_context.py`).
    *   **Physics Engine:** Custom implementations for solar astronomy, 3D ray-tracing for shadow detection, and rigorous hardware models (King thermal model, Spectral Correction, Sky View Factor) located in `src/physics_engine/`.
    *   **AI Policy:** A PyTorch wrapper (`src/heliosx_ai_policy.py`) that executes a 25-dimensional state inference to determine the optimal panel tilt and azimuth.
    *   **Database:** Async PostgreSQL persistence using SQLAlchemy (`src/database.py`, `src/db_models.py`).

2.  **Frontend (Next.js, React, TailwindCSS, Three.js):**
    *   Located in `frontend/`.
    *   **Dashboard (`frontend/src/app/page.tsx`):** A dense, 3-column layout.
    *   **Map Selection:** Leaflet map with a custom `/api/search` proxy to query OpenStreetMap Nominatim.
    *   **3D Viewer (`frontend/src/components/DigitalTwin3D.tsx`):** Renders the simulated environment. Features true 3D extruded building polygons, an animated sun sphere, dynamic twilight lighting, and a fully articulated 2-axis solar panel model controlled by the AI's output.
    *   **Analytics (`frontend/src/components/AnalyticsCharts.tsx`):** Real-time Recharts comparing Fixed, Tracker, and AI energy yields.

## Where to Find Detailed Documentation
To understand the deep mechanics, refer to the following files:
*   `backend_architecture_flow.md`: The theoretical foundation of the physics engine and AI model integration.
*   `CURRENT_STATUS.md`: A detailed breakdown of what is finished, including the latest 3D graphics upgrades, and future recommendations.
*   `UI_UX_DESIGN_NOTES.md`: The rationale behind the frontend's visual design, color palettes, and layout.
*   `docs/superpowers/plans/`: Contains the step-by-step implementation plans used to build Phase 1 through Phase 3 of the backend, as well as the frontend dashboard.

## Quick Start
To spin up the entire application stack:
```bash
docker-compose up --build
```
This will launch the Postgres database, the FastAPI backend on port `8000`, and the Next.js frontend on port `3000`.