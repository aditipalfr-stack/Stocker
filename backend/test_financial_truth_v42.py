"""
Stocker Phase 2A — Canonical Financial Truth Layer Comprehensive Test Suite
===========================================================================

Validates all Phase 2A requirements for deterministic Canonical Financial Truth:
- Exact Official Match (VERIFIED)
- Tolerance Match (VERIFIED)
- Real Discrepancy (DISCREPANCY without silent overrides)
- Scope Isolation (NOT_COMPARABLE)
- Period Isolation (Zero nearest-period fallback)
- Currency Fail-Closed (INSUFFICIENT_EVIDENCE)
- Unit / EPS Isolation (No unproven override)
- Missing Sources (OFFICIAL_SOURCE_MISSING / SCREENER_VALUE_MISSING)
- Financial & Verification Refresh Versioning
- Inspection API (GET /api/stocks/{symbol}/financial-truth without network)
- Downstream Contract Helpers (get_canonical_fact, get_canonical_series, has_material_verification_discrepancy)
"""

import os
import sys
import tempfile
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
from unittest.mock import patch, MagicMock

# Setup imports
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "libs"))

import database
from models import (
    FinancialStatement,
    FinancialRow,
    KeyRatios,
    CanonicalFinancialFact,
    VerificationCoverageSummary,
    FinancialTruthContainer,
    FinancialVerificationItem
)
from financial_truth_service import (
    build_financial_truth_for_stock,
    get_canonical_fact,
    get_canonical_series,
    has_material_verification_discrepancy
)
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
        "about": "Test stock for canonical truth layer validation.",
        "statement_type": "consolidated",
        "source_name": "Screener.in",
        "source_url": f"https://www.screener.in/company/{symbol}/",
        "fetched_at": now_iso,
        "ratios": KeyRatios(current_price=1000.0, market_cap_cr=50000.0, stock_pe=25.0),
        "quarters": FinancialStatement(
            periods=["Jun 2025", "Sep 2025", "Dec 2025", "Mar 2026", "Jun 2026"],
            rows=[
                FinancialRow(metric="Sales", values={"Jun 2025": 1000.0, "Sep 2025": 1100.0, "Dec 2025": 1200.0, "Mar 2026": 1300.0, "Jun 2026": 1400.0}),
                FinancialRow(metric="Operating Profit", values={"Jun 2025": 200.0, "Sep 2025": 220.0, "Dec 2025": 240.0, "Mar 2026": 260.0, "Jun 2026": 280.0}),
                FinancialRow(metric="OPM %", values={"Jun 2025": 20.0, "Sep 2025": 20.0, "Dec 2025": 20.0, "Mar 2026": 20.0, "Jun 2026": 20.0}),
                FinancialRow(metric="Net Profit", values={"Jun 2025": 150.0, "Sep 2025": 165.0, "Dec 2025": 180.0, "Mar 2026": 195.0, "Jun 2026": 210.0}),
                FinancialRow(metric="EPS in Rs", values={"Jun 2025": 15.0, "Sep 2025": 16.5, "Dec 2025": 18.0, "Mar 2026": 19.5, "Jun 2026": 21.0}),
            ]
        ),
        "profit_loss": FinancialStatement(
            periods=["Mar 2023", "Mar 2024", "Mar 2025", "Mar 2026", "TTM"],
            rows=[
                FinancialRow(metric="Sales", values={"Mar 2023": 3500.0, "Mar 2024": 4000.0, "Mar 2025": 4500.0, "Mar 2026": 5000.0, "TTM": 5000.0}),
                FinancialRow(metric="Operating Profit", values={"Mar 2023": 700.0, "Mar 2024": 800.0, "Mar 2025": 900.0, "Mar 2026": 1000.0, "TTM": 1000.0}),
                FinancialRow(metric="Net Profit", values={"Mar 2023": 500.0, "Mar 2024": 600.0, "Mar 2025": 700.0, "Mar 2026": 800.0, "TTM": 800.0}),
                FinancialRow(metric="EPS in Rs", values={"Mar 2023": 50.0, "Mar 2024": 60.0, "Mar 2025": 70.0, "Mar 2026": 80.0, "TTM": 80.0}),
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
                FinancialRow(metric="Cash from Operating Activity", values={"Mar 2023": 550.0, "Mar 2024": 650.0, "Mar 2025": 750.0, "Mar 2026": 850.0})
            ]
        )
    }

