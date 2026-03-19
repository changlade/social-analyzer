-- ============================================================
-- Gold Layer: Impact Delta — CSR Claims vs Public Reality
-- Danone Social Impact Analyzer
-- ============================================================
-- The "money table" of the pipeline. Joins official CSR claims
-- with the aggregated public sentiment for the same ESG category
-- and period, then calls ai_query() to produce a structured
-- gap analysis: alignment score, gap explanation, and recommendations.
-- Powers the "Impact Delta" page in the marketing app.
-- ============================================================

CREATE OR REPLACE MATERIALIZED VIEW gold_impact_delta
COMMENT 'CSR claim vs public reality gap analysis per ESG category — the core intelligence table'
TBLPROPERTIES ('quality' = 'gold')
AS
WITH claim_summary AS (
  -- Roll up individual claims to ESG category + sub_theme level
  SELECT
    esg_category,
    sub_theme,
    COUNT(*)                                         AS claim_count,
    CONCAT_WS(' | ', COLLECT_LIST(LEFT(claim_text, 200)))
                                                     AS claims_combined,
    MAX(scraped_date)                                AS latest_claim_date
  FROM LIVE.gold_csr_claims
  WHERE claim_text IS NOT NULL
  GROUP BY esg_category, sub_theme
),
sentiment_latest AS (
  -- Latest month of public sentiment per ESG category
  SELECT
    esg_category,
    esg_sub_theme,
    AVG(avg_sentiment_score)                         AS period_avg_sentiment,
    SUM(article_count)                               AS total_articles,
    AVG(pct_critical)                                AS avg_pct_critical,
    MAX(overall_sentiment_label)                     AS dominant_sentiment,
    CONCAT_WS(' | ',
      TRANSFORM(
        COLLECT_LIST(CONCAT(
          'Week ', DATE_FORMAT(week_start, 'yyyy-MM-dd'), ': ',
          CAST(article_count AS STRING), ' articles, score=',
          CAST(ROUND(avg_sentiment_score, 2) AS STRING)
        )),
        x -> x
      )
    )                                                AS sentiment_evidence_summary,
    MAX(week_start)                                  AS latest_week
  FROM LIVE.gold_public_sentiment
  WHERE week_start >= DATE_SUB(CURRENT_DATE(), 90)  -- last 90 days
  GROUP BY esg_category, esg_sub_theme
),
joined AS (
  SELECT
    c.esg_category,
    c.sub_theme,
    c.claim_count,
    c.claims_combined,
    c.latest_claim_date,
    s.period_avg_sentiment,
    s.total_articles,
    s.avg_pct_critical,
    s.dominant_sentiment,
    s.sentiment_evidence_summary,
    s.latest_week
  FROM claim_summary c
  LEFT JOIN sentiment_latest s
    ON c.esg_category = s.esg_category
   AND (c.sub_theme = s.esg_sub_theme OR s.esg_sub_theme IS NULL)
  WHERE c.claim_count > 0
)
SELECT
  -- Unique delta record key
  SHA2(CONCAT(esg_category, '|', sub_theme, '|', CURRENT_DATE()), 256)
                                                     AS delta_id,
  esg_category,
  sub_theme,
  claim_count,
  total_articles,
  period_avg_sentiment,
  avg_pct_critical,
  dominant_sentiment,
  latest_claim_date,
  latest_week,
  CURRENT_DATE()                                     AS analysis_date,

  -- ── AI Gap Analysis ───────────────────────────────────────────────────────
  -- Produces a structured comparison of Danone's official position vs public perception
  ai_query(
    '${ai_endpoint_name}',
    CONCAT(
      'You are a critical ESG analyst creating a "Social Impact Delta" report for Danone. ',
      'You will compare Danone''s official CSR claims against public sentiment data. ',
      'Be balanced but honest: highlight real gaps, not just PR spin. ',
      'Respond ONLY with valid JSON (no markdown) matching exactly: ',
      '{"alignment_score": <integer 0-10, 10=perfect alignment>, ',
      '"alignment_label": "Aligned|Partial|Divergent|Contradictory", ',
      '"gap_headline": "<one punchy sentence describing the main gap>", ',
      '"official_narrative": "<what Danone claims in 2-3 sentences>", ',
      '"public_narrative": "<what the public data shows in 2-3 sentences>", ',
      '"key_gaps": [<up to 3 specific gaps or contradictions found>], ',
      '"marketing_opportunity": "<one actionable insight for Danone marketing team>", ',
      '"risk_level": "Low|Medium|High|Critical"} ',
      'ESG CATEGORY: ', esg_category, ' | SUB-THEME: ', sub_theme, ' ',
      'OFFICIAL CLAIMS (', CAST(claim_count AS STRING), ' claims): ',
      LEFT(claims_combined, 2000), ' ',
      'PUBLIC SENTIMENT DATA (', CAST(COALESCE(total_articles, 0) AS STRING), ' articles, ',
      'avg score=', CAST(ROUND(COALESCE(period_avg_sentiment, 0), 2) AS STRING), ', ',
      CAST(ROUND(COALESCE(avg_pct_critical, 0), 1) AS STRING), '% critical): ',
      LEFT(COALESCE(sentiment_evidence_summary, 'No public data available for this period'), 1500)
    )
  )                                                  AS delta_json_raw,

  -- ── Flat parsed columns ───────────────────────────────────────────────────
  TRY_CAST(get_json_object(
    ai_query('${ai_endpoint_name}',
      CONCAT('Return only a JSON object: {"alignment_score": <0-10>}. ',
             'Based on: claims="', LEFT(COALESCE(claims_combined,''), 500), '" ',
             'vs public sentiment score=', CAST(ROUND(COALESCE(period_avg_sentiment,0),2) AS STRING))
    ), '$.alignment_score') AS INT)                  AS alignment_score_quick,

  current_timestamp()                                AS _gold_at
FROM joined;
