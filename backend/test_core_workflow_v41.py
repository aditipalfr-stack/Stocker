"""
=============================================================================
Stocker Phase V4.1 Step 1A Regression & Core Workflow Test Suite
=============================================================================
Verifies:
1. Canonical company resolution & alias search (COLPAL, Colgate, INFY, Reliance)
2. Fail-closed behavior on unknown queries
3. Ingestion & Add Company flow without external waterfall blocking
4. Deterministic research lifecycle status across all 8 contract dimensions
5. Missing ratios represented as None (not 0.0)
6. Empty universe semantics (no unwanted auto-reseeding when active universe is empty)
7. Dedicated /discover-filings endpoint
=============================================================================
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
from bs4 import BeautifulSoup

os.environ["STOCKER_TEST_MODE"] = "1"
sys.path.insert(0, str(Path(__file__).parent.parent / "libs"))
sys.path.insert(0, str(Path(__file__).parent))

import database
from main import (
    search_companies, execute_add_company_to_universe,
    add_company_to_universe_by_body, get_stock_research_status,
    discover_stock_filings, get_all_stocks
)
from models import (
    KeyRatios, FinancialStatement, FinancialRow, AddCompanyRequest,
    ResearchLifecycleStatus
)
from scraper import parse_screener_ratios, parse_screener_documents
from research_lifecycle_service import get_research_lifecycle_status
from company_resolver import resolve_and_search_companies, resolve_canonical_company

class IsolatedTestDatabase:
    def __enter__(self):
        self.temp_dir = tempfile.mkdtemp(prefix="stocker_test_v41_")
        self.db_path = Path(self.temp_dir) / "test_stocker.db"
        self.orig_env_db = os.environ.get("STOCKER_DB_PATH")
        os.environ["STOCKER_DB_PATH"] = str(self.db_path)
        self.orig_db_path = database.DB_PATH
        database.DB_PATH = self.db_path
        database.init_db()
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

def run_tests():
    print("==================================================================")
    print("Running Stocker Phase V4.1 Core Workflow Test Suite")
    print("==================================================================")

    with IsolatedTestDatabase():
        # Seed test companies
        database.upsert_company_registry_item({
            "symbol": "INFY",
            "company_name": "Infosys Limited",
            "nse_symbol": "INFY",
            "bse_code": "500209",
            "sector": "Information Technology",
            "industry": "Computers - Software",
            "aliases": ["Infosys", "INFY"],
            "source": "seed_reference",
            "in_universe": True,
            "is_active": True
        })
        database.upsert_company_registry_item({
            "symbol": "RELIANCE",
            "company_name": "Reliance Industries Limited",
            "nse_symbol": "RELIANCE",
            "bse_code": "500325",
            "sector": "Energy",
            "industry": "Refineries",
            "aliases": ["Reliance", "RIL", "Reliance Industries"],
            "source": "seed_reference",
            "in_universe": True,
            "is_active": True
        })
        database.upsert_company_registry_item({
            "symbol": "COLPAL",
            "company_name": "Colgate-Palmolive (India) Limited",
            "nse_symbol": "COLPAL",
            "bse_code": "500830",
            "sector": "FMCG",
            "industry": "Personal Care",
            "aliases": ["Colgate", "Colgate Palmolive", "COLPAL"],
            "source": "seed_reference",
            "in_universe": True,
            "is_active": True
        })

        # Test 1: Search resolves exact ticker
        print("Test 1: Search resolves exact ticker symbol (INFY)...")
        res1 = search_companies(q="INFY", limit=5)
        assert res1.count > 0, "Expected at least 1 result for INFY"
        assert res1.results[0].symbol == "INFY", f"Expected INFY top result, got {res1.results[0].symbol}"
        assert res1.results[0].match_score >= 80, f"Expected match score >= 80, got {res1.results[0].match_score}"
        print("✓ Test 1 Passed.")

        # Test 2: Search resolves company name
        print("Test 2: Search resolves company name ('Reliance Industries')...")
        res2 = search_companies(q="Reliance Industries", limit=5)
        assert res2.count > 0, "Expected at least 1 result for Reliance Industries"
        symbols2 = [r.symbol for r in res2.results]
        assert "RELIANCE" in symbols2, f"Expected RELIANCE in results, got {symbols2}"
        print("✓ Test 2 Passed.")

        # Test 3: Search resolves partial name / alias (Colgate -> COLPAL)
        print("Test 3: Search resolves partial name and aliases (Colgate -> COLPAL) without hardcoding...")
        res3 = search_companies(q="Colgate", limit=5)
        assert res3.count > 0, "Expected at least 1 result for Colgate"
        assert res3.results[0].symbol == "COLPAL", f"Expected COLPAL top result, got {res3.results[0].symbol}"
        
        canonical_colpal = resolve_canonical_company("Colgate-Palmolive (India) Ltd")
        assert canonical_colpal is not None, "Expected canonical resolution for Colgate-Palmolive (India) Ltd"
        assert canonical_colpal["symbol"] == "COLPAL", f"Expected COLPAL, got {canonical_colpal['symbol']}"
        print("✓ Test 3 Passed.")

        # Test 4: Fail closed on completely unknown query
        print("Test 4: Fail closed on unknown query without fabricating security identifiers...")
        res4 = search_companies(q="XYZNONEXISTENT999XYZ", limit=5)
        for r in res4.results:
            assert r.isin is None, "ISIN must not be fabricated"
            assert r.exchange is None, "Exchange must not be fabricated"
        print("✓ Test 4 Passed.")

        # Test 5 & 6: Add Company flow with query and symbol
        print("Test 5 & 6: Add company via query and symbol...")
        mock_stock = {
            "symbol": "TESTCO",
            "name": "Test Company Limited",
            "sector": "FMCG",
            "industry": "Personal Care",
            "about": "Test description",
            "source_name": "Screener.in",
            "source_url": "https://www.screener.in/company/TESTCO/",
            "statement_type": "consolidated",
            "fetched_at": "2026-08-31T09:00:00Z",
            "ratios": KeyRatios(
                market_cap_cr=5000.0,
                current_price=250.0,
                stock_pe=25.0,
                book_value=50.0,
                dividend_yield_pct=1.5,
                roce_pct=22.0,
                roe_pct=18.0,
                face_value=1.0,
                debt_to_equity=0.1,
                interest_coverage=15.0,
                fcf_yield_pct=3.0,
                sales_growth_3yr_cagr=12.0,
                profit_growth_3yr_cagr=14.0
            ),
            "quarters": FinancialStatement(periods=["Jun 2025"], rows=[FinancialRow(metric="Sales", values={"Jun 2025": 1000.0})]),
            "profit_loss": FinancialStatement(periods=["Mar 2025"], rows=[FinancialRow(metric="Sales", values={"Mar 2025": 4000.0})]),
            "balance_sheet": FinancialStatement(periods=["Mar 2025"], rows=[FinancialRow(metric="Equity Capital", values={"Mar 2025": 500.0})]),
            "cash_flow": FinancialStatement(periods=["Mar 2025"], rows=[FinancialRow(metric="Cash from Operating Activity", values={"Mar 2025": 600.0})]),
            "concall_insights": [],
            "annual_report_insights": [],
            "documents": None
        }

        with patch("main.fetch_stock_from_screener", return_value=mock_stock):
            # Query body
            add_res1 = add_company_to_universe_by_body(AddCompanyRequest(query="TESTCO"))
            assert add_res1.success is True
            assert add_res1.symbol == "TESTCO"
            assert add_res1.research_status is not None
            assert add_res1.research_status.financial_data == "ready"
            assert add_res1.research_status.deterministic_analysis == "ready"

            # Symbol body (backward compatibility)
            add_res2 = add_company_to_universe_by_body(AddCompanyRequest(symbol="TESTCO"))
            assert add_res2.already_existed is True
        print("✓ Test 5 & 6 Passed.")

        # Test 7: Decoupled document sourcing during financial ingestion
        print("Test 7: Financial statement parsing extracts cheap HTML docs without executing external waterfall...")
        sample_html = """
        <html>
            <ul id="top-ratios">
                <li><span class="name">Market Cap</span><span class="value">10,000</span></li>
                <li><span class="name">Stock P/E</span><span class="value">20.5</span></li>
            </ul>
            <div class="documents">
                <a href="https://example.com/ar2025.pdf">Annual Report 2025</a>
            </div>
        </html>
        """
        soup = BeautifulSoup(sample_html, "html.parser")
        with patch("document_sourcing.execute_document_sourcing_waterfall") as mock_waterfall:
            docs = parse_screener_documents(soup, "TESTCO", company_name="Test Company")
            mock_waterfall.assert_not_called()
            assert docs is not None
        print("✓ Test 7 Passed.")

        # Test 8: Missing Screener ratios remain None instead of collapsing to 0.0
        print("Test 8: Missing Screener ratios remain None instead of collapsing to 0.0...")
        minimal_html = """
        <html>
            <ul id="top-ratios">
                <li><span class="name">Current Price</span><span class="value">150.0</span></li>
            </ul>
        </html>
        """
        soup = BeautifulSoup(minimal_html, "html.parser")
        ratios = parse_screener_ratios(soup)
        assert ratios.current_price == 150.0
        assert ratios.roce_pct is None, f"Expected None, got {ratios.roce_pct}"
        assert ratios.roe_pct is None, f"Expected None, got {ratios.roe_pct}"
        assert ratios.debt_to_equity is None, f"Expected None, got {ratios.debt_to_equity}"
        assert ratios.fcf_yield_pct is None, f"Expected None, got {ratios.fcf_yield_pct}"
        print("✓ Test 8 Passed.")

        # Test 9: Research status endpoint returns 8 valid dimensions conforming to contract
        print("Test 9: Research status endpoint returns 8 valid dimensions conforming to contract...")
        st = get_stock_research_status("INFY")
        assert st.symbol == "INFY"
        assert st.identity in ["unresolved", "resolved", "officially_verified"]
        assert st.financial_data in ["missing", "ready", "stale", "error"]
        assert st.deterministic_analysis in ["not_ready", "ready"]
        assert st.official_verification in ["not_run", "partial", "verified", "discrepancy"]
        assert st.source_filings in ["not_searched", "partial", "ready", "error"]
        assert st.business_analysis in ["not_run", "running", "ready", "stale", "error"]
        assert st.projection in ["unavailable", "historical_only", "evidence_enriched", "stale"]
        assert st.investment_score in ["unavailable", "provisional", "evidence_enriched", "incomplete"]
        print("✓ Test 9 Passed.")

        # Test 10: Empty universe semantics (total_count > 0, active == 0 does NOT auto-reseed)
        print("Test 10: Empty universe semantics (total_count > 0, active == 0 does NOT auto-reseed)...")
        database.upsert_company_registry_item({
            "symbol": "INACTIVE_ONLY",
            "company_name": "Inactive Only Co",
            "in_universe": False,
            "is_active": False
        })
        with patch("database.get_universe_symbols", return_value=[]):
            with patch("database.seed_company_registry") as mock_seed:
                stocks = get_all_stocks()
                assert stocks == [], f"Expected empty list, got {stocks}"
                mock_seed.assert_not_called()
        print("✓ Test 10 Passed.")

        # Test 11: Dedicated discover-filings endpoint
        print("Test 11: Dedicated discover-filings endpoint executes waterfall and updates lifecycle...")
        with patch("document_sourcing.execute_document_sourcing_waterfall") as mock_exec:
            mock_exec.return_value = None
            disc_res = discover_stock_filings("RELIANCE")
            assert disc_res.symbol == "RELIANCE"
            assert disc_res.research_status is not None
            mock_exec.assert_called_once()
        print("✓ Test 11 Passed.")

    print("\n==================================================================")
    print("ALL 11 TEST CASES PASSED CLEANLY!")
    print("==================================================================")

if __name__ == "__main__":
    run_tests()
