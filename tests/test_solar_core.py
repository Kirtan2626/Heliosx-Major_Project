import pytest
import datetime
from src.physics_engine.solar_core import get_solar_position

def test_solar_position_noon():
    # Test roughly solar noon in New Delhi
    # Solar noon is around 12:22 PM local time due to longitude 77.21 E and IST meridian 82.5 E
    dt = datetime.datetime(2026, 6, 21, 12, 22)
    alt, az = get_solar_position(lat=28.61, lon=77.21, utc_offset=5.5, dt=dt)
    
    assert alt > 80.0 # High in the sky near summer solstice
    assert 170.0 < az < 190.0 # Roughly South

def test_clear_sky_dni():
    from src.physics_engine.solar_core import get_clear_sky_dni
    
    # Midday, sea level
    dni_midday = get_clear_sky_dni(alt_deg=90.0, altitude_m=0.0)
    assert 800.0 < dni_midday < 1100.0
    
    # Nighttime
    dni_night = get_clear_sky_dni(alt_deg=-10.0, altitude_m=0.0)
    assert dni_night == 0.0
    
    # High altitude should have higher DNI
    dni_mountain = get_clear_sky_dni(alt_deg=90.0, altitude_m=5000.0)
    assert dni_mountain > dni_midday

def test_solar_position_edge_cases():
    # Test zenith case (where it used to crash)
    dt = datetime.datetime(2026, 6, 21, 12, 0)
    
    # Matching the logic that triggered ZeroDivisionError in reproduction
    import math
    n = dt.timetuple().tm_yday
    gamma = 2 * math.pi / 365 * (n - 1 + (dt.hour - 12) / 24)
    decl_rad = 0.006918 - 0.399912 * math.cos(gamma) + 0.070257 * math.sin(gamma) \
               - 0.006758 * math.cos(2 * gamma) + 0.000907 * math.sin(2 * gamma) \
               - 0.002697 * math.cos(3 * gamma) + 0.00148 * math.sin(3 * gamma)
    lat = math.degrees(decl_rad)
    
    eqtime = 229.18 * (0.000075 + 0.001868 * math.cos(gamma) - 0.032077 * math.sin(gamma) 
                       - 0.014615 * math.cos(2 * gamma) - 0.040849 * math.sin(2 * gamma))
    lon = -eqtime / 4
    
    alt, az = get_solar_position(lat=lat, lon=lon, utc_offset=0.0, dt=dt)
    
    assert abs(alt - 90.0) < 0.0001
    assert az == 180.0 # Our fallback value for zenith/poles
    
    # Test North Pole
    alt_np, az_np = get_solar_position(lat=90.0, lon=0.0, utc_offset=0.0, dt=dt)
    assert alt_np > 0 # Polar day in June
    assert az_np == 180.0
