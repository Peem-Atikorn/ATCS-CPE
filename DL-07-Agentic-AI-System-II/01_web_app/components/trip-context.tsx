"use client";
import { createContext, useCallback, useContext, useRef, useState } from "react";
import { requestRecommendation } from "@/lib/api";
import { toUserMessage } from "@/lib/api/problem";
import { geocode, type GeoPoint } from "@/lib/geocode";
import { buildMockRecommendation } from "@/lib/mock-recommendation";
import { fetchDrivingRoute, type DrivingRoute } from "@/lib/routing";
import type { RecommendationResponse, TravelMode } from "@/lib/types";

/** Travel modes OSRM's public driving profile can approximate with a real road route. */
const ROAD_MODES = new Set<TravelMode>(["CAR", "BUS"]);

export type TripStatus = "idle" | "geocoding" | "submitting" | "streaming" | "success" | "error";

export type TripFormInput = {
  origin: string;
  destination: string;
  date: string;
  mode: TravelMode;
  note?: string;
};

type TripContextValue = {
  status: TripStatus;
  originPoint: GeoPoint | null;
  destinationPoint: GeoPoint | null;
  recommendation: RecommendationResponse | null;
  usingMock: boolean;
  progressMessage: string | null;
  errorMessage: string | null;
  /** Real road-following geometry for CAR/BUS, fetched independently of the recommendation. */
  roadRoute: DrivingRoute | null;
  submit: (input: TripFormInput) => Promise<void>;
};

const TripContext = createContext<TripContextValue | null>(null);

export function TripProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<TripStatus>("idle");
  const [originPoint, setOriginPoint] = useState<GeoPoint | null>(null);
  const [destinationPoint, setDestinationPoint] = useState<GeoPoint | null>(null);
  const [recommendation, setRecommendation] = useState<RecommendationResponse | null>(null);
  const [usingMock, setUsingMock] = useState(false);
  const [progressMessage, setProgressMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [roadRoute, setRoadRoute] = useState<DrivingRoute | null>(null);
  const requestSeq = useRef(0);

  const submit = useCallback(async (input: TripFormInput) => {
    const seq = ++requestSeq.current;
    const isStale = () => seq !== requestSeq.current;

    setStatus("geocoding");
    setErrorMessage(null);
    setProgressMessage(null);
    setRoadRoute(null);

    let origin: GeoPoint;
    let destination: GeoPoint;
    try {
      [origin, destination] = await Promise.all([geocode(input.origin), geocode(input.destination)]);
    } catch {
      // geocode() already falls back internally; this only triggers on a thrown bug.
      if (isStale()) return;
      setStatus("error");
      setErrorMessage("ไม่สามารถระบุตำแหน่งจากชื่อสถานที่ได้");
      return;
    }
    if (isStale()) return;
    setOriginPoint(origin);
    setDestinationPoint(destination);
    setStatus("submitting");

    if (ROAD_MODES.has(input.mode)) {
      fetchDrivingRoute(origin, destination).then((route) => {
        if (!isStale()) setRoadRoute(route);
      });
    }

    const departureTime = `${input.date}T08:00:00+07:00`;

    try {
      const result = await requestRecommendation(
        {
          origin: { name: origin.name, lat: origin.lat, lon: origin.lon },
          destination: { name: destination.name, lat: destination.lat, lon: destination.lon },
          departure_time: departureTime,
          timezone: "Asia/Bangkok",
          preferences: { travel_modes: [input.mode] },
          question: input.note || null,
        },
        {
          onProgress: (message) => {
            if (!isStale()) {
              setStatus("streaming");
              setProgressMessage(message);
            }
          },
        },
      );
      if (isStale()) return;
      setRecommendation(result);
      setUsingMock(false);
      setStatus("success");
    } catch (err) {
      if (isStale()) return;
      setErrorMessage(toUserMessage(err));
      setRecommendation(
        buildMockRecommendation({ origin, destination, mode: input.mode, departureTime }),
      );
      setUsingMock(true);
      setStatus("success");
    }
  }, []);

  return (
    <TripContext.Provider
      value={{
        status,
        originPoint,
        destinationPoint,
        recommendation,
        usingMock,
        progressMessage,
        errorMessage,
        roadRoute,
        submit,
      }}
    >
      {children}
    </TripContext.Provider>
  );
}

export function useTrip(): TripContextValue {
  const ctx = useContext(TripContext);
  if (!ctx) throw new Error("useTrip must be used within TripProvider");
  return ctx;
}
