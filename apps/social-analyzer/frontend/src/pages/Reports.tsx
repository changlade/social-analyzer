import { useState } from "react";
import { FileText, Loader2, Download, AlertCircle } from "lucide-react";
import { generateReport, getDailyBrief, GeneratedReport, DailyBrief } from "../lib/api";
import { cn } from "../lib/utils";

const REPORT_TYPES = [
  { id: "executive_brief",  label: "Executive Brief",      desc: "4-paragraph summary for leadership" },
  { id: "esg_deep_dive",    label: "ESG Deep Dive",        desc: "Detailed 8-section analysis" },
  { id: "csr_vs_reality",   label: "CSR vs Reality",       desc: "Official narrative vs public perception" },
  { id: "source_analysis",  label: "Source Analysis",      desc: "Patterns by data source type" },
  { id: "custom",           label: "Custom",               desc: "Write your own prompt" },
];

const AUDIENCES = [
  { id: "marketing",       label: "Marketing" },
  { id: "executive",       label: "Executive" },
  { id: "investor",        label: "Investor" },
  { id: "communications",  label: "Communications" },
];

const ESG_CATS = ["Environmental", "Social", "Governance"];

export default function Reports() {
  const [reportType, setReportType] = useState("executive_brief");
  const [audience, setAudience]     = useState("marketing");
  const [categories, setCategories] = useState<string[]>(ESG_CATS);
  const [dateFrom, setDateFrom]     = useState("");
  const [dateTo, setDateTo]         = useState("");
  const [customPrompt, setCustomPrompt] = useState("");
  const [generating, setGenerating] = useState(false);
  const [result, setResult]         = useState<GeneratedReport | null>(null);
  const [error, setError]           = useState("");

  const toggleCat = (cat: string) =>
    setCategories((prev) =>
      prev.includes(cat) ? prev.filter((c) => c !== cat) : [...prev, cat]
    );

  const handleGenerate = async () => {
    if (categories.length === 0) {
      setError("Select at least one ESG category.");
      return;
    }
    setGenerating(true);
    setError("");
    setResult(null);
    try {
      const r = await generateReport({
        report_type: reportType,
        esg_categories: categories,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        audience,
        custom_prompt: reportType === "custom" ? customPrompt : undefined,
      });
      setResult(r);
    } catch (e: unknown) {
      setError((e as Error).message ?? "Report generation failed.");
    } finally {
      setGenerating(false);
    }
  };

  const handleExport = () => {
    if (!result) return;
    const content = formatReportAsText(result);
    const blob = new Blob([content], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `danone-esg-report-${new Date().toISOString().slice(0, 10)}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Report Builder</h1>
        <p className="text-slate-400 text-sm mt-1">
          Generate AI-powered ESG reports tailored to your audience using live gold layer data.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Config panel */}
        <div className="space-y-5">
          {/* Report type */}
          <div className="bg-slate-900 rounded-xl border border-slate-800 p-4 space-y-2">
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-3">Report Type</p>
            {REPORT_TYPES.map((t) => (
              <button
                key={t.id}
                onClick={() => setReportType(t.id)}
                className={cn(
                  "w-full text-left rounded-lg px-3 py-2.5 transition-colors",
                  reportType === t.id
                    ? "bg-blue-600/20 border border-blue-500/40"
                    : "hover:bg-slate-800 border border-transparent"
                )}
              >
                <p className={cn("text-sm font-medium", reportType === t.id ? "text-blue-300" : "text-white")}>
                  {t.label}
                </p>
                <p className="text-xs text-slate-500 mt-0.5">{t.desc}</p>
              </button>
            ))}
          </div>

          {/* Custom prompt */}
          {reportType === "custom" && (
            <div className="bg-slate-900 rounded-xl border border-slate-800 p-4">
              <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">Custom Instructions</p>
              <textarea
                value={customPrompt}
                onChange={(e) => setCustomPrompt(e.target.value)}
                placeholder="Describe the report you want the AI to generate…"
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 resize-none h-28"
              />
            </div>
          )}

          {/* Audience */}
          <div className="bg-slate-900 rounded-xl border border-slate-800 p-4">
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-3">Audience</p>
            <div className="grid grid-cols-2 gap-2">
              {AUDIENCES.map((a) => (
                <button
                  key={a.id}
                  onClick={() => setAudience(a.id)}
                  className={cn(
                    "px-3 py-2 rounded-lg text-sm font-medium transition-colors text-center",
                    audience === a.id ? "bg-blue-600 text-white" : "bg-slate-800 text-slate-400 hover:text-white"
                  )}
                >
                  {a.label}
                </button>
              ))}
            </div>
          </div>

          {/* ESG Categories */}
          <div className="bg-slate-900 rounded-xl border border-slate-800 p-4">
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-3">ESG Scope</p>
            <div className="space-y-2">
              {ESG_CATS.map((c) => (
                <label key={c} className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={categories.includes(c)}
                    onChange={() => toggleCat(c)}
                    className="rounded border-slate-600 bg-slate-800 text-blue-500 focus:ring-0"
                  />
                  <span className="text-sm text-slate-300">{c}</span>
                </label>
              ))}
            </div>
          </div>

          {/* Date range */}
          <div className="bg-slate-900 rounded-xl border border-slate-800 p-4 space-y-3">
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide">Date Range</p>
            <div className="space-y-2">
              <input
                type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)}
                className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:outline-none focus:border-blue-500"
                placeholder="From"
              />
              <input
                type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)}
                className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:outline-none focus:border-blue-500"
                placeholder="To"
              />
            </div>
          </div>

          <button
            onClick={handleGenerate}
            disabled={generating}
            className="w-full flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-60 disabled:cursor-not-allowed text-white font-medium py-3 rounded-xl transition-colors"
          >
            {generating ? (
              <><Loader2 size={16} className="animate-spin" /> Generating…</>
            ) : (
              <><FileText size={16} /> Generate Report</>
            )}
          </button>

          {error && (
            <div className="flex gap-2 text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
              <AlertCircle size={14} className="flex-shrink-0 mt-0.5" />
              {error}
            </div>
          )}
        </div>

        {/* Report output */}
        <div className="lg:col-span-2">
          {!result && !generating && (
            <div className="h-full flex flex-col items-center justify-center text-slate-600 min-h-96 bg-slate-900 rounded-xl border border-slate-800">
              <FileText size={48} className="mb-4 text-slate-700" />
              <p className="text-lg font-medium text-slate-500">Configure and generate your report</p>
              <p className="text-sm text-slate-600 mt-1">Results will appear here</p>
            </div>
          )}

          {generating && (
            <div className="h-full flex flex-col items-center justify-center min-h-96 bg-slate-900 rounded-xl border border-slate-800">
              <Loader2 size={32} className="animate-spin text-blue-500 mb-4" />
              <p className="text-white font-medium">AI is generating your report…</p>
              <p className="text-sm text-slate-400 mt-1">Querying gold layer data and running analysis</p>
            </div>
          )}

          {result && (
            <div className="bg-slate-900 rounded-xl border border-slate-800 p-6 space-y-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="text-lg font-bold text-white">
                    {result.report.title ?? "ESG Report"}
                  </h2>
                  <p className="text-xs text-slate-400 mt-0.5">
                    {result.report_type.replace(/_/g, " ")} · Audience: {result.audience}
                  </p>
                </div>
                <button
                  onClick={handleExport}
                  className="flex items-center gap-1.5 text-sm text-slate-400 hover:text-white bg-slate-800 border border-slate-700 px-3 py-1.5 rounded-lg transition-colors"
                >
                  <Download size={14} /> Export MD
                </button>
              </div>

              {result.report.executive_summary && (
                <div className="bg-blue-500/10 border border-blue-500/20 rounded-lg p-4">
                  <p className="text-xs font-semibold text-blue-400 uppercase tracking-wide mb-1">Executive Summary</p>
                  <p className="text-sm text-slate-300 leading-relaxed">{result.report.executive_summary}</p>
                </div>
              )}

              {result.report.sections?.map((s, i) => (
                <div key={i}>
                  <h3 className="text-sm font-semibold text-white mb-1">{s.heading}</h3>
                  <p className="text-sm text-slate-400 leading-relaxed">{s.content}</p>
                </div>
              ))}

              {result.report.key_findings && result.report.key_findings.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">Key Findings</p>
                  <ul className="space-y-1.5">
                    {result.report.key_findings.map((f, i) => (
                      <li key={i} className="text-sm text-slate-300 flex gap-2">
                        <span className="text-blue-400 font-bold">•</span>{f}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {result.report.recommendations && result.report.recommendations.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">Recommendations</p>
                  <ul className="space-y-1.5">
                    {result.report.recommendations.map((r, i) => (
                      <li key={i} className="text-sm text-slate-300 flex gap-2">
                        <span className="text-green-400 font-bold">{i + 1}.</span>{r}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {result.report.risk_flags && result.report.risk_flags.length > 0 && (
                <div className="bg-red-500/5 border border-red-500/20 rounded-lg p-4">
                  <p className="text-xs font-semibold text-red-400 uppercase tracking-wide mb-2">Risk Flags</p>
                  <ul className="space-y-1">
                    {result.report.risk_flags.map((r, i) => (
                      <li key={i} className="text-sm text-red-300 flex gap-2">
                        <span>⚠</span>{r}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function formatReportAsText(r: GeneratedReport): string {
  const lines: string[] = [];
  lines.push(`# ${r.report.title ?? "ESG Report"}`);
  lines.push(`\n_Report type: ${r.report_type} | Audience: ${r.audience}_\n`);
  if (r.report.executive_summary) {
    lines.push("## Executive Summary\n" + r.report.executive_summary + "\n");
  }
  r.report.sections?.forEach((s) => {
    lines.push(`## ${s.heading}\n${s.content}\n`);
  });
  if (r.report.key_findings?.length) {
    lines.push("## Key Findings\n" + r.report.key_findings.map((f) => `- ${f}`).join("\n") + "\n");
  }
  if (r.report.recommendations?.length) {
    lines.push("## Recommendations\n" + r.report.recommendations.map((rec, i) => `${i + 1}. ${rec}`).join("\n") + "\n");
  }
  if (r.report.risk_flags?.length) {
    lines.push("## Risk Flags\n" + r.report.risk_flags.map((f) => `⚠ ${f}`).join("\n") + "\n");
  }
  return lines.join("\n");
}
