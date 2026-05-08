import pytest
import sys
import importlib
import numpy as np
from src.heliosx_ai_policy import HeliosXPolicy

def test_fallback_initialization(monkeypatch):
    # Simulate missing torch
    monkeypatch.setitem(sys.modules, "torch", None)
    import src.heliosx_ai_policy
    importlib.reload(src.heliosx_ai_policy)
    
    policy = src.heliosx_ai_policy.HeliosXPolicy(model_path="dummy.pt")
    assert policy.use_fallback is True
    # Restore torch for other tests
    importlib.reload(src.heliosx_ai_policy)

def test_torch_load_failure_fallback():
    # Test fallback when file doesn't exist or is invalid
    policy = HeliosXPolicy(model_path="non_existent.pt")
    assert policy.use_fallback is True

def test_state_construction():
    policy = HeliosXPolicy(model_path="dqn_final_helios_x_v2_regime_conditioned.pt")
    raw_state = {
        "sun_altitude": 45.0,
        "sun_azimuth": 180.0,
        "hour_of_day": 12.0,
        "day_of_year": 180,
        "cloud_fraction": 0.2,
        "aqi": 50,
        "shadow_factor": 0.0,
        "latitude": 35.0,
        "longitude": -119.0,
        "site_altitude": 100.0,
        "dni": 800.0,
        "regime_vector": [1.0] + [0.0] * 10
    }
    state_tensor = policy._construct_state(raw_state)
    
    # Check dimensionality
    shape = tuple(state_tensor.shape)
    assert 25 in shape
    
    # Normalize to (25,) for value checking
    if len(shape) == 2:
        val_vec = state_tensor[0]
    else:
        val_vec = state_tensor
        
    # Check physical state values (first 14)
    # sin(pi) approx 0, cos(pi) approx -1
    assert abs(float(val_vec[3]) - 0.0) < 1e-5
    assert abs(float(val_vec[4]) - (-1.0)) < 1e-5
    # Check regime vector (last 11)
    assert float(val_vec[14]) == 1.0
    assert float(val_vec[15]) == 0.0

def test_action_decoding():
    policy = HeliosXPolicy(model_path="dqn_final_helios_x_v2_regime_conditioned.pt")
    
    # Test action ID 0: Tilt Bias -15
    action = policy._decode_action(0)
    assert action["tilt_bias"] == -15
    assert action["mode"] == "tracking"
    
    # Test action ID 11: Stow
    action = policy._decode_action(11)
    assert action["mode"] == "stow"
