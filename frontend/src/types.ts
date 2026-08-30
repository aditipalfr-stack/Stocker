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

export interface DocumentItem {
  ticker: string;
  company_name: string;
  title: string;
  url: string;
  doc_type: string;
  period_or_date?: string;
  discovery_source: string;
  actual_source_host: string;
  actual_source_url: string;
  is_direct_pdf: boolean;
  validation_status: string;
  file_size_bytes?: number;
  fetched_date?: string;
}

export interface DocumentDiscoveryDiagnostics {
  target_annual_reports_count: number;
  annual_reports_found: number;
  target_concalls_count: number;
  concalls_found: number;
  target_presentations_count: number;
  presentations_found: number;
  target_announcements_count: number;
  announcements_found: number;
  invalid_links_rejected: number;
  fallback_sources_used: string[];
  ai_ready_documents_count: number;
  overall_status: string;
}

export interface DocumentLinks {
  annual_reports: DocumentItem[];
  concalls: DocumentItem[];
  presentations: DocumentItem[];
  material_announcements?: DocumentItem[];
  diagnostics?: DocumentDiscoveryDiagnostics;
  checked_at?: string;
}

export interface ProjectionAssumption {
  revenue_growth_rate_pct: number;
  revenue_growth_source?: string;
  target_opm_pct: number;
  opm_source?: string;
  capex_pct_of_sales: number;
  capex_source?: string;
  effective_tax_rate_pct: number;
  tax_source?: string;
  terminal_growth_rate_pct: number;
  discount_rate_wacc_pct: number;
  target_exit_pe: number;
  exit_pe_source?: string;
  projection_confidence?: string;
  forward_drivers_used?: string[];
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
  source_name?: string;
  source_url?: string;
  statement_type?: string;
  fetched_at?: string;
}

export interface FormulaTransparencyItem {
  metric_name: string;
  value: any;
  formula: string;
  inputs: Record<string, any>;
  source: string;
  explanation: string;
}

export interface StockDetail {
  symbol: string;
  name: string;
  sector: string;
  industry: string;
  about: string;
  source_name?: string;
  source_url?: string;
  statement_type?: string;
  fetched_at?: string;
  documents_checked_at?: string;
  ratios: KeyRatios;
  quarters: FinancialStatement;
  profit_loss: FinancialStatement;
  balance_sheet: FinancialStatement;
  cash_flow: FinancialStatement;
  concall_insights: ConcallInsight[];
  annual_report_insights: AnnualReportInsight[];
  documents: DocumentLinks;
  projection: ProjectionResult;
  score: ScoreBreakdown;
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
      cumulative_5y_pat_cr?: number;
      cumulative_5y_cfo_cr?: number;
      cumulative_5y_fcf_cr?: number;
      cfo_to_pat_5yr_pct?: number;
      cash_conversion_quality?: string;
      is_cash_conversion_superior?: boolean;
      is_fcf_directly_reported?: boolean;
      overall_fcf_confidence?: string;
      methodology_notes?: string | string[];
      fcf_trends?: Array<{
        period: string;
        reported_cfo_cr: number | null;
        reported_pat_cr: number | null;
        capex_cr: number | null;
        capex_methodology: string;
        fcf_confidence?: string;
        confidence_reason?: string;
        possible_anomaly_warning?: string | null;
        stocker_derived_fcf_cr: number | null;
        cfo_to_pat_pct: number | null;
      }>;
      fcf_reconciliation?: Array<{
        period: string;
        reported_cfo_cr: number | null;
        reported_pat_cr: number | null;
        capex_cr: number | null;
        capex_methodology: string;
        fcf_confidence?: string;
        confidence_reason?: string;
        possible_anomaly_warning?: string | null;
        stocker_derived_fcf_cr: number | null;
        cfo_to_pat_pct: number | null;
      }>;
    };
    balance_sheet_efficiency: {
      latest_debt_to_equity?: number;
      latest_cwip_to_net_block_pct?: number;
      has_significant_capex_trigger?: boolean;
      bs_trends?: Array<{
        period: string;
        total_equity_cr?: number | null;
        borrowings_cr?: number | null;
        fixed_assets_cr?: number | null;
        cwip_cr?: number | null;
        total_assets_cr?: number | null;
        cwip_to_fixed_assets_pct?: number | null;
        debt_to_equity?: number | null;
      }>;
      borrowings_cr?: number;
      fixed_assets_cr?: number;
      cwip_cr?: number;
      cwip_to_fixed_assets_pct?: number;
      debt_to_equity?: number;
    };
    formula_transparency?: Record<string, FormulaTransparencyItem>;
  };
}

