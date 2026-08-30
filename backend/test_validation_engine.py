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
            assert any("FY27" in d.title for d in docs)
            assert all(d.discovery_source == "Company IR" for d in docs)
            assert all(d.actual_source_host == "testir.com" for d in docs)
            print("✓ Case G passed: Company IR incremental scan safely filtered older historical filings.")

def test_screener_document_url_parsing():
    """Screener document discovery must parse relative filing URLs without a runtime NameError."""
    print("Testing Screener document URL parsing...")
    soup = BeautifulSoup(
        '<section id="documents"><a href="/company/reports/demo.pdf">Annual Report FY26</a></section>',
        "html.parser"
    )
    docs = document_sourcing.discover_documents_screener(soup, "TEST", "Test Ltd")
    assert len(docs) == 1
    assert docs[0].url == "https://www.screener.in/company/reports/demo.pdf"
    assert docs[0].actual_source_host == "www.screener.in"
    assert docs[0].discovery_source == "Screener.in"
    print("✓ Screener document URL parsing passed without NameError.")

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
    assert ft["free_cash_flow"]["formula"] == "FCF = CFO - Capex"
    assert ft["free_cash_flow"]["source"]
    print("✓ Formula transparency verified successfully.")

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
            ai_provider_used="GEMINI (gemini-3.1-flash-lite)",
            source_documents=kwargs.get("candidate_documents_meta", [])
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
        expected_source_documents = captured_llm_kwargs["candidate_documents_meta"]
        assert expected_source_documents
        assert output["source_documents"] == expected_source_documents
        assert {doc["url"] for doc in output["source_documents"]}.issubset({
            "https://example.com/ar26.pdf",
            "https://example.com/ar25.pdf",
            "https://example.com/cc26.pdf"
        })
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

def test_knowledge_fact_persistence():
    """Validates saving and querying extracted facts in SQLite company_knowledge_facts table."""
    print("Testing persistent company knowledge fact store...")
    sym = "TESTSYM"
    database.clear_company_knowledge_facts(sym)
    
    sample_facts = [
        {
            "metric_name": "EBITDA Margin",
            "stated_value_raw": "52%",
            "numeric_value": 52.0,
            "unit": "%",
            "period_or_date": "FY26",
            "category": "financial_metric",
            "scope": "Consolidated",
            "claim_type": "reported_fact",
            "doc_url": "https://example.com/ar26.pdf",
            "doc_title": "FY26 Annual Report",
            "source_quote": "Operating leverage expanded EBITDA margin to 52%."
        },
        {
            "metric_name": "ARPU",
            "stated_value_raw": "₹245",
            "numeric_value": 245.0,
            "unit": "₹",
            "period_or_date": "FY26",
            "category": "operational_kpi",
            "scope": "Consolidated",
            "claim_type": "reported_fact",
            "doc_url": "https://example.com/ar26.pdf",
            "doc_title": "FY26 Annual Report",
            "source_quote": "Subscriber ARPU increased to ₹245."
        }
    ]
    
    saved_count = database.save_company_knowledge_facts(sym, sample_facts)
    assert saved_count == 2
    
    retrieved = database.get_company_knowledge_facts(sym)
    assert len(retrieved) == 2
    metrics = {r["metric_name"] for r in retrieved}
    assert "EBITDA Margin" in metrics
    assert "ARPU" in metrics
    assert retrieved[0]["numeric_value"] == 52.0
    print("✓ Knowledge fact persistence and retrieval verified.")

def test_statement_claim_verification():
    """Validates deterministic verification of document claims against audited P&L/BS/CF."""
    print("Testing document claim verification against audited financial statements...")
    from financial_engine import verify_document_claim_against_financials
    
    dummy_stock_data = {
        "profit_loss": {
            "periods": ["Mar 2024", "Mar 2025", "Mar 2026"],
            "rows": [
                {"metric": "Sales", "values": {"Mar 2024": 100000.0, "Mar 2025": 114000.0, "Mar 2026": 130000.0}}, # Mar 2026 growth = 14.0%
                {"metric": "OPM %", "values": {"Mar 2024": 18.0, "Mar 2025": 49.0, "Mar 2026": 52.0}},              # OPM delta = +300 bps
                {"metric": "Net Profit", "values": {"Mar 2024": 15000.0, "Mar 2025": 18000.0, "Mar 2026": 21240.0}} # PAT growth = 18.0%
            ]
        },
        "balance_sheet": {
            "periods": ["Mar 2025", "Mar 2026"],
            "rows": [
                {"metric": "Borrowings", "values": {"Mar 2025": 25000.0, "Mar 2026": 20000.0}} # Debt reduction = -5000 Cr
            ]
        }
    }
    
    # 1. Revenue claim: "Revenue grew 14%"
    rev_fact = {
        "metric_name": "Revenue Growth",
        "stated_value_raw": "14%",
        "numeric_value": 14.0,
        "unit": "%",
        "period_or_date": "FY26",
        "doc_title": "FY26 Annual Report",
        "doc_url": "https://example.com/ar26.pdf"
    }
    rev_res = verify_document_claim_against_financials(rev_fact, dummy_stock_data)
    assert rev_res["statement_verification_status"] == "Verified against Reported Financials"
    assert rev_res["prior_period"] == "Mar 2025"
    assert rev_res["pct_change"] == 14.0
    assert "₹130,000 Cr" in rev_res["statement_reported_value"]
    
    # 2. EBITDA Margin claim: "EBITDA margin reached 52%"
    margin_fact = {
        "metric_name": "EBITDA Margin",
        "stated_value_raw": "52%",
        "numeric_value": 52.0,
        "unit": "%",
        "period_or_date": "FY26",
        "doc_title": "FY26 Annual Report",
        "doc_url": "https://example.com/ar26.pdf",
        "source_quote": "Operating leverage drove expansion."
    }
    margin_res = verify_document_claim_against_financials(margin_fact, dummy_stock_data)
    assert margin_res["statement_verification_status"] == "Verified against Reported Financials"
    assert margin_res["prior_value_raw"] == "49.0%"
    assert margin_res["delta_numeric"] == 3.0
    assert "+300 bps" in margin_res["statement_reported_value"]
    
    # 3. Debt claim: "Debt reduced significantly"
    debt_fact = {
        "metric_name": "Total Borrowings",
        "stated_value_raw": "₹20,000 Cr",
        "numeric_value": 20000.0,
        "unit": "₹ Cr",
        "period_or_date": "FY26",
        "doc_title": "FY26 Annual Report"
    }
    debt_res = verify_document_claim_against_financials(debt_fact, dummy_stock_data)
    assert debt_res["statement_verification_status"] == "Verified against Reported Financials"
    assert debt_res["delta_numeric"] == -5000.0
    print("✓ Document claims successfully verified against audited statements.")

