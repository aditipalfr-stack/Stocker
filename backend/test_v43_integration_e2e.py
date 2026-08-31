"""
=============================================================================
Stocker V4.3 Integration Test Suite: Dynamic Taxonomy + Bank Analytics
=============================================================================
Verifies seamless end-to-end integration of:
- Canonical Company Taxonomy
- Business Model Classification
- Deterministic Bank Analytics Tier 1
- Corporate Analytics Integrity
- Safety Quarantine for Non-Bank Financial Businesses (NBFC, Insurance)
- Taxonomy Downgrade Protection
- Strict SQLite DB Isolation (zero mutations to runtime backend/data/stocker.db)

Scenarios:
- DB Isolation check: verifies test execution strictly uses isolated temp DB
- Scenario A: WIPRO (general corporate -> GENERAL_CORPORATE, bank_analytics=None, corporate analytics active)
- Scenario B: ICICIBANK (canonical taxonomy -> BANK -> BankEngine runs, DuPont quarantined, corporate DCF suppressed)
- Scenario C: HDFCBANK (seeded bank -> normalized taxonomy -> BANK -> BankEngine routes correctly)
- Scenario D: NBFC fixture (NBFC_LENDER -> BankEngine does NOT run, bank_analytics=None, financial safety active)
- Scenario E: Insurance fixture (INSURANCE -> BankEngine does NOT run, bank_analytics=None)
- Scenario F: Taxonomy Refresh (rich existing taxonomy never downgrades on weaker/incomplete refresh)
=============================================================================
"""

import os
import shutil
import sys
import tempfile
from pathlib import Path
import unittest

os.environ["STOCKER_TEST_MODE"] = "1"
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "libs"))

from models import (
    FinancialStatement,
    FinancialRow,
    KeyRatios,
    CompanyTaxonomy,
    StockDetail,
    StockSummary
)
from company_taxonomy_service import (
    normalize_classification,
    classify_and_persist_company,
    resolve_local_company_taxonomy,
    get_company_taxonomy
)
from financial_engine import (
    classify_financial_business_model,
    compute_financial_analytics
)
from bank_engine import compute_bank_analytics
import database

