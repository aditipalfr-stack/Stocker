import sys
import os
import json
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent / "libs"))
sys.path.insert(0, str(Path(__file__).parent))

from scraper import (
    fetch_stock_from_screener, clean_metric_name, parse_num,
    CACHE_FILE, CACHE_TTL_SECONDS
)
from financial_engine import compute_financial_analytics, calculate_cagr
from projection_engine import run_projections
from ranking_engine import compute_stock_score
from models import ProjectionAssumption

def test_parsing_helpers():
    print("Testing parser helpers...")
    assert parse_num("1,123,055") == 1123055.0
    assert parse_num("(64,706)") == -64706.0
    assert parse_num("-150.5") == -150.5
    assert parse_num("18%") == 18.0
    assert parse_num("₹ 2,920") == 2920.0
    # Missing values must be None
    assert parse_num("") is None
    assert parse_num("-") is None
    assert parse_num("--") is None
    assert parse_num("N/A") is None
    assert parse_num(None) is None
    
    # Metric label cleaning
    assert clean_metric_name("Sales\xa0+") == "Sales"
    assert clean_metric_name("Expenses\xa0+") == "Expenses"
    assert clean_metric_name("Borrowings +") == "Borrowings"
    assert clean_metric_name("Cash from Operating Activity\xa0+") == "Cash from Operating Activity"
    print("✓ Parser helpers and honest null handling verified.")

def test_live_screener_extraction():
    print("\nTesting live Screener.in extraction for test companies...")
    test_symbols = ["RELIANCE", "TCS", "INFY", "LT", "ITC", "HINDUNILVR", "TATAMOTORS"]
    
    for sym in test_symbols:
        print(f"  Fetching {sym} live from Screener.in...")
        stock = fetch_stock_from_screener(sym, force_refresh=True)
        assert stock is not None, f"Failed to fetch {sym} from Screener"
        assert stock["source_name"] == "Screener.in"
        assert stock["statement_type"] in ("consolidated", "standalone")
        assert len(stock["quarters"].periods) >= 6
        assert len(stock["profit_loss"].periods) >= 6
        assert len(stock["balance_sheet"].periods) >= 6
        assert len(stock["cash_flow"].periods) >= 6
        
        # Verify non-empty data in statements
        latest_q = stock["quarters"].periods[-1]
        sales_row = next((r for r in stock["quarters"].rows if r.metric.lower() in ("sales", "revenue")), None)
        assert sales_row is not None, f"Missing Sales row for {sym}"
        assert sales_row.values.get(latest_q) is not None, f"Missing latest quarter sales for {sym}"
        
        latest_bs = stock["balance_sheet"].periods[-1]
        assets_row = next((r for r in stock["balance_sheet"].rows if r.metric.lower() == "total assets"), None)
        assert assets_row is not None, f"Missing Total Assets for {sym}"
        assert assets_row.values.get(latest_bs) is not None, f"Missing latest Total Assets for {sym}"
        
        print(f"    ✓ {sym}: {stock['name']} | Statement: {stock['statement_type']} | Latest Q: {latest_q} (Sales: ₹{sales_row.values[latest_q]:,.0f} Cr) | Latest BS: {latest_bs} (Assets: ₹{assets_row.values[latest_bs]:,.0f} Cr)")

def test_cache_freshness():
    print("\nTesting cache freshness and force_refresh...")
    # Scrape TCS with force refresh
    stock_fresh = fetch_stock_from_screener("TCS", force_refresh=True)
    assert stock_fresh is not None
    
    # Read cache file
    assert os.path.exists(CACHE_FILE)
    with open(CACHE_FILE, "r") as f:
        cache = json.load(f)
    assert "TCS" in cache
    assert "fetched_at" in cache["TCS"]
    assert cache["TCS"]["source_name"] == "Screener.in"
    
    # Subsequent call without force_refresh hits cache
    stock_cached = fetch_stock_from_screener("TCS", force_refresh=False)
    assert stock_cached is not None
    assert stock_cached["symbol"] == "TCS"
    print("✓ Cache storage and freshness verification passed.")

def test_financial_engine_on_live_data():
    print("\nTesting financial engine and DCF on live Screener data...")
    rel = fetch_stock_from_screener("RELIANCE")
    assert rel is not None
    
    analytics = compute_financial_analytics(rel["quarters"], rel["profit_loss"], rel["balance_sheet"], rel["cash_flow"])
    assert "quarterly_analysis" in analytics
    assert "cash_flow_quality" in analytics
    assert "balance_sheet_efficiency" in analytics
    
    projection = run_projections(rel["ratios"], rel["profit_loss"], rel["balance_sheet"], rel["cash_flow"])
    assert len(projection.projections) == 5
    assert projection.dcf_fair_value_per_share > 0
    
    score = compute_stock_score(rel["symbol"], rel["name"], rel["ratios"], analytics, projection, sector=rel["sector"])
    assert 0 <= score.total_composite_score <= 100
    print(f"✓ Reliance Live Analytics: Score={score.total_composite_score}/100, Verdict={score.verdict}, DCF Upside={projection.dcf_upside_pct}%")

if __name__ == "__main__":
    print("==================================================")
    print("   STOCKER SCREENER RAW DATA TEST SUITE           ")
    print("==================================================")
    test_parsing_helpers()
    test_live_screener_extraction()
    test_cache_freshness()
    test_financial_engine_on_live_data()
    print("\n🎉 ALL TESTS PASSED! Screener live ingestion verified.")