def test_inter_document_kpi_evolution():
    """Validates multi-year operational KPI evolution tracking across disparate filings."""
    print("Testing multi-document operational KPI evolution tracking...")
    from financial_engine import build_inter_document_kpi_trends
    
    multi_doc_facts = [
        # ARPU evolution
        {"metric_name": "ARPU", "stated_value_raw": "₹210", "numeric_value": 210.0, "unit": "₹", "period_or_date": "FY25", "doc_title": "FY25 Annual Report", "doc_type": "annual_report"},
        {"metric_name": "ARPU", "stated_value_raw": "₹225", "numeric_value": 225.0, "unit": "₹", "period_or_date": "Q2 FY26", "doc_title": "Q2 Presentation", "doc_type": "presentation"},
        {"metric_name": "ARPU", "stated_value_raw": "₹245", "numeric_value": 245.0, "unit": "₹", "period_or_date": "FY26", "doc_title": "FY26 Annual Report", "doc_type": "annual_report"},
        # Solar Capacity evolution
        {"metric_name": "Solar Capacity", "stated_value_raw": "300 MW", "numeric_value": 300.0, "unit": "MW", "period_or_date": "FY25", "doc_title": "FY25 Annual Report", "doc_type": "annual_report"},
        {"metric_name": "Solar Capacity", "stated_value_raw": "420 MW", "numeric_value": 420.0, "unit": "MW", "period_or_date": "Q2 FY26", "doc_title": "Q2 Presentation", "doc_type": "presentation"},
        {"metric_name": "Solar Capacity", "stated_value_raw": "600 MW", "numeric_value": 600.0, "unit": "MW", "period_or_date": "FY26", "doc_title": "FY26 Annual Report", "doc_type": "annual_report"}
    ]
    
    trends = build_inter_document_kpi_trends(multi_doc_facts)
    assert len(trends) == 2
    
    arpu_trend = next(t for t in trends if "ARPU" in t["metric_name"].upper())
    assert len(arpu_trend["data_points"]) == 3
    assert arpu_trend["trajectory"] == "Expanding / Accelerating"
    assert "+20.0" in arpu_trend["latest_vs_prior_change"] or "+8.9%" in arpu_trend["latest_vs_prior_change"]
    assert arpu_trend["data_points"][0]["stated_value"] == "₹210"
    assert arpu_trend["data_points"][-1]["stated_value"] == "₹245"
    
    solar_trend = next(t for t in trends if "SOLAR" in t["metric_name"].upper() or "CAPACITY" in t["metric_name"].upper())
    assert len(solar_trend["data_points"]) == 3
    assert solar_trend["trajectory"] == "Expanding / Accelerating"
    assert solar_trend["data_points"][-1]["numeric_value"] == 600.0
    print("✓ Inter-document operational KPI evolution verified.")

def test_guidance_vs_projections_triangulation():
    """Validates triangulation between Management Guidance and Stocker DCF Projections."""
    print("Testing Management Guidance vs Stocker Projections triangulation...")
    from financial_engine import triangulate_guidance_vs_projections
    
    facts = [
        {
            "metric_name": "Management Revenue Guidance",
            "stated_value_raw": "15.0%",
            "numeric_value": 15.0,
            "unit": "%",
            "target_period": "FY27",
            "category": "management_guidance",
            "claim_type": "management_guidance",
            "doc_title": "Q4 Concall Transcript",
            "doc_url": "https://example.com/cc26.pdf"
        }
    ]
    
    dummy_stock_data = {
        "quarters": {
            "periods": ["Jun 2024", "Sep 2024", "Dec 2024", "Mar 2025", "Jun 2025"],
            "rows": [
                {"metric": "Sales", "values": {"Jun 2024": 40000.0, "Sep 2024": 41000.0, "Dec 2024": 42000.0, "Mar 2025": 43000.0, "Jun 2025": 45000.0}} # Jun 25 YoY = 12.5%
            ]
        }
    }
    
    assumptions = {"revenue_growth_rate_pct": 10.0}
    triangulation = triangulate_guidance_vs_projections(facts, dummy_stock_data, assumptions)
    assert len(triangulation) == 1
    t_item = triangulation[0]
    assert t_item["stocker_projected_base"] == 10.0
    assert t_item["management_guidance_numeric"] == 15.0
    assert t_item["variance_guidance_vs_base_bps"] == 500.0
    assert t_item["current_run_rate_value"] == 12.5
    assert "+500 bps above" in t_item["stocker_assessment"]
    print("✓ Guidance vs Stocker Projections triangulation verified.")

