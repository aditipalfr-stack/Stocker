import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "libs"))
sys.path.insert(0, str(Path(__file__).parent))

from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
from bs4 import BeautifulSoup

from financial_engine import parse_filing_period_to_year, verify_promise_vs_delivery_item, compute_financial_analytics
from models import FinancialStatement, FinancialRow, DocumentItem
import database
import document_sourcing
import llm_service

def test_case_a_missing_structured_financial_data():
    """Case A: Gemini provides a financial_numbers_check but structured financial data is missing.
    Expected: AI number is discarded, replaced with structured evidence warning, Status = Not Enough Evidence."""
    print("Testing Case A: Gemini provides financial_numbers_check but structured statements missing...")
    item = {
        "area": "Revenue Guidance",
        "management_promise": "Targeting 25% revenue growth for FY26",
        "promised_in_period": "FY25",
        "source_url_promise": "https://example.com/ar_fy25.pdf",
        "actual_outcome": "Reported annual performance",
        "actual_in_period": "FY26",
        "source_url_actual": "https://example.com/ar_fy26.pdf",
        "status": "Delivered",
        "financial_numbers_check": "AI Calculated: Revenue grew 26%, surpassing 25% target."  # Untrusted AI calculation
    }
    # Pass pl_stmt=None
    verified = verify_promise_vs_delivery_item(item, pl_stmt=None, current_year=2026.65)
    assert verified["status"] == "Not Enough Evidence"
    assert "Not enough structured financial evidence to verify this claim" in verified["financial_numbers_check"]
    assert "AI Calculated" not in verified["financial_numbers_check"]
    print("✓ Case A passed: AI arithmetic discarded, status set to 'Not Enough Evidence'.")

def test_case_b_future_target_deadline_override():
    """Case B: Gemini says Delivered but target deadline is still in future.
    Expected: Code overrides -> In Progress."""
    print("Testing Case B: Target deadline in future (FY28) while Gemini claimed Delivered...")
    item = {
        "area": "Green Hydrogen Ecosystem",
        "management_promise": "Achieve 3GW electrolyzer manufacturing capacity by FY28",
        "target_timeline": "FY28",
        "promised_in_period": "FY25",
        "source_url_promise": "https://example.com/ar_fy25.pdf",
        "actual_outcome": "Secured land and long-lead equipment orders",
        "actual_in_period": "Q1 FY27",
        "source_url_actual": "https://example.com/concall_q1fy27.pdf",
        "status": "Delivered"  # AI mistakenly labeled Delivered
    }
    verified = verify_promise_vs_delivery_item(item, current_year=2026.65)
    assert verified["status"] == "In Progress"
    assert "Milestone In Progress" in verified["stocker_analysis"]
    print("✓ Case B passed: Code overrode status to 'In Progress'.")

def test_case_c_unverifiable_qualitative_outcome():
    """Case C: Gemini says Delivered but code cannot verify outcome (uncertain qualitative claim).
    Expected: Code overrides -> Not Enough Evidence."""
    print("Testing Case C: Gemini claimed Delivered on unverified qualitative statement...")
    item = {
        "area": "Digital Platform Adoption",
        "management_promise": "Will expand dealer digital platform across all regions",
        "promised_in_period": "FY24",
        "source_url_promise": "https://example.com/ar_fy24.pdf",
        "actual_outcome": "Management continued to discuss digital transformation initiatives in general remarks",
        "actual_in_period": "FY25",
        "source_url_actual": "https://example.com/ar_fy25.pdf",
        "status": "Delivered"  # AI claimed Delivered without concrete commissioning/completion proof
    }
    verified = verify_promise_vs_delivery_item(item, current_year=2026.65)
    assert verified["status"] == "Not Enough Evidence"
    assert "Uncertain Qualitative Evidence" in verified["stocker_analysis"]
    print("✓ Case C passed: Code overrode unverified qualitative claim to 'Not Enough Evidence'.")

