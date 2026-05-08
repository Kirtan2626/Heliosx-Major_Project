import math
from src.physics_engine.solar_core import calculate_air_mass

# System constants
PANEL_AREA = 2.0 # m^2
EFFICIENCY = 0.20 # 20%
TEMP_COEF = -0.0035 # -0.35% per degree C above 25

def get_incident_angle(sun_alt: float, sun_az: float, panel_tilt: float, panel_az: float) -> float:
    # Cosine of angle of incidence
    # cos(theta) = sin(alt)*cos(tilt) + cos(alt)*sin(tilt)*cos(sun_az - panel_az)
    sin_alt = math.sin(math.radians(sun_alt))
    cos_alt = math.cos(math.radians(sun_alt))
    sin_tilt = math.sin(math.radians(panel_tilt))
    cos_tilt = math.cos(math.radians(panel_tilt))
    cos_az_diff = math.cos(math.radians(sun_az - panel_az))
    
    cos_inc = sin_alt * cos_tilt + cos_alt * sin_tilt * cos_az_diff
    return max(0.0, cos_inc)

def get_sky_view_factor(tilt: float) -> float:
    # SVF = (1 + cos(tilt)) / 2
    return (1.0 + math.cos(math.radians(tilt))) / 2.0

def calculate_energy(dni: float, temp_c: float, wind_speed: float, aqi: float, shadow_factor: float, 
                     sun_alt: float, sun_az: float, ai_action: dict) -> tuple:
    if sun_alt <= 0:
        return 0.0, 0.0, 0.0
        
    # King Model for cell temperature (open-rack constants)
    # Tcell = Tamb + DNI * exp(a + b * WS)
    a, b = -3.47, -0.05
    cell_temp = temp_c + dni * math.exp(a + b * wind_speed)
    
    # Spectral Correction (Air Mass)
    am = calculate_air_mass(sun_alt)
    
    # f1(AM) = 0.98 + 0.02 * AM - 0.001 * AM^2
    # Guard against negative values and cap at 1.0
    spectral_correction = max(0.0, min(1.0, 0.98 + 0.02 * am - 0.001 * (am**2)))
    
    # Hardware losses (efficiency can increase below 25C)
    temp_derate = 1.0 + ((cell_temp - 25.0) * TEMP_COEF)
    aqi_derate = max(0.5, 1.0 - (aqi / 500.0) * 0.2) # Max 20% loss at 500 AQI
    hardware_efficiency = EFFICIENCY * temp_derate * aqi_derate * spectral_correction
    
    # 1. Fixed Baseline (30 deg tilt, facing South/180)
    tilt_fixed = 30.0
    inc_fixed = get_incident_angle(sun_alt, sun_az, tilt_fixed, 180.0)
    g_beam_fixed = dni * (1.0 - shadow_factor) * inc_fixed
    g_diffuse_fixed = dni * 0.2 * get_sky_view_factor(tilt_fixed)
    energy_fixed = (g_beam_fixed + g_diffuse_fixed) * PANEL_AREA * hardware_efficiency
    
    # 2. Perfect Tracker Baseline (Tilt = 90-Alt, Az = Sun Az)
    tilt_tracker = 90.0 - sun_alt
    inc_tracker = 1.0 # Perfect tracking
    g_beam_tracker = dni * (1.0 - shadow_factor) * inc_tracker
    g_diffuse_tracker = dni * 0.2 * get_sky_view_factor(tilt_tracker)
    energy_tracker = (g_beam_tracker + g_diffuse_tracker) * PANEL_AREA * hardware_efficiency
    
    # 3. AI Tracker
    if ai_action.get("mode") == "stow":
        tilt_ai = 0.0
        az_ai = 180.0
    elif ai_action.get("mode") == "diffuse":
        tilt_ai = 0.0
        az_ai = 180.0
        # Diffuse mode specifically targets scattered light
        # Increase diffuse contribution if shaded
        inc_ai = get_incident_angle(sun_alt, sun_az, tilt_ai, az_ai)
        g_beam_ai = dni * (1.0 - shadow_factor) * inc_ai
        diffuse_boost = 0.3 if shadow_factor > 0 else 0.2
        g_diffuse_ai = dni * diffuse_boost * get_sky_view_factor(tilt_ai)
        energy_ai = (g_beam_ai + g_diffuse_ai) * PANEL_AREA * hardware_efficiency
        return energy_fixed, energy_tracker, energy_ai
    else:
        tilt_ai = max(0, min(90, (90 - sun_alt) + ai_action.get("tilt_bias", 0)))
        az_ai = sun_az + ai_action.get("azimuth_bias", 0)
    
    inc_ai = get_incident_angle(sun_alt, sun_az, tilt_ai, az_ai)
    g_beam_ai = dni * (1.0 - shadow_factor) * inc_ai
    g_diffuse_ai = dni * 0.2 * get_sky_view_factor(tilt_ai)
    energy_ai = (g_beam_ai + g_diffuse_ai) * PANEL_AREA * hardware_efficiency
    
    return energy_fixed, energy_tracker, energy_ai
