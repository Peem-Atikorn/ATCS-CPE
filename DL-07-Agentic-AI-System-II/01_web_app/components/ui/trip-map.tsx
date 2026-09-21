"use client";
import "leaflet/dist/leaflet.css";
import { useEffect, useRef, useState } from "react";
import type { Map as LeafletMap, LayerGroup } from "leaflet";
import type { GeoPoint } from "@/lib/geocode";
import type { RiskLevel } from "@/lib/types";

const RISK_COLOR: Record<RiskLevel, string> = {
  LOW: "#0f766e",
  MEDIUM: "#b45309",
  HIGH: "#b91c1c",
};

function dot(color: string, letter: string) {
  return `<span style="display:flex;align-items:center;justify-content:center;width:28px;height:28px;border-radius:9999px;background:${color};color:#fff;font-size:12px;font-weight:700;border:2px solid white;box-shadow:0 2px 6px rgba(0,0,0,.35)">${letter}</span>`;
}

export function TripMap({
  origin,
  destination,
  routeCoordinates,
  riskLevel,
}: {
  origin: GeoPoint | null;
  destination: GeoPoint | null;
  routeCoordinates?: Array<[number, number]> | null;
  riskLevel: RiskLevel | null;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  const layerRef = useRef<LayerGroup | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void import("leaflet").then((leaflet) => {
      if (cancelled || !containerRef.current || mapRef.current) return;
      const L = leaflet.default;
      const map = L.map(containerRef.current, { scrollWheelZoom: false }).setView(
        [13.7563, 100.5018],
        6,
      );
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        maxZoom: 19,
      }).addTo(map);
      layerRef.current = L.layerGroup().addTo(map);
      mapRef.current = map;
      setReady(true);
    });
    return () => {
      cancelled = true;
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!ready || !mapRef.current || !layerRef.current) return;
    void import("leaflet").then((leaflet) => {
      const L = leaflet.default;
      const map = mapRef.current;
      const group = layerRef.current;
      if (!map || !group) return;
      group.clearLayers();

      const color = riskLevel ? RISK_COLOR[riskLevel] : "#0e7490";
      const points: Array<[number, number]> = [];

      if (origin) {
        L.marker([origin.lat, origin.lon], {
          icon: L.divIcon({ html: dot("#0e7490", "A"), className: "", iconSize: [28, 28] }),
        })
          .bindTooltip(`ต้นทาง: ${origin.name}`)
          .addTo(group);
        points.push([origin.lat, origin.lon]);
      }
      if (destination) {
        L.marker([destination.lat, destination.lon], {
          icon: L.divIcon({ html: dot(color, "B"), className: "", iconSize: [28, 28] }),
        })
          .bindTooltip(`ปลายทาง: ${destination.name}`)
          .addTo(group);
        points.push([destination.lat, destination.lon]);
      }

      const line = routeCoordinates?.map(([lon, lat]) => [lat, lon] as [number, number]) ??
        (points.length === 2 ? points : null);
      if (line && line.length >= 2) {
        L.polyline(line, { color, weight: 4, opacity: 0.85, dashArray: "1 8", lineCap: "round" }).addTo(
          group,
        );
      }

      if (points.length > 0) {
        map.fitBounds(L.latLngBounds(line ?? points), { padding: [36, 36], maxZoom: 12 });
      }
    });
  }, [ready, origin, destination, routeCoordinates, riskLevel]);

  return (
    <div
      ref={containerRef}
      role="img"
      aria-label={
        origin && destination
          ? `แผนที่แสดงเส้นทางจาก ${origin.name} ไปยัง ${destination.name}`
          : "แผนที่แสดงตำแหน่งต้นทางและปลายทาง"
      }
      className="h-full min-h-[360px] w-full"
    />
  );
}