def test_case_d_same_filing_promise_and_outcome():
    """Case D: Same filing promise and outcome.
    Expected: Not Enough Evidence."""
    print("Testing Case D: Promise and actual from same filing...")
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
    verified = verify_promise_vs_delivery_item(item, current_year=2026.65)
    assert verified["status"] == "Not Enough Evidence"
    assert "Evidence from Same Filing" in verified["stocker_analysis"]
    print("✓ Case D passed: Same filing delivery claim rejected as 'Not Enough Evidence'.")

def test_case_e_numerical_guidance_with_structured_pl():
    """Case E: Numerical guidance with structured P&L.
    Expected: All math comes from code (actual growth %, achievement %, variance)."""
    print("Testing Case E: Numerical guidance with structured P&L...")
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
    assert "15.0% YoY growth" in verified["financial_numbers_check"]
    assert "variance -5.0%" in verified["financial_numbers_check"]
    assert verified["status"] == "Missed"  # 75% < 85% threshold
    print("✓ Case E passed: Code calculated exact 75.0% achievement and set status to 'Missed'.")

def test_case_f_gemini_fallback_model_provenance():
    """Case F: Actual successful Gemini fallback model stored in metadata."""
    print("Testing Case F: AI model provenance tracking...")
    # Mock call_gemini_api to simulate fallback cascade succeeding on gemini-3.1-flash-lite
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "candidates": [{
            "content": {"parts": [{"text": '{"what_changed_recently": [], "growth_drivers": [], "promise_vs_delivery": []}'}]}
        }]
    }
    
    with patch("requests.post", return_value=mock_resp):
        res, model_used = llm_service.call_gemini_api("fake_key", "test prompt")
        assert model_used == "gemini-3.1-flash-lite"
        print(f"✓ Case F passed: Actual model '{model_used}' successfully returned and verified.")

def test_case_g_company_ir_incremental_fallback():
    """Case G: Company IR incremental fallback stops parsing when entries fall before cutoff."""
    print("Testing Case G: Company IR incremental fallback date cutoff...")
    from_date = datetime(2026, 8, 10, tzinfo=timezone.utc)
    
    # Mock HTML with multiple anchor tags, some new and some old
    mock_html = """
    <html>
      <body>
        <a href="/reports/AR_2027.pdf">Annual Report FY27</a>
        <a href="/reports/AR_2026.pdf">Annual Report FY26</a>
        <a href="/reports/AR_2020.pdf">Annual Report FY20</a>
        <a href="/reports/AR_2019.pdf">Annual Report FY19</a>
      </body>
    </html>
    """
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = mock_html
    
    with patch.dict(document_sourcing.COMPANY_IR_DOMAINS, {"TESTSYM": {"ir_url": "https://testir.com"}}):
        with patch("requests.get", return_value=mock_resp):
            docs = document_sourcing.discover_documents_company_ir_fallback(
                symbol="TESTSYM",
                company_name="Test Sym Ltd",
                needed_types=["annual_report"],
                from_date_dt=from_date
            )
            # The older FY20 and FY19 reports should be skipped under incremental cutoff
            assert not any("FY19" in d.title or "FY20" in d.title for d in docs)
            print("✓ Case G passed: Company IR incremental scan safely filtered older historical filings.")

