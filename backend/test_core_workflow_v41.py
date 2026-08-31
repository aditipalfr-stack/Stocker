"""
=============================================================================
Stocker Phase V4.1 Step 1A Comprehensive Core Workflow & Persistence Suite
=============================================================================
Verifies:
1. Fresh/Unseeded Canonical Resolution (COLPAL, Colgate, Colgate-Palmolive (India) Ltd -> same canonical security)
2. Ambiguous query handling -> HTTP 409 AMBIGUOUS_COMPANY
3. Unresolved input safety -> HTTP 404 without universe enrollment
4. SQLite Durable Financial Cache (survives restart/request simulation without JSON cache)
5. Decoupled document discovery boundary (no external waterfall during financial ingestion)
6. /discover-filings canonical safety & trusted sync state
7. Nullable ratios safe end-to-end (StockDetail, Projections, Ranking, StockSummary)
8. Research Lifecycle state transitions (financial-only -> new AI -> stale -> recomputed -> evidence_enriched)
9. Financial data freshness states (ready vs stale >90d vs error)
10. Empty universe semantics (in-universe=0 preserved without unwanted re-seeding)
=============================================================================
"""

import os
import sys
import json
import tempfile
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock
from bs4 import BeautifulSoup
from fastapi import HTTPException

os.environ["STOCKER_TEST_MODE"] = "1"
sys.path.insert(0, str(Path(__file__).parent.parent / "libs"))
sys.path.insert(0, str(Path(__file__).parent))

import database
from main import (
    search_companies, execute_add_company_to_universe,
    add_company_to_universe_by_body, get_stock_research_status,
    discover_stock_filings, get_all_stocks, build_full_stock_detail
)
from models import (
    KeyRatios, FinancialStatement, FinancialRow, AddCompanyRequest,
    ResearchLifecycleStatus, StockDetail, DocumentLinks, DocumentItem
)
from scraper import (
    parse_screener_ratios, parse_screener_documents,
    fetch_stock_from_screener, serialize_stock_data, hydrate_stock_data
)
from research_lifecycle_service import get_research_lifecycle_status
from company_resolver import (
    resolve_and_search_companies, resolve_canonical_company,
    resolve_proven_security_for_add
)
from projection_engine import run_projections, derive_projection_assumptions
from ranking_engine import compute_stock_score
from doc_intelligence_models import BusinessOutlookResult, PromiseVsDeliveryItem, StockerView

class IsolatedTestDatabase:
    def __init__(self, seed: bool = True):
        self.seed = seed

    def __enter__(self):
        self.temp_dir = tempfile.mkdtemp(prefix="stocker_test_v41_")
        self.db_path = Path(self.temp_dir) / "test_stocker.db"
        self.orig_env_db = os.environ.get("STOCKER_DB_PATH")
        os.environ["STOCKER_DB_PATH"] = str(self.db_path)
        self.orig_db_path = database.DB_PATH
        database.DB_PATH = self.db_path
        database.init_db()
        if not self.seed:
            conn = database.get_db_connection()
            with conn:
                conn.execute("DELETE FROM company_registry")
                conn.execute("DELETE FROM stocks_cache")
                conn.execute("DELETE FROM source_documents")
            conn.close()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        database.DB_PATH = self.orig_db_path
        if self.orig_env_db is not None:
            os.environ["STOCKER_DB_PATH"] = self.orig_env_db
        else:
            os.environ.pop("STOCKER_DB_PATH", None)
        try:
            shutil.rmtree(self.temp_dir)
        except Exception:
            pass

