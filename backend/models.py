from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field

class KeyRatios(BaseModel):
    market_cap_cr: Optional[float] = None
    current_price: Optional[float] = None
    high_low: Optional[str] = ""
    stock_pe: Optional[float] = None
    book_value: Optional[float] = None
    dividend_yield_pct: Optional[float] = None
    roce_pct: Optional[float] = None
    roe_pct: Optional[float] = None
    face_value: Optional[float] = None
    industry_pe: Optional[float] = None
    debt_to_equity: Optional[float] = None
    interest_coverage: Optional[float] = None
    fcf_yield_pct: Optional[float] = None
    sales_growth_3yr_cagr: Optional[float] = None
    profit_growth_3yr_cagr: Optional[float] = None

class FinancialRow(BaseModel):
    metric: str
    values: Dict[str, Optional[float]]  # e.g. {"Jun 2023": 207559.0, "Sep 2023": 231886.0, ...}

class FinancialStatement(BaseModel):
    periods: List[str]  # e.g. ["Jun 2023", "Sep 2023", ..., "Jun 2026"]
    rows: List[FinancialRow]

class ConcallInsight(BaseModel):
    period: str
    transcript_url: Optional[str] = None
    presentation_url: Optional[str] = None
    audio_url: Optional[str] = None
    cfo_and_fcf_analysis: str
    demand_drivers: List[str]
    supply_and_capex: List[str]
    management_guidance: str
    risks_and_headwinds: List[str]
    analyst_sentiment: str

class AnnualReportInsight(BaseModel):
    year: str
    report_url: Optional[str] = None
    cfo_fcf_performance: str
    capex_cwip_summary: str
    strategic_priorities: List[str]
    forensic_checklist: Dict[str, str]

class DocumentItem(BaseModel):
    ticker: str = ""
    company_name: str = ""
    title: str = ""
    name: Optional[str] = None # Backward compatibility alias for title
    url: str = ""
    doc_type: str = "general" # "annual_report", "concall_transcript", "presentation", "announcement"
    period_or_date: Optional[str] = None
    discovery_source: str = "Screener.in" # "Screener.in", "BSE", "NSE", "Company IR"
    actual_source_host: str = "bseindia.com"
    actual_source_url: str = ""
    is_direct_pdf: bool = True
    validation_status: str = "Valid" # "Valid", "Invalid", "Unchecked"
    file_size_bytes: Optional[int] = None
    fetched_date: Optional[str] = None
    checksum_sha256: Optional[str] = None

    def model_post_init(self, __context: Any) -> None:
        if not self.title and self.name:
            self.title = self.name
        elif not self.name and self.title:
            self.name = self.title
        if not self.actual_source_url and self.url:
            self.actual_source_url = self.url

class DocumentDiscoveryDiagnostics(BaseModel):
    target_annual_reports_count: int = 3
    annual_reports_found: int = 0
    target_concalls_count: int = 6
    concalls_found: int = 0
    target_presentations_count: int = 6
    presentations_found: int = 0
    target_announcements_count: int = 8
    announcements_found: int = 0
    invalid_links_rejected: int = 0
    fallback_sources_used: List[str] = []
    ai_ready_documents_count: int = 0
    overall_status: str = "Ready" # "Ready", "Partial", "Missing"

class DocumentLinks(BaseModel):
    annual_reports: List[DocumentItem] = []
    concalls: List[DocumentItem] = []
    presentations: List[DocumentItem] = []
    material_announcements: List[DocumentItem] = []
    diagnostics: Optional[DocumentDiscoveryDiagnostics] = None
    checked_at: Optional[str] = None

class ProjectionAssumption(BaseModel):
    revenue_growth_rate_pct: float = 12.0
    revenue_growth_source: str = "Historical CAGR" # "Historical CAGR", "Management Guidance", "Stocker Derived", "User Override"
    target_opm_pct: float = 22.0
    opm_source: str = "Historical Median"
    capex_pct_of_sales: float = 5.0
    capex_source: str = "Historical Average"
    effective_tax_rate_pct: float = 25.0
    tax_source: str = "Historical Tax/PBT"
    terminal_growth_rate_pct: float = 5.0
    discount_rate_wacc_pct: float = 12.0
    target_exit_pe: float = 25.0
    exit_pe_source: str = "Historical Median P/E"
    projection_confidence: str = "Moderate" # "High", "Moderate", "Low"
    forward_drivers_used: List[str] = []

