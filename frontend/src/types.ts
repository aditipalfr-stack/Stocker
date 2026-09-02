export interface KeyRatios {
  market_cap_cr: number | null;
  current_price: number | null;
  high_low: string | null;
  stock_pe: number | null;
  book_value: number | null;
  dividend_yield_pct: number | null;
  roce_pct: number | null;
  roe_pct: number | null;
  face_value: number | null;
  industry_pe: number | null;
  debt_to_equity: number | null;
  interest_coverage: number | null;
  fcf_yield_pct: number | null;
  sales_growth_3yr_cagr: number | null;
  profit_growth_3yr_cagr: number | null;
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
  transcript_url?: string | null;
  presentation_url?: string | null;
  audio_url?: string | null;
  cfo_and_fcf_analysis: string;
  demand_drivers: string[];
  supply_and_capex: string[];
  management_guidance: string;
  risks_and_headwinds: string[];
  analyst_sentiment: string;
}

export interface AnnualReportInsight {
  year: string;
  report_url?: string | null;
  cfo_fcf_performance: string;
  capex_cwip_summary: string;
  strategic_priorities: string[];
  forensic_checklist: Record<string, string>;
}

export interface DocumentItem {
  ticker: string;
  company_name: string;
  title: string;
  name?: string | null;
  url: string;
  doc_type: string;
  doc_subtype?: string | null;
  event_key?: string | null;
  is_substantive?: boolean;
  is_wrapper?: boolean;
  wrapper_source_url?: string | null;
  ai_eligible?: boolean;
  selected_for_ai?: boolean;
  ai_priority?: number | null;
  selection_reason?: string | null;
  period_or_date?: string | null;
  discovery_source: string;
  discovered_sources?: string[];
  source_aliases?: string[];
  actual_source_host: string;
  actual_source_url: string;
  is_direct_pdf: boolean;
  validation_status: string;
  file_size_bytes?: number | null;
  fetched_date?: string | null;
  checksum_sha256?: string | null;
  doc_key?: string | null;
  ai_status?: 'AI_ANALYZED' | 'NOT_SELECTED' | 'PROCESSING_FAILED' | 'NOT_ANALYZED_YET' | null;
  ai_failure_reason?: string | null;
  sort_timestamp?: string | null;
  materiality_score?: number | null;
  materiality_level?: 'HIGH' | 'MEDIUM' | 'ROUTINE' | null;
  materiality_reason?: string | null;
  content_hash?: string | null;
  extraction_schema_version?: string | null;
  extraction_prompt_version?: string | null;
  cache_status?: 'CACHED_CURRENT' | 'LEGACY_STALE' | 'NEWLY_EXTRACTED' | null;
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
  regulatory_annual_filings?: DocumentItem[];
  concalls: DocumentItem[];
  presentations: DocumentItem[];
  material_announcements?: DocumentItem[];
  brsr_reports?: DocumentItem[];
  other_filings?: DocumentItem[];
  all_documents?: DocumentItem[];
  diagnostics?: DocumentDiscoveryDiagnostics | null;
  checked_at?: string | null;
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
  cfo_cr: number | null;
  capex_cr: number | null;
  fcf_cr: number | null;
}

export interface ProjectionResult {
  assumptions: ProjectionAssumption;
  historical_revenue_cagr_3yr: number | null;
  historical_opm_median: number | null;
  projections: YearlyProjection[];
  dcf_fair_value_per_share: number;
  dcf_upside_pct: number;
  target_price_exit_pe: number;
  target_price_upside_pct: number;
  projected_3yr_irr_cagr_pct: number;
  scenario_type: string;
  data_quality: string;
}

export interface ScoreBreakdown {
  growth_momentum_score: number;
  cash_quality_fcf_score: number;
  capital_efficiency_score: number;
  balance_sheet_safety_score: number;
  valuation_margin_score: number;
  management_execution_impact: number;
  future_visibility_impact: number;
  total_composite_score: number;
  verdict: string;
  data_confidence: string;
  investment_thesis: string;
  key_catalysts: string[];
  key_risks: string[];
}

