import { useEffect, useState } from "react";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from "recharts";
import {
  AlertTriangle, ShieldAlert, Info, CheckCircle2, Globe, Package, TrendingDown, RefreshCcw,
} from "lucide-react";
import { cn } from "../lib/utils";
import {
  getNewsEvents,
  getNewsEventsSummary,
  getNewsEventsTimeline,
  type NewsEvent,
  type NewsEventsSummary,
  type NewsEventsTimeline,
} from "../lib/api";

// ── Severity helpers ──────────────────────────────────────────────────────────

const SEVERITY_CONFIG: Record<string, {
  label: string;
  icon: React.ElementType;
  bg: string;
  border: string;
  text: string;
  badge: string;
}> = {
  critical: {
    label: "Critical",
    icon: ShieldAlert,
    bg: "bg-red-950/60",
    border: "border-red-700",
    text: "text-red-400",
    badge: "bg-red-700 text-red-100",
  },
  high: {
    label: "High",
    icon: AlertTriangle,
    bg: "bg-orange-950/60",
    border: "border-orange-700",
    text: "text-orange-400",
    badge: "bg-orange-700 text-orange-100",
  },
  medium: {
    label: "Medium",
    icon: Info,
    bg: "bg-yellow-950/60",
    border: "border-yellow-700",
    text: "text-yellow-400",
    badge: "bg-yellow-700 text-yellow-100",
  },
  low: {
    label: "Low",
    icon: CheckCircle2,
    bg: "bg-slate-800/60",
    border: "border-slate-600",
    text: "text-slate-400",
    badge: "bg-slate-600 text-slate-100",
  },
};

const EVENT_TYPE_LABELS: Record<string, string> = {
  recall: "Product Recall",
  regulatory: "Regulatory",
  financial: "Financial Impact",
  reputational: "Reputational",
  positive: "Positive",
  other: "Other",
};

function SeverityBadge({ severity }: { severity: string }) {
  const cfg = SEVERITY_CONFIG[severity] ?? SEVERITY_CONFIG.low;
  return (
    <span className={cn("inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold", cfg.badge)}>
      <cfg.icon size={11} />
      {cfg.label}
    </span>
  );
}

function EventTypeBadge({ eventType }: { eventType: string }) {
  return (
    <span className="inline-block px-2 py-0.5 rounded text-xs font-medium bg-slate-700 text-slate-200">
      {EVENT_TYPE_LABELS[eventType] ?? eventType}
    </span>
  );
}

// ── Severity summary cards ─────────────────────────────────────────────────────

function SeverityCards({ summary }: { summary: NewsEventsSummary | null }) {
  const severities = ["critical", "high", "medium", "low"];
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {severities.map((sev) => {
        const cfg = SEVERITY_CONFIG[sev];
        const Icon = cfg.icon;
        const row = summary?.by_severity.find((r) => r.severity === sev);
        const count = row?.count ?? 0;
        return (
          <div
            key={sev}
            className={cn(
              "rounded-xl border p-4 flex flex-col gap-2",
              cfg.bg, cfg.border
            )}
          >
            <div className={cn("flex items-center gap-2", cfg.text)}>
              <Icon size={18} />
              <span className="text-sm font-semibold">{cfg.label}</span>
            </div>
            <p className="text-3xl font-bold text-white">{count}</p>
            <p className="text-xs text-slate-400">events (last 30d)</p>
          </div>
        );
      })}
    </div>
  );
}

// ── Timeline chart ─────────────────────────────────────────────────────────────

function TimelineChart({ data }: { data: NewsEventsTimeline["timeline"] }) {
  if (!data || data.length === 0) {
    return (
      <div className="flex items-center justify-center h-40 text-slate-500 text-sm">
        No timeline data yet. Run the pipeline to populate news events.
      </div>
    );
  }
  return (
    <ResponsiveContainer width="100%" height={220}>
      <AreaChart data={data} margin={{ top: 8, right: 16, left: -8, bottom: 0 }}>
        <defs>
          <linearGradient id="gradCritical" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#dc2626" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#dc2626" stopOpacity={0} />
          </linearGradient>
          <linearGradient id="gradHigh" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#ea580c" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#ea580c" stopOpacity={0} />
          </linearGradient>
          <linearGradient id="gradMedium" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#ca8a04" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#ca8a04" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
        <XAxis
          dataKey="scraped_date"
          tick={{ fill: "#94a3b8", fontSize: 11 }}
          tickFormatter={(v) => v?.slice(5) ?? v}
        />
        <YAxis tick={{ fill: "#94a3b8", fontSize: 11 }} allowDecimals={false} />
        <Tooltip
          contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8 }}
          labelStyle={{ color: "#94a3b8" }}
        />
        <Legend wrapperStyle={{ color: "#94a3b8", fontSize: 12 }} />
        <Area type="monotone" dataKey="critical" stroke="#dc2626" fill="url(#gradCritical)" strokeWidth={2} name="Critical" />
        <Area type="monotone" dataKey="high"     stroke="#ea580c" fill="url(#gradHigh)"     strokeWidth={2} name="High" />
        <Area type="monotone" dataKey="medium"   stroke="#ca8a04" fill="url(#gradMedium)"   strokeWidth={2} name="Medium" />
      </AreaChart>
    </ResponsiveContainer>
  );
}

