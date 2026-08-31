"""
Stocker Phase 2B — Canonical Truth-Driven Analytics Test Suite
==============================================================

Validates all Phase 2B requirements:
- Scenario A: VERIFIED Revenue values (QoQ = 20%, quality = "verified", provenance = official)
- Scenario B: Screener standardized only (QoQ calculated, quality = "standardized")
- Scenario C: Mixed provenance (Q1 standardized + Q2 verified -> quality = "mixed")
- Scenario D: DISCREPANCY input (continuity value used, numeric output accurate, has_discrepancy = True, quality = "discrepant")
- Scenario E: SCREENER_VALUE_MISSING (canonical value None, result unavailable, no raw official substitution)
- Scenario F: Missing prior quarter (QoQ unavailable, zero nearest-quarter substitution)
- Scenario G: Missing same quarter last year (YoY unavailable)
- Scenario H: Annual verified Revenue series (3Y Sales CAGR uses canonical verified values)
- Scenario I: CFO mixed provenance (cash conversion uses canonical values, quality state correct)
- Scenario J: Debt trend with discrepancy (numeric trend + discrepancy marker)
- Scenario K: Financial refresh (analytics use refreshed canonical truth, not stale facts)
- Scenario L: Verification refresh (analytics update automatically from standardized -> verified/discrepant)
"""

import os
import sys
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

# Setup imports
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "libs"))

import database
from scraper import serialize_stock_data
from models import (
    FinancialStatement,
    FinancialRow,
    KeyRatios,
    CanonicalFinancialFact,
    FinancialTruthContainer
)
from financial_truth_service import (
    build_financial_truth_for_stock,
    get_or_recompute_financial_truth
)
from financial_engine import compute_financial_analytics
from financial_truth_resolver import TruthAwareFinancialResolver
import main