export interface CompanyTaxonomy {
  sector: string;
  industry: string;
  sub_industry?: string | null;
  source: string;
  classification_method: string;
  confidence: string;
  classification_state: 'COMPLETE' | 'PARTIAL' | 'UNCLASSIFIED' | string;
  classified_at?: string | null;
  updated_at?: string | null;
}

export interface BankTrendItem {
  period: string;
  deposits_cr?: number | null;
  advances_cr?: number | null;
  borrowings_cr?: number | null;
  cd_ratio_pct?: number | null;
  pat_cr?: number | null;
  total_assets_cr?: number | null;
  total_equity_cr?: number | null;
  roa_pct?: number | null;
  roe_pct?: number | null;
  gross_npa_pct?: number | null;
  net_npa_pct?: number | null;
  credit_cost_pct?: number | null;
  cost_to_income_pct?: number | null;
}

export interface BankAnalytics {
  applicability: string;
  latest_period?: string | null;
  deposit_growth_yoy_pct?: number | null;
  deposit_growth_3yr_cagr_pct?: number | null;
  advances_growth_yoy_pct?: number | null;
  advances_growth_3yr_cagr_pct?: number | null;
  credit_deposit_ratio_pct?: number | null;
  roa_pct?: number | null;
  roe_pct?: number | null;
  gross_npa_pct?: number | null;
  net_npa_pct?: number | null;
  cost_to_income_pct?: number | null;
  credit_cost_pct?: number | null;
  trends?: BankTrendItem[];
  provenance?: Record<string, any>;
  unavailable_reasons?: Record<string, string>;
}

export interface StockSummary {
  symbol: string;
  name: string;
  sector: string;
  industry: string;
  sub_industry?: string | null;
  taxonomy?: CompanyTaxonomy | null;
  current_price: number | null;
  market_cap_cr: number | null;
  pe_ratio: number | null;
  roce_pct: number | null;
  roe_pct: number | null;
  fcf_yield_pct: number | null;
  sales_growth_3yr_pct: number | null;
  cfo_to_pat_5yr_pct: number | null;
  net_debt_to_equity: number | null;
  composite_score: number;
  verdict: string;
  data_confidence: string;
  rank: number;
  is_top_conviction: boolean;
  investment_thesis_short: string;
  source_name?: string;
  source_url?: string;
  statement_type?: string;
  financial_business_model?: string;
  bank_analytics?: BankAnalytics;
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
  sub_industry?: string | null;
  taxonomy?: CompanyTaxonomy | null;
  about: string;
  source_name?: string;
  source_url?: string;
  statement_type?: string;
  financial_business_model?: string;
  bank_analytics?: BankAnalytics;
  fetched_at?: string;
  documents_checked_at?: string | null;
  verification_summary?: FinancialVerificationSummary | null;
  financial_truth?: FinancialTruthContainer | null;
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
    financial_business_model?: string;
    bank_analytics?: BankAnalytics;
    bank_metrics?: {
      latest_deposits_cr?: number | null;
      latest_advances_cr?: number | null;
      latest_gross_npa_pct?: number | null;
      latest_net_npa_pct?: number | null;
    };
    quarterly_analysis: {
      trends: Array<{
        period: string;
        sales: number | null;
        operating_profit: number | null;
        opm_pct: number | null;
        net_profit: number | null;
        sales_growth_qoq_pct?: number | null;
        sales_growth_yoy_pct?: number | null;
        operating_profit_growth_qoq_pct?: number | null;
        operating_profit_growth_yoy_pct?: number | null;
        pat_growth_qoq_pct?: number | null;
        pat_growth_yoy_pct?: number | null;
        provenance?: {
          sales?: AnalyticInputProvenance;
          operating_profit?: AnalyticInputProvenance;
          opm_pct?: AnalyticInputProvenance;
          net_profit?: AnalyticInputProvenance;
          sales_growth_qoq?: AnalyticValueWithProvenance;
          sales_growth_yoy?: AnalyticValueWithProvenance;
          operating_profit_growth_qoq?: AnalyticValueWithProvenance;
          operating_profit_growth_yoy?: AnalyticValueWithProvenance;
          pat_growth_qoq?: AnalyticValueWithProvenance;
          pat_growth_yoy?: AnalyticValueWithProvenance;
        };
      }>;
    };
    growth_rates: {
      sales_cagr_3yr?: number | null;
      pat_cagr_3yr?: number | null;
      sales_cagr_5yr?: number | null;
      pat_cagr_5yr?: number | null;
      sales_cagr_10yr?: number | null;
      pat_cagr_10yr?: number | null;
    };
    provenance?: Record<string, AnalyticValueWithProvenance>;
    provenance_summary?: AnalyticProvenanceSummary;
    cash_flow_quality: {
      applicability?: string;
      common_annual_periods?: string[];
      cumulative_5y_pat_cr?: number | null;
      cumulative_5y_cfo_cr?: number | null;
      cumulative_5y_fcf_cr?: number | null;
      cfo_to_pat_5yr_pct?: number | null;
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
        provenance?: {
          cfo?: AnalyticInputProvenance;
          pat?: AnalyticInputProvenance;
        };
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
        provenance?: {
          cfo?: AnalyticInputProvenance;
          pat?: AnalyticInputProvenance;
        };
      }>;
    };
    balance_sheet_efficiency: {
      latest_debt_to_equity?: number | null;
      latest_cwip_to_net_block_pct?: number | null;
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
        provenance?: {
          borrowings?: AnalyticInputProvenance;
          fixed_assets?: AnalyticInputProvenance;
          cwip?: AnalyticInputProvenance;
        };
      }>;
      borrowings_cr?: number | null;
      fixed_assets_cr?: number | null;
      cwip_cr?: number | null;
      cwip_to_fixed_assets_pct?: number | null;
      debt_to_equity?: number | null;
    };
    formula_transparency?: Record<string, FormulaTransparencyItem>;
  };
}

