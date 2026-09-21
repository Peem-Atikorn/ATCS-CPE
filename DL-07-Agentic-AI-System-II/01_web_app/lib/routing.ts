export type RoutePoint = [number, number]; // [lon, lat], matches GeoJSON order

export type DrivingRoute = {
  coordinates: RoutePoint[];
  distanceKm: number;
  durationMinutes: number;
};

const OSRM_DRIVING_BASE = "https://router.project-osrm.org/route/v1/driving";

/**
 * Real road-following geometry from OSRM's public demo server (driving profile).
 * Free, no API key, but a shared demo instance — fine for this project's scope, not
 * for production traffic. Used because the backend's mock Agent (stand-in for
 * Module 03) always returns the same canned train-route geometry no matter what
 * travel mode or destination was actually requested, which drew a line straight
 * across the sea for a "drive" request to somewhere like Krabi.
 */
export async function fetchDrivingRoute(
  origin: { lat: number; lon: number },
  destination: { lat: number; lon: number },
  signal?: AbortSignal,
): Promise<DrivingRoute | null> {
  try {
    const url = `${OSRM_DRIVING_BASE}/${origin.lon},${origin.lat};${destination.lon},${destination.lat}?overview=full&geometries=geojson`;
    const response = await fetch(url, { signal });
    if (!response.ok) return null;
    const data = (await response.json()) as {
      code?: string;
      routes?: Array<{
        geometry?: { coordinates?: RoutePoint[] };
        distance?: number;
        duration?: number;
      }>;
    };
    if (data.code !== "Ok") return null;
    const route = data.routes?.[0];
    const coordinates = route?.geometry?.coordinates;
    if (!coordinates || coordinates.length < 2) return null;
    return {
      coordinates,
      distanceKm: route?.distance != null ? route.distance / 1000 : 0,
      durationMinutes: route?.duration != null ? route.duration / 60 : 0,
    };
  } catch {
    // Network error, CORS, or the demo server is throttling us — caller falls back.
    return null;
  }
}
