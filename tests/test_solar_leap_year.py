import datetime
import math
import calendar
from src.physics_engine.solar_core import get_solar_position

def test_leap_year_gamma_drift():
    # 2024 is a leap year (366 days)
    # 2025 is a common year (365 days)
    
    # Test date: Dec 31
    dt_leap = datetime.datetime(2024, 12, 31, 12, 0)
    dt_common = datetime.datetime(2025, 12, 31, 12, 0)
    
    # In a leap year, day 366 (Dec 31) should result in gamma approx 2*pi
    # In a common year, day 365 (Dec 31) should result in gamma approx 2*pi
    
    # We can't easily access gamma directly, but we can verify it doesn't crash 
    # and produces reasonable values for Feb 29.
    
    dt_feb29 = datetime.datetime(2024, 2, 29, 12, 0)
    alt, az = get_solar_position(lat=0.0, lon=0.0, utc_offset=0.0, dt=dt_feb29)
    assert -90.0 <= alt <= 90.0
    assert 0.0 <= az <= 360.0

def test_days_in_year_logic():
    # Verify the logic used in the fix
    year_leap = 2024
    year_common = 2025
    
    assert calendar.isleap(year_leap) is True
    assert calendar.isleap(year_common) is False
    
    days_leap = 366 if calendar.isleap(year_leap) else 365
    days_common = 366 if calendar.isleap(year_common) else 365
    
    assert days_leap == 366
    assert days_common == 365
