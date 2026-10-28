import type { InferenceStatus } from "./types";

export function badgeClass(mode: InferenceStatus["mode"]) {
  if (mode === "live") return "badge live";
  if (mode === "offline_demo") return "badge offline";
  return "badge unconfigured";
}

export function formatNum(value: number | null | undefined, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toFixed(digits);
}

export function routeFromHash(): "plan" | "review" | "agent" {
  const hash = window.location.hash.replace(/^#\/?/, "");
  if (hash.startsWith("review")) return "review";
  if (hash.startsWith("agent")) return "agent";
  return "plan";
}
