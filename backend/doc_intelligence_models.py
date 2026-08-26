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
    
    status: Literal["Delivered", "In Progress", "Delayed", "Missed", "Not Enough Data"] = Field(default="Not Enough Data")
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
            if values.get("status") == "Not enough data":
                values["status"] = "Not Enough Data"
        return values

# 4. DEMAND / BUSINESS MOMENTUM
class DemandMomentum(BaseModel):
    summary: str = Field(default="", description="Plain English synthesis of current demand environment")
    company_specific_metrics: List[Dict[str, str]] = Field(default_factory=list, description="Company-relevant indicators e.g. TCV/backlog, subscriber/ARPU, volume, loan growth, NIM, pricing")
    segment_trends: List[Dict[str, str]] = Field(default_factory=list, description="Segment-wise acceleration or deceleration")
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

# ROOT DOCUMENT INTELLIGENCE OBJECT
class BusinessOutlookResult(BaseModel):
    symbol: str
    company_name: str
    latest_document_period: str = Field(default="Latest Filing")
    older_document_period: Optional[str] = Field(default=None)
    source_documents: List[Dict[str, str]] = Field(default_factory=list)
    ai_provider_used: str = Field(default="None")
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
