export type GeoPoint = {
  lat: number;
  lon: number;
  /** What the user typed, kept as the display label regardless of source. */
  name: string;
  source: "nominatim" | "offline";
};

/** Common Thai destinations, so the map still works without internet access to Nominatim. */
const CITY_TABLE: Array<{ key: string; lat: number; lon: number }> = [
  { key: "bangkok", lat: 13.7563, lon: 100.5018 },
  { key: "กรุงเทพ", lat: 13.7563, lon: 100.5018 },
  { key: "chiang mai", lat: 18.7883, lon: 98.9853 },
  { key: "เชียงใหม่", lat: 18.7883, lon: 98.9853 },
  { key: "chiang rai", lat: 19.9105, lon: 99.8406 },
  { key: "เชียงราย", lat: 19.9105, lon: 99.8406 },
  { key: "phuket", lat: 7.8804, lon: 98.3923 },
  { key: "ภูเก็ต", lat: 7.8804, lon: 98.3923 },
  { key: "pattaya", lat: 12.9236, lon: 100.8825 },
  { key: "พัทยา", lat: 12.9236, lon: 100.8825 },
  { key: "krabi", lat: 8.0863, lon: 98.9063 },
  { key: "กระบี่", lat: 8.0863, lon: 98.9063 },
  { key: "khon kaen", lat: 16.4419, lon: 102.836 },
  { key: "ขอนแก่น", lat: 16.4419, lon: 102.836 },
  { key: "hat yai", lat: 7.0086, lon: 100.4747 },
  { key: "หาดใหญ่", lat: 7.0086, lon: 100.4747 },
  { key: "ayutthaya", lat: 14.3532, lon: 100.5488 },
  { key: "อยุธยา", lat: 14.3532, lon: 100.5488 },
  { key: "nakhon ratchasima", lat: 14.9799, lon: 102.0978 },
  { key: "โคราช", lat: 14.9799, lon: 102.0978 },
  { key: "surat thani", lat: 9.1382, lon: 99.3215 },
  { key: "สุราษฎร์", lat: 9.1382, lon: 99.3215 },
  { key: "udon thani", lat: 17.4138, lon: 102.787 },
  { key: "อุดรธานี", lat: 17.4138, lon: 102.787 },
  { key: "rayong", lat: 12.6813, lon: 101.278 },
  { key: "ระยอง", lat: 12.6813, lon: 101.278 },
  { key: "hua hin", lat: 12.5684, lon: 99.9577 },
  { key: "หัวหิน", lat: 12.5684, lon: 99.9577 },
  { key: "kanchanaburi", lat: 14.0227, lon: 99.5328 },
  { key: "กาญจนบุรี", lat: 14.0227, lon: 99.5328 },
  { key: "mae hong son", lat: 19.3020, lon: 97.9654 },
  { key: "แม่ฮ่องสอน", lat: 19.3020, lon: 97.9654 },
  { key: "sukhothai", lat: 17.0068, lon: 99.8265 },
  { key: "สุโขทัย", lat: 17.0068, lon: 99.8265 },
  { key: "koh samui", lat: 9.512, lon: 100.0136 },
  { key: "เกาะสมุย", lat: 9.512, lon: 100.0136 },
  { key: "pai", lat: 19.3583, lon: 98.4392 },
  { key: "ปาย", lat: 19.3583, lon: 98.4392 },
];

/** Nominatim usage policy asks for at most ~1 request/second from a client. */
let lastNominatimCall = 0;

async function nominatim(query: string, signal?: AbortSignal): Promise<GeoPoint | null> {
  const wait = Math.max(0, 1100 - (Date.now() - lastNominatimCall));
  if (wait > 0) await new Promise((resolve) => setTimeout(resolve, wait));
  lastNominatimCall = Date.now();

  const url = new URL("https://nominatim.openstreetmap.org/search");
  url.searchParams.set("q", query);
  url.searchParams.set("format", "jsonv2");
  url.searchParams.set("limit", "1");
  url.searchParams.set("accept-language", "th");

  const response = await fetch(url.toString(), {
    signal,
    headers: { Accept: "application/json" },
  });
  if (!response.ok) return null;
  const hits = (await response.json()) as Array<{ lat: string; lon: string }>;
  if (!Array.isArray(hits) || hits.length === 0) return null;
  return { lat: parseFloat(hits[0].lat), lon: parseFloat(hits[0].lon), name: query, source: "nominatim" };
}

function offlineLookup(query: string): GeoPoint {
  const normalized = query.trim().toLowerCase();
  const hit = CITY_TABLE.find((c) => normalized.includes(c.key) || c.key.includes(normalized));
  if (hit) return { lat: hit.lat, lon: hit.lon, name: query, source: "offline" };

  // Deterministic pseudo-position inside Thailand's bounding box, so an unknown
  // place name still lands somewhere sensible and stays put between renders.
  let hash = 0;
  for (let i = 0; i < normalized.length; i++) hash = (hash * 31 + normalized.charCodeAt(i)) >>> 0;
  const lat = 7 + ((hash % 1000) / 1000) * (20 - 7);
  const lon = 98 + (((hash >> 8) % 1000) / 1000) * (105 - 98);
  return { lat, lon, name: query, source: "offline" };
}

/** Resolve a free-text place name to coordinates, preferring live geocoding. */
export async function geocode(query: string, signal?: AbortSignal): Promise<GeoPoint> {
  try {
    const hit = await nominatim(query, signal);
    if (hit) return hit;
  } catch {
    // network error, CORS, or the service is unreachable — fall through
  }
  return offlineLookup(query);
}
