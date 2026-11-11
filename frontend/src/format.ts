import type { RiskLevel } from "./types";

export const RISK_LABELS: Record<RiskLevel, string> = {
  low: "Low",
  moderate: "Moderate",
  high: "High",
  severe: "Severe",
  no_travel: "No Travel",
};

export const RISK_COLORS: Record<RiskLevel, string> = {
  low: "#2f9e6e",
  moderate: "#d9a406",
  high: "#e8702a",
  severe: "#d42a3c",
  no_travel: "#6b1d7a",
};

export const NO_DATA_COLOR = "#8a94a3";

export function riskLabel(risk: RiskLevel | null): string {
  return risk ? RISK_LABELS[risk] : "No data";
}

export function riskColor(risk: RiskLevel | null): string {
  return risk ? RISK_COLORS[risk] : NO_DATA_COLOR;
}

export function formatDuration(seconds: number): string {
  const totalMinutes = Math.round(seconds / 60);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  return hours > 0 ? `${hours} h ${minutes} min` : `${minutes} min`;
}

export function formatMiles(miles: number): string {
  return `${Math.round(miles).toLocaleString()} mi`;
}

const dateTimeFormat = new Intl.DateTimeFormat(undefined, {
  weekday: "short",
  month: "short",
  day: "numeric",
  hour: "numeric",
  minute: "2-digit",
  timeZoneName: "short",
});

export function formatDateTime(value: string | Date): string {
  return dateTimeFormat.format(new Date(value));
}

// datetime-local inputs work in local time and have no timezone suffix.
export function toLocalInputValue(date: Date): string {
  const offsetMs = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offsetMs).toISOString().slice(0, 16);
}