export interface ComparisonItem {
  symbol: string;
  name: string;
  sector: string;
  current_price: number | null;
  market_cap_cr: number | null;
  pe_ratio?: number | null;
  roce_pct?: number | null;
  roe_pct?: number | null;
  fcf_yield_pct?: number | null;
  debt_to_equity?: number | null;
  interest_coverage?: number | null;
  sales_cagr_3yr: number | null;
  cfo_to_pat_5yr: number | null;
  cwip_to_fixed_assets?: number | null;
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
  direction?: 'POSITIVE' | 'NEGATIVE' | 'NEUTRAL' | 'MIXED' | string | null;
  period_comparison?: string | null;
  is_one_off?: boolean;
  why_it_matters?: string | null;
  source_doc?: string | null;
  source_page?: number | null;
  source_url?: string | null;
  source_quote?: string | null;
}

export interface GrowthDriver {
  driver_title: string;
  driver_type: string;
  description: string;
  is_one_off?: boolean;
  target_timeline?: string | null;
  stated_outlay_or_value?: string | null;
  execution_status: string;
  expected_impact?: string | null;
  source_doc_title?: string | null;
  source_page?: number | null;
  source_quote?: string | null;
  source_url?: string | null;
  confidence?: number;
}

export interface PromiseVsDeliveryItem {
  area: string;
  management_promise: string;
  promised_in_period: string;
  promise_source_doc?: string | null;
  source_url_promise?: string | null;
  promise_source_page?: number | null;
  promise_quote?: string | null;
  actual_outcome: string;
  actual_in_period: string;
  actual_source_doc?: string | null;
  source_url_actual?: string | null;
  actual_source_page?: number | null;
  actual_quote?: string | null;
  status: 'Delivered' | 'On Track' | 'Partially Delivered' | 'In Progress' | 'Delayed' | 'Missed' | 'Not Yet Measurable' | 'Not Enough Data' | 'Not Enough Evidence' | string;
  stocker_analysis: string;
  financial_numbers_check?: string | null;
  confidence?: number;
}

export interface DemandMomentum {
  summary: string;
  company_specific_metrics: Array<{ metric?: string | null; value?: string | number | null; [key: string]: unknown }>;
  segment_trends: Array<{ segment?: string | null; trend?: string | null; [key: string]: unknown }>;
  market_share_and_pricing?: string | null;
  headwinds_and_risks: string[];
  source_page?: number | null;
  source_quote?: string | null;
  source_url?: string | null;
  confidence?: number;
}

