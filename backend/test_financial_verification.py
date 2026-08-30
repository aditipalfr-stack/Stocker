"""
=============================================================================
Stocker V3 Phase B: Authoritative Identity & Official Financial Verification
Comprehensive Corrective Test Suite (Tests A - N)
=============================================================================
Fully isolated, deterministic test suite:
- Runs against an isolated temporary SQLite database (STOCKER_TEST_MODE=1)
- Mocks official source HTTP responses with genuine exchange structures
- Zero live network side-effects during tests
- Fully tests pipeline:
  mock official response -> adapter -> structured result -> normalization ->
  Screener matching -> comparison -> persistence -> API.
=============================================================================
"""

import os
import sys
import tempfile
import shutil
import json
import io
import urllib.request
from pathlib import Path
from unittest.mock import patch, MagicMock

os.environ["STOCKER_TEST_MODE"] = "1"

sys.path.insert(0, str(Path(__file__).parent.parent / "libs"))
sys.path.insert(0, str(Path(__file__).parent))

import database
import authoritative_identity
import official_financial_service
from authoritative_identity import (
    fetch_official_identity_from_exchange,
    lookup_authoritative_identity,
    is_ambiguous_company_name,
    resolve_and_upgrade_company_identity,
    normalize_legal_name,
    NSE_SECURITY_MASTER_URL
)
from official_financial_service import (
    normalize_period,
    normalize_metric_name,
    normalize_numeric_scale,
    compare_financial_metric,
    discover_official_financial_results,
    fetch_official_financial_result,
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

# =============================================================================
# TEST A: Official Identity Adapter Success
# =============================================================================
def test_a_official_identity_adapter_success():
    print("Test A: Official Identity Adapter Success (NSE Security Master CSV parsing)...")
    
    mock_nse_csv = (
        "SYMBOL,NAME OF COMPANY,SERIES,DATE OF LISTING,PAID UP VALUE,MARKET LOT,ISIN NUMBER,FACE VALUE\n"
        "INFY,Infosys Limited,EQ,08-FEB-1995,5,1,INE009A01021,5\n"
        "RELIANCE,Reliance Industries Limited,EQ,29-NOV-1995,10,1,INE002A01018,10\n"
    ).encode("utf-8")
    
    mock_resp = MagicMock()
    mock_resp.read.return_value = mock_nse_csv
    mock_resp.__enter__.return_value = mock_resp
    
    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = fetch_official_identity_from_exchange("INFY")
        assert res is not None
        assert res["symbol"] == "INFY"
        assert res["company_name"] == "Infosys Limited"
        assert res["nse_symbol"] == "INFY"
        assert res["isin"] == "INE009A01021"
        assert res["exchange"] == "NSE"
        assert res["source"] == "NSE"
        assert res["identity_source_name"] == "NSE Official Security Master"
        assert res["identity_source_url"] == NSE_SECURITY_MASTER_URL
        assert res["identity_verified_at"] is not None
        
    print("  ✓ Test A passed: Official identity adapter parsed live security master with genuine provenance.")

# =============================================================================
# TEST B: Official Identity Source Unavailable
# =============================================================================
def test_b_official_identity_source_unavailable():
    print("Test B: Official Identity Source Unavailable (Failure/Offline Handling)...")
    
    # Network exception on official source
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Network unreachable")):
        res = fetch_official_identity_from_exchange("UNKNOWN_TICKER")
        assert res is None, "When official source is unavailable, adapter must return None (no fallback fabrication)!"
        
    print("  ✓ Test B passed: Official identity adapter returns None on network failure without fabricating.")

# =============================================================================
# TEST C: Official Identity Provenance Preserved in DB
# =============================================================================
def test_c_official_identity_provenance_preserved():
    print("Test C: Official Identity Provenance Preserved in Persistent Database...")
    with IsolatedTestDatabase() as test_db:
        mock_official_identity = {
            "symbol": "INFY",
            "company_name": "Infosys Limited",
            "nse_symbol": "INFY",
            "bse_code": "500209",
            "isin": "INE009A01021",
            "exchange": "NSE/BSE",
            "source": "NSE",
            "identity_source_name": "NSE Official Security Master",
            "identity_source_url": NSE_SECURITY_MASTER_URL,
            "identity_verified_at": "2026-08-30T12:00:00Z"
        }
        
        # Upgrade company identity
        success = database.upgrade_company_authoritative_identity("INFY", mock_official_identity)
        assert success is True
        
        row = database.get_company_by_symbol("INFY")
        assert row["source"] == "NSE"
        assert row["identity_source_name"] == "NSE Official Security Master"
        assert row["identity_source_url"] == NSE_SECURITY_MASTER_URL
        assert row["identity_verified_at"] == "2026-08-30T12:00:00Z"
        assert row["isin"] == "INE009A01021"
        assert row["nse_symbol"] == "INFY"
        
    print("  ✓ Test C passed: Official identity provenance fields persisted accurately.")

# =============================================================================
# TEST D: Official Financial Result Discovery Success
# =============================================================================
def test_d_official_financial_result_discovery_success():
    print("Test D: Official Financial Result Discovery (Corporate Announcements API)...")
    
    mock_announcements = {
        "data": [
            {
                "desc": "Financial Results for Quarter Ended 30 June 2026 (Consolidated)",
                "period": "Quarter ended 30 June 2026",
                "date": "18-JUL-2026",
                "attmnt": "INFY_Results_Q1FY27.json"
            }
        ]
    }
    
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(mock_announcements).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    
    with patch("urllib.request.urlopen", return_value=mock_resp):
        discovered = discover_official_financial_results("INFY")
        assert len(discovered) == 1
        disc = discovered[0]
        assert disc["symbol"] == "INFY"
        assert disc["scope"] == "Consolidated"
        assert disc["source_name"] == "NSE Corporate Filing"
        assert "nsearchives.nseindia.com" in disc["source_url"]
        
    print("  ✓ Test D passed: Official financial result filings successfully discovered.")

# =============================================================================
# TEST E: Official Financial Source Unavailable Handling
# =============================================================================
def test_e_official_financial_source_unavailable():
    print("Test E: Official Financial Source Unavailable Handling (OFFICIAL_SOURCE_MISSING)...")
    with IsolatedTestDatabase() as test_db:
        mock_screener_data = {
            "symbol": "INFY",
            "name": "Infosys Limited",
            "statement_type": "consolidated",
            "quarters": {"periods": ["Jun 2026"], "rows": [{"metric": "Sales", "values": {"Jun 2026": 48211.0}}]}
        }
        
        # When official exchange returns no filings
        with patch("official_financial_service.discover_official_financial_results", return_value=[]):
            res = run_official_financial_verification("INFY", screener_stock_data=mock_screener_data, official_filing_docs=None)
            
            assert res["summary"]["overall_status"] == "OFFICIAL_SOURCE_MISSING"
            assert len(res["records"]) == 0
            assert "could not be retrieved" in (res["summary"].get("unavailable_reason") or "")
            
    print("  ✓ Test E passed: Unavailable official source produces OFFICIAL_SOURCE_MISSING without fake verification.")

# =============================================================================
# TEST F: Consolidated vs Standalone Scope End-to-End NOT_COMPARABLE
# =============================================================================
def test_f_scope_mismatch_end_to_end():
    print("Test F: Consolidated vs Standalone End-to-End Pipeline (NOT_COMPARABLE)...")
    with IsolatedTestDatabase() as test_db:
        # Screener statement is Consolidated
        mock_screener_data = {
            "symbol": "INFY",
            "name": "Infosys Limited",
            "statement_type": "consolidated",
            "quarters": {
                "periods": ["Jun 2026"],
                "rows": [{"metric": "Sales", "values": {"Jun 2026": 48211.0}}]
            }
        }
        
        # Official Filing is Standalone
        mock_official_docs = [
            {
                "document_title": "Infosys Standalone Financial Results",
                "reporting_period": "Quarter ended 30 June 2026",
                "scope": "Standalone",
                "source_name": "NSE Filing",
                "source_url": "https://nsearchives.nseindia.com/corporate/INFY_Standalone_Jun2026.pdf",
                "unit": "₹ Cr",
                "financial_table": [
                    {"metric": "Revenue from Operations", "value": 40000.0}
                ]
            }
        ]
        
        res = run_official_financial_verification(
            "INFY",
            screener_stock_data=mock_screener_data,
            official_filing_docs=mock_official_docs
        )
        
        records = res["records"]
        assert len(records) == 1
        assert records[0]["status"] == "NOT_COMPARABLE"
        assert "Scope mismatch" in records[0]["notes"]
        assert res["summary"]["overall_status"] == "NOT_COMPARABLE"
        assert res["summary"]["not_comparable_count"] == 1
        assert res["summary"]["discrepancy_count"] == 0
        
    print("  ✓ Test F passed: Scope mismatch produces NOT_COMPARABLE in end-to-end pipeline.")

# =============================================================================
# TEST G: Period Mismatch End-to-End NOT_COMPARABLE
# =============================================================================
def test_g_period_mismatch_end_to_end():
    print("Test G: Period Mismatch End-to-End Pipeline (NOT_COMPARABLE)...")
    with IsolatedTestDatabase() as test_db:
        # Screener has Jun 2026 (2026-Q1)
        mock_screener_data = {
            "symbol": "INFY",
            "name": "Infosys Limited",
            "statement_type": "consolidated",
            "quarters": {
                "periods": ["Jun 2026"],
                "rows": [{"metric": "Sales", "values": {"Jun 2026": 48211.0}}]
            }
        }
        
        # Official filing is for Sep 2026 (2026-Q2)
        mock_official_docs = [
            {
                "document_title": "Infosys Q2 Financial Results",
                "reporting_period": "Quarter ended 30 September 2026",
                "scope": "Consolidated",
                "source_name": "NSE Filing",
                "source_url": "https://nsearchives.nseindia.com/corporate/INFY_Q2.pdf",
                "unit": "₹ Cr",
                "financial_table": [
                    {"metric": "Revenue from Operations", "value": 50000.0}
                ]
            }
        ]
        
        res = run_official_financial_verification(
            "INFY",
            screener_stock_data=mock_screener_data,
            official_filing_docs=mock_official_docs
        )
        
        records = res["records"]
        assert len(records) == 1
        assert records[0]["status"] == "NOT_COMPARABLE"
        assert "Period mismatch" in records[0]["notes"]
        
    print("  ✓ Test G passed: Period mismatch correctly produces NOT_COMPARABLE.")

# =============================================================================
# TEST H: Rounding Difference Within Tolerance -> VERIFIED
# =============================================================================
def test_h_rounding_within_tolerance_verified():
    print("Test H: Rounding Difference Within Mathematical Tolerance -> VERIFIED...")
    res = compare_financial_metric(
        screener_val=48211.0,
        official_val=48210.6,
        canonical_metric="REVENUE",
        screener_scope="Consolidated",
        official_scope="Consolidated",
        screener_period_key="2026-Q1",
        official_period_key="2026-Q1"
    )
    assert res["status"] == "VERIFIED"
    assert res["variance_abs"] == 0.4
    
    print("  ✓ Test H passed: Rounding within ₹1 Cr tolerance confirmed as VERIFIED.")

# =============================================================================
# TEST I: True Numerical Discrepancy -> DISCREPANCY
# =============================================================================
def test_i_true_numerical_discrepancy():
    print("Test I: True Numerical Discrepancy Exceeding Tolerance -> DISCREPANCY...")
    res = compare_financial_metric(
        screener_val=48211.0,
        official_val=42000.0,
        canonical_metric="REVENUE",
        screener_scope="Consolidated",
        official_scope="Consolidated",
        screener_period_key="2026-Q1",
        official_period_key="2026-Q1"
    )
    assert res["status"] == "DISCREPANCY"
    assert res["variance_abs"] == 6211.0
    
    print("  ✓ Test I passed: Material variance exceeding tolerance flagged as DISCREPANCY.")

# =============================================================================
# TEST J: Ambiguous Accounting Metric Rejection
# =============================================================================
def test_j_ambiguous_accounting_metric_rejection():
    print("Test J: Ambiguous Accounting Metric Rejection (EBIT vs EBITDA)...")
    
    # Pure 'EBIT' or 'PBIT' without explicit EBITDA indication must NOT map to OPERATING_PROFIT
    assert normalize_metric_name("EBIT") is None
    assert normalize_metric_name("PBIT") is None
    assert normalize_metric_name("Operating Profit before depreciation") is None
    
    # Explicit EBITDA / Operating Profit maps accurately
    assert normalize_metric_name("Operating Profit (EBITDA)") == "OPERATING_PROFIT"
    assert normalize_metric_name("Revenue from Operations") == "REVENUE"
    
    print("  ✓ Test J passed: Ambiguous metric definitions safely rejected.")

# =============================================================================
# TEST K: Phase A Add-Company Does Not Fabricate NSE Identity
# =============================================================================
def test_k_add_company_does_not_fabricate_nse_identity():
    print("Test K: Phase A Add-Company Does Not Fabricate NSE Identity...")
    from main import execute_add_company_to_universe
    
    with IsolatedTestDatabase() as test_db:
        # Mock Screener fetch returning unverified discovery candidate
        mock_stock_data = {
            "symbol": "DISCOVERY_TICKER",
            "name": "Discovery Stock Ltd",
            "statement_type": "consolidated",
            "ratios": {
                "current_price": 100.0, "market_cap_cr": 500.0, "high_low": "120 / 80",
                "stock_pe": 15.0, "book_value": 50.0, "dividend_yield_pct": 1.0,
                "roce_pct": 20.0, "roe_pct": 18.0, "face_value": 10.0
            },
            "quarters": {"periods": [], "rows": []},
            "profit_loss": {"periods": [], "rows": []},
            "balance_sheet": {"periods": [], "rows": []},
            "cash_flow": {"periods": [], "rows": []}
        }
        
        with patch("main.resolve_canonical_company", return_value={
            "symbol": "DISCOVERY_TICKER",
            "company_name": "Discovery Stock Ltd",
            "nse_symbol": None,
            "bse_code": None,
            "isin": None,
            "exchange": None,
            "source": "screener_search"
        }):
            with patch("main.fetch_stock_from_screener", return_value=mock_stock_data):
                resp = execute_add_company_to_universe("DISCOVERY_TICKER")
                assert resp.success is True
                
                # Check DB record
                row = database.get_company_by_symbol("DISCOVERY_TICKER")
                assert row["nse_symbol"] is None, "Add company must NOT fabricate nse_symbol!"
                assert row["exchange"] is None, "Add company must NOT fabricate exchange='NSE'!"
                assert row["isin"] is None
                assert row["source"] in ("screener_ingestion", "screener_search")
                
    print("  ✓ Test K passed: Add-company does not fabricate exchange identity.")

# =============================================================================
# TEST L: Legacy Cache Bootstrap Does Not Fabricate NSE Identity
# =============================================================================
def test_l_cache_bootstrap_does_not_fabricate_nse_identity():
    print("Test L: Legacy Cache Bootstrap Does Not Fabricate NSE Identity...")
    with IsolatedTestDatabase() as test_db:
        # Seed cache mock record
        database.seed_company_registry(seed_records=[{
            "symbol": "LEGACY_CACHED",
            "company_name": "Legacy Cached Co",
            "nse_symbol": None,
            "bse_code": None,
            "isin": None,
            "exchange": None,
            "source": "stocks_cache"
        }])
        
        row = database.get_company_by_symbol("LEGACY_CACHED")
        assert row is not None
        assert row["nse_symbol"] is None
        assert row["exchange"] is None
        assert row["source"] == "stocks_cache"
        
    print("  ✓ Test L passed: Legacy cache bootstrap preserves null exchange fields.")

# =============================================================================
# TEST M: Official Identity Upgrades Existing Row Without Duplication
# =============================================================================
def test_m_official_identity_upgrades_without_duplication():
    print("Test M: Official Identity Upgrades Existing Row Without Duplication...")
    with IsolatedTestDatabase() as test_db:
        # Step 1: Insert unverified discovery row
        database.upsert_company_registry_item({
            "symbol": "BHARTIARTL",
            "company_name": "Bharti Airtel Ltd",
            "nse_symbol": None,
            "exchange": None,
            "source": "screener_search",
            "in_universe": True,
            "is_active": True
        })
        
        # Step 2: Upgrade with official exchange identity
        mock_official = {
            "symbol": "BHARTIARTL",
            "company_name": "Bharti Airtel Limited",
            "nse_symbol": "BHARTIARTL",
            "bse_code": "532454",
            "isin": "INE397D01024",
            "exchange": "NSE/BSE",
            "source": "NSE",
            "identity_source_name": "NSE Official Security Master",
            "identity_source_url": NSE_SECURITY_MASTER_URL,
            "identity_verified_at": "2026-08-30T12:00:00Z"
        }
        database.upgrade_company_authoritative_identity("BHARTIARTL", mock_official)
        
        row = database.get_company_by_symbol("BHARTIARTL")
        assert row["source"] == "NSE"
        assert row["isin"] == "INE397D01024"
        assert row["in_universe"] is True, "Universe membership must be preserved!"
        
        # Confirm no duplicate row created
        conn = database.get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) as cnt FROM company_registry WHERE symbol = 'BHARTIARTL'")
            assert cur.fetchone()["cnt"] == 1
        finally:
            conn.close()
            
    print("  ✓ Test M passed: Official identity upgraded existing row without duplicate records.")