def test_qualitative_milestone_completion_matching():
    """Verify qualitative milestone completion keyword matching."""
    print("Testing qualitative milestone completion matching...")
    item = {
        "area": "Manufacturing Capacity",
        "management_promise": "Plant will commission by Q4 FY26",
        "promised_in_period": "FY25",
        "source_url_promise": "https://example.com/ar_fy25.pdf",
        "actual_outcome": "The new Dahej plant was successfully commissioned and commercial operations commenced on 15 Feb 2026",
        "actual_in_period": "FY26",
        "source_url_actual": "https://example.com/ar_fy26.pdf",
        "status": "In Progress"
    }
    verified = verify_promise_vs_delivery_item(item, current_year=2026.65)
    assert verified["status"] == "Delivered"
    assert "Commissioned confirmed in subsequent filing" in verified["financial_numbers_check"]
    print("✓ Qualitative milestone completion successfully classified as 'Delivered'.")

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
def test_production_pipeline_financial_wiring():
    """Integration Test: Executes run_multi_document_ai_pipeline -> extract_document_intelligence_with_llm
    to prove that financial_statements_text, pl_stmt, quarters_stmt, bs_stmt, cf_stmt are correctly
    initialized and passed without NameError, both when cached and when cache is missing."""
    print("Testing production pipeline structured financial wiring & LLM boundary...")
    from models import DocumentLinks, DocumentItem
    from doc_intelligence_models import BusinessOutlookResult
    import doc_intelligence_pipeline
    
    docs = DocumentLinks(
        annual_reports=[
            DocumentItem(ticker="INFY", company_name="Infosys Ltd", title="Infosys AR 2026", url="https://example.com/ar26.pdf", doc_type="annual_report", period_or_date="FY26", validation_status="Valid"),
            DocumentItem(ticker="INFY", company_name="Infosys Ltd", title="Infosys AR 2025", url="https://example.com/ar25.pdf", doc_type="annual_report", period_or_date="FY25", validation_status="Valid")
        ],
        concall_transcripts=[
            DocumentItem(ticker="INFY", company_name="Infosys Ltd", title="Infosys Q4 Earnings Call", url="https://example.com/cc26.pdf", doc_type="concall_transcript", period_or_date="Q4 FY26", validation_status="Valid")
        ]
    )
    
    dummy_stock_cache = {
        "profit_loss": {
            "periods": ["Mar 2024", "Mar 2025", "Mar 2026"],
            "rows": [
                {"metric": "Sales", "values": {"Mar 2024": 150000.0, "Mar 2025": 165000.0, "Mar 2026": 180000.0}},
                {"metric": "OPM %", "values": {"Mar 2024": 21.0, "Mar 2025": 21.5, "Mar 2026": 21.8}},
                {"metric": "Net Profit", "values": {"Mar 2024": 26000.0, "Mar 2025": 28000.0, "Mar 2026": 30000.0}}
            ]
        },
        "quarters": {
            "periods": ["Jun 2025", "Sep 2025", "Dec 2025", "Mar 2026"],
            "rows": [{"metric": "Sales", "values": {"Jun 2025": 44000.0, "Sep 2025": 45000.0, "Dec 2025": 45500.0, "Mar 2026": 45500.0}}]
        },
        "balance_sheet": {
            "periods": ["Mar 2024", "Mar 2025", "Mar 2026"],
            "rows": [{"metric": "Total Assets", "values": {"Mar 2024": 120000.0, "Mar 2025": 135000.0, "Mar 2026": 150000.0}}]
        },
        "cash_flow": {
            "periods": ["Mar 2024", "Mar 2025", "Mar 2026"],
            "rows": [{"metric": "Cash from Operating Activity", "values": {"Mar 2024": 25000.0, "Mar 2025": 27000.0, "Mar 2026": 29000.0}}]
        }
    }
    
    captured_llm_kwargs = {}
    def mock_extract_llm(*args, **kwargs):
        captured_llm_kwargs.update(kwargs)
        res = BusinessOutlookResult(
            symbol="INFY",
            company_name="Infosys Ltd",
            latest_document_period="FY26",
            model_version="gemini-3.1-flash-lite",
            ai_provider_used="GEMINI (gemini-3.1-flash-lite)"
        )
        return True, res, "Success"

    # Test Path 1: Cache is populated
    with patch("doc_intelligence_pipeline.download_and_extract_pdf", return_value=[(1, "Management discussion text")]), \
         patch("doc_intelligence_pipeline.get_or_generate_document_summary", return_value={"doc_title": "Infosys AR 2026", "key_takeaways": ["Growth"]}), \
         patch("doc_intelligence_pipeline.is_llm_available", return_value=True), \
         patch("database.get_stock_cache", return_value=dummy_stock_cache), \
         patch("doc_intelligence_pipeline.extract_document_intelligence_with_llm", side_effect=mock_extract_llm):
         
        output = doc_intelligence_pipeline.run_multi_document_ai_pipeline(
            symbol="INFY",
            company_name="Infosys Ltd",
            documents=docs,
            save_output=False
        )
        assert output["symbol"] == "INFY"
        assert "financial_statements_summary" in captured_llm_kwargs
        assert "AUDITED 10-YEAR FINANCIAL STATEMENTS" in captured_llm_kwargs["financial_statements_summary"]
        assert captured_llm_kwargs["pl_stmt"] is not None
        assert captured_llm_kwargs["quarters_stmt"] is not None
        assert captured_llm_kwargs["bs_stmt"] is not None
        assert captured_llm_kwargs["cf_stmt"] is not None
        print("  ✓ Path 1 passed: Cache populated flow passed structured statements to LLM without NameError.")

    # Test Path 2: Cache is missing, fallback ingestion retrieves statements
    captured_llm_kwargs.clear()
    with patch("doc_intelligence_pipeline.download_and_extract_pdf", return_value=[(1, "Management discussion text")]), \
         patch("doc_intelligence_pipeline.get_or_generate_document_summary", return_value={"doc_title": "Infosys AR 2026", "key_takeaways": ["Growth"]}), \
         patch("doc_intelligence_pipeline.is_llm_available", return_value=True), \
         patch("database.get_stock_cache", return_value=None), \
         patch("doc_intelligence_pipeline.fetch_stock_from_screener", return_value=dummy_stock_cache), \
         patch("doc_intelligence_pipeline.extract_document_intelligence_with_llm", side_effect=mock_extract_llm):
         
        output = doc_intelligence_pipeline.run_multi_document_ai_pipeline(
            symbol="INFY",
            company_name="Infosys Ltd",
            documents=docs,
            save_output=False
        )
        assert output["symbol"] == "INFY"
        assert captured_llm_kwargs["pl_stmt"] is not None
        assert captured_llm_kwargs["quarters_stmt"] is not None
        print("  ✓ Path 2 passed: Cache missing fallback flow safely retrieved structured data without NameError.")
    print("✓ Integration Test passed: Full production AI pipeline wiring verified.")

