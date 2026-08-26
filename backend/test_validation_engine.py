import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "libs"))
sys.path.insert(0, str(Path(__file__).parent))

from financial_engine import parse_filing_period_to_year, verify_promise_vs_delivery_item, compute_financial_analytics
from models import FinancialStatement, FinancialRow

def test_chronology_parser():
    print("Testing period string parser...")
    assert parse_filing_period_to_year("FY24") == 2024.0
    assert parse_filing_period_to_year("FY2025") == 2025.0
    assert parse_filing_period_to_year("Q2 FY25") == 2024.5
    assert parse_filing_period_to_year("Mar 2026") == 2026.25
    print("✓ Chronology parsing passed.")

def test_chronology_enforcement():
    print("Testing chronology and backwards comparison rejection...")
    # Test case 1: Backwards outcome (Actual is FY23, Promise is FY25)
    bad_item = {
        "area": "Retail Growth",
        "management_promise": "Double footprint to 30,000 stores",
        "promised_in_period": "FY25",
        "actual_outcome": "Expanded store count by 10%",
        "actual_in_period": "FY23",
        "status": "Delivered"
    }
    verified = verify_promise_vs_delivery_item(bad_item)
    assert verified["status"] == "Not Enough Evidence"
    assert "Chronological Mismatch" in verified["stocker_analysis"]
    print("✓ Backwards chronological comparison successfully rejected.")

    # Test case 2: Future deadline (Target FY28)
    future_item = {
        "area": "New Energy Gigafactory",
        "management_promise": "Commission 20GW solar giga-complex by FY28",
        "target_timeline": "FY28",
        "promised_in_period": "FY24",
        "actual_outcome": "Phase 1 civil work initiated",
        "actual_in_period": "FY26",
        "status": "Delivered"
    }
    verified_future = verify_promise_vs_delivery_item(future_item)
    assert verified_future["status"] == "In Progress"
    print("✓ Future target milestone correctly forced to 'In Progress'.")

def test_mathematical_achievement():
    print("Testing mathematical achievement rate verification...")
    pl = FinancialStatement(
        periods=["Mar 2024", "Mar 2025", "Mar 2026"],
        rows=[
            FinancialRow(metric="Sales", values={"Mar 2024": 100000.0, "Mar 2025": 120000.0, "Mar 2026": 138000.0}),
            FinancialRow(metric="OPM %", values={"Mar 2024": 15.0, "Mar 2025": 16.0, "Mar 2026": 16.5}),
            FinancialRow(metric="Net Profit", values={"Mar 2024": 10000.0, "Mar 2025": 12500.0, "Mar 2026": 15000.0})
        ]
    )
    guided_item = {
        "area": "Revenue Guidance",
        "management_promise": "Guide for 20% revenue growth in FY26",
        "promised_in_period": "FY25",
        "actual_outcome": "Reported audited annual numbers",
        "actual_in_period": "FY26",
        "status": "Delivered"
    }
    verified = verify_promise_vs_delivery_item(guided_item, pl_stmt=pl)
    # Sales grew from 120000 to 138000 = 15.0% YoY vs 20% promised -> Achievement: 75.0%
    assert "75.0%" in verified["financial_numbers_check"]
    print("✓ Numerical achievement percentage correctly computed: 75.0%.")

