import sys
import os
from pathlib import Path
from typing import Dict, Any

# Ensure path includes libs and backend
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "libs"))

from doc_intelligence_models import (
    BusinessAnalysisResult, BusinessOutlookResult, BusinessQuality,
    CompetitivePosition, CapitalAllocationAudit, GovernanceAndForensicWatch,
    RecentChange, GrowthDriver, PromiseVsDeliveryItem, DemandMomentum, RisksAndCashIssues,
    StockerView, DocumentSummaryItem, CompanyFactItem
)
from doc_intelligence_engine import _apply_financial_cross_check
from financial_engine import (
    process_and_verify_company_knowledge,
    verify_document_claim_against_financials,
    build_inter_document_kpi_trends,
    triangulate_guidance_vs_projections
)

def test_1_models_and_backward_compatibility():
    print("Test 1: V4 Models & Backward-Compatibility Layer...")
    
    # 1. Instantiation with new fundamental fields
    res = BusinessAnalysisResult(
        symbol="INFY",
        company_name="Infosys Ltd",
        business_quality=BusinessQuality(
            business_model_summary="Infosys provides next-generation digital services and consulting.",
            segment_mix=[{"segment": "Financial Services", "share_pct": 27.5}],
            geography_mix=[{"region": "North America", "share_pct": 59.8}]
        ),
        competitive_position=CompetitivePosition(
            moat_type="High Switching Costs",
            key_advantages=["Global delivery network", "Deep client integration"],
            competitive_threats=["Cloud consulting competitors"]
        ),
        capital_allocation=CapitalAllocationAudit(
            capex_efficiency="CWIP at 1.2% of net block with robust FCF conversion.",
            shareholder_returns="Maintains >85% cumulative dividend payout policy."
        ),
        governance_watch=GovernanceAndForensicWatch(
            auditor_observations="Unqualified audit report with clean key audit matters."
        )
    )
    
    assert res.symbol == "INFY"
    assert res.business_quality.business_model_summary.startswith("Infosys")
    assert res.business_quality.segment_mix[0]["share_pct"] == 27.5
    assert res.competitive_position.moat_type == "High Switching Costs"
    assert res.capital_allocation.shareholder_returns.startswith("Maintains")
    assert res.governance_watch.auditor_observations.startswith("Unqualified")

    # 2. Backward compatibility with legacy dictionary payload
    legacy_payload = {
        "symbol": "TCS",
        "company_name": "Tata Consultancy Services",
        "last_analyzed_period": "Q1 FY27",
        "plan_vs_reality": [
            {
                "category": "Margins",
                "past_promise": "Target 26-28% EBIT margin",
                "original_timeline": "FY26",
                "actual_outcome": "Reported 26.2% EBIT margin",
                "source_document": "Q4 FY26 Results",
                "status": "Delivered"
            }
        ],
        "growth_pipeline": [
            {
                "initiative": "BSNL 4G/5G Network Deployment",
                "type": "Large Contract",
                "current_status": "Over 19,000 sites deployed",
                "outlay_cr": "₹15,000 Cr"
            }
        ]
    }
    
    adapted = BusinessAnalysisResult(**legacy_payload)
    assert adapted.latest_document_period == "Q1 FY27"
    assert len(adapted.promise_vs_delivery) == 1
    assert adapted.promise_vs_delivery[0].management_promise == "Target 26-28% EBIT margin"
    assert adapted.promise_vs_delivery[0].status == "Delivered"
    assert len(adapted.growth_drivers) == 1
    assert adapted.growth_drivers[0].driver_title == "BSNL 4G/5G Network Deployment"
    assert adapted.growth_drivers[0].stated_outlay_or_value == "₹15,000 Cr"
    
    print("  ✓ Test 1 passed: Fundamental models and backward-compatibility verified.")

def test_2_deterministic_financial_cross_check_enrichment():
    print("Test 2: Deterministic Financial Statement Cross-Check Enrichment...")
    
    res = BusinessAnalysisResult(
        symbol="INFY",
        company_name="Infosys Ltd"
    )
    
    mock_analytics = {
        "cash_flow_quality": {
            "cumulative_5y_pat_cr": 115000.0,
            "cumulative_5y_cfo_cr": 122000.0,
            "cumulative_5y_fcf_cr": 105000.0,
            "cfo_to_pat_5yr_pct": 106.1,
            "cash_conversion_quality": "Superior"
        },
        "balance_sheet_efficiency": {
            "latest_debt_to_equity": 0.05,
            "latest_cwip_to_net_block_pct": 3.4
        },
        "growth_rates": {
            "sales_cagr_3yr": 12.4,
            "pat_cagr_3yr": 10.8
        },
        "working_capital_audit": {
            "debtor_days": 68.5,
            "inventory_days": 0.0
        }
    }
    
    _apply_financial_cross_check(res, mock_analytics)
    
    assert "5-Year Cumulative CFO of ₹122,000 Cr vs PAT of ₹115,000 Cr (106.1% cash conversion ratio)" in res.risks_and_cash.reported_numbers_comparison
    assert "CWIP stands at 3.4% of net block with 5-Year cumulative FCF of ₹105,000 Cr" in res.capital_allocation.capex_efficiency
    assert "5-Year CFO/PAT conversion is 106.1% (Superior quality)" in res.capital_allocation.shareholder_returns
    assert "Working capital cycle: Debtor Days ~68.5 days" in res.governance_watch.working_capital_anomalies
    
    print("  ✓ Test 2 passed: Deterministic statement analytics accurately enrich Capital Allocation & Governance.")

