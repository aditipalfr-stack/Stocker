from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, model_validator

# 1. WHAT CHANGED RECENTLY
class RecentChange(BaseModel):
    headline: str = Field(description="Short, impactful headline of what changed")
    category: str = Field(description="Category e.g. Margins / Funding Costs, Asset Quality / Provisions, Business Mix, Demand / Volumes, Capex / Expansion, Debt / Cash, Strategic / M&A, Regulatory / Policy")
    detail: str = Field(description="Plain English context, magnitude, and why the change matters fundamentally")
    direction: Optional[str] = Field(default="NEUTRAL", description="Direction of change: POSITIVE | NEGATIVE | NEUTRAL | MIXED")
    period_comparison: Optional[str] = Field(default=None, description="Comparable period basis e.g. Q1 FY27 vs Q4 FY26 / FY26 vs FY25")
    is_one_off: bool = Field(default=False, description="Whether this change is driven by a non-recurring or one-off event (e.g. tax refund interest)")
    why_it_matters: Optional[str] = Field(default=None, description="Why this development is fundamentally material for investors")
    source_doc: Optional[str] = None
    source_page: Optional[int] = None
    source_url: Optional[str] = None
    source_quote: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def adapt_recent_change(cls, values: Any) -> Any:
        if isinstance(values, dict):
            if "source_doc_title" in values and not values.get("source_doc"):
                values["source_doc"] = values["source_doc_title"]
            if "delta_headline" in values and not values.get("headline"):
                values["headline"] = values["delta_headline"]
            if "page_number" in values and not values.get("source_page"):
                values["source_page"] = values["page_number"]
            if "quote" in values and not values.get("source_quote"):
                values["source_quote"] = values["quote"]
        return values

# 2. MANAGEMENT PLAN & GROWTH DRIVERS
class GrowthDriver(BaseModel):
    driver_title: str = Field(description="Initiative / loan vertical / plant / program / market expansion name")
    driver_type: str = Field(default="Structural Driver", description="Type: Structural Driver | Cyclical Driver | Management Action | External Environment | One-off Driver | Capacity / Plant | Product / Market")
    description: str = Field(description="What is driving growth/performance and why")
    is_one_off: bool = Field(default=False, description="Whether this driver is a one-off / non-recurring development")
    target_timeline: Optional[str] = Field(default=None, description="Stated target timeline or COD if mentioned")
    stated_outlay_or_value: Optional[str] = Field(default=None, description="Stated capex outlay or contract value in ₹ Cr or original currency")
    execution_status: str = Field(default="In Progress", description="Current execution progress stated by company")
    expected_impact: Optional[str] = Field(default=None, description="Management stated business impact (do not fabricate)")
    source_doc_title: Optional[str] = None
    source_page: Optional[int] = None
    source_quote: Optional[str] = None
    source_url: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    @model_validator(mode="before")
    @classmethod
    def adapt_growth_driver(cls, values: Any) -> Any:
        if isinstance(values, dict):
            if "page_number" in values and not values.get("source_page"):
                values["source_page"] = values["page_number"]
            if "quote" in values and not values.get("source_quote"):
                values["source_quote"] = values["quote"]
            if "source_doc" in values and not values.get("source_doc_title"):
                values["source_doc_title"] = values["source_doc"]
            if values.get("driver_type") == "One-off Driver":
                values["is_one_off"] = True
        return values