def test_review_cases_a_b_c_statement_verification_discrepancies():
    """Validates Cases A, B, C: Strict verification vs discrepancy handling on financial statements."""
    print("Testing Review Cases A, B, C: Financial claim verification and discrepancy detection...")
    from financial_engine import verify_document_claim_against_financials

    dummy_stock_data = {
        "profit_loss": {
            "periods": ["Mar 2024", "Mar 2025", "Mar 2026"],
            "rows": [
                {"metric": "Sales", "values": {"Mar 2024": 100000.0, "Mar 2025": 114000.0, "Mar 2026": 130000.0}}, # Mar 2026 growth = 14.0%
                {"metric": "OPM %", "values": {"Mar 2024": 18.0, "Mar 2025": 49.0, "Mar 2026": 52.0}},              # OPM = 52.0% (+300 bps)
                {"metric": "Net Profit", "values": {"Mar 2024": 15000.0, "Mar 2025": 18000.0, "Mar 2026": 21240.0}} # PAT growth = 18.0%
            ]
        }
    }

    # Case A: Revenue claim matches audited statement (14% growth) -> Verified
    fact_a = {
        "metric_name": "Revenue Growth",
        "stated_value_raw": "14%",
        "numeric_value": 14.0,
        "unit": "%",
        "period_or_date": "FY26",
        "scope": "Consolidated"
    }
    res_a = verify_document_claim_against_financials(fact_a, dummy_stock_data)
    assert res_a["statement_verification_status"] == "Verified against Reported Financials"
    assert "Matches stated claim" in res_a["stocker_assessment"]
    print("  ✓ Case A passed: Matching revenue claim verified.")

    # Case B: Revenue claim materially differs (claims 20% growth when actual is 14%) -> Discrepancy
    fact_b = {
        "metric_name": "Revenue Growth",
        "stated_value_raw": "20%",
        "numeric_value": 20.0,
        "unit": "%",
        "period_or_date": "FY26",
        "scope": "Consolidated"
    }
    res_b = verify_document_claim_against_financials(fact_b, dummy_stock_data)
    assert res_b["statement_verification_status"] == "Discrepancy vs Reported Financials"
    assert "Discrepancy" in res_b["stocker_assessment"]
    assert "show revenue grew 14.0% YoY" in res_b["stocker_assessment"]
    print("  ✓ Case B passed: Material revenue discrepancy flagged accurately.")

    # Case C: EBITDA margin claim differs (claims 56% when actual is 52%) -> Discrepancy
    fact_c = {
        "metric_name": "EBITDA Margin",
        "stated_value_raw": "56%",
        "numeric_value": 56.0,
        "unit": "%",
        "period_or_date": "FY26",
        "scope": "Consolidated"
    }
    res_c = verify_document_claim_against_financials(fact_c, dummy_stock_data)
    assert res_c["statement_verification_status"] == "Discrepancy vs Reported Financials"
    assert "Discrepancy" in res_c["stocker_assessment"]
    assert "reported audited OPM was 52.0%" in res_c["stocker_assessment"]
    print("  ✓ Case C passed: EBITDA margin discrepancy flagged accurately.")