export interface RisksAndCashIssues {
  working_capital_and_receivables?: string | null;
  debt_and_capex_burden?: string | null;
  margin_and_cost_pressures?: string | null;
  execution_and_bottlenecks: string[];
  regulatory_or_legal_headwinds: string[];
  risk_items?: Array<{
    risk_title?: string;
    risk_category?: string;
    severity?: string;
    is_current_or_potential?: string;
    evidence_statement?: string;
    metric_to_watch?: string;
    source_url?: string | null;
    source_page?: number | null;
  }>;
  reported_numbers_comparison?: string | null;
  source_page?: number | null;
  source_quote?: string | null;
  source_url?: string | null;
  confidence?: number;
}

export interface StockerView {
  execution_verdict: 'Strong Execution' | 'Mixed Execution' | 'Weak Execution' | 'Evolving / Watchlist' | string;
  business_momentum?: string | null;
  financial_quality?: string | null;
  evidence_confidence?: string | null;
  positive_triggers: string[];
  main_risks: string[];
  what_to_watch_next: string[];
  investor_summary: string;
}

export interface BusinessQuality {
  business_model_summary?: string;
  segment_mix?: Array<{ segment?: string; share_pct?: number; growth_pct?: number; [key: string]: unknown }>;
  geography_mix?: Array<{ region?: string; share_pct?: number; [key: string]: unknown }>;
  revenue_characteristics?: Record<string, unknown>;
  source_page?: number | null;
  source_quote?: string | null;
  source_url?: string | null;
  confidence?: number;
}

export interface CompetitivePosition {
  moat_type?: string;
  market_share_trend?: string | null;
  pricing_power_assessment?: string | null;
  key_advantages?: string[];
  competitive_threats?: string[];
  source_page?: number | null;
  source_quote?: string | null;
  source_url?: string | null;
  confidence?: number;
}

export interface CapitalAllocationAudit {
  capex_efficiency?: string | null;
  reinvestment_rate?: string | null;
  ma_track_record?: string | null;
  shareholder_returns?: string | null;
  capital_deployed_vs_returns?: string | null;
  source_page?: number | null;
  source_quote?: string | null;
  source_url?: string | null;
  confidence?: number;
}

export interface GovernanceAndForensicWatch {
  auditor_observations?: string | null;
  related_party_transactions?: string | null;
  contingent_liabilities?: string | null;
  working_capital_anomalies?: string | null;
  regulatory_or_legal_risks?: string[];
  promoter_and_shareholding_notes?: string | null;
  source_page?: number | null;
  source_quote?: string | null;
  source_url?: string | null;
  confidence?: number;
}

export interface ConcallSpecificSummary {
  demand_commentary?: string | null;
  order_book_or_pipeline?: string | null;
  margin_outlook?: string | null;
  execution_updates?: string | null;
  quarterly_changes_or_shifts?: string | null;
}

export interface PresentationSpecificSummary {
  major_kpis?: string[];
  expansion_roadmap?: string | null;
  segment_highlights?: string[];
  forward_targets?: string | null;
}

export interface AnnouncementSpecificSummary {
  event_summary?: string | null;
  fundamental_importance?: string | null;
  business_impact?: string | null;
  changes_management_guidance?: string | null;
}

export interface CompanyFactItem {
  metric_name: string;
  stated_value_raw: string;
  numeric_value?: number | null;
  unit?: string | null;
  period_or_date: string;
  target_period?: string | null;
  category: string;
  scope?: string;
  claim_type?: string;
  source_doc_title?: string | null;
  source_url?: string | null;
  source_page?: number | null;
  source_quote?: string | null;
  id?: number;
  symbol?: string;
  doc_title?: string;
  doc_url?: string;
  doc_type?: string;
  extracted_at?: string;
}

export interface VerifiedFactComparison {
  metric_name: string;
  category: string;
  scope: string;
  latest_period: string;
  latest_value_raw: string;
  latest_numeric?: number | null;
  prior_period?: string | null;
  prior_value_raw?: string | null;
  prior_numeric?: number | null;
  delta_numeric?: number | null;
  pct_change?: number | null;
  unit?: string | null;
  statement_verification_status: string;
  statement_reported_value?: string | null;
  management_explanation?: string | null;
  stocker_assessment: string;
  source_doc_title?: string | null;
  source_url?: string | null;
  source_page?: number | null;
  newer_evidence_available?: boolean;
  newer_evidence_note?: string | null;
}