def test_3_guidance_vs_projections_triangulation():
    print("Test 3: Guidance vs Stocker DCF Projections Triangulation...")
    
    mock_facts = [
        {
            "metric_name": "Revenue Growth",
            "stated_value_raw": "14-16%",
            "numeric_value": 15.0,
            "period_or_date": "FY27",
            "target_period": "FY27",
            "category": "management_guidance",
            "claim_type": "management_guidance",
            "doc_title": "INFY Q1 FY27 Concall",
            "doc_url": "https://example.com/infy_q1.pdf"
        },
        {
            "metric_name": "EBITDA Margin",
            "stated_value_raw": "24.5%",
            "numeric_value": 24.5,
            "period_or_date": "FY27",
            "target_period": "FY27",
            "category": "management_guidance",
            "claim_type": "management_guidance",
            "doc_title": "INFY Q1 FY27 Concall",
            "doc_url": "https://example.com/infy_q1.pdf"
        }
    ]
    
    mock_stock_data = {
        "profit_loss": None,
        "quarters": {
            "periods": ["Jun 2025", "Sep 2025", "Dec 2025", "Mar 2026", "Jun 2026"],
            "rows": [
                {"metric": "Sales", "values": {"Jun 2025": 40000.0, "Jun 2026": 44800.0}},
                {"metric": "Operating Profit", "values": {"Jun 2025": 9600.0, "Jun 2026": 10752.0}},
                {"metric": "OPM %", "values": {"Jun 2025": 24.0, "Jun 2026": 24.0}}
            ]
        }
    }
    
    mock_projections = {
        "revenue_growth_rate_pct": 12.0,
        "base_sales_cagr": 12.0,
        "bull_sales_cagr": 15.0,
        "bear_sales_cagr": 8.0,
        "target_opm_pct": 23.5,
        "projection_source": "Stocker DCF Projection Engine"
    }
    
    triangulation = triangulate_guidance_vs_projections(mock_facts, mock_stock_data, mock_projections)
    assert len(triangulation) == 2
    
    rev_item = next(t for t in triangulation if "Revenue" in t["metric_name"])
    assert rev_item["stocker_projected_base"] == 12.0
    assert rev_item["variance_guidance_vs_base_bps"] == 300.0  # (15.0 - 12.0) * 100
    assert "is +300 bps above" in rev_item["stocker_assessment"]
    assert rev_item["current_run_rate_value"] == 12.0  # (44800 - 40000)/40000 = 12% YoY
    
    opm_item = next(t for t in triangulation if "Margin" in t["metric_name"])
    assert opm_item["stocker_projected_base"] == 23.5
    assert opm_item["variance_guidance_vs_base_bps"] == 100.0  # (24.5 - 23.5) * 100
    assert "is +100 bps above" in opm_item["stocker_assessment"]
    assert opm_item["current_run_rate_value"] == 24.0
    
    print("  ✓ Test 3 passed: Guidance vs Stocker DCF projection triangulation math verified.")

def test_4_inter_document_kpi_evolution():
    print("Test 4: Inter-Document Operational KPI Evolution Time Series...")
    
    mock_facts = [
        {
            "metric_name": "Active 5G Subscribers",
            "stated_value_raw": "85 Million",
            "numeric_value": 85.0,
            "unit": "Million",
            "period_or_date": "Q1 FY26",
            "doc_title": "Airtel Q1 FY26 PPT",
            "doc_url": "https://airtel.in/q1.pdf",
            "doc_type": "presentation",
            "category": "operational_kpi",
            "claim_type": "reported_fact",
            "scope": "India Wireless"
        },
        {
            "metric_name": "Active 5G Subscribers",
            "stated_value_raw": "105 Million",
            "numeric_value": 105.0,
            "unit": "Million",
            "period_or_date": "Q2 FY26",
            "doc_title": "Airtel Q2 FY26 PPT",
            "doc_url": "https://airtel.in/q2.pdf",
            "doc_type": "presentation",
            "category": "operational_kpi",
            "claim_type": "reported_fact",
            "scope": "India Wireless"
        },
        {
            "metric_name": "Active 5G Subscribers",
            "stated_value_raw": "130 Million",
            "numeric_value": 130.0,
            "unit": "Million",
            "period_or_date": "Q3 FY26",
            "doc_title": "Airtel Q3 FY26 PPT",
            "doc_url": "https://airtel.in/q3.pdf",
            "doc_type": "presentation",
            "category": "operational_kpi",
            "claim_type": "reported_fact",
            "scope": "India Wireless"
        }
    ]
    
    trends = build_inter_document_kpi_trends(mock_facts)
    assert len(trends) == 1
    t = trends[0]
    assert t["metric_name"] == "Active 5G Subscribers"
    assert len(t["data_points"]) == 3
    assert "Expanding" in t["trajectory"]
    assert t["pct_change"] == 23.8  # (130 - 105)/105 = 23.8%
    
    print("  ✓ Test 4 passed: Multi-filing KPI time series accurately tracked.")

if __name__ == "__main__":
    test_1_models_and_backward_compatibility()
    test_2_deterministic_financial_cross_check_enrichment()
    test_3_guidance_vs_projections_triangulation()
    test_4_inter_document_kpi_evolution()
    print("\n🎉 ALL V4 BUSINESS ANALYSIS TESTS PASSED CLEANLY!")
