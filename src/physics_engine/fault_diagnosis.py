def classify_faults(sim_results: list[dict]) -> list[dict]:
    """
    Analyzes simulation results to identify diagnostic faults based on heuristics.
    """
    faults = []
    
    # Aggregates for daily heuristics
    high_temp_count = 0
    high_aqi_count = 0
    low_sun_shading = False
    
    for r in sim_results:
        energy_tracker = r.get("energy_tracker", 0.0)
        energy_ai = r.get("energy_ai", 0.0)
        sun_alt = r.get("sun_alt", 0.0)
        
        loss = energy_tracker - energy_ai
        
        if r.get("temp_c", 0.0) > 50.0 and loss > (energy_tracker * 0.05):
            high_temp_count += 1
            
        if r.get("aqi", 0.0) > 200.0 and r.get("wind_speed", 5.0) < 2.0 and loss > (energy_tracker * 0.1):
            high_aqi_count += 1

        # Shading detection: loss > 30% during low sun
        if sun_alt < 20.0 and loss > (energy_tracker * 0.3):
            low_sun_shading = True

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
        
    if low_sun_shading:
         faults.append({
            "type": "shading_anomaly", 
            "severity": "medium", 
            "message": "Unavoidable shadow detected at low sun altitude."
        })
        
    return faults