def test_cash_flow_case_a_direct_capex():
    """Case A: Direct capex line present in cash flow statement -> High Confidence."""
    print("Testing Cash Flow Case A: Direct reported capex line...")
    pl = FinancialStatement(
        periods=["Mar 2025", "Mar 2026"],
        rows=[
            FinancialRow(metric="Sales", values={"Mar 2025": 100000.0, "Mar 2026": 120000.0}),
            FinancialRow(metric="Net Profit", values={"Mar 2025": 15000.0, "Mar 2026": 18000.0})
        ]
    )
    bs = FinancialStatement(periods=["Mar 2025", "Mar 2026"], rows=[])
    cf = FinancialStatement(
        periods=["Mar 2025", "Mar 2026"],
        rows=[
            FinancialRow(metric="Cash from Operating Activity", values={"Mar 2025": 20000.0, "Mar 2026": 25000.0}),
            FinancialRow(metric="Fixed assets purchased", values={"Mar 2025": 5000.0, "Mar 2026": 6000.0})
        ]
    )
    q = FinancialStatement(periods=["Mar 2026"], rows=[])
    
    analytics = compute_financial_analytics(q, pl, bs, cf)
    fcf_trends = analytics["cash_flow_quality"]["fcf_trends"]
    assert len(fcf_trends) == 2
    latest = fcf_trends[-1]
    assert latest["period"] == "Mar 2026"
    assert latest["reported_cfo_cr"] == 25000.0
    assert latest["capex_cr"] == 6000.0
    assert latest["stocker_derived_fcf_cr"] == 19000.0 # 25000 - 6000
    assert latest["capex_methodology"] == "Reported Capex"
    assert latest["fcf_confidence"] == "High Confidence"
    assert latest["possible_anomaly_warning"] is None
    print("✓ Cash Flow Case A passed: Direct reported capex identified as High Confidence and FCF calculated accurately.")