# 3. PROMISE VS DELIVERY
class PromiseVsDeliveryItem(BaseModel):
    area: str = Field(description="Initiative / guidance area / metric")
    management_promise: str = Field(description="MANAGEMENT SAID: Explicit guidance, numerical target/range, timeline, or observable strategic commitment in earlier filing")
    promised_in_period: str = Field(description="When guidance was given (quarter / year / document)")
    promise_source_doc: Optional[str] = None
    source_url_promise: Optional[str] = None
    promise_source_page: Optional[int] = None
    promise_quote: Optional[str] = None
    
    actual_outcome: str = Field(description="REPORTED RESULT: What was actually reported later in subsequent filing")
    actual_in_period: str = Field(description="When outcome was reported (document / period)")
    actual_source_doc: Optional[str] = None
    source_url_actual: Optional[str] = None
    actual_source_page: Optional[int] = None
    actual_quote: Optional[str] = None
    
    status: Literal["Delivered", "On Track", "Partially Delivered", "Delayed", "Missed", "Not Yet Measurable", "Not Enough Evidence"] = Field(default="Not Enough Evidence")
    stocker_analysis: str = Field(default="", description="STOCKER INTERPRETATION: Concise variance analysis explaining why target was met/on track/delayed/missed")
    financial_numbers_check: Optional[str] = Field(default=None, description="REPORTED NUMBERS: Comparison against actual reported financial statement metrics")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    @model_validator(mode="before")
    @classmethod
    def adapt_legacy_promise(cls, values: Any) -> Any:
        if isinstance(values, dict):
            if "past_promise" in values and not values.get("management_promise"):
                values["management_promise"] = values["past_promise"]
            if "original_timeline" in values and not values.get("promised_in_period"):
                values["promised_in_period"] = values["original_timeline"]
            if "area" not in values or not values.get("area"):
                values["area"] = values.get("category", "Corporate Strategy")
            if "actual_in_period" not in values or not values.get("actual_in_period"):
                values["actual_in_period"] = values.get("source_document", "Latest Reported Results")
            if "variance_analysis" in values and not values.get("stocker_analysis"):
                values["stocker_analysis"] = values["variance_analysis"]
            if "source_doc_promise" in values and not values.get("promise_source_doc"):
                values["promise_source_doc"] = values["source_doc_promise"]
            if "source_doc_actual" in values and not values.get("actual_source_doc"):
                values["actual_source_doc"] = values["source_doc_actual"]
                
            raw_status = str(values.get("status", "")).strip().lower()
            if raw_status in ("delivered", "met", "achieved", "completed", "delivered on target"):
                values["status"] = "Delivered"
            elif raw_status in ("on track", "in progress", "active", "underway"):
                values["status"] = "On Track"
            elif raw_status in ("partially delivered", "partially met", "partial"):
                values["status"] = "Partially Delivered"
            elif raw_status in ("delayed", "postponed", "deferred"):
                values["status"] = "Delayed"
            elif raw_status in ("missed", "underperformed", "unachieved"):
                values["status"] = "Missed"
            elif raw_status in ("not yet measurable", "not measurable", "unmeasurable"):
                values["status"] = "Not Yet Measurable"
            else:
                values["status"] = "Not Enough Evidence"
        return values

# 4. DEMAND / BUSINESS MOMENTUM
class DemandMomentum(BaseModel):
    summary: str = Field(default="", description="Plain English synthesis of current demand environment")
    company_specific_metrics: List[Dict[str, Any]] = Field(default_factory=list, description="Company-relevant indicators e.g. TCV/backlog, subscriber/ARPU, volume, loan growth, NIM, pricing")
    segment_trends: List[Dict[str, Any]] = Field(default_factory=list, description="Segment-wise acceleration or deceleration")
    market_share_and_pricing: Optional[str] = None
    headwinds_and_risks: List[str] = Field(default_factory=list)
    source_page: Optional[int] = None
    source_quote: Optional[str] = None
    source_url: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

# 5. RISKS, CASH & EXECUTION ISSUES
class RisksAndCashIssues(BaseModel):
    working_capital_and_receivables: Optional[str] = Field(default=None, description="Inventory turns, debtor days, working capital lock-in (Corporate only)")
    debt_and_capex_burden: Optional[str] = Field(default=None, description="Net debt trajectory, interest cost burden, capex commitments")
    margin_and_cost_pressures: Optional[str] = Field(default=None, description="Raw material costs, tariff/pricing headwinds, operating leverage, funding costs")
    execution_and_bottlenecks: List[str] = Field(default_factory=list, description="Supply constraints, commissioning delays, execution hurdles")
    regulatory_or_legal_headwinds: List[str] = Field(default_factory=list, description="Litigation, tax demands, compliance, regulatory changes")
    risk_items: List[Dict[str, Any]] = Field(default_factory=list, description="Structured risk register: risk_title, risk_category, severity, is_current_or_potential, evidence_statement, metric_to_watch, source_url, source_page")
    reported_numbers_comparison: Optional[str] = Field(default=None, description="REPORTED NUMBERS: Comparison against 5-Year CFO/PAT % and Balance Sheet CWIP trends")
    source_page: Optional[int] = None
    source_quote: Optional[str] = None
    source_url: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

# 6. STOCKER VIEW
class StockerView(BaseModel):
    execution_verdict: Literal["Strong Execution", "Mixed Execution", "Weak Execution", "Evolving / Watchlist"] = Field(default="Evolving / Watchlist")
    business_momentum: Optional[str] = Field(default=None, description="Acceleration | Steady Growth | Moderating | Contracting")
    financial_quality: Optional[str] = Field(default=None, description="High Quality | Adequate | Under Pressure | Distressed")
    evidence_confidence: Optional[str] = Field(default="High", description="High | Moderate | Low / Incomplete")
    positive_triggers: List[str] = Field(default_factory=list, description="Key upcoming positive triggers / opportunities (commissioning, tariff hike, new market)")
    main_risks: List[str] = Field(default_factory=list, description="Critical fundamental risks to monitor")
    what_to_watch_next: List[str] = Field(default_factory=list, description="Specific milestones and financial numbers to watch in next 2-4 quarters")
    investor_summary: str = Field(default="", description="Concise, plain-English synthesis for fundamental investors. Strictly no buy/sell recommendations.")

