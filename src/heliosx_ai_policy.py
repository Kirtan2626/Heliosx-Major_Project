import logging
import math
import numpy as np

try:
    import torch
    import torch.nn as nn
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

logger = logging.getLogger(__name__)

if TORCH_AVAILABLE:
    class RegimeConditionedQNetwork(nn.Module):
        def __init__(self, input_dim=25, hidden_layers=[128, 128, 64], output_dim=13):
            super(RegimeConditionedQNetwork, self).__init__()
            layers = []
            curr_dim = input_dim
            for h in hidden_layers:
                layers.append(nn.Linear(curr_dim, h))
                layers.append(nn.ReLU())
                curr_dim = h
            layers.append(nn.Linear(curr_dim, output_dim))
            self.net = nn.Sequential(*layers)

        def forward(self, x):
            return self.net(x)

class HeliosXPolicy:
    def __init__(self, model_path: str = "dqn_final_helios_x_v2_regime_conditioned.pt"):
        self.use_fallback = not TORCH_AVAILABLE
        self.model = None
        
        if TORCH_AVAILABLE:
            try:
                # Load checkpoint (using weights_only=False to read the dict structure)
                checkpoint = torch.load(model_path, map_location=torch.device('cpu'), weights_only=False)
                
                # Instantiate model architecture (matching the .pt config)
                self.model = RegimeConditionedQNetwork(input_dim=25, hidden_layers=[128, 128, 64], output_dim=13)
                
                # Load state dict
                if isinstance(checkpoint, dict) and 'policy_net' in checkpoint:
                    self.model.load_state_dict(checkpoint['policy_net'])
                else:
                    state_dict = checkpoint if isinstance(checkpoint, dict) else checkpoint.state_dict()
                    self.model.load_state_dict(state_dict)
                
                self.model.eval()
                logger.info("Successfully loaded Helios-X Regime-Conditioned DQN model.")
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
        state_tensor = self._construct_state(raw_state)
        try:
            with torch.no_grad():
                q_values = self.model(state_tensor)
                action_id = torch.argmax(q_values).item()
        except Exception as e:
            logger.error(f"Inference failed: {e}. Using fallback.")
            return self._fallback_policy(raw_state)
            
        return self._decode_action(action_id)

    def _construct_state(self, raw: dict):
        # Physical State (14 Dimensions)
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
        
        physical_state = [
            sun_alt, az_sin, az_cos, h_sin, h_cos, d_sin, d_cos,
            cloud, aqi_norm, shadow, lat_norm, lon_norm, alt_norm, dni_norm
        ]

        # Climate Regime Vectors (11 Dimensions)
        # Default to New Delhi (regime 0) or zeros if not provided
        regime_vec = raw.get("regime_vector", [0.0] * 11)
        if len(regime_vec) != 11:
            regime_vec = [0.0] * 11
            
        full_state = np.array(physical_state + regime_vec, dtype=np.float32)
        
        if TORCH_AVAILABLE:
            return torch.tensor(full_state, dtype=torch.float32).unsqueeze(0)
        return full_state

    def _decode_action(self, action_id: int) -> dict:
        # Mapping based on checkpoint config
        mapping = {
            0: {"tilt_bias": -15, "azimuth_bias": 0, "mode": "tracking"},
            1: {"tilt_bias": -10, "azimuth_bias": 0, "mode": "tracking"},
            2: {"tilt_bias": -5,  "azimuth_bias": 0, "mode": "tracking"},
            3: {"tilt_bias": 0,   "azimuth_bias": 0, "mode": "tracking"}, # Perfect tracking
            4: {"tilt_bias": 5,   "azimuth_bias": 0, "mode": "tracking"},
            5: {"tilt_bias": 10,  "azimuth_bias": 0, "mode": "tracking"},
            6: {"tilt_bias": 15,  "azimuth_bias": 0, "mode": "tracking"},
            7: {"tilt_bias": 0,   "azimuth_bias": -15, "mode": "tracking"},
            8: {"tilt_bias": 0,   "azimuth_bias": 15, "mode": "tracking"},
            9: {"tilt_bias": 10,  "azimuth_bias": 10, "mode": "tracking"},
            10: {"tilt_bias": -10, "azimuth_bias": 10, "mode": "tracking"},
            11: {"tilt_bias": 0,   "azimuth_bias": 0, "mode": "stow"},
            12: {"tilt_bias": 0,   "azimuth_bias": 0, "mode": "diffuse"}
        }
        action = mapping.get(action_id, mapping[3]).copy()
        action["action_id"] = action_id
        return action