class TestV43IntegrationE2E(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="stocker_e2e_integration_test_")
        self.db_path = Path(self.temp_dir) / "stocker_e2e.db"
        self.old_env = os.environ.get("STOCKER_DB_PATH")
        self.old_path = database.DB_PATH
        os.environ["STOCKER_DB_PATH"] = str(self.db_path)
        database.DB_PATH = self.db_path
        database.init_db()

    def tearDown(self):
        database.DB_PATH = self.old_path
        if self.old_env is None:
            os.environ.pop("STOCKER_DB_PATH", None)
        else:
            os.environ["STOCKER_DB_PATH"] = self.old_env
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_db_isolation_never_touches_runtime_db(self):
        """Verify test DB path is isolated and not pointing to production/runtime DB."""
        runtime_db_path = Path(__file__).parent / "data" / "stocker.db"
        self.assertNotEqual(str(database.DB_PATH), str(runtime_db_path))
        self.assertTrue(str(database.DB_PATH).startswith(self.temp_dir))
        self.assertTrue(self.db_path.exists())

    def test_scenario_a_wipro_general_corporate(self):
        """Scenario A: General corporate (WIPRO) gets canonical taxonomy, GENERAL_CORPORATE, no bank_analytics."""
        tax = classify_and_persist_company(
            symbol="WIPRO",
            sector="Information Technology",
            industry="IT Services & Consulting",
            sub_industry="Software Services",
            source="screener_metadata"
        )
        self.assertEqual(tax["sector"], "Information Technology")
        self.assertEqual(tax["industry"], "IT Services")
        self.assertEqual(tax["classification_state"], "COMPLETE")
        
        # Route to business model
        biz_model = classify_financial_business_model(sector=tax["sector"], industry=tax["industry"])
        self.assertEqual(biz_model, "GENERAL_CORPORATE")
        
        # Financial analytics
        pl = FinancialStatement(
            statement_name="profit_loss",
            periods=["Mar 2022", "Mar 2023", "Mar 2024", "Mar 2025", "Mar 2026"],
            rows=[
                FinancialRow(metric="Sales", values={"Mar 2022": 79000, "Mar 2023": 90000, "Mar 2024": 89000, "Mar 2025": 89500, "Mar 2026": 92000}),
                FinancialRow(metric="Net Profit", values={"Mar 2022": 12200, "Mar 2023": 11300, "Mar 2024": 11000, "Mar 2025": 11200, "Mar 2026": 11800})
            ]
        )
        cf = FinancialStatement(
            statement_name="cash_flow",
            periods=["Mar 2022", "Mar 2023", "Mar 2024", "Mar 2025", "Mar 2026"],
            rows=[
                FinancialRow(metric="Cash from Operating Activity", values={"Mar 2022": 11000, "Mar 2023": 13000, "Mar 2024": 14000, "Mar 2025": 15000, "Mar 2026": 16000}),
                FinancialRow(metric="Fixed assets purchased", values={"Mar 2022": -2000, "Mar 2023": -2500, "Mar 2024": -2000, "Mar 2025": -1800, "Mar 2026": -2200})
            ]
        )
        bs = FinancialStatement(
            statement_name="balance_sheet",
            periods=["Mar 2022", "Mar 2023", "Mar 2024", "Mar 2025", "Mar 2026"],
            rows=[
                FinancialRow(metric="Total Assets", values={"Mar 2022": 70000, "Mar 2023": 80000, "Mar 2024": 85000, "Mar 2025": 90000, "Mar 2026": 95000}),
                FinancialRow(metric="Equity Capital", values={"Mar 2022": 1000, "Mar 2023": 1000, "Mar 2024": 1000, "Mar 2025": 1000, "Mar 2026": 1000}),
                FinancialRow(metric="Reserves", values={"Mar 2022": 50000, "Mar 2023": 55000, "Mar 2024": 60000, "Mar 2025": 65000, "Mar 2026": 70000})
            ]
        )
        analytics = compute_financial_analytics(
            quarters=None,
            pl=pl,
            bs=bs,
            cf=cf,
            sector=tax["sector"],
            industry=tax["industry"]
        )
        self.assertEqual(analytics["financial_business_model"], "GENERAL_CORPORATE")
        self.assertNotIn("bank_analytics", analytics)
        self.assertNotIn("bank_metrics", analytics)
        self.assertEqual(analytics["cash_flow_quality"]["applicability"], "applicable")
        self.assertEqual(analytics["du_pont_analysis"]["applicability"], "applicable")

    def test_scenario_b_icicibank_routing_and_quarantine(self):
        """Scenario B: ICICIBANK gets Financial Services taxonomy -> BANK -> BankEngine runs, DuPont quarantined."""
        tax = classify_and_persist_company(
            symbol="ICICIBANK",
            sector="Financial Services",
            industry="Private Sector Bank",
            source="screener_metadata"
        )
        self.assertEqual(tax["sector"], "Financial Services")
        self.assertEqual(tax["industry"], "Private Sector Banks")
        
        # Route to business model
        biz_model = classify_financial_business_model(sector=tax["sector"], industry=tax["industry"])
        self.assertEqual(biz_model, "BANK")
        
        # Bank statements
        bs = FinancialStatement(
            statement_name="balance_sheet",
            periods=["Mar 2025", "Mar 2026"],
            rows=[
                FinancialRow(metric="Total Assets", values={"Mar 2025": 2000000.0, "Mar 2026": 2300000.0}),
                FinancialRow(metric="Deposits", values={"Mar 2025": 1400000.0, "Mar 2026": 1600000.0}),
                FinancialRow(metric="Advances", values={"Mar 2025": 1200000.0, "Mar 2026": 1400000.0}),
                FinancialRow(metric="Equity Capital", values={"Mar 2025": 1400.0, "Mar 2026": 1400.0}),
                FinancialRow(metric="Reserves", values={"Mar 2025": 240000.0, "Mar 2026": 280000.0})
            ]
        )
        pl = FinancialStatement(
            statement_name="profit_loss",
            periods=["Mar 2025", "Mar 2026"],
            rows=[
                FinancialRow(metric="Net Interest Income", values={"Mar 2025": 75000.0, "Mar 2026": 85000.0}),
                FinancialRow(metric="Other Income", values={"Mar 2025": 25000.0, "Mar 2026": 30000.0}),
                FinancialRow(metric="Operating Expenses", values={"Mar 2025": 40000.0, "Mar 2026": 46000.0}),
                FinancialRow(metric="Provisions", values={"Mar 2025": 6000.0, "Mar 2026": 5500.0}),
                FinancialRow(metric="Net Profit", values={"Mar 2025": 40000.0, "Mar 2026": 48000.0}),
                FinancialRow(metric="Gross NPA %", values={"Mar 2025": 2.2, "Mar 2026": 1.9}),
                FinancialRow(metric="Net NPA %", values={"Mar 2025": 0.45, "Mar 2026": 0.40})
            ]
        )
        analytics = compute_financial_analytics(
            quarters=None,
            pl=pl,
            bs=bs,
            cf=None,
            sector=tax["sector"],
            industry=tax["industry"]
        )
        self.assertEqual(analytics["financial_business_model"], "BANK")
        self.assertIn("bank_analytics", analytics)
        self.assertIn("bank_metrics", analytics)
        
        bank_an = analytics["bank_analytics"]
        self.assertEqual(bank_an["applicability"], "applicable")
        self.assertEqual(bank_an["deposit_growth_yoy_pct"], 14.3) # (1600000 - 1400000) / 1400000 * 100
        self.assertEqual(bank_an["advances_growth_yoy_pct"], 16.7) # (1400000 - 1200000) / 1200000 * 100
        self.assertEqual(bank_an["credit_deposit_ratio_pct"], 87.5) # 1400000 / 1600000 * 100
        # Avg Assets = 2150000 -> ROA = 48000 / 2150000 * 100 = 2.23%
        self.assertEqual(bank_an["roa_pct"], 2.23)
        # Avg Equity = (241400 + 281400) / 2 = 261400 -> ROE = 48000 / 261400 * 100 = 18.36%
        self.assertEqual(bank_an["roe_pct"], 18.36)
        self.assertEqual(bank_an["gross_npa_pct"], 1.9)
        self.assertEqual(bank_an["net_npa_pct"], 0.4)
        # Net Income = 85000 + 30000 = 115000 -> Cost-to-Income = 46000 / 115000 * 100 = 40.0%
        self.assertEqual(bank_an["cost_to_income_pct"], 40.0)
        # Avg Advances = 1300000 -> Credit Cost = 5500 / 1300000 * 100 = 0.42%
        self.assertEqual(bank_an["credit_cost_pct"], 0.42)
        
        # Quarantines active
        self.assertEqual(analytics["cash_flow_quality"]["applicability"], "not_applicable_financial_business")
        self.assertEqual(analytics["du_pont_analysis"]["applicability"], "not_applicable_financial_business")

    def test_scenario_c_hdfcbank_seed_normalization(self):
        """Scenario C: Seeded HDFCBANK metadata normalizes to canonical taxonomy and routes to BankEngine."""
        sec, ind, sub, state = normalize_classification(
            sector="Financials",
            industry="Banks - Private"
        )
        self.assertEqual(sec, "Financial Services")
        self.assertEqual(ind, "Private Sector Banks")
        biz_model = classify_financial_business_model(sector=sec, industry=ind)
        self.assertEqual(biz_model, "BANK")

    def test_scenario_d_nbfc_fixture(self):
        """Scenario D: NBFC routes to NBFC_LENDER, does NOT execute BankEngine, and keeps safety active."""
        tax = classify_and_persist_company(
            symbol="BAJFINANCE",
            sector="Financial Services",
            industry="NBFC",
            source="screener_metadata"
        )
        self.assertEqual(tax["sector"], "Financial Services")
        biz_model = classify_financial_business_model(sector=tax["sector"], industry=tax["industry"])
        self.assertEqual(biz_model, "NBFC_LENDER")
        
        bs = FinancialStatement(
            statement_name="balance_sheet",
            periods=["Mar 2026"],
            rows=[
                FinancialRow(metric="Borrowings", values={"Mar 2026": 200000.0}),
                FinancialRow(metric="Investments", values={"Mar 2026": 50000.0})
            ]
        )
        analytics = compute_financial_analytics(
            quarters=None, pl=None, bs=bs, cf=None,
            sector=tax["sector"], industry=tax["industry"]
        )
        self.assertEqual(analytics["financial_business_model"], "NBFC_LENDER")
        self.assertNotIn("bank_analytics", analytics)
        self.assertNotIn("bank_metrics", analytics)
        self.assertEqual(analytics["cash_flow_quality"]["applicability"], "not_applicable_financial_business")
        self.assertEqual(analytics["du_pont_analysis"]["applicability"], "not_applicable_financial_business")

    def test_scenario_e_insurance_fixture(self):
        """Scenario E: Insurance routes to INSURANCE, does NOT execute BankEngine."""
        tax = classify_and_persist_company(
            symbol="HDFCLIFE",
            sector="Financial Services",
            industry="Life Insurance",
            source="screener_metadata"
        )
        self.assertEqual(tax["sector"], "Financial Services")
        biz_model = classify_financial_business_model(sector=tax["sector"], industry=tax["industry"])
        self.assertEqual(biz_model, "INSURANCE")
        
        analytics = compute_financial_analytics(
            quarters=None, pl=None, bs=None, cf=None,
            sector=tax["sector"], industry=tax["industry"]
        )
        self.assertEqual(analytics["financial_business_model"], "INSURANCE")
        self.assertNotIn("bank_analytics", analytics)
        self.assertNotIn("bank_metrics", analytics)
        self.assertEqual(analytics["cash_flow_quality"]["applicability"], "not_applicable_financial_business")
        self.assertEqual(analytics["du_pont_analysis"]["applicability"], "not_applicable_financial_business")

    def test_scenario_f_taxonomy_downgrade_protection(self):
        """Scenario F: Existing rich taxonomy does NOT downgrade on weaker refresh."""
        # 1. Establish strong classification
        classify_and_persist_company(
            symbol="TESTBANK",
            sector="Financial Services",
            industry="Private Sector Bank",
            sub_industry="Large Cap Commercial Bank",
            source="screener_metadata"
        )
        
        # 2. Attempt weak refresh with unknown source
        classify_and_persist_company(
            symbol="TESTBANK",
            sector="Unclassified",
            industry="Unclassified",
            sub_industry=None,
            source="unknown"
        )
        
        preserved = get_company_taxonomy("TESTBANK")
        self.assertEqual(preserved["sector"], "Financial Services")
        self.assertEqual(preserved["industry"], "Private Sector Banks")
        self.assertEqual(preserved["sub_industry"], "Large Cap Commercial Bank")
        self.assertEqual(preserved["classification_state"], "COMPLETE")

if __name__ == "__main__":
    unittest.main()