# 7. BUSINESS QUALITY & MONETIZATION MODEL
class BusinessQuality(BaseModel):
    business_model_summary: str = Field(default="", description="How the company creates value, serves customers, and makes money")
    segment_mix: List[Dict[str, Any]] = Field(default_factory=list, description="Segment revenue share, growth rate, and margin contribution")
    geography_mix: List[Dict[str, Any]] = Field(default_factory=list, description="Domestic vs exports / regional revenue breakdown")
    revenue_characteristics: Dict[str, Any] = Field(default_factory=dict, description="Recurring vs cyclical nature, customer concentration, pricing power signals")
    source_page: Optional[int] = None
    source_quote: Optional[str] = None
    source_url: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

# 8. COMPETITIVE POSITION & ECONOMIC MOAT
class CompetitivePosition(BaseModel):
    moat_type: str = Field(default="Narrow / Evolving", description="Cost Advantage | High Switching Costs | Network Effects | Brand / Intangibles | Scale Advantage | Narrow / None")
    market_share_trend: Optional[str] = Field(default=None, description="Market share expansion, stability, or loss")
    pricing_power_assessment: Optional[str] = Field(default=None, description="Ability to pass on cost increases without volume loss")
    key_advantages: List[str] = Field(default_factory=list, description="Key competitive moats and differentiation pillars")
    competitive_threats: List[str] = Field(default_factory=list, description="Direct competitors, emerging threats, technology shifts")
    source_page: Optional[int] = None
    source_quote: Optional[str] = None
    source_url: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

# 9. CAPITAL ALLOCATION & CASH CONVERSION QUALITY
class CapitalAllocationAudit(BaseModel):
    capex_efficiency: Optional[str] = Field(default=None, description="Gross block addition vs revenue generation, CWIP conversion")
    reinvestment_rate: Optional[str] = Field(default=None, description="Percentage of cash flow reinvested into core growth vs payouts")
    ma_track_record: Optional[str] = Field(default=None, description="Acquisitions synergy realization, integration discipline, goodwill")
    shareholder_returns: Optional[str] = Field(default=None, description="Dividend payout sustainability, share buybacks, dilution history")
    capital_deployed_vs_returns: Optional[str] = Field(default=None, description="Incremental return on invested capital vs cost of capital")
    source_page: Optional[int] = None
    source_quote: Optional[str] = None
    source_url: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

# 10. GOVERNANCE & ACCOUNTING / FORENSIC WATCH
class GovernanceAndForensicWatch(BaseModel):
    auditor_observations: Optional[str] = Field(default=None, description="Auditor qualifications, emphasis of matter, key audit matters")
    related_party_transactions: Optional[str] = Field(default=None, description="Magnitude and business rationale of RPTs / promoter entity dealings")
    contingent_liabilities: Optional[str] = Field(default=None, description="Tax disputes, claims not acknowledged as debts vs net worth")
    working_capital_anomalies: Optional[str] = Field(default=None, description="Debtor days drift, unbilled revenue, inventory aging divergence")
    regulatory_or_legal_risks: List[str] = Field(default_factory=list, description="Regulatory inquiries, environmental compliance, litigation")
    promoter_and_shareholding_notes: Optional[str] = Field(default=None, description="Promoter holding, pledging changes, institutional holdings")
    source_page: Optional[int] = None
    source_quote: Optional[str] = None
    source_url: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

# 11. PER-DOCUMENT EXECUTIVE SUMMARY
class ConcallSpecificSummary(BaseModel):
    demand_commentary: Optional[str] = None
    order_book_or_pipeline: Optional[str] = None
    margin_outlook: Optional[str] = None
    execution_updates: Optional[str] = None
    quarterly_changes_or_shifts: Optional[str] = None

class PresentationSpecificSummary(BaseModel):
    major_kpis: List[str] = Field(default_factory=list)
    expansion_roadmap: Optional[str] = None
    segment_highlights: List[str] = Field(default_factory=list)
    forward_targets: Optional[str] = None

class AnnouncementSpecificSummary(BaseModel):
    event_summary: Optional[str] = None
    fundamental_importance: Optional[str] = None
    business_impact: Optional[str] = None
    changes_management_guidance: Optional[str] = None

