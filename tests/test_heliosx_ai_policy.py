import pytest
import sys
import importlib
import src.heliosx_ai_policy
from src.heliosx_ai_policy import HeliosXPolicy

def test_fallback_initialization(monkeypatch):
    """
    Verify that the policy correctly identifies when torch is unavailable
    and enters fallback mode.
    """
    # 1. Simulate missing torch by putting None in sys.modules
    # Use monkeypatch.setitem on sys.modules which is the standard way to mock imports
    monkeypatch.setitem(sys.modules, "torch", None)
    
    # 2. Reload the module so the module-level TORCH_AVAILABLE is re-evaluated
    # This is necessary because the module was likely imported already at the top of the file
    importlib.reload(src.heliosx_ai_policy)
    
    try:
        # Verify the constant was correctly set to False
        assert src.heliosx_ai_policy.TORCH_AVAILABLE is False
        
        # 3. Initialize the policy. It should now set use_fallback=True 
        # based on the TORCH_AVAILABLE constant.
        policy = src.heliosx_ai_policy.HeliosXPolicy(model_path="dummy.pt")
        assert policy.use_fallback is True
    finally:
        # Cleanup: Restore the module state for other tests in the session
        monkeypatch.undo()
        importlib.reload(src.heliosx_ai_policy)

def test_torch_load_failure_fallback(monkeypatch):
    """
    Verify that even if torch IS available, a failure to load the model
    file still triggers fallback mode.
    """
    # Ensure torch is "available"
    monkeypatch.setattr("src.heliosx_ai_policy.TORCH_AVAILABLE", True)
    
    # Mock torch.load to raise an exception
    import torch
    def mock_load(*args, **kwargs):
        raise RuntimeError("Simulated load failure")
    
    monkeypatch.setattr(torch, "load", mock_load)
    
    policy = HeliosXPolicy(model_path="non_existent.pt")
    assert policy.use_fallback is True

def test_state_construction():
    policy = HeliosXPolicy(model_path="dummy.pt")
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
        "dni": 800.0
    }
    state_tensor = policy._construct_state(raw_state)
    
    # Since we are running in an environment where torch might be available, 
    # we check the shape accordingly.
    if src.heliosx_ai_policy.TORCH_AVAILABLE:
        import torch
        assert isinstance(state_tensor, torch.Tensor)
        assert state_tensor.shape == (1, 14)
        # Check normalized hour sine/cosine
        assert abs(state_tensor[0, 3] - 0.0) < 1e-5 # sin(pi)
        assert abs(state_tensor[0, 4] - (-1.0)) < 1e-5 # cos(pi)
    else:
        import numpy as np
        assert isinstance(state_tensor, np.ndarray)
        assert state_tensor.shape == (14,)
        assert abs(state_tensor[3] - 0.0) < 1e-5
        assert abs(state_tensor[4] - (-1.0)) < 1e-5

def test_action_decoding():
    policy = HeliosXPolicy(model_path="dummy.pt")
    
    # Test action ID 0: Tilt Bias -15
    action = policy._decode_action(0)
    assert action["tilt_bias"] == -15
    assert action["mode"] == "tracking"
    
    # Test action ID 11: Stow
    action = policy._decode_action(11)
    assert action["mode"] == "stow"
    
    # Test action ID 12: Diffuse
    action = policy._decode_action(12)
    assert action["mode"] == "diffuse"
