import type { JobAccepted, RecommendationResponse, TravelRequest } from "@/lib/types";
import { isJobAccepted } from "@/lib/types";
import { apiFetch, BASE_URL } from "./client";
import { ApiError } from "./problem";

export * from "./client";
export * from "./problem";
export * from "./service-status";

/**
 * Same call surface as the old lib/api.ts, so existing imports keep working.
 * What changed underneath: every request now carries Authorization,
 * Accept-Language and (on POST) Idempotency-Key, and failures arrive as
 * ApiError carrying the backend's RFC 9457 problem body instead of raw text.
 */
export const api = {
  createRecommendation: (
    payload: TravelRequest,
    options?: { idempotencyKey?: string; mode?: "auto" | "sync" | "async"; signal?: AbortSignal },
  ) =>
    apiFetch<RecommendationResponse | JobAccepted>("/v1/travel/recommendations", {
      method: "POST",
      body: payload,
      idempotencyKey: options?.idempotencyKey,
      searchParams: { mode: options?.mode ?? "auto" },
      signal: options?.signal,
    }),

  getRecommendation: (id: string, signal?: AbortSignal) =>
    apiFetch<RecommendationResponse>(`/v1/travel/recommendations/${id}`, { signal }),

  getServiceStatus: (signal?: AbortSignal) =>
    apiFetch<{ services: Array<{ name: string; status: string }> }>(
      "/v1/service-status",
      { signal },
    ),

  getAdminJobs: (signal?: AbortSignal) =>
    apiFetch<{ items: unknown[] }>("/v1/admin/jobs", { signal }),

  getFeedbackReviews: (signal?: AbortSignal) =>
    apiFetch<{ items: unknown[] }>("/v1/admin/feedback/reviews", { signal }),
};

/**
 * SSE sequence for a 202 JobAccepted: POST /v1/jobs/:id/stream-ticket (needs the
 * normal JWT — EventSource cannot send headers), then open
 * `GET /v1/jobs/:id/events?ticket=...` and close the stream on completed/failed/cancelled.
 */
export async function followRecommendationJob(
  accepted: JobAccepted,
  options?: { onProgress?: (message: string, stage: string) => void; timeoutMs?: number },
): Promise<RecommendationResponse> {
  const ticket = await apiFetch<{ ticket: string; expires_in: number }>(
    `/v1/jobs/${accepted.job_id}/stream-ticket`,
    { method: "POST" },
  );

  return new Promise((resolve, reject) => {
    const url = `${BASE_URL}/v1/jobs/${accepted.job_id}/events?ticket=${encodeURIComponent(ticket.ticket)}`;
    const source = new EventSource(url);
    let settled = false;

    const finish = (fn: () => void) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      source.close();
      fn();
    };

    const timer = setTimeout(
      () => finish(() => reject(new ApiError(408, { code: "job_timeout", title: "หมดเวลารอผลลัพธ์" }))),
      options?.timeoutMs ?? 45_000,
    );

    source.addEventListener("progress", (event) => {
      try {
        const data = JSON.parse((event as MessageEvent).data) as { message?: string; stage?: string };
        if (data.message) options?.onProgress?.(data.message, data.stage ?? "");
      } catch {
        // ignore malformed progress frames
      }
    });

    source.addEventListener("completed", () => {
      finish(() => {
        api.getRecommendation(accepted.recommendation_id).then(resolve, reject);
      });
    });

    source.addEventListener("failed", (event) => {
      finish(() => {
        try {
          const data = JSON.parse((event as MessageEvent).data) as {
            error?: { code?: string; message?: string };
          };
          reject(
            new ApiError(502, {
              code: data.error?.code ?? "job_failed",
              title: data.error?.message ?? "งานล้มเหลว",
            }),
          );
        } catch {
          reject(new ApiError(502, { code: "job_failed", title: "งานล้มเหลว" }));
        }
      });
    });

    source.addEventListener("cancelled", () => {
      finish(() => reject(new ApiError(499, { code: "cancelled", title: "ยกเลิกคำขอแล้ว" })));
    });

    source.onerror = () => {
      // EventSource retries connection drops on its own; only the timeout above
      // treats a stuck stream as a hard failure.
    };
  });
}

/** Ask for a recommendation and resolve once it is ready, following the SSE hop if needed. */
export async function requestRecommendation(
  payload: TravelRequest,
  options?: {
    idempotencyKey?: string;
    onProgress?: (message: string, stage: string) => void;
    signal?: AbortSignal;
  },
): Promise<RecommendationResponse> {
  const result = await api.createRecommendation(payload, {
    idempotencyKey: options?.idempotencyKey,
    signal: options?.signal,
  });
  if (isJobAccepted(result)) {
    return followRecommendationJob(result, { onProgress: options?.onProgress });
  }
  return result;
}
