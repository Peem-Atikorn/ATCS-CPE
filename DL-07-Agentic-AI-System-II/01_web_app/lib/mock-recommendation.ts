import { haversineKm, type GeoPoint } from "@/lib/geocode";
import type {
  EmergencyInstructions,
  RecommendationResponse,
  RecommendationType,
  RiskLevel,
  TravelMode,
} from "@/lib/types";

/**
 * Client-side stand-in for `POST /v1/travel/recommendations`, used only when the real
 * API cannot be reached. Shaped exactly like RecommendationResponse so the dashboard
 * and map never need to know whether a result is real or demo data.
 */
export function buildMockRecommendation(input: {
  origin: GeoPoint;
  destination: GeoPoint;
  mode: TravelMode;
  departureTime: string;
}): RecommendationResponse {
  const level = pickLevel(`${input.origin.name}|${input.destination.name}`);
  const now = new Date();
  const scenario = SCENARIOS[level];
  const midLat = (input.origin.lat + input.destination.lat) / 2 + jitter(input.origin.name, 0.4);
  const midLon = (input.origin.lon + input.destination.lon) / 2 + jitter(input.destination.name, 0.4);

  return {
    recommendation_id: `demo-${Date.now()}`,
    conversation_id: null,
    request_id: `demo-request-${Date.now()}`,
    status: "completed",
    created_at: now.toISOString(),
    valid_until: new Date(now.getTime() + 60 * 60 * 1000).toISOString(),
    language: "th",
    risk: {
      level,
      score: scenario.score,
      confidence: scenario.confidence,
      factors: [
        { type: "WEATHER", level: scenario.weatherLevel, description: scenario.weather },
        { type: "TRANSPORT", level: "LOW", description: "การเดินทางส่วนใหญ่เป็นไปตามปกติ" },
      ],
    },
    recommendation: {
      type: scenario.action,
      summary: scenario.summary,
      reasons: scenario.reasons,
      suggested_departure_time: null,
    },
    routes: {
      primary: {
        route_id: "demo-primary",
        label: `${input.origin.name} → ${input.destination.name}`,
        travel_modes: [input.mode],
        distance_km: Math.round(haversineKm(input.origin, input.destination)),
        duration_minutes: Math.round((haversineKm(input.origin, input.destination) / 70) * 60),
        risk_level: level,
        geometry: {
          type: "LineString",
          coordinates: [
            [input.origin.lon, input.origin.lat],
            [midLon, midLat],
            [input.destination.lon, input.destination.lat],
          ],
        },
        legs: [],
        restrictions: [],
        tips: scenario.tips,
      },
      alternatives: [],
    },
    hazards: scenario.hazard
      ? [
          {
            hazard_id: "demo-hazard",
            type: scenario.hazard.type,
            severity: level,
            title: scenario.hazard.title,
            area: null,
            starts_at: null,
            ends_at: null,
            source_id: null,
          },
        ]
      : [],
    emergency_instructions: scenario.emergency,
    sources: [
      {
        source_id: "demo-weather",
        name: "ข้อมูลจำลอง (โหมดออฟไลน์)",
        category: "WEATHER",
        url: null,
        retrieved_at: now.toISOString(),
      },
    ],
    data_freshness: {
      overall_is_stale: false,
      items: [{ category: "WEATHER", updated_at: now.toISOString(), age_seconds: 0, is_stale: false }],
    },
    service_status: {
      weather: "not_used",
      transport: "not_used",
      disaster: "not_used",
      risk_model: "not_used",
      rag: "not_used",
      llm: "not_used",
    },
    clarification: null,
    warnings: [],
    versions: { api: "demo", agent: "offline-demo", risk_model: "offline-demo", prompt: "offline-demo" },
    disclaimer: "นี่คือข้อมูลตัวอย่างที่สร้างในเบราว์เซอร์ เนื่องจากเชื่อมต่อ API จริงไม่ได้ในขณะนี้",
    job_id: null,
    error: null,
  };
}