# 12. PERSISTENT COMPANY FACT / KPI ITEM
class CompanyFactItem(BaseModel):
    metric_name: str = Field(description="Name of metric e.g. Revenue, EBITDA Margin, ARPU, Solar Capacity, Order Book")
    stated_value_raw: str = Field(description="Exact value as stated in filing e.g. 52%, ₹245, 1 GW, ₹14,500 Cr")
    numeric_value: Optional[float] = Field(default=None, description="Parsed numeric value for deterministic code math")
    unit: Optional[str] = Field(default=None, description="Unit e.g. %, ₹, MW, ₹ Cr, bps, subscribers")
    period_or_date: str = Field(description="Period described e.g. FY26, Q3 FY26, Mar 2026")
    target_period: Optional[str] = Field(default=None, description="Target period if forward guidance e.g. FY27, FY28")
    category: str = Field(default="operational_kpi", description="financial_metric, operational_kpi, management_guidance, strategic_initiative, risk_headwind")
    scope: str = Field(default="Consolidated", description="Consolidated, Standalone, Segment name, Geography")
    claim_type: str = Field(default="reported_fact", description="reported_fact, management_guidance, management_target, strategic_commentary")
    source_doc_title: Optional[str] = None
    source_url: Optional[str] = None
    source_page: Optional[int] = None
    source_quote: Optional[str] = None

# 9. VERIFIED FACT & CONTEXT COMPARISON
class VerifiedFactComparison(BaseModel):
    metric_name: str
    category: str = "operational_kpi"
    scope: str = "Consolidated"
    latest_period: str
    latest_value_raw: str
    latest_numeric: Optional[float] = None
    prior_period: Optional[str] = None
    prior_value_raw: Optional[str] = None
    prior_numeric: Optional[float] = None
    delta_numeric: Optional[float] = None
    pct_change: Optional[float] = None
    unit: Optional[str] = None
    statement_verification_status: str = Field(default="Not Enough Evidence", description="Verified against Reported Financials | Discrepancy vs Reported Financials | Operational KPI (Inter-Document Comparison) | Not Enough Evidence")
    statement_reported_value: Optional[str] = None
    management_explanation: Optional[str] = None
    stocker_assessment: str = Field(default="", description="Deterministic code verification or assessment note")
    source_doc_title: Optional[str] = None
    source_url: Optional[str] = None
    source_page: Optional[int] = None
    newer_evidence_available: bool = False
    newer_evidence_note: Optional[str] = None

# 10. INTER-DOCUMENT OPERATIONAL KPI EVOLUTION
class InterDocumentKPITrend(BaseModel):
    metric_name: str
    category: str = "operational_kpi"
    unit: Optional[str] = None
    trajectory: str = "Evolving"
    data_points: List[Dict[str, Any]] = Field(default_factory=list, description="Chronological series: period, numeric_value, stated_value, doc_title, doc_url, doc_type")
    latest_vs_prior_change: Optional[str] = None
    pct_change: Optional[float] = None
    insight: str = ""

# 11. GUIDANCE VS STOCKER PROJECTIONS TRIANGULATION
class GuidanceVsProjection(BaseModel):
    metric_name: str
    period_target: str
    management_guidance_raw: str
    management_guidance_numeric: Optional[float] = None
    guidance_source_doc: str
    guidance_source_url: Optional[str] = None
    stocker_projected_base: Optional[float] = None
    stocker_projected_bull: Optional[float] = None
    stocker_projected_bear: Optional[float] = None
    current_run_rate_value: Optional[float] = None
    current_run_rate_period: Optional[str] = None
    variance_guidance_vs_base_bps: Optional[float] = None
    stocker_assessment: str = ""

