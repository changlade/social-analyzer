import { cn } from "../lib/utils";

interface KPICardProps {
  label: string;
  value: string | number;
  sub?: string;
  accent?: string;
  className?: string;
}

export default function KPICard({ label, value, sub, accent, className }: KPICardProps) {
  return (
    <div className={cn("bg-slate-900 rounded-xl p-5 border border-slate-800", className)}>
      <p className="text-xs font-medium text-slate-400 uppercase tracking-wide">{label}</p>
      <p
        className="mt-1.5 text-3xl font-bold"
        style={accent ? { color: accent } : undefined}
      >
        {value}
      </p>
      {sub && <p className="mt-1 text-xs text-slate-500">{sub}</p>}
    </div>
  );
}
