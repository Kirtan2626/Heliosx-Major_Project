// frontend/src/types/index.ts
export interface Coordinates {
  lat: number;
  lon: number;
}

export interface SimulationResult {
  timeseries: Array<{
    time: string;
    sun_alt: number;
    sun_az: number;
    action: string;
    energy_ai: number;
    temp_c: number;
    dni: number;
    wind_speed: number;
    aqi: number;
  }>;
  daily_totals: {
    fixed_wh: number;
    tracker_wh: number;
    ai_wh: number;
  };
  commercial_impact: {
    kwh_loss: number;
    financial_loss_usd: number;
    urgency: string;
  };
  faults: Array<{
    type: string;
    severity: string;
    message: string;
  }>;
  obstacles: Array<{
    type: string;
    polygon?: Array<[number, number]>;
    point?: [number, number];
    radius?: number;
    z_height: number;
  }>;
}