class DocumentSummaryItem(BaseModel):
    doc_title: str
    doc_url: str
    doc_key: Optional[str] = None
    doc_type: Optional[str] = None
    period_or_date: Optional[str] = None
    analyzed_at: Optional[str] = None
    status: Literal["success", "failed"] = "success"
    error: Optional[str] = None
    key_takeaways: List[str] = Field(default_factory=list, description="3-5 bullet executive takeaways")
    management_tone: Optional[str] = Field(default=None, description="Tone e.g. Confident, Prudent, Cautious, Neutral")
    guidance_and_capex: Optional[str] = Field(default=None, description="Important forward-looking guidance or capex roadmap")
    risks_and_headwinds: List[str] = Field(default_factory=list, description="Important risks or execution issues")
    capex_or_guidance_highlight: Optional[str] = Field(default=None, description="Legacy alias for guidance_and_capex")
    
    # Persistent structured facts extracted from this document
    extracted_facts: List[CompanyFactItem] = Field(default_factory=list, description="Structured investor-relevant KPIs, metrics, guidance, and claims")

    # Document-Type Specialized Extractions
    strategic_priorities: Optional[str] = None
    capex_and_expansion: Optional[str] = None
    cash_debt_working_capital: Optional[str] = None
    major_risks: List[str] = Field(default_factory=list)
    long_term_targets: Optional[str] = None
    management_guidance: Optional[str] = None
    demand_and_orders: Optional[str] = None
    margin_outlook: Optional[str] = None
    capex_and_execution: Optional[str] = None
    quarterly_shifts: Optional[str] = None
    major_kpis: List[str] = Field(default_factory=list)
    expansion_roadmap: Optional[str] = None
    segment_highlights: List[str] = Field(default_factory=list)
    forward_targets: Optional[str] = None
    event_summary: Optional[str] = None
    fundamental_importance: Optional[str] = None
    business_and_financial_impact: Optional[str] = None
    guidance_impact: Optional[str] = None

    concall_specific: Optional[ConcallSpecificSummary] = None
    presentation_specific: Optional[PresentationSpecificSummary] = None
    announcement_specific: Optional[AnnouncementSpecificSummary] = None

    @model_validator(mode="before")
    @classmethod
    def adapt_summary_fields(cls, values: Any) -> Any:
        if isinstance(values, dict):
            if not values.get("guidance_and_capex") and values.get("capex_or_guidance_highlight"):
                values["guidance_and_capex"] = values.get("capex_or_guidance_highlight")
            elif not values.get("capex_or_guidance_highlight") and values.get("guidance_and_capex"):
                values["capex_or_guidance_highlight"] = values.get("guidance_and_capex")
        return values

DocumentEvidenceType = Literal[
    "MANAGEMENT_GUIDANCE",
    "DEMAND_DRIVER",
    "SUPPLY_DRIVER",
    "CAPEX_PLAN",
    "CAPACITY_EXPANSION",
    "MARGIN_DRIVER",
    "COST_PRESSURE",
    "ORDER_BOOK",
    "CUSTOMER_CONCENTRATION",
    "GEOGRAPHIC_EXPOSURE",
    "NEW_PRODUCT",
    "REGULATORY_RISK",
    "COMPETITIVE_RISK",
    "CAPITAL_ALLOCATION",
    "WORKING_CAPITAL_COMMENTARY",
    "MANAGEMENT_COMMITMENT",
    "KPI",
    "OTHER_MATERIAL_EVIDENCE"
]

class DocumentEvidenceItem(BaseModel):
    id: Optional[str] = None
    symbol: Optional[str] = None
    evidence_type: DocumentEvidenceType = Field(default="OTHER_MATERIAL_EVIDENCE", description="Strict categorical classification of evidence")
    title: str = Field(default="Document Evidence", description="Concise, informative title of the evidence claim")
    normalized_topic: str = Field(default="General", description="Standardized topic area e.g. Revenue, OPM, Capex, Loan Growth, Asset Quality")
    statement: str = Field(default="", description="The exact extracted claim or factual assertion")
    source_document_type: str = Field(default="annual_report", description="annual_report | concall_transcript | presentation | announcement")
    source_document_title: str = Field(default="", description="Title of source document")
    source_url: str = Field(default="", description="Direct URL of source document")
    source_period: Optional[str] = Field(default=None, description="Filing period e.g. FY25, Q3 FY26")
    source_date: Optional[str] = Field(default=None, description="Filing publication date e.g. 2025-01-20")
    page: Optional[int] = Field(default=None, description="Verified page number in source filing")
    section: Optional[str] = Field(default=None, description="Section or chapter name in filing")
    evidence_quote: Optional[str] = Field(default=None, description="Short supporting quote excerpt from text")
    extraction_method: str = Field(default="llm_structured_extraction", description="Method of extraction")
    confidence: Literal["HIGH", "MEDIUM", "LOW"] = Field(default="HIGH", description="Confidence rating")
    status: Literal["SUPPORTED", "UNSUPPORTED", "SUPERSEDED"] = Field(default="SUPPORTED", description="Factual support status")
    created_at: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def adapt_evidence_item(cls, values: Any) -> Any:
        if isinstance(values, dict):
            if "claim" in values and not values.get("statement"):
                values["statement"] = values["claim"]
            if "evidence_statement" in values and not values.get("statement"):
                values["statement"] = values["evidence_statement"]
            if "topic" in values and not values.get("normalized_topic"):
                values["normalized_topic"] = values["topic"]
            if "source_doc" in values and not values.get("source_document_title"):
                values["source_document_title"] = values["source_doc"]
            if "source_document" in values and not values.get("source_document_title"):
                values["source_document_title"] = values["source_document"]
            if "source_page" in values and not values.get("page"):
                values["page"] = values["source_page"]
            if "page_number" in values and not values.get("page"):
                values["page"] = values["page_number"]
            if "quote" in values and not values.get("evidence_quote"):
                values["evidence_quote"] = values["quote"]
            ev_type = values.get("evidence_type")
            if isinstance(ev_type, str):
                normalized = ev_type.upper().strip().replace(" ", "_")
                valid_types = {
                    "DEMAND_DRIVER", "PRICING_POWER", "CAPEX_PLAN", "UNIT_ECONOMICS",
                    "MONETIZATION_ENGINE", "GEOGRAPHIC_EXPANSION", "PRODUCT_LAUNCH",
                    "REGULATORY_CATALYST", "RISK_FACTOR", "MANAGEMENT_GUIDANCE",
                    "MANAGEMENT_COMMITMENT", "KPI", "OTHER_MATERIAL_EVIDENCE"
                }
                if normalized in valid_types:
                    values["evidence_type"] = normalized
                else:
                    values["evidence_type"] = ev_type
        return values

