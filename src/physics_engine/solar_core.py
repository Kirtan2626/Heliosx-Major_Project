import math
import datetime

def get_day_of_year(dt: datetime.datetime) -> int:
    return dt.timetuple().tm_yday

def get_solar_position(lat: float, lon: float, utc_offset: float, dt: datetime.datetime) -> tuple:
    # 1. Fractional year
    n = get_day_of_year(dt)
    gamma = 2 * math.pi / 365 * (n - 1 + (dt.hour - 12) / 24)
    
    # 2. Equation of time (minutes)
    eqtime = 229.18 * (0.000075 + 0.001868 * math.cos(gamma) - 0.032077 * math.sin(gamma) 
                       - 0.014615 * math.cos(2 * gamma) - 0.040849 * math.sin(2 * gamma))
    
    # 3. Solar declination (radians)
    decl_rad = 0.006918 - 0.399912 * math.cos(gamma) + 0.070257 * math.sin(gamma) \
               - 0.006758 * math.cos(2 * gamma) + 0.000907 * math.sin(2 * gamma) \
               - 0.002697 * math.cos(3 * gamma) + 0.00148 * math.sin(3 * gamma)
               
    # 4. True solar time (minutes)
    time_offset = eqtime + 4 * lon - 60 * utc_offset
    tst = dt.hour * 60 + dt.minute + dt.second / 60 + time_offset
    
    # 5. Hour angle (radians)
    ha_rad = math.radians((tst / 4) - 180)
    lat_rad = math.radians(lat)
    
    # 6. Solar Zenith Angle (radians)
    zenith_rad = math.acos(math.sin(lat_rad) * math.sin(decl_rad) + 
                           math.cos(lat_rad) * math.cos(decl_rad) * math.cos(ha_rad))
    alt_deg = 90 - math.degrees(zenith_rad)
    
    # 7. Solar Azimuth Angle (radians)
    cos_az = (math.sin(decl_rad) - math.sin(lat_rad) * math.cos(zenith_rad)) / \
             (math.cos(lat_rad) * math.sin(zenith_rad))
    cos_az = max(-1.0, min(1.0, cos_az)) # clip
    az_rad = math.acos(cos_az)
    
    az_deg = math.degrees(az_rad)
    if ha_rad > 0:
        az_deg = 360 - az_deg
        
    return alt_deg, az_deg

def get_clear_sky_dni(alt_deg: float, altitude_m: float) -> float:
    # Simplified Hottel model
    if alt_deg <= 0: return 0.0
    
    a0 = 0.4237 - 0.00821 * (6 - altitude_m/1000)**2
    a1 = 0.5055 + 0.00595 * (6.5 - altitude_m/1000)**2
    k = 0.2711 + 0.01858 * (2.5 - altitude_m/1000)**2
    
    air_mass = 1 / (math.sin(math.radians(alt_deg)) + 0.50572 * (alt_deg + 6.07995)**-1.6364)
    tau = a0 + a1 * math.exp(-k * air_mass)
    
    return 1367.0 * tau # Solar constant
