import math
from datetime import datetime, timedelta
from src.physics_engine.solar_core import get_solar_position, get_clear_sky_dni
from src.physics_engine.obstacle_engine import calculate_shadow_factor
from src.physics_engine.panel_feedback import calculate_energy
from src.heliosx_ai_policy import HeliosXPolicy
from src.physics_engine.fault_diagnosis import classify_faults
from src.services.commercial_impact import calculate_impact

policy = HeliosXPolicy()

DEFAULT_AQI = 50.0

def project_coordinates(base_lat: float, base_lon: float, target_lat: float, target_lon: float) -> tuple:
    # Haversine approximation to local Cartesian (Meters)
    R = 6378137 # Earth radius in meters
    dLat = math.radians(target_lat - base_lat)
    dLon = math.radians(target_lon - base_lon)
    
    x = R * dLon * math.cos(math.radians(base_lat))
    y = R * dLat
    return (x, y)

def build_cartesian_context(base_lat: float, base_lon: float, context_data: dict) -> list:
    obstacles = []
    for b in context_data.get("buildings", []):
        geom = b.get("geometry", [])
        if geom:
            poly = []
            for pt in geom:
                x, y = project_coordinates(base_lat, base_lon, pt["lat"], pt["lon"])
                poly.append((x, y))
        else:
            # Fallback to a square slightly North if no geometry
            poly = [(-5, 5), (5, 5), (5, 15), (-5, 15)]
            
        obstacles.append({
            "type": "building", 
            "polygon": poly, 
            "z_height": float(b.get("tags", {}).get("height", 10.0))
        })
        
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

def run_simulation(lat: float, lon: float, weather: dict, context: dict, start_dt: datetime = None, utc_offset: float = 0.0, **kwargs) -> dict:
    if start_dt is None:
        # Default to today at midnight if not provided
        start_dt = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    obstacles = build_cartesian_context(lat, lon, context)
    
    results = []
    total_fixed, total_tracker, total_ai = 0.0, 0.0, 0.0
    
    # Safe default regime (e.g., New Delhi regime 0)
    regime = [1.0] + [0.0] * 10
    
    for step in range(48): # 48 half-hour intervals
        dt = start_dt + timedelta(minutes=30 * step)
        
        # 1. Solar Math
        alt, az = get_solar_position(lat, lon, utc_offset, dt)
        dni = get_clear_sky_dni(alt, 100.0) # assume 100m site alt
        
        # 2. Shadows
        shadow = calculate_shadow_factor(alt, az, obstacles)
        
        # 3. AI Policy
        temp_c = weather.get("temperatureC", 25.0)
        wind_speed = weather.get("windSpeed", 5.0)
        aqi = kwargs.get("aqi", DEFAULT_AQI)
        
        state = {
            "sun_altitude": alt, 
            "sun_azimuth": az,
            "hour_of_day": dt.hour + (dt.minute/60.0), 
            "day_of_year": dt.timetuple().tm_yday,
            "cloud_fraction": weather.get("cloudCoverPercent", 0.0) / 100.0,
            "aqi": aqi, 
            "shadow_factor": shadow,
            "latitude": lat, 
            "longitude": lon, 
            "site_altitude": 100.0, 
            "dni": dni,
            "regime_vector": regime
        }
        action = policy.get_action(state)
        
        # 4. Energy
        e_fix, e_tr, e_ai = calculate_energy(
            dni, 
            temp_c, 
            wind_speed, 
            aqi, 
            shadow, 
            alt, 
            az, 
            action
        )
        
        total_fixed += e_fix
        total_tracker += e_tr
        total_ai += e_ai
        
        results.append({
            "time": dt.strftime("%H:%M"),
            "sun_alt": round(alt, 2),
            "shadow": shadow,
            "action": action["mode"],
            "energy_ai": round(e_ai, 2),
            "energy_tracker": round(e_tr, 2),
            "temp_c": temp_c,
            "dni": round(dni, 2),
            "aqi": aqi,
            "wind_speed": wind_speed
        })
        
    totals = {
        "fixed_wh": round(total_fixed, 2),
        "tracker_wh": round(total_tracker, 2),
        "ai_wh": round(total_ai, 2)
    }
    
    results_dict = {
        "lat": lat, "lon": lon,
        "daily_totals": totals,
        "timeseries": results,
        "obstacles": obstacles
    }
    
    # Analytics
    results_dict["faults"] = classify_faults(results)
    
    # wh_loss is tracker minus ai
    wh_loss = max(0.0, totals["tracker_wh"] - totals["ai_wh"])
    # use dynamic tariff if provided in kwargs, else 0.15
    results_dict["commercial_impact"] = calculate_impact(wh_loss, tariff=kwargs.get("tariff", 0.15))
    
    return results_dict
