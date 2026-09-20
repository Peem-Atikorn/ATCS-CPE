export type RiskLevel = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
export type TravelRequest = {
  origin: { name: string; latitude?: number; longitude?: number };
  destination: { name: string; latitude?: number; longitude?: number };
  departure_at: string;
  mode: "DRIVING" | "WALKING" | "TRANSIT";
  preferences?: { avoid_tolls?: boolean; avoid_highways?: boolean; note?: string };
};
export type Recommendation = {
  id: string; risk_level: RiskLevel; action: "TRAVEL_NORMALLY" | "CHANGE_ROUTE" | "DELAY_TRAVEL" | "AVOID_TRAVEL";
  score?: number; confidence?: number; summary?: string; reasons?: Array<{ title: string; detail: string; source?: string; observed_at?: string }>;
};
