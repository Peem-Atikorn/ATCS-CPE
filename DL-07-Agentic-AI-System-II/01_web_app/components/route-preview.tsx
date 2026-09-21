"use client";
import { LoaderCircle, MapPinned } from "lucide-react";
import { TripMap } from "@/components/ui/trip-map";
import { useTrip } from "@/components/trip-context";

export function RoutePreview() {
  const { status, originPoint, destinationPoint, recommendation } = useTrip();
  const route = recommendation?.routes?.primary;
  const coordinates =
    route?.geometry && (route.geometry as { type?: string }).type === "LineString"
      ? ((route.geometry as { coordinates?: unknown }).coordinates as Array<[number, number]>)
      : null;

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
            {route?.distance_km ? ` · ${Math.round(route.distance_km)} km` : ""}
          </p>
        </div>
      )}
    </div>
  );
}
