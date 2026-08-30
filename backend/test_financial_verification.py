"""
=============================================================================
Stocker V3 Phase B: Authoritative Identity & Official Financial Verification
Comprehensive Unit & Integration Test Suite
=============================================================================
Fully isolated, deterministic test suite:
- Runs against an isolated temporary SQLite database (STOCKER_TEST_MODE=1)
- Zero external live network dependence (all mock isolated)
- Verifies exact tolerance math, scope matching, period normalization,
  authoritative ordered lookup, and source precedence.
=============================================================================
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

os.environ["STOCKER_TEST_MODE"] = "1"

sys.path.insert(0, str(Path(__file__).parent.parent / "libs"))
sys.path.insert(0, str(Path(__file__).parent))

import database
import authoritative_identity
import official_financial_service
from authoritative_identity import (
    lookup_authoritative_exchange_identity,
    is_ambiguous_company_name,
    resolve_and_upgrade_company_identity,
    normalize_legal_name
)
from official_financial_service import (
    normalize_period,
    normalize_metric_name,
    normalize_numeric_scale,
    compare_financial_metric,
    extract_official_filing_metrics,
    run_official_financial_verification
)

# Helper fixture for isolated test database
class IsolatedTestDatabase:
    def __enter__(self):
        self.temp_dir = tempfile.mkdtemp(prefix="stocker_phase_b_test_")
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

def test_authoritative_identity_ordered_lookup():
    print("1. Testing Authoritative Identity Ordered Lookup (ISIN > NSE > BSE > Symbol > Name)...")
    
    # 1. Lookup by ISIN
    res_isin, amb1 = lookup_authoritative_exchange_identity("INE009A01021")
    assert amb1 is False
    assert res_isin is not None
    assert res_isin["symbol"] == "INFY"
    assert res_isin["nse_symbol"] == "INFY"
    assert res_isin["isin"] == "INE009A01021"
    assert res_isin["source"] == "NSE"

    # 2. Lookup by verified NSE Symbol
    res_nse, amb2 = lookup_authoritative_exchange_identity("BHARTIARTL")
    assert amb2 is False
    assert res_nse is not None
    assert res_nse["symbol"] == "BHARTIARTL"
    assert res_nse["isin"] == "INE397D01024"
    assert res_nse["bse_code"] == "532454"

    # 3. Lookup by verified BSE Code
    res_bse, amb3 = lookup_authoritative_exchange_identity("500325")
    assert amb3 is False
    assert res_bse is not None
    assert res_bse["symbol"] == "RELIANCE"
    assert res_bse["isin"] == "INE002A01018"
    assert res_bse["source"] == "BSE"

    # 4. Lookup by exact Legal Company Name
    res_name, amb4 = lookup_authoritative_exchange_identity("Larsen & Toubro Limited")
    assert amb4 is False
    assert res_name is not None
    assert res_name["symbol"] == "LT"
    assert res_name["nse_symbol"] == "LT"

    # 5. Unknown input lookup returns None without fabricating
    res_unknown, amb5 = lookup_authoritative_exchange_identity("XYZUNKNOWN_CO")
    assert res_unknown is None
    
    print("  ✓ Authoritative identity ordered matching verified.")

def test_ambiguous_identity_rejection():
    print("2. Testing Ambiguous Identity Rejection (Separate Securities with Similar Names)...")
    
    # Partial query 'Tata' matches Tata Motors, Tata Steel, etc.
    res, is_amb = lookup_authoritative_exchange_identity("Tata")
    assert is_amb is True
    assert res is None, "Ambiguous partial query 'Tata' must NOT falsely merge into an arbitrary company!"

    # Specific distinct securities match accurately without conflict
    res_steel, is_amb_steel = lookup_authoritative_exchange_identity("Tata Steel Limited")
    assert is_amb_steel is False
    assert res_steel["symbol"] == "TATASTEEL"

    res_motors, is_amb_motors = lookup_authoritative_exchange_identity("Tata Motors Limited")
    assert is_amb_motors is False
    assert res_motors["symbol"] == "TATAMOTORS"

    print("  ✓ Ambiguous identities rejected safely.")

def test_source_precedence_and_identity_upgrade():
    print("3. Testing Source Precedence & Authoritative Identity Upgrade...")
    with IsolatedTestDatabase() as test_db:
        # Step A: Insert a discovery record for BHARTIARTL with null official fields
        database.upsert_company_registry_item({
            "symbol": "BHARTIARTL",
            "company_name": "Bharti Airtel Ltd",
            "nse_symbol": None,
            "bse_code": None,
            "isin": None,
            "exchange": None,
            "source": "screener_search",
            "in_universe": True,
            "is_active": True
        })
        
        item_before = database.get_company_by_symbol("BHARTIARTL")
        assert item_before["source"] == "screener_search"
        assert item_before["isin"] is None
        assert item_before["exchange"] is None

        # Step B: Upgrade with authoritative official exchange metadata
        upgraded = resolve_and_upgrade_company_identity("BHARTIARTL")
        assert upgraded is not None
        assert upgraded["symbol"] == "BHARTIARTL"
        assert upgraded["nse_symbol"] == "BHARTIARTL"
        assert upgraded["bse_code"] == "532454"
        assert upgraded["isin"] == "INE397D01024"
        assert upgraded["exchange"] == "NSE/BSE"
        assert upgraded["source"] == "NSE"
        assert upgraded["in_universe"] is True, "Universe status must be preserved!"

        # Step C: Lower-tier source (screener_search / manual) must NEVER downgrade verified identity
        database.upgrade_company_authoritative_identity("BHARTIARTL", {
            "symbol": "BHARTIARTL",
            "company_name": "Bharti Airtel Weak Name",
            "source": "screener_search"
        })
        item_after_weak = database.get_company_by_symbol("BHARTIARTL")
        assert item_after_weak["source"] == "NSE", "Higher-tier verified source must NOT be downgraded!"
        assert item_after_weak["isin"] == "INE397D01024"

        # Step D: Confirm NO duplicate rows exist
        conn = database.get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) as cnt FROM company_registry WHERE symbol = 'BHARTIARTL'")
            assert cur.fetchone()["cnt"] == 1, "Identity upgrade must NOT create duplicate rows!"
        finally:
            conn.close()

    print("  ✓ Source precedence and idempotent upgrade verified.")

def test_canonical_period_normalization():
    print("4. Testing Canonical Period Normalization (Quarters & Fiscal Years)...")
    
    # Quarterly formats
    assert normalize_period("Jun 2026") == ("Jun 2026", "2026-Q1")
    assert normalize_period("Q1 FY27") == ("Jun 2026", "2026-Q1")
    assert normalize_period("Quarter ended 30 June 2026") == ("Jun 2026", "2026-Q1")
    assert normalize_period("30-Jun-2026") == ("Jun 2026", "2026-Q1")

    assert normalize_period("Sep 2026") == ("Sep 2026", "2026-Q2")
    assert normalize_period("Q2 FY27") == ("Sep 2026", "2026-Q2")
    
    assert normalize_period("Dec 2025") == ("Dec 2025", "2025-Q3")
    assert normalize_period("Q3 FY26") == ("Dec 2025", "2025-Q3")

    assert normalize_period("Mar 2026") == ("Mar 2026", "2026-Q4")
    assert normalize_period("Q4 FY26") == ("Mar 2026", "2026-Q4")

    # Annual formats
    assert normalize_period("FY26") == ("FY26", "2026-FY")
    assert normalize_period("Year ended 31 March 2026") == ("FY26", "2026-FY")
    assert normalize_period("12M FY26") == ("FY26", "2026-FY")

    print("  ✓ Canonical period normalization verified.")

def test_metric_alias_and_scale_normalization():
    print("5. Testing Metric Alias Mapping & Scale Normalization (Lakhs/Millions -> ₹ Cr)...")
    
    # Metric aliases
    assert normalize_metric_name("Revenue from Operations") == "REVENUE"
    assert normalize_metric_name("Net Sales") == "REVENUE"
    assert normalize_metric_name("Operating Profit (EBITDA)") == "OPERATING_PROFIT"
    assert normalize_metric_name("Profit before tax and exceptional items") == "PBT"
    assert normalize_metric_name("Profit for the period") == "PAT"
    assert normalize_metric_name("Basic EPS (Rs)") == "EPS"

    # Scale conversion
    assert normalize_numeric_scale(4821100.0, "₹ Lakhs") == 48211.0
    assert normalize_numeric_scale(482110.0, "₹ Millions") == 48211.0
    assert normalize_numeric_scale(482.11, "₹ Billions") == 48211.0
    assert normalize_numeric_scale(48211.0, "₹ Cr") == 48211.0
    
    print("  ✓ Metric alias mapping and scale conversion verified.")

def test_scope_mismatch_not_comparable():
    print("6. Testing Consolidated vs Standalone Scope Mismatch (NOT_COMPARABLE)...")
    
    # Screener is Consolidated (₹48,211 Cr) while Official filing is Standalone (₹40,000 Cr)
    res = compare_financial_metric(
        screener_val=48211.0,
        official_val=40000.0,
        canonical_metric="REVENUE",
        screener_scope="Consolidated",
        official_scope="Standalone",
        screener_period_key="2026-Q1",
        official_period_key="2026-Q1"
    )
    assert res["status"] == "NOT_COMPARABLE"
    assert "Scope mismatch" in res["notes"]
    assert res["variance_abs"] is None, "Scope mismatch must not compute a misleading variance!"

    print("  ✓ Scope mismatch correctly handled as NOT_COMPARABLE.")

def test_deterministic_numeric_tolerance_and_discrepancy():
    print("7. Testing Deterministic Numeric Tolerance Math & Discrepancy Detection...")
    
    # Case A: Rounding difference within ₹1 Cr tolerance -> VERIFIED
    res_round = compare_financial_metric(
        screener_val=48211.0,
        official_val=48210.6,
        canonical_metric="REVENUE",
        screener_scope="Consolidated",
        official_scope="Consolidated",
        screener_period_key="2026-Q1",
        official_period_key="2026-Q1"
    )
    assert res_round["status"] == "VERIFIED"
    assert res_round["variance_abs"] == 0.4
    assert "Verified" in res_round["notes"]

    # Case B: Relative tolerance for large numbers (₹300,000 Cr with ₹500 Cr difference, 0.16% < 0.5%) -> VERIFIED
    res_large = compare_financial_metric(
        screener_val=309468.0,
        official_val=309000.0,
        canonical_metric="REVENUE",
        screener_scope="Consolidated",
        official_scope="Consolidated",
        screener_period_key="2026-Q1",
        official_period_key="2026-Q1"
    )
    assert res_large["status"] == "VERIFIED"

    # Case C: Material numerical discrepancy (> 0.5% and > ₹1 Cr) -> DISCREPANCY
    res_disc = compare_financial_metric(
        screener_val=48211.0,
        official_val=42000.0, # ₹6,211 Cr difference
        canonical_metric="REVENUE",
        screener_scope="Consolidated",
        official_scope="Consolidated",
        screener_period_key="2026-Q1",
        official_period_key="2026-Q1"
    )
    assert res_disc["status"] == "DISCREPANCY"
    assert res_disc["variance_abs"] == 6211.0
    assert "Discrepancy detected" in res_disc["notes"]

    # Case D: EPS tolerance (0.05 tolerance)
    res_eps_ver = compare_financial_metric(
        screener_val=15.42,
        official_val=15.40,
        canonical_metric="EPS",
        screener_scope="Consolidated",
        official_scope="Consolidated",
        screener_period_key="2026-Q1",
        official_period_key="2026-Q1"
    )
    assert res_eps_ver["status"] == "VERIFIED"

    res_eps_disc = compare_financial_metric(
        screener_val=15.42,
        official_val=12.10,
        canonical_metric="EPS",
        screener_scope="Consolidated",
        official_scope="Consolidated",
        screener_period_key="2026-Q1",
        official_period_key="2026-Q1"
    )
    assert res_eps_disc["status"] == "DISCREPANCY"

    print("  ✓ Deterministic tolerance math and discrepancy detection verified.")

def test_missing_values_status():
    print("8. Testing Missing Official & Screener Values...")
    
    # Official value missing
    res_off_miss = compare_financial_metric(
        screener_val=48211.0,
        official_val=None,
        canonical_metric="REVENUE",
        screener_scope="Consolidated",
        official_scope="Consolidated",
        screener_period_key="2026-Q1",
        official_period_key="2026-Q1"
    )
    assert res_off_miss["status"] == "OFFICIAL_SOURCE_MISSING"

    # Screener value missing
    res_scr_miss = compare_financial_metric(
        screener_val=None,
        official_val=48211.0,
        canonical_metric="REVENUE",
        screener_scope="Consolidated",
        official_scope="Consolidated",
        screener_period_key="2026-Q1",
        official_period_key="2026-Q1"
    )
    assert res_scr_miss["status"] == "SCREENER_VALUE_MISSING"

    print("  ✓ Missing value status classifications verified.")

def test_full_financial_verification_pipeline_and_persistence():
    print("9. Testing Full Financial Verification Pipeline & Persistence (Pilot Company: INFY)...")
    
    mock_screener_infy = {
        "symbol": "INFY",
        "name": "Infosys Limited",
        "statement_type": "consolidated",
        "source_url": "https://www.screener.in/company/INFY/consolidated/",
        "quarters": {
            "periods": ["Jun 2026", "Mar 2026"],
            "rows": [
                {"metric": "Sales", "values": {"Jun 2026": 48211.0, "Mar 2026": 45000.0}},
                {"metric": "Operating Profit", "values": {"Jun 2026": 10800.0, "Mar 2026": 10200.0}},
                {"metric": "Profit before tax", "values": {"Jun 2026": 9200.0, "Mar 2026": 8900.0}},
                {"metric": "Net Profit", "values": {"Jun 2026": 6800.0, "Mar 2026": 6500.0}},
                {"metric": "EPS in Rs", "values": {"Jun 2026": 16.4, "Mar 2026": 15.7}}
            ]
        },
        "profit_loss": {
            "periods": ["Mar 2026"],
            "rows": [
                {"metric": "Sales", "values": {"Mar 2026": 185000.0}},
                {"metric": "Net Profit", "values": {"Mar 2026": 27000.0}}
            ]
        }
    }
    
    mock_official_filings = [
        {
            "document_title": "Infosys Q1 FY27 Financial Results Outcome (NSE/BSE)",
            "reporting_period": "Quarter ended 30 June 2026",
            "scope": "Consolidated",
            "source_name": "NSE Filing",
            "source_url": "https://nsearchives.nseindia.com/corporate/INFY_Outcome_Jun2026.pdf",
            "unit": "₹ Cr",
            "financial_table": [
                {"metric": "Revenue from Operations", "value": 48211.0},
                {"metric": "Operating Profit (EBITDA)", "value": 10800.0},
                {"metric": "Profit Before Tax", "value": 9200.0},
                {"metric": "Profit After Tax", "value": 6800.0},
                {"metric": "Basic EPS", "value": 16.4}
            ]
        }
    ]
    
    with IsolatedTestDatabase() as test_db:
        # Run verification pipeline
        res = run_official_financial_verification(
            "INFY",
            screener_stock_data=mock_screener_infy,
            official_filing_docs=mock_official_filings
        )
        
        summary = res["summary"]
        records = res["records"]
        
        assert summary["symbol"] == "INFY"
        assert summary["overall_status"] == "VERIFIED"
        assert summary["verified_count"] == 5
        assert summary["discrepancy_count"] == 0
        assert summary["confidence_score"] == 1.0
        assert summary["isin"] == "INE009A01021"
        assert summary["nse_symbol"] == "INFY"
        assert summary["bse_code"] == "500209"
        
        # Verify database persistence
        db_records = database.get_financial_verification_records("INFY")
        assert len(db_records) == 5
        db_summary = database.get_financial_verification_summary("INFY")
        assert db_summary["overall_status"] == "VERIFIED"
        assert db_summary["verified_count"] == 5

    print("  ✓ Full financial verification pipeline and database persistence verified.")

def test_api_endpoints_and_stock_detail_integration():
    print("10. Testing API Endpoints & StockDetail Verification Integration...")
    from main import get_stock_financial_verification, build_full_stock_detail
    
    mock_stock_data = {
        "symbol": "TCS",
        "name": "Tata Consultancy Services Limited",
        "sector": "Information Technology",
        "industry": "IT Services",
        "about": "TCS is a global leader in IT services.",
        "source_name": "Screener.in",
        "source_url": "https://www.screener.in/company/TCS/consolidated/",
        "statement_type": "consolidated",
        "fetched_at": "2026-08-30T12:00:00Z",
        "ratios": {
            "market_cap_cr": 1500000.0, "current_price": 4000.0, "high_low": "4200 / 3500",
            "stock_pe": 30.0, "book_value": 300.0, "dividend_yield_pct": 1.5,
            "roce_pct": 50.0, "roe_pct": 45.0, "face_value": 1.0
        },
        "quarters": {
            "periods": ["Jun 2026"],
            "rows": [{"metric": "Sales", "values": {"Jun 2026": 72275.0}}]
        },
        "profit_loss": {
            "periods": ["Mar 2026"],
            "rows": [{"metric": "Sales", "values": {"Mar 2026": 280000.0}}]
        },
        "balance_sheet": {"periods": ["Mar 2026"], "rows": [{"metric": "Fixed Assets", "values": {"Mar 2026": 30000.0}}]},
        "cash_flow": {"periods": ["Mar 2026"], "rows": [{"metric": "Cash from Operating Activity", "values": {"Mar 2026": 45000.0}}]}
    }
    
    with IsolatedTestDatabase() as test_db:
        # StockDetail integration
        detail = build_full_stock_detail(mock_stock_data)
        assert detail.verification_summary is not None
        assert detail.verification_summary.symbol == "TCS"
        assert detail.verification_summary.isin == "INE467B01029"

        # Verification endpoint with auto-run fallback
        with patch("main.fetch_stock_from_screener", return_value=mock_stock_data):
            api_res = get_stock_financial_verification("TCS")
            assert api_res.symbol == "TCS"
            assert api_res.summary.symbol == "TCS"

    print("  ✓ API endpoints and StockDetail integration verified.")

if __name__ == "__main__":
    test_authoritative_identity_ordered_lookup()
    test_ambiguous_identity_rejection()
    test_source_precedence_and_identity_upgrade()
    test_canonical_period_normalization()
    test_metric_alias_and_scale_normalization()
    test_scope_mismatch_not_comparable()
    test_deterministic_numeric_tolerance_and_discrepancy()
    test_missing_values_status()
    test_full_financial_verification_pipeline_and_persistence()
    test_api_endpoints_and_stock_detail_integration()
    print("\n🎉 ALL 10 PHASE B AUTHORITATIVE FINANCIAL VERIFICATION TESTS PASSED WITH 100% ISOLATION!")