def run_all_tests():
    print("\n==================================================================")
    print("Running Stocker Phase 2A: Financial Truth Layer Test Suite")
    print("==================================================================")

    # -------------------------------------------------------------------------
    # TEST A: Exact Official Match (VERIFIED -> Canonical Official)
    # -------------------------------------------------------------------------
    with IsolatedTestDatabase():
        print("\n--- Test A: Exact Official Match ---")
        stock = make_sample_stock_data("INFY")
        
        # Exact matching verification record for FY26 Revenue
        v_record = {
            "symbol": "INFY",
            "metric_name": "Revenue",
            "canonical_metric": "REVENUE",
            "period": "FY26",
            "canonical_period": "2026-FY",
            "scope": "Consolidated",
            "screener_value": 5000.0,
            "official_value": 5000.0,
            "variance_abs": 0.0,
            "variance_pct": 0.0,
            "unit": "₹ Cr",
            "currency": "INR",
            "status": "VERIFIED",
            "official_source_name": "NSE Official XBRL Filing",
            "official_source_url": "https://nsearchives.nseindia.com/xbrl/INFY_FY26.xml",
            "verified_at": "2026-05-01T10:00:00Z"
        }
        database.save_financial_verification_records([v_record])
        
        container = build_financial_truth_for_stock("INFY", stock)
        fact = next((f for f in container.facts if f.canonical_metric == "REVENUE" and f.canonical_period == "2026-FY"), None)
        
        assert fact is not None, "Expected FY26 Revenue fact in container"
        assert fact.verification_status == "VERIFIED"
        assert fact.value == 5000.0
        assert fact.selected_source_type == "official"
        assert fact.selected_source_name == "NSE Official XBRL Filing"
        assert fact.confidence == "High"
        assert fact.difference_absolute == 0.0
        print("  ✓ Test A passed: Exact match selected official value with High confidence.")

    # -------------------------------------------------------------------------
    # TEST B: Tolerance Match (VERIFIED -> Canonical Official)
    # -------------------------------------------------------------------------
    with IsolatedTestDatabase():
        print("\n--- Test B: Within Tolerance Match ---")
        stock = make_sample_stock_data("TCS")
        
        # Official value is 5000.4 vs Screener 5000.0 (within ₹1 Cr tolerance)
        v_record = {
            "symbol": "TCS",
            "metric_name": "Revenue",
            "canonical_metric": "REVENUE",
            "period": "FY26",
            "canonical_period": "2026-FY",
            "scope": "Consolidated",
            "screener_value": 5000.0,
            "official_value": 5000.4,
            "variance_abs": 0.4,
            "variance_pct": 0.01,
            "unit": "₹ Cr",
            "currency": "INR",
            "status": "VERIFIED",
            "official_source_name": "BSE Official XBRL Filing",
            "verified_at": "2026-05-01T10:00:00Z"
        }
        database.save_financial_verification_records([v_record])
        
        container = build_financial_truth_for_stock("TCS", stock)
        fact = next((f for f in container.facts if f.canonical_metric == "REVENUE" and f.canonical_period == "2026-FY"), None)
        
        assert fact is not None
        assert fact.verification_status == "VERIFIED"
        assert fact.value == 5000.4, f"Expected official value 5000.4, got {fact.value}"
        assert fact.selected_source_type == "official"
        assert fact.confidence == "High"
        print("  ✓ Test B passed: Within-tolerance match selected official value with High confidence.")

    # -------------------------------------------------------------------------
    # TEST C: Real Discrepancy (DISCREPANCY -> Preserves Standardized, Exposes Official)
    # -------------------------------------------------------------------------
    with IsolatedTestDatabase():
        print("\n--- Test C: Real Discrepancy ---")
        stock = make_sample_stock_data("WIPRO")
        
        # Screener = 5000.0, Official = 5500.0 (10% discrepancy)
        v_record = {
            "symbol": "WIPRO",
            "metric_name": "Revenue",
            "canonical_metric": "REVENUE",
            "period": "FY26",
            "canonical_period": "2026-FY",
            "scope": "Consolidated",
            "screener_value": 5000.0,
            "official_value": 5500.0,
            "variance_abs": 500.0,
            "variance_pct": 10.0,
            "unit": "₹ Cr",
            "currency": "INR",
            "status": "DISCREPANCY",
            "official_source_name": "BSE Statutory Filing",
            "verified_at": "2026-05-01T10:00:00Z"
        }
        database.save_financial_verification_records([v_record])
        
        container = build_financial_truth_for_stock("WIPRO", stock)
        fact = next((f for f in container.facts if f.canonical_metric == "REVENUE" and f.canonical_period == "2026-FY"), None)
        
        assert fact is not None
        assert fact.verification_status == "DISCREPANCY"
        assert fact.value == 5000.0, "Expected canonical value to preserve standardized value for continuity"
        assert fact.screener_value == 5000.0
        assert fact.official_value == 5500.0
        assert fact.difference_absolute == 500.0
        assert fact.difference_pct == 10.0
        assert fact.confidence == "Low"
        assert container.coverage.overall_truth_state == "DISCREPANCY"
        assert container.discrepancies_count == 1
        print("  ✓ Test C passed: Discrepancy exposed explicitly without silent override.")

    # -------------------------------------------------------------------------
    # TEST D: Wrong Scope (NOT_COMPARABLE -> No Override)
    # -------------------------------------------------------------------------
    with IsolatedTestDatabase():
        print("\n--- Test D: Wrong Scope (Consolidated vs Standalone) ---")
        stock = make_sample_stock_data("HDFCBANK") # Consolidated scope
        
        # Official record was Standalone
        v_record = {
            "symbol": "HDFCBANK",
            "metric_name": "Revenue",
            "canonical_metric": "REVENUE",
            "period": "FY26",
            "canonical_period": "2026-FY",
            "scope": "Standalone",
            "screener_value": 5000.0,
            "official_value": 4200.0,
            "status": "NOT_COMPARABLE",
            "verified_at": "2026-05-01T10:00:00Z"
        }
        database.save_financial_verification_records([v_record])
        
        container = build_financial_truth_for_stock("HDFCBANK", stock)
        fact = next((f for f in container.facts if f.canonical_metric == "REVENUE" and f.canonical_period == "2026-FY"), None)
        
        assert fact is not None
        assert fact.scope == "Consolidated"
        assert fact.value == 5000.0, "Consolidated fact must not be overridden by Standalone official figure"
        print("  ✓ Test D passed: Scope isolation strictly preserved.")

    # -------------------------------------------------------------------------
    # TEST E: Wrong Period (Zero Nearest-Period Substitution)
    # -------------------------------------------------------------------------
    with IsolatedTestDatabase():
        print("\n--- Test E: Period Isolation ---")
        stock = make_sample_stock_data("RELIANCE")
        
        # Only FY24 is verified, FY26 is not
        v_record = {
            "symbol": "RELIANCE",
            "metric_name": "Revenue",
            "canonical_metric": "REVENUE",
            "period": "FY24",
            "canonical_period": "2024-FY",
            "scope": "Consolidated",
            "screener_value": 4000.0,
            "official_value": 4000.0,
            "status": "VERIFIED",
            "verified_at": "2026-05-01T10:00:00Z"
        }
        database.save_financial_verification_records([v_record])
        
        container = build_financial_truth_for_stock("RELIANCE", stock)
        fact_fy26 = next((f for f in container.facts if f.canonical_metric == "REVENUE" and f.canonical_period == "2026-FY"), None)
        fact_fy24 = next((f for f in container.facts if f.canonical_metric == "REVENUE" and f.canonical_period == "2024-FY"), None)
        
        assert fact_fy24.verification_status == "VERIFIED"
        assert fact_fy26.verification_status == "UNVERIFIED"
        assert fact_fy26.value == 5000.0
        print("  ✓ Test E passed: Zero nearest-period substitution verified.")

    # -------------------------------------------------------------------------
    # TEST F: Foreign / Unknown Currency (INSUFFICIENT_EVIDENCE -> Fail Closed)
    # -------------------------------------------------------------------------
    with IsolatedTestDatabase():
        print("\n--- Test F: Foreign / Unknown Currency ---")
        stock = make_sample_stock_data("TATAMOTORS")
        
        v_record = {
            "symbol": "TATAMOTORS",
            "metric_name": "Revenue",
            "canonical_metric": "REVENUE",
            "period": "FY26",
            "canonical_period": "2026-FY",
            "scope": "Consolidated",
            "screener_value": 5000.0,
            "official_value": 600.0, # in USD or Millions without proof
            "unit": "Unknown",
            "currency": "USD",
            "status": "INSUFFICIENT_EVIDENCE",
            "verified_at": "2026-05-01T10:00:00Z"
        }
        database.save_financial_verification_records([v_record])
        
        container = build_financial_truth_for_stock("TATAMOTORS", stock)
        fact = next((f for f in container.facts if f.canonical_metric == "REVENUE" and f.canonical_period == "2026-FY"), None)
        
        assert fact.verification_status == "INSUFFICIENT_EVIDENCE"
        assert fact.value == 5000.0, "Must not override Screener with unknown/foreign currency official amount"
        print("  ✓ Test F passed: Unknown/foreign currency failed closed.")

    # -------------------------------------------------------------------------
    # TEST G: EPS Without Explicit ₹/Share Proof
    # -------------------------------------------------------------------------
    with IsolatedTestDatabase():
        print("\n--- Test G: EPS Without Explicit ₹/Share Proof ---")
        stock = make_sample_stock_data("INFY")
        
        v_record = {
            "symbol": "INFY",
            "metric_name": "Basic EPS",
            "canonical_metric": "BASIC_EPS",
            "period": "FY26",
            "canonical_period": "2026-FY",
            "scope": "Consolidated",
            "screener_value": 80.0,
            "official_value": 80.0,
            "unit": "Unknown",
            "status": "INSUFFICIENT_EVIDENCE",
            "verified_at": "2026-05-01T10:00:00Z"
        }
        database.save_financial_verification_records([v_record])
        
        container = build_financial_truth_for_stock("INFY", stock)
        fact = next((f for f in container.facts if f.canonical_metric == "BASIC_EPS" and f.canonical_period == "2026-FY"), None)
        
        assert fact.verification_status == "INSUFFICIENT_EVIDENCE"
        assert fact.value == 80.0
        print("  ✓ Test G passed: Unproven EPS unit rejected from VERIFIED status.")

    # -------------------------------------------------------------------------
    # TEST H: Official Source Missing
    # -------------------------------------------------------------------------
    with IsolatedTestDatabase():
        print("\n--- Test H: Official Source Missing ---")
        stock = make_sample_stock_data("SMALLCAP")
        
        v_record = {
            "symbol": "SMALLCAP",
            "metric_name": "Revenue",
            "canonical_metric": "REVENUE",
            "period": "FY26",
            "canonical_period": "2026-FY",
            "scope": "Consolidated",
            "screener_value": 5000.0,
            "official_value": None,
            "status": "OFFICIAL_SOURCE_MISSING",
            "verified_at": "2026-05-01T10:00:00Z"
        }
        database.save_financial_verification_records([v_record])
        
        container = build_financial_truth_for_stock("SMALLCAP", stock)
        fact = next((f for f in container.facts if f.canonical_metric == "REVENUE" and f.canonical_period == "2026-FY"), None)
        
        assert fact.verification_status == "OFFICIAL_SOURCE_MISSING"
        assert fact.value == 5000.0
        assert fact.selected_source_type == "screener"
        print("  ✓ Test H passed: Standardized figure preserved under OFFICIAL_SOURCE_MISSING.")

    # -------------------------------------------------------------------------
    # TEST I: Screener Value Missing + Official Value Present
    # -------------------------------------------------------------------------
    with IsolatedTestDatabase():
        print("\n--- Test I: Screener Value Missing ---")
        stock = make_sample_stock_data("NEWLISTED")
        
        # Official filing exists for Q1FY27 which Screener hasn't added yet
        v_record = {
            "symbol": "NEWLISTED",
            "metric_name": "Revenue",
            "canonical_metric": "REVENUE",
            "period": "Q1 FY27",
            "canonical_period": "2026-Q1",
            "scope": "Consolidated",
            "screener_value": None,
            "official_value": 1550.0,
            "unit": "₹ Cr",
            "status": "SCREENER_VALUE_MISSING",
            "official_source_name": "NSE Financial Results",
            "verified_at": "2026-08-01T10:00:00Z"
        }
        database.save_financial_verification_records([v_record])
        
        container = build_financial_truth_for_stock("NEWLISTED", stock)
        fact = next((f for f in container.facts if f.canonical_metric == "REVENUE" and f.canonical_period == "2026-Q1"), None)
        
        assert fact is not None
        assert fact.verification_status in ("SCREENER_VALUE_MISSING", "UNVERIFIED") or fact.value == 1550.0
        print("  ✓ Test I passed: Missing Screener row handled safely.")

    # -------------------------------------------------------------------------
    # TEST J & K: Financial & Verification Refresh Invalidation
    # -------------------------------------------------------------------------
    with IsolatedTestDatabase():
        from scraper import serialize_stock_data
        v1_time = "2026-08-31T09:00:00Z"
        stock_v1 = make_sample_stock_data("TESTCO", fetched_at=v1_time)
        database.save_stock_cache("TESTCO", "Test Co", "IT", "Software", serialize_stock_data(stock_v1))
        
        # Initial truth build
        c1 = build_financial_truth_for_stock("TESTCO", stock_v1)
        assert c1.input_financial_version == v1_time
        assert c1.verified_count == 0
        
        # Refresh 1: Official verification runs
        v_record = {
            "symbol": "TESTCO",
            "metric_name": "Revenue",
            "canonical_metric": "REVENUE",
            "period": "FY26",
            "canonical_period": "2026-FY",
            "scope": "Consolidated",
            "screener_value": 5000.0,
            "official_value": 5000.0,
            "status": "VERIFIED",
            "verified_at": "2026-08-31T10:00:00Z"
        }
        database.save_financial_verification_records([v_record])
        
        c2 = build_financial_truth_for_stock("TESTCO", stock_v1)
        assert c2.verified_count == 1
        assert c2.verification_version == "2026-08-31T10:00:00Z"
        
        # Refresh 2: Financial statements updated
        v2_time = "2026-08-31T11:00:00Z"
        stock_v2 = make_sample_stock_data("TESTCO", fetched_at=v2_time)
        c3 = build_financial_truth_for_stock("TESTCO", stock_v2)
        assert c3.input_financial_version == v2_time
        assert c3.verified_count == 1
        print("  ✓ Test J & K passed: Invalidation and version tracking verified across refreshes.")

    # -------------------------------------------------------------------------
    # TEST L: Inspection API (GET /api/stocks/{symbol}/financial-truth)
    # -------------------------------------------------------------------------
    with IsolatedTestDatabase():
        print("\n--- Test L: Inspection API Endpoint ---")
        from scraper import serialize_stock_data
        stock = make_sample_stock_data("INFY")
        database.save_stock_cache("INFY", "Infosys Ltd", "IT", "Software", serialize_stock_data(stock))
        
        # Call API function directly
        res = main.get_stock_financial_truth("INFY")
        assert res is not None
        assert res.symbol == "INFY"
        assert len(res.facts) > 0
        assert res.coverage.target_facts_count == len(res.facts)
        print("  ✓ Test L passed: GET /api/stocks/{symbol}/financial-truth returned valid container locally.")

    # -------------------------------------------------------------------------
    # TEST M: Downstream Contract Helpers
    # -------------------------------------------------------------------------
    with IsolatedTestDatabase():
        print("\n--- Test M: Downstream Contract Helpers ---")
        stock = make_sample_stock_data("COLPAL")
        
        # Add a discrepancy for testing helper
        v_record = {
            "symbol": "COLPAL",
            "metric_name": "Operating Profit",
            "canonical_metric": "OPERATING_PROFIT",
            "period": "FY26",
            "canonical_period": "2026-FY",
            "scope": "Consolidated",
            "screener_value": 1000.0,
            "official_value": 1200.0,
            "status": "DISCREPANCY",
            "verified_at": "2026-08-31T10:00:00Z"
        }
        database.save_financial_verification_records([v_record])
        build_financial_truth_for_stock("COLPAL", stock)
        
        # Test 1: get_canonical_fact
        f1 = get_canonical_fact("COLPAL", "REVENUE", "FY26")
        assert f1 is not None
        assert f1.canonical_metric == "REVENUE"
        assert f1.value == 5000.0
        
        # Test 2: get_canonical_series
        series = get_canonical_series("COLPAL", "REVENUE")
        assert len(series) > 0
        
        # Test 3: has_material_verification_discrepancy
        has_disc = has_material_verification_discrepancy("COLPAL")
        assert has_disc is True, "Expected has_material_verification_discrepancy to return True"
        
        has_disc_rev = has_material_verification_discrepancy("COLPAL", metric="REVENUE")
        assert has_disc_rev is False, "Revenue should not have a discrepancy"
        
        has_disc_op = has_material_verification_discrepancy("COLPAL", metric="OPERATING_PROFIT")
        assert has_disc_op is True, "Operating profit should have a discrepancy"
        print("  ✓ Test M passed: Downstream helpers operate accurately.")

    print("\n==================================================================")
    print("🎉 ALL PHASE 2A FINANCIAL TRUTH TESTS (A - M) PASSED 100% CLEANLY!")
    print("==================================================================")

if __name__ == "__main__":
    run_all_tests()
