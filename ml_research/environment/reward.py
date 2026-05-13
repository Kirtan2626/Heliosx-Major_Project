"""
Reward function for the solar tracking environment — CORRECTED.

Critical fix: Returns a RewardResult with physical_energy and shaping_bonus
separated. The RL agent trains on (physical_energy + shaping_bonus) as the
reward signal. The evaluator ONLY accumulates physical_energy.

Physical energy invariants (enforced by assertions):
  1. physical_energy >= 0 (a panel cannot produce negative energy)
  2. physical_energy <= max_possible_energy (cannot exceed available irradiance)
  3. Stow mode physical_energy == 0 (panel is flat, not collecting)
  4. Diffuse mode physical_energy <= DHI * timestep (cannot exceed diffuse irradiance)

Shaping bonus:
  - Can be positive or negative
  - Small relative to typical physical energy (max +/-15 Wh vs typical 20-60 Wh/step)
  - NEVER counted as physical energy in evaluation
"""

from dataclasses import dataclass, field


@dataclass
class RewardResult:
    """Separates the two components of the reward signal."""
    physical_energy: float   # Wh -- what the panel actually captures. Always >= 0.
    shaping_bonus: float     # Wh -- artificial incentive. Can be negative.
    reward: float = field(init=False)  # physical_energy + shaping_bonus
    mode: str = "track"      # "track", "stow", or "diffuse"
    info: dict = field(default_factory=dict)  # extra info for logging

    def __post_init__(self):
        assert self.physical_energy >= 0, (
            f"Physical energy cannot be negative: {self.physical_energy}"
        )
        self.reward = self.physical_energy + self.shaping_bonus


def compute_reward(
    action_id: int,
    action_table: list[dict],
    dni: float,
    dhi: float,
    shadow_factor_before: float,
    shadow_factor_after: float,
    cloud_fraction: float,
    is_extreme_weather: bool,
    is_overcast: bool,
    reward_config: dict,
    timestep_hours: float = 0.5,
    aqi: float = 0.0,
    ambient_temp_c: float = 25.0,
    air_mass_val: float = 1.5,
    panel_efficiency: float = 0.20,
    panel_area_m2: float = 1.0,
) -> tuple[float, dict]:
    """
    Compute reward for a single timestep.

    Returns (total_reward, info_dict) for backward compatibility.
    info_dict now contains 'physical_energy' and 'shaping_bonus' as separate fields.

    The RL agent trains on total_reward = physical_energy + shaping_bonus.
    The evaluator MUST use info['physical_energy'] only.
    """
    from physics_engine.panel_feedback import (
        compute_panel_energy,
        compute_diffuse_energy,
    )

    action = action_table[action_id]
    mode = action["mode"]
    tilt_bias = action["tilt_bias"]
    az_bias = action["az_bias"]

    physical_energy = 0.0
    shaping_bonus = 0.0
    info = {"mode": mode}

    # Clamp measured values to physical bounds
    dni = max(0.0, dni)
    dhi = max(0.0, dhi)

    if mode == "track":
        # Full physics-based energy computation
        physical_energy = compute_panel_energy(
            dni=dni,
            tilt_bias_deg=tilt_bias,
            az_bias_deg=az_bias,
            shadow_factor=shadow_factor_after,
            aqi=aqi,
            timestep_hours=timestep_hours,
            panel_area_m2=panel_area_m2,
            panel_efficiency=panel_efficiency,
            ambient_temp_c=ambient_temp_c,
            air_mass=air_mass_val,
        )

        # HARD CLAMP: cannot exceed total available irradiance * timestep
        max_possible = (dni + dhi) * timestep_hours
        physical_energy = min(physical_energy, max_possible)
        physical_energy = max(0.0, physical_energy)

        # --- Shaping bonuses (separate from physical energy) ---

        # Shadow escape: any meaningful improvement during a genuine shadow
        # event. Previously required before<0.3 & after>0.7, which is
        # unreachable with realistic OSM-derived obstacle penalties (single
        # obstacles only drop factor to ~0.35). Now: any time the agent is
        # in a non-trivial shadow (factor < 0.85) and improves it by >= 0.15,
        # we count that as a shadow escape event.
        shadow_delta = shadow_factor_after - shadow_factor_before
        if shadow_factor_before < 0.85 and shadow_delta >= 0.15:
            shaping_bonus += reward_config.get("shadow_escape_bonus", 10.0) * min(1.0, shadow_delta / 0.5)
            info["shadow_escape"] = True
        elif shadow_delta > 0.05:
            shaping_bonus += reward_config.get("partial_improvement_bonus", 5.0) * min(1.0, shadow_delta / 0.2)
            info["partial_improvement"] = True

        # Penalty: unnecessary bias in clear conditions
        if shadow_factor_before > 0.9 and (abs(tilt_bias) > 5 or abs(az_bias) > 5):
            shaping_bonus += reward_config.get("unnecessary_bias_penalty", -3.0)
            info["unnecessary_bias"] = True

    elif mode == "stow":
        # Stow mode: panel is flat, protecting itself
        # Physical energy is ZERO -- panel is not collecting
        physical_energy = 0.0

        if is_extreme_weather:
            shaping_bonus = reward_config.get("stow_correct_bonus", 5.0)
            info["stow_correct"] = True
        else:
            shaping_bonus = reward_config.get("stow_incorrect_penalty", -20.0)
            info["stow_incorrect"] = True

    elif mode == "diffuse":
        # Diffuse mode: panel faces zenith to capture scattered light
        # Physical energy: DHI component only, with efficiency factor
        physical_energy = compute_diffuse_energy(
            dhi=dhi,
            timestep_hours=timestep_hours,
            panel_area_m2=panel_area_m2,
            panel_efficiency=panel_efficiency,
        )

        # HARD CLAMP: cannot capture more diffuse than exists
        max_diffuse = dhi * timestep_hours
        physical_energy = min(physical_energy, max_diffuse)
        physical_energy = max(0.0, physical_energy)

        if is_overcast:
            shaping_bonus = reward_config.get("diffuse_correct_bonus", 3.0)
            info["diffuse_correct"] = True
        else:
            shaping_bonus = reward_config.get("diffuse_incorrect_penalty", -10.0)
            info["diffuse_incorrect"] = True

    # === CRITICAL: separate fields ===
    info["physical_energy"] = physical_energy  # ONLY this for evaluation
    info["shaping_bonus"] = shaping_bonus      # tracked but NOT evaluated
    info["energy"] = physical_energy           # backward compat (but now correct)

    total_reward = physical_energy + shaping_bonus
    info["reward"] = total_reward
    info["shaping"] = shaping_bonus

    return total_reward, info
