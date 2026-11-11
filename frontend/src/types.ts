export type RiskLevel = "low" | "moderate" | "high" | "severe" | "no_travel";

export interface Place {
  name: string;
  lat: number;
  lon: number;
}

export interface CheckpointWeather {
  wind_mph: number;
  rain_in_hr: number;
  snow_in_hr: number;
}

export interface Checkpoint {
  mile: number;
  lat: number;
  lon: number;
  eta: string;
  risk: RiskLevel | null;
  weather: CheckpointWeather | null;
}

export interface RouteSegment {
  risk: RiskLevel | null;
  path: [number, number][];
}

export interface RoutePlan {
  id: string;
  duration_s: number;
  distance_miles: number;
  average_risk: number | null;
  miles_by_risk: Record<RiskLevel | "no_data", number>;
  segments: RouteSegment[];
  checkpoints: Checkpoint[];
}

export interface Recommendation {
  route_id: string;
  is_safe: boolean;
  is_complete: boolean;
  reason: string;
}

export interface TripPlan {
  origin: Place;
  destination: Place;
  departure_at: string;
  load_lb: number;
  interval_miles: number;
  routes: RoutePlan[];
  recommendation: Recommendation;
}

export interface TripRequest {
  origin: string;
  destination: string;
  departure_at: string;
  load_lb: number;
  interval_miles: number;
}

export interface HeatmapPoint {
  lat: number;
  lon: number;
  risk: (number | null)[];
}

export interface Heatmap {
  departure_at: string;
  hours: number;
  step_miles: number;
  points: HeatmapPoint[];
}
