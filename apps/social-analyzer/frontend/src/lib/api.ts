const BASE = import.meta.env.VITE_API_URL ?? "";

async function get<T>(path: string, params?: Record<string, string | number | undefined>): Promise<T> {
  const url = new URL(`${BASE}/api${path}`, window.location.origin);
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, String(v));
    });
  }
  const res = await fetch(url.toString());
  if (!res.ok) throw new Error(`API ${path} failed: ${res.status}`);
  return res.json();
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const url = `${BASE}/api${path}`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API ${path} failed: ${res.status}`);
  return res.json();
}

// ── Sentiment ─────────────────────────────────────────────────────────────────
export const getKPIs = (p?: { date_from?: string; date_to?: string }) =>
  get<Record<string, number | string>>("/sentiment/kpis", p);

export const getSentimentTimeline = (p?: {
  esg_category?: string;
  source_type?: string;
  granularity?: string;
  date_from?: string;
  date_to?: string;
}) => get<SentimentPoint[]>("/sentiment/timeline", p);

export const getSentimentBySource = (p?: { date_from?: string; date_to?: string }) =>
  get<SourceSentiment[]>("/sentiment/by-source", p);

// ── Insights ─────────────────────────────────────────────────────────────────
export const getESGBreakdown = (p?: { date_from?: string; date_to?: string }) =>
  get<ESGBreakdown[]>("/insights/breakdown", p);

export const getInsights = (p?: {
  esg_category?: string;
  source_type?: string;
  sentiment?: string;
  stance?: string;
  date_from?: string;
  date_to?: string;
  search?: string;
  limit?: number;
  offset?: number;
}) => get<InsightPage>("/insights", p);

export const getSubThemes = (p?: { esg_category?: string; date_from?: string; date_to?: string }) =>
  get<SubTheme[]>("/insights/sub-themes", p);

// ── Impact Delta ──────────────────────────────────────────────────────────────
export const getImpactDelta = (p?: {
  esg_category?: string;
  min_alignment?: number;
  max_alignment?: number;
}) => get<DeltaRecord[]>("/impact-delta", p);

export const getDeltaSummary = () => get<DeltaSummary[]>("/impact-delta/summary");

export const getCSRClaims = (p?: { esg_category?: string; claim_type?: string }) =>
  get<CSRClaim[]>("/impact-delta/claims", p);

// ── Sources ───────────────────────────────────────────────────────────────────
export const getSourceBreakdown = (p?: { date_from?: string; date_to?: string }) =>
  get<SourceRecord[]>("/sources", p);

// ── Reports ───────────────────────────────────────────────────────────────────
export const getDailyBrief = (date?: string) =>
  get<DailyBrief>("/reports/daily-brief", date ? { date } : undefined);

export const generateReport = (body: ReportRequest) =>
  post<GeneratedReport>("/reports/generate", body);

// ── Types ─────────────────────────────────────────────────────────────────────
export interface SentimentPoint {
  period: string;
  avg_sentiment: number;
  official_sentiment: number | null;
  public_sentiment: number | null;
  article_count: number;
  positive_count: number;
  neutral_count: number;
  negative_count: number;
  critical_count: number;
}

export interface SourceSentiment {
  source_type: string;
  article_count: number;
  avg_sentiment: number;
  positive_count: number;
  negative_count: number;
  avg_credibility: number;
}

export interface ESGBreakdown {
  esg_category: string;
  article_count: number;
  avg_sentiment: number;
  positive_count: number;
  negative_count: number;
  critical_count: number;
  avg_credibility: number;
}

export interface InsightPage {
  total: number;
  offset: number;
  limit: number;
  items: InsightItem[];
}

export interface InsightItem {
  article_id: string;
  url: string;
  title: string;
  content_preview: string;
  source_type: string;
  search_topic: string;
  esg_category: string;
  esg_sub_theme: string;
  sentiment_label: string;
  sentiment_score: number;
  danone_stance: string;
  credibility_score: number;
  is_official_csr: boolean;
  impact_summary: string;
  scraped_date: string;
  published_at: string;
  language: string;
  scraper: string;
}

export interface SubTheme {
  esg_category: string;
  esg_sub_theme: string;
  article_count: number;
  avg_sentiment: number;
}

export interface DeltaRecord {
  delta_id: string;
  esg_category: string;
  sub_theme: string;
  claim_count: number;
  total_articles: number | null;
  period_avg_sentiment: number | null;
  pct_critical: number | null;
  dominant_sentiment: string | null;
  alignment_score_quick: number | null;
  alignment_label: string | null;
  gap_headline: string | null;
  official_narrative: string | null;
  public_narrative: string | null;
  marketing_opportunity: string | null;
  risk_level: string | null;
  analysis_date: string;
}

export interface DeltaSummary {
  esg_category: string;
  avg_alignment: number;
  theme_count: number;
  divergent_themes: number;
  max_risk_level: string | null;
}

export interface CSRClaim {
  claim_id: string;
  esg_category: string;
  sub_theme: string;
  claim_text: string;
  metric: string | null;
  timeframe: string | null;
  claim_type: string;
  credibility_score: number;
  url: string;
  scraped_date: string;
}

export interface SourceRecord {
  source_type: string;
  search_topic: string;
  article_count: number;
  avg_sentiment: number;
  avg_credibility: number;
  critical_count: number;
  supportive_count: number;
  active_days: number;
  last_seen: string;
}

export interface DailyBrief {
  report_date: string;
  total_articles: number;
  unique_sources: number;
  avg_sentiment: number;
  headline: string;
  brief: {
    headline?: string;
    executive_brief?: string;
    top_risk?: string;
    top_opportunity?: string;
    esg_pulse?: { environmental: number; social: number; governance: number };
    recommended_actions?: string[];
  };
}

export interface ReportRequest {
  report_type: string;
  esg_categories: string[];
  date_from?: string;
  date_to?: string;
  audience: string;
  custom_prompt?: string;
  max_articles?: number;
}

export interface GeneratedReport {
  report_type: string;
  audience: string;
  report: {
    title?: string;
    executive_summary?: string;
    sections?: { heading: string; content: string }[];
    key_findings?: string[];
    recommendations?: string[];
    risk_flags?: string[];
  };
}