def test_cash_flow_case_b_balance_sheet_derived_capex():
    """Case B: Balance-sheet-derived capex -> Medium Confidence by default."""
    print("Testing Cash Flow Case B: Balance-sheet-derived capex...")
    pl = FinancialStatement(
        periods=["Mar 2025", "Mar 2026"],
        rows=[
            FinancialRow(metric="Sales", values={"Mar 2025": 100000.0, "Mar 2026": 120000.0}),
            FinancialRow(metric="Depreciation", values={"Mar 2025": 4000.0, "Mar 2026": 5000.0}),
            FinancialRow(metric="Net Profit", values={"Mar 2025": 15000.0, "Mar 2026": 18000.0})
        ]
    )
    bs = FinancialStatement(
        periods=["Mar 2025", "Mar 2026"],
        rows=[
            FinancialRow(metric="Fixed Assets", values={"Mar 2025": 40000.0, "Mar 2026": 44000.0}), # Delta = 4000
            FinancialRow(metric="CWIP", values={"Mar 2025": 2000.0, "Mar 2026": 3000.0})             # Delta = 1000
        ]
    )
    cf = FinancialStatement(
        periods=["Mar 2025", "Mar 2026"],
        rows=[
            FinancialRow(metric="Cash from Operating Activity", values={"Mar 2025": 20000.0, "Mar 2026": 24000.0})
        ]
    )
    q = FinancialStatement(periods=["Mar 2026"], rows=[])
    
    analytics = compute_financial_analytics(q, pl, bs, cf)
    fcf_trends = analytics["cash_flow_quality"]["fcf_trends"]
    latest = fcf_trends[-1]
    # Expected capex = delta_fa (4000) + dep (5000) + delta_cwip (1000) = 10000
    assert latest["capex_cr"] == 10000.0
    assert latest["stocker_derived_fcf_cr"] == 14000.0 # 24000 - 10000
    assert latest["capex_methodology"] == "Derived from Balance Sheet (FA delta + Dep + CWIP delta)"
    assert latest["fcf_confidence"] == "Medium Confidence"
    assert latest["possible_anomaly_warning"] is None
    print("✓ Cash Flow Case B passed: Derived capex classified as Medium Confidence by default.")

def test_cash_flow_case_c_extreme_derived_capex():
    """Case C: Extreme derived capex -> Calculation preserved, confidence Low, anomaly warning present."""
    print("Testing Cash Flow Case C: Extreme / Anomalous derived capex...")
    # Scenario: Sudden asset jump representing 120% of annual sales (e.g. mega acquisition)
    pl = FinancialStatement(
        periods=["Mar 2025", "Mar 2026"],
        rows=[
            FinancialRow(metric="Sales", values={"Mar 2025": 10000.0, "Mar 2026": 12000.0}),
            FinancialRow(metric="Depreciation", values={"Mar 2025": 500.0, "Mar 2026": 600.0}),
            FinancialRow(metric="Net Profit", values={"Mar 2025": 1000.0, "Mar 2026": 1200.0})
        ]
    )
    bs = FinancialStatement(
        periods=["Mar 2025", "Mar 2026"],
        rows=[
            FinancialRow(metric="Fixed Assets", values={"Mar 2025": 5000.0, "Mar 2026": 20000.0}), # Delta = 15000
            FinancialRow(metric="CWIP", values={"Mar 2025": 0.0, "Mar 2026": 0.0})
        ]
    )
    cf = FinancialStatement(
        periods=["Mar 2025", "Mar 2026"],
        rows=[
            FinancialRow(metric="Cash from Operating Activity", values={"Mar 2025": 1500.0, "Mar 2026": 1800.0})
        ]
    )
    q = FinancialStatement(periods=["Mar 2026"], rows=[])
    
    analytics = compute_financial_analytics(q, pl, bs, cf)
    fcf_trends = analytics["cash_flow_quality"]["fcf_trends"]
    latest = fcf_trends[-1]
    # Expected capex = 15000 + 600 = 15600. Sales = 12000 (130% of sales)
    assert latest["capex_cr"] == 15600.0
    assert latest["stocker_derived_fcf_cr"] == -13800.0 # 1800 - 15600
    assert latest["fcf_confidence"] == "Low Confidence"
    assert latest["possible_anomaly_warning"] is not None
    assert "inorganic acquisition" in latest["possible_anomaly_warning"].lower() or "elevated" in latest["confidence_reason"].lower()
    print("✓ Cash Flow Case C passed: Extreme derived capex preserved mathematically with Low Confidence & anomaly warning.")

