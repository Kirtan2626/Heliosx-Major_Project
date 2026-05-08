import logging
import math

try:
    import torch
    import numpy as np
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

logger = logging.getLogger(__name__)

class HeliosXPolicy:
    def __init__(self, model_path: str = "dqn_final_helios_x_v2_regime_conditioned.pt"):
        self.use_fallback = not TORCH_AVAILABLE
        self.model = None
        
        if TORCH_AVAILABLE:
            try:
                # Attempt to load as a TorchScript or standard PyTorch model
                self.model = torch.load(model_path, map_location=torch.device('cpu'))
                if hasattr(self.model, "eval"):
                    self.model.eval()
            except Exception as e:
                logger.error(f"Failed to load model from {model_path}: {e}. Using fallback.")
                self.use_fallback = True

    def get_action(self, raw_state: dict) -> dict:
        if self.use_fallback:
            return self._fallback_policy(raw_state)
        return self._inference(raw_state)
        
    def _fallback_policy(self, raw_state: dict) -> dict:
        # Deterministic fallback: Identity tracking
        return {"action_id": 3, "tilt_bias": 0, "azimuth_bias": 0, "mode": "identity"}
        
    def _inference(self, raw_state: dict) -> dict:
        raise NotImplementedError()
