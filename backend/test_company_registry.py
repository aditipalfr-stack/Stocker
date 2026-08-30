import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "libs"))
sys.path.insert(0, str(Path(__file__).parent))

import database
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

def test_registry_schema_and_seed_population():
    print("Testing Company Registry Schema & Seed Population...")
    database.init_db()
    
    # 1. Verify table exists
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

    # 2. Seed registry and test idempotency
    inserted_first = database.seed_company_registry()
    inserted_second = database.seed_company_registry()
    assert inserted_second == 0, "Second seed run must be idempotent (0 duplicate insertions)!"
    
    # 3. Check anchor universe presence
    universe_syms = database.get_universe_symbols(active_only=True)
    for sym in DEFAULT_UNIVERSE_SYMBOLS:
        assert sym in universe_syms, f"Anchor symbol {sym} must be present in active universe!"
        
    print("  ✓ Registry schema and idempotent seed population verified.")

def test_canonical_symbol_normalization():
    print("Testing Canonical Symbol Normalization & Aliases...")
    assert normalize_symbol("RELIANCE.NS") == "RELIANCE"
    assert normalize_symbol("tcs.bo") == "TCS"
    assert normalize_symbol("infy:nse") == "INFY"
    assert normalize_symbol("TATAMOTORS-EQ") == "TATAMOTORS"
    assert normalize_symbol("TMPV") == "TATAMOTORS"
    assert normalize_symbol("HUL") == "HINDUNILVR"
    assert normalize_symbol("RIL") == "RELIANCE"
    assert normalize_symbol("TISCO") == "TATASTEEL"
    assert normalize_symbol("L&T") == "LT"
    assert normalize_symbol("airtel") == "BHARTIARTL"
    
    assert extract_symbol_from_url_slug("/company/BHARTIARTL/consolidated/") == "BHARTIARTL"
    assert extract_symbol_from_url_slug("/company/ZOMATO/") == "ZOMATO"
    print("  ✓ Canonical symbol normalization verified.")

def test_company_search_ranking():
    print("Testing Company Search Ranking & Scoring Precedence...")
    
    # 1. Exact Symbol match should rank highest (score 100)
    infy_res = resolve_and_search_companies("INFY", limit=5)
    assert len(infy_res) > 0
    assert infy_res[0]["symbol"] == "INFY"
    assert infy_res[0]["match_score"] == 100
    
    # Case insensitivity
    infy_lower = resolve_and_search_companies("infy", limit=5)
    assert infy_lower[0]["symbol"] == "INFY"
    assert infy_lower[0]["match_score"] == 100

    # 2. Exact Company Name match (score 90)
    rel_res = resolve_and_search_companies("Reliance Industries Limited", limit=5)
    assert len(rel_res) > 0
    assert rel_res[0]["symbol"] == "RELIANCE"
    assert rel_res[0]["match_score"] == 90

    # 3. Symbol Prefix match (score 80)
    tata_res = resolve_and_search_companies("TATA", limit=5)
    assert len(tata_res) >= 2
    tata_syms = [r["symbol"] for r in tata_res]
    assert "TATAMOTORS" in tata_syms
    assert "TATASTEEL" in tata_syms

    # 4. Exact Alias match (score 75)
    hul_res = resolve_and_search_companies("HUL", limit=5)
    assert len(hul_res) > 0
    assert hul_res[0]["symbol"] == "HINDUNILVR"
    assert hul_res[0]["match_score"] >= 75

    # 5. Partial Name match (score 65-70)
    lt_res = resolve_and_search_companies("Larsen", limit=5)
    assert len(lt_res) > 0
    assert lt_res[0]["symbol"] == "LT"
    
    print("  ✓ Multi-tier search ranking precedence verified.")

