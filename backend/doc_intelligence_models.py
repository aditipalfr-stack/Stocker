from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field

class GenericPlanVsRealityItem(BaseModel):
    area: str = Field(description="Target area/initiative/metric")
    management_promise: str = Field(description="What management guided/promised in earlier document")
    promised_in_period: str = Field(description="Earlier document title and period")
    promise_source_page: Optional[int] = Field(default=None, description="Page number in earlier document")
    promise_quote: Optional[str] = Field(default=None, description="Verbatim quote from earlier document")
    
    actual_outcome: str = Field(description="What was actually reported in later document")
    actual_in_period: str = Field(description="Later document title and period")
    actual_source_page: Optional[int] = Field(default=None, description="Page number in later document")
    actual_quote: Optional[str] = Field(default=None, description="Verbatim quote from later document")
    
    status: Literal["Delivered", "In Progress", "Delayed", "Missed", "Not Enough Data"]
    variance_analysis: str = Field(description="Reason for outcome vs target")
    source_url_promise: Optional[str] = None
    source_url_actual: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

class GenericGrowthPipelineItem(BaseModel):
    initiative: str = Field(description="Project, plant, capacity, or M&A name")
    type: Literal["Capacity / Plant", "Capex Program", "M&A / Acquisition", "New Product / Market"]
    outlay_cr: Optional[str] = Field(default=None, description="Capex/outlay in ₹ Cr or original currency, or null if unstated")
    target_commissioning: Optional[str] = Field(default=None, description="Target timeline or COD, or null if unstated")
    current_status: str = Field(description="Latest execution progress from document")
    expected_impact: Optional[str] = Field(default=None, description="Management stated business or revenue impact")
    source_page: Optional[int] = Field(default=None, description="Page number in document")
    source_quote: Optional[str] = Field(default=None, description="Verbatim quote snippet")
    source_url: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

class GenericDemandAndOrders(BaseModel):
    order_book_or_tcv: Optional[str] = Field(default=None, description="Order book, backlog, or quarterly TCV value")
    book_to_bill_ratio: Optional[str] = Field(default=None, description="Book to bill ratio if stated")
    customer_or_subscriber_growth: Optional[str] = Field(default=None, description="Subscriber or client additions")
    volume_and_pricing_trends: Optional[str] = Field(default=None, description="Volume growth and pricing realization")
    segment_demand_trends: List[Dict[str, str]] = Field(default_factory=list, description="Segment-wise demand acceleration/deceleration")
    market_share_signals: Optional[str] = Field(default=None, description="Market share trends or competitive position")
    headwinds_and_risks: List[str] = Field(default_factory=list, description="Stated demand headwinds or client caution")
    source_page: Optional[int] = None
    source_quote: Optional[str] = None
    source_url: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

class GenericCashAndProblems(BaseModel):
    cfo_fcf_drivers: Optional[str] = Field(default=None, description="Primary drivers of operating cash flow")
    inventory_and_receivables_audit: Optional[str] = Field(default=None, description="Working capital, inventory days, debtor days")
    debt_and_leverage_status: Optional[str] = Field(default=None, description="Debt trajectory, interest costs, capex deployment")
    operational_bottlenecks: List[str] = Field(default_factory=list, description="Supply bottlenecks, margin headwinds, execution hurdles")
    financial_cross_check: Optional[str] = Field(default=None, description="Numerical financial engine cross-check")
    source_page: Optional[int] = None
    source_quote: Optional[str] = None
    source_url: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

class GenericDocumentIntelligenceResult(BaseModel):
    symbol: str
    company_name: str
    latest_document_period: str
    older_document_period: Optional[str] = None
    source_documents: List[Dict[str, str]] = Field(default_factory=list)
    ai_provider_used: str = Field(default="None")
    extraction_timestamp: str = Field(default="")
    
    # The 4 required sections
    plan_vs_reality: List[GenericPlanVsRealityItem] = Field(default_factory=list)
    growth_pipeline: List[GenericGrowthPipelineItem] = Field(default_factory=list)
    demand_and_orders: GenericDemandAndOrders = Field(default_factory=GenericDemandAndOrders)
    cash_and_problems: GenericCashAndProblems = Field(default_factory=GenericCashAndProblems)

# Backward-compatible model aliases for doc_intelligence_engine & API consumers
PlanVsRealityItem = GenericPlanVsRealityItem
GrowthPipelineItem = GenericGrowthPipelineItem
DemandAndOrders = GenericDemandAndOrders
CashAndProblems = GenericCashAndProblems
CompanyDocumentIntelligence = GenericDocumentIntelligenceResult
