import pytest
import math
from src.physics_engine.panel_feedback import calculate_energy

def test_energy_calculation():
    # 1000 W/m2, full sun, ideal temp
    energy_fixed, energy_tracker, energy_ai = calculate_energy(
        dni=1000.0,
        temp_c=25.0,
        aqi=20,
        shadow_factor=0.0,
        sun_alt=45.0,
        sun_az=180.0,
        ai_action={"tilt_bias": 0, "azimuth_bias": 0, "mode": "tracking"}
    )
    
    assert energy_tracker > energy_fixed # Tracker points directly at sun
    assert energy_ai == pytest.approx(energy_tracker) # AI with 0 bias equals perfect tracker
    
    # Test shading
    e_fix_shaded, _, _ = calculate_energy(1000.0, 25.0, 20, 1.0, 45.0, 180.0, {"mode": "tracking"})
    assert e_fix_shaded < energy_fixed * 0.3 # Significant drop when shaded

def test_modes_and_bias():
    # Stow mode: Tilt should be 0
    _, _, energy_stow = calculate_energy(1000.0, 25.0, 20, 0.0, 45.0, 180.0, {"mode": "stow"})
    expected_stow_inc = math.sin(math.radians(45.0)) # get_incident_angle(45, 180, 0, 180) = sin(45)*cos(0) + cos(45)*sin(0) = sin(45)
    # hardware_efficiency = 0.2 * (1 + 0) * (1 - (20/500)*0.2) = 0.2 * 0.992 = 0.1984
    # max_power = 1000 * 2.0 * 0.1984 = 396.8
    # energy_stow = 396.8 * sin(45) = 396.8 * 0.7071 = 280.58
    assert energy_stow == pytest.approx(396.8 * math.sin(math.radians(45.0)))

    # Bias: Positive tilt bias should decrease energy if already perfect
    _, energy_tracker, energy_biased = calculate_energy(1000.0, 25.0, 20, 0.0, 45.0, 180.0, {"tilt_bias": 10, "mode": "tracking"})
    assert energy_biased < energy_tracker

    # Diffuse mode when shaded
    _, energy_tracker_shaded, energy_diffuse_shaded = calculate_energy(1000.0, 25.0, 20, 1.0, 45.0, 180.0, {"mode": "diffuse"})
    # energy_tracker_shaded uses effective_dni = 1000 * (1 - 0.8) = 200
    # energy_diffuse_shaded uses effective_dni_diffuse = 1000 * 0.3 = 300
    # inc_ai for diffuse is sin(45) approx 0.707
    # 200 * 1.0 = 200 vs 300 * 0.707 = 212.1
    assert energy_diffuse_shaded > energy_tracker_shaded

