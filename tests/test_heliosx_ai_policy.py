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