def test_formula_transparency():
    print("Testing formula transparency in financial analytics...")
    pl = FinancialStatement(
        periods=["Mar 2023", "Mar 2024", "Mar 2025", "Mar 2026"],
        rows=[
            FinancialRow(metric="Sales", values={"Mar 2023": 100000.0, "Mar 2024": 115000.0, "Mar 2025": 130000.0, "Mar 2026": 149000.0}),
            FinancialRow(metric="Operating Profit", values={"Mar 2023": 15000.0, "Mar 2024": 18000.0, "Mar 2025": 21000.0, "Mar 2026": 25000.0}),
            FinancialRow(metric="OPM %", values={"Mar 2023": 15.0, "Mar 2024": 15.6, "Mar 2025": 16.1, "Mar 2026": 16.8}),
            FinancialRow(metric="Net Profit", values={"Mar 2023": 10000.0, "Mar 2024": 12000.0, "Mar 2025": 14000.0, "Mar 2026": 17000.0})
        ]
    )
    bs = FinancialStatement(
        periods=["Mar 2023", "Mar 2024", "Mar 2025", "Mar 2026"],
        rows=[
            FinancialRow(metric="Equity Capital", values={"Mar 2023": 1000.0, "Mar 2024": 1000.0, "Mar 2025": 1000.0, "Mar 2026": 1000.0}),
            FinancialRow(metric="Reserves", values={"Mar 2023": 49000.0, "Mar 2024": 59000.0, "Mar 2025": 71000.0, "Mar 2026": 86000.0}),
            FinancialRow(metric="Borrowings", values={"Mar 2023": 20000.0, "Mar 2024": 22000.0, "Mar 2025": 24000.0, "Mar 2026": 26000.0}),
            FinancialRow(metric="Fixed Assets", values={"Mar 2023": 40000.0, "Mar 2024": 48000.0, "Mar 2025": 58000.0, "Mar 2026": 70000.0}),
            FinancialRow(metric="CWIP", values={"Mar 2023": 5000.0, "Mar 2024": 6000.0, "Mar 2025": 7000.0, "Mar 2026": 8000.0}),
            FinancialRow(metric="Total Assets", values={"Mar 2023": 70000.0, "Mar 2024": 82000.0, "Mar 2025": 96000.0, "Mar 2026": 113000.0})
        ]
    )
    cf = FinancialStatement(
        periods=["Mar 2023", "Mar 2024", "Mar 2025", "Mar 2026"],
        rows=[
            FinancialRow(metric="Cash from Operating Activity", values={"Mar 2023": 12000.0, "Mar 2024": 14500.0, "Mar 2025": 17000.0, "Mar 2026": 21000.0}),
            FinancialRow(metric="Fixed assets purchased", values={"Mar 2023": 8000.0, "Mar 2024": 10000.0, "Mar 2025": 12000.0, "Mar 2026": 15000.0})
        ]
    )
    q = FinancialStatement(
        periods=["Jun 2025", "Sep 2025", "Dec 2025", "Mar 2026"],
        rows=[
            FinancialRow(metric="Sales", values={"Jun 2025": 35000.0, "Sep 2025": 37000.0, "Dec 2025": 38000.0, "Mar 2026": 39000.0}),
            FinancialRow(metric="Operating Profit", values={"Jun 2025": 6000.0, "Sep 2025": 6200.0, "Dec 2025": 6400.0, "Mar 2026": 6500.0}),
            FinancialRow(metric="OPM %", values={"Jun 2025": 17.1, "Sep 2025": 16.8, "Dec 2025": 16.8, "Mar 2026": 16.7}),
            FinancialRow(metric="Net Profit", values={"Jun 2025": 4000.0, "Sep 2025": 4200.0, "Dec 2025": 4300.0, "Mar 2026": 4500.0})
        ]
    )
    analytics = compute_financial_analytics(q, pl, bs, cf)
    assert "formula_transparency" in analytics
    ft = analytics["formula_transparency"]
    assert "sales_cagr_3yr" in ft
    assert "free_cash_flow" in ft
    assert ft["free_cash_flow"]["value"] == 6000.0 # CFO 21000 - Capex 15000 = 6000
    assert ft["free_cash_flow"]["formula"] == "FCF = CFO - Capex"
    print("✓ Formula transparency verified successfully.")

if __name__ == "__main__":
    test_chronology_parser()
    test_chronology_enforcement()
    test_mathematical_achievement()
    test_formula_transparency()
    print("\n🎉 ALL VERIFICATION ENGINE TESTS PASSED!")
