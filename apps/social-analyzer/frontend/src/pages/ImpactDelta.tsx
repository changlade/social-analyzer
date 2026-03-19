import { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Cell, ResponsiveContainer } from "recharts";
import { Shield, AlertTriangle, TrendingDown, ChevronDown, ChevronUp } from "lucide-react";
import { getImpactDelta, getDeltaSummary, getCSRClaims, DeltaRecord, DeltaSummary, CSRClaim } from "../lib/api";
import { alignmentColor, riskColor, ESG_COLORS, cn } from "../lib/utils";

const ESG_CATS = ["", "Environmental", "Social", "Governance"];

export default function ImpactDelta() {
  const [deltas, setDeltas]   = useState<DeltaRecord[]>([]);
  const [summary, setSummary] = useState<DeltaSummary[]>([]);
  const [claims, setClaims]   = useState<CSRClaim[]>([]);
  const [esgCat, setEsgCat]   = useState("");
  const [tab, setTab]         = useState<"delta" | "claims">("delta");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      getImpactDelta({ esg_category: esgCat || undefined }),
      getDeltaSummary(),
      getCSRClaims({ esg_category: esgCat || undefined }),
    ]).then(([d, s, c]) => {
      setDeltas(d);
      setSummary(s);
      setClaims(c);
    }).finally(() => setLoading(false));
  }, [esgCat]);

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Impact Delta</h1>
        <p className="text-slate-400 text-sm mt-1">
          Official CSR claims vs public perception — where the story diverges.
        </p>
      </div>

      {/* Summary bar chart */}
      <div className="bg-slate-900 rounded-xl border border-slate-800 p-5">
        <h2 className="text-sm font-semibold text-white mb-4">Alignment Score by ESG Category (0 = biggest gap)</h2>
        <ResponsiveContainer width="100%" height={140}>
          <BarChart data={summary} margin={{ left: -20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
            <XAxis dataKey="esg_category" tick={{ fill: "#94a3b8", fontSize: 12 }} />
            <YAxis domain={[0, 10]} tick={{ fill: "#94a3b8", fontSize: 12 }} />
            <Tooltip
              contentStyle={{ backgroundColor: "#0f172a", border: "1px solid #1e293b", borderRadius: 8 }}
            />
            <Bar dataKey="avg_alignment" radius={[4, 4, 0, 0]} name="Avg Alignment">
              {summary.map((s) => (
                <Cell key={s.esg_category} fill={alignmentColor(s.avg_alignment)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Filter + tabs */}
      <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center justify-between">
        <div className="flex gap-2">
          {ESG_CATS.map((c) => (
            <button
              key={c}
              onClick={() => setEsgCat(c)}
              className={cn(
                "px-3 py-1.5 rounded-lg text-sm font-medium transition-colors",
                esgCat === c
                  ? "text-white"
                  : "bg-slate-800 text-slate-400 hover:text-white"
              )}
              style={esgCat === c ? { backgroundColor: ESG_COLORS[c] ?? "#3b82f6" } : {}}
            >
              {c || "All"}
            </button>
          ))}
        </div>
        <div className="flex gap-2">
          {(["delta", "claims"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={cn(
                "px-3 py-1.5 rounded-lg text-sm font-medium transition-colors",
                tab === t ? "bg-blue-600 text-white" : "bg-slate-800 text-slate-400 hover:text-white"
              )}
            >
              {t === "delta" ? "Gap Analysis" : "CSR Claims"}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-40">
          <div className="animate-spin w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full" />
        </div>
      ) : tab === "delta" ? (
        <div className="space-y-4">
          {deltas.length === 0 && (
            <p className="text-center text-slate-500 py-12">No delta records yet. Run the pipeline first.</p>
          )}
          {deltas.map((delta) => (
            <DeltaCard key={delta.delta_id} delta={delta} />
          ))}
        </div>
      ) : (
        <ClaimsTable claims={claims} />
      )}
    </div>
  );
}

function DeltaCard({ delta }: { delta: DeltaRecord }) {
  const [open, setOpen] = useState(false);

  const score = delta.alignment_score_quick;
  const risk  = delta.risk_level;

  return (
    <div className="bg-slate-900 rounded-xl border border-slate-800 overflow-hidden">
      <button
        className="w-full text-left p-5 hover:bg-slate-800/50 transition-colors"
        onClick={() => setOpen(!open)}
      >
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <span
                className="px-2 py-0.5 rounded-full text-xs font-medium"
                style={{ backgroundColor: `${ESG_COLORS[delta.esg_category] ?? "#94a3b8"}20`, color: ESG_COLORS[delta.esg_category] ?? "#94a3b8" }}
              >
                {delta.esg_category}
              </span>
              <span className="text-xs text-slate-400">{delta.sub_theme}</span>
              {risk && (
                <span
                  className="px-2 py-0.5 rounded-full text-xs font-medium"
                  style={{ color: riskColor(risk), backgroundColor: `${riskColor(risk)}20` }}
                >
                  {risk} Risk
                </span>
              )}
            </div>
            <p className="text-sm font-medium text-white">{delta.gap_headline ?? `${delta.sub_theme} gap analysis`}</p>
          </div>
          <div className="flex items-center gap-3 flex-shrink-0">
            {/* Alignment score */}
            <div className="text-center">
              <div
                className="w-12 h-12 rounded-full flex items-center justify-center text-lg font-bold border-2"
                style={{ borderColor: alignmentColor(score), color: alignmentColor(score) }}
              >
                {score ?? "?"}
              </div>
              <p className="text-xs text-slate-500 mt-1">/ 10</p>
            </div>
            {open ? <ChevronUp size={16} className="text-slate-400" /> : <ChevronDown size={16} className="text-slate-400" />}
          </div>
        </div>
      </button>

      {open && (
        <div className="px-5 pb-5 border-t border-slate-800 pt-4 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Official narrative */}
            <div className="bg-blue-500/5 rounded-lg p-4 border border-blue-500/20">
              <div className="flex items-center gap-2 mb-2">
                <Shield size={14} className="text-blue-400" />
                <p className="text-xs font-semibold text-blue-400 uppercase tracking-wide">Official Narrative</p>
              </div>
              <p className="text-sm text-slate-300 leading-relaxed">
                {delta.official_narrative ?? "No official narrative extracted yet."}
              </p>
            </div>

            {/* Public narrative */}
            <div className="bg-amber-500/5 rounded-lg p-4 border border-amber-500/20">
              <div className="flex items-center gap-2 mb-2">
                <TrendingDown size={14} className="text-amber-400" />
                <p className="text-xs font-semibold text-amber-400 uppercase tracking-wide">Public Reality</p>
              </div>
              <p className="text-sm text-slate-300 leading-relaxed">
                {delta.public_narrative ?? "Insufficient public data collected yet."}
              </p>
            </div>
          </div>

          {/* Stats row */}
          <div className="flex flex-wrap gap-4 text-xs text-slate-400">
            <span><span className="text-white font-medium">{delta.claim_count}</span> official claims</span>
            <span><span className="text-white font-medium">{delta.total_articles ?? 0}</span> public articles</span>
            {delta.pct_critical != null && (
              <span><span className="text-red-400 font-medium">{delta.pct_critical}%</span> critical coverage</span>
            )}
            {delta.alignment_label && (
              <span>Alignment: <span className="text-white font-medium">{delta.alignment_label}</span></span>
            )}
          </div>

          {/* Marketing opportunity */}
          {delta.marketing_opportunity && (
            <div className="bg-green-500/5 rounded-lg p-3 border border-green-500/20">
              <p className="text-xs font-semibold text-green-400 mb-1">Marketing Opportunity</p>
              <p className="text-sm text-slate-300">{delta.marketing_opportunity}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ClaimsTable({ claims }: { claims: CSRClaim[] }) {
  if (claims.length === 0) {
    return <p className="text-center text-slate-500 py-12">No CSR claims extracted yet. Run the pipeline first.</p>;
  }

  return (
    <div className="bg-slate-900 rounded-xl border border-slate-800 overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-800">
            <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wide">Claim</th>
            <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wide hidden md:table-cell">Category</th>
            <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wide hidden lg:table-cell">Type</th>
            <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wide hidden lg:table-cell">Metric</th>
            <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wide">Score</th>
          </tr>
        </thead>
        <tbody>
          {claims.map((c) => (
            <tr key={c.claim_id} className="border-b border-slate-800 hover:bg-slate-800/40 transition-colors">
              <td className="px-4 py-3 text-slate-300 max-w-xs">{c.claim_text}</td>
              <td className="px-4 py-3 hidden md:table-cell">
                <span
                  className="px-2 py-0.5 rounded-full text-xs"
                  style={{ backgroundColor: `${ESG_COLORS[c.esg_category] ?? "#94a3b8"}20`, color: ESG_COLORS[c.esg_category] ?? "#94a3b8" }}
                >
                  {c.esg_category}
                </span>
              </td>
              <td className="px-4 py-3 hidden lg:table-cell text-slate-400">{c.claim_type}</td>
              <td className="px-4 py-3 hidden lg:table-cell text-slate-400">{c.metric ?? "—"}</td>
              <td className="px-4 py-3 text-slate-300 font-medium">{c.credibility_score}/10</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
