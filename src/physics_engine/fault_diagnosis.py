def classify_faults(sim_results: list) -> list:
    """
    Analyzes simulation results to identify diagnostic faults based on heuristics.
    """
    faults = []
    
    # Aggregates for daily heuristics
    total_loss = 0.0
    total_tracker = 0.0
    high_temp_count = 0
    high_aqi_count = 0
    
    for r in sim_results:
        loss = r["energy_tracker"] - r["energy_ai"]
        total_loss += max(0, loss)
        total_tracker += r["energy_tracker"]
        
        if r.get("temp_c", 0) > 50.0 and loss > (r["energy_tracker"] * 0.05):
            high_temp_count += 1
            
        if r.get("aqi", 0) > 200 and r.get("wind_speed", 5) < 2.0 and loss > (r["energy_tracker"] * 0.1):
            high_aqi_count += 1

    # Logic gates
    if high_temp_count > 4: # at least 2 hours of high temp derating
        faults.append({
            "type": "thermal_derating", 
            "severity": "medium", 
            "message": "Critical cell temperature reached. Consider active cooling."
        })
        
    if high_aqi_count > 8: # at least 4 hours of heavy soiling
        faults.append({
            "type": "dust_soiling", 
            "severity": "high", 
            "message": "High AQI and low wind detected. Panel cleaning recommended."
        })
        
    # Shading detection (simplified)
    # If loss > 30% during low sun but tracker is fine
    low_sun_shading = any(r["sun_alt"] < 20 and (r["energy_tracker"] - r["energy_ai"]) > (r["energy_tracker"] * 0.3) for r in sim_results)
    if low_sun_shading:
         faults.append({
            "type": "shading_anomaly", 
            "severity": "medium", 
            "message": "Unavoidable shadow detected at low sun altitude."
        })
        
    return faults