def test_review_cases_d_e_f_kpi_identity_matching():
    """Validates Cases D, E, F: Conservative KPI identity matching and same-period scope preservation."""
    print("Testing Review Cases D, E, F: KPI Identity isolation & safe same-period deduplication...")
    from financial_engine import build_inter_document_kpi_trends, extract_kpi_identity

    # Case D: India Mobile ARPU vs Africa ARPU must be separate series
    facts_d = [
        {"metric_name": "India Mobile ARPU", "stated_value_raw": "₹210", "numeric_value": 210.0, "unit": "₹", "period_or_date": "FY25", "scope": "India"},
        {"metric_name": "India Mobile ARPU", "stated_value_raw": "₹245", "numeric_value": 245.0, "unit": "₹", "period_or_date": "FY26", "scope": "India"},
        {"metric_name": "Africa ARPU", "stated_value_raw": "$2.8", "numeric_value": 2.8, "unit": "$", "period_or_date": "FY25", "scope": "Africa"},
        {"metric_name": "Africa ARPU", "stated_value_raw": "$3.1", "numeric_value": 3.1, "unit": "$", "period_or_date": "FY26", "scope": "Africa"},
    ]
    trends_d = build_inter_document_kpi_trends(facts_d)
    assert len(trends_d) == 2, f"Expected 2 separate trends for India and Africa ARPU, got {len(trends_d)}"
    series_names = [t["metric_name"] for t in trends_d]
    assert any("India" in n for n in series_names)
    assert any("Africa" in n for n in series_names)
    print("  ✓ Case D passed: India ARPU and Africa ARPU kept strictly in separate series.")

    # Case E: Installed Capacity vs Target Capacity must NOT merge as same actual series
    facts_e = [
        {"metric_name": "Installed Solar Capacity", "stated_value_raw": "300 MW", "numeric_value": 300.0, "unit": "MW", "period_or_date": "FY25", "claim_type": "reported_fact"},
        {"metric_name": "Installed Solar Capacity", "stated_value_raw": "600 MW", "numeric_value": 600.0, "unit": "MW", "period_or_date": "FY26", "claim_type": "reported_fact"},
        {"metric_name": "Target Solar Capacity", "stated_value_raw": "1000 MW", "numeric_value": 1000.0, "unit": "MW", "period_or_date": "FY27", "claim_type": "management_target"},
    ]
    trends_e = build_inter_document_kpi_trends(facts_e)
    assert len(trends_e) == 2, f"Expected Installed Capacity and Target Capacity to be separate, got {len(trends_e)}"
    print("  ✓ Case E passed: Installed Capacity and Target Capacity not blindly merged.")

    # Case F: Same period, different scope (e.g. FY26 Consolidated vs FY26 India Segment) -> Both preserved
    facts_f = [
        {"metric_name": "Revenue", "stated_value_raw": "₹130,000 Cr", "numeric_value": 130000.0, "unit": "₹ Cr", "period_or_date": "FY26", "scope": "Consolidated"},
        {"metric_name": "India Revenue", "stated_value_raw": "₹90,000 Cr", "numeric_value": 90000.0, "unit": "₹ Cr", "period_or_date": "FY26", "scope": "India"}
    ]
    trends_f = build_inter_document_kpi_trends(facts_f)
    assert len(trends_f) == 2, f"Expected 2 trends for different scopes in same period, got {len(trends_f)}"
    print("  ✓ Case F passed: Same period, different scope facts safely preserved.")

def test_review_cases_g_h_i_j_k_guidance_triangulation_correctness():
    """Validates Cases G, H, I, J, K: Metric-aware guidance triangulation without fake defaults."""
    print("Testing Review Cases G, H, I, J, K: Guidance vs Projections metric awareness...")
    from financial_engine import triangulate_guidance_vs_projections

    dummy_stock_data = {
        "quarters": {
            "periods": ["Jun 2024", "Sep 2024", "Dec 2024", "Mar 2025", "Jun 2025"],
            "rows": [
                {"metric": "Sales", "values": {"Jun 2024": 40000.0, "Sep 2024": 41000.0, "Dec 2024": 42000.0, "Mar 2025": 43000.0, "Jun 2025": 45000.0}}, # Jun 25 YoY = 12.5%
                {"metric": "OPM %", "values": {"Jun 2024": 20.0, "Sep 2024": 21.0, "Dec 2024": 21.5, "Mar 2025": 22.0, "Jun 2025": 23.5}}             # Jun 25 OPM = 23.5%
            ]
        }
    }

    # Case G: Revenue guidance compares to real Stocker revenue projection
    guidance_g = [{
        "metric_name": "Revenue Growth Guidance",
        "stated_value_raw": "16.0%",
        "numeric_value": 16.0,
        "target_period": "FY27",
        "claim_type": "management_guidance"
    }]
    res_g = triangulate_guidance_vs_projections(guidance_g, dummy_stock_data, {"revenue_growth_rate_pct": 12.0})
    assert res_g[0]["stocker_projected_base"] == 12.0
    assert res_g[0]["variance_guidance_vs_base_bps"] == 400.0
    assert res_g[0]["current_run_rate_value"] == 12.5 # Quarterly sales run-rate
    print("  ✓ Case G passed: Revenue guidance compares to real revenue projection and sales run-rate.")

    # Case H: EBITDA margin guidance does NOT compare to revenue projection
    guidance_h = [{
        "metric_name": "EBITDA Margin Guidance",
        "stated_value_raw": "25.0%",
        "numeric_value": 25.0,
        "target_period": "FY27",
        "claim_type": "management_guidance"
    }]
    # Assumptions only contain revenue growth, no margin assumption
    res_h = triangulate_guidance_vs_projections(guidance_h, dummy_stock_data, {"revenue_growth_rate_pct": 12.0})
    assert res_h[0]["stocker_projected_base"] is None, "EBITDA margin must NOT receive revenue growth assumption!"
    assert res_h[0]["current_run_rate_value"] == 23.5 # Quarterly OPM run-rate, NOT sales growth!
    assert "No directly comparable Stocker margin projection available" in res_h[0]["stocker_assessment"]
    print("  ✓ Case H passed: EBITDA margin guidance does NOT receive revenue growth assumption; uses OPM run-rate.")

    # Case I: Capacity guidance (e.g. 1 GW Solar) does NOT receive DCF revenue growth projection
    guidance_i = [{
        "metric_name": "Target Solar Capacity",
        "stated_value_raw": "1 GW",
        "numeric_value": 1000.0,
        "unit": "MW",
        "target_period": "FY28",
        "claim_type": "management_target"
    }]
    res_i = triangulate_guidance_vs_projections(guidance_i, dummy_stock_data, {"revenue_growth_rate_pct": 12.0})
    assert res_i[0]["stocker_projected_base"] is None
    assert "No directly comparable Stocker projection available" in res_i[0]["stocker_assessment"]
    print("  ✓ Case I passed: Capacity target guidance does not invent fake DCF projection.")

    # Case J: Missing projection assumptions -> No generic 10/15/5% fallback
    res_j = triangulate_guidance_vs_projections(guidance_g, dummy_stock_data, None)
    assert res_j[0]["stocker_projected_base"] is None
    assert "No directly comparable Stocker projection available" in res_j[0]["stocker_assessment"]
    print("  ✓ Case J passed: Missing assumptions cleanly yields None without fake 10% defaults.")

    # Case K: Current run-rate uses correct metric for each type
    assert res_g[0]["current_run_rate_value"] == 12.5 # Revenue YoY
    assert res_h[0]["current_run_rate_value"] == 23.5 # OPM %
    print("  ✓ Case K passed: Current run-rate matches metric identity correctly.")

