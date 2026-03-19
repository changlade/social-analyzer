import { cn } from "../lib/utils";

interface SentimentBadgeProps {
  label?: string;
  score?: number | null;
  className?: string;
}

export default function SentimentBadge({ label, score, className }: SentimentBadgeProps) {
  const resolved = label ?? (score != null ? (score >= 0.1 ? "positive" : score <= -0.1 ? "negative" : "neutral") : "unknown");

  const styles: Record<string, string> = {
    positive: "bg-green-500/10 text-green-400 border-green-500/20",
    negative: "bg-red-500/10 text-red-400 border-red-500/20",
    neutral:  "bg-amber-500/10 text-amber-400 border-amber-500/20",
    unknown:  "bg-slate-500/10 text-slate-400 border-slate-500/20",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border",
        styles[resolved] ?? styles.unknown,
        className
      )}
    >
      {resolved.charAt(0).toUpperCase() + resolved.slice(1)}
    </span>
  );
}