class YearlyProjection(BaseModel):
    year: str
    revenue_cr: float
    opm_pct: float
    ebitda_cr: float
    depreciation_cr: float
    interest_cr: float
    pbt_cr: float
    tax_cr: float
    pat_cr: float
    eps: float
    cfo_cr: Optional[float] = None
    capex_cr: Optional[float] = None
    fcf_cr: Optional[float] = None

class ProjectionResult(BaseModel):
    assumptions: ProjectionAssumption
    historical_revenue_cagr_3yr: Optional[float] = None
    historical_opm_median: Optional[float] = None
    projections: List[YearlyProjection]
    dcf_fair_value_per_share: float
    dcf_upside_pct: float
    target_price_exit_pe: float
    target_price_upside_pct: float
    projected_3yr_irr_cagr_pct: float
    scenario_type: str = "Base Case"
    data_quality: str = "High"

class ScoreBreakdown(BaseModel):
    growth_momentum_score: float      # 0 - 100
    cash_quality_fcf_score: float     # 0 - 100
    capital_efficiency_score: float   # 0 - 100
    balance_sheet_safety_score: float # 0 - 100
    valuation_margin_score: float     # 0 - 100
    management_execution_impact: float = 0.0 # Bonus/penalty based on Promise vs Delivery
    future_visibility_impact: float = 0.0    # Bonus from active capex / orders
    total_composite_score: float      # 0 - 100
    verdict: str
    data_confidence: str = "High"     # "High", "Moderate", "Low / Incomplete"
    investment_thesis: str
    key_catalysts: List[str]
    key_risks: List[str]

class StockSummary(BaseModel):
    symbol: str
    name: str
    sector: str
    industry: str
    current_price: Optional[float] = None
    market_cap_cr: Optional[float] = None
    pe_ratio: Optional[float] = None
    roce_pct: Optional[float] = None
    roe_pct: Optional[float] = None
    fcf_yield_pct: Optional[float] = None
    sales_growth_3yr_pct: Optional[float] = None
    cfo_to_pat_5yr_pct: Optional[float] = None
    net_debt_to_equity: Optional[float] = None
    composite_score: float
    verdict: str
    data_confidence: str = "High"
    rank: int
    is_top_conviction: bool = False
    investment_thesis_short: str
    source_name: str = "Screener.in"
    source_url: str = ""
    statement_type: str = "consolidated"
    fetched_at: str = ""

class StockDetail(BaseModel):
    symbol: str
    name: str
    sector: str
    industry: str
    about: str
    ratios: KeyRatios
    quarters: FinancialStatement
    profit_loss: FinancialStatement
    balance_sheet: FinancialStatement
    cash_flow: FinancialStatement
    concall_insights: List[ConcallInsight]
    annual_report_insights: List[AnnualReportInsight]
    documents: DocumentLinks
    analytics: Dict[str, Any]
    projection: ProjectionResult
    score: ScoreBreakdown
    source_name: str = "Screener.in"
    source_url: str = ""
    statement_type: str = "consolidated"
    fetched_at: str = ""
    documents_checked_at: Optional[str] = None
    verification_summary: Optional["FinancialVerificationSummary"] = None
    financial_truth: Optional["FinancialTruthContainer"] = None

# =============================================================================
# COMPANY REGISTRY & IDENTITY MODELS (PHASE A & B)
# =============================================================================

class CompanyRegistryItem(BaseModel):
    id: Optional[int] = None
    symbol: str
    company_name: str
    nse_symbol: Optional[str] = None
    bse_code: Optional[str] = None
    isin: Optional[str] = None
    exchange: Optional[str] = None
    sector: Optional[str] = "Broad Market"
    industry: Optional[str] = "Indian Equities"
    aliases: List[str] = []
    is_active: bool = True
    in_universe: bool = True
    already_added: bool = False
    source: str = "seed_reference"
    source_last_verified_at: Optional[str] = None
    identity_source_name: Optional[str] = None
    identity_source_url: Optional[str] = None
    identity_verified_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class CompanySearchResult(BaseModel):
    symbol: str
    company_name: str
    nse_symbol: Optional[str] = None
    bse_code: Optional[str] = None
    isin: Optional[str] = None
    exchange: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    already_added: bool = False
    source: str = "local" # "local", "screener_search", "nse_master", "bse_master", "unresolved_input"
    match_score: Optional[int] = None