function pickLevel(seed: string): RiskLevel {
  let hash = 0;
  for (let i = 0; i < seed.length; i++) hash = (hash * 31 + seed.charCodeAt(i)) >>> 0;
  const bucket = hash % 10;
  if (bucket < 6) return "LOW";
  if (bucket < 9) return "MEDIUM";
  return "HIGH";
}

function jitter(seed: string, scale: number): number {
  let hash = 0;
  for (let i = 0; i < seed.length; i++) hash = (hash * 17 + seed.charCodeAt(i)) >>> 0;
  return ((hash % 1000) / 1000 - 0.5) * scale;
}

const SCENARIOS: Record<
  RiskLevel,
  {
    score: number;
    confidence: number;
    weather: string;
    weatherLevel: RiskLevel;
    action: RecommendationType;
    summary: string;
    reasons: string[];
    tips: string[];
    hazard: { type: string; title: string } | null;
    emergency: EmergencyInstructions | null;
  }
> = {
  LOW: {
    score: 0.12,
    confidence: 0.88,
    weather: "ท้องฟ้าแจ่มใส มีเมฆบางส่วน ไม่มีฝนตกตลอดเส้นทาง",
    weatherLevel: "LOW",
    action: "TRAVEL_NORMALLY",
    summary: "สภาพอากาศและเส้นทางเหมาะสมสำหรับการเดินทางตามแผน",
    reasons: ["ไม่มีประกาศเตือนภัยบนเส้นทาง", "สภาพอากาศแจ่มใสตลอดช่วงเวลาที่เดินทาง"],
    tips: ["ตรวจสอบสภาพอากาศอีกครั้งก่อนออกเดินทางจริง"],
    hazard: null,
    emergency: null,
  },
  MEDIUM: {
    score: 0.48,
    confidence: 0.8,
    weather: "ฝนตกปานกลางบางช่วง อาจมีน้ำขังบนถนนบางจุด",
    weatherLevel: "MEDIUM",
    action: "CHANGE_ROUTE",
    summary: "มีความเสี่ยงระดับปานกลางจากสภาพอากาศ แนะนำให้พิจารณาเส้นทางสำรอง",
    reasons: ["มีฝนตกปานกลางบางช่วงเวลาของการเดินทาง", "บางจุดบนเส้นทางหลักมีรายงานน้ำขัง"],
    tips: ["เผื่อเวลาการเดินทางเพิ่มขึ้น", "ติดตามสภาพอากาศระหว่างทาง"],
    hazard: { type: "WEATHER", title: "ฝนตกหนักเป็นบางช่วง" },
    emergency: null,
  },
  HIGH: {
    score: 0.86,
    confidence: 0.82,
    weather: "พายุฝนฟ้าคะนองรุนแรง มีประกาศเตือนน้ำท่วมฉับพลันในพื้นที่ปลายทาง",
    weatherLevel: "HIGH",
    action: "AVOID_TRAVEL",
    summary: "หลีกเลี่ยงการเดินทางจนกว่าประกาศเตือนภัยจะถูกยกเลิก",
    reasons: ["มีประกาศเตือนน้ำท่วมฉับพลันในพื้นที่", "การเดินทางบางช่วงถูกระงับชั่วคราว"],
    tips: ["ติดตามประกาศจากหน่วยงานทางการอย่างใกล้ชิด"],
    hazard: { type: "FLOOD", title: "ประกาศเตือนน้ำท่วมฉับพลัน" },
    emergency: {
      what_to_do_now: "หลีกเลี่ยงการเดินทางเข้าพื้นที่น้ำท่วม อยู่ในที่ปลอดภัยและพื้นที่สูง",
      safety_steps: ["หลีกเลี่ยงการเดินหรือขับรถผ่านน้ำท่วม", "ชาร์จแบตโทรศัพท์ให้พร้อมใช้งาน", "ปฏิบัติตามคำแนะนำของเจ้าหน้าที่ในพื้นที่"],
      contacts: [
        { name: "แจ้งเหตุฉุกเฉินทางการแพทย์", phone: "1669", available_hours: "24 ชั่วโมง" },
        { name: "กรมป้องกันและบรรเทาสาธารณภัย", phone: "1784", available_hours: "24 ชั่วโมง" },
      ],
      nearest_support: [],
    },
  },
};