export interface InterDocumentKPITrend {
  metric_name: string;
  category: string;
  unit?: string | null;
  trajectory: string;
  data_points: Array<{
    period: string;
    stated_value: string;
    numeric_value?: number | null;
    doc_title?: string | null;
    doc_url?: string | null;
    doc_type?: string | null;
  }>;
  latest_vs_prior_change?: string | null;
  pct_change?: number | null;
  insight: string;
}

export interface GuidanceVsProjection {
  metric_name: string;
  period_target: string;
  management_guidance_raw: string;
  management_guidance_numeric?: number | null;
  guidance_source_doc: string;
  guidance_source_url?: string | null;
  stocker_projected_base?: number | null;
  stocker_projected_bull?: number | null;
  stocker_projected_bear?: number | null;
  current_run_rate_value?: number | null;
  current_run_rate_period?: string | null;
  variance_guidance_vs_base_bps?: number | null;
  stocker_assessment: string;
}

export interface DocumentSummaryItem {
  doc_title: string;
  doc_url: string;
  doc_key?: string | null;
  doc_type?: string | null;
  period_or_date?: string | null;
  analyzed_at?: string | null;
  status?: 'success' | 'failed' | null;
  error?: string | null;
  key_takeaways: string[];
  management_tone?: string | null;
  guidance_and_capex?: string | null;
  risks_and_headwinds?: string[];
  capex_or_guidance_highlight?: string | null;
  extracted_facts?: CompanyFactItem[];
  
  // Document-Type Specialized Extractions
  strategic_priorities?: string | null;
  capex_and_expansion?: string | null;
  cash_debt_working_capital?: string | null;
  major_risks?: string[];
  long_term_targets?: string | null;
  management_guidance?: string | null;
  demand_and_orders?: string | null;
  margin_outlook?: string | null;
  capex_and_execution?: string | null;
  quarterly_shifts?: string | null;
  major_kpis?: string[];
  expansion_roadmap?: string | null;
  segment_highlights?: string[];
  forward_targets?: string | null;
  event_summary?: string | null;
  fundamental_importance?: string | null;
  business_and_financial_impact?: string | null;
  guidance_impact?: string | null;

  concall_specific?: ConcallSpecificSummary | null;
  presentation_specific?: PresentationSpecificSummary | null;
  announcement_specific?: AnnouncementSpecificSummary | null;
  
  content_hash?: string | null;
  extraction_schema_version?: string | null;
  extraction_prompt_version?: string | null;
  provider?: string | null;
  model?: string | null;
  cache_status?: 'CACHED_CURRENT' | 'LEGACY_STALE' | 'NEWLY_EXTRACTED' | null;
}

export interface SourceDocumentReference {
  title: string;
  url: string;
  symbol?: string;
  type?: string | null;
  period?: string | null;
  ticker?: string;
  company_name?: string;
  name?: string | null;
  doc_type?: string;
  period_or_date?: string | null;
  discovery_source?: string;
  actual_source_host?: string;
  actual_source_url?: string;
  is_direct_pdf?: boolean;
  validation_status?: string;
  is_valid?: boolean | number;
  file_size_bytes?: number | null;
  fetched_date?: string | null;
  checksum_sha256?: string | null;
  added_at?: string;
}

export interface DocumentEvidenceItem {
  id: string;
  symbol: string;
  evidence_type: string;
  title: string;
  normalized_topic: string;
  statement: string;
  source_document_type: string;
  source_document_title: string;
  source_url: string;
  source_period?: string | null;
  source_date?: string | null;
  page?: number | null;
  section?: string | null;
  evidence_quote?: string | null;
  extraction_method?: string;
  confidence?: string;
  status?: string;
  created_at?: string | null;
}

export interface ManagementGuidanceItem {
  id?: string | null;
  metric_or_topic: string;
  guidance_text: string;
  quantified_value?: number | null;
  quantified_range_min?: number | null;
  quantified_range_max?: number | null;
  unit?: string | null;
  target_period: string;
  direction?: string | null;
  source_document_title: string;
  source_document_url?: string | null;
  source_date_or_period?: string | null;
  confidence?: string;
  status: 'MET' | 'PARTIALLY_MET' | 'MISSED' | 'NOT_YET_DUE' | 'NOT_COMPARABLE' | 'INSUFFICIENT_EVIDENCE';
  actual_reported_value?: number | null;
  actual_reported_period?: string | null;
  actual_reported_source?: string | null;
  comparison_detail?: string | null;
}

