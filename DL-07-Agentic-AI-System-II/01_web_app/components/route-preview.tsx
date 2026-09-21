"use client";
import { LoaderCircle, MapPinned } from "lucide-react";
import { TripMap } from "@/components/ui/trip-map";
import { useTrip } from "@/components/trip-context";
import { haversineKm } from "@/lib/geocode";

/**
 * The backend's mock Agent (a stand-in for Module 03) returns the same canned
 * "Bangkok → Chiang Mai" route geometry for every request regardless of what
 * origin/destination was actually asked for. Trust the geometry only when its
 * endpoints are close to the markers we actually placed — otherwise a request
 * like Bangkok → Krabi would draw a line running off toward Chiang Mai instead.
 */
const ROUTE_ENDPOINT_TOLERANCE_KM = 150;

export function RoutePreview() {
  const { status, originPoint, destinationPoint, recommendation, roadRoute } = useTrip();
  const route = recommendation?.routes?.primary;
  const rawCoordinates =
    route?.geometry && (route.geometry as { type?: string }).type === "LineString"
      ? ((route.geometry as { coordinates?: unknown }).coordinates as Array<[number, number]>)
      : null;

  const routeMatchesMarkers =
    !!rawCoordinates &&
    rawCoordinates.length >= 2 &&
    !!originPoint &&
    !!destinationPoint &&
    haversineKm(originPoint, { lat: rawCoordinates[0][1], lon: rawCoordinates[0][0] }) <=
      ROUTE_ENDPOINT_TOLERANCE_KM &&
    haversineKm(destinationPoint, {
      lat: rawCoordinates[rawCoordinates.length - 1][1],
      lon: rawCoordinates[rawCoordinates.length - 1][0],
    }) <= ROUTE_ENDPOINT_TOLERANCE_KM;

  // Prefer a real road route (OSRM) over the backend's geometry — the mock Agent
  // returns the same canned train route no matter which mode was requested.
  const usingRoadRoute = !!roadRoute;
  const coordinates = roadRoute?.coordinates ?? (routeMatchesMarkers ? rawCoordinates : null);
  const distanceKm = roadRoute
    ? Math.round(roadRoute.distanceKm)
    : routeMatchesMarkers && route?.distance_km != null
      ? Math.round(route.distance_km)
      : originPoint && destinationPoint
        ? Math.round(haversineKm(originPoint, destinationPoint))
        : null;
  const showApproximateWarning = !usingRoadRoute && !routeMatchesMarkers && !!recommendation;

  return (
    <div className="relative min-h-[430px] overflow-hidden rounded-2xl shadow-float">
      <TripMap
        origin={originPoint}
        destination={destinationPoint}
        routeCoordinates={coordinates}
        riskLevel={recommendation?.risk?.level ?? null}
      />

      {!originPoint && !destinationPoint && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center bg-[#eef6fb]/70 text-center text-sm text-slate-500">
          <p className="max-w-xs px-6">กรอกต้นทางและปลายทางด้านบนแล้วกด &ldquo;ตรวจเส้นทางอย่างมั่นใจ&rdquo; เพื่อดูหมุดบนแผนที่</p>
        </div>
      )}

      {(status === "geocoding" || status === "submitting" || status === "streaming") && (
        <div className="absolute inset-x-5 top-5 flex items-center gap-2 rounded-xl bg-white/95 px-4 py-3 text-xs font-bold text-ink shadow-lg backdrop-blur">
          <LoaderCircle className="animate-spin text-aqua" size={16} />
          {status === "geocoding" ? "กำลังค้นหาตำแหน่งบนแผนที่…" : "กำลังประเมินความเสี่ยง…"}
        </div>
      )}

      {originPoint && destinationPoint && (
        <div className="absolute bottom-5 left-5 rounded-xl bg-white/95 p-4 text-xs text-ink shadow-lg backdrop-blur">
          <div className="flex items-center gap-2 font-bold">
            <MapPinned size={16} className="text-aqua" /> Route preview
          </div>
          <p className="mt-1 text-slate-500">
            {originPoint.name} → {destinationPoint.name}
            {distanceKm != null ? ` · ${distanceKm} km` : ""}
          </p>
          {showApproximateWarning && (
            <p className="mt-1 text-[11px] text-amber-600">
              เส้นทางเป็นเส้นประมาณระยะทาง ยังไม่ใช่เส้นทางถนนจริง
            </p>
          )}
        </div>
      )}
    </div>
  );
}
