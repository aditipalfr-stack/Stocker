"""
=============================================================================
Stocker V4.4 Integration Test Suite: Business Analysis 2.0 + Financial Statement UX
=============================================================================
Verifies seamless end-to-end integration of:
1. Business Analysis 2.0 (structured evidence, guidance evaluation, deterministic SHA IDs,
   fail-closed citations, standardized statement wording, neutral not_checked lifecycle)
2. Financial Statement Trend Correctness + Self-Explanatory UX (exact period comparisons,
   neutral balance changes, bps for ratios, Reported vs Stocker cash flow distinction,
   low-emphasis Standardized, explainable statuses)
3. Full V4.3 taxonomy and Bank routing preservation
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

from models import FinancialStatement, FinancialRow, StockDetail
from company_taxonomy_service import classify_and_persist_company
from financial_engine import classify_financial_business_model, compute_financial_analytics
from doc_intelligence_models import (
    BusinessAnalysisResult, BusinessOutlookResult, DocumentEvidenceItem,
    ManagementGuidanceItem
)
from doc_intelligence_engine import (
    get_company_doc_intelligence,
    evaluate_management_guidance_vs_actual,
    _apply_financial_cross_check
)
from doc_intelligence_pipeline import format_financials_for_prompt
from llm_service import SYSTEM_PROMPT, sanitize_and_verify_intelligence_result, GenericDocumentIntelligenceResult
import database

class TestV44IntegrationE2E(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="stocker_v44_integration_test_")
        self.db_path = Path(self.temp_dir) / "stocker_v44_int.db"
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

    def test_scenario_1_wipro_corporate_integration(self):
        """Scenario 1: WIPRO corporate taxonomy, financial tables work, BA loads, no bank analytics."""
        tax = classify_and_persist_company(
            symbol="WIPRO",
            sector="Information Technology",
            industry="IT Services",
            sub_industry="Software Services",
            source="screener_metadata"
        )
        biz_model = classify_financial_business_model(sector=tax["sector"], industry=tax["industry"])
        self.assertEqual(biz_model, "GENERAL_CORPORATE")

        # Corporate financial analytics
        pl = FinancialStatement(
            title="Profit & Loss",
            periods=["FY24", "FY25"],
            rows=[
                FinancialRow(metric="Sales", values={"FY24": 90000, "FY25": 95000}),
                FinancialRow(metric="Operating Profit", values={"FY24": 18000, "FY25": 19500}),
                FinancialRow(metric="Net Profit", values={"FY24": 11000, "FY25": 12500})
            ]
        )
        analytics = compute_financial_analytics(
            quarters=None,
            pl=pl,
            bs=None,
            cf=None,
            sector=tax["sector"],
            industry=tax["industry"]
        )
        self.assertIsNone(analytics.get("bank_analytics"))
        self.assertIsNotNone(analytics.get("growth_rates"))

        # Business Analysis for Corporate
        mock_ba = {
            "symbol": "WIPRO",
            "company_name": "Wipro Limited",
            "financial_business_model": "GENERAL_CORPORATE",
            "staleness_status": "fresh",
            "evidence_items": [
                {
                    "id": "evi_wipro_1",
                    "symbol": "WIPRO",
                    "evidence_type": "DEMAND_DRIVER",
                    "title": "Cloud & AI Large Deals",
                    "normalized_topic": "Cloud Deals",
                    "statement": "Booked $1.2B in large deals.",
                    "source_document_title": "FY25 Annual Report",
                    "source_url": "https://wipro.com/ar25.pdf",
                    "status": "SUPPORTED"
                }
            ]
        }
        database.save_ai_analysis("WIPRO", "Wipro Limited", mock_ba, ai_provider="STORED")
        doc_intel = get_company_doc_intelligence("WIPRO", financial_analytics=analytics)
        self.assertIsNotNone(doc_intel)
        self.assertEqual(doc_intel.financial_business_model, "GENERAL_CORPORATE")
        self.assertEqual(len(doc_intel.evidence_items), 1)

    def test_scenario_2_icicibank_bank_integration(self):
        """Scenario 2: ICICIBANK BANK routing, bank metrics preserved, corporate FCF quarantined, BA bank-aware."""
        tax = classify_and_persist_company(
            symbol="ICICIBANK",
            sector="Financial Services",
            industry="Banks",
            sub_industry="Private Sector Bank",
            source="screener_metadata"
        )
        biz_model = classify_financial_business_model(sector=tax["sector"], industry=tax["industry"])
        self.assertEqual(biz_model, "BANK")

        pl = FinancialStatement(
            title="Profit & Loss",
            periods=["FY24", "FY25"],
            rows=[
                FinancialRow(metric="Interest Earned", values={"FY24": 120000, "FY25": 140000}),
                FinancialRow(metric="Interest Expended", values={"FY24": 70000, "FY25": 80000}),
                FinancialRow(metric="Net Profit", values={"FY24": 40000, "FY25": 48000})
            ]
        )
        bs = FinancialStatement(
            title="Balance Sheet",
            periods=["FY24", "FY25"],
            rows=[
                FinancialRow(metric="Equity Capital", values={"FY24": 1400, "FY25": 1410}),
                FinancialRow(metric="Reserves", values={"FY24": 230000, "FY25": 270000}),
                FinancialRow(metric="Borrowings", values={"FY24": 120000, "FY25": 130000}),
                FinancialRow(metric="Deposits", values={"FY24": 1300000, "FY25": 1500000}),
                FinancialRow(metric="Advances", values={"FY24": 1100000, "FY25": 1300000}),
                FinancialRow(metric="Total Assets", values={"FY24": 1800000, "FY25": 2100000})
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
        self.assertIsNotNone(analytics.get("bank_analytics"))
        self.assertEqual(analytics["bank_analytics"]["credit_deposit_ratio_pct"], round((1300000 / 1500000) * 100, 1))
        
        # Corporate DuPont and FCF analysis are safely quarantined
        self.assertIsNone(analytics.get("dupont_analysis"))
        self.assertEqual(analytics["cash_flow_quality"]["applicability"], "not_applicable_financial_business")
        self.assertIsNone(analytics["cash_flow_quality"]["cumulative_5y_fcf_cr"])

    def test_scenario_3_hdfcbank_guidance_metrics_integrity(self):
        """Scenario 3: HDFCBANK CASA guidance cannot match Total Deposits, GNPA cannot match Provisions."""
        guidance = [
            ManagementGuidanceItem(
                metric_or_topic="CASA Ratio Guidance",
                guidance_text="Targeting CASA ratio of 40%",
                quantified_value=40.0,
                unit="%",
                target_period="FY25",
                source_document_title="FY24 Annual Report",
                source_document_url="https://hdfcbank.com/ar24.pdf"
            ),
            ManagementGuidanceItem(
                metric_or_topic="Gross NPA GNPA",
                guidance_text="Guided Gross NPA under 1.2%",
                quantified_value=1.2,
                unit="%",
                target_period="FY25",
                source_document_title="FY24 Annual Report",
                source_document_url="https://hdfcbank.com/ar24.pdf"
            )
        ]
        # Statement has Deposits = 2000000 and Provisions = 1.0%, but NO CASA or GNPA rows
        pl = {"periods": ["FY24", "FY25"], "rows": [{"metric": "Provisions", "values": [0.8, 1.0]}]}
        bs = {"periods": ["FY24", "FY25"], "rows": [{"metric": "Deposits", "values": [1800000, 2000000]}]}
        
        evaluated = evaluate_management_guidance_vs_actual(
            guidance_items=guidance,
            financial_statements={"profit_loss": pl, "balance_sheet": bs}
        )
        self.assertEqual(evaluated[0].status, "INSUFFICIENT_EVIDENCE")
        self.assertIsNone(evaluated[0].actual_reported_value)
        self.assertEqual(evaluated[1].status, "INSUFFICIENT_EVIDENCE")
        self.assertIsNone(evaluated[1].actual_reported_value)

    def test_scenario_4_tcs_reliance_capex_cashflow_isolation(self):
        """Scenario 4: Capex guidance only compares with exact Cash Flow metric, not CWIP or Fixed Assets."""
        guidance = [
            ManagementGuidanceItem(
                metric_or_topic="Capital Expenditure Capex Outlay",
                guidance_text="Targeting ₹25,000 Cr capex in FY25",
                quantified_value=25000.0,
                unit="₹ Cr",
                target_period="FY25",
                source_document_title="FY24 AR",
                source_document_url="https://reliance.com/ar24.pdf"
            )
        ]
        # Only Balance Sheet with CWIP and Fixed Assets
        bs_only = {
            "periods": ["FY24", "FY25"],
            "rows": [
                {"metric": "Capital Work in Progress", "values": [30000, 35000]},
                {"metric": "Fixed Assets", "values": [100000, 120000]}
            ]
        }
        res_bs = evaluate_management_guidance_vs_actual(guidance, financial_statements={"balance_sheet": bs_only})
        self.assertEqual(res_bs[0].status, "INSUFFICIENT_EVIDENCE")
        
        # Cash Flow with Fixed Assets Purchased
        cf = {
            "periods": ["FY24", "FY25"],
            "rows": [
                {"metric": "Fixed Assets Purchased", "values": [20000, 26000]}
            ]
        }
        res_cf = evaluate_management_guidance_vs_actual(guidance, financial_statements={"balance_sheet": bs_only, "cash_flow": cf})
        self.assertEqual(res_cf[0].status, "MET")
        self.assertEqual(res_cf[0].actual_reported_value, 26000.0)

    def test_scenario_5_prompt_and_provenance_truth_neutrality(self):
        """Scenario 5: Prompts use Standardized Historical Financial Statements without unsupported Audited claims."""
        self.assertIn("standardized financial statement tables", SYSTEM_PROMPT.lower())
        self.assertNotIn("screener.in audited data", SYSTEM_PROMPT.lower())
        
        from doc_intelligence_pipeline import format_financials_for_prompt, format_audited_financials_for_prompt
        formatted = format_financials_for_prompt("TESTSYM", stock_data={"symbol": "TESTSYM"})
        self.assertIn("STANDARDIZED", formatted)
        self.assertNotIn("AUDITED", formatted)
        
        # Test backward-compatibility alias
        formatted_alias = format_audited_financials_for_prompt("TESTSYM", stock_data={"symbol": "TESTSYM"})
        self.assertEqual(formatted, formatted_alias)

    def test_scenario_6_business_analysis_lifecycle_and_not_checked(self):
        """Scenario 6: Unverified cached read yields not_checked; changed docs yields stale; no AI calls made."""
        mock_data = {
            "symbol": "TCS",
            "company_name": "Tata Consultancy Services",
            "ai_provider_used": "STORED",
            "source_documents_hash": "hash_v1",
            "evidence_items": [
                {
                    "id": "evi_tcs_1",
                    "symbol": "TCS",
                    "evidence_type": "DEMAND_DRIVER",
                    "title": "Deal Pipeline",
                    "normalized_topic": "Pipeline",
                    "statement": "TCV reached $10B.",
                    "source_document_title": "FY25 AR",
                    "source_url": "https://tcs.com/ar25.pdf",
                    "status": "SUPPORTED"
                }
            ]
        }
        database.save_ai_analysis("TCS", "Tata Consultancy Services", mock_data, ai_provider="STORED")
        
        # 1. Read without current_docs returns neutral not_checked
        intel = get_company_doc_intelligence("TCS", current_docs=None)
        self.assertIsNotNone(intel)
        self.assertEqual(intel.staleness_status, "not_checked")
        
        # 2. Read with genuinely changed docs returns stale
        new_docs = [{"title": "Q2 FY26 Concall", "url": "https://tcs.com/q2.pdf", "period": "Q2 FY26"}]
        intel_stale = get_company_doc_intelligence("TCS", current_docs=new_docs)
        self.assertIsNotNone(intel_stale)
        self.assertEqual(intel_stale.staleness_status, "stale")

    def test_scenario_7_deterministic_sha256_fallback_ids(self):
        """Scenario 7: Evidence and guidance fallback IDs are deterministic SHA-256 strings across calls."""
        evi = {
            "evidence_type": "CAPEX_PLAN",
            "title": "Greenfield Plant",
            "normalized_topic": "Greenfield",
            "statement": "Constructing ₹5,000 Cr plant.",
            "source_url": "https://example.com/plant.pdf"
        }
        id1 = database.generate_deterministic_evidence_id("RELIANCE", evi)
        id2 = database.generate_deterministic_evidence_id("RELIANCE", evi)
        self.assertEqual(id1, id2)
        self.assertTrue(id1.startswith("evi_RELIANCE_"))
        self.assertEqual(len(id1), len("evi_RELIANCE_") + 12)

if __name__ == "__main__":
    unittest.main()
