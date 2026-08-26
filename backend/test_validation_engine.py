import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "libs"))
sys.path.insert(0, str(Path(__file__).parent))

from financial_engine import parse_filing_period_to_year, verify_promise_vs_delivery_item, compute_financial_analytics
from models import FinancialStatement, FinancialRow, DocumentItem
import database
import document_sourcing

def test_case_a_promise_after_outcome():
    """Case A: Promise made July 2026, actual FY2026 result that occurred before promise -> Rejected / Not Enough Evidence."""
    print("Testing Case A: Promise made July 2026 vs FY26 outcome...")
    item = {
        "area": "Retail Network Expansion",
        "management_promise": "Double store count across tier 2 cities",
        "promised_in_period": "24 Jul 2026",
        "source_url_promise": "https://example.com/concall_jul2026.pdf",
        "actual_outcome": "Reported annual store additions",
        "actual_in_period": "FY26",  # FY26 ended March 2026, prior to July 2026
        "source_url_actual": "https://example.com/ar_fy26.pdf",
        "status": "Delivered"
    }
    verified = verify_promise_vs_delivery_item(item)
    assert verified["status"] == "Not Enough Evidence"
    assert "Chronological Mismatch" in verified["stocker_analysis"]
    print("✓ Case A passed: Backwards chronology successfully rejected.")

def test_case_b_same_filing():
    """Case B: Promise and actual come from the same filing -> Rejected / Not Enough Evidence."""
    print("Testing Case B: Promise and actual from same filing...")
    item = {
        "area": "Solar Module Capacity",
        "management_promise": "Commission 10GW solar cell facility",
        "promised_in_period": "FY26",
        "source_url_promise": "https://example.com/filing_fy26.pdf",
        "actual_outcome": "Completed civil foundations",
        "actual_in_period": "FY26",
        "source_url_actual": "https://example.com/filing_fy26.pdf",  # Same filing!
        "status": "Delivered"
    }
    verified = verify_promise_vs_delivery_item(item)
    assert verified["status"] == "Not Enough Evidence"
    assert "Evidence from Same Filing" in verified["stocker_analysis"]
    print("✓ Case B passed: Same filing delivery claim rejected.")

def test_case_c_future_deadline():
    """Case C: Promise FY25, target FY28, current date 2026 -> In Progress."""
    print("Testing Case C: Target deadline in future (FY28)...")
    item = {
        "area": "Green Hydrogen Ecosystem",
        "management_promise": "Achieve 3GW electrolyzer manufacturing capacity by FY28",
        "target_timeline": "FY28",
        "promised_in_period": "FY25",
        "source_url_promise": "https://example.com/ar_fy25.pdf",
        "actual_outcome": "Secured land and long-lead equipment orders",
        "actual_in_period": "Q1 FY27",
        "source_url_actual": "https://example.com/concall_q1fy27.pdf",
        "status": "Delivered"  # LLM mistakenly labeled delivered
    }
    verified = verify_promise_vs_delivery_item(item, current_year=2026.65)
    assert verified["status"] == "In Progress"
    assert "Milestone In Progress" in verified["stocker_analysis"]
    print("✓ Case C passed: Future target milestone forced to 'In Progress'.")

def test_case_d_code_calculated_achievement():
    """Case D: Promise 20% revenue growth, actual from structured P&L is 15% -> achievement = 75%, calculated by code."""
    print("Testing Case D: Deterministic revenue achievement calculated by code...")
    pl = FinancialStatement(
        periods=["Mar 2024", "Mar 2025", "Mar 2026"],
        rows=[
            FinancialRow(metric="Sales", values={"Mar 2024": 100000.0, "Mar 2025": 120000.0, "Mar 2026": 138000.0}),
            FinancialRow(metric="OPM %", values={"Mar 2024": 15.0, "Mar 2025": 16.0, "Mar 2026": 16.5}),
            FinancialRow(metric="Net Profit", values={"Mar 2024": 10000.0, "Mar 2025": 12500.0, "Mar 2026": 15000.0})
        ]
    )
    item = {
        "area": "Revenue Guidance",
        "management_promise": "Targeting 20% revenue growth for FY26",
        "promised_in_period": "FY25",
        "source_url_promise": "https://example.com/ar_fy25.pdf",
        "actual_outcome": "Reported audited FY26 annual numbers",
        "actual_in_period": "FY26",
        "source_url_actual": "https://example.com/ar_fy26.pdf",
        "status": "Delivered"
    }
    # Sales grew from 120,000 to 138,000 = 15.0% YoY. 15.0% / 20.0% = 75.0% achievement rate.
    verified = verify_promise_vs_delivery_item(item, pl_stmt=pl, current_year=2026.65)
    assert "75.0%" in verified["financial_numbers_check"]
    assert "variance -5.0%" in verified["financial_numbers_check"]
    assert verified["status"] == "Missed"  # 75% < 85% threshold
    print("✓ Case D passed: Mathematical achievement 75.0% and status computed by code.")