class ManagementGuidanceItem(BaseModel):
    id: Optional[str] = None
    metric_or_topic: str = Field(default="Guidance", description="Metric or qualitative topic e.g. Revenue, OPM %, Capex, Loan Growth, Deposits, GNPA")
    guidance_text: str = Field(default="", description="Verbatim or close management guidance statement")
    quantified_value: Optional[float] = Field(default=None, description="Point target if explicitly stated")
    quantified_range_min: Optional[float] = Field(default=None, description="Lower bound of guided range")
    quantified_range_max: Optional[float] = Field(default=None, description="Upper bound of guided range")
    unit: Optional[str] = Field(default=None, description="Unit e.g. %, ₹ Cr, bps, MW, stores")
    target_period: str = Field(default="Future Period", description="Target period for guidance e.g. FY26, Q4 FY26, FY27")
    direction: Optional[str] = Field(default=None, description="GROWTH, MARGIN_EXPANSION, CAPEX, MAINTAIN, REDUCTION")
    source_document_title: str = Field(default="", description="Document where guidance was stated")
    source_document_url: Optional[str] = Field(default=None, description="Direct URL of source document")
    source_date_or_period: Optional[str] = Field(default=None, description="Period or date of source filing")
    confidence: Literal["HIGH", "MEDIUM", "LOW"] = Field(default="HIGH")
    status: Literal["MET", "PARTIALLY_MET", "MISSED", "NOT_YET_DUE", "NOT_COMPARABLE", "INSUFFICIENT_EVIDENCE"] = Field(default="INSUFFICIENT_EVIDENCE")
    source_support_status: Literal["SUPPORTED", "UNSUPPORTED"] = Field(default="SUPPORTED", description="Whether source document citation is verified in corpus")
    actual_reported_value: Optional[float] = None
    actual_reported_period: Optional[str] = None
    actual_reported_source: Optional[str] = None
    comparison_detail: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def adapt_guidance_item(cls, values: Any) -> Any:
        if isinstance(values, dict):
            if "metric" in values and not values.get("metric_or_topic"):
                values["metric_or_topic"] = values["metric"]
            if "topic" in values and not values.get("metric_or_topic"):
                values["metric_or_topic"] = values["topic"]
            if "statement" in values and not values.get("guidance_text"):
                values["guidance_text"] = values["statement"]
            if "target_timeline" in values and not values.get("target_period"):
                values["target_period"] = values["target_timeline"]
            if "source_doc" in values and not values.get("source_document_title"):
                values["source_document_title"] = values["source_doc"]
            if "source_document" in values and not values.get("source_document_title"):
                values["source_document_title"] = values["source_document"]
            if "source_url" in values and not values.get("source_document_url"):
                values["source_document_url"] = values["source_url"]
        return values

