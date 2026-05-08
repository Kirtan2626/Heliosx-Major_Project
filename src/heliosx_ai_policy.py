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
                # weights_only=True for security to prevent arbitrary code execution
                self.model = torch.load(model_path, map_location=torch.device('cpu'), weights_only=True)
                if hasattr(self.model, "eval"):
                    self.model.eval()
            except Exception as e:
                logger.error(f"Failed to load model from {model_path}: {e}. Using fallback.")
                self.use_fallback = True

    def get_action(self, raw_state: dict) -> dict:
        if self.use_fallback:
            return self._fallback_policy(raw_state)
        return self._inference(raw_state)
        
    def _construct_state(self, raw: dict):
        # Normalization constraints based on architecture doc
        sun_alt = np.clip(raw.get("sun_altitude", 0) / 90.0, -1.0, 1.0)
        
        az_rad = math.radians(raw.get("sun_azimuth", 180.0))
        az_sin, az_cos = math.sin(az_rad), math.cos(az_rad)
        
        hour_rad = (raw.get("hour_of_day", 12.0) / 24.0) * 2 * math.pi
        h_sin, h_cos = math.sin(hour_rad), math.cos(hour_rad)
        
        day_rad = (raw.get("day_of_year", 1) / 365.0) * 2 * math.pi
        d_sin, d_cos = math.sin(day_rad), math.cos(day_rad)
        
        cloud = np.clip(raw.get("cloud_fraction", 0.0), 0.0, 1.0)
        aqi_norm = np.clip(raw.get("aqi", 0) / 500.0, 0.0, 1.0)
        shadow = np.clip(raw.get("shadow_factor", 0.0), 0.0, 1.0)
        
        lat_norm = raw.get("latitude", 0) / 90.0
        lon_norm = raw.get("longitude", 0) / 180.0
        alt_norm = np.clip(raw.get("site_altitude", 0) / 4000.0, 0.0, 1.0)
        dni_norm = np.clip(raw.get("dni", 0) / 1200.0, 0.0, 1.0)
        
        state_arr = np.array([
            sun_alt, az_sin, az_cos, h_sin, h_cos, d_sin, d_cos,
            cloud, aqi_norm, shadow, lat_norm, lon_norm, alt_norm, dni_norm
        ], dtype=np.float32)
        
        if TORCH_AVAILABLE:
            return torch.FloatTensor(state_arr).unsqueeze(0) # Shape: (1, 14)
        return state_arr

    def _fallback_policy(self, raw_state: dict) -> dict:
        # Deterministic fallback: Identity tracking
        return {"action_id": 3, "tilt_bias": 0, "azimuth_bias": 0, "mode": "identity"}
        
    def _inference(self, raw_state: dict) -> dict:
        raise NotImplementedError()