def test_external_discovery_fallback():
    print("Testing External Discovery Fallback (Screener Company Search)...")
    
    mock_screener_response = [
        {
            "id": 15474,
            "name": "Zomato Ltd.",
            "url": "/company/ZOMATO/"
        },
        {
            "id": 3365,
            "name": "Bharti Airtel Ltd.",
            "url": "/company/BHARTIARTL/consolidated/"
        }
    ]
    
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_screener_response
    
    with patch("requests.get", return_value=mock_resp):
        candidates = search_screener_company_discovery("Zomato")
        assert len(candidates) >= 1
        assert candidates[0]["symbol"] == "ZOMATO"
        assert candidates[0]["company_name"] == "Zomato Ltd."
        assert candidates[0]["source"] == "screener_search"
        
        # End-to-end resolver with external search fallback
        results = resolve_and_search_companies("Zomato", limit=5)
        assert len(results) >= 1
        assert any(r["symbol"] == "ZOMATO" for r in results)
        
    print("  ✓ External discovery fallback verified.")

def test_duplicate_prevention_and_case_insensitivity():
    print("Testing Duplicate Prevention & Case-Insensitive Uniqueness...")
    
    # Insert initial item
    database.upsert_company_registry_item({
        "symbol": "DMART",
        "company_name": "Avenue Supermarts Limited",
        "nse_symbol": "DMART",
        "bse_code": "540376",
        "sector": "Retail",
        "industry": "Hypermarkets",
        "in_universe": True,
        "is_active": True
    })
    
    # Try inserting lowercase / alias variant
    database.upsert_company_registry_item({
        "symbol": "dmart",
        "company_name": "Avenue Supermarts Limited (DMart)",
        "nse_symbol": "DMART",
        "bse_code": "540376",
        "sector": "Retail",
        "industry": "Hypermarkets & Supermarkets",
        "in_universe": True,
        "is_active": True
    })
    
    conn = database.get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as cnt FROM company_registry WHERE symbol = 'DMART' COLLATE NOCASE")
        row = cur.fetchone()
        assert row["cnt"] == 1, "There must be exactly 1 row for DMART (no duplicates allowed)!"
    finally:
        conn.close()
        
    fetched = database.get_company_by_symbol("dmart")
    assert fetched is not None
    assert fetched["symbol"] == "DMART"
    assert fetched["industry"] == "Hypermarkets & Supermarkets"
    print("  ✓ Duplicate prevention and case-insensitive uniqueness verified.")

def test_add_company_flow_and_idempotency():
    print("Testing Add Company Flow & Universe Idempotency...")
    from main import execute_add_company_to_universe
    
    # Ensure WIPRO is not present before starting add test
    conn = database.get_db_connection()
    try:
        with conn:
            conn.execute("DELETE FROM company_registry WHERE symbol = 'WIPRO' COLLATE NOCASE")
    finally:
        conn.close()
    
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

def test_universe_active_toggle():
    print("Testing Universe Active/Inactive Toggle...")
    assert database.set_company_universe_status("WIPRO", in_universe=False, is_active=False) is True
    assert "WIPRO" not in database.get_universe_symbols(active_only=True)
    assert "WIPRO" in database.get_universe_symbols(active_only=False)
    
    assert database.set_company_universe_status("WIPRO", in_universe=True, is_active=True) is True
    assert "WIPRO" in database.get_universe_symbols(active_only=True)
    print("  ✓ Universe active/inactive toggle verified.")

def test_api_stocks_universe_integration():
    print("Testing /api/stocks Universe Integration...")
    from main import get_all_stocks
    
    stocks = get_all_stocks()
    assert len(stocks) >= 10
    symbols = [s.symbol for s in stocks]
    for sym in DEFAULT_UNIVERSE_SYMBOLS:
        assert sym in symbols, f"{sym} must be present in get_all_stocks output!"
        
    print("  ✓ /api/stocks dynamic universe integration verified.")

if __name__ == "__main__":
    test_registry_schema_and_seed_population()
    test_canonical_symbol_normalization()
    test_company_search_ranking()
    test_external_discovery_fallback()
    test_duplicate_prevention_and_case_insensitivity()
    test_add_company_flow_and_idempotency()
    test_universe_active_toggle()
    test_api_stocks_universe_integration()
    print("\n🎉 ALL COMPANY REGISTRY & DISCOVERY (PHASE A) TESTS PASSED PERFECTLY!")