# ROOT DOCUMENT INTELLIGENCE OBJECT
class BusinessOutlookResult(BaseModel):
    symbol: str
    company_name: str
    latest_document_period: str = Field(default="Latest Filing")
    older_document_period: Optional[str] = Field(default=None)
    source_documents: List[Dict[str, Any]] = Field(default_factory=list)
    ai_provider_used: str = Field(default="None")
    model_version: Optional[str] = Field(default="gemini-3.6-flash")
    extraction_timestamp: Optional[str] = Field(default=None)
    status: Optional[str] = Field(default=None)
    message: Optional[str] = Field(default=None)
    
    # 6 Core Investor Sections
    what_changed_recently: List[RecentChange] = Field(default_factory=list)
    growth_drivers: List[GrowthDriver] = Field(default_factory=list)
    promise_vs_delivery: List[PromiseVsDeliveryItem] = Field(default_factory=list)
    demand_momentum: DemandMomentum = Field(default_factory=DemandMomentum)
    risks_and_cash: RisksAndCashIssues = Field(default_factory=RisksAndCashIssues)
    stocker_view: StockerView = Field(default_factory=StockerView)
    document_summaries: List[DocumentSummaryItem] = Field(default_factory=list)

    # 4 Fundamental Completeness Dimensions
    business_quality: BusinessQuality = Field(default_factory=BusinessQuality)
    competitive_position: CompetitivePosition = Field(default_factory=CompetitivePosition)
    capital_allocation: CapitalAllocationAudit = Field(default_factory=CapitalAllocationAudit)
    governance_watch: GovernanceAndForensicWatch = Field(default_factory=GovernanceAndForensicWatch)

    # Integrated Knowledge & Triangulation Layer
    verified_facts: List[VerifiedFactComparison] = Field(default_factory=list)
    operational_kpi_evolution: List[InterDocumentKPITrend] = Field(default_factory=list)
    guidance_vs_projections: List[GuidanceVsProjection] = Field(default_factory=list)

    # V2 Document Intelligence & Evidence Layer
    evidence_items: List[DocumentEvidenceItem] = Field(default_factory=list)
    management_guidance_items: List[ManagementGuidanceItem] = Field(default_factory=list)
    source_documents_hash: Optional[str] = None
    analysis_version: str = "2.0"
    staleness_status: str = "not_checked"
    financial_business_model: str = "GENERAL_CORPORATE"

    # Backward-compatible properties / validators
    @model_validator(mode="before")
    @classmethod
    def adapt_legacy_and_flexible_schemas(cls, values: Any) -> Any:
        if isinstance(values, dict):
            # Normalize legacy field names
            if "last_analyzed_period" in values and not values.get("latest_document_period"):
                values["latest_document_period"] = values["last_analyzed_period"]
            if "analyzed_documents" in values and not values.get("source_documents"):
                values["source_documents"] = values["analyzed_documents"]
            
            # Adapt plan_vs_reality -> promise_vs_delivery
            if "plan_vs_reality" in values and not values.get("promise_vs_delivery"):
                values["promise_vs_delivery"] = values["plan_vs_reality"]
            elif "promise_vs_delivery" in values and not values.get("plan_vs_reality"):
                values["plan_vs_reality"] = values["promise_vs_delivery"]

            # Adapt growth_pipeline -> growth_drivers
            if "growth_pipeline" in values and not values.get("growth_drivers"):
                drivers = []
                for g in values.get("growth_pipeline", []):
                    drivers.append({
                        "driver_title": g.get("initiative", "Growth Initiative"),
                        "driver_type": g.get("type", "Expansion / Capex"),
                        "description": g.get("current_status", ""),
                        "target_timeline": g.get("target_commissioning"),
                        "stated_outlay_or_value": g.get("outlay_cr"),
                        "execution_status": g.get("current_status", "In Progress"),
                        "expected_impact": g.get("expected_impact"),
                        "source_page": g.get("source_page"),
                        "source_quote": g.get("source_quote"),
                        "source_url": g.get("source_url"),
                    })
                values["growth_drivers"] = drivers

            # Adapt demand_and_orders -> demand_momentum
            if "demand_and_orders" in values and not values.get("demand_momentum"):
                dao = values.get("demand_and_orders", {})
                metrics = []
                if dao.get("order_book_or_tcv"):
                    metrics.append({"metric": "Order Book / TCV", "value": dao["order_book_or_tcv"]})
                if dao.get("customer_or_subscriber_growth"):
                    metrics.append({"metric": "Customer / Subscriber Additions", "value": dao["customer_or_subscriber_growth"]})
                if dao.get("volume_and_pricing_trends"):
                    metrics.append({"metric": "Volume & Pricing", "value": dao["volume_and_pricing_trends"]})
                
                values["demand_momentum"] = {
                    "summary": dao.get("volume_and_pricing_trends") or "Operational volume and demand momentum.",
                    "company_specific_metrics": metrics,
                    "segment_trends": dao.get("segment_demand_trends", []),
                    "market_share_and_pricing": dao.get("market_share_signals"),
                    "headwinds_and_risks": dao.get("headwinds_and_risks", []),
                    "source_page": dao.get("source_page"),
                    "source_quote": dao.get("source_quote"),
                    "source_url": dao.get("source_url"),
                }

            # Adapt cash_and_problems -> risks_and_cash
            if "cash_and_problems" in values and not values.get("risks_and_cash"):
                cap = values.get("cash_and_problems", {})
                values["risks_and_cash"] = {
                    "working_capital_and_receivables": cap.get("inventory_and_receivables_audit"),
                    "debt_and_capex_burden": cap.get("debt_and_leverage_status"),
                    "margin_and_cost_pressures": None,
                    "execution_and_bottlenecks": cap.get("operational_bottlenecks", []),
                    "regulatory_or_legal_headwinds": [],
                    "reported_numbers_comparison": cap.get("financial_cross_check"),
                    "source_page": cap.get("source_page"),
                    "source_quote": cap.get("source_quote"),
                    "source_url": cap.get("source_url"),
                }

            # Synthesize what_changed_recently if not present
            if not values.get("what_changed_recently"):
                changes = []
                for p in values.get("promise_vs_delivery", [])[:2]:
                    p_area = p.get("area", "Key Metric") if isinstance(p, dict) else getattr(p, "area", "Key Metric")
                    p_stat = p.get("status", "Update") if isinstance(p, dict) else getattr(p, "status", "Update")
                    p_out = p.get("actual_outcome", "") if isinstance(p, dict) else getattr(p, "actual_outcome", "")
                    p_in = p.get("actual_in_period") if isinstance(p, dict) else getattr(p, "actual_in_period", None)
                    p_page = p.get("actual_source_page") if isinstance(p, dict) else getattr(p, "actual_source_page", None)
                    p_url = p.get("source_url_actual") if isinstance(p, dict) else getattr(p, "source_url_actual", None)
                    changes.append({
                        "headline": f"{p_area}: {p_stat}",
                        "category": "Promise vs Delivery",
                        "detail": p_out,
                        "source_doc": p_in,
                        "source_page": p_page,
                        "source_url": p_url
                    })
                for g in values.get("growth_drivers", [])[:2]:
                    g_title = g.get("driver_title", "Initiative") if isinstance(g, dict) else getattr(g, "driver_title", "Initiative")
                    g_type = g.get("driver_type", "Growth Driver") if isinstance(g, dict) else getattr(g, "driver_type", "Growth Driver")
                    g_desc = g.get("description", "") if isinstance(g, dict) else getattr(g, "description", "")
                    g_page = g.get("source_page") if isinstance(g, dict) else getattr(g, "source_page", None)
                    g_url = g.get("source_url") if isinstance(g, dict) else getattr(g, "source_url", None)
                    changes.append({
                        "headline": f"{g_title}",
                        "category": g_type,
                        "detail": g_desc,
                        "source_doc": values.get("latest_document_period"),
                        "source_page": g_page,
                        "source_url": g_url
                    })
                values["what_changed_recently"] = changes

            # Synthesize stocker_view if not present
            if not values.get("stocker_view"):
                p_items = values.get("promise_vs_delivery", [])
                delivered_count = sum(1 for p in p_items if (p.get("status") if isinstance(p, dict) else getattr(p, "status", None)) == "Delivered")
                total_pvr = len(p_items)
                if total_pvr > 0 and (delivered_count / total_pvr) >= 0.6:
                    verdict = "Strong Execution"
                elif total_pvr > 0 and delivered_count > 0:
                    verdict = "Mixed Execution"
                elif total_pvr > 0:
                    verdict = "Weak Execution"
                else:
                    verdict = "Evolving / Watchlist"

                values["stocker_view"] = {
                    "execution_verdict": verdict,
                    "business_momentum": "Steady Growth",
                    "financial_quality": "High Quality",
                    "evidence_confidence": "High",
                    "positive_triggers": [g.get("driver_title") if isinstance(g, dict) else getattr(g, "driver_title", "Initiative") for g in values.get("growth_drivers", [])[:3]],
                    "main_risks": values.get("risks_and_cash", {}).get("execution_and_bottlenecks", [])[:3] if isinstance(values.get("risks_and_cash"), dict) else getattr(values.get("risks_and_cash"), "execution_and_bottlenecks", [])[:3],
                    "what_to_watch_next": ["Next quarterly results and capacity commissioning"],
                    "investor_summary": f"Management execution verdict: {verdict}. Detailed evidence extracted from filings."
                }

            # Ensure symbol is set on evidence items
            sym = values.get("symbol", "")
            if "evidence_items" in values and isinstance(values["evidence_items"], list):
                for item in values["evidence_items"]:
                    if isinstance(item, dict):
                        if not item.get("symbol") and sym:
                            item["symbol"] = sym
        return values

# Backward-compatible model aliases for engine and consumers
WhatChangedItem = RecentChange
GrowthDriverItem = GrowthDriver
RisksAndCash = RisksAndCashIssues
GenericPlanVsRealityItem = PromiseVsDeliveryItem
GenericGrowthPipelineItem = GrowthDriver
GenericDemandAndOrders = DemandMomentum
GenericCashAndProblems = RisksAndCashIssues
GenericDocumentIntelligenceResult = BusinessOutlookResult

PlanVsRealityItem = PromiseVsDeliveryItem
GrowthPipelineItem = GrowthDriver
DemandAndOrders = DemandMomentum
CashAndProblems = RisksAndCashIssues
CompanyDocumentIntelligence = BusinessOutlookResult
BusinessAnalysisResult = BusinessOutlookResult

