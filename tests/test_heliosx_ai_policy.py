import pytest
import sys
from src.heliosx_ai_policy import HeliosXPolicy

def test_fallback_initialization(monkeypatch):
    # Simulate missing torch
    monkeypatch.setitem(sys.modules, "torch", None)
    policy = HeliosXPolicy(model_path="dummy.pt")
    assert policy.use_fallback is True
