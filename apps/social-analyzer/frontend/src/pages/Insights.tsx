import { useEffect, useState, useCallback } from "react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { Search, ExternalLink, ChevronLeft, ChevronRight } from "lucide-react";
import { getInsights, getSubThemes, InsightItem, SubTheme } from "../lib/api";
import { ESG_COLORS, SOURCE_COLORS, sentimentColor, formatDate, cn } from "../lib/utils";
import SentimentBadge from "../components/SentimentBadge";

const ESG_CATS = ["", "Environmental", "Social", "Governance", "Cross-ESG"];
const SOURCE_TYPES = ["", "official", "news", "ngo", "social", "benchmark"];
const STANCES = ["", "supportive", "critical", "neutral", "mixed"];
const PAGE_SIZE = 20;

export default function Insights() {
  const [items, setItems] = useState<InsightItem[]>([]);
  const [total, setTotal] = useState(0);
  const [subThemes, setSubThemes] = useState<SubTheme[]>([]);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(false);

  // Filters
  const [esgCat, setEsgCat]     = useState("");
  const [srcType, setSrcType]   = useState("");
  const [stance, setStance]     = useState("");
  const [search, setSearch]     = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo]     = useState("");

  const fetchData = useCallback(async (pageNum = 0) => {
    setLoading(true);
    try {
      const [res, themes] = await Promise.all([
        getInsights({
          esg_category: esgCat || undefined,
          source_type: srcType || undefined,
          stance: stance || undefined,
          search: search || undefined,
          date_from: dateFrom || undefined,
          date_to: dateTo || undefined,
          limit: PAGE_SIZE,
          offset: pageNum * PAGE_SIZE,
        }),
        getSubThemes({ esg_category: esgCat || undefined }),
      ]);
      setItems(res.items);
      setTotal(res.total);
      setSubThemes(themes);
    } finally {
      setLoading(false);
    }
  }, [esgCat, srcType, stance, search, dateFrom, dateTo]);

  useEffect(() => {
    setPage(0);
    fetchData(0);
  }, [fetchData]);

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold text-white">Insights Explorer</h1>

      {/* Filters */}
      <div className="bg-slate-900 rounded-xl border border-slate-800 p-4">
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          {/* Search */}
          <div className="relative lg:col-span-2">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search titles…"
              className="w-full pl-8 pr-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
            />
          </div>

          {/* ESG Category */}
          <select
            value={esgCat}
            onChange={(e) => setEsgCat(e.target.value)}
            className="px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:outline-none focus:border-blue-500"
          >
            {ESG_CATS.map((c) => <option key={c} value={c}>{c || "All Categories"}</option>)}
          </select>

          {/* Source Type */}
          <select
            value={srcType}
            onChange={(e) => setSrcType(e.target.value)}
            className="px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:outline-none focus:border-blue-500"
          >
            {SOURCE_TYPES.map((s) => <option key={s} value={s}>{s || "All Sources"}</option>)}
          </select>

          {/* Stance */}
          <select
            value={stance}
            onChange={(e) => setStance(e.target.value)}
            className="px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:outline-none focus:border-blue-500"
          >
            {STANCES.map((s) => <option key={s} value={s}>{s || "All Stances"}</option>)}
          </select>

          {/* Date from */}
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className="px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:outline-none focus:border-blue-500"
          />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        {/* Sub-theme chart */}
        <div className="bg-slate-900 rounded-xl border border-slate-800 p-4">
          <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-3">Top Sub-themes</h2>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart
              data={subThemes.slice(0, 10)}
              layout="vertical"
              margin={{ left: 8, right: 16, top: 0, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" horizontal={false} />
              <XAxis type="number" tick={{ fill: "#94a3b8", fontSize: 10 }} />
              <YAxis type="category" dataKey="esg_sub_theme" width={110} tick={{ fill: "#94a3b8", fontSize: 10 }} />
              <Tooltip
                contentStyle={{ backgroundColor: "#0f172a", border: "1px solid #1e293b", borderRadius: 8 }}
              />
              <Bar dataKey="article_count" radius={[0, 4, 4, 0]}>
                {subThemes.slice(0, 10).map((s) => (
                  <Cell key={s.esg_sub_theme} fill={ESG_COLORS[s.esg_category] ?? "#3b82f6"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Article list */}
        <div className="lg:col-span-3 space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-sm text-slate-400">{total.toLocaleString()} articles found</p>
            <div className="flex items-center gap-2">
              <button
                onClick={() => { const p = Math.max(0, page - 1); setPage(p); fetchData(p); }}
                disabled={page === 0}
                className="p-1.5 rounded-lg border border-slate-700 text-slate-400 hover:text-white disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <ChevronLeft size={14} />
              </button>
              <span className="text-xs text-slate-400">{page + 1} / {totalPages || 1}</span>
              <button
                onClick={() => { const p = Math.min(totalPages - 1, page + 1); setPage(p); fetchData(p); }}
                disabled={page >= totalPages - 1}
                className="p-1.5 rounded-lg border border-slate-700 text-slate-400 hover:text-white disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <ChevronRight size={14} />
              </button>
            </div>
          </div>

          {loading ? (
            <div className="flex items-center justify-center h-40">
              <div className="animate-spin w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full" />
            </div>
          ) : (
            <div className="space-y-3">
              {items.map((item) => (
                <ArticleCard key={item.article_id} item={item} />
              ))}
              {items.length === 0 && (
                <div className="text-center py-12 text-slate-500">No articles match the current filters.</div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function ArticleCard({ item }: { item: InsightItem }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div
      className="bg-slate-900 rounded-xl border border-slate-800 p-4 cursor-pointer hover:border-slate-600 transition-colors"
      onClick={() => setExpanded(!expanded)}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1.5">
            {/* ESG category badge */}
            <span
              className="px-2 py-0.5 rounded-full text-xs font-medium"
              style={{
                backgroundColor: `${ESG_COLORS[item.esg_category] ?? "#94a3b8"}20`,
                color: ESG_COLORS[item.esg_category] ?? "#94a3b8",
              }}
            >
              {item.esg_category}
            </span>
            {/* Source type badge */}
            <span
              className="px-2 py-0.5 rounded-full text-xs font-medium"
              style={{
                backgroundColor: `${SOURCE_COLORS[item.source_type] ?? "#94a3b8"}20`,
                color: SOURCE_COLORS[item.source_type] ?? "#94a3b8",
              }}
            >
              {item.source_type}
            </span>
            <SentimentBadge label={item.sentiment_label} />
            {item.danone_stance === "critical" && (
              <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-red-500/10 text-red-400 border border-red-500/20">
                Critical
              </span>
            )}
          </div>
          <p className="text-sm font-medium text-white truncate">{item.title}</p>
          {expanded && (
            <p className="mt-2 text-sm text-slate-400 leading-relaxed">{item.content_preview}</p>
          )}
          {expanded && item.impact_summary && (
            <p className="mt-2 text-xs text-blue-300 leading-relaxed border-l-2 border-blue-500 pl-3">
              {item.impact_summary}
            </p>
          )}
        </div>
        <div className="text-right flex-shrink-0">
          <p className="text-xs text-slate-500">{formatDate(item.scraped_date)}</p>
          <p className="text-xs text-slate-600 mt-0.5">Score: {item.credibility_score}/10</p>
          <a
            href={item.url}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="mt-1.5 inline-flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300"
          >
            <ExternalLink size={10} /> Source
          </a>
        </div>
      </div>
    </div>
  );
}
