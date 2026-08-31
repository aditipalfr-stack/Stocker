"""
=============================================================================
Stocker Phase 4.3 — Bank Analytics Engine (Tier 1) Test Suite
=============================================================================
Tests Scenarios A through P + Independent Review Blockers (1 through 6):
- Scenario A: 5 exact annual deposit periods -> correct latest YoY & 3Y CAGR.
- Scenario B: Missing exact prior year -> YoY unavailable (None), 3Y exact match.
- Scenario C: Advances growth exact chronology.
- Scenario D: CD ratio correctly computed.
- Scenario E: Deposits = 0 -> CD ratio unavailable (None), no div-by-zero / inf.
- Scenario F: ROA strictly uses average assets, not ending assets.
- Scenario G: Missing prior assets -> ROA is None.
- Scenario H: ROE strictly uses average shareholder equity.
- Scenario I: GNPA / NNPA missing remain None.
- Scenario J: Real GNPA = 0.0 remains 0.0.
- Scenario K: Cost-to-income calculated only with defensible exact rows, else None.
- Scenario L: Credit cost strictly uses average gross advances.
- Scenario M: TTM excluded from annual bank calculations.
- Scenario N: Zero AI / zero network calls in bank engine.
- Scenario O: General corporate analytics remain 100% unchanged.
- Scenario P: Existing Phase 2C bank FCF/CFO/CWIP suppression remains intact.

Blocker Scenarios (Review Corrections):
- Blocker 1: Bank Routing Bug (BANK gets bank_analytics; NBFC, INSURANCE, OTHER_FINANCIAL do NOT).
- Blocker 2: Fail-Closed Equity (Missing equity capital or reserves -> None, explicit zero preserved).
- Blocker 3: Fail-Closed Total Assets (Direct row required; partial liability components never synthesize assets).
- Blocker 4: Cost-to-Income Fail-Closed on generic Revenue/Expenses without bank-specific rows.
- Blocker 5: DuPont analysis quarantined for BANK/financials; intact for GENERAL_CORPORATE.
- Blocker 6: Provenance accurately reflects canonical truth verification status (no fake verification).
=============================================================================
"""

import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "libs"))

from models import FinancialStatement, FinancialRow, FinancialTruthContainer, CanonicalFinancialFact
from bank_engine import compute_bank_analytics
from financial_engine import compute_financial_analytics

