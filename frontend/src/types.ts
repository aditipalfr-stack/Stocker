export interface KeyRatios {
  market_cap_cr: number;
  current_price: number;
  high_low: string;
  stock_pe: number;
  book_value: number;
  dividend_yield_pct: number;
  roce_pct: number;
  roe_pct: number;
  face_value: number;
  industry_pe?: number;
  debt_to_equity?: number;
  interest_coverage?: number;
  fcf_yield_pct?: number;
  sales_growth_3yr_cagr?: number;
  profit_growth_3yr_cagr?: number;
}

export interface FinancialRow {
  metric: string;
  values: Record<string, number | null>;
}

export interface FinancialStatement {
  periods: string[];
  rows: FinancialRow[];
}

export interface ConcallInsight {
  period: string;
  transcript_url?: string;
  presentation_url?: string;
  audio_url?: string;
  cfo_and_fcf_analysis: string;
  demand_drivers: string[];
  supply_and_capex: string[];
  management_guidance: string;
  risks_and_headwinds: string[];
  analyst_sentiment: string;
}

export interface AnnualReportInsight {
  year: string;
  report_url?: string;
  cfo_fcf_performance: string;
  capex_cwip_summary: string;
  strategic_priorities: string[];
  forensic_checklist: Record<string, string>;
}

export interface DocumentLinks {
  annual_reports: Array<{ name: string; url: string }>;
  concalls: Array<{ name: string; url: string }>;
  presentations: Array<{ name: string; url: string }>;
}

export interface ProjectionAssumption {
  revenue_growth_rate_pct: number;
  target_opm_pct: number;
  capex_pct_of_sales: number;
  effective_tax_rate_pct: number;
  terminal_growth_rate_pct: number;
  discount_rate_wacc_pct: number;
  target_exit_pe: number;
}

export interface YearlyProjection {
  year: string;
  revenue_cr: number;
  opm_pct: number;
  ebitda_cr: number;
  depreciation_cr: number;
  interest_cr: number;
  pbt_cr: number;
  tax_cr: number;
  pat_cr: number;
  eps: number;
  cfo_cr: number;
  capex_cr: number;
  fcf_cr: number;
}

export interface ProjectionResult {
  assumptions: ProjectionAssumption;
  historical_revenue_cagr_3yr: number;
  historical_opm_median: number;
  projections: YearlyProjection[];
  dcf_fair_value_per_share: number;
  dcf_upside_pct: number;
  target_price_exit_pe: number;
  target_price_upside_pct: number;
  projected_3yr_irr_cagr_pct: number;
  scenario_type: string;
}

export interface ScoreBreakdown {
  growth_momentum_score: number;
  cash_quality_fcf_score: number;
  capital_efficiency_score: number;
  balance_sheet_safety_score: number;
  valuation_margin_score: number;
  total_composite_score: number;
  verdict: string;
  investment_thesis: string;
  key_catalysts: string[];
  key_risks: string[];
}

export interface StockSummary {
  symbol: string;
  name: string;
  sector: string;
  industry: string;
  current_price: number;
  market_cap_cr: number;
  pe_ratio: number;
  roce_pct: number;
  roe_pct: number;
  fcf_yield_pct: number;
  sales_growth_3yr_pct: number;
  cfo_to_pat_5yr_pct: number;
  net_debt_to_equity: number;
  composite_score: number;
  verdict: string;
  rank: number;
  is_top_conviction: boolean;
  investment_thesis_short: string;
}

export interface StockDetail {
  symbol: string;
  name: string;
  sector: string;
  industry: string;
  about: string;
  ratios: KeyRatios;
  quarters: FinancialStatement;
  profit_loss: FinancialStatement;
  balance_sheet: FinancialStatement;
  cash_flow: FinancialStatement;
  concall_insights: ConcallInsight[];
  annual_report_insights: AnnualReportInsight[];
  documents: DocumentLinks;
  analytics: {
    quarterly_analysis: {
      trends: Array<{
        period: string;
        sales: number;
        operating_profit: number;
        opm_pct: number;
        net_profit: number;
        sales_growth_qoq_pct?: number;
        sales_growth_yoy_pct?: number;
        pat_growth_qoq_pct?: number;
        pat_growth_yoy_pct?: number;
      }>;
    };
    growth_rates: {
      sales_cagr_3yr?: number;
      pat_cagr_3yr?: number;
      sales_cagr_5yr?: number;
      pat_cagr_5yr?: number;
      sales_cagr_10yr?: number;
      pat_cagr_10yr?: number;
    };
    cash_flow_quality: {
      cumulative_5y_pat_cr: number;
      cumulative_5y_cfo_cr: number;
      cumulative_5y_fcf_cr: number;
      cfo_to_pat_5yr_pct: number;
      is_cash_conversion_superior: boolean;
      fcf_trends: Array<{
        period: string;
        cfo_cr: number;
        pat_cr: number;
        capex_cr: number;
        fcf_cr: number;
        cfo_to_pat_pct?: number;
      }>;
    };
    balance_sheet_efficiency: {
      latest_debt_to_equity: number;
      latest_cwip_to_net_block_pct: number;
      has_significant_capex_trigger: boolean;
      bs_trends: Array<{
        period: string;
        total_equity_cr: number;
        borrowings_cr: number;
        fixed_assets_cr: number;
        cwip_cr: number;
        cwip_to_fixed_assets_pct: number;
        debt_to_equity: number;
      }>;
    };
  };
  projection: ProjectionResult;
  score: ScoreBreakdown;
}

export interface ComparisonItem {
  symbol: string;
  name: string;
  sector: string;
  current_price: number;
  market_cap_cr: number;
  pe_ratio: number;
  roce_pct: number;
  roe_pct: number;
  fcf_yield_pct: number;
  debt_to_equity: number;
  interest_coverage: number;
  sales_cagr_3yr: number;
  cfo_to_pat_5yr: number;
  cwip_to_fixed_assets: number;
  composite_score: number;
  verdict: string;
  dcf_upside_pct: number;
  projected_3yr_irr_pct: number;
  score_breakdown: {
    growth: number;
    cash_quality: number;
    efficiency: number;
    safety: number;
    valuation: number;
  };
}