class CompanySearchResponse(BaseModel):
    query: str
    count: int
    results: List[CompanySearchResult]

class ResearchLifecycleStatus(BaseModel):
    symbol: str
    identity: str # "unresolved", "resolved", "officially_verified"
    financial_data: str # "missing", "ready", "stale", "error"
    deterministic_analysis: str # "not_ready", "ready"
    official_verification: str # "not_run", "partial", "verified", "discrepancy"
    source_filings: str # "not_searched", "partial", "ready", "error"
    business_analysis: str # "not_run", "running", "ready", "stale", "error"
    projection: str # "unavailable", "historical_only", "evidence_enriched", "stale"
    investment_score: str # "unavailable", "provisional", "evidence_enriched", "incomplete"
    
    filing_count: int = 0
    financial_data_updated_at: Optional[str] = None
    filings_checked_at: Optional[str] = None
    business_analysis_updated_at: Optional[str] = None
    projection_updated_at: Optional[str] = None
    notes: List[str] = []

class AddCompanyRequest(BaseModel):
    query: Optional[str] = None
    symbol: Optional[str] = None

class AddCompanyResponse(BaseModel):
    success: bool
    message: str
    symbol: str
    company_name: str
    already_existed: bool = False
    stock: Optional[StockDetail] = None
    research_status: Optional[ResearchLifecycleStatus] = None

class DiscoverFilingsResponse(BaseModel):
    symbol: str
    company_name: str
    filing_count: int
    documents_checked_at: str
    research_status: Optional[ResearchLifecycleStatus] = None

# =============================================================================
# FINANCIAL VERIFICATION MODELS (PHASE B)
# =============================================================================

class FinancialVerificationItem(BaseModel):
    id: Optional[int] = None
    symbol: str
    metric_name: str
    canonical_metric: str
    period: str
    canonical_period: str
    scope: str
    screener_value: Optional[float] = None
    official_value: Optional[float] = None
    variance_abs: Optional[float] = None
    variance_pct: Optional[float] = None
    unit: str = "₹ Cr"
    currency: str = "INR"
    status: str # "VERIFIED", "DISCREPANCY", "NOT_COMPARABLE", "OFFICIAL_SOURCE_MISSING", "SCREENER_VALUE_MISSING", "INSUFFICIENT_EVIDENCE"
    tolerance_used: Optional[float] = None
    screener_source_url: Optional[str] = None
    official_source_url: Optional[str] = None
    official_source_name: Optional[str] = None
    official_document_id: Optional[str] = None
    notes: Optional[str] = None
    verified_at: Optional[str] = None

class FinancialVerificationSummary(BaseModel):
    symbol: str
    overall_status: str # "VERIFIED", "DISCREPANCY", "NOT_COMPARABLE", "OFFICIAL_SOURCE_MISSING", "UNVERIFIED"
    total_metrics_checked: int = 0
    verified_count: int = 0
    discrepancy_count: int = 0
    not_comparable_count: int = 0
    missing_source_count: int = 0
    authoritative_source_name: Optional[str] = None
    identity_source_name: Optional[str] = None
    identity_source_url: Optional[str] = None
    identity_verified_at: Optional[str] = None
    isin: Optional[str] = None
    nse_symbol: Optional[str] = None
    bse_code: Optional[str] = None
    exchange: Optional[str] = None
    last_verified_at: Optional[str] = None
    confidence_score: float = 1.0
    unavailable_reason: Optional[str] = None

class FinancialVerificationResponse(BaseModel):
    symbol: str
    company_name: str
    summary: FinancialVerificationSummary
    records: List[FinancialVerificationItem]

# =============================================================================
# CANONICAL FINANCIAL TRUTH MODELS (PHASE 2A)
# =============================================================================

