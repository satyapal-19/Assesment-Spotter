import type { Heatmap, TripPlan, TripRequest } from "./types";

const API_ROOT = `${import.meta.env.VITE_API_URL ?? ""}/api`;
const MAX_PATH_POINTS = 500;

function readError(status: number, body: unknown): string {
  if (body && typeof body === "object") {
    if ("detail" in body && typeof body.detail === "string") {
      return body.detail;
    }
    const firstField = Object.values(body)[0];
    if (Array.isArray(firstField) && typeof firstField[0] === "string") {
      return firstField[0];
    }
  }
  return `The request failed (${status}). Please try again.`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_ROOT}${path}`, init);
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(readError(response.status, body));
  }
  return body as T;
}

function post<T>(path: string, payload: unknown, signal?: AbortSignal): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });
}

export function planTrip(trip: TripRequest, signal?: AbortSignal): Promise<TripPlan> {
  return post("/trips/plan", trip, signal);
}

export function fetchHeatmap(plan: TripPlan, signal?: AbortSignal): Promise<Heatmap> {
  return post(
    "/trips/heatmap",
    {
      departure_at: plan.departure_at,
      load_lb: plan.load_lb,
      paths: plan.routes.map((route) => {
        // The corridor is 50 miles wide on each side, so very long routes can skip checkpoints.
        const stride = Math.ceil(route.checkpoints.length / MAX_PATH_POINTS);
        return route.checkpoints
          .filter((_, index) => index % stride === 0)
          .map((checkpoint) => [checkpoint.lat, checkpoint.lon]);
      }),
    },
    signal,
  );
}

export async function fetchSuggestions(query: string, signal: AbortSignal): Promise<string[]> {
  const params = new URLSearchParams({ q: query });
  const { suggestions } = await request<{ suggestions: string[] }>(`/places?${params}`, { signal });
  return suggestions;
}
