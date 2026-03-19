import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function sentimentColor(score: number | null | undefined): string {
  if (score == null) return "#94a3b8";
  if (score >= 0.1) return "#22c55e";
  if (score <= -0.1) return "#ef4444";
  return "#f59e0b";
}

export function sentimentLabel(score: number | null | undefined): string {
  if (score == null) return "Unknown";
  if (score >= 0.1) return "Positive";
  if (score <= -0.1) return "Negative";
  return "Neutral";
}

export function alignmentColor(score: number | null): string {
  if (score == null) return "#94a3b8";
  if (score >= 7) return "#22c55e";
  if (score >= 4) return "#f59e0b";
  return "#ef4444";
}

export function riskColor(level: string | null): string {
  switch (level) {
    case "Low":      return "#22c55e";
    case "Medium":   return "#f59e0b";
    case "High":     return "#f97316";
    case "Critical": return "#ef4444";
    default:         return "#94a3b8";
  }
}

export const ESG_COLORS: Record<string, string> = {
  Environmental: "#22c55e",
  Social:        "#3b82f6",
  Governance:    "#8b5cf6",
  "Cross-ESG":   "#f59e0b",
  Unknown:       "#94a3b8",
};

export const SOURCE_COLORS: Record<string, string> = {
  official:  "#3b82f6",
  news:      "#f59e0b",
  ngo:       "#8b5cf6",
  social:    "#ec4899",
  benchmark: "#14b8a6",
  rss:       "#f97316",
};

export function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return "—";
  try {
    return new Date(dateStr).toLocaleDateString("en-GB", {
      day: "2-digit", month: "short", year: "numeric",
    });
  } catch {
    return dateStr;
  }
}
