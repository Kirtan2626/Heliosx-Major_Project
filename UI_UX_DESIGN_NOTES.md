# UI/UX & Color Expert Design Notes

The frontend of Helios-X was designed using principles from expert UI/UX and color theory guidelines, specifically tailored for "Spatial Computing" and "Climate Tech" data-dense dashboards. If you modify the frontend, please adhere to these design decisions.

## 1. The Theme: Glassmorphism + Dark Mode (OLED)
The application uses a deep dark theme. This is not just an aesthetic choice; for a highly data-dense, real-time tracking application, a dark background prevents eye strain and provides maximum contrast for telemetry data.

*   **Background:** Deep slate (`bg-slate-950` / `#020617`). We avoid pure `#000000` to soften the contrast slightly for extended viewing, but keep it dark enough for OLED efficiency.
*   **Panels:** We use a variation of **Glassmorphism**. The panels are `bg-slate-900` with subtle borders (`border-slate-800`). This gives the UI a "Spatial OS" feel, making the controls feel like they are floating around the central 3D environment.

## 2. Color Palette (Semantic OKLCH principles)
We avoid arbitrary, clashing hex codes in favor of a perceptually balanced palette:
*   **Action/Brand (Orange/Yellow):** We use gradients (`from-orange-400 to-yellow-200`) and solid accents (`bg-orange-600`) for primary CTAs like the "Run Simulation" button and the AI Yield lines on the charts. Orange is energetic and visually represents solar power without the harshness of pure yellow on a dark background.
*   **Data/Neutral (Slate/Blue):** The Fixed and Tracker baseline data use cool blues (`text-blue-400`, `stroke-#3b82f6`) to recede into the background compared to the AI metrics.
*   **Diagnostics (Semantic):** 
    *   Healthy/Success: Green (`text-green-400`).
    *   Warnings (Shading/Thermal): Yellow (`text-yellow-400`).
    *   Critical (High Financial Loss): Red (`text-red-400`).

## 3. Layout: Three-Column Dashboard
The layout abandons standard vertical scrolling in favor of a rigid, full-height (`h-[85vh]`), three-column grid:
1.  **Left Column (Controls):** Dedicated exclusively to inputs (Map, Lat/Lon, Search bar). By keeping these together without scrolling (`overflow` removed), the user's focus remains steady.
2.  **Center Column (Visualization):** The largest column, dedicated entirely to the 3D Digital Twin. 
    *   **3D Environment Colors:** To avoid a "pitch black" void at night, the Three.js Canvas uses a softer slate background (`#1e293b`), with boosted hemisphere lighting (`#334155` ground) and a clamped twilight sky. This ensures spatial awareness is never lost.
3.  **Right Column (Analytics):** Dedicated to outputs. Organizes data hierarchically: Current State (Weather) -> Yield Results (Charts) -> Impact (Diagnostics).

## 4. Typography & Icons
*   **Font:** We use the system sans-serif (Inter-like) for clear, readable numbers in dense data tables.
*   **Icons:** We exclusively use `lucide-react` SVG icons. **Rule:** Never use emojis as UI icons. Emojis lack consistent sizing and professional aesthetic control.
*   **Monospace:** All numbers that change frequently (telemetry, coordinates, timeline timestamps) use the `font-mono` class to prevent jittery layout shifts as the numbers update during the 3D replay animation.