export interface BusinessOutlookIntelligence {
  symbol: string;
  company_name: string;
  status?: string | null;
  message?: string | null;
  latest_document_period: string;
  older_document_period?: string | null;
  source_documents: SourceDocumentReference[];
  ai_provider_used: string;
  model_version?: string | null;
  extraction_timestamp?: string | null;
  what_changed_recently: RecentChange[];
  growth_drivers: GrowthDriver[];
  promise_vs_delivery: PromiseVsDeliveryItem[];
  demand_momentum: DemandMomentum;
  risks_and_cash: RisksAndCashIssues;
  stocker_view: StockerView;
  business_quality?: BusinessQuality;
  competitive_position?: CompetitivePosition;
  capital_allocation?: CapitalAllocationAudit;
  governance_watch?: GovernanceAndForensicWatch;
  document_summaries?: DocumentSummaryItem[];
  verified_facts?: VerifiedFactComparison[];
  operational_kpi_evolution?: InterDocumentKPITrend[];
  guidance_vs_projections?: GuidanceVsProjection[];
  evidence_items?: DocumentEvidenceItem[];
  management_guidance_items?: ManagementGuidanceItem[];
  source_documents_hash?: string | null;
  analysis_version?: string;
  staleness_status?: 'fresh' | 'stale' | 'not_analyzed' | 'not_checked';
  financial_business_model?: string;
}

export type BusinessAnalysisIntelligence = BusinessOutlookIntelligence;

export interface SourceFilingsResponse {
  symbol: string;
  company_name: string;
  documents: DocumentLinks;
  summaries: Record<string, DocumentSummaryItem>;
  has_company_analysis?: boolean;
}

export interface CompanySearchResult {
  symbol: string;
  company_name: string;
  nse_symbol?: string | null;
  bse_code?: string | null;
  isin?: string | null;
  exchange?: string | null;
  sector?: string | null;
  industry?: string | null;
  already_added: boolean;
  source?: string;
  match_score?: number | null;
}

export interface CompanySearchResponse {
  query: string;
  count: number;
  results: CompanySearchResult[];
}

export interface ResearchLifecycleStatus {
  symbol: string;
  identity: 'unresolved' | 'resolved' | 'officially_verified';
  financial_data: 'missing' | 'ready' | 'stale' | 'error';
  deterministic_analysis: 'not_ready' | 'ready';
  official_verification: 'not_run' | 'partial' | 'verified' | 'discrepancy';
  source_filings: 'not_searched' | 'partial' | 'ready' | 'error';
  business_analysis: 'not_run' | 'running' | 'ready' | 'stale' | 'error';
  projection: 'unavailable' | 'historical_only' | 'evidence_enriched' | 'stale';
  investment_score: 'unavailable' | 'provisional' | 'evidence_enriched' | 'incomplete';
  filing_count: number;
  financial_data_updated_at?: string | null;
  filings_checked_at?: string | null;
  business_analysis_updated_at?: string | null;
  projection_updated_at?: string | null;
  notes?: string[];
}

export interface AddCompanyResponse {
  success: boolean;
  message: string;
  symbol: string;
  company_name: string;
  already_existed: boolean;
  stock: StockDetail | null;
  research_status: ResearchLifecycleStatus | null;
}

export interface DiscoverFilingsResponse {
  symbol: string;
  company_name: string;
  filing_count: number;
  documents_checked_at: string;
  research_status: ResearchLifecycleStatus | null;
}

