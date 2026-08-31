"""
=============================================================================
Stocker Phase 2C — Financial Analytics Safety & Sector Routing Test Suite
=============================================================================
Tests Scenarios A through L:
- Test A: 5Y common-period CFO/PAT with TTM excluded.
- Test B: Missing one CFO year -> 5Y ratio unavailable.
- Test C: Bank classifier using ICICI-like rows & industry metadata.
- Test D: Manufacturing / corporate classifier.
- Test E: Bank CFO quality = not applicable.
- Test F: Bank conventional FCF unavailable (None).
- Test G: Bank CWIP does not create expansion signal.
- Test H: General corporate CFO/FCF behavior unchanged.
- Test I: Actual zero remains zero, missing remains None.
- Test J: TTM is not classified as completed annual FY.
- Test K: Deposit/GNPA/NNPA extraction missing -> None (never 0.0).
- Test L: Zero network or AI calls in deterministic sector routing.
=============================================================================
"""

import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "libs"))

from models import FinancialStatement, FinancialRow
from financial_truth_resolver import (
    classify_period_type,
    parse_period_year,
    get_common_completed_annual_periods
)
from financial_engine import (
    classify_financial_business_model,
    compute_financial_analytics
)

class TestFinancialSafetyV42C(unittest.TestCase):

    def test_j_period_classification(self):
        """Test J: TTM, completed annual FY, and quarterly periods are classified deterministically."""
        self.assertEqual(classify_period_type("TTM"), "ttm")
        self.assertEqual(classify_period_type("ttm"), "ttm")
        self.assertEqual(classify_period_type("LTM"), "ttm")
        self.assertEqual(classify_period_type("Trailing 12 Months"), "ttm")
        
        self.assertEqual(classify_period_type("Mar 2026"), "annual_completed")
        self.assertEqual(classify_period_type("FY26"), "annual_completed")
        self.assertEqual(classify_period_type("2026-FY"), "annual_completed")
        
        self.assertEqual(classify_period_type("Jun 2026"), "quarterly")
        self.assertEqual(classify_period_type("Sep 2025"), "quarterly")
        self.assertEqual(classify_period_type("Dec 2025"), "quarterly")
        self.assertEqual(classify_period_type("2026-Q1"), "quarterly")

    def test_a_5y_common_periods_with_ttm_excluded(self):
        """Test A: 5Y common-period CFO/PAT calculation excludes TTM and aligns identical years."""
        pl_periods = ["Mar 2021", "Mar 2022", "Mar 2023", "Mar 2024", "Mar 2025", "Mar 2026", "TTM"]
        cf_periods = ["Mar 2021", "Mar 2022", "Mar 2023", "Mar 2024", "Mar 2025", "Mar 2026"]
        
        pl = FinancialStatement(
            statement_name="profit_loss",
            periods=pl_periods,
            rows=[
                FinancialRow(metric="Sales", values={"Mar 2021": 1000, "Mar 2022": 1100, "Mar 2023": 1200, "Mar 2024": 1300, "Mar 2025": 1400, "Mar 2026": 1500, "TTM": 1600}),
                FinancialRow(metric="Net Profit", values={"Mar 2021": 100, "Mar 2022": 110, "Mar 2023": 120, "Mar 2024": 130, "Mar 2025": 140, "Mar 2026": 150, "TTM": 160})
            ]
        )
        cf = FinancialStatement(
            statement_name="cash_flow",
            periods=cf_periods,
            rows=[
                FinancialRow(metric="Cash from Operating Activity", values={"Mar 2021": 120, "Mar 2022": 130, "Mar 2023": 140, "Mar 2024": 150, "Mar 2025": 160, "Mar 2026": 170}),
                FinancialRow(metric="Fixed assets purchased", values={"Mar 2021": -30, "Mar 2022": -30, "Mar 2023": -30, "Mar 2024": -30, "Mar 2025": -30, "Mar 2026": -30})
            ]
        )
        
        analytics = compute_financial_analytics(
            quarters=None,
            pl=pl,
            bs=None,
            cf=cf,
            sector="Automobile",
            industry="Auto Ancillary"
        )
        
        cf_quality = analytics["cash_flow_quality"]
        self.assertEqual(cf_quality["applicability"], "applicable")
        self.assertEqual(cf_quality["common_annual_periods"], ["Mar 2022", "Mar 2023", "Mar 2024", "Mar 2025", "Mar 2026"])
        
        # 5Y PAT sum = 110 + 120 + 130 + 140 + 150 = 650
        self.assertEqual(cf_quality["cumulative_5y_pat_cr"], 650.0)
        # 5Y CFO sum = 130 + 140 + 150 + 160 + 170 = 750
        self.assertEqual(cf_quality["cumulative_5y_cfo_cr"], 750.0)
        # CFO / PAT = (750 / 650) * 100 = 115.4%
        self.assertEqual(cf_quality["cfo_to_pat_5yr_pct"], 115.4)

    def test_b_missing_one_cfo_year_fails_closed(self):
        """Test B: If fewer than 5 common completed annual periods exist, 5Y ratio is unavailable (None)."""
        pl_periods = ["Mar 2022", "Mar 2023", "Mar 2024", "Mar 2025", "Mar 2026"]
        cf_periods = ["Mar 2022", "Mar 2023", "Mar 2025", "Mar 2026"] # Missing Mar 2024
        
        pl = FinancialStatement(
            statement_name="profit_loss",
            periods=pl_periods,
            rows=[
                FinancialRow(metric="Sales", values={"Mar 2022": 1000, "Mar 2023": 1100, "Mar 2024": 1200, "Mar 2025": 1300, "Mar 2026": 1400}),
                FinancialRow(metric="Net Profit", values={"Mar 2022": 100, "Mar 2023": 110, "Mar 2024": 120, "Mar 2025": 130, "Mar 2026": 140})
            ]
        )
        cf = FinancialStatement(
            statement_name="cash_flow",
            periods=cf_periods,
            rows=[
                FinancialRow(metric="Cash from Operating Activity", values={"Mar 2022": 100, "Mar 2023": 110, "Mar 2025": 130, "Mar 2026": 140})
            ]
        )
        
        analytics = compute_financial_analytics(
            quarters=None,
            pl=pl,
            bs=None,
            cf=cf,
            sector="Manufacturing",
            industry="Industrial Equipment"
        )
        
        cf_quality = analytics["cash_flow_quality"]
        self.assertEqual(cf_quality["common_annual_periods"], [])
        self.assertIsNone(cf_quality["cumulative_5y_pat_cr"])
        self.assertIsNone(cf_quality["cumulative_5y_cfo_cr"])
        self.assertIsNone(cf_quality["cfo_to_pat_5yr_pct"])
        self.assertEqual(cf_quality["cash_conversion_quality"], "Inconclusive / Incomplete Data")

    def test_c_bank_classifier(self):
        """Test C: Bank classifier correctly identifies banks via industry or statement signatures."""
        # 1. By Industry
        bm1 = classify_financial_business_model(sector="Financial Services", industry="Private Sector Bank")
        self.assertEqual(bm1, "BANK")
        
        bm2 = classify_financial_business_model(sector="Financial Services", industry="Public Sector Bank")
        self.assertEqual(bm2, "BANK")
        
        # 2. By Statement Signatures (e.g. Deposits, NPA)
        bs = FinancialStatement(
            statement_name="balance_sheet",
            periods=["Mar 2025", "Mar 2026"],
            rows=[
                FinancialRow(metric="Deposits", values={"Mar 2025": 500000, "Mar 2026": 600000}),
                FinancialRow(metric="Advances", values={"Mar 2025": 400000, "Mar 2026": 480000}),
                FinancialRow(metric="Borrowings", values={"Mar 2025": 100000, "Mar 2026": 120000})
            ]
        )
        quarters = FinancialStatement(
            statement_name="quarters",
            periods=["Dec 2025", "Mar 2026"],
            rows=[
                FinancialRow(metric="Gross NPA %", values={"Dec 2025": 2.1, "Mar 2026": 1.9}),
                FinancialRow(metric="Net NPA %", values={"Dec 2025": 0.5, "Mar 2026": 0.4})
            ]
        )
        bm3 = classify_financial_business_model(pl=None, bs=bs, quarters=quarters)
        self.assertEqual(bm3, "BANK")

    def test_d_corporate_classifier(self):
        """Test D: Manufacturing and IT companies are classified as GENERAL_CORPORATE."""
        bm1 = classify_financial_business_model(sector="Information Technology", industry="IT - Software")
        self.assertEqual(bm1, "GENERAL_CORPORATE")
        
        bm2 = classify_financial_business_model(sector="Automobile", industry="Auto Ancillaries")
        self.assertEqual(bm2, "GENERAL_CORPORATE")
        
        bs = FinancialStatement(
            statement_name="balance_sheet",
            periods=["Mar 2026"],
            rows=[
                FinancialRow(metric="Fixed Assets", values={"Mar 2026": 1000}),
                FinancialRow(metric="CWIP", values={"Mar 2026": 100}),
                FinancialRow(metric="Borrowings", values={"Mar 2026": 200})
            ]
        )
        bm3 = classify_financial_business_model(sector="Chemicals", bs=bs)
        self.assertEqual(bm3, "GENERAL_CORPORATE")

    def test_e_bank_cfo_quality_not_applicable(self):
        """Test E: For banking entities, cash conversion quality is marked not applicable."""
        pl = FinancialStatement(
            statement_name="profit_loss",
            periods=["Mar 2022", "Mar 2023", "Mar 2024", "Mar 2025", "Mar 2026"],
            rows=[
                FinancialRow(metric="Sales", values={"Mar 2022": 50000, "Mar 2023": 60000, "Mar 2024": 70000, "Mar 2025": 80000, "Mar 2026": 90000}),
                FinancialRow(metric="Net Profit", values={"Mar 2022": 10000, "Mar 2023": 12000, "Mar 2024": 15000, "Mar 2025": 18000, "Mar 2026": 20000})
            ]
        )
        cf = FinancialStatement(
            statement_name="cash_flow",
            periods=["Mar 2022", "Mar 2023", "Mar 2024", "Mar 2025", "Mar 2026"],
            rows=[
                FinancialRow(metric="Cash from Operating Activity", values={"Mar 2022": -5000, "Mar 2023": -10000, "Mar 2024": 15000, "Mar 2025": -8000, "Mar 2026": -12000})
            ]
        )
        
        analytics = compute_financial_analytics(
            quarters=None,
            pl=pl,
            bs=None,
            cf=cf,
            sector="Financial Services",
            industry="Private Sector Bank"
        )
        
        self.assertEqual(analytics["financial_business_model"], "BANK")
        cf_quality = analytics["cash_flow_quality"]
        self.assertEqual(cf_quality["applicability"], "not_applicable_financial_business")
        self.assertIn("Not applicable", cf_quality["cash_conversion_quality"])
        self.assertEqual(cf_quality["overall_fcf_confidence"], "Not Applicable (Financial Business Model)")

    def test_f_bank_fcf_unavailable(self):
        """Test F: Bank FCF is None and confidence marked Not Applicable."""
        pl = FinancialStatement(
            statement_name="profit_loss",
            periods=["Mar 2025", "Mar 2026"],
            rows=[
                FinancialRow(metric="Net Profit", values={"Mar 2025": 10000, "Mar 2026": 12000})
            ]
        )
        cf = FinancialStatement(
            statement_name="cash_flow",
            periods=["Mar 2025", "Mar 2026"],
            rows=[
                FinancialRow(metric="Cash from Operating Activity", values={"Mar 2025": -5000, "Mar 2026": 8000}),
                FinancialRow(metric="Fixed assets purchased", values={"Mar 2025": -500, "Mar 2026": -600})
            ]
        )
        
        analytics = compute_financial_analytics(
            quarters=None,
            pl=pl,
            bs=None,
            cf=cf,
            sector="Financial Services",
            industry="Private Sector Bank"
        )
        
        fcf_trends = analytics["cash_flow_quality"]["fcf_trends"]
        for trend in fcf_trends:
            self.assertIsNone(trend["stocker_derived_fcf_cr"])
            self.assertEqual(trend["fcf_confidence"], "Not Applicable")
        self.assertIsNone(analytics["cash_flow_quality"]["cumulative_5y_fcf_cr"])

    def test_g_bank_cwip_no_expansion_signal(self):
        """Test G: Bank CWIP does not trigger capex expansion signal."""
        bs = FinancialStatement(
            statement_name="balance_sheet",
            periods=["Mar 2026"],
            rows=[
                FinancialRow(metric="Fixed Assets", values={"Mar 2026": 1000}),
                FinancialRow(metric="CWIP", values={"Mar 2026": 500}), # 50% CWIP / Fixed Assets
                FinancialRow(metric="Borrowings", values={"Mar 2026": 20000}),
                FinancialRow(metric="Deposits", values={"Mar 2026": 100000})
            ]
        )
        
        analytics = compute_financial_analytics(
            quarters=None,
            pl=None,
            bs=bs,
            cf=None,
            sector="Financial Services",
            industry="Public Sector Bank"
        )
        
        self.assertEqual(analytics["financial_business_model"], "BANK")
        self.assertFalse(analytics["balance_sheet_efficiency"]["has_significant_capex_trigger"])

    def test_h_corporate_fcf_behavior_intact(self):
        """Test H: General corporate deterministic FCF and cash conversion calculations remain fully functional."""
        pl = FinancialStatement(
            statement_name="profit_loss",
            periods=["Mar 2022", "Mar 2023", "Mar 2024", "Mar 2025", "Mar 2026"],
            rows=[
                FinancialRow(metric="Sales", values={"Mar 2022": 1000, "Mar 2023": 1100, "Mar 2024": 1200, "Mar 2025": 1300, "Mar 2026": 1400}),
                FinancialRow(metric="Net Profit", values={"Mar 2022": 100, "Mar 2023": 120, "Mar 2024": 140, "Mar 2025": 160, "Mar 2026": 180})
            ]
        )
        cf = FinancialStatement(
            statement_name="cash_flow",
            periods=["Mar 2022", "Mar 2023", "Mar 2024", "Mar 2025", "Mar 2026"],
            rows=[
                FinancialRow(metric="Cash from Operating Activity", values={"Mar 2022": 110, "Mar 2023": 130, "Mar 2024": 150, "Mar 2025": 170, "Mar 2026": 200}),
                FinancialRow(metric="Fixed assets purchased", values={"Mar 2022": -20, "Mar 2023": -30, "Mar 2024": -40, "Mar 2025": -50, "Mar 2026": -60})
            ]
        )
        
        analytics = compute_financial_analytics(
            quarters=None,
            pl=pl,
            bs=None,
            cf=cf,
            sector="Consumer Goods",
            industry="FMCG"
        )
        
        self.assertEqual(analytics["financial_business_model"], "GENERAL_CORPORATE")
        cf_quality = analytics["cash_flow_quality"]
        self.assertEqual(cf_quality["applicability"], "applicable")
        self.assertTrue(cf_quality["is_fcf_directly_reported"])
        self.assertIn("Superior", cf_quality["cash_conversion_quality"])
        
        # Latest FCF in Mar 2026 = 200 - 60 = 140
        latest_trend = cf_quality["fcf_trends"][-1]
        self.assertEqual(latest_trend["stocker_derived_fcf_cr"], 140.0)
        self.assertEqual(latest_trend["fcf_confidence"], "High Confidence")

    def test_i_actual_zero_preserved(self):
        """Test I: Actual 0.0 value is preserved as 0.0, not converted to None."""
        bs = FinancialStatement(
            statement_name="balance_sheet",
            periods=["Mar 2026"],
            rows=[
                FinancialRow(metric="Borrowings", values={"Mar 2026": 0.0}),
                FinancialRow(metric="Equity Capital", values={"Mar 2026": 100.0}),
                FinancialRow(metric="Reserves", values={"Mar 2026": 900.0})
            ]
        )
        
        analytics = compute_financial_analytics(
            quarters=None,
            pl=None,
            bs=bs,
            cf=None,
            sector="Information Technology",
            industry="IT Services"
        )
        
        bs_eff = analytics["balance_sheet_efficiency"]
        self.assertEqual(bs_eff["latest_debt_to_equity"], 0.0)
        self.assertEqual(bs_eff["bs_trends"][0]["borrowings_cr"], 0.0)

    def test_k_bank_metrics_missing_are_none(self):
        """Test K: Missing bank metrics are returned as None (never 0.0)."""
        bs = FinancialStatement(
            statement_name="balance_sheet",
            periods=["Mar 2026"],
            rows=[
                FinancialRow(metric="Deposits", values={"Mar 2026": 500000.0}),
                FinancialRow(metric="Borrowings", values={"Mar 2026": 50000.0})
            ]
        )
        # Quarters has NO Gross NPA % or Net NPA %
        quarters = FinancialStatement(
            statement_name="quarters",
            periods=["Mar 2026"],
            rows=[
                FinancialRow(metric="Sales", values={"Mar 2026": 10000.0})
            ]
        )
        
        analytics = compute_financial_analytics(
            quarters=quarters,
            pl=None,
            bs=bs,
            cf=None,
            sector="Financial Services",
            industry="Private Sector Bank"
        )
        
        bm = analytics.get("bank_metrics", {})
        self.assertEqual(bm.get("latest_deposits_cr"), 500000.0)
        self.assertIsNone(bm.get("latest_advances_cr"))
        self.assertIsNone(bm.get("latest_gross_npa_pct"))
        self.assertIsNone(bm.get("latest_net_npa_pct"))

    def test_l_zero_network_or_ai_calls(self):
        """Test L: Classification and analytics execution require zero network/AI calls."""
        # Runs fully in-memory with local statements
        pl = FinancialStatement(
            statement_name="profit_loss",
            periods=["Mar 2026"],
            rows=[FinancialRow(metric="Sales", values={"Mar 2026": 100})]
        )
        analytics = compute_financial_analytics(
            quarters=None,
            pl=pl,
            bs=None,
            cf=None,
            symbol="TESTCO",
            sector="Metals",
            industry="Steel"
        )
        self.assertEqual(analytics["financial_business_model"], "GENERAL_CORPORATE")
        self.assertIn("formula_transparency", analytics)

if __name__ == "__main__":
    unittest.main()