class IsolatedTestDatabase:
    """Creates a temporary isolated SQLite database for fail-closed test execution."""
    def __init__(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()

    def __enter__(self):
        os.environ["STOCKER_DB_PATH"] = self.db_path
        os.environ["STOCKER_TEST_MODE"] = "1"
        database.init_db()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except Exception:
                pass
        os.environ.pop("STOCKER_DB_PATH", None)
        os.environ.pop("STOCKER_TEST_MODE", None)

def make_sample_stock_data(symbol: str = "TESTCO", fetched_at: Optional[str] = None) -> Dict[str, Any]:
    now_iso = fetched_at or datetime.now(timezone.utc).isoformat()
    return {
        "symbol": symbol,
        "name": f"{symbol} Test Corporation Ltd",
        "sector": "Technology",
        "industry": "Software",
        "about": "Test stock for canonical truth layer analytics validation.",
        "statement_type": "consolidated",
        "source_name": "Screener.in",
        "source_url": f"https://www.screener.in/company/{symbol}/",
        "fetched_at": now_iso,
        "ratios": KeyRatios(current_price=1000.0, market_cap_cr=50000.0, stock_pe=25.0),
        "quarters": FinancialStatement(
            periods=["Jun 2025", "Sep 2025", "Dec 2025", "Mar 2026", "Jun 2026"],
            rows=[
                FinancialRow(metric="Sales", values={"Jun 2025": 1000.0, "Sep 2025": 1200.0, "Dec 2025": 1300.0, "Mar 2026": 1400.0, "Jun 2026": 1500.0}),
                FinancialRow(metric="Operating Profit", values={"Jun 2025": 200.0, "Sep 2025": 240.0, "Dec 2025": 260.0, "Mar 2026": 280.0, "Jun 2026": 300.0}),
                FinancialRow(metric="OPM %", values={"Jun 2025": 20.0, "Sep 2025": 20.0, "Dec 2025": 20.0, "Mar 2026": 20.0, "Jun 2026": 20.0}),
                FinancialRow(metric="Net Profit", values={"Jun 2025": 150.0, "Sep 2025": 180.0, "Dec 2025": 195.0, "Mar 2026": 210.0, "Jun 2026": 225.0}),
                FinancialRow(metric="EPS in Rs", values={"Jun 2025": 15.0, "Sep 2025": 18.0, "Dec 2025": 19.5, "Mar 2026": 21.0, "Jun 2026": 22.5}),
            ]
        ),
        "profit_loss": FinancialStatement(
            periods=["Mar 2023", "Mar 2024", "Mar 2025", "Mar 2026", "TTM"],
            rows=[
                FinancialRow(metric="Sales", values={"Mar 2023": 1000.0, "Mar 2024": 1100.0, "Mar 2025": 1210.0, "Mar 2026": 1331.0, "TTM": 1331.0}),
                FinancialRow(metric="Operating Profit", values={"Mar 2023": 200.0, "Mar 2024": 220.0, "Mar 2025": 242.0, "Mar 2026": 266.2, "TTM": 266.2}),
                FinancialRow(metric="Net Profit", values={"Mar 2023": 100.0, "Mar 2024": 110.0, "Mar 2025": 121.0, "Mar 2026": 133.1, "TTM": 133.1}),
                FinancialRow(metric="EPS in Rs", values={"Mar 2023": 10.0, "Mar 2024": 11.0, "Mar 2025": 12.1, "Mar 2026": 13.31, "TTM": 13.31}),
            ]
        ),
        "balance_sheet": FinancialStatement(
            periods=["Mar 2023", "Mar 2024", "Mar 2025", "Mar 2026"],
            rows=[
                FinancialRow(metric="Borrowings", values={"Mar 2023": 100.0, "Mar 2024": 90.0, "Mar 2025": 80.0, "Mar 2026": 70.0}),
                FinancialRow(metric="Fixed Assets", values={"Mar 2023": 1000.0, "Mar 2024": 1200.0, "Mar 2025": 1400.0, "Mar 2026": 1600.0}),
                FinancialRow(metric="CWIP", values={"Mar 2023": 50.0, "Mar 2024": 40.0, "Mar 2025": 30.0, "Mar 2026": 20.0}),
            ]
        ),
        "cash_flow": FinancialStatement(
            periods=["Mar 2023", "Mar 2024", "Mar 2025", "Mar 2026"],
            rows=[
                FinancialRow(metric="Cash from Operating Activity", values={"Mar 2023": 120.0, "Mar 2024": 130.0, "Mar 2025": 145.0, "Mar 2026": 160.0})
            ]
        )
    }

def run_all_tests():
    print("\n==================================================================")
    print("Running Stocker Phase 2B: Truth-Driven Analytics Test Suite")
    print("==================================================================")

    # -------------------------------------------------------------------------
    # SCENARIO A: VERIFIED Revenue Values (Q1=100, Q2=120 -> QoQ=20%, quality="verified")
    # -------------------------------------------------------------------------
    with IsolatedTestDatabase():
        print("\n--- Scenario A: VERIFIED Revenue Values ---")
        stock = make_sample_stock_data("VERIFCO")
        
        # Save verification records for Jun 2025 (2025-Q1) and Sep 2025 (2025-Q2)
        v_records = [
            {
                "symbol": "VERIFCO",
                "metric_name": "Revenue",
                "canonical_metric": "REVENUE",
                "period": "Jun 2025",
                "canonical_period": "2025-Q1",
                "scope": "Consolidated",
                "screener_value": 1000.0,
                "official_value": 1000.0,
                "unit": "₹ Cr",
                "currency": "INR",
                "status": "VERIFIED",
                "official_source_name": "NSE XBRL Filing",
                "verified_at": "2026-05-01T10:00:00Z"
            },
            {
                "symbol": "VERIFCO",
                "metric_name": "Revenue",
                "canonical_metric": "REVENUE",
                "period": "Sep 2025",
                "canonical_period": "2025-Q2",
                "scope": "Consolidated",
                "screener_value": 1200.0,
                "official_value": 1200.0,
                "unit": "₹ Cr",
                "currency": "INR",
                "status": "VERIFIED",
                "official_source_name": "NSE XBRL Filing",
                "verified_at": "2026-05-01T10:00:00Z"
            }
        ]
        database.save_financial_verification_records(v_records)
        database.save_stock_cache("VERIFCO", "Verif Co", "IT", "Software", serialize_stock_data(stock))
        
        truth = get_or_recompute_financial_truth("VERIFCO")
        analytics = compute_financial_analytics(
            quarters=stock["quarters"],
            pl=stock["profit_loss"],
            bs=stock["balance_sheet"],
            cf=stock["cash_flow"],
            symbol="VERIFCO",
            financial_truth=truth
        )
        
        # Inspect Sep 2025 quarterly trend (QoQ vs Jun 2025)
        trends = analytics["quarterly_analysis"]["trends"]
        sep_trend = next((t for t in trends if t["period"] == "Sep 2025"), None)
        assert sep_trend is not None
        assert sep_trend["sales_growth_qoq_pct"] == 20.0, f"Expected QoQ = 20.0%, got {sep_trend['sales_growth_qoq_pct']}"
        
        prov = sep_trend["provenance"]["sales_growth_qoq"]
        assert prov["quality"] == "verified", f"Expected quality = 'verified', got {prov['quality']}"
        assert prov["has_discrepancy"] is False
        assert len(prov["inputs"]) == 2
        assert all(inp["source_type"] == "official" for inp in prov["inputs"])
        print("  ✓ Scenario A passed: VERIFIED QoQ growth = 20.0% with verified quality.")

    # -------------------------------------------------------------------------
    # SCENARIO B: Screener Standardized Only
    # -------------------------------------------------------------------------
    with IsolatedTestDatabase():
        print("\n--- Scenario B: Screener Standardized Only ---")
        stock = make_sample_stock_data("STANDCO")
        database.save_stock_cache("STANDCO", "Stand Co", "IT", "Software", serialize_stock_data(stock))
        
        truth = get_or_recompute_financial_truth("STANDCO")
        analytics = compute_financial_analytics(
            quarters=stock["quarters"],
            pl=stock["profit_loss"],
            bs=stock["balance_sheet"],
            cf=stock["cash_flow"],
            symbol="STANDCO",
            financial_truth=truth
        )
        
        trends = analytics["quarterly_analysis"]["trends"]
        sep_trend = next((t for t in trends if t["period"] == "Sep 2025"), None)
        assert sep_trend is not None
        assert sep_trend["sales_growth_qoq_pct"] == 20.0
        
        prov = sep_trend["provenance"]["sales_growth_qoq"]
        assert prov["quality"] == "standardized", f"Expected quality = 'standardized', got {prov['quality']}"
        assert prov["has_discrepancy"] is False
        print("  ✓ Scenario B passed: Standardized QoQ growth calculated with standardized quality.")

    # -------------------------------------------------------------------------
    # SCENARIO C: Mixed Provenance (Q1 standardized + Q2 verified)
    # -------------------------------------------------------------------------
    with IsolatedTestDatabase():
        print("\n--- Scenario C: Mixed Provenance ---")
        stock = make_sample_stock_data("MIXCO")
        
        # Only Sep 2025 is verified; Jun 2025 is unverified standardized
        v_record = {
            "symbol": "MIXCO",
            "metric_name": "Revenue",
            "canonical_metric": "REVENUE",
            "period": "Sep 2025",
            "canonical_period": "2025-Q2",
            "scope": "Consolidated",
            "screener_value": 1200.0,
            "official_value": 1200.0,
            "unit": "₹ Cr",
            "currency": "INR",
            "status": "VERIFIED",
            "official_source_name": "NSE XBRL Filing",
            "verified_at": "2026-05-01T10:00:00Z"
        }
        database.save_financial_verification_records([v_record])
        database.save_stock_cache("MIXCO", "Mix Co", "IT", "Software", serialize_stock_data(stock))
        
        truth = get_or_recompute_financial_truth("MIXCO")
        analytics = compute_financial_analytics(
            quarters=stock["quarters"],
            pl=stock["profit_loss"],
            bs=stock["balance_sheet"],
            cf=stock["cash_flow"],
            symbol="MIXCO",
            financial_truth=truth
        )
        
        sep_trend = next((t for t in analytics["quarterly_analysis"]["trends"] if t["period"] == "Sep 2025"), None)
        assert sep_trend is not None
        assert sep_trend["sales_growth_qoq_pct"] == 20.0
        
        prov = sep_trend["provenance"]["sales_growth_qoq"]
        assert prov["quality"] == "mixed", f"Expected quality = 'mixed', got {prov['quality']}"
        assert prov["has_discrepancy"] is False
        print("  ✓ Scenario C passed: Mixed provenance correctly identified as 'mixed'.")

    # -------------------------------------------------------------------------
    # SCENARIO D: DISCREPANCY Input
    # -------------------------------------------------------------------------
    with IsolatedTestDatabase():
        print("\n--- Scenario D: DISCREPANCY Input ---")
        stock = make_sample_stock_data("DISCCO")
        
        # Sep 2025 has discrepancy: Screener=1200, Official=1400
        v_record = {
            "symbol": "DISCCO",
            "metric_name": "Revenue",
            "canonical_metric": "REVENUE",
            "period": "Sep 2025",
            "canonical_period": "2025-Q2",
            "scope": "Consolidated",
            "screener_value": 1200.0,
            "official_value": 1400.0,
            "variance_abs": 200.0,
            "variance_pct": 16.67,
            "unit": "₹ Cr",
            "currency": "INR",
            "status": "DISCREPANCY",
            "official_source_name": "BSE Filing",
            "verified_at": "2026-05-01T10:00:00Z"
        }
        database.save_financial_verification_records([v_record])
        database.save_stock_cache("DISCCO", "Disc Co", "IT", "Software", serialize_stock_data(stock))
        
        truth = get_or_recompute_financial_truth("DISCCO")
        analytics = compute_financial_analytics(
            quarters=stock["quarters"],
            pl=stock["profit_loss"],
            bs=stock["balance_sheet"],
            cf=stock["cash_flow"],
            symbol="DISCCO",
            financial_truth=truth
        )
        
        sep_trend = next((t for t in analytics["quarterly_analysis"]["trends"] if t["period"] == "Sep 2025"), None)
        assert sep_trend is not None
        # Uses continuity value 1200 vs 1000 -> 20%
        assert sep_trend["sales_growth_qoq_pct"] == 20.0
        
        prov = sep_trend["provenance"]["sales_growth_qoq"]
        assert prov["has_discrepancy"] is True, "Expected has_discrepancy = True"
        assert prov["quality"] == "discrepant", f"Expected quality = 'discrepant', got {prov['quality']}"
        print("  ✓ Scenario D passed: Discrepancy continuity calculation preserves math and propagates discrepancy marker.")

    # -------------------------------------------------------------------------
    # SCENARIO E: SCREENER_VALUE_MISSING Policy
    # -------------------------------------------------------------------------
    with IsolatedTestDatabase():
        print("\n--- Scenario E: SCREENER_VALUE_MISSING ---")
        stock = make_sample_stock_data("MISSINGCO")
        
        # Verification record for Q1 FY27 (not in Screener)
        v_record = {
            "symbol": "MISSINGCO",
            "metric_name": "Revenue",
            "canonical_metric": "REVENUE",
            "period": "Q1 FY27",
            "canonical_period": "2026-Q1",
            "scope": "Consolidated",
            "screener_value": None,
            "official_value": 1600.0,
            "status": "SCREENER_VALUE_MISSING",
            "verified_at": "2026-08-01T10:00:00Z"
        }
        database.save_financial_verification_records([v_record])
        database.save_stock_cache("MISSINGCO", "Missing Co", "IT", "Software", serialize_stock_data(stock))
        
        truth = get_or_recompute_financial_truth("MISSINGCO")
        resolver = TruthAwareFinancialResolver(symbol="MISSINGCO", financial_truth=truth, quarters=stock["quarters"])
        
        # Resolve Q1 FY27 fact
        fact = resolver.resolve_quarterly_fact("REVENUE", "Q1 FY27")
        assert fact.value is None, f"Canonical usable value must remain None for SCREENER_VALUE_MISSING, got {fact.value}"
        assert fact.source_type == "unverified"
        
        # Calculate growth against prior quarter -> must be insufficient/None
        prev_fact = resolver.resolve_quarterly_fact("REVENUE", "Jun 2026")
        growth_res = resolver.calculate_growth_with_provenance(fact, prev_fact)
        assert growth_res.value is None, f"Growth must be None when input is missing, got {growth_res.value}"
        assert growth_res.quality == "insufficient"
        print("  ✓ Scenario E passed: SCREENER_VALUE_MISSING correctly yields None without raw official substitution.")

    # -------------------------------------------------------------------------
    # SCENARIO F: Missing Prior Quarter (Zero Nearest-Quarter Fallback)
    # -------------------------------------------------------------------------
    with IsolatedTestDatabase():
        print("\n--- Scenario F: Missing Prior Quarter ---")
        stock = make_sample_stock_data("FIRSTQCO")
        # First quarter in statement has no prior quarter in list
        analytics = compute_financial_analytics(
            quarters=stock["quarters"],
            pl=stock["profit_loss"],
            bs=stock["balance_sheet"],
            cf=stock["cash_flow"],
            symbol="FIRSTQCO"
        )
        
        first_q = analytics["quarterly_analysis"]["trends"][0]
        assert first_q["sales_growth_qoq_pct"] is None, "First quarter QoQ must be None without prior quarter"
        print("  ✓ Scenario F passed: Missing prior quarter cleanly yields None without fuzzy fallback.")

    # -------------------------------------------------------------------------
    # SCENARIO G: Missing Same Quarter Last Year
    # -------------------------------------------------------------------------
    with IsolatedTestDatabase():
        print("\n--- Scenario G: Missing Same Quarter Last Year ---")
        stock = make_sample_stock_data("NOYOYCO")
        analytics = compute_financial_analytics(
            quarters=stock["quarters"],
            pl=stock["profit_loss"],
            bs=stock["balance_sheet"],
            cf=stock["cash_flow"],
            symbol="NOYOYCO"
        )
        
        # Q1 through Q3 cannot have YoY (require 4 quarters back)
        for idx in range(4):
            q_item = analytics["quarterly_analysis"]["trends"][idx]
            assert q_item["sales_growth_yoy_pct"] is None, f"Quarter {idx} YoY must be None"
        print("  ✓ Scenario G passed: Missing YoY counterpart correctly yields None.")

    # -------------------------------------------------------------------------
    # SCENARIO H: Annual Verified Revenue Series (3Y Sales CAGR)
    # -------------------------------------------------------------------------
    with IsolatedTestDatabase():
        print("\n--- Scenario H: Annual Verified Revenue Series (3Y Sales CAGR) ---")
        stock = make_sample_stock_data("CAGRCO")
        
        # FY23 Revenue = 1000, FY26 Revenue = 1331 -> 3Y CAGR = 10.0%
        v_records = [
            {
                "symbol": "CAGRCO",
                "metric_name": "Revenue",
                "canonical_metric": "REVENUE",
                "period": "FY23",
                "canonical_period": "2023-FY",
                "scope": "Consolidated",
                "screener_value": 1000.0,
                "official_value": 1000.0,
                "unit": "₹ Cr",
                "currency": "INR",
                "status": "VERIFIED",
                "verified_at": "2026-05-01T10:00:00Z"
            },
            {
                "symbol": "CAGRCO",
                "metric_name": "Revenue",
                "canonical_metric": "REVENUE",
                "period": "FY26",
                "canonical_period": "2026-FY",
                "scope": "Consolidated",
                "screener_value": 1331.0,
                "official_value": 1331.0,
                "unit": "₹ Cr",
                "currency": "INR",
                "status": "VERIFIED",
                "verified_at": "2026-05-01T10:00:00Z"
            }
        ]
        database.save_financial_verification_records(v_records)
        database.save_stock_cache("CAGRCO", "CAGR Co", "IT", "Software", serialize_stock_data(stock))
        
        truth = get_or_recompute_financial_truth("CAGRCO")
        analytics = compute_financial_analytics(
            quarters=stock["quarters"],
            pl=stock["profit_loss"],
            bs=stock["balance_sheet"],
            cf=stock["cash_flow"],
            symbol="CAGRCO",
            financial_truth=truth
        )
        
        sales_cagr = analytics["growth_rates"]["sales_cagr_3yr"]
        assert sales_cagr == 10.0, f"Expected 3Y Sales CAGR = 10.0%, got {sales_cagr}"
        
        prov = analytics["provenance"]["sales_cagr_3yr"]
        assert prov["quality"] == "verified", f"Expected quality = 'verified', got {prov['quality']}"
        assert prov["value"] == 10.0
        print("  ✓ Scenario H passed: 3Y Sales CAGR = 10.0% with verified quality.")

    # -------------------------------------------------------------------------
    # SCENARIO I: CFO Mixed Provenance & Cash Conversion
    # -------------------------------------------------------------------------
    with IsolatedTestDatabase():
        print("\n--- Scenario I: CFO Mixed Provenance ---")
        stock = make_sample_stock_data("CFOCO")
        
        # Verify CFO for FY26 only
        v_record = {
            "symbol": "CFOCO",
            "metric_name": "Cash from Operations",
            "canonical_metric": "CFO",
            "period": "FY26",
            "canonical_period": "2026-FY",
            "scope": "Consolidated",
            "screener_value": 160.0,
            "official_value": 160.0,
            "unit": "₹ Cr",
            "currency": "INR",
            "status": "VERIFIED",
            "verified_at": "2026-05-01T10:00:00Z"
        }
        database.save_financial_verification_records([v_record])
        database.save_stock_cache("CFOCO", "CFO Co", "IT", "Software", serialize_stock_data(stock))
        
        truth = get_or_recompute_financial_truth("CFOCO")
        analytics = compute_financial_analytics(
            quarters=stock["quarters"],
            pl=stock["profit_loss"],
            bs=stock["balance_sheet"],
            cf=stock["cash_flow"],
            symbol="CFOCO",
            financial_truth=truth
        )
        
        fcf_trends = analytics["cash_flow_quality"]["fcf_trends"]
        fy26_fcf = next((f for f in fcf_trends if f["period"] == "Mar 2026"), None)
        assert fy26_fcf is not None
        assert fy26_fcf["reported_cfo_cr"] == 160.0
        assert fy26_fcf["provenance"]["cfo"]["verification_status"] == "VERIFIED"
        print("  ✓ Scenario I passed: CFO mixed provenance correctly tracked in FCF trends.")

    # -------------------------------------------------------------------------
    # SCENARIO J: Debt Trend with Discrepancy
    # -------------------------------------------------------------------------
    with IsolatedTestDatabase():
        print("\n--- Scenario J: Debt Trend with Discrepancy ---")
        stock = make_sample_stock_data("DEBTCO")
        
        # FY26 Borrowings has discrepancy: Screener=70, Official=100
        v_record = {
            "symbol": "DEBTCO",
            "metric_name": "Borrowings",
            "canonical_metric": "BORROWINGS",
            "period": "FY26",
            "canonical_period": "2026-FY",
            "scope": "Consolidated",
            "screener_value": 70.0,
            "official_value": 100.0,
            "variance_abs": 30.0,
            "variance_pct": 42.86,
            "unit": "₹ Cr",
            "currency": "INR",
            "status": "DISCREPANCY",
            "verified_at": "2026-05-01T10:00:00Z"
        }
        database.save_financial_verification_records([v_record])
        database.save_stock_cache("DEBTCO", "Debt Co", "IT", "Software", serialize_stock_data(stock))
        
        truth = get_or_recompute_financial_truth("DEBTCO")
        analytics = compute_financial_analytics(
            quarters=stock["quarters"],
            pl=stock["profit_loss"],
            bs=stock["balance_sheet"],
            cf=stock["cash_flow"],
            symbol="DEBTCO",
            financial_truth=truth
        )
        
        bs_trends = analytics["balance_sheet_efficiency"]["bs_trends"]
        fy26_bs = next((b for b in bs_trends if b["period"] == "Mar 2026"), None)
        assert fy26_bs is not None
        assert fy26_bs["borrowings_cr"] == 70.0 # continuity value
        assert fy26_bs["provenance"]["borrowings"]["has_discrepancy"] is True
        assert fy26_bs["provenance"]["borrowings"]["verification_status"] == "DISCREPANCY"
        print("  ✓ Scenario J passed: Debt trend preserved numeric continuity and exposed discrepancy.")

    # -------------------------------------------------------------------------
    # SCENARIO K: Financial Refresh Invalidation
    # -------------------------------------------------------------------------
    with IsolatedTestDatabase():
        print("\n--- Scenario K: Financial Refresh Invalidation ---")
        f1_time = "2026-08-31T09:00:00Z"
        stock_f1 = make_sample_stock_data("REFINV", fetched_at=f1_time)
        database.save_stock_cache("REFINV", "Ref Inv Co", "IT", "Software", serialize_stock_data(stock_f1))
        
        # 1. First build detail
        detail1 = main.build_full_stock_detail(stock_f1)
        assert detail1.analytics["growth_rates"]["sales_cagr_3yr"] == 10.0
        
        # 2. Update stock cache with modified Sales for Mar 2026 (1400 instead of 1331)
        f2_time = "2026-08-31T11:00:00Z"
        stock_f2 = make_sample_stock_data("REFINV", fetched_at=f2_time)
        for r in stock_f2["profit_loss"].rows:
            if r.metric == "Sales":
                r.values["Mar 2026"] = 1400.0
        database.save_stock_cache("REFINV", "Ref Inv Co", "IT", "Software", serialize_stock_data(stock_f2))
        
        # 3. Build detail again without manual truth build
        detail2 = main.build_full_stock_detail(stock_f2)
        # CAGR from 1000 to 1400 over 3 years is ((1400/1000)^(1/3) - 1)*100 = 11.87%
        assert detail2.analytics["growth_rates"]["sales_cagr_3yr"] == 11.87
        assert detail2.financial_truth.input_financial_version == f2_time
        print("  ✓ Scenario K passed: Financial refresh automatically updated truth and analytics.")

    # -------------------------------------------------------------------------
    # SCENARIO L: Verification Refresh Invalidation
    # -------------------------------------------------------------------------
    with IsolatedTestDatabase():
        print("\n--- Scenario L: Verification Refresh Invalidation ---")
        stock = make_sample_stock_data("VERIFREF")
        database.save_stock_cache("VERIFREF", "Verif Ref Co", "IT", "Software", serialize_stock_data(stock))
        
        # 1. Initially unverified
        detail1 = main.build_full_stock_detail(stock)
        assert detail1.analytics["quarterly_analysis"]["trends"][1]["provenance"]["sales_growth_qoq"]["quality"] == "standardized"
        
        # 2. Verification runs and verifies Jun 2025 & Sep 2025
        v_time = "2026-08-31T12:00:00Z"
        v_records = [
            {
                "symbol": "VERIFREF",
                "metric_name": "Revenue",
                "canonical_metric": "REVENUE",
                "period": "Jun 2025",
                "canonical_period": "2025-Q1",
                "scope": "Consolidated",
                "screener_value": 1000.0,
                "official_value": 1000.0,
                "status": "VERIFIED",
                "verified_at": v_time
            },
            {
                "symbol": "VERIFREF",
                "metric_name": "Revenue",
                "canonical_metric": "REVENUE",
                "period": "Sep 2025",
                "canonical_period": "2025-Q2",
                "scope": "Consolidated",
                "screener_value": 1200.0,
                "official_value": 1200.0,
                "status": "VERIFIED",
                "verified_at": v_time
            }
        ]
        database.save_financial_verification_records(v_records)
        
        # 3. Build detail again without manual truth build
        detail2 = main.build_full_stock_detail(stock)
        assert detail2.analytics["quarterly_analysis"]["trends"][1]["provenance"]["sales_growth_qoq"]["quality"] == "verified"
        assert detail2.financial_truth.verification_version == v_time
        print("  ✓ Scenario L passed: Verification refresh automatically upgraded analytics from standardized to verified.")

    print("\n==================================================================")
    print("🎉 ALL PHASE 2B TRUTH-DRIVEN ANALYTICS TESTS (A - L) PASSED 100%!")
    print("==================================================================")

if __name__ == "__main__":
    run_all_tests()

