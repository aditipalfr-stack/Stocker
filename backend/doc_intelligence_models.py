from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field

class PlanVsRealityItem(BaseModel):
    area: str = Field(description="Target Area or Metric, e.g. 'Revenue Growth Guidance', 'Operating Margin Target'")
    management_promise: str = Field(description="What management stated or guided in previous periods")
    promised_in_period: str = Field(description="Period/Document where promise was made, e.g. 'Q1 FY26 Concall'")
    expected_timeline: str = Field(description="Committed timeline, e.g. 'By end of FY26'")
    actual_outcome: str = Field(description="What actually happened later based on subsequent filings/concalls")
    actual_in_period: str = Field(description="Period when outcome was reported, e.g. 'FY26 Annual Filing / Q4 FY26'")
    status: Literal["Delivered", "In Progress", "Delayed", "Missed", "Not enough data"]
    variance_analysis: str = Field(description="Reason for delivery, delay, or miss")
    source_document: str = Field(description="Citation with document name and section/page")
    source_url: Optional[str] = None

class GrowthPipelineItem(BaseModel):
    initiative: str = Field(description="Name of project, plant, capacity, or M&A")
    type: Literal["Capacity / Plant", "Capex Program", "M&A / Acquisition", "New Product / Market"]
    outlay_cr: Optional[str] = Field(description="Capex / Outlay in ₹ Cr, or 'Not stated'")
    target_commissioning: str = Field(description="Target timeline or COD")
    current_status: str = Field(description="Latest execution progress")
    expected_impact: str = Field(description="Management stated business or revenue impact")
    source_citation: str = Field(description="Document reference and link")
    source_url: Optional[str] = None

class DemandAndOrders(BaseModel):
    order_book_or_tcv: str = Field(description="Order backlog or quarterly deal TCV in ₹ Cr or $")
    book_to_bill_ratio: Optional[str] = Field(default="Not found", description="Book to bill ratio if stated")
    customer_or_subscriber_growth: str = Field(description="Subscriber/client additions and active accounts")
    volume_and_pricing_trends: str = Field(description="Volume growth vs pricing/realization commentary")
    segment_demand_trends: List[Dict[str, str]] = Field(description="Segment-wise acceleration vs deceleration commentary")
    market_share_signals: str = Field(description="Market share trends and competitive positioning")
    headwinds_and_risks: List[str] = Field(description="Stated demand headwinds, client caution, or macro drag")
    source_citation: str = Field(description="Document reference")
    source_url: Optional[str] = None

class CashAndProblems(BaseModel):
    cfo_fcf_drivers: str = Field(description="Primary operational drivers of operating cash flow")
    inventory_and_receivables_audit: str = Field(description="Working capital, inventory days, and receivables collection")
    debt_and_leverage_status: str = Field(description="Debt trajectory, interest costs, and capex funding source")
    operational_bottlenecks: List[str] = Field(description="Stated supply bottlenecks, margin pressures, or execution hurdles")
    financial_cross_check: str = Field(description="Verification against our actual numerical balance sheet / cash flow data")
    source_citation: str = Field(description="Document reference")
    source_url: Optional[str] = None

class CompanyDocumentIntelligence(BaseModel):
    symbol: str
    company_name: str
    last_analyzed_period: str
    analyzed_documents: List[Dict[str, str]]  # [{"title": "...", "type": "concall/annual_report", "period": "...", "url": "..."}]
    
    # 4 Clean Core Sections
    plan_vs_reality: List[PlanVsRealityItem]
    growth_pipeline: List[GrowthPipelineItem]
    demand_and_orders: DemandAndOrders
    cash_and_problems: CashAndProblems
