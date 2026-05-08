import math
import datetime
from src.physics_engine.solar_core import get_solar_position

def test_zenith():
    print("Testing Zenith (alt=90)...")
    # Forcing a situation where sun is at zenith
    # If lat = declination and ha = 0, zenith = 0
    # Summer solstice: declination is ~23.44 deg
    # I will look at the code to see how it calculates declination
    import datetime
    dt = datetime.datetime(2026, 6, 21, 12, 0)
    # n = 172
    # gamma = 2 * pi / 365 * (172 - 1) = 2.943...
    # decl_rad = 0.409... rad ~= 23.44 deg
    # I'll just try to match the calculation in the function to get ha_rad = 0 and lat_rad = decl_rad
    
    from src.physics_engine.solar_core import get_day_of_year
    import math
    n = get_day_of_year(dt)
    gamma = 2 * math.pi / 365 * (n - 1 + (dt.hour - 12) / 24)
    decl_rad = 0.006918 - 0.399912 * math.cos(gamma) + 0.070257 * math.sin(gamma) \
               - 0.006758 * math.cos(2 * gamma) + 0.000907 * math.sin(2 * gamma) \
               - 0.002697 * math.cos(3 * gamma) + 0.00148 * math.sin(3 * gamma)
    lat_exact = math.degrees(decl_rad)
    
    # We also need ha_rad = 0
    # ha_rad = math.radians((tst / 4) - 180)
    # tst = 720
    # tst = dt.hour * 60 + dt.minute + dt.second / 60 + time_offset
    # dt.hour = 12, dt.minute = 0, dt.second = 0 -> tst = 720 + time_offset
    # time_offset = eqtime + 4 * lon - 60 * utc_offset
    # Let's set lon and utc_offset such that time_offset = -eqtime
    # or just Lon = 0, UTC = 0 and assume eqtime is small or handle it
    
    eqtime = 229.18 * (0.000075 + 0.001868 * math.cos(gamma) - 0.032077 * math.sin(gamma) 
                       - 0.014615 * math.cos(2 * gamma) - 0.040849 * math.sin(2 * gamma))
    
    lon_fix = -eqtime / 4
    
    try:
        alt, az = get_solar_position(lat=lat_exact, lon=lon_fix, utc_offset=0.0, dt=dt)
        print(f"Zenith result: alt={alt}, az={az}")
    except ZeroDivisionError:
        print("Zenith result: FAILED with ZeroDivisionError")
    except Exception as e:
        print(f"Zenith result: FAILED with {type(e).__name__}: {e}")

def test_poles():
    print("\nTesting North Pole (lat=90)...")
    # Using a date far from equinox so zenith is not 0
    dt = datetime.datetime(2026, 6, 21, 12, 0)
    try:
        alt, az = get_solar_position(lat=90.0, lon=0.0, utc_offset=0.0, dt=dt)
        print(f"North Pole result: alt={alt}, az={az}")
    except ZeroDivisionError:
        print("North Pole result: FAILED with ZeroDivisionError")
    except Exception as e:
        print(f"North Pole result: FAILED with {type(e).__name__}: {e}")

    print("\nTesting South Pole (lat=-90)...")
    try:
        alt, az = get_solar_position(lat=-90.0, lon=0.0, utc_offset=0.0, dt=dt)
        print(f"South Pole result: alt={alt}, az={az}")
    except ZeroDivisionError:
        print("South Pole result: FAILED with ZeroDivisionError")
    except Exception as e:
        print(f"South Pole result: FAILED with {type(e).__name__}: {e}")

if __name__ == "__main__":
    test_zenith()
    test_poles()