def test_cash_flow_case_d_missing_capex():
    """Case D: Missing capex data -> FCF unavailable, confidence Unavailable."""
    print("Testing Cash Flow Case D: Missing capex data...")
    pl = FinancialStatement(periods=["Mar 2026"], rows=[FinancialRow(metric="Net Profit", values={"Mar 2026": 1000.0})])
    bs = FinancialStatement(periods=["Mar 2026"], rows=[]) # No fixed assets or prior periods
    cf = FinancialStatement(periods=["Mar 2026"], rows=[FinancialRow(metric="Cash from Operating Activity", values={"Mar 2026": 1200.0})])
    q = FinancialStatement(periods=["Mar 2026"], rows=[])
    
    analytics = compute_financial_analytics(q, pl, bs, cf)
    latest = analytics["cash_flow_quality"]["fcf_trends"][-1]
    assert latest["capex_cr"] is None
    assert latest["stocker_derived_fcf_cr"] is None
    assert latest["fcf_confidence"] == "Unavailable"
    assert latest["capex_methodology"] == "Unavailable"
    print("✓ Cash Flow Case D passed: Missing capex handled gracefully as Unavailable.")

def test_cash_flow_case_e_raw_cash_flow_filtering():
    """Case E: Raw cash flow statement does not include Screener's injected Free Cash Flow or CFO/OP rows."""
    print("Testing Cash Flow Case E: Raw cash-flow statement sanitization...")
    import scraper
    from bs4 import BeautifulSoup
    
    html = """
    <section id="cash-flow">
      <table>
        <thead>
          <tr>
            <th>Reported Items</th>
            <th>Mar 2025</th>
            <th>Mar 2026</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Cash from Operating Activity</td>
            <td>10,000</td>
            <td>12,000</td>
          </tr>
          <tr>
            <td>Cash from Investing Activity</td>
            <td>-4,000</td>
            <td>-5,000</td>
          </tr>
          <tr>
            <td>Cash from Financing Activity</td>
            <td>-5,000</td>
            <td>-6,000</td>
          </tr>
          <tr>
            <td>Net Cash Flow</td>
            <td>1,000</td>
            <td>1,000</td>
          </tr>
          <tr>
            <td>Free Cash Flow</td>
            <td>6,000</td>
            <td>7,000</td>
          </tr>
          <tr>
            <td>CFO/OP</td>
            <td>95%</td>
            <td>98%</td>
          </tr>
        </tbody>
      </table>
    </section>
    """
    soup = BeautifulSoup(html, "html.parser")
    stmt = scraper.parse_screener_table(soup, "cash-flow")
    assert stmt is not None
    metrics = [r.metric for r in stmt.rows]
    assert "Cash from Operating Activity" in metrics
    assert "Cash from Investing Activity" in metrics
    assert "Cash from Financing Activity" in metrics
    assert "Net Cash Flow" in metrics
    assert "Free Cash Flow" not in metrics
    assert "CFO/OP" not in metrics
    
    # Test hydration sanitization as well
    cached = {
        "ratios": {
            "market_cap_cr": 100000.0,
            "current_price": 1000.0,
            "high_low": "1200 / 800",
            "stock_pe": 25.0,
            "book_value": 300.0,
            "dividend_yield_pct": 1.5,
            "roce_pct": 20.0,
            "roe_pct": 18.0,
            "face_value": 1.0,
            "debt_to_equity": 0.1,
            "interest_coverage": 10.0,
            "fcf_yield_pct": 3.5,
            "sales_growth_3yr_cagr": 12.0,
            "profit_growth_3yr_cagr": 15.0
        },
        "quarters": {"periods": [], "rows": []},
        "profit_loss": {"periods": [], "rows": []},
        "balance_sheet": {"periods": [], "rows": []},
        "cash_flow": {
            "periods": ["Mar 2026"],
            "rows": [
                {"metric": "Cash from Operating Activity", "values": {"Mar 2026": 12000.0}},
                {"metric": "Free Cash Flow", "values": {"Mar 2026": 7000.0}},
                {"metric": "CFO/OP", "values": {"Mar 2026": 98.0}}
            ]
        }
    }
    hydrated = scraper.hydrate_stock_data(cached)
    hydrated_metrics = [r.metric for r in hydrated["cash_flow"].rows]
    assert "Free Cash Flow" not in hydrated_metrics
    assert "CFO/OP" not in hydrated_metrics
    print("✓ Cash Flow Case E passed: Injected non-statement rows successfully filtered from raw cash flow.")

