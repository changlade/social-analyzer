import { useEffect, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  PieChart, Pie, Cell, RadarChart, PolarGrid, PolarAngleAxis, Radar,
} from "recharts";
import { format } from "date-fns";
import { AlertTriangle, TrendingUp, Newspaper, Globe } from "lucide-react";

import {
  getKPIs, getSentimentTimeline, getESGBreakdown, getDailyBrief,
  SentimentPoint, ESGBreakdown, DailyBrief,
} from "../lib/api";
import { sentimentColor, ESG_COLORS, formatDate } from "../lib/utils";
import KPICard from "../components/KPICard";

export default function Overview() {
  const [kpis, setKpis] = useState<Record<string, number | string>>({});
  const [timeline, setTimeline] = useState<SentimentPoint[]>([]);
  const [breakdown, setBreakdown] = useState<ESGBreakdown[]>([]);
  const [brief, setBrief] = useState<DailyBrief | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const since = format(new Date(Date.now() - 30 * 864e5), "yyyy-MM-dd");
    Promise.all([
      getKPIs({ date_from: since }),
      getSentimentTimeline({ granularity: "week", date_from: since }),
      getESGBreakdown({ date_from: since }),
      getDailyBrief(),
    ]).then(([k, t, b, br]) => {
      setKpis(k);
      setTimeline(t);
      setBreakdown(b);
      setBrief(br);
    }).finally(() => setLoading(false));
  }, []);

  const radarData = breakdown.map((r) => ({
    subject: r.esg_category,
    sentiment: Math.round((r.avg_sentiment + 1) * 50),   // normalise -1..1 → 0..100
    articles: r.article_count,
  }));

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full" />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">ESG Intelligence Overview</h1>
        <p className="text-slate-400 text-sm mt-1">
          Last 30 days · Updated {formatDate(kpis.latest_scrape_date as string)}
        </p>
      </div>

      {/* Daily brief banner */}
      {brief?.brief?.headline && (
        <div className="bg-blue-600/10 border border-blue-500/30 rounded-xl p-4">
          <div className="flex items-start gap-3">
            <Newspaper className="text-blue-400 mt-0.5 flex-shrink-0" size={18} />
            <div>
              <p className="text-sm font-semibold text-blue-300">Today's AI Brief</p>
              <p className="text-sm text-slate-300 mt-1">{brief.brief.headline}</p>
            </div>
          </div>
        </div>
      )}

      {/* KPI row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard
          label="Total Articles"
          value={(kpis.total_articles as number ?? 0).toLocaleString()}
          sub="Unique sources"
          accent="#3b82f6"
        />
        <KPICard
          label="Overall Sentiment"
          value={kpis.overall_sentiment != null ? `${((kpis.overall_sentiment as number) * 100).toFixed(1)}%` : "—"}
          sub="–100 → +100 scale"
          accent={sentimentColor(kpis.overall_sentiment as number)}
        />
        <KPICard
          label="Public vs Official"
          value={
            kpis.public_sentiment != null && kpis.official_sentiment != null
              ? `${Math.abs(((kpis.public_sentiment as number) - (kpis.official_sentiment as number)) * 100).toFixed(1)}% gap`
              : "—"
          }
          sub="Public is lower = perception gap"
          accent="#f59e0b"
        />
        <KPICard
          label="Critical Coverage"
          value={(kpis.critical_articles as number ?? 0).toLocaleString()}
          sub="Articles with critical stance"
          accent="#ef4444"
        />
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Sentiment timeline */}
        <div className="lg:col-span-2 bg-slate-900 rounded-xl border border-slate-800 p-5">
          <h2 className="text-sm font-semibold text-white mb-4">Sentiment Timeline (weekly)</h2>
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={timeline} margin={{ top: 4, right: 12, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis
                dataKey="period"
                tickFormatter={(v) => format(new Date(v), "MMM dd")}
                tick={{ fill: "#94a3b8", fontSize: 11 }}
              />
              <YAxis domain={[-1, 1]} tick={{ fill: "#94a3b8", fontSize: 11 }} />
              <Tooltip
                contentStyle={{ backgroundColor: "#0f172a", border: "1px solid #1e293b", borderRadius: 8 }}
                labelFormatter={(v) => format(new Date(v as string), "dd MMM yyyy")}
              />
              <Legend wrapperStyle={{ fontSize: 12, color: "#94a3b8" }} />
              <Line type="monotone" dataKey="official_sentiment" name="Official" stroke="#3b82f6" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="public_sentiment"   name="Public"  stroke="#f59e0b" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="avg_sentiment"      name="Overall" stroke="#8b5cf6" strokeWidth={1.5} strokeDasharray="4 2" dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* ESG donut */}
        <div className="bg-slate-900 rounded-xl border border-slate-800 p-5">
          <h2 className="text-sm font-semibold text-white mb-4">ESG Category Split</h2>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie
                data={breakdown}
                dataKey="article_count"
                nameKey="esg_category"
                cx="50%" cy="50%"
                innerRadius={55} outerRadius={85}
                paddingAngle={3}
              >
                {breakdown.map((entry) => (
                  <Cell key={entry.esg_category} fill={ESG_COLORS[entry.esg_category] ?? "#94a3b8"} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{ backgroundColor: "#0f172a", border: "1px solid #1e293b", borderRadius: 8 }}
              />
            </PieChart>
          </ResponsiveContainer>
          <div className="space-y-1 mt-2">
            {breakdown.map((r) => (
              <div key={r.esg_category} className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-2">
                  <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: ESG_COLORS[r.esg_category] ?? "#94a3b8" }} />
                  <span className="text-slate-300">{r.esg_category}</span>
                </div>
                <span className="text-slate-400">{r.article_count}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ESG radar + recommendations */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-slate-900 rounded-xl border border-slate-800 p-5">
          <h2 className="text-sm font-semibold text-white mb-4">ESG Sentiment Radar</h2>
          <ResponsiveContainer width="100%" height={220}>
            <RadarChart data={radarData}>
              <PolarGrid stroke="#1e293b" />
              <PolarAngleAxis dataKey="subject" tick={{ fill: "#94a3b8", fontSize: 11 }} />
              <Radar name="Sentiment (0–100)" dataKey="sentiment" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.2} />
            </RadarChart>
          </ResponsiveContainer>
        </div>

        {/* Daily brief detail */}
        {brief?.brief && (
          <div className="bg-slate-900 rounded-xl border border-slate-800 p-5 space-y-4">
            <h2 className="text-sm font-semibold text-white">Today's AI Brief</h2>
            {brief.brief.executive_brief && (
              <p className="text-sm text-slate-300 leading-relaxed">{brief.brief.executive_brief}</p>
            )}
            {brief.brief.top_risk && (
              <div className="flex gap-2 text-sm">
                <AlertTriangle size={16} className="text-red-400 flex-shrink-0 mt-0.5" />
                <p className="text-slate-300"><span className="text-red-400 font-medium">Risk: </span>{brief.brief.top_risk}</p>
              </div>
            )}
            {brief.brief.top_opportunity && (
              <div className="flex gap-2 text-sm">
                <TrendingUp size={16} className="text-green-400 flex-shrink-0 mt-0.5" />
                <p className="text-slate-300"><span className="text-green-400 font-medium">Opportunity: </span>{brief.brief.top_opportunity}</p>
              </div>
            )}
            {brief.brief.recommended_actions && brief.brief.recommended_actions.length > 0 && (
              <div>
                <p className="text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Actions</p>
                <ul className="space-y-1">
                  {brief.brief.recommended_actions.map((a, i) => (
                    <li key={i} className="text-sm text-slate-300 flex gap-2">
                      <span className="text-blue-400 font-semibold">{i + 1}.</span>
                      {a}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
