import math

# Baseline climate clusters from the 6 training cities context
# Suppose the training set covers specific extremes:
# Hot-Dry, Hot-Humid, Coastal, High-Wind, Cloudy/Monsoon, High-Altitude
CLIMATE_CLUSTERS = {
    "hot_dry": {"temp": 35.0, "humidity": 20.0, "wind": 4.0, "cloud": 0.1, "irradiance_class": 0.9},
    "hot_humid": {"temp": 32.0, "humidity": 80.0, "wind": 3.0, "cloud": 0.4, "irradiance_class": 0.7},
    "coastal": {"temp": 25.0, "humidity": 70.0, "wind": 6.0, "cloud": 0.5, "irradiance_class": 0.6},
    "high_wind": {"temp": 20.0, "humidity": 40.0, "wind": 10.0, "cloud": 0.3, "irradiance_class": 0.8},
    "cloudy": {"temp": 15.0, "humidity": 60.0, "wind": 5.0, "cloud": 0.8, "irradiance_class": 0.4},
    "high_altitude": {"temp": 10.0, "humidity": 30.0, "wind": 5.0, "cloud": 0.2, "irradiance_class": 0.95},
    "mixed": {"temp": 22.0, "humidity": 50.0, "wind": 4.0, "cloud": 0.4, "irradiance_class": 0.7}
}

def classify_climate(temp: float, humidity: float, wind: float, cloud: float) -> str:
    """
    Classifies a new location into a climate cluster based on real-time/historical Euclidean distance.
    Used for Zero-Shot Generalization transfer learning.
    """
    # Simple irradiance proxy
    irradiance_proxy = 1.0 - (cloud * 0.7)
    
    best_cluster = "mixed"
    min_dist = float('inf')
    
    for cluster_name, features in CLIMATE_CLUSTERS.items():
        # Weighted euclidean distance
        dist = math.sqrt(
            0.4 * ((temp - features["temp"]) / 40.0)**2 + 
            0.2 * ((humidity - features["humidity"]) / 100.0)**2 +
            0.1 * ((wind - features["wind"]) / 15.0)**2 +
            0.3 * (cloud - features["cloud"])**2
        )
        
        if dist < min_dist:
            min_dist = dist
            best_cluster = cluster_name
            
    return best_cluster

def get_climate_risk_profile(cluster: str):
    """
    Returns baseline physical risk thresholds and maintenance assumptions 
    for the identified climate cluster.
    """
    profiles = {
        "hot_dry": {"thermal_risk": "high", "soiling_risk": "high", "corrosion_risk": "low", "q_baseline_mode": "diffuse_during_dust"},
        "hot_humid": {"thermal_risk": "high", "soiling_risk": "medium", "corrosion_risk": "high", "q_baseline_mode": "standard_tracking"},
        "coastal": {"thermal_risk": "medium", "soiling_risk": "low", "corrosion_risk": "high", "q_baseline_mode": "stow_on_high_wind"},
        "high_wind": {"thermal_risk": "low", "soiling_risk": "low", "corrosion_risk": "low", "q_baseline_mode": "stow_on_high_wind"},
        "cloudy": {"thermal_risk": "low", "soiling_risk": "low", "corrosion_risk": "medium", "q_baseline_mode": "diffuse"},
        "high_altitude": {"thermal_risk": "low", "soiling_risk": "low", "corrosion_risk": "low", "q_baseline_mode": "standard_tracking"},
        "mixed": {"thermal_risk": "medium", "soiling_risk": "medium", "corrosion_risk": "medium", "q_baseline_mode": "standard_tracking"}
    }
    return profiles.get(cluster, profiles["mixed"])