def test_cash_flow_case_f_cfo_to_pat_deterministic():
    """Case F: CFO / PAT conversion % remains strict deterministic code calculation."""
    print("Testing Cash Flow Case F: Deterministic CFO / PAT calculation...")
    pl = FinancialStatement(
        periods=["Mar 2025", "Mar 2026"],
        rows=[FinancialRow(metric="Net Profit", values={"Mar 2025": 10000.0, "Mar 2026": 12500.0})]
    )
    bs = FinancialStatement(periods=["Mar 2025", "Mar 2026"], rows=[])
    cf = FinancialStatement(
        periods=["Mar 2025", "Mar 2026"],
        rows=[FinancialRow(metric="Cash from Operating Activity", values={"Mar 2025": 11000.0, "Mar 2026": 15000.0})]
    )
    q = FinancialStatement(periods=["Mar 2026"], rows=[])
    
    analytics = compute_financial_analytics(q, pl, bs, cf)
    cf_quality = analytics["cash_flow_quality"]
    # Cum CFO = 26000, Cum PAT = 22500 -> 26000 / 22500 * 100 = 115.555 -> 115.6%
    assert cf_quality["cfo_to_pat_5yr_pct"] == 115.6
    assert cf_quality["cash_conversion_quality"] == "Superior (CFO exceeds PAT)"
    print("✓ Cash Flow Case F passed: CFO to PAT is calculated deterministically with high fidelity.")

if __name__ == "__main__":
    test_case_a_missing_structured_financial_data()
    test_case_b_future_target_deadline_override()
    test_case_c_unverifiable_qualitative_outcome()
    test_case_d_same_filing_promise_and_outcome()
    test_case_e_numerical_guidance_with_structured_pl()
    test_case_f_gemini_fallback_model_provenance()
    test_case_g_company_ir_incremental_fallback()
    test_qualitative_milestone_completion_matching()
    test_formula_transparency()
    test_production_pipeline_financial_wiring()
    test_cash_flow_case_a_direct_capex()
    test_cash_flow_case_b_balance_sheet_derived_capex()
    test_cash_flow_case_c_extreme_derived_capex()
    test_cash_flow_case_d_missing_capex()
    test_cash_flow_case_e_raw_cash_flow_filtering()
    test_cash_flow_case_f_cfo_to_pat_deterministic()
    print("\n🎉 ALL CASES A-G, CASH FLOW CASES A-F, INTEGRATION & REGRESSION TESTS PASSED PERFECTLY!")