// ── Event list item ───────────────────────────────────────────────────────────

function EventCard({ event }: { event: NewsEvent }) {
  const [expanded, setExpanded] = useState(false);
  const sev = event.severity ?? "low";
  const cfg = SEVERITY_CONFIG[sev] ?? SEVERITY_CONFIG.low;

  return (
    <div className={cn("rounded-xl border p-4 space-y-3", cfg.bg, cfg.border)}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2 mb-1.5">
            <SeverityBadge severity={sev} />
            <EventTypeBadge eventType={event.event_type ?? "other"} />
            {event.affected_region && (
              <span className="inline-flex items-center gap-1 text-xs text-slate-400">
                <Globe size={11} /> {event.affected_region}
              </span>
            )}
            {event.affected_product && (
              <span className="inline-flex items-center gap-1 text-xs text-slate-400">
                <Package size={11} /> {event.affected_product}
              </span>
            )}
          </div>
          <a
            href={event.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm font-semibold text-white hover:text-blue-400 transition-colors line-clamp-2"
          >
            {event.title}
          </a>
        </div>
        <div className="text-right text-xs text-slate-500 whitespace-nowrap">
          {event.scraped_date}
        </div>
      </div>

      {event.impact_summary && (
        <p className="text-xs text-slate-300 leading-relaxed">{event.impact_summary}</p>
      )}

      {event.recommended_response && (
        <div className={cn("rounded-lg px-3 py-2 text-xs", cfg.bg, "border", cfg.border)}>
          <span className={cn("font-semibold", cfg.text)}>Recommended response: </span>
          <span className="text-slate-300">{event.recommended_response}</span>
        </div>
      )}

      {event.financial_impact_estimate && event.financial_impact_estimate !== "null" && (
        <div className="flex items-center gap-1.5 text-xs text-slate-400">
          <TrendingDown size={12} className="text-red-400" />
          <span>Financial impact: </span>
          <span className="text-slate-200 font-medium">{event.financial_impact_estimate}</span>
        </div>
      )}

      {event.content_preview && (
        <>
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
          >
            {expanded ? "Show less" : "Show article preview"}
          </button>
          {expanded && (
            <p className="text-xs text-slate-400 leading-relaxed border-t border-slate-700 pt-2">
              {event.content_preview}
            </p>
          )}
        </>
      )}
    </div>
  );
}

// ── Filters ───────────────────────────────────────────────────────────────────

function Filters({
  severity, onSeverity,
  eventType, onEventType,
  days, onDays,
}: {
  severity: string; onSeverity: (v: string) => void;
  eventType: string; onEventType: (v: string) => void;
  days: number; onDays: (v: number) => void;
}) {
  const selectClass =
    "bg-slate-800 border border-slate-700 text-slate-200 text-sm rounded-lg px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-500";
  return (
    <div className="flex flex-wrap items-center gap-3">
      <select className={selectClass} value={severity} onChange={(e) => onSeverity(e.target.value)}>
        <option value="">All severities</option>
        <option value="critical">Critical</option>
        <option value="high">High</option>
        <option value="medium">Medium</option>
        <option value="low">Low</option>
      </select>
      <select className={selectClass} value={eventType} onChange={(e) => onEventType(e.target.value)}>
        <option value="">All types</option>
        <option value="recall">Product Recall</option>
        <option value="regulatory">Regulatory</option>
        <option value="financial">Financial</option>
        <option value="reputational">Reputational</option>
        <option value="positive">Positive</option>
      </select>
      <select className={selectClass} value={String(days)} onChange={(e) => onDays(Number(e.target.value))}>
        <option value="7">Last 7 days</option>
        <option value="14">Last 14 days</option>
        <option value="30">Last 30 days</option>
        <option value="90">Last 90 days</option>
      </select>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function NewsEvents() {
  const [events, setEvents]     = useState<NewsEvent[]>([]);
  const [summary, setSummary]   = useState<NewsEventsSummary | null>(null);
  const [timeline, setTimeline] = useState<NewsEventsTimeline["timeline"]>([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState<string | null>(null);

  const [severity,  setSeverity]  = useState("");
  const [eventType, setEventType] = useState("");
  const [days,      setDays]      = useState(30);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [eventsRes, summaryRes, timelineRes] = await Promise.allSettled([
        getNewsEvents({ severity: severity || undefined, event_type: eventType || undefined, days }),
        getNewsEventsSummary(days),
        getNewsEventsTimeline(days),
      ]);
      if (eventsRes.status === "fulfilled")   setEvents(eventsRes.value.items ?? []);
      if (summaryRes.status === "fulfilled")  setSummary(summaryRes.value);
      if (timelineRes.status === "fulfilled") setTimeline(timelineRes.value.timeline ?? []);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load news events");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [severity, eventType, days]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-xl font-bold text-white">News Events & Crisis Monitor</h1>
          <p className="text-sm text-slate-400 mt-1">
            Breaking news, product recalls, regulatory actions, and reputational events — classified by AI
          </p>
        </div>
        <button
          onClick={load}
          disabled={loading}
          className="flex items-center gap-2 px-3 py-1.5 text-sm bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg transition-colors disabled:opacity-50"
        >
          <RefreshCcw size={14} className={loading ? "animate-spin" : ""} />
          Refresh
        </button>
      </div>

      {/* Severity badge cards */}
      <SeverityCards summary={summary} />

      {/* Timeline chart */}
      <div className="bg-slate-900 rounded-xl border border-slate-800 p-5">
        <h2 className="text-sm font-semibold text-slate-300 mb-4">Event Volume by Severity (last {days} days)</h2>
        <TimelineChart data={timeline} />
      </div>

      {/* Event type breakdown */}
      {summary && summary.by_type.length > 0 && (
        <div className="bg-slate-900 rounded-xl border border-slate-800 p-5">
          <h2 className="text-sm font-semibold text-slate-300 mb-3">Event Type Breakdown</h2>
          <div className="flex flex-wrap gap-3">
            {summary.by_type.map((row) => (
              <div
                key={row.event_type}
                className="bg-slate-800 border border-slate-700 rounded-lg px-4 py-2 text-center min-w-[110px]"
              >
                <p className="text-lg font-bold text-white">{row.count}</p>
                <p className="text-xs text-slate-400">{EVENT_TYPE_LABELS[row.event_type] ?? row.event_type}</p>
                {row.avg_sentiment !== undefined && (
                  <p
                    className={cn(
                      "text-xs mt-0.5 font-medium",
                      row.avg_sentiment >= 0.1 ? "text-green-400" :
                      row.avg_sentiment <= -0.1 ? "text-red-400" : "text-slate-400"
                    )}
                  >
                    {row.avg_sentiment >= 0 ? "+" : ""}{Number(row.avg_sentiment).toFixed(2)} sentiment
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Filters + event list */}
      <div className="space-y-4">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <h2 className="text-sm font-semibold text-slate-300">
            Recent Events {events.length > 0 && <span className="text-slate-500">({events.length})</span>}
          </h2>
          <Filters
            severity={severity}   onSeverity={setSeverity}
            eventType={eventType} onEventType={setEventType}
            days={days}           onDays={setDays}
          />
        </div>

        {error && (
          <div className="bg-red-950/60 border border-red-700 rounded-xl p-4 text-sm text-red-300">
            {error}
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-20 text-slate-400 text-sm gap-2">
            <RefreshCcw size={16} className="animate-spin" />
            Loading news events…
          </div>
        ) : events.length === 0 ? (
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-10 text-center">
            <ShieldAlert size={36} className="mx-auto mb-3 text-slate-600" />
            <p className="text-slate-400 text-sm">No news events found for the selected filters.</p>
            <p className="text-slate-500 text-xs mt-1">
              Run the scraper job with the news event topics to populate this table.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {events.map((event) => (
              <EventCard key={event.article_id} event={event} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