def test_ebitda_margin_vs_ebitda_amount_separation():
    """Validates full separation of EBITDA Margin, OPM bps, EBITDA absolute amount, and Operating Profit Growth."""
    print("Testing EBITDA amount vs EBITDA Margin vs Growth separation...")
    from financial_engine import verify_document_claim_against_financials

    dummy_stock_data = {
        "profit_loss": {
            "periods": ["Mar 2024", "Mar 2025", "Mar 2026"],
            "rows": [
                {"metric": "Sales", "values": {"Mar 2024": 100000.0, "Mar 2025": 114000.0, "Mar 2026": 130000.0}},
                {"metric": "Operating Profit", "values": {"Mar 2024": 18000.0, "Mar 2025": 69565.0, "Mar 2026": 80000.0}}, # FY26 OP = 80,000 Cr (+15.0% YoY vs 69,565 Cr)
                {"metric": "OPM %", "values": {"Mar 2024": 18.0, "Mar 2025": 49.0, "Mar 2026": 52.0}},                      # FY26 OPM = 52.0% (+300 bps)
                {"metric": "Net Profit", "values": {"Mar 2024": 15000.0, "Mar 2025": 18000.0, "Mar 2026": 21240.0}}
            ]
        }
    }

    # 1. EBITDA Margin 52% -> compared against OPM %, not EBITDA amount
    fact_margin = {
        "metric_name": "EBITDA Margin",
        "stated_value_raw": "52%",
        "numeric_value": 52.0,
        "unit": "%",
        "period_or_date": "FY26"
    }
    res_margin = verify_document_claim_against_financials(fact_margin, dummy_stock_data)
    assert res_margin["statement_verification_status"] == "Verified against Reported Financials"
    assert "52.0%" in res_margin["statement_reported_value"]
    assert "Reported OPM was 52.0%" in res_margin["stocker_assessment"]
    print("  ✓ Test 1 passed: EBITDA Margin 52% compared against OPM %.")

    # 2. EBITDA = ₹80,000 Cr -> compared against Operating Profit / EBITDA amount
    fact_ebitda_amt = {
        "metric_name": "EBITDA",
        "stated_value_raw": "₹80,000 Cr",
        "numeric_value": 80000.0,
        "unit": "₹ Cr",
        "period_or_date": "FY26"
    }
    res_ebitda_amt = verify_document_claim_against_financials(fact_ebitda_amt, dummy_stock_data)
    assert res_ebitda_amt["statement_verification_status"] == "Verified against Reported Financials"
    assert "₹80,000 Cr" in res_ebitda_amt["statement_reported_value"]
    assert "Operating Profit (EBITDA) in Mar 2026 was ₹80,000 Cr" in res_ebitda_amt["stocker_assessment"]
    print("  ✓ Test 2 passed: EBITDA ₹80,000 Cr compared against Operating Profit amount.")

    # 3. EBITDA Growth 15% -> compares against deterministic operating-profit growth
    fact_ebitda_growth = {
        "metric_name": "Operating Profit Growth",
        "stated_value_raw": "15%",
        "numeric_value": 15.0,
        "unit": "%",
        "period_or_date": "FY26"
    }
    res_ebitda_growth = verify_document_claim_against_financials(fact_ebitda_growth, dummy_stock_data)
    assert res_ebitda_growth["statement_verification_status"] == "Verified against Reported Financials"
    assert "grew 15.0% YoY" in res_ebitda_growth["stocker_assessment"]
    print("  ✓ Test 3 passed: Operating Profit Growth 15% verified against deterministic OP YoY growth.")

    # 4. OPM +300 bps -> compares against margin movement in bps
    fact_bps = {
        "metric_name": "OPM Expansion",
        "stated_value_raw": "+300 bps",
        "numeric_value": 300.0,
        "unit": "bps",
        "period_or_date": "FY26"
    }
    res_bps = verify_document_claim_against_financials(fact_bps, dummy_stock_data)
    assert res_bps["statement_verification_status"] == "Verified against Reported Financials"
    assert "+300 bps" in res_bps["statement_reported_value"]
    assert "Audited OPM moved +300 bps" in res_bps["stocker_assessment"]
    print("  ✓ Test 4 passed: OPM +300 bps verified against margin movement.")

    # 5. Absolute EBITDA must NEVER be compared against OPM %
    # If document claims EBITDA = ₹80,000 Cr, but statements show Operating Profit = ₹60,000 Cr, it must be Discrepancy vs OP, NOT 52%
    fact_ebitda_wrong = {
        "metric_name": "Operating Profit",
        "stated_value_raw": "₹95,000 Cr",
        "numeric_value": 95000.0,
        "unit": "₹ Cr",
        "period_or_date": "FY26"
    }
    res_ebitda_wrong = verify_document_claim_against_financials(fact_ebitda_wrong, dummy_stock_data)
    assert res_ebitda_wrong["statement_verification_status"] == "Discrepancy vs Reported Financials"
    assert "reported audited Operating Profit for Mar 2026 was ₹80,000 Cr" in res_ebitda_wrong["stocker_assessment"]
    assert "52" not in res_ebitda_wrong["stocker_assessment"], "Must not leak OPM % into absolute EBITDA comparison!"
    print("  ✓ Test 5 passed: Absolute EBITDA is never compared against OPM %.")

    # 5b. Missing Operating Profit row -> Context Only, does NOT fall into OPM %
    data_no_op = {
        "profit_loss": {
            "periods": ["Mar 2025", "Mar 2026"],
            "rows": [
                {"metric": "Sales", "values": {"Mar 2025": 114000.0, "Mar 2026": 130000.0}},
                {"metric": "OPM %", "values": {"Mar 2025": 49.0, "Mar 2026": 52.0}}
            ]
        }
    }
    res_no_op = verify_document_claim_against_financials(fact_ebitda_amt, data_no_op)
    assert res_no_op["statement_verification_status"] == "Statement Context Only / Not Directly Comparable"
    assert "Operating Profit / EBITDA absolute line is not broken out" in res_no_op["stocker_assessment"]
    print("  ✓ Test 5b passed: Missing OP row returns Context Only without falling into OPM %.")