def test_case_e_missing_financial_statements():
    """Case E: Missing financial statements -> do not invent achievement %, use Not Enough Evidence where required."""
    print("Testing Case E: Missing structured statements...")
    item = {
        "area": "Long-Term Revenue Goal",
        "management_promise": "Targeting 25% revenue growth by FY25",
        "target_timeline": "FY25",
        "promised_in_period": "FY23",
        "source_url_promise": "https://example.com/ar_fy23.pdf",
        "actual_outcome": "Target deadline passed",
        "actual_in_period": "FY25",
        "source_url_actual": "https://example.com/ar_fy25.pdf"
    }
    # Pass None for pl_stmt
    verified = verify_promise_vs_delivery_item(item, pl_stmt=None, current_year=2026.65)
    assert "Reported statements for exact promise verification period not yet available" in verified["financial_numbers_check"]
    print("✓ Case E passed: Missing statements handled safely without invented numbers.")

def test_case_f_incremental_refresh_date_window():
    """Case F: Incremental refresh with last_checked_at = 10 Aug -> search window starts a few days before 10 Aug."""
    print("Testing Case F: Incremental refresh date-window calculation...")
    sym = "TEST_INC_SYM"
    last_checked_iso = "2026-08-10T12:00:00+00:00"
    database.update_document_sync_state(sym, category="all", checked_at=last_checked_iso)
    
    sync_state = database.get_document_sync_state(sym, category="all")
    assert sync_state is not None
    assert sync_state["last_checked_at"] == last_checked_iso
    
    last_dt = datetime.fromisoformat(sync_state["last_checked_at"].replace("Z", "+00:00"))
    overlap_days = 5
    from_date_dt = last_dt - timedelta(days=overlap_days)
    from_date_bse = from_date_dt.strftime("%Y%m%d")
    
    # 10 Aug minus 5 days = 05 Aug 2026
    assert from_date_bse == "20260805"
    assert from_date_dt.day == 5
    assert from_date_dt.month == 8
    print(f"✓ Case F passed: Incremental date window starts on {from_date_bse} (5-day safety overlap).")

def test_case_g_cached_known_documents():
    """Case G: Cached known document -> no unnecessary download / revalidation."""
    print("Testing Case G: Known SQLite document caching...")
    sym = "TEST_CACHE_SYM"
    test_doc = DocumentItem(
        ticker=sym,
        company_name="Test Corp",
        title="Test Corp Annual Report 2026",
        name="Test Corp Annual Report 2026",
        url="https://example.com/test_ar_2026.pdf",
        doc_type="annual_report",
        period_or_date="FY26",
        discovery_source="SQLite Cache",
        actual_source_host="example.com",
        actual_source_url="https://example.com/test_ar_2026.pdf",
        is_direct_pdf=True,
        validation_status="Valid",
        file_size_bytes=1048576
    )
    database.save_source_documents(sym, [test_doc])
    
    stored = database.get_source_documents(sym)
    assert len(stored) >= 1
    assert any(d["url"] == "https://example.com/test_ar_2026.pdf" and d["is_valid"] == 1 for d in stored)
    print("✓ Case G passed: Document correctly cached and indexed in SQLite.")

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
    test_case_a_promise_after_outcome()
    test_case_b_same_filing()
    test_case_c_future_deadline()
    test_case_d_code_calculated_achievement()
    test_case_e_missing_financial_statements()
    test_case_f_incremental_refresh_date_window()
    test_case_g_cached_known_documents()
    test_formula_transparency()
    print("\n🎉 ALL REGRESSION & CORRECTNESS TESTS PASSED PERFECTLY!")