class CanonicalFinancialFact(BaseModel):
    symbol: str
    canonical_metric: str # e.g. "REVENUE", "OPERATING_PROFIT", "OPM_PCT", "NET_PROFIT", "BASIC_EPS", "CFO", "BORROWINGS", "FIXED_ASSETS", "CWIP"
    display_metric: str # e.g. "Revenue / Sales", "Operating Profit", "Operating Profit Margin %", "Net Profit", "Basic EPS"
    period: str # e.g. "Jun 2026", "FY26"
    canonical_period: str # e.g. "2026-Q1", "2026-FY"
    scope: str # "Consolidated" or "Standalone"
    value: Optional[float] = None # Canonical usable truth value (None if missing, never 0.0)
    unit: str = "₹ Cr" # "₹ Cr", "₹ / Share", "%"
    currency: str = "INR"
    selected_source_type: str # "official", "screener", "stocker_calculation", "unverified"
    selected_source_name: Optional[str] = None
    selected_source_url: Optional[str] = None
    screener_value: Optional[float] = None
    official_value: Optional[float] = None
    verification_status: str # "VERIFIED", "DISCREPANCY", "NOT_COMPARABLE", "INSUFFICIENT_EVIDENCE", "OFFICIAL_SOURCE_MISSING", "SCREENER_VALUE_MISSING", "UNVERIFIED"
    difference_absolute: Optional[float] = None
    difference_pct: Optional[float] = None
    confidence: str = "Unverified" # "High", "Moderate", "Low", "Unverified"
    provenance_note: str = ""
    verified_at: Optional[str] = None
    computed_at: Optional[str] = None

class VerificationCoverageSummary(BaseModel):
    symbol: str
    target_facts_count: int = 0
    officially_verified_count: int = 0
    discrepancy_count: int = 0
    not_comparable_count: int = 0
    insufficient_evidence_count: int = 0
    official_source_missing_count: int = 0
    screener_value_missing_count: int = 0
    unverified_count: int = 0
    coverage_pct: float = 0.0
    overall_truth_state: str = "UNVERIFIED" # "VERIFIED", "DISCREPANCY", "PARTIAL", "UNVERIFIED"

class FinancialTruthContainer(BaseModel):
    symbol: str
    facts: List[CanonicalFinancialFact] = []
    coverage: VerificationCoverageSummary
    discrepancies_count: int = 0
    verified_count: int = 0
    unverified_count: int = 0
    last_computed_at: str
    input_financial_version: Optional[str] = None
    verification_version: Optional[str] = None

# =============================================================================
# ANALYTIC PROVENANCE MODELS (PHASE 2B)
# =============================================================================

class AnalyticInputProvenance(BaseModel):
    canonical_metric: str
    period: str
    canonical_period: str
    scope: str = "Consolidated"
    value: Optional[float] = None
    source_type: str = "screener"  # "official" | "screener" | "unavailable"
    verification_status: str = "UNVERIFIED"  # "VERIFIED" | "DISCREPANCY" | "NOT_COMPARABLE" | "INSUFFICIENT_EVIDENCE" | "OFFICIAL_SOURCE_MISSING" | "SCREENER_VALUE_MISSING" | "UNVERIFIED"
    selected_source_name: Optional[str] = None
    selected_source_url: Optional[str] = None
    confidence: str = "Unverified"  # "High" | "Moderate" | "Low" | "Unverified"
    has_discrepancy: bool = False

class AnalyticValueWithProvenance(BaseModel):
    value: Optional[float] = None
    quality: str = "standardized"  # "verified" | "mixed" | "standardized" | "discrepant" | "insufficient"
    has_discrepancy: bool = False
    inputs: List[AnalyticInputProvenance] = []

class AnalyticProvenanceSummary(BaseModel):
    verified_inputs: int = 0
    standardized_inputs: int = 0
    discrepancy_inputs: int = 0
    unavailable_inputs: int = 0
    overall_quality: str = "standardized"  # "verified" | "mixed" | "standardized" | "discrepant" | "insufficient"

# Rebuild models for forward references
FinancialTruthContainer.model_rebuild()
StockDetail.model_rebuild()
FinancialVerificationResponse.model_rebuild()
AnalyticValueWithProvenance.model_rebuild()

