from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, model_validator

# 1. WHAT CHANGED RECENTLY
class RecentChange(BaseModel):
    headline: str = Field(description="Short, impactful headline of what changed")
    category: str = Field(description="Category e.g. Capex / Expansion, Demand / Deal Win, Pricing / Tariff, Debt / Working Capital, Strategic / M&A")
    detail: str = Field(description="Plain English context and magnitude of change")
    source_doc: Optional[str] = None
    source_page: Optional[int] = None
    source_url: Optional[str] = None

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
        return values

# 2. MANAGEMENT PLAN & GROWTH DRIVERS
class GrowthDriver(BaseModel):
    driver_title: str = Field(description="Initiative / plant / program / market expansion name")
    driver_type: str = Field(default="Expansion / Capex", description="Type e.g. Capacity / Plant, New Product, M&A, Large Contract, Strategic Pivot")
    description: str = Field(description="What management is planning and expected business driver")
    target_timeline: Optional[str] = Field(default=None, description="Stated target timeline or COD if mentioned")
    stated_outlay_or_value: Optional[str] = Field(default=None, description="Stated capex outlay or contract value in ₹ Cr or original currency")
    execution_status: str = Field(default="In Progress", description="Current execution progress stated by company")
    expected_impact: Optional[str] = Field(default=None, description="Management stated business impact (do not fabricate)")
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
        return values

# 3. PROMISE VS DELIVERY
class PromiseVsDeliveryItem(BaseModel):
    area: str = Field(description="Initiative / guidance area / metric")
    management_promise: str = Field(description="MANAGEMENT SAID: What was guided or promised in earlier filing")
    promised_in_period: str = Field(description="When guidance was given (quarter / year / document)")
    promise_source_page: Optional[int] = None
    promise_quote: Optional[str] = None
    
    actual_outcome: str = Field(description="REPORTED RESULT: What was actually reported later")
    actual_in_period: str = Field(description="When outcome was reported (document / period)")
    actual_source_page: Optional[int] = None
    actual_quote: Optional[str] = None
    
    status: Literal["Delivered", "In Progress", "Delayed", "Missed", "Not Enough Data", "Not Enough Evidence"] = Field(default="Not Enough Evidence")
    stocker_analysis: str = Field(default="", description="STOCKER INTERPRETATION: Concise variance analysis explaining why target was met/delayed/missed")
    financial_numbers_check: Optional[str] = Field(default=None, description="REPORTED NUMBERS: Comparison against actual reported financial statement metrics")
    source_url_promise: Optional[str] = None
    source_url_actual: Optional[str] = None
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
                values["actual_in_period"] = values.get("source_document", "Latest Audited Results")
            if "variance_analysis" in values and not values.get("stocker_analysis"):
                values["stocker_analysis"] = values["variance_analysis"]
            if values.get("status") in ("Not enough data", "Not Enough Data", "Not enough evidence", "Not Enough Evidence"):
                values["status"] = "Not Enough Evidence"
        return values

# 4. DEMAND / BUSINESS MOMENTUM
class DemandMomentum(BaseModel):
    summary: str = Field(default="", description="Plain English synthesis of current demand environment")
    company_specific_metrics: List[Dict[str, Any]] = Field(default_factory=list, description="Company-relevant indicators e.g. TCV/backlog, subscriber/ARPU, volume, loan growth, NIM, pricing")
    segment_trends: List[Dict[str, Any]] = Field(default_factory=list, description="Segment-wise acceleration or deceleration")
    market_share_and_pricing: Optional[str] = Field(default=None, description="Market share position and pricing power signals")
    headwinds_and_risks: List[str] = Field(default_factory=list, description="Stated demand headwinds or client caution")
    source_page: Optional[int] = None
    source_quote: Optional[str] = None
    source_url: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

# 5. RISKS, CASH & EXECUTION ISSUES
class RisksAndCashIssues(BaseModel):
    working_capital_and_receivables: Optional[str] = Field(default=None, description="Inventory turns, debtor days, working capital lock-in")
    debt_and_capex_burden: Optional[str] = Field(default=None, description="Net debt trajectory, interest cost burden, capex commitments")
    margin_and_cost_pressures: Optional[str] = Field(default=None, description="Raw material costs, tariff/pricing headwinds, operating leverage")
    execution_and_bottlenecks: List[str] = Field(default_factory=list, description="Supply constraints, commissioning delays, execution hurdles")
    regulatory_or_legal_headwinds: List[str] = Field(default_factory=list, description="Litigation, tax demands, compliance, regulatory changes")
    reported_numbers_comparison: Optional[str] = Field(default=None, description="REPORTED NUMBERS: Comparison against 5-Year CFO/PAT % and Balance Sheet CWIP trends")
    source_page: Optional[int] = None
    source_quote: Optional[str] = None
    source_url: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

