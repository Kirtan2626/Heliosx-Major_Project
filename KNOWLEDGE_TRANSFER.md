# Helios-X Knowledge Transfer: AI Agent Handover

**Project Status:** Stable Production Candidate (KIRTAN - Copy)
**Date:** May 12, 2026
**Current Branch:** Master (Production API + Next.js Frontend)

## 1. Architectural Overview
The project has been unified into the `KIRTAN - Copy` directory. It uses a **Hybrid Intelligence** approach:
- **Frontend:** Next.js (App Router), React Three Fiber (3D), Tailwind CSS, Recharts.
- **Backend:** FastAPI (Python), SQLAlchemy Asyncio, PyTorch (DQN Inference).
- **Research:** Isolated sandbox for training and data scraping.

## 2. Completed Work (The Bridge Phase)

### 🧪 ML Research Isolation
We successfully migrated the advanced R&D code from `temp-main` into an isolated `ml_research/` directory.
- **Why:** To prevent the production FastAPI server from being bloated by heavy historical data scrapers (NASA Power, PVGIS) and training environments.
- **Contents:** `agent/`, `environment/`, `training/`, `data_pipeline/`, and `simulation/`. This allows future agents to **retrain** the AI without touching production code.

### 🏔️ Terrain-Aware Physics (Phase 3)
We upgraded the physics engine to be scientifically rigorous.
- **Logic:** Integrated `src/physics_engine/horizon_dem.py`.
- **Implementation:** The simulation loop now uses `is_sun_visible` to check if local terrain (hills/valleys) blocks the sun. If blocked, yield is zeroed out.
- **API Change:** `run_simulation` and the `/simulate` endpoint now accept an optional `horizon` array.

### 🛡️ Frontend Stabilization (The "Crash Fix")
We resolved a series of critical runtime errors that were forcing Next.js to "Fast Refresh" (sudden reloads).
- **Leaflet Fix:** Added a stable `key` to `MapContainer` in `SiteMap.tsx` to prevent instance collision.
- **3D Safety:** Added `isNaN` guards in `DigitalTwin3D.tsx` to handle missing sun parameters gracefully.
- **Data Completeness:** Fixed `src/heliosx_sim_server.py` to correctly include `sun_az` (azimuth), preventing `undefined` values from reaching the 3D renderer.
- **CORS:** Updated `src/serve_dashboard.py` to allow port `3001` (standard fallback port if `3000` is busy).

## 3. Current System State
- **Production Server:** Starts with `python -m uvicorn src.serve_dashboard:app --port 8000`.
- **Frontend Server:** Starts with `npm run dev` (usually on port 3000 or 3001).
- **Database:** `heliosx.db` (SQLite) is used for persistence. The schema is defined in `src/db_models.py`.

## 4. Future Roadmap (For Incoming Agents)

### Phase 4: Database Model Expansion
- **Task:** Update `src/db_models.py` to store extended telemetry (AQI source metadata, climate cluster ID).
- **Goal:** Enable historical trend charts for multi-source data.

### Phase 5: Dynamic Terrain Loading
- **Task:** Create a service to fetch real SRTM (NASA) elevation data based on coordinates and pass the `horizon` array to the `/simulate` endpoint.
- **Goal:** Automated "hill shading" for any point on Earth.

### Phase 6: Climate-Aware Initialization
- **Task:** Hook `src/services/climate_similarity.py` into the user onboarding flow.
- **Goal:** Automatically select the best pre-trained model weights based on the user's local climate (Coastal vs. Desert).

## ⚠️ Critical Notes
- **DO NOT** move files from `ml_research/` into `src/` unless they are lightweight inference/math helpers.
- **ALWAYS** check for `sun_alt` and `sun_az` completeness when modifying the simulation results payload.
- **STAY SAFE** with Leaflet components; they are sensitive to Next.js HMR (Hot Module Replacement). Use the `key` prop pattern to stabilize them.
