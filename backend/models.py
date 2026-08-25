from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field

class KeyRatios(BaseModel):
    market_cap_cr: float
    current_price: float
    high_low: str = ""
    stock_pe: float
    book_value: float
    dividend_yield_pct: float
    roce_pct: float
    roe_pct: float
    face_value: float
    industry_pe: Optional[float] = None
    debt_to_equity: Optional[float] = 0.0
    interest_coverage: Optional[float] = 0.0
    fcf_yield_pct: Optional[float] = 0.0
    sales_growth_3yr_cagr: Optional[float] = 0.0
    profit_growth_3yr_cagr: Optional[float] = 0.0

class FinancialRow(BaseModel):
    metric: str
    values: Dict[str, Optional[float]]  # e.g. {"Dec 2022": 1500.0, "Mar 2023": 1650.0, ...}

class FinancialStatement(BaseModel):
    periods: List[str]  # e.g. ["Sep 2023", "Dec 2023", "Mar 2024", "Jun 2024"]
    rows: List[FinancialRow]

class ConcallInsight(BaseModel):
    period: str  # e.g. "Q3 FY25 / Dec 2024"
    transcript_url: Optional[str] = None
    presentation_url: Optional[str] = None
    audio_url: Optional[str] = None
    cfo_and_fcf_analysis: str  # Operational cash flow analysis, conversion, working capital
    demand_drivers: List[str]  # Key demand tailwinds, order book, market share
    supply_and_capex: List[str] # Capacity utilization, new plants commissioning, bottleneck fixes
    management_guidance: str    # Revenue / Margin / Volume guidance
    risks_and_headwinds: List[str] # Margin pressure, input costs, regulatory risks
    analyst_sentiment: str     # Bullish / Constructive / Cautious

class AnnualReportInsight(BaseModel):
    year: str  # e.g. "FY 2024"
    report_url: Optional[str] = None
    cfo_fcf_performance: str
    capex_cwip_summary: str
    strategic_priorities: List[str]
    forensic_checklist: Dict[str, str] # e.g. {"promoter_pledge": "0%", "auditor_qualification": "Clean", "related_party_tx": "Normal business course"}

class DocumentLinks(BaseModel):
    annual_reports: List[Dict[str, str]] = [] # [{"name": "FY24 Annual Report", "url": "..."}]
    concalls: List[Dict[str, str]] = []       # [{"name": "Q3 FY25 Concall Transcript", "url": "..."}]
    presentations: List[Dict[str, str]] = []   # [{"name": "Q3 FY25 Investor PPT", "url": "..."}]

class ProjectionAssumption(BaseModel):
    revenue_growth_rate_pct: float = 12.0  # Annual sales growth %
    target_opm_pct: float = 22.0          # Target Operating Profit Margin %
    capex_pct_of_sales: float = 5.0       # Capex as % of sales
    effective_tax_rate_pct: float = 25.0  # Effective Tax %
    terminal_growth_rate_pct: float = 5.0 # Terminal growth rate for DCF
    discount_rate_wacc_pct: float = 12.0  # WACC / Cost of Capital
    target_exit_pe: float = 25.0          # Target Exit P/E multiple

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
    cfo_cr: float
    capex_cr: float
    fcf_cr: float

class ProjectionResult(BaseModel):
    assumptions: ProjectionAssumption
    historical_revenue_cagr_3yr: float
    historical_opm_median: float
    projections: List[YearlyProjection]
    dcf_fair_value_per_share: float
    dcf_upside_pct: float
    target_price_exit_pe: float
    target_price_upside_pct: float
    projected_3yr_irr_cagr_pct: float
    scenario_type: str = "Base Case"

class ScoreBreakdown(BaseModel):
    growth_momentum_score: float      # 0 - 100
    cash_quality_fcf_score: float     # 0 - 100
    capital_efficiency_score: float   # 0 - 100
    balance_sheet_safety_score: float # 0 - 100
    valuation_margin_score: float     # 0 - 100
    total_composite_score: float      # 0 - 100
    verdict: str                      # "High Conviction Buy", "Strong Growth Buy", "Fair Value Hold", "Watchlist", "Avoid"
    investment_thesis: str
    key_catalysts: List[str]
    key_risks: List[str]

class StockSummary(BaseModel):
    symbol: str
    name: str
    sector: str
    industry: str
    current_price: float
    market_cap_cr: float
    pe_ratio: float
    roce_pct: float
    roe_pct: float
    fcf_yield_pct: float
    sales_growth_3yr_pct: float
    cfo_to_pat_5yr_pct: float
    net_debt_to_equity: float
    composite_score: float
    verdict: str
    rank: int
    is_top_conviction: bool = False
    investment_thesis_short: str

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

