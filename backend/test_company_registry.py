"""
=============================================================================
Stocker V3 Phase A: Company Registry & Search Unit & Integration Test Suite
=============================================================================
Fully isolated, deterministic test suite:
- Runs against an isolated temporary SQLite database
- Mocks external Screener discovery and financial ingestion
- Zero mutations to development stocker.db or production cache files
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
import company_resolver
from data_seed import SEED_REGISTRY_COMPANIES, DEFAULT_UNIVERSE_SYMBOLS
from company_resolver import (
    normalize_symbol, clean_company_name, extract_symbol_from_url_slug,
    calculate_match_score, search_screener_company_discovery,
    resolve_and_search_companies, resolve_canonical_company
)
from models import (
    CompanyRegistryItem, CompanySearchResult, CompanySearchResponse,
    AddCompanyResponse
)

# Helper fixture for isolated test database
class IsolatedTestDatabase:
    def __enter__(self):
        self.temp_dir = tempfile.mkdtemp(prefix="stocker_test_")
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

def test_registry_schema_and_seed_population():
    print("1. Testing Company Registry Schema & Idempotent Seed Population...")
    with IsolatedTestDatabase() as test_db:
        conn = database.get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(company_registry);")
            columns = {r["name"]: r["type"] for r in cur.fetchall()}
            required_cols = [
                "id", "symbol", "company_name", "nse_symbol", "bse_code",
                "isin", "exchange", "sector", "industry", "aliases",
                "is_active", "in_universe", "source", "source_last_verified_at",
                "created_at", "updated_at"
            ]
            for col in required_cols:
                assert col in columns, f"Column '{col}' must exist in company_registry table!"
        finally:
            conn.close()

        # Seed idempotency: running seed again should insert 0 new duplicate records
        inserted_again = database.seed_company_registry()
        assert inserted_again == 0, "Second seed run must be idempotent (0 insertions)!"
        
        # Verify 10 anchor companies are seeded
        universe_syms = database.get_universe_symbols(active_only=True)
        for sym in DEFAULT_UNIVERSE_SYMBOLS:
            assert sym in universe_syms, f"Anchor symbol {sym} must be present in active universe!"
            
    print("  ✓ Registry schema and idempotent seed population verified.")

def test_seed_preserves_user_removal():
    print("2. Testing Seed Logic Preserves User Inactive/Removed Status...")
    with IsolatedTestDatabase() as test_db:
        # User explicitly removes a company from universe
        assert database.set_company_universe_status("RELIANCE", in_universe=False, is_active=True) is True
        
        rel_before = database.get_company_by_symbol("RELIANCE")
        assert rel_before["in_universe"] is False
        assert "RELIANCE" not in database.get_universe_symbols(active_only=True)
        
        # Re-running init_db() and seed_company_registry() must NOT re-enable RELIANCE
        database.seed_company_registry()
        database.init_db()
        
        rel_after = database.get_company_by_symbol("RELIANCE")
        assert rel_after["in_universe"] is False, "Seed must NEVER re-enable in_universe if set to False by user!"
        assert "RELIANCE" not in database.get_universe_symbols(active_only=True)
        
    print("  ✓ User universe removals preserved across re-seeding.")

def test_canonical_symbol_normalization_without_silent_rewrites():
    print("3. Testing Canonical Symbol Normalization (No Silent Security Rewrites)...")
    # Clean exchange suffixes
    assert normalize_symbol("RELIANCE.NS") == "RELIANCE"
    assert normalize_symbol("tcs.bo") == "TCS"
    assert normalize_symbol("infy:nse") == "INFY"
    assert normalize_symbol("TATAMOTORS-EQ") == "TATAMOTORS"
    assert normalize_symbol(" ITC ") == "ITC"
    
    # Aliases must NOT silently rewrite raw ticker symbols into other securities
    assert normalize_symbol("TMPV") == "TMPV", "normalize_symbol must not silently rewrite distinct ticker symbols!"
    assert normalize_symbol("RIL") == "RIL"
    assert normalize_symbol("HUL") == "HUL"
    
    # URL slug extraction
    assert extract_symbol_from_url_slug("/company/BHARTIARTL/consolidated/") == "BHARTIARTL"
    assert extract_symbol_from_url_slug("/company/ZOMATO/") == "ZOMATO"
    print("  ✓ Symbol normalization cleans tickers without fabricating security identity.")

def test_company_search_ranking_and_alias_expansion():
    print("4. Testing Multi-Tier Search Ranking & Search Query Aliases...")
    with IsolatedTestDatabase() as test_db:
        # 1. Exact Symbol match -> Score 100
        infy_res = resolve_and_search_companies("INFY", limit=5)
        assert len(infy_res) > 0
        assert infy_res[0]["symbol"] == "INFY"
        assert infy_res[0]["match_score"] == 100
        
        # Case-insensitivity
        infy_lower = resolve_and_search_companies("infy", limit=5)
        assert infy_lower[0]["symbol"] == "INFY"
        assert infy_lower[0]["match_score"] == 100

        # 2. Exact Company Name match -> Score 90
        rel_res = resolve_and_search_companies("Reliance Industries Limited", limit=5)
        assert len(rel_res) > 0
        assert rel_res[0]["symbol"] == "RELIANCE"
        assert rel_res[0]["match_score"] == 90

        # 3. Symbol Prefix match -> Score 80
        tata_res = resolve_and_search_companies("TATA", limit=5)
        assert len(tata_res) >= 2
        tata_syms = [r["symbol"] for r in tata_res]
        assert "TATAMOTORS" in tata_syms
        assert "TATASTEEL" in tata_syms

        # 4. Search Query Alias match (e.g. 'RIL' -> RELIANCE, 'HUL' -> HINDUNILVR) -> Score 75
        ril_res = resolve_and_search_companies("RIL", limit=5)
        assert len(ril_res) > 0
        assert ril_res[0]["symbol"] == "RELIANCE"
        assert ril_res[0]["match_score"] >= 75

        hul_res = resolve_and_search_companies("HUL", limit=5)
        assert len(hul_res) > 0
        assert hul_res[0]["symbol"] == "HINDUNILVR"
        assert hul_res[0]["match_score"] >= 75

        # 5. Partial Name match
        lt_res = resolve_and_search_companies("Larsen", limit=5)
        assert len(lt_res) > 0
        assert lt_res[0]["symbol"] == "LT"
        
    print("  ✓ Search ranking and search query alias expansion verified.")

def test_screener_discovery_does_not_fabricate_exchange_identity():
    print("5. Testing Screener Discovery Does NOT Fabricate Exchange Identity (NSE/BSE/ISIN)...")
    mock_screener_response = [
        {
            "id": 15474, # Internal Screener database ID
            "name": "Zomato Ltd.",
            "url": "/company/ZOMATO/"
        },
        {
            "id": 3365,
            "name": "Bharti Airtel Ltd.",
            "url": "/company/BHARTIARTL/consolidated/"
        },
        {
            "id": 500325,
            "name": "Reliance Industries Limited",
            "url": "/company/500325/"
        }
    ]
    
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_screener_response
    
    with patch("requests.get", return_value=mock_resp):
        # A. Screener discovery with numeric BSE-like URL slug
        candidates_numeric = search_screener_company_discovery("500325")
        cand_500325 = next(c for c in candidates_numeric if c["symbol"] == "500325")
        assert cand_500325["symbol"] == "500325"
        assert cand_500325["nse_symbol"] is None, "Numeric Screener slug must NOT become nse_symbol!"
        assert cand_500325["bse_code"] is None, "Screener internal id must NOT be mapped to bse_code!"
        assert cand_500325["isin"] is None, "ISIN must remain None until verified!"
        assert cand_500325["exchange"] is None, "exchange must remain None for unverified discovery!"
        assert cand_500325["source"] == "screener_search"

        # B. Screener discovery with normal ticker-looking URL slug (BHARTIARTL)
        candidates_ticker = search_screener_company_discovery("Bharti Airtel")
        cand_bharti = next(c for c in candidates_ticker if c["symbol"] == "BHARTIARTL")
        assert cand_bharti["symbol"] == "BHARTIARTL"
        assert cand_bharti["nse_symbol"] is None, "Discovered symbol must NOT imply verified nse_symbol!"
        assert cand_bharti["bse_code"] is None
        assert cand_bharti["isin"] is None
        assert cand_bharti["exchange"] is None, "exchange must remain None for unverified discovery!"
        assert cand_bharti["source"] == "screener_search"
        
    print("  ✓ Screener discovery provenance and unverified null exchange identity verified.")

def test_canonical_duplicate_prevention_with_precedence():
    print("6. Testing Canonical Duplicate Prevention & Precedence Merge...")
    with IsolatedTestDatabase() as test_db:
        # Initial insert for RELIANCE with basic symbol
        database.upsert_company_registry_item({
            "symbol": "RELIANCE",
            "company_name": "Reliance Industries Limited",
            "nse_symbol": "RELIANCE",
            "bse_code": None,
            "isin": None,
            "exchange": "NSE",
            "sector": "Energy",
            "industry": "Oil & Gas"
        })
        
        # 1. Duplicate ticker attempt with exchange suffix (.NS)
        database.upsert_company_registry_item({
            "symbol": "RELIANCE.NS",
            "company_name": "Reliance Industries Ltd (NSE)",
            "nse_symbol": "RELIANCE",
            "exchange": "NSE",
            "sector": "Energy & Petrochemicals"
        })
        
        conn = database.get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) as cnt FROM company_registry WHERE symbol = 'RELIANCE' COLLATE NOCASE")
            assert cur.fetchone()["cnt"] == 1, "RELIANCE.NS must merge into existing RELIANCE row!"
        finally:
            conn.close()

        # 2. Update with official BSE code and ISIN
        database.upsert_company_registry_item({
            "symbol": "RELIANCE",
            "company_name": "Reliance Industries Limited",
            "nse_symbol": "RELIANCE",
            "bse_code": "500325",
            "isin": "INE002A01018",
            "exchange": "NSE",
            "aliases": ["RIL", "Jio", "Reliance"]
        })
        
        # 3. Lookup by ISIN must find the exact same record
        by_isin = database.find_existing_company_row(
            database.get_db_connection(),
            isin="INE002A01018"
        )
        assert by_isin is not None
        assert by_isin["symbol"] == "RELIANCE"
        assert by_isin["bse_code"] == "500325"
        
        # 4. Lookup by BSE code must find the exact same record
        by_bse = database.find_existing_company_row(
            database.get_db_connection(),
            bse_code="500325"
        )
        assert by_bse is not None
        assert by_bse["symbol"] == "RELIANCE"

    print("  ✓ Canonical deduplication and identity precedence merge verified.")

def test_unresolved_manual_input_safety():
    print("7. Testing Unresolved Manual Input Candidate Safety (Condition C)...")
    with IsolatedTestDatabase() as test_db:
        # C. Unresolved manual input XYZUNKNOWN_CO
        candidate = resolve_canonical_company("XYZUNKNOWN_CO")
        assert candidate is not None
        assert candidate["symbol"] == "XYZUNKNOWN_CO"
        assert candidate["nse_symbol"] is None, "Manual unresolved candidate must have nse_symbol=None!"
        assert candidate["bse_code"] is None, "Manual unresolved candidate must have bse_code=None!"
        assert candidate["isin"] is None, "Manual unresolved candidate must have isin=None!"
        assert candidate["exchange"] is None, "Manual unresolved candidate must have exchange=None!"
        assert candidate["sector"] is None
        assert candidate["industry"] is None
        assert candidate["source"] == "unresolved_input"
        
        # Verified Seed Companies retain authoritative exchange metadata
        rel_seed = database.get_company_by_symbol("RELIANCE")
        assert rel_seed["exchange"] == "NSE", "Seeded verified records must keep real exchange metadata!"
        assert rel_seed["nse_symbol"] == "RELIANCE"
        assert rel_seed["bse_code"] == "500325"
        assert rel_seed["isin"] == "INE002A01018"
        assert rel_seed["source"] == "seed"

    print("  ✓ Unresolved manual inputs remain unverified while seeded records retain verified metadata.")

def test_add_company_flow_and_idempotency():
    print("8. Testing Add Company Flow & Universe Idempotency...")
    from main import execute_add_company_to_universe
    
    mock_stock_data = {
        "symbol": "WIPRO",
        "name": "Wipro Limited",
        "sector": "Information Technology",
        "industry": "IT Services",
        "about": "Wipro Limited is a global technology services company.",
        "source_name": "Screener.in",
        "source_url": "https://www.screener.in/company/WIPRO/consolidated/",
        "statement_type": "consolidated",
        "fetched_at": "2026-08-30T12:00:00Z",
        "ratios": {
            "market_cap_cr": 250000.0, "current_price": 500.0, "high_low": "550 / 400",
            "stock_pe": 22.0, "book_value": 150.0, "dividend_yield_pct": 1.2,
            "roce_pct": 18.0, "roe_pct": 16.0, "face_value": 2.0
        },
        "quarters": {"periods": ["Jun 2026"], "rows": [{"metric": "Sales", "values": {"Jun 2026": 22000.0}}]},
        "profit_loss": {"periods": ["Mar 2026"], "rows": [{"metric": "Sales", "values": {"Mar 2026": 89000.0}}]},
        "balance_sheet": {"periods": ["Mar 2026"], "rows": [{"metric": "Fixed Assets", "values": {"Mar 2026": 15000.0}}]},
        "cash_flow": {"periods": ["Mar 2026"], "rows": [{"metric": "Cash from Operating Activity", "values": {"Mar 2026": 14000.0}}]}
    }
    
    with IsolatedTestDatabase() as test_db:
        with patch("main.fetch_stock_from_screener", return_value=mock_stock_data):
            # 1. First Add
            res1 = execute_add_company_to_universe("WIPRO")
            assert res1.success is True
            assert res1.symbol == "WIPRO"
            assert res1.already_existed is False
            assert "Successfully added" in res1.message
            
            # Verify in universe
            assert "WIPRO" in database.get_universe_symbols(active_only=True)
            
            # 2. Second Add (Idempotent Refresh)
            res2 = execute_add_company_to_universe("WIPRO")
            assert res2.success is True
            assert res2.symbol == "WIPRO"
            assert res2.already_existed is True
            assert "Successfully refreshed" in res2.message
            
    print("  ✓ Add company flow and idempotency verified.")

def test_api_stocks_excludes_inactive_cached_companies():
    print("9. Testing /api/stocks Excludes Inactive Cached Companies...")
    from main import get_all_stocks
    
    with IsolatedTestDatabase() as test_db:
        # Mock fetch_stock_from_screener for all active stocks
        mock_stock_factory = lambda sym, **kwargs: {
            "symbol": sym,
            "name": f"{sym} Limited",
            "sector": "Diversified",
            "industry": "Indian Equities",
            "about": f"{sym} is listed on NSE.",
            "source_name": "Screener.in",
            "source_url": f"https://www.screener.in/company/{sym}/",
            "statement_type": "consolidated",
            "fetched_at": "2026-08-30T12:00:00Z",
            "ratios": {
                "market_cap_cr": 100000.0, "current_price": 1000.0, "high_low": "1100 / 900",
                "stock_pe": 20.0, "book_value": 300.0, "dividend_yield_pct": 1.0,
                "roce_pct": 15.0, "roe_pct": 15.0, "face_value": 1.0
            },
            "quarters": {"periods": ["Jun 2026"], "rows": [{"metric": "Sales", "values": {"Jun 2026": 10000.0}}]},
            "profit_loss": {"periods": ["Mar 2026"], "rows": [{"metric": "Sales", "values": {"Mar 2026": 40000.0}}]},
            "balance_sheet": {"periods": ["Mar 2026"], "rows": [{"metric": "Fixed Assets", "values": {"Mar 2026": 10000.0}}]},
            "cash_flow": {"periods": ["Mar 2026"], "rows": [{"metric": "Cash from Operating Activity", "values": {"Mar 2026": 5000.0}}]}
        }
        
        # Mark INFY as in_universe = False
        database.set_company_universe_status("INFY", in_universe=False, is_active=True)
        
        with patch("main.fetch_stock_from_screener", side_effect=mock_stock_factory):
            stocks = get_all_stocks()
            stock_symbols = [s.symbol for s in stocks]
            
            # INFY must NOT be present in output
            assert "INFY" not in stock_symbols, "Inactive/removed company INFY must NOT be returned by /api/stocks!"
            # Other active anchor symbols must be present
            assert "RELIANCE" in stock_symbols
            assert "TCS" in stock_symbols
            
    print("  ✓ /api/stocks strictly respects registry universe membership without cache leakage.")

if __name__ == "__main__":
    test_registry_schema_and_seed_population()
    test_seed_preserves_user_removal()
    test_canonical_symbol_normalization_without_silent_rewrites()
    test_company_search_ranking_and_alias_expansion()
    test_screener_discovery_does_not_fabricate_exchange_identity()
    test_canonical_duplicate_prevention_with_precedence()
    test_unresolved_manual_input_safety()
    test_add_company_flow_and_idempotency()
    test_api_stocks_excludes_inactive_cached_companies()
    print("\n🎉 ALL CORRECTED PHASE A AUDIT TESTS PASSED WITH COMPLETE DB/NETWORK ISOLATION!")
