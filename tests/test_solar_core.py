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
