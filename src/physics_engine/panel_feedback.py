import math

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

def calculate_energy(dni: float, temp_c: float, aqi: float, shadow_factor: float, 
                     sun_alt: float, sun_az: float, ai_action: dict) -> tuple:
    if sun_alt <= 0:
        return 0.0, 0.0, 0.0
        
    # Hardware losses
    temp_derate = 1.0 + (max(0.0, temp_c - 25.0) * TEMP_COEF)
    aqi_derate = max(0.5, 1.0 - (aqi / 500.0) * 0.2) # Max 20% loss at 500 AQI
    hardware_efficiency = EFFICIENCY * temp_derate * aqi_derate
    
    # Shadow logic (Diffuse sky radiation still exists even if DNI is blocked)
    # If shaded, assume 80% DNI loss (leaving 20% diffuse)
    effective_dni = dni * (1.0 - (shadow_factor * 0.8))
    
    max_power = effective_dni * PANEL_AREA * hardware_efficiency
    
    # 1. Fixed Baseline (30 deg tilt, facing South/180)
    inc_fixed = get_incident_angle(sun_alt, sun_az, 30.0, 180.0)
    energy_fixed = max_power * inc_fixed
    
    # 2. Perfect Tracker Baseline (Tilt = 90-Alt, Az = Sun Az)
    # Cosine of incidence is always 1.0
    energy_tracker = max_power * 1.0
    
    # 3. AI Tracker
    if ai_action.get("mode") == "stow":
        inc_ai = get_incident_angle(sun_alt, sun_az, 0.0, 180.0)
    elif ai_action.get("mode") == "diffuse":
        inc_ai = get_incident_angle(sun_alt, sun_az, 0.0, 180.0)
        # Diffuse mode is meant to capture scattered light, boost slightly if shaded
        if shadow_factor > 0:
            # Re-calculate max_power for diffuse mode if shaded
            # 20% was base diffuse, maybe 30% is better?
            effective_dni_diffuse = dni * 0.3 # Better than 0.2
            max_power_diffuse = effective_dni_diffuse * PANEL_AREA * hardware_efficiency
            energy_ai = max_power_diffuse * inc_ai
            return energy_fixed, energy_tracker, energy_ai
    else:
        ai_tilt = max(0, min(90, (90 - sun_alt) + ai_action.get("tilt_bias", 0)))
        ai_az = sun_az + ai_action.get("azimuth_bias", 0)
        inc_ai = get_incident_angle(sun_alt, sun_az, ai_tilt, ai_az)
        
    energy_ai = max_power * inc_ai
    
    return energy_fixed, energy_tracker, energy_ai