export interface CompanyRegistryItem {
  id?: number;
  symbol: string;
  company_name: string;
  nse_symbol?: string | null;
  bse_code?: string | null;
  isin?: string | null;
  exchange?: string | null;
  sector?: string | null;
  industry?: string | null;
  aliases?: string[];
  is_active?: boolean;
  in_universe?: boolean;
  already_added?: boolean;
  source?: string;
  source_last_verified_at?: string | null;
  identity_source_name?: string | null;
  identity_source_url?: string | null;
  identity_verified_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface FinancialVerificationItem {
  id?: number;
  symbol: string;
  metric_name: string;
  canonical_metric: string;
  period: string;
  canonical_period: string;
  scope: string;
  screener_value?: number | null;
  official_value?: number | null;
  variance_abs?: number | null;
  variance_pct?: number | null;
  unit: string;
  currency: string;
  status: "VERIFIED" | "DISCREPANCY" | "NOT_COMPARABLE" | "OFFICIAL_SOURCE_MISSING" | "SCREENER_VALUE_MISSING" | "INSUFFICIENT_EVIDENCE";
  tolerance_used?: number | null;
  screener_source_url?: string | null;
  official_source_url?: string | null;
  official_source_name?: string | null;
  official_document_id?: string | null;
  notes?: string | null;
  verified_at?: string | null;
}

export interface FinancialVerificationSummary {
  symbol: string;
  overall_status: "VERIFIED" | "DISCREPANCY" | "NOT_COMPARABLE" | "OFFICIAL_SOURCE_MISSING" | "UNVERIFIED";
  total_metrics_checked: number;
  verified_count: number;
  discrepancy_count: number;
  not_comparable_count: number;
  missing_source_count: number;
  authoritative_source_name?: string | null;
  identity_source_name?: string | null;
  identity_source_url?: string | null;
  identity_verified_at?: string | null;
  isin?: string | null;
  nse_symbol?: string | null;
  bse_code?: string | null;
  exchange?: string | null;
  last_verified_at?: string | null;
  confidence_score: number;
  unavailable_reason?: string | null;
}

export interface FinancialVerificationResponse {
  symbol: string;
  company_name: string;
  summary: FinancialVerificationSummary;
  records: FinancialVerificationItem[];
}

export interface CanonicalFinancialFact {
  symbol: string;
  canonical_metric: string;
  display_metric: string;
  period: string;
  canonical_period: string;
  scope: string;
  value: number | null;
  unit: string;
  currency: string;
  verification_status: "VERIFIED" | "DISCREPANCY" | "NOT_COMPARABLE" | "INSUFFICIENT_EVIDENCE" | "OFFICIAL_SOURCE_MISSING" | "SCREENER_VALUE_MISSING" | "UNVERIFIED";
  selected_source_type: "official" | "screener" | "unverified";
  selected_source_name?: string | null;
  selected_source_url?: string | null;
  screener_value?: number | null;
  official_value?: number | null;
  difference_absolute?: number | null;
  difference_pct?: number | null;
  confidence: "High" | "Moderate" | "Low" | "Unverified";
  computed_at: string;
}

export interface FinancialTruthContainer {
  symbol: string;
  facts: CanonicalFinancialFact[];
  coverage: {
    total_tracked_facts: number;
    verified_facts: number;
    discrepant_facts: number;
    unverified_facts: number;
    coverage_ratio: number;
  };
  discrepancies_count: number;
  verified_count: number;
  unverified_count: number;
  last_computed_at: string;
  input_financial_version?: string | null;
  verification_version?: string | null;
}

export interface AnalyticInputProvenance {
  canonical_metric: string;
  period: string;
  canonical_period: string;
  scope: string;
  value: number | null;
  unit?: string;
  currency?: string;
  source_type: "official" | "screener" | "unavailable";
  verification_status: "VERIFIED" | "DISCREPANCY" | "NOT_COMPARABLE" | "INSUFFICIENT_EVIDENCE" | "OFFICIAL_SOURCE_MISSING" | "SCREENER_VALUE_MISSING" | "UNVERIFIED";
  selected_source_name?: string | null;
  selected_source_url?: string | null;
  confidence: "High" | "Moderate" | "Low" | "Unverified";
  has_discrepancy: boolean;
}

export interface AnalyticValueWithProvenance {
  value: number | null;
  quality: "verified" | "mixed" | "standardized" | "discrepant" | "insufficient";
  has_discrepancy: boolean;
  inputs: AnalyticInputProvenance[];
}

export interface AnalyticProvenanceSummary {
  verified_inputs: number;
  standardized_inputs: number;
  discrepancy_inputs: number;
  unavailable_inputs: number;
  overall_quality: "verified" | "mixed" | "standardized" | "discrepant" | "insufficient";
}
