import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "libs"))
sys.path.insert(0, str(Path(__file__).parent))

from data_seed import SEED_STOCKS
from financial_engine import compute_financial_analytics, calculate_cagr
from projection_engine import run_projections
from ranking_engine import compute_stock_score
from models import ProjectionAssumption

def test_cagr_math():
    cagr = calculate_cagr(100, 200, 3)
    assert cagr is not None
    assert round(cagr, 1) == 26.0
    print("✓ CAGR math verified.")

def test_seed_stocks_integrity():
    assert len(SEED_STOCKS) == 10
    for sym, data in SEED_STOCKS.items():
        assert data["symbol"] == sym
        assert len(data["quarters"].periods) >= 8
        assert len(data["profit_loss"].periods) >= 8
        assert len(data["balance_sheet"].periods) >= 6
        assert len(data["cash_flow"].periods) >= 6
        assert len(data["concall_insights"]) >= 1
    print("✓ All 10 Top Indian Company seed datasets structurally validated.")

def test_financial_analytics():
    rel = SEED_STOCKS["RELIANCE"]
    analytics = compute_financial_analytics(rel["quarters"], rel["profit_loss"], rel["balance_sheet"], rel["cash_flow"])
    assert "quarterly_analysis" in analytics
    assert "cash_flow_quality" in analytics
    assert "balance_sheet_efficiency" in analytics
    assert analytics["cash_flow_quality"]["cfo_to_pat_5yr_pct"] > 50.0
    print("✓ Financial analytics calculation verified.")

def test_projections_and_dcf():
    tcs = SEED_STOCKS["TCS"]
    assumptions = ProjectionAssumption(
        revenue_growth_rate_pct=14.0,
        target_opm_pct=27.0,
        capex_pct_of_sales=2.0,
        target_exit_pe=30.0
    )
    result = run_projections(tcs["ratios"], tcs["profit_loss"], tcs["balance_sheet"], tcs["cash_flow"], assumptions=assumptions)
    assert len(result.projections) == 5
    assert result.dcf_fair_value_per_share > 0
    assert result.target_price_exit_pe > 0
    assert result.projected_3yr_irr_cagr_pct > 0
    print("✓ Projection and DCF Valuation models verified.")

def test_ranking_engine():
    scores = []
    for sym, data in SEED_STOCKS.items():
        analytics = compute_financial_analytics(data["quarters"], data["profit_loss"], data["balance_sheet"], data["cash_flow"])
        projection = run_projections(data["ratios"], data["profit_loss"], data["balance_sheet"], data["cash_flow"])
        score = compute_stock_score(sym, data["name"], data["ratios"], analytics, projection, sector=data.get("sector", ""))
        assert 0 <= score.total_composite_score <= 100
        assert len(score.investment_thesis) > 10
        assert len(score.key_catalysts) >= 1
        assert len(score.key_risks) >= 1
        scores.append((sym, score.total_composite_score, score.verdict))
    
    scores.sort(key=lambda x: x[1], reverse=True)
    print("✓ Ranking engine scored all universe stocks successfully:")
    for s in scores:
        print(f"   - {s[0]}: Score {s[1]}/100 -> {s[2]}")

if __name__ == "__main__":
    print("Running Stocker Test Suite...")
    test_cagr_math()
    test_seed_stocks_integrity()
    test_financial_analytics()
    test_projections_and_dcf()
    test_ranking_engine()
    print("\nALL 5 AUTOMATED TESTS PASSED!")