def test_real_stocker_projections_wiring():
    """Validates metric-aware wiring of real Stocker projections into document triangulation."""
    print("Testing Real Stocker Projections wiring into Document Triangulation...")
    from financial_engine import triangulate_guidance_vs_projections

    dummy_stock_data = {
        "quarters": {
            "periods": ["Jun 2024", "Sep 2024", "Dec 2024", "Mar 2025", "Jun 2025"],
            "rows": [
                {"metric": "Sales", "values": {"Jun 2024": 40000.0, "Sep 2024": 41000.0, "Dec 2024": 42000.0, "Mar 2025": 43000.0, "Jun 2025": 45000.0}}, # 12.5% YoY
                {"metric": "OPM %", "values": {"Jun 2024": 20.0, "Sep 2024": 21.0, "Dec 2024": 21.5, "Mar 2025": 22.0, "Jun 2025": 23.5}},
                {"metric": "Net Profit", "values": {"Jun 2024": 5000.0, "Sep 2024": 5200.0, "Dec 2024": 5500.0, "Mar 2025": 5800.0, "Jun 2025": 6000.0}}  # 20.0% YoY
            ]
        }
    }

    # 6. Real revenue projection supplied by Stocker -> used for revenue guidance
    rev_guidance = [{"metric_name": "Revenue Guidance", "stated_value_raw": "15.0%", "numeric_value": 15.0, "target_period": "FY27", "claim_type": "management_guidance"}]
    stocker_pkg = {
        "revenue_growth_rate_pct": 11.5,
        "base_sales_cagr": 11.5,
        "bull_sales_cagr": 15.5,
        "bear_sales_cagr": 7.5,
        "target_opm_pct": 24.0,
        "base_pat_cagr": 14.0,
        "bull_pat_cagr": 18.0,
        "bear_pat_cagr": 9.0,
        "capex_pct_of_sales": 6.5
    }
    res_6 = triangulate_guidance_vs_projections(rev_guidance, dummy_stock_data, stocker_pkg)
    assert res_6[0]["stocker_projected_base"] == 11.5
    assert res_6[0]["stocker_projected_bull"] == 15.5
    assert res_6[0]["stocker_projected_bear"] == 7.5
    assert res_6[0]["variance_guidance_vs_base_bps"] == 350.0 # 15.0 - 11.5 = +350 bps
    print("  ✓ Test 6 passed: Real revenue projection supplied by Stocker used for revenue guidance.")

    # 7. No real Stocker projection supplied -> no fake projection appears
    res_7 = triangulate_guidance_vs_projections(rev_guidance, dummy_stock_data, None)
    assert res_7[0]["stocker_projected_base"] is None
    assert res_7[0]["stocker_projected_bull"] is None
    assert res_7[0]["stocker_projected_bear"] is None
    assert "No directly comparable Stocker projection available" in res_7[0]["stocker_assessment"]
    print("  ✓ Test 7 passed: No fake projection appears when projection data is absent.")

    # 8. Margin guidance when Stocker has a real margin projection -> correctly compared
    margin_guidance = [{"metric_name": "EBITDA Margin Guidance", "stated_value_raw": "25.0%", "numeric_value": 25.0, "target_period": "FY27", "claim_type": "management_guidance"}]
    res_8 = triangulate_guidance_vs_projections(margin_guidance, dummy_stock_data, stocker_pkg)
    assert res_8[0]["stocker_projected_base"] == 24.0
    assert res_8[0]["variance_guidance_vs_base_bps"] == 100.0 # 25.0 - 24.0 = +100 bps
    assert res_8[0]["current_run_rate_value"] == 23.5 # Quarterly OPM run-rate
    print("  ✓ Test 8 passed: Margin guidance compared with Stocker margin projection & quarterly OPM.")

    # 9. Margin guidance when Stocker has NO margin projection (only revenue) -> unavailable, not revenue projection
    pkg_revenue_only = {"revenue_growth_rate_pct": 11.5, "base_sales_cagr": 11.5}
    res_9 = triangulate_guidance_vs_projections(margin_guidance, dummy_stock_data, pkg_revenue_only)
    assert res_9[0]["stocker_projected_base"] is None
    assert "No directly comparable Stocker margin projection available" in res_9[0]["stocker_assessment"]
    print("  ✓ Test 9 passed: Margin guidance does NOT receive revenue growth projection.")

    # 10. Operational target such as 1 GW capacity -> never mapped to DCF financial projection
    cap_target = [
        {"metric_name": "Target Solar Capacity", "stated_value_raw": "1 GW", "numeric_value": 1000.0, "unit": "MW", "target_period": "FY28", "claim_type": "management_target"},
        {"metric_name": "Installed Solar Capacity", "stated_value_raw": "600 MW", "numeric_value": 600.0, "unit": "MW", "period_or_date": "FY26", "claim_type": "reported_fact"}
    ]
    res_10 = triangulate_guidance_vs_projections(cap_target, dummy_stock_data, stocker_pkg)
    assert len(res_10) == 1
    assert res_10[0]["stocker_projected_base"] is None
    assert res_10[0]["current_run_rate_value"] == 600.0
    assert "Current reported baseline is 600 MW (FY26)" in res_10[0]["stocker_assessment"]
    assert "No directly comparable Stocker projection available" in res_10[0]["stocker_assessment"]
    print("  ✓ Test 10 passed: Operational target (1 GW) not mapped to DCF; uses baseline fact from knowledge store.")