def sample_complete_stock_data(symbol="COLPAL", name="Colgate-Palmolive (India) Limited", fetched_at=None):
    if not fetched_at:
        fetched_at = datetime.now(timezone.utc).isoformat()
    return {
        "symbol": symbol,
        "name": name,
        "sector": "FMCG",
        "industry": "Personal Care",
        "about": f"{name} is a leading oral care company in India.",
        "source_name": "Screener.in",
        "source_url": f"https://www.screener.in/company/{symbol}/",
        "statement_type": "consolidated",
        "fetched_at": fetched_at,
        "ratios": KeyRatios(
            market_cap_cr=75000.0,
            current_price=2800.0,
            stock_pe=55.0,
            book_value=65.0,
            dividend_yield_pct=1.8,
            roce_pct=72.0,
            roe_pct=58.0,
            face_value=1.0,
            debt_to_equity=0.02,
            interest_coverage=45.0,
            fcf_yield_pct=2.4,
            sales_growth_3yr_cagr=8.5,
            profit_growth_3yr_cagr=10.2
        ),
        "quarters": FinancialStatement(periods=["Jun 2025", "Sep 2025"], rows=[FinancialRow(metric="Sales", values={"Jun 2025": 1400.0, "Sep 2025": 1450.0})]),
        "profit_loss": FinancialStatement(periods=["Mar 2024", "Mar 2025"], rows=[
            FinancialRow(metric="Sales", values={"Mar 2024": 5200.0, "Mar 2025": 5600.0}),
            FinancialRow(metric="Operating Profit", values={"Mar 2024": 1500.0, "Mar 2025": 1700.0}),
            FinancialRow(metric="OPM %", values={"Mar 2024": 28.8, "Mar 2025": 30.3}),
            FinancialRow(metric="Net Profit", values={"Mar 2024": 1100.0, "Mar 2025": 1300.0})
        ]),
        "balance_sheet": FinancialStatement(periods=["Mar 2024", "Mar 2025"], rows=[
            FinancialRow(metric="Equity Capital", values={"Mar 2024": 27.0, "Mar 2025": 27.0}),
            FinancialRow(metric="Reserves", values={"Mar 2024": 1700.0, "Mar 2025": 1800.0}),
            FinancialRow(metric="Borrowings", values={"Mar 2024": 50.0, "Mar 2025": 40.0}),
            FinancialRow(metric="Investments", values={"Mar 2024": 300.0, "Mar 2025": 400.0})
        ]),
        "cash_flow": FinancialStatement(periods=["Mar 2024", "Mar 2025"], rows=[
            FinancialRow(metric="Cash from Operating Activity", values={"Mar 2024": 1200.0, "Mar 2025": 1350.0}),
            FinancialRow(metric="Fixed assets purchased", values={"Mar 2024": -120.0, "Mar 2025": -140.0})
        ]),
        "concall_insights": [],
        "annual_report_insights": [],
        "documents": DocumentLinks()
    }