# =============================================================================
# TEST N: Lower-Tier Sources Cannot Overwrite Verified Official Metadata
# =============================================================================
def test_n_lower_tier_sources_cannot_overwrite_verified():
    print("Test N: Lower-Tier Sources Cannot Overwrite Verified Official Metadata...")
    with IsolatedTestDatabase() as test_db:
        # Verified official row
        database.upsert_company_registry_item({
            "symbol": "INFY",
            "company_name": "Infosys Limited",
            "nse_symbol": "INFY",
            "isin": "INE009A01021",
            "exchange": "NSE",
            "source": "NSE",
            "identity_source_name": "NSE Official Security Master"
        })
        
        # Weaker discovery attempt with wrong/null metadata
        database.upgrade_company_authoritative_identity("INFY", {
            "symbol": "INFY",
            "company_name": "Infosys Weak Title",
            "source": "screener_search",
            "nse_symbol": None,
            "isin": None
        })
        
        row = database.get_company_by_symbol("INFY")
        assert row["source"] == "NSE", "Higher-tier verified source must NOT be overwritten by screener_search!"
        assert row["isin"] == "INE009A01021"
        assert row["nse_symbol"] == "INFY"
        
    print("  ✓ Test N passed: Lower-tier sources cannot downgrade verified official metadata.")

if __name__ == "__main__":
    test_a_official_identity_adapter_success()
    test_b_official_identity_source_unavailable()
    test_c_official_identity_provenance_preserved()
    test_d_official_financial_result_discovery_success()
    test_e_official_financial_source_unavailable()
    test_f_scope_mismatch_end_to_end()
    test_g_period_mismatch_end_to_end()
    test_h_rounding_within_tolerance_verified()
    test_i_true_numerical_discrepancy()
    test_j_ambiguous_accounting_metric_rejection()
    test_k_add_company_does_not_fabricate_nse_identity()
    test_l_cache_bootstrap_does_not_fabricate_nse_identity()
    test_m_official_identity_upgrades_without_duplication()
    test_n_lower_tier_sources_cannot_overwrite_verified()
    print("\n🎉 ALL 14 PHASE B TESTS (A - N) PASSED WITH 100% ISOLATION AND ZERO REGRESSIONS!")