def test_extract_document_intelligence_production_projection_wiring():
    """
    Integration test preventing regression of commit 76f67b2:
    Verifies that extract_document_intelligence_with_llm in production:
    1. Obtains real projection assumptions and scenario CAGRs from projection_engine
    2. Passes doc_intel=None to prevent circular guidance feedback
    3. Passes projection_assumptions into process_and_verify_company_knowledge
    4. Populates guidance_vs_projections with real Stocker projections
    """
    print("Testing Production AI Pipeline Real Stocker Projection Integration...")
    from llm_service import extract_document_intelligence_with_llm
    from doc_intelligence_models import BusinessOutlookResult
    
    mock_llm_json = {
        "what_changed_recently": [],
        "growth_drivers": [],
        "promise_vs_delivery": [],
        "demand_momentum": {"summary": "Strong demand", "company_specific_metrics": []},
        "risks_and_cash": {"operational_bottlenecks": []},
        "stocker_view": {
            "execution_verdict": "Strong Execution",
            "positive_triggers": ["Expansion"],
            "main_risks": ["Competition"],
            "what_to_watch_next": ["Q1"],
            "investor_summary": "Summary"
        }
    }
    
    dummy_ratios = {
        "market_cap_cr": 250000.0,
        "current_price": 1500.0,
        "high_low": "1600 / 1200",
        "stock_pe": 25.0,
        "book_value": 300.0,
        "dividend_yield_pct": 1.5,
        "roce_pct": 28.0,
        "roe_pct": 24.0,
        "face_value": 5.0,
        "sales_growth_3yr_cagr": 14.5,
        "profit_growth_3yr_cagr": 16.0
    }
    
    dummy_pl = {
        "periods": ["Mar 2024", "Mar 2025", "Mar 2026"],
        "rows": [
            {"metric": "Sales", "values": {"Mar 2024": 80000.0, "Mar 2025": 92000.0, "Mar 2026": 105000.0}},
            {"metric": "Operating Profit", "values": {"Mar 2024": 16000.0, "Mar 2025": 19000.0, "Mar 2026": 23000.0}},
            {"metric": "OPM %", "values": {"Mar 2024": 20.0, "Mar 2025": 20.7, "Mar 2026": 21.9}},
            {"metric": "Net Profit", "values": {"Mar 2024": 12000.0, "Mar 2025": 14500.0, "Mar 2026": 17500.0}}
        ]
    }
    dummy_quarters = {
        "periods": ["Jun 2025", "Sep 2025", "Dec 2025", "Mar 2026"],
        "rows": [
            {"metric": "Sales", "values": {"Jun 2025": 25000.0, "Sep 2025": 26000.0, "Dec 2025": 26500.0, "Mar 2026": 27500.0}},
            {"metric": "OPM %", "values": {"Jun 2025": 21.0, "Sep 2025": 21.5, "Dec 2025": 21.8, "Mar 2026": 22.0}}
        ]
    }
    dummy_bs = {
        "periods": ["Mar 2025", "Mar 2026"],
        "rows": [
            {"metric": "Fixed Assets", "values": {"Mar 2025": 30000.0, "Mar 2026": 34000.0}},
            {"metric": "CWIP", "values": {"Mar 2025": 2000.0, "Mar 2026": 3000.0}}
        ]
    }
    dummy_cf = {
        "periods": ["Mar 2025", "Mar 2026"],
        "rows": [
            {"metric": "Cash from Operating Activity", "values": {"Mar 2025": 15000.0, "Mar 2026": 18000.0}}
        ]
    }
    dummy_analytics = {
        "historical_parameters": {
            "opm_median_pct": 21.0,
            "capex_to_sales_pct": 5.0,
            "effective_tax_rate_pct": 25.0
        },
        "growth_rates": {
            "sales_cagr_3yr": 14.5
        }
    }
    dummy_cache = {
        "ratios": dummy_ratios,
        "analytics": dummy_analytics,
        "profit_loss": dummy_pl,
        "quarters": dummy_quarters,
        "balance_sheet": dummy_bs,
        "cash_flow": dummy_cf
    }
    
    # Mock extracted facts containing Revenue Guidance
    precomputed_summaries = [{
        "doc_title": "Infosys Q4 Earnings Call",
        "doc_url": "https://example.com/q4.pdf",
        "doc_type": "concall_transcript",
        "extracted_facts": [
            {
                "metric_name": "Revenue Guidance",
                "stated_value_raw": "18.0%",
                "numeric_value": 18.0,
                "unit": "%",
                "period_or_date": "Q4 FY26",
                "target_period": "FY27",
                "category": "management_guidance",
                "claim_type": "management_guidance"
            },
            {
                "metric_name": "EBITDA Margin Guidance",
                "stated_value_raw": "22.5%",
                "numeric_value": 22.5,
                "unit": "%",
                "period_or_date": "Q4 FY26",
                "target_period": "FY27",
                "category": "management_guidance",
                "claim_type": "management_guidance"
            }
        ]
    }]

    with patch("llm_service.is_llm_available", return_value=True), \
         patch("llm_service.call_gemini_api", return_value=(mock_llm_json, "gemini-3.1-flash-lite")), \
         patch("database.get_stock_cache", return_value=dummy_cache), \
         patch("database.get_company_knowledge_facts", return_value=[]):
         
        success, result, msg = extract_document_intelligence_with_llm(
            symbol="INFY",
            company_name="Infosys Ltd",
            latest_doc_title="Infosys Q4 Earnings Call",
            latest_doc_url="https://example.com/q4.pdf",
            latest_pages=[],
            older_doc_title=None,
            older_doc_url=None,
            older_pages=[],
            financial_statements_summary="",
            candidate_documents_meta=[{"title": "Infosys Q4", "url": "https://example.com/q4.pdf", "type": "concall_transcript", "period": "Q4 FY26"}],
            precomputed_document_summaries=precomputed_summaries,
            tagged_all_documents_text="",
            pl_stmt=dummy_pl,
            quarters_stmt=dummy_quarters,
            bs_stmt=dummy_bs,
            cf_stmt=dummy_cf
        )
        
        assert success is True
        assert result is not None
        assert len(result.guidance_vs_projections) == 2
        
        rev_tri = next(g for g in result.guidance_vs_projections if "revenue" in g.metric_name.lower())
        assert rev_tri.stocker_projected_base is not None, "Real Stocker revenue projection must be populated!"
        assert rev_tri.stocker_projected_base == 14.5
        assert rev_tri.variance_guidance_vs_base_bps == 350.0 # 18.0 - 14.5 = +350 bps
        assert "+350 bps above Stocker's Base DCF projection of 14.5%" in rev_tri.stocker_assessment
        
        margin_tri = next(g for g in result.guidance_vs_projections if "margin" in g.metric_name.lower())
        assert margin_tri.stocker_projected_base is not None, "Real Stocker margin projection must be populated!"
        assert margin_tri.stocker_projected_base == 21.0
        assert margin_tri.variance_guidance_vs_base_bps == 150.0 # 22.5 - 21.0 = +150 bps
        assert "Latest reported quarterly OPM is 22.0%" in margin_tri.stocker_assessment
        print("  ✓ Integration Test passed: Real Stocker projection engine accurately wired into production AI pipeline.")