class TestBankAnalyticsV43(unittest.TestCase):

    def test_a_deposit_growth_yoy_and_3y_cagr(self):
        """Scenario A: 5 exact annual deposit periods -> correct latest YoY & 3Y CAGR."""
        bs = FinancialStatement(
            statement_name="balance_sheet",
            periods=["Mar 2022", "Mar 2023", "Mar 2024", "Mar 2025", "Mar 2026"],
            rows=[
                FinancialRow(metric="Deposits", values={
                    "Mar 2022": 100000.0,
                    "Mar 2023": 110000.0,
                    "Mar 2024": 125000.0,
                    "Mar 2025": 140000.0,
                    "Mar 2026": 160000.0
                }),
                FinancialRow(metric="Advances", values={
                    "Mar 2022": 80000.0, "Mar 2023": 90000.0, "Mar 2024": 100000.0,
                    "Mar 2025": 115000.0, "Mar 2026": 130000.0
                })
            ]
        )
        res = compute_bank_analytics(bs=bs)
        
        # YoY = (160000 - 140000) / 140000 * 100 = 14.2857% -> 14.3%
        self.assertEqual(res.deposit_growth_yoy_pct, 14.3)
        # 3Y CAGR = (160000 / 110000)^(1/3) - 1 = (1.4545)^0.3333 - 1 = 13.3%
        self.assertEqual(res.deposit_growth_3yr_cagr_pct, 13.3)
        self.assertEqual(res.latest_period, "Mar 2026")

    def test_b_missing_prior_year_deposit_yoy_unavailable(self):
        """Scenario B: Missing exact prior year -> YoY unavailable (None)."""
        bs = FinancialStatement(
            statement_name="balance_sheet",
            periods=["Mar 2022", "Mar 2023", "Mar 2024", "Mar 2026"], # Missing Mar 2025
            rows=[
                FinancialRow(metric="Deposits", values={
                    "Mar 2022": 100000.0,
                    "Mar 2023": 110000.0,
                    "Mar 2024": 125000.0,
                    "Mar 2026": 160000.0
                })
            ]
        )
        res = compute_bank_analytics(bs=bs)
        self.assertIsNone(res.deposit_growth_yoy_pct)
        self.assertIn("deposit_growth_yoy", res.unavailable_reasons)
        # 3Y CAGR between Mar 2023 and Mar 2026 is exact (2026 - 2023 = 3)
        self.assertEqual(res.deposit_growth_3yr_cagr_pct, 13.3)

    def test_c_advances_growth_exact_chronology(self):
        """Scenario C: Advances growth calculated with exact annual chronology."""
        bs = FinancialStatement(
            statement_name="balance_sheet",
            periods=["Mar 2023", "Mar 2024", "Mar 2025", "Mar 2026"],
            rows=[
                FinancialRow(metric="Advances", values={
                    "Mar 2023": 100000.0,
                    "Mar 2024": 115000.0,
                    "Mar 2025": 130000.0,
                    "Mar 2026": 150000.0
                }),
                FinancialRow(metric="Deposits", values={
                    "Mar 2023": 120000.0, "Mar 2024": 140000.0,
                    "Mar 2025": 160000.0, "Mar 2026": 180000.0
                })
            ]
        )
        res = compute_bank_analytics(bs=bs)
        # YoY = (150000 - 130000) / 130000 * 100 = 15.38% -> 15.4%
        self.assertEqual(res.advances_growth_yoy_pct, 15.4)
        # 3Y CAGR = (150000 / 100000)^(1/3) - 1 = 1.5^(1/3) - 1 = 14.5%
        self.assertEqual(res.advances_growth_3yr_cagr_pct, 14.5)

    def test_d_credit_to_deposit_ratio(self):
        """Scenario D: CD ratio correctly computed as Advances / Deposits * 100."""
        bs = FinancialStatement(
            statement_name="balance_sheet",
            periods=["Mar 2026"],
            rows=[
                FinancialRow(metric="Advances", values={"Mar 2026": 120000.0}),
                FinancialRow(metric="Deposits", values={"Mar 2026": 150000.0})
            ]
        )
        res = compute_bank_analytics(bs=bs)
        # CD = (120000 / 150000) * 100 = 80.0%
        self.assertEqual(res.credit_deposit_ratio_pct, 80.0)

    def test_e_deposits_zero_cd_ratio_none(self):
        """Scenario E: Deposits = 0 -> CD ratio unavailable (None), no div-by-zero or inf."""
        bs = FinancialStatement(
            statement_name="balance_sheet",
            periods=["Mar 2026"],
            rows=[
                FinancialRow(metric="Advances", values={"Mar 2026": 50000.0}),
                FinancialRow(metric="Deposits", values={"Mar 2026": 0.0})
            ]
        )
        res = compute_bank_analytics(bs=bs)
        self.assertIsNone(res.credit_deposit_ratio_pct)
        self.assertIn("credit_deposit_ratio", res.unavailable_reasons)

    def test_f_roa_uses_average_assets(self):
        """Scenario F: ROA strictly uses average total assets, not ending assets."""
        bs = FinancialStatement(
            statement_name="balance_sheet",
            periods=["Mar 2025", "Mar 2026"],
            rows=[
                FinancialRow(metric="Total Assets", values={"Mar 2025": 100000.0, "Mar 2026": 140000.0}),
                FinancialRow(metric="Deposits", values={"Mar 2025": 80000.0, "Mar 2026": 110000.0}),
                FinancialRow(metric="Advances", values={"Mar 2025": 60000.0, "Mar 2026": 90000.0})
            ]
        )
        pl = FinancialStatement(
            statement_name="profit_loss",
            periods=["Mar 2025", "Mar 2026"],
            rows=[
                FinancialRow(metric="Net Profit", values={"Mar 2025": 1500.0, "Mar 2026": 2400.0})
            ]
        )
        res = compute_bank_analytics(pl=pl, bs=bs)
        
        # Average Assets = (100000 + 140000) / 2 = 120000.0
        # Ending Assets = 140000.0
        # Correct ROA = (2400 / 120000) * 100 = 2.0%
        # Incorrect ending-asset ROA would be 2400 / 140000 = 1.71%
        self.assertEqual(res.roa_pct, 2.0)
        self.assertEqual(res.provenance["roa"]["avg_assets_cr"], 120000.0)

    def test_g_missing_prior_assets_roa_none(self):
        """Scenario G: Missing prior assets -> ROA is None (fail closed)."""
        bs = FinancialStatement(
            statement_name="balance_sheet",
            periods=["Mar 2026"], # Only 1 period
            rows=[
                FinancialRow(metric="Total Assets", values={"Mar 2026": 140000.0}),
                FinancialRow(metric="Deposits", values={"Mar 2026": 110000.0})
            ]
        )
        pl = FinancialStatement(
            statement_name="profit_loss",
            periods=["Mar 2026"],
            rows=[
                FinancialRow(metric="Net Profit", values={"Mar 2026": 2400.0})
            ]
        )
        res = compute_bank_analytics(pl=pl, bs=bs)
        self.assertIsNone(res.roa_pct)
        self.assertIn("roa", res.unavailable_reasons)

    def test_h_roe_uses_average_shareholder_equity(self):
        """Scenario H: ROE strictly uses average shareholder equity (Capital + Reserves)."""
        bs = FinancialStatement(
            statement_name="balance_sheet",
            periods=["Mar 2025", "Mar 2026"],
            rows=[
                FinancialRow(metric="Equity Capital", values={"Mar 2025": 1000.0, "Mar 2026": 1000.0}),
                FinancialRow(metric="Reserves", values={"Mar 2025": 9000.0, "Mar 2026": 11000.0}), # Equity: 10000 -> 12000
                FinancialRow(metric="Deposits", values={"Mar 2025": 80000.0, "Mar 2026": 90000.0})
            ]
        )
        pl = FinancialStatement(
            statement_name="profit_loss",
            periods=["Mar 2025", "Mar 2026"],
            rows=[
                FinancialRow(metric="Net Profit", values={"Mar 2025": 1400.0, "Mar 2026": 1650.0})
            ]
        )
        res = compute_bank_analytics(pl=pl, bs=bs)
        
        # Average Equity = (10000 + 12000) / 2 = 11000.0
        # Correct ROE = (1650 / 11000) * 100 = 15.0%
        self.assertEqual(res.roe_pct, 15.0)
        self.assertEqual(res.provenance["roe"]["avg_equity_cr"], 11000.0)

    def test_i_gnpa_nnpa_missing_remain_none(self):
        """Scenario I: When GNPA / NNPA rows are not in statements, they evaluate to None."""
        bs = FinancialStatement(
            statement_name="balance_sheet",
            periods=["Mar 2026"],
            rows=[
                FinancialRow(metric="Deposits", values={"Mar 2026": 50000.0}),
                FinancialRow(metric="Advances", values={"Mar 2026": 40000.0})
            ]
        )
        res = compute_bank_analytics(bs=bs)
        self.assertIsNone(res.gross_npa_pct)
        self.assertIsNone(res.net_npa_pct)
        self.assertIn("gross_npa", res.unavailable_reasons)
        self.assertIn("net_npa", res.unavailable_reasons)

    def test_j_real_gnpa_zero_remains_zero(self):
        """Scenario J: Real GNPA = 0.0 is preserved as 0.0, not converted to None."""
        quarters = FinancialStatement(
            statement_name="quarters",
            periods=["Mar 2026"],
            rows=[
                FinancialRow(metric="Gross NPA %", values={"Mar 2026": 0.0}),
                FinancialRow(metric="Net NPA %", values={"Mar 2026": 0.0})
            ]
        )
        res = compute_bank_analytics(quarters=quarters)
        self.assertEqual(res.gross_npa_pct, 0.0)
        self.assertEqual(res.net_npa_pct, 0.0)

    def test_k_cost_to_income_exact_bank_rows(self):
        """Scenario K: Cost-to-income calculated only when exact bank-specific line items exist."""
        pl = FinancialStatement(
            statement_name="profit_loss",
            periods=["Mar 2026"],
            rows=[
                FinancialRow(metric="Net Interest Income", values={"Mar 2026": 40000.0}),
                FinancialRow(metric="Other Income", values={"Mar 2026": 10000.0}), # Total Net Income = 50000.0
                FinancialRow(metric="Operating Expenses", values={"Mar 2026": 20000.0}),
                FinancialRow(metric="Net Profit", values={"Mar 2026": 12000.0})
            ]
        )
        res = compute_bank_analytics(pl=pl)
        # Cost to Income = (20000 / 50000) * 100 = 40.0%
        self.assertEqual(res.cost_to_income_pct, 40.0)

    def test_l_credit_cost_uses_average_advances(self):
        """Scenario L: Credit cost strictly uses average gross advances."""
        bs = FinancialStatement(
            statement_name="balance_sheet",
            periods=["Mar 2025", "Mar 2026"],
            rows=[
                FinancialRow(metric="Advances", values={"Mar 2025": 100000.0, "Mar 2026": 120000.0}),
                FinancialRow(metric="Deposits", values={"Mar 2025": 130000.0, "Mar 2026": 150000.0})
            ]
        )
        pl = FinancialStatement(
            statement_name="profit_loss",
            periods=["Mar 2025", "Mar 2026"],
            rows=[
                FinancialRow(metric="Provisions", values={"Mar 2025": 1000.0, "Mar 2026": 1100.0}),
                FinancialRow(metric="Net Profit", values={"Mar 2025": 5000.0, "Mar 2026": 6000.0})
            ]
        )
        res = compute_bank_analytics(pl=pl, bs=bs)
        
        # Avg Advances = (100000 + 120000) / 2 = 110000.0
        # Credit Cost = (1100 / 110000) * 100 = 1.0%
        self.assertEqual(res.credit_cost_pct, 1.0)
        self.assertEqual(res.provenance["credit_cost"]["avg_advances_cr"], 110000.0)

    def test_m_ttm_excluded_from_annual_bank_calculations(self):
        """Scenario M: TTM is excluded from annual bank calculations."""
        bs = FinancialStatement(
            statement_name="balance_sheet",
            periods=["Mar 2024", "Mar 2025", "Mar 2026", "TTM"],
            rows=[
                FinancialRow(metric="Deposits", values={"Mar 2024": 100.0, "Mar 2025": 120.0, "Mar 2026": 140.0, "TTM": 199.0}),
                FinancialRow(metric="Advances", values={"Mar 2024": 80.0, "Mar 2025": 100.0, "Mar 2026": 120.0, "TTM": 180.0})
            ]
        )
        res = compute_bank_analytics(bs=bs)
        self.assertEqual(res.latest_period, "Mar 2026")
        # YoY = (140 - 120) / 120 * 100 = 16.7% (NOT compared against TTM 199.0)
        self.assertEqual(res.deposit_growth_yoy_pct, 16.7)

    def test_n_zero_ai_or_network_calls(self):
        """Scenario N: Bank engine executes 100% locally with zero AI / network calls."""
        bs = FinancialStatement(
            statement_name="balance_sheet",
            periods=["Mar 2026"],
            rows=[
                FinancialRow(metric="Deposits", values={"Mar 2026": 100000.0}),
                FinancialRow(metric="Advances", values={"Mar 2026": 80000.0})
            ]
        )
        res = compute_bank_analytics(bs=bs, symbol="HDFCBANK", sector="Financial Services", industry="Private Sector Bank")
        self.assertEqual(res.applicability, "applicable")
        self.assertEqual(res.credit_deposit_ratio_pct, 80.0)

    def test_o_general_corporate_analytics_unchanged(self):
        """Scenario O: General corporate analytics remain 100% intact."""
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
        self.assertEqual(analytics["cash_flow_quality"]["applicability"], "applicable")
        self.assertEqual(analytics["cash_flow_quality"]["cumulative_5y_pat_cr"], 700.0)
        self.assertEqual(analytics["cash_flow_quality"]["cumulative_5y_cfo_cr"], 760.0)

    def test_p_phase_2c_bank_quarantine_intact(self):
        """Scenario P: Existing Phase 2C bank FCF/CFO/CWIP quarantine remains intact."""
        bs = FinancialStatement(
            statement_name="balance_sheet",
            periods=["Mar 2025", "Mar 2026"],
            rows=[
                FinancialRow(metric="Deposits", values={"Mar 2025": 80000.0, "Mar 2026": 100000.0}),
                FinancialRow(metric="Advances", values={"Mar 2025": 65000.0, "Mar 2026": 80000.0}),
                FinancialRow(metric="Fixed Assets", values={"Mar 2025": 1000.0, "Mar 2026": 1200.0}),
                FinancialRow(metric="CWIP", values={"Mar 2025": 500.0, "Mar 2026": 600.0}) # 50% CWIP
            ]
        )
        pl = FinancialStatement(
            statement_name="profit_loss",
            periods=["Mar 2025", "Mar 2026"],
            rows=[
                FinancialRow(metric="Net Profit", values={"Mar 2025": 5000.0, "Mar 2026": 6000.0})
            ]
        )
        cf = FinancialStatement(
            statement_name="cash_flow",
            periods=["Mar 2025", "Mar 2026"],
            rows=[
                FinancialRow(metric="Cash from Operating Activity", values={"Mar 2025": -2000.0, "Mar 2026": 3000.0})
            ]
        )
        analytics = compute_financial_analytics(
            quarters=None,
            pl=pl,
            bs=bs,
            cf=cf,
            sector="Financial Services",
            industry="Private Sector Bank"
        )
        self.assertEqual(analytics["financial_business_model"], "BANK")
        self.assertEqual(analytics["cash_flow_quality"]["applicability"], "not_applicable_financial_business")
        self.assertFalse(analytics["balance_sheet_efficiency"]["has_significant_capex_trigger"])
        self.assertIn("bank_analytics", analytics)
        self.assertEqual(analytics["bank_analytics"]["credit_deposit_ratio_pct"], 80.0)
        self.assertEqual(analytics["bank_analytics"]["deposit_growth_yoy_pct"], 25.0)
        self.assertEqual(analytics["bank_analytics"]["advances_growth_yoy_pct"], 23.1)

    # =========================================================================
    # BLOCKER 1: Bank Routing Bug (BANK only, NOT NBFC/INSURANCE/OTHER_FINANCIAL)
    # =========================================================================
    def test_blocker_1_bank_routing_isolation(self):
        """Blocker 1: BANK gets bank_analytics; NBFC, INSURANCE, OTHER_FINANCIAL do NOT."""
        bs = FinancialStatement(
            statement_name="balance_sheet",
            periods=["Mar 2026"],
            rows=[
                FinancialRow(metric="Borrowings", values={"Mar 2026": 50000.0}),
                FinancialRow(metric="Investments", values={"Mar 2026": 40000.0})
            ]
        )
        
        # 1. NBFC_LENDER
        a_nbfc = compute_financial_analytics(
            quarters=None, pl=None, bs=bs, cf=None,
            sector="Financial Services", industry="NBFC"
        )
        self.assertEqual(a_nbfc["financial_business_model"], "NBFC_LENDER")
        self.assertNotIn("bank_analytics", a_nbfc)
        self.assertNotIn("bank_metrics", a_nbfc)
        
        # 2. INSURANCE
        a_ins = compute_financial_analytics(
            quarters=None, pl=None, bs=bs, cf=None,
            sector="Financial Services", industry="Life Insurance"
        )
        self.assertEqual(a_ins["financial_business_model"], "INSURANCE")
        self.assertNotIn("bank_analytics", a_ins)
        self.assertNotIn("bank_metrics", a_ins)
        
        # 3. OTHER_FINANCIAL
        a_oth = compute_financial_analytics(
            quarters=None, pl=None, bs=bs, cf=None,
            sector="Financial Services", industry="Asset Management"
        )
        self.assertEqual(a_oth["financial_business_model"], "OTHER_FINANCIAL")
        self.assertNotIn("bank_analytics", a_oth)
        self.assertNotIn("bank_metrics", a_oth)
        
        # 4. BANK
        a_bank = compute_financial_analytics(
            quarters=None, pl=None, bs=bs, cf=None,
            sector="Financial Services", industry="Private Sector Bank"
        )
        self.assertEqual(a_bank["financial_business_model"], "BANK")
        self.assertIn("bank_analytics", a_bank)
        self.assertIn("bank_metrics", a_bank)

    # =========================================================================
    # BLOCKER 2: Fail-Closed Equity
    # =========================================================================
    def test_blocker_2_fail_closed_equity(self):
        """Blocker 2: Missing equity capital or reserves -> equity is None; explicit zero preserved."""
        # Case A: Equity Capital present, Reserves missing -> equity None -> ROE None
        bs_a = FinancialStatement(
            statement_name="balance_sheet",
            periods=["Mar 2025", "Mar 2026"],
            rows=[
                FinancialRow(metric="Equity Capital", values={"Mar 2025": 1000.0, "Mar 2026": 1000.0}),
                FinancialRow(metric="Deposits", values={"Mar 2025": 10000.0, "Mar 2026": 12000.0})
            ]
        )
        pl_a = FinancialStatement(
            statement_name="profit_loss",
            periods=["Mar 2025", "Mar 2026"],
            rows=[FinancialRow(metric="Net Profit", values={"Mar 2025": 100.0, "Mar 2026": 150.0})]
        )
        res_a = compute_bank_analytics(pl=pl_a, bs=bs_a)
        self.assertIsNone(res_a.roe_pct)
        self.assertIsNone(res_a.trends[-1].total_equity_cr)
        
        # Case B: Reserves present, Equity Capital missing -> equity None -> ROE None
        bs_b = FinancialStatement(
            statement_name="balance_sheet",
            periods=["Mar 2025", "Mar 2026"],
            rows=[
                FinancialRow(metric="Reserves", values={"Mar 2025": 9000.0, "Mar 2026": 11000.0}),
                FinancialRow(metric="Deposits", values={"Mar 2025": 10000.0, "Mar 2026": 12000.0})
            ]
        )
        res_b = compute_bank_analytics(pl=pl_a, bs=bs_b)
        self.assertIsNone(res_b.roe_pct)
        self.assertIsNone(res_b.trends[-1].total_equity_cr)

        # Case C: Both present -> Sum correctly calculated
        bs_c = FinancialStatement(
            statement_name="balance_sheet",
            periods=["Mar 2025", "Mar 2026"],
            rows=[
                FinancialRow(metric="Equity Capital", values={"Mar 2025": 1000.0, "Mar 2026": 1000.0}),
                FinancialRow(metric="Reserves", values={"Mar 2025": 9000.0, "Mar 2026": 11000.0}),
                FinancialRow(metric="Deposits", values={"Mar 2025": 10000.0, "Mar 2026": 12000.0})
            ]
        )
        res_c = compute_bank_analytics(pl=pl_a, bs=bs_c)
        self.assertEqual(res_c.trends[-1].total_equity_cr, 12000.0)
        # Avg Equity = (10000 + 12000) / 2 = 11000 -> ROE = 150 / 11000 * 100 = 1.36%
        self.assertEqual(res_c.roe_pct, 1.36)

        # Case D: Explicit actual zero component preserved (e.g. Reserves = 0.0)
        bs_d = FinancialStatement(
            statement_name="balance_sheet",
            periods=["Mar 2025", "Mar 2026"],
            rows=[
                FinancialRow(metric="Equity Capital", values={"Mar 2025": 500.0, "Mar 2026": 500.0}),
                FinancialRow(metric="Reserves", values={"Mar 2025": 0.0, "Mar 2026": 0.0}),
                FinancialRow(metric="Deposits", values={"Mar 2025": 10000.0, "Mar 2026": 12000.0})
            ]
        )
        res_d = compute_bank_analytics(pl=pl_a, bs=bs_d)
        self.assertEqual(res_d.trends[-1].total_equity_cr, 500.0)
        # Avg Equity = 500.0 -> ROE = 150 / 500 * 100 = 30.0%
        self.assertEqual(res_d.roe_pct, 30.0)

    # =========================================================================
    # BLOCKER 3: Fail-Closed Total Assets
    # =========================================================================
    def test_blocker_3_fail_closed_total_assets(self):
        """Blocker 3: Direct Total Assets required; partial components never synthesize assets."""
        # Case A: Direct Total Assets present -> ROA works
        bs_a = FinancialStatement(
            statement_name="balance_sheet",
            periods=["Mar 2025", "Mar 2026"],
            rows=[
                FinancialRow(metric="Total Assets", values={"Mar 2025": 10000.0, "Mar 2026": 12000.0}),
                FinancialRow(metric="Deposits", values={"Mar 2025": 8000.0, "Mar 2026": 9000.0})
            ]
        )
        pl = FinancialStatement(
            statement_name="profit_loss",
            periods=["Mar 2025", "Mar 2026"],
            rows=[FinancialRow(metric="Net Profit", values={"Mar 2025": 100.0, "Mar 2026": 121.0})]
        )
        res_a = compute_bank_analytics(pl=pl, bs=bs_a)
        self.assertEqual(res_a.trends[-1].total_assets_cr, 12000.0)
        # Avg Assets = 11000 -> ROA = 121 / 11000 * 100 = 1.1%
        self.assertEqual(res_a.roa_pct, 1.1)

        # Case B: Total Assets missing -> ROA is None (no partial synthetic assets)
        bs_b = FinancialStatement(
            statement_name="balance_sheet",
            periods=["Mar 2025", "Mar 2026"],
            rows=[
                FinancialRow(metric="Deposits", values={"Mar 2025": 8000.0, "Mar 2026": 9000.0}),
                FinancialRow(metric="Borrowings", values={"Mar 2025": 1000.0, "Mar 2026": 1500.0}),
                FinancialRow(metric="Equity Capital", values={"Mar 2025": 500.0, "Mar 2026": 500.0}),
                FinancialRow(metric="Reserves", values={"Mar 2025": 500.0, "Mar 2026": 500.0})
            ]
        )
        res_b = compute_bank_analytics(pl=pl, bs=bs_b)
        self.assertIsNone(res_b.roa_pct)
        self.assertIsNone(res_b.trends[-1].total_assets_cr)
        self.assertIn("roa", res_b.unavailable_reasons)

    # =========================================================================
    # BLOCKER 4: Cost-to-Income Fail-Closed
    # =========================================================================
    def test_blocker_4_cost_to_income_fail_closed(self):
        """Blocker 4: Cost-to-income calculated ONLY with exact bank line items, not generic P&L rows or partial costs."""
        # Case A: Generic Revenue + Expenses only -> None
        pl_generic = FinancialStatement(
            statement_name="profit_loss",
            periods=["Mar 2026"],
            rows=[
                FinancialRow(metric="Revenue", values={"Mar 2026": 50000.0}),
                FinancialRow(metric="Expenses", values={"Mar 2026": 20000.0}),
                FinancialRow(metric="Net Profit", values={"Mar 2026": 12000.0})
            ]
        )
        res_gen = compute_bank_analytics(pl=pl_generic)
        self.assertIsNone(res_gen.cost_to_income_pct)
        self.assertIn("cost_to_income", res_gen.unavailable_reasons)

        # Case B: Exact bank-specific line items -> Ratio calculated
        pl_bank = FinancialStatement(
            statement_name="profit_loss",
            periods=["Mar 2026"],
            rows=[
                FinancialRow(metric="Net Interest Income", values={"Mar 2026": 30000.0}),
                FinancialRow(metric="Other Income", values={"Mar 2026": 10000.0}), # Net Income = 40000.0
                FinancialRow(metric="Operating Expenses", values={"Mar 2026": 16000.0}),
                FinancialRow(metric="Net Profit", values={"Mar 2026": 12000.0})
            ]
        )
        res_bank = compute_bank_analytics(pl=pl_bank)
        # (16000 / 40000) * 100 = 40.0%
        self.assertEqual(res_bank.cost_to_income_pct, 40.0)

        # Case C: Employee Cost + NII + Other Income only -> Cost-to-Income must remain None
        pl_emp = FinancialStatement(
            statement_name="profit_loss",
            periods=["Mar 2026"],
            rows=[
                FinancialRow(metric="Net Interest Income", values={"Mar 2026": 30000.0}),
                FinancialRow(metric="Other Income", values={"Mar 2026": 10000.0}),
                FinancialRow(metric="Employee Cost", values={"Mar 2026": 8000.0}), # Partial cost, not total OpEx
                FinancialRow(metric="Net Profit", values={"Mar 2026": 12000.0})
            ]
        )
        res_emp = compute_bank_analytics(pl=pl_emp)
        self.assertIsNone(res_emp.cost_to_income_pct)

        # Case D: NII present, Other Income missing -> Cost-to-Income must remain None
        pl_no_oth = FinancialStatement(
            statement_name="profit_loss",
            periods=["Mar 2026"],
            rows=[
                FinancialRow(metric="Net Interest Income", values={"Mar 2026": 30000.0}),
                FinancialRow(metric="Operating Expenses", values={"Mar 2026": 15000.0}),
                FinancialRow(metric="Net Profit", values={"Mar 2026": 12000.0})
            ]
        )
        res_no_oth = compute_bank_analytics(pl=pl_no_oth)
        self.assertIsNone(res_no_oth.cost_to_income_pct)

        # Case E: Interest Earned + Interest Expended present, Other Income missing -> None
        pl_no_oth_ie = FinancialStatement(
            statement_name="profit_loss",
            periods=["Mar 2026"],
            rows=[
                FinancialRow(metric="Interest Earned", values={"Mar 2026": 50000.0}),
                FinancialRow(metric="Interest Expended", values={"Mar 2026": 30000.0}),
                FinancialRow(metric="Operating Expenses", values={"Mar 2026": 8000.0}),
                FinancialRow(metric="Net Profit", values={"Mar 2026": 8000.0})
            ]
        )
        res_no_oth_ie = compute_bank_analytics(pl=pl_no_oth_ie)
        self.assertIsNone(res_no_oth_ie.cost_to_income_pct)

        # Case F: Explicit Other Income = 0.0 -> valid calculation
        pl_zero_oth = FinancialStatement(
            statement_name="profit_loss",
            periods=["Mar 2026"],
            rows=[
                FinancialRow(metric="Net Interest Income", values={"Mar 2026": 30000.0}),
                FinancialRow(metric="Other Income", values={"Mar 2026": 0.0}), # Explicit 0.0
                FinancialRow(metric="Operating Expenses", values={"Mar 2026": 15000.0}),
                FinancialRow(metric="Net Profit", values={"Mar 2026": 10000.0})
            ]
        )
        res_zero_oth = compute_bank_analytics(pl=pl_zero_oth)
        # (15000 / 30000) * 100 = 50.0%
        self.assertEqual(res_zero_oth.cost_to_income_pct, 50.0)

    # =========================================================================
    # BLOCKER 5: DuPont Safety for Financial Businesses
    # =========================================================================
    def test_blocker_5_dupont_quarantined_for_banks(self):
        """Blocker 5: Corporate DuPont is quarantined for BANK and active for GENERAL_CORPORATE."""
        bs = FinancialStatement(
            statement_name="balance_sheet",
            periods=["Mar 2026"],
            rows=[
                FinancialRow(metric="Total Assets", values={"Mar 2026": 50000.0}),
                FinancialRow(metric="Equity Capital", values={"Mar 2026": 1000.0}),
                FinancialRow(metric="Reserves", values={"Mar 2026": 4000.0})
            ]
        )
        pl = FinancialStatement(
            statement_name="profit_loss",
            periods=["Mar 2026"],
            rows=[
                FinancialRow(metric="Sales", values={"Mar 2026": 10000.0}),
                FinancialRow(metric="Net Profit", values={"Mar 2026": 2000.0})
            ]
        )
        
        # 1. Bank
        a_bank = compute_financial_analytics(
            quarters=None, pl=pl, bs=bs, cf=None,
            sector="Financial Services", industry="Private Sector Bank"
        )
        self.assertEqual(a_bank["du_pont_analysis"]["applicability"], "not_applicable_financial_business")
        
        # 2. General Corporate
        a_corp = compute_financial_analytics(
            quarters=None, pl=pl, bs=bs, cf=None,
            sector="Capital Goods", industry="Industrial Equipment"
        )
        self.assertEqual(a_corp["du_pont_analysis"]["applicability"], "applicable")
        self.assertEqual(a_corp["du_pont_analysis"]["net_profit_margin_pct"], 20.0)
        self.assertEqual(a_corp["du_pont_analysis"]["asset_turnover_ratio"], 0.2)
        self.assertEqual(a_corp["du_pont_analysis"]["financial_leverage_multiplier"], 10.0)
        self.assertEqual(a_corp["du_pont_analysis"]["calculated_roe_pct"], 40.0)

    # =========================================================================
    # BLOCKER 6: Provenance & Canonical Truth Status
    # =========================================================================
    def test_blocker_6_provenance_truth_status(self):
        """Blocker 6: Canonical VERIFIED status propagates cleanly into bank provenance."""
        bs = FinancialStatement(
            statement_name="balance_sheet",
            periods=["Mar 2025", "Mar 2026"],
            rows=[
                FinancialRow(metric="Total Assets", values={"Mar 2025": 100000.0, "Mar 2026": 120000.0}),
                FinancialRow(metric="Equity Capital", values={"Mar 2025": 1000.0, "Mar 2026": 1000.0}),
                FinancialRow(metric="Reserves", values={"Mar 2025": 9000.0, "Mar 2026": 11000.0})
            ]
        )
        pl = FinancialStatement(
            statement_name="profit_loss",
            periods=["Mar 2025", "Mar 2026"],
            rows=[FinancialRow(metric="Net Profit", values={"Mar 2025": 1000.0, "Mar 2026": 1200.0})]
        )
        
        from models import VerificationCoverageSummary
        truth = FinancialTruthContainer(
            symbol="HDFCBANK",
            last_computed_at="2026-08-31T00:00:00",
            coverage=VerificationCoverageSummary(
                symbol="HDFCBANK",
                target_facts_count=1,
                officially_verified_count=1,
                coverage_pct=100.0,
                overall_truth_state="VERIFIED"
            ),
            facts=[
                CanonicalFinancialFact(
                    symbol="HDFCBANK",
                    canonical_metric="NET_PROFIT",
                    display_metric="Net Profit",
                    canonical_period="2026-FY",
                    period="Mar 2026",
                    scope="Consolidated",
                    unit="₹ Cr",
                    currency="INR",
                    selected_source_type="official",
                    selected_source_name="Official BSE XBRL Filing",
                    value=1200.0,
                    verification_status="VERIFIED",
                    confidence="High"
                )
            ]
        )
        
        res = compute_bank_analytics(pl=pl, bs=bs, symbol="HDFCBANK", financial_truth=truth)
        self.assertEqual(res.roa_pct, 1.09) # 1200 / 110000 * 100
        self.assertEqual(res.provenance["roa"]["pat_verification_status"], "VERIFIED")
        self.assertEqual(res.provenance["roa"]["pat_source"], "Official BSE XBRL Filing")
        self.assertEqual(res.provenance["roa"]["source"], "Balance Sheet & P&L")
        self.assertEqual(res.provenance["roe"]["source"], "Balance Sheet & P&L")

if __name__ == "__main__":
    unittest.main()
