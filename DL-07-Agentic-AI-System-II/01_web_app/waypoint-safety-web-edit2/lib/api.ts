import type { Recommendation, TravelRequest } from "./types";
const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, { ...init, headers: { "Content-Type": "application/json", ...init?.headers } });
  if (!response.ok) throw new Error(`API ${response.status}: ${await response.text()}`);
  return response.json() as Promise<T>;
}
export const api = {
  createRecommendation: (payload: TravelRequest) => request<{ id?: string; job_id?: string; recommendation_id?: string }>("/v1/travel/recommendations", { method: "POST", body: JSON.stringify(payload) }),
  getRecommendation: (id: string) => request<Recommendation>(`/v1/travel/recommendations/${id}`),
  getServiceStatus: () => request<{ services: Array<{ name: string; status: string }> }>("/v1/service-status"),
  getAdminJobs: () => request<{ items: unknown[] }>("/v1/admin/jobs"),
  getFeedbackReviews: () => request<{ items: unknown[] }>("/v1/admin/feedback/reviews")
};
/** SSE sequence: POST /v1/jobs/:id/stream-ticket then EventSource(`/v1/jobs/:id/events?ticket=${ticket}`). Close on completed/failed. */