export interface ComparisonItem {
  symbol: string;
  name: string;
  sector: string;
  current_price: number;
  market_cap_cr: number;
  pe_ratio?: number;
  roce_pct?: number;
  roe_pct?: number;
  fcf_yield_pct?: number;
  debt_to_equity?: number;
  sales_cagr_3yr: number;
  cfo_to_pat_5yr: number;
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

export interface RecentChange {
  headline: string;
  category: string;
  detail: string;
  source_doc?: string;
  source_page?: number;
  source_url?: string;
}

export interface GrowthDriver {
  driver_title: string;
  driver_type: string;
  description: string;
  target_timeline?: string;
  stated_outlay_or_value?: string;
  execution_status: string;
  expected_impact?: string;
  source_page?: number;
  source_quote?: string;
  source_url?: string;
  confidence?: number;
}

export interface PromiseVsDeliveryItem {
  area: string;
  management_promise: string;
  promised_in_period: string;
  promise_source_page?: number;
  promise_quote?: string;
  actual_outcome: string;
  actual_in_period: string;
  actual_source_page?: number;
  actual_quote?: string;
  status: 'Delivered' | 'In Progress' | 'Delayed' | 'Missed' | 'Not Enough Data' | 'Not Enough Evidence';
  stocker_analysis: string;
  financial_numbers_check?: string;
  source_url_promise?: string;
  source_url_actual?: string;
  confidence?: number;
}

export interface DemandMomentum {
  summary: string;
  company_specific_metrics: Array<{ metric: string; value: string }>;
  segment_trends: Array<{ segment: string; trend: string }>;
  market_share_and_pricing?: string;
  headwinds_and_risks: string[];
  source_page?: number;
  source_quote?: string;
  source_url?: string;
  confidence?: number;
}

export interface RisksAndCashIssues {
  working_capital_and_receivables?: string;
  debt_and_capex_burden?: string;
  margin_and_cost_pressures?: string;
  execution_and_bottlenecks: string[];
  regulatory_or_legal_headwinds: string[];
  reported_numbers_comparison?: string;
  source_page?: number;
  source_quote?: string;
  source_url?: string;
  confidence?: number;
}

export interface StockerView {
  execution_verdict: 'Strong Execution' | 'Mixed Execution' | 'Weak Execution' | 'Evolving / Watchlist';
  positive_triggers: string[];
  main_risks: string[];
  what_to_watch_next: string[];
  investor_summary: string;
}

export interface ConcallSpecificSummary {
  demand_commentary?: string;
  order_book_or_pipeline?: string;
  margin_outlook?: string;
  execution_updates?: string;
  quarterly_changes_or_shifts?: string;
}

export interface PresentationSpecificSummary {
  major_kpis?: string[];
  expansion_roadmap?: string;
  segment_highlights?: string[];
  forward_targets?: string;
}

export interface AnnouncementSpecificSummary {
  event_summary?: string;
  fundamental_importance?: string;
  business_impact?: string;
  changes_management_guidance?: string;
}

export interface CompanyFactItem {
  metric_name: string;
  stated_value_raw: string;
  numeric_value?: number;
  unit?: string;
  period_or_date: string;
  target_period?: string;
  category: string;
  scope?: string;
  claim_type?: string;
  source_doc_title?: string;
  source_url?: string;
  source_page?: number;
  source_quote?: string;
}

export interface VerifiedFactComparison {
  metric_name: string;
  category: string;
  scope: string;
  latest_period: string;
  latest_value_raw: string;
  latest_numeric?: number;
  prior_period?: string;
  prior_value_raw?: string;
  prior_numeric?: number;
  delta_numeric?: number;
  pct_change?: number;
  unit?: string;
  statement_verification_status: string;
  statement_reported_value?: string;
  management_explanation?: string;
  stocker_assessment: string;
  source_doc_title?: string;
  source_url?: string;
  source_page?: number;
  newer_evidence_available?: boolean;
  newer_evidence_note?: string;
}

export interface InterDocumentKPITrend {
  metric_name: string;
  category: string;
  unit?: string;
  trajectory: string;
  data_points: Array<{
    period: string;
    stated_value: string;
    numeric_value?: number;
    doc_title?: string;
    doc_url?: string;
    doc_type?: string;
  }>;
  latest_vs_prior_change?: string;
  pct_change?: number;
  insight: string;
}

export interface GuidanceVsProjection {
  metric_name: string;
  period_target: string;
  management_guidance_raw: string;
  management_guidance_numeric?: number;
  guidance_source_doc: string;
  guidance_source_url?: string;
  stocker_projected_base?: number;
  stocker_projected_bull?: number;
  stocker_projected_bear?: number;
  current_run_rate_value?: number;
  current_run_rate_period?: string;
  variance_guidance_vs_base_bps?: number;
  stocker_assessment: string;
}

export interface DocumentSummaryItem {
  doc_title: string;
  doc_url: string;
  doc_type?: string;
  period_or_date?: string;
  analyzed_at?: string;
  key_takeaways: string[];
  management_tone?: string;
  guidance_and_capex?: string;
  risks_and_headwinds?: string[];
  capex_or_guidance_highlight?: string;
  extracted_facts?: CompanyFactItem[];
  
  // Document-Type Specialized Extractions
  strategic_priorities?: string;
  capex_and_expansion?: string;
  cash_debt_working_capital?: string;
  major_risks?: string[];
  long_term_targets?: string;
  management_guidance?: string;
  demand_and_orders?: string;
  margin_outlook?: string;
  capex_and_execution?: string;
  quarterly_shifts?: string;
  major_kpis?: string[];
  expansion_roadmap?: string;
  segment_highlights?: string[];
  forward_targets?: string;
  event_summary?: string;
  fundamental_importance?: string;
  business_and_financial_impact?: string;
  guidance_impact?: string;

  concall_specific?: ConcallSpecificSummary;
  presentation_specific?: PresentationSpecificSummary;
  announcement_specific?: AnnouncementSpecificSummary;
}

export interface BusinessOutlookIntelligence {
  symbol: string;
  company_name: string;
  status?: string;
  message?: string;
  latest_document_period: string;
  older_document_period?: string;
  source_documents: Array<{ title: string; url: string; type?: string; period?: string }>;
  ai_provider_used: string;
  model_version?: string;
  extraction_timestamp?: string;
  what_changed_recently: RecentChange[];
  growth_drivers: GrowthDriver[];
  promise_vs_delivery: PromiseVsDeliveryItem[];
  demand_momentum: DemandMomentum;
  risks_and_cash: RisksAndCashIssues;
  stocker_view: StockerView;
  document_summaries?: DocumentSummaryItem[];
  verified_facts?: VerifiedFactComparison[];
  operational_kpi_evolution?: InterDocumentKPITrend[];
  guidance_vs_projections?: GuidanceVsProjection[];
}



