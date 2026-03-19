import { useEffect, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Cell,
  ResponsiveContainer, ScatterChart, Scatter, ZAxis,
} from "recharts";
import { getSourceBreakdown, SourceRecord } from "../lib/api";
import { SOURCE_COLORS, sentimentColor, formatDate } from "../lib/utils";

export default function Sources() {
  const [sources, setSources] = useState<SourceRecord[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const since = new Date(Date.now() - 30 * 864e5).toISOString().slice(0, 10);
    getSourceBreakdown({ date_from: since })
      .then(setSources)
      .finally(() => setLoading(false));
  }, []);

  // Aggregate by source_type
  const byType = Object.values(
    sources.reduce<Record<string, SourceRecord & { topic_count: number }>>((acc, s) => {
      if (!acc[s.source_type]) {
        acc[s.source_type] = { ...s, topic_count: 0 };
      } else {
        acc[s.source_type].article_count += s.article_count;
        acc[s.source_type].critical_count += s.critical_count;
        acc[s.source_type].supportive_count += s.supportive_count;
      }
      acc[s.source_type].topic_count = (acc[s.source_type].topic_count ?? 0) + 1;
      return acc;
    }, {})
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full" />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Source Coverage</h1>
        <p className="text-slate-400 text-sm mt-1">Article distribution and sentiment by data source — last 30 days.</p>
      </div>

      {/* Source type summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
        {byType.map((s) => (
          <div key={s.source_type} className="bg-slate-900 rounded-xl border border-slate-800 p-4">
            <div
              className="w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold uppercase mb-3"
              style={{ backgroundColor: `${SOURCE_COLORS[s.source_type] ?? "#94a3b8"}20`, color: SOURCE_COLORS[s.source_type] ?? "#94a3b8" }}
            >
              {s.source_type.slice(0, 2)}
            </div>
            <p className="text-sm font-semibold text-white capitalize">{s.source_type}</p>
            <p className="text-xl font-bold text-white mt-1">{s.article_count.toLocaleString()}</p>
            <p className="text-xs text-slate-500 mt-0.5">articles · {s.topic_count} topics</p>
            <div
              className="mt-2 text-xs font-medium"
              style={{ color: sentimentColor(s.avg_sentiment) }}
            >
              Sentiment: {s.avg_sentiment >= 0.1 ? "+" : ""}{(s.avg_sentiment * 100).toFixed(0)}%
            </div>
          </div>
        ))}
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Articles by source type */}
        <div className="bg-slate-900 rounded-xl border border-slate-800 p-5">
          <h2 className="text-sm font-semibold text-white mb-4">Articles by Source Type</h2>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={byType}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
              <XAxis dataKey="source_type" tick={{ fill: "#94a3b8", fontSize: 12 }} />
              <YAxis tick={{ fill: "#94a3b8", fontSize: 12 }} />
              <Tooltip
                contentStyle={{ backgroundColor: "#0f172a", border: "1px solid #1e293b", borderRadius: 8 }}
              />
              <Bar dataKey="article_count" radius={[4, 4, 0, 0]} name="Articles">
                {byType.map((s) => (
                  <Cell key={s.source_type} fill={SOURCE_COLORS[s.source_type] ?? "#94a3b8"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Critical vs supportive stacked */}
        <div className="bg-slate-900 rounded-xl border border-slate-800 p-5">
          <h2 className="text-sm font-semibold text-white mb-4">Critical vs Supportive by Source</h2>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={byType}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
              <XAxis dataKey="source_type" tick={{ fill: "#94a3b8", fontSize: 12 }} />
              <YAxis tick={{ fill: "#94a3b8", fontSize: 12 }} />
              <Tooltip
                contentStyle={{ backgroundColor: "#0f172a", border: "1px solid #1e293b", borderRadius: 8 }}
              />
              <Bar dataKey="supportive_count" stackId="a" fill="#22c55e" name="Supportive" radius={[0, 0, 0, 0]} />
              <Bar dataKey="critical_count"   stackId="a" fill="#ef4444" name="Critical"   radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Topic breakdown table */}
      <div className="bg-slate-900 rounded-xl border border-slate-800 overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-800">
          <h2 className="text-sm font-semibold text-white">Topic Coverage Detail</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-800">
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wide">Source</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wide">Topic</th>
                <th className="text-right px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wide">Articles</th>
                <th className="text-right px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wide hidden md:table-cell">Sentiment</th>
                <th className="text-right px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wide hidden lg:table-cell">Critical</th>
                <th className="text-right px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wide hidden lg:table-cell">Last seen</th>
              </tr>
            </thead>
            <tbody>
              {sources.map((s, i) => (
                <tr key={i} className="border-b border-slate-800 hover:bg-slate-800/40 transition-colors">
                  <td className="px-4 py-2.5">
                    <span
                      className="px-2 py-0.5 rounded-full text-xs font-medium capitalize"
                      style={{ backgroundColor: `${SOURCE_COLORS[s.source_type] ?? "#94a3b8"}20`, color: SOURCE_COLORS[s.source_type] ?? "#94a3b8" }}
                    >
                      {s.source_type}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-slate-300">{s.search_topic.replace(/_/g, " ")}</td>
                  <td className="px-4 py-2.5 text-right text-white font-medium">{s.article_count}</td>
                  <td className="px-4 py-2.5 text-right hidden md:table-cell">
                    <span style={{ color: sentimentColor(s.avg_sentiment) }}>
                      {s.avg_sentiment >= 0 ? "+" : ""}{(s.avg_sentiment * 100).toFixed(0)}%
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-right hidden lg:table-cell text-red-400">{s.critical_count}</td>
                  <td className="px-4 py-2.5 text-right hidden lg:table-cell text-slate-500">{formatDate(s.last_seen)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