if __name__ == "__main__":
    test_case_a_missing_structured_financial_data()
    test_case_b_future_target_deadline_override()
    test_case_c_unverifiable_qualitative_outcome()
    test_case_d_same_filing_promise_and_outcome()
    test_case_e_numerical_guidance_with_structured_pl()
    test_case_f_gemini_fallback_model_provenance()
    test_case_g_company_ir_incremental_fallback()
    test_screener_document_url_parsing()
    test_qualitative_milestone_completion_matching()
    test_formula_transparency()
    test_production_pipeline_financial_wiring()
    test_cash_flow_case_a_direct_capex()
    test_cash_flow_case_b_balance_sheet_derived_capex()
    test_cash_flow_case_c_extreme_derived_capex()
    test_cash_flow_case_d_missing_capex()
    test_cash_flow_case_e_raw_cash_flow_filtering()
    test_cash_flow_case_f_cfo_to_pat_deterministic()
    test_knowledge_fact_persistence()
    test_statement_claim_verification()
    test_inter_document_kpi_evolution()
    test_guidance_vs_projections_triangulation()
    test_review_cases_a_b_c_statement_verification_discrepancies()
    test_review_cases_d_e_f_kpi_identity_matching()
    test_review_cases_g_h_i_j_k_guidance_triangulation_correctness()
    test_ebitda_margin_vs_ebitda_amount_separation()
    test_real_stocker_projections_wiring()
    test_extract_document_intelligence_production_projection_wiring()
    print("\n🎉 ALL TESTS 1-15, REVIEW CASES A-K, CASH FLOW CASES A-F & PRODUCTION INTEGRATION PASSED PERFECTLY!")