def run_all_tests():
    print("==================================================================")
    print("Running Stocker Phase V4.1 Step 1A Comprehensive Test Suite")
    print("==================================================================")

    # -------------------------------------------------------------------------
    # TEST 1: Fresh / Unseeded COLPAL Resolution across Ticker, Name, Legal Name
    # -------------------------------------------------------------------------
    with IsolatedTestDatabase(seed=False):
        print("\n--- Test 1: Fresh/Unseeded Canonical Resolution for COLPAL-Class Entities ---")
        # Empty registry check
        assert database.get_company_registry_total_count() == 0, "DB must be completely empty before test"
        
        mock_nse_csv = (
            "SYMBOL,NAME OF COMPANY,SERIES,DATE OF LISTING,PAID UP VALUE,MARKET LOT,ISIN NUMBER,FACE VALUE\n"
            "COLPAL,Colgate-Palmolive (India) Limited,EQ,17-NOV-1978,1,1,INE162A01024,1\n"
            "INFY,Infosys Limited,EQ,08-FEB-1995,5,1,INE009A01021,5\n"
            "TATAMOTORS,Tata Motors Limited,EQ,22-JUL-1998,2,1,INE155A01022,2\n"
            "TATASTEEL,Tata Steel Limited,EQ,18-NOV-1998,1,1,INE081A01020,1\n"
            "TATAPOWER,Tata Power Company Limited,EQ,05-OCT-1998,1,1,INE245A01021,1\n"
        )
        
        def mock_screener_discovery(q):
            clean_q = q.lower().strip()
            if "colgate" in clean_q or "colpal" in clean_q:
                return [{
                    "symbol": "COLPAL",
                    "company_name": "Colgate-Palmolive (India) Limited",
                    "source": "screener_search",
                    "aliases": ["Colgate", "COLPAL"]
                }]
            elif "tata" in clean_q:
                return [
                    {"symbol": "TATAMOTORS", "company_name": "Tata Motors Limited", "source": "screener_search", "aliases": ["Tata Motors"]},
                    {"symbol": "TATASTEEL", "company_name": "Tata Steel Limited", "source": "screener_search", "aliases": ["Tata Steel"]},
                    {"symbol": "TATAPOWER", "company_name": "Tata Power Company Limited", "source": "screener_search", "aliases": ["Tata Power"]}
                ]
            return []

        with patch("urllib.request.urlopen") as mock_url_open, \
             patch("company_resolver.search_screener_company_discovery", side_effect=mock_screener_discovery):
            
            mock_resp = MagicMock()
            mock_resp.read.return_value = mock_nse_csv.encode("utf-8")
            mock_resp.__enter__.return_value = mock_resp
            mock_url_open.return_value = mock_resp

            # Case A: Exact Ticker "COLPAL"
            sec_a, is_ambig_a, _ = resolve_proven_security_for_add("COLPAL")
            assert is_ambig_a is False, "COLPAL must not be ambiguous"
            assert sec_a is not None, "COLPAL must resolve"
            assert sec_a["symbol"] == "COLPAL", f"Expected COLPAL, got {sec_a['symbol']}"

            # Case B: Brand Name "Colgate"
            sec_b, is_ambig_b, _ = resolve_proven_security_for_add("Colgate")
            assert is_ambig_b is False, "Colgate must not be ambiguous"
            assert sec_b is not None, "Colgate must resolve"
            assert sec_b["symbol"] == "COLPAL", f"Expected COLPAL, got {sec_b['symbol']}"

            # Case C: Full Legal Name "Colgate-Palmolive (India) Ltd"
            sec_c, is_ambig_c, _ = resolve_proven_security_for_add("Colgate-Palmolive (India) Ltd")
            assert is_ambig_c is False, "Full name must not be ambiguous"
            assert sec_c is not None, "Full name must resolve"
            assert sec_c["symbol"] == "COLPAL", f"Expected COLPAL, got {sec_c['symbol']}"

            print("✓ Case A, B, C passed: All 3 forms resolve to the exact same canonical COLPAL security from empty DB.")

            # -----------------------------------------------------------------
            # TEST 2: Ambiguous Query Rejection (HTTP 409 AMBIGUOUS_COMPANY)
            # -----------------------------------------------------------------
            print("\n--- Test 2: Ambiguous Query Handling (HTTP 409 AMBIGUOUS_COMPANY) ---")
            sec_ambig, is_ambig, ambig_cands = resolve_proven_security_for_add("TATA")
            assert is_ambig is True, "Query 'TATA' must be flagged as ambiguous"
            assert len(ambig_cands) >= 2, f"Expected multiple candidates, got {len(ambig_cands)}"

            try:
                execute_add_company_to_universe("TATA")
                assert False, "execute_add_company_to_universe('TATA') should have raised HTTPException 409"
            except HTTPException as he:
                assert he.status_code == 409, f"Expected 409, got {he.status_code}"
                detail = he.detail
                assert isinstance(detail, dict), "Detail must be a structured dictionary"
                assert detail.get("code") == "AMBIGUOUS_COMPANY", f"Expected AMBIGUOUS_COMPANY, got {detail.get('code')}"
                assert len(detail.get("candidates", [])) >= 2
                print("✓ Test 2 passed: Ambiguous query returned HTTP 409 with candidate choices.")

            # -----------------------------------------------------------------
            # TEST 3: Unresolved Input Safety (HTTP 404 without universe pollution)
            # -----------------------------------------------------------------
            print("\n--- Test 3: Unresolved Input Safety (Fail Closed) ---")
            sec_unres, is_ambig_u, unres_cands = resolve_proven_security_for_add("NONEXISTENTQUERY999")
            assert sec_unres is None, "Unknown query must not resolve to any security"
            assert is_ambig_u is False

            try:
                execute_add_company_to_universe("NONEXISTENTQUERY999")
                assert False, "Unknown query must raise HTTPException 404"
            except HTTPException as he:
                assert he.status_code == 404, f"Expected 404, got {he.status_code}"
                
            # Verify universe has 0 polluted records
            assert database.get_company_by_symbol("NONEXISTENTQUERY999") is None, "No fake security must be enrolled in DB"
            print("✓ Test 3 passed: Unknown input rejected with 404 and 0 DB pollution.")

    # -------------------------------------------------------------------------
    # TEST 4: SQLite Durable Financial Cache (Survives restart/request context)
    # -------------------------------------------------------------------------
    with IsolatedTestDatabase():
        print("\n--- Test 4: SQLite Durable Financial Cache (Survives restart/request simulation) ---")
        mock_colpal = sample_complete_stock_data("COLPAL")
        
        # 1. Scrape & persist to SQLite
        with patch("scraper.fetch_screener_html", return_value=("<html>mock</html>", "https://screener.in/colpal", "consolidated")), \
             patch("scraper.parse_screener_table", return_value=mock_colpal["profit_loss"]), \
             patch("scraper.parse_screener_ratios", return_value=mock_colpal["ratios"]), \
             patch("scraper.parse_screener_documents", return_value=mock_colpal["documents"]):
            
            res_scrape = fetch_stock_from_screener("COLPAL", force_refresh=True)
            assert res_scrape is not None
            assert res_scrape["symbol"] == "COLPAL"

        # 2. Simulate Application Restart & Delete JSON cache file
        from scraper import CACHE_FILE
        if os.path.exists(CACHE_FILE):
            os.remove(CACHE_FILE)
        assert not os.path.exists(CACHE_FILE), "JSON cache must be absent to test pure SQLite restoration"

        # 3. Request stock in fresh context with live network completely disabled
        with patch("scraper.fetch_screener_html", side_effect=Exception("Network Disabled!")):
            restored = fetch_stock_from_screener("COLPAL", force_refresh=False)
            assert restored is not None, "Stock must be restored from durable SQLite storage"
            assert restored["symbol"] == "COLPAL"
            assert restored["ratios"].roce_pct == 72.0
            assert restored["ratios"].current_price == 2800.0
            assert restored["profit_loss"] is not None

            # Verify StockDetail can be built from pure SQLite cache
            detail = build_full_stock_detail(restored)
            assert detail.symbol == "COLPAL"
            assert detail.score.total_composite_score > 0
            assert detail.projection.dcf_fair_value_per_share > 0

        print("✓ Test 4 passed: SQLite stocks_cache is durable and restores complete StockDetail without JSON cache or network.")

    # -------------------------------------------------------------------------
    # TEST 5: Decoupled Document Discovery Boundary
    # -------------------------------------------------------------------------
    with IsolatedTestDatabase():
        print("\n--- Test 5: Decoupled Document Discovery Boundary during Ingestion ---")
        sample_html = """
        <html>
            <ul id="top-ratios">
                <li><span class="name">Current Price</span><span class="value">2800</span></li>
            </ul>
            <div class="documents">
                <a href="https://example.com/ar2025.pdf">Annual Report 2025</a>
            </div>
        </html>
        """
        soup = BeautifulSoup(sample_html, "html.parser")
        with patch("document_sourcing.execute_document_sourcing_waterfall") as mock_wf:
            docs = parse_screener_documents(soup, "COLPAL", company_name="Colgate")
            mock_wf.assert_not_called()
            assert docs is not None

        # Verify nothing was written to source_documents SQLite table
        assert database.get_source_documents("COLPAL") == [], "Ingestion must NOT populate source_documents table"
        assert database.get_document_sources_checked_at("COLPAL") is None, "Ingestion must NOT set documents_checked_at"
        print("✓ Test 5 passed: Financial ingestion decoupled from external waterfall and does not fake discovery state.")

    # -------------------------------------------------------------------------
    # TEST 6: Explicit /discover-filings Restores Screener Stage 1 & Sync State
    # -------------------------------------------------------------------------
    with IsolatedTestDatabase():
        print("\n--- Test 6: Explicit /discover-filings Restores Screener Stage 1 & Sync State ---")
        mock_screener_docs = DocumentLinks(
            annual_reports=[
                DocumentItem(
                    title="Colgate Annual Report FY25",
                    url="https://www.screener.in/ar2025.pdf",
                    doc_type="annual_report",
                    period_or_date="FY25",
                    discovery_source="Screener.in",
                    actual_source_host="screener.in",
                    actual_source_url="https://www.screener.in/ar2025.pdf"
                )
            ],
            concalls=[
                DocumentItem(
                    title="Colgate Q3 FY25 Earnings Call",
                    url="https://www.screener.in/cc_q3_2025.pdf",
                    doc_type="concall_transcript",
                    period_or_date="Q3 FY25",
                    discovery_source="Screener.in",
                    actual_source_host="screener.in",
                    actual_source_url="https://www.screener.in/cc_q3_2025.pdf"
                )
            ]
        )

        mock_stock = sample_complete_stock_data("COLPAL")
        mock_stock["documents"] = mock_screener_docs

        # 1. Ingestion: scrapes financials and caches Screener document links
        database.save_stock_cache("COLPAL", "Colgate-Palmolive (India) Limited", "FMCG", "Personal Care", serialize_stock_data(mock_stock))
        database.upsert_company_registry_item({
            "symbol": "COLPAL",
            "company_name": "Colgate-Palmolive (India) Limited",
            "source": "seed_reference",
            "in_universe": True,
            "is_active": True
        })

        # Confirm source_documents is strictly empty immediately after financial ingestion
        assert database.get_source_documents("COLPAL") == [], "Ingestion must NOT populate source_documents table"
        assert database.get_document_sources_checked_at("COLPAL") is None
        pre_status = get_research_lifecycle_status("COLPAL")
        assert pre_status.source_filings == "not_searched"
        print("  ✓ Step 1 verified: source_documents is empty and source_filings='not_searched' post-ingestion.")

        # 2. Explicit /discover-filings invocation
        with patch("document_sourcing.verify_document_network_and_content", return_value=(True, 102400, "application/pdf")), \
             patch("document_sourcing.discover_documents_bse_fallback", return_value=[]), \
             patch("document_sourcing.discover_documents_nse_fallback", return_value=[]), \
             patch("document_sourcing.discover_documents_company_ir_fallback", return_value=[]):
            
            disc_res = discover_stock_filings("COLPAL")
            assert disc_res.symbol == "COLPAL"
            assert disc_res.filing_count >= 2, f"Expected >= 2 Screener documents promoted, got {disc_res.filing_count}"
            assert disc_res.documents_checked_at is not None
            assert disc_res.research_status.source_filings == "ready"

        # Confirm Screener candidates are now persisted in SQLite source_documents
        persisted_docs = database.get_source_documents("COLPAL")
        assert len(persisted_docs) >= 2
        urls = [d["url"] for d in persisted_docs]
        assert "https://www.screener.in/ar2025.pdf" in urls
        assert "https://www.screener.in/cc_q3_2025.pdf" in urls
        print("  ✓ Step 2 verified: Explicit discover-filings promoted and persisted Screener Stage 1 candidates.")

        # Unregistered symbol must fail with 404
        try:
            discover_stock_filings("UNKNOWN_SECURITY_XYZ")
            assert False, "Unregistered symbol must raise HTTPException 404 in /discover-filings"
        except HTTPException as he:
            assert he.status_code == 404

        print("✓ Test 6 passed: Screener Stage 1 restored during explicit discovery only and persisted safely.")

    # -------------------------------------------------------------------------
    # TEST 7: Nullable Ratios Safe End-to-End (Fallback Path Fully Exercised)
    # -------------------------------------------------------------------------
    with IsolatedTestDatabase():
        print("\n--- Test 7: Nullable Ratios Safe End-to-End (Fallback Path Fully Exercised) ---")
        sparse_ratios = KeyRatios(
            current_price=None,
            market_cap_cr=None,
            stock_pe=None,
            book_value=None,
            roce_pct=None,
            roe_pct=None,
            debt_to_equity=None,
            interest_coverage=None,
            fcf_yield_pct=None,
            sales_growth_3yr_cagr=None,
            profit_growth_3yr_cagr=None
        )
        
        # Completely empty / zero historical Sales to exercise fallback sales path
        stock_sparse = {
            "symbol": "SPARSECO",
            "name": "Sparse Company Ltd",
            "sector": "Industrials",
            "industry": "Machinery",
            "about": "A company with missing reported ratios and missing historical sales rows.",
            "source_name": "Screener.in",
            "source_url": "https://screener.in/sparseco",
            "statement_type": "consolidated",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "ratios": sparse_ratios,
            "quarters": FinancialStatement(periods=[], rows=[]),
            "profit_loss": FinancialStatement(periods=[], rows=[]),
            "balance_sheet": FinancialStatement(periods=[], rows=[]),
            "cash_flow": FinancialStatement(periods=[], rows=[]),
            "concall_insights": [],
            "annual_report_insights": [],
            "documents": DocumentLinks()
        }

        # 1. build_full_stock_detail must not crash and must not throw TypeError
        detail = build_full_stock_detail(stock_sparse)
        assert detail.symbol == "SPARSECO"
        assert detail.ratios.current_price is None
        assert detail.ratios.market_cap_cr is None
        assert detail.ratios.stock_pe is None
        assert detail.score.data_confidence == "Low / Incomplete Data"
        assert detail.projection.dcf_fair_value_per_share > 0

        # 2. compute_stock_score must not crash
        analytics = {"growth_rates": {}, "cash_flow_quality": {}}
        score = compute_stock_score("SPARSECO", "Sparse Company Ltd", sparse_ratios, analytics, detail.projection)
        assert score.data_confidence == "Low / Incomplete Data"

        print("✓ Test 7 passed: Fallback calculation paths safely handle KeyRatios with all None values without TypeError or crashing.")

    # -------------------------------------------------------------------------
    # TEST 8: Research Lifecycle State Transitions (Dual Version & Refresh Stale Tracking)
    # -------------------------------------------------------------------------
    with IsolatedTestDatabase():
        print("\n--- Test 8: Research Lifecycle State Transitions & Version Tracking ---")
        fin_v1 = "2026-08-31T09:00:00Z"
        mock_stock = sample_complete_stock_data("INFY", "Infosys Limited", fetched_at=fin_v1)
        serialized = serialize_stock_data(mock_stock)
        database.save_stock_cache("INFY", "Infosys Limited", "IT", "Software", serialized)
        database.upsert_company_registry_item({
            "symbol": "INFY",
            "company_name": "Infosys Limited",
            "source": "seed_reference",
            "in_universe": True,
            "is_active": True
        })

        # Phase 1: Financial-Only stock (no business analysis yet)
        st1 = get_research_lifecycle_status("INFY")
        assert st1.financial_data == "ready"
        assert st1.business_analysis == "not_run"
        assert st1.projection == "unavailable", f"Expected unavailable for financial-only baseline, got {st1.projection}"
        assert st1.investment_score == "provisional"
        assert st1.projection_updated_at is None, f"projection_updated_at must be None before projection computation, got {st1.projection_updated_at}"
        print("  ✓ State 1 verified: Financial-only -> projection=unavailable, projection_updated_at=None, investment_score=provisional")

        # Phase 2: Newly Generated Business Analysis (before StockDetail recomputation)
        ai_v1 = "2026-08-31T10:00:00Z"
        ai_data = {
            "company_name": "Infosys Limited",
            "symbol": "INFY",
            "extraction_timestamp": ai_v1,
            "latest_document_period": "FY25",
            "promise_vs_delivery": [
                {
                    "area": "Revenue Growth",
                    "management_promise": "Reach 15% revenue growth",
                    "promised_in_period": "FY24",
                    "actual_outcome": "Delivered 16% revenue growth",
                    "actual_in_period": "FY25",
                    "status": "Delivered",
                    "stocker_analysis": "Target met."
                }
            ],
            "growth_drivers": [
                {
                    "driver_title": "Cloud Migration",
                    "description": "Cloud migration pipeline",
                    "execution_status": "In Progress"
                }
            ],
            "what_changed_recently": [
                {
                    "headline": "Margin expansion across large deals",
                    "category": "Demand / Deal Win",
                    "detail": "Expanded operating margins across multi-year contracts."
                }
            ]
        }
        database.save_ai_analysis("INFY", "Infosys Limited", ai_data, "Gemini", "gemini-3.1-flash-lite")

        # Check lifecycle immediately after AI generation
        st2 = get_research_lifecycle_status("INFY")
        assert st2.business_analysis == "ready"
        assert st2.projection == "stale", f"Expected stale projection before recomputation, got {st2.projection}"
        assert st2.investment_score == "provisional", f"Expected provisional score before recomputation, got {st2.investment_score}"
        print("  ✓ State 2 verified: Business Analysis ready -> projection=stale (NOT evidence_enriched automatically)")

        # Phase 3: Actual StockDetail Recomputation
        with patch("scraper.fetch_stock_from_screener", return_value=mock_stock):
            recomputed_detail = build_full_stock_detail(mock_stock)
            assert recomputed_detail.symbol == "INFY"

        # Check lifecycle after StockDetail recomputed with matching versions
        st3 = get_research_lifecycle_status("INFY")
        assert st3.business_analysis == "ready"
        assert st3.projection == "evidence_enriched", f"Expected evidence_enriched projection, got {st3.projection}"
        assert st3.investment_score == "evidence_enriched", f"Expected evidence_enriched investment_score, got {st3.investment_score}"
        assert st3.projection_updated_at is not None, "projection_updated_at must be populated after projection computation"
        print("  ✓ State 3 verified: Post-recomputation with matching versions -> projection=evidence_enriched, projection_updated_at populated")

        # Phase 4: Financial Refresh (Version C) occurring AFTER Business Analysis
        fin_v2 = "2026-08-31T11:00:00Z"
        mock_stock_refreshed = sample_complete_stock_data("INFY", "Infosys Limited", fetched_at=fin_v2)
        database.save_stock_cache("INFY", "Infosys Limited", "IT", "Software", serialize_stock_data(mock_stock_refreshed))

        # Lifecycle must become stale because financials are now newer than AI analysis
        st4 = get_research_lifecycle_status("INFY")
        assert st4.business_analysis == "stale", f"Expected stale Business Analysis after financial refresh, got {st4.business_analysis}"
        assert st4.projection == "stale", f"Expected stale projection after financial refresh, got {st4.projection}"
        assert st4.investment_score == "provisional", f"Expected provisional score after financial refresh, got {st4.investment_score}"

        # Even if build_full_stock_detail runs with old AI, it must NOT become evidence_enriched
        with patch("scraper.fetch_stock_from_screener", return_value=mock_stock_refreshed):
            recomputed_detail2 = build_full_stock_detail(mock_stock_refreshed)
            assert recomputed_detail2.symbol == "INFY"

        st5 = get_research_lifecycle_status("INFY")
        assert st5.business_analysis == "stale"
        assert st5.projection == "stale"
        assert st5.investment_score == "provisional"
        print("  ✓ State 4 & 5 verified: Financial refresh invalidates prior AI evidence and prevents false evidence_enriched promotion.")

    # -------------------------------------------------------------------------
    # TEST 9: Financial Freshness & Usable Statement Readiness
    # -------------------------------------------------------------------------
    with IsolatedTestDatabase():
        print("\n--- Test 9: Financial Freshness & Usable Statement Readiness ---")
        # Case A: Usable Fresh statements (<90 days)
        mock_fresh = sample_complete_stock_data("FRESHCO", fetched_at=datetime.now(timezone.utc).isoformat())
        database.save_stock_cache("FRESHCO", "Fresh Co", "FMCG", "Food", serialize_stock_data(mock_fresh))
        database.upsert_company_registry_item({"symbol": "FRESHCO", "company_name": "Fresh Co", "in_universe": True, "is_active": True})
        st_fresh = get_research_lifecycle_status("FRESHCO")
        assert st_fresh.financial_data == "ready"
        assert st_fresh.deterministic_analysis == "ready"

        # Case B: Stale (>90 days old)
        old_time = (datetime.now(timezone.utc) - timedelta(days=120)).isoformat()
        mock_old = sample_complete_stock_data("OLDCO", fetched_at=old_time)
        database.save_stock_cache("OLDCO", "Old Co", "FMCG", "Food", serialize_stock_data(mock_old))
        database.upsert_company_registry_item({"symbol": "OLDCO", "company_name": "Old Co", "in_universe": True, "is_active": True})
        st_old = get_research_lifecycle_status("OLDCO")
        assert st_old.financial_data == "stale", f"Expected stale for 120d old financials, got {st_old.financial_data}"
        assert st_old.deterministic_analysis == "ready"

        # Case C: Structurally present but EMPTY statements (periods: [], rows: [])
        empty_struct_data = {
            "symbol": "EMPTYCO",
            "name": "Empty Struct Co",
            "profit_loss": {"periods": [], "rows": []},
            "balance_sheet": {"periods": [], "rows": []},
            "cash_flow": {"periods": [], "rows": []},
            "quarters": {"periods": [], "rows": []},
            "fetched_at": datetime.now(timezone.utc).isoformat()
        }
        database.save_stock_cache("EMPTYCO", "Empty Struct Co", "FMCG", "Food", empty_struct_data)
        database.upsert_company_registry_item({"symbol": "EMPTYCO", "company_name": "Empty Struct Co", "in_universe": True, "is_active": True})
        st_empty = get_research_lifecycle_status("EMPTYCO")
        assert st_empty.financial_data == "error", f"Expected error for empty statement structures, got {st_empty.financial_data}"
        assert st_empty.deterministic_analysis == "not_ready", f"Expected not_ready for empty statement structures, got {st_empty.deterministic_analysis}"

        # Case D: Malformed / Partial
        partial_data = {
            "symbol": "PARTIALCO",
            "name": "Partial Co",
            "profit_loss": None,
            "balance_sheet": None,
            "cash_flow": None,
            "quarters": None,
            "fetched_at": datetime.now(timezone.utc).isoformat()
        }
        database.save_stock_cache("PARTIALCO", "Partial Co", "FMCG", "Food", partial_data)
        database.upsert_company_registry_item({"symbol": "PARTIALCO", "company_name": "Partial Co", "in_universe": True, "is_active": True})
        st_part = get_research_lifecycle_status("PARTIALCO")
        assert st_part.financial_data in ("missing", "error")
        assert st_part.deterministic_analysis == "not_ready"

        print("✓ Test 9 passed: Statement readiness requires usable periods and rows; empty structures reject to error/not_ready.")

    # -------------------------------------------------------------------------
    # TEST 10: Empty Universe Semantics
    # -------------------------------------------------------------------------
    with IsolatedTestDatabase(seed=False):
        print("\n--- Test 10: Empty Universe Semantics ---")
        # Populate inactive registry item
        database.upsert_company_registry_item({
            "symbol": "REMOVED_CO",
            "company_name": "Removed Co",
            "in_universe": False,
            "is_active": False
        })
        assert database.get_company_registry_total_count() == 1
        assert len(database.get_universe_companies(active_only=True)) == 0

        with patch("database.seed_company_registry") as mock_seed:
            stocks = get_all_stocks()
            assert stocks == [], f"Expected empty list, got {stocks}"
            mock_seed.assert_not_called()
        print("✓ Test 10 passed: Total count > 0 with 0 active items preserves empty universe without reseeding.")

    # -------------------------------------------------------------------------
    # TEST 11: Authoritative Identity Provenance & Lifecycle State
    # -------------------------------------------------------------------------
    with IsolatedTestDatabase(seed=False):
        print("\n--- Test 11: Authoritative Identity Provenance & Lifecycle State ---")
        verif_time = "2026-08-31T08:00:00Z"
        
        # 1. Authoritative NSE-resolved company
        database.upsert_company_registry_item({
            "symbol": "COLPAL",
            "company_name": "Colgate-Palmolive (India) Limited",
            "nse_symbol": "COLPAL",
            "bse_code": "500830",
            "isin": "INE162A01024",
            "exchange": "NSE",
            "source": "NSE",
            "identity_source_name": "NSE Security Master",
            "identity_source_url": "https://archives.nseindia.com/content/equities/EQUITY_L.csv",
            "identity_verified_at": verif_time,
            "source_last_verified_at": verif_time,
            "in_universe": True,
            "is_active": True
        })
        
        colpal_reg = database.get_company_by_symbol("COLPAL")
        assert colpal_reg["identity_source_name"] == "NSE Security Master"
        assert colpal_reg["identity_verified_at"] == verif_time
        assert colpal_reg["source"] == "NSE"
        
        colpal_lifecycle = get_research_lifecycle_status("COLPAL")
        assert colpal_lifecycle.identity == "officially_verified", f"Expected officially_verified, got {colpal_lifecycle.identity}"

        # 2. Screener/seed-reference company without official verification timestamp
        database.upsert_company_registry_item({
            "symbol": "UNVERIFIED_CO",
            "company_name": "Unverified Co Ltd",
            "source": "screener_ingestion",
            "in_universe": True,
            "is_active": True
        })
        
        unver_reg = database.get_company_by_symbol("UNVERIFIED_CO")
        assert unver_reg["source_last_verified_at"] is None, "Verification timestamp must not be fabricated!"
        
        unver_lifecycle = get_research_lifecycle_status("UNVERIFIED_CO")
        assert unver_lifecycle.identity == "resolved", f"Expected resolved, got {unver_lifecycle.identity}"

        print("✓ Test 11 passed: Authoritative identity provenance persisted and lifecycle distinguishes officially_verified vs resolved.")

    # -------------------------------------------------------------------------
    # TEST 12: BSE Filing Discovery Using Canonical Registry Scrip Code
    # -------------------------------------------------------------------------
    with IsolatedTestDatabase(seed=False):
        print("\n--- Test 12: BSE Filing Discovery Using Canonical Registry Scrip Code ---")
        from document_sourcing import BSE_SCRIP_CODES, discover_documents_bse_fallback
        
        # Security NOT present in hardcoded BSE_SCRIP_CODES map
        unmapped_symbol = "BERGEPAINT"
        assert unmapped_symbol not in BSE_SCRIP_CODES, "Security must not be in hardcoded fallback map for this test"
        
        database.upsert_company_registry_item({
            "symbol": unmapped_symbol,
            "company_name": "Berger Paints India Limited",
            "nse_symbol": "BERGEPAINT",
            "bse_code": "509480",
            "source": "NSE",
            "in_universe": True,
            "is_active": True
        })

        mock_bse_response = {
            "Table": [
                {
                    "NEWSSUB": "Berger Paints Q3 FY26 Earnings Conference Call Transcript",
                    "ATTACHMENTNAME": "berge_q3_transcript.pdf",
                    "NEWS_DT": "2026-01-15"
                }
            ]
        }

        with patch("requests.get") as mock_get, \
             patch("document_sourcing.validate_document_candidate", return_value=(True, "berge_q3_transcript.pdf")):
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = mock_bse_response
            mock_get.return_value = mock_resp

            found_docs = discover_documents_bse_fallback(
                symbol=unmapped_symbol,
                company_name="Berger Paints India Limited",
                needed_types=["concall_transcript"]
            )
            
            assert len(found_docs) > 0, "Expected BSE discovery to find document using registry bse_code"
            assert found_docs[0].ticker == unmapped_symbol
            assert "berge_q3_transcript.pdf" in found_docs[0].url
            
            # Verify the API URL called included the registry bse_code '509480'
            called_url = mock_get.call_args[0][0]
            assert "strScrip=509480" in called_url, f"Expected strScrip=509480 in {called_url}"

        print("✓ Test 12 passed: BSE filing discovery successfully uses persisted registry bse_code for unmapped companies.")

    print("\n==================================================================")
    print("🎉 ALL PHASE V4.1 STEP 1A TESTS (1-12) PASSED 100% CLEANLY!")
    print("==================================================================")

if __name__ == "__main__":
    run_all_tests()