# 6. STOCKER VIEW
class StockerView(BaseModel):
    execution_verdict: Literal["Strong Execution", "Mixed Execution", "Weak Execution", "Evolving / Watchlist"] = Field(default="Evolving / Watchlist")
    positive_triggers: List[str] = Field(default_factory=list, description="Key upcoming positive triggers (commissioning, tariff hike, new market)")
    main_risks: List[str] = Field(default_factory=list, description="Critical fundamental risks to monitor")
    what_to_watch_next: List[str] = Field(default_factory=list, description="Specific milestones and financial numbers to watch in next 2-4 quarters")
    investor_summary: str = Field(default="", description="Concise, plain-English synthesis for fundamental investors")

# 7. PER-DOCUMENT EXECUTIVE SUMMARY
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

# 8. PERSISTENT COMPANY FACT / KPI ITEM
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
    doc_type: Optional[str] = None
    period_or_date: Optional[str] = None
    analyzed_at: Optional[str] = None
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

# ROOT DOCUMENT INTELLIGENCE OBJECT
class BusinessOutlookResult(BaseModel):
    symbol: str
    company_name: str
    latest_document_period: str = Field(default="Latest Filing")
    older_document_period: Optional[str] = Field(default=None)
    source_documents: List[Dict[str, Any]] = Field(default_factory=list)
    ai_provider_used: str = Field(default="None")
    model_version: Optional[str] = Field(default="gemini-3.6-flash")
    extraction_timestamp: str = Field(default="")
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

    # Integrated Knowledge & Triangulation Layer
    verified_facts: List[VerifiedFactComparison] = Field(default_factory=list)
    operational_kpi_evolution: List[InterDocumentKPITrend] = Field(default_factory=list)
    guidance_vs_projections: List[GuidanceVsProjection] = Field(default_factory=list)

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
                    changes.append({
                        "headline": f"{p.get('area', 'Key Metric')}: {p.get('status', 'Update')}",
                        "category": "Promise vs Delivery",
                        "detail": p.get("actual_outcome", ""),
                        "source_doc": p.get("actual_in_period"),
                        "source_page": p.get("actual_source_page"),
                        "source_url": p.get("source_url_actual")
                    })
                for g in values.get("growth_drivers", [])[:2]:
                    changes.append({
                        "headline": f"{g.get('driver_title', 'Initiative')}",
                        "category": g.get("driver_type", "Growth Driver"),
                        "detail": g.get("description", ""),
                        "source_doc": values.get("latest_document_period"),
                        "source_page": g.get("source_page"),
                        "source_url": g.get("source_url")
                    })
                values["what_changed_recently"] = changes

            # Synthesize stocker_view if not present
            if not values.get("stocker_view"):
                delivered_count = sum(1 for p in values.get("promise_vs_delivery", []) if p.get("status") == "Delivered")
                total_pvr = len(values.get("promise_vs_delivery", []))
                verdict: Literal["Strong Execution", "Mixed Execution", "Weak Execution", "Evolving / Watchlist"] = (
                    "Strong Execution" if (total_pvr > 0 and delivered_count / total_pvr >= 0.7)
                    else "Mixed Execution" if total_pvr > 0
                    else "Evolving / Watchlist"
                )
                values["stocker_view"] = {
                    "execution_verdict": verdict,
                    "positive_triggers": [g.get("driver_title") for g in values.get("growth_drivers", []) if g.get("driver_title")],
                    "main_risks": values.get("demand_momentum", {}).get("headwinds_and_risks", []) if isinstance(values.get("demand_momentum"), dict) else [],
                    "what_to_watch_next": ["Upcoming quarterly operational metrics", "Capacity commissioning milestones"],
                    "investor_summary": f"Management execution is tracking as {verdict.lower()} based on verified filings and actual financial metrics."
                }
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
