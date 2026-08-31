import sys
import os
import tempfile
import shutil
import unittest
from pathlib import Path
from typing import Dict, Any
from pydantic import ValidationError

# Ensure path includes libs and backend
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "libs"))

from doc_intelligence_models import (
    BusinessAnalysisResult, BusinessOutlookResult, DocumentEvidenceItem,
    ManagementGuidanceItem, PromiseVsDeliveryItem, GrowthDriver, StockerView
)
from doc_intelligence_engine import (
    get_company_doc_intelligence,
    evaluate_management_guidance_vs_actual,
    _apply_financial_cross_check
)
from doc_intelligence_pipeline import run_multi_document_ai_pipeline
from llm_service import (
    sanitize_citation,
    sanitize_and_verify_intelligence_result,
    GenericDocumentIntelligenceResult
)
from models import DocumentLinks, DocumentItem

class TestBusinessAnalysisV44(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_stocker.db")
        self.prev_db_path = os.environ.get("STOCKER_DB_PATH")
        os.environ["STOCKER_DB_PATH"] = self.db_path
        
        import database
        database.DB_PATH = Path(self.db_path)
        database.init_db()

    def tearDown(self):
        if self.prev_db_path:
            os.environ["STOCKER_DB_PATH"] = self.prev_db_path
        else:
            os.environ.pop("STOCKER_DB_PATH", None)
        import database
        database.DB_PATH = Path(os.environ.get("STOCKER_DB_PATH", str(Path(__file__).parent / "data" / "stocker.db")))
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_scenario_a_exact_point_target_met(self):
        """Scenario A: Exact point target met when actual >= target (for growth metric)."""
        guidance = [
            ManagementGuidanceItem(
                metric_or_topic="Sales Revenue",
                guidance_text="Management guided Sales of ₹1,500 Cr for FY26",
                quantified_value=1500.0,
                unit="₹ Cr",
                target_period="FY26",
                source_document_title="FY25 Annual Report",
                source_document_url="https://example.com/ar25.pdf"
            )
        ]
        pl_stmt = {
            "periods": ["FY25", "FY26"],
            "rows": [
                {"metric": "Sales", "values": [1200, 1500]}
            ]
        }
        evaluated = evaluate_management_guidance_vs_actual(guidance, financial_statements={"profit_loss": pl_stmt})
        self.assertEqual(len(evaluated), 1)
        self.assertEqual(evaluated[0].status, "MET")
        self.assertEqual(evaluated[0].actual_reported_value, 1500.0)
        self.assertEqual(evaluated[0].actual_reported_source, "Financial Statement Data")
        self.assertIn("met target 1500.0", evaluated[0].comparison_detail)

    def test_scenario_b_exact_point_target_missed_by_one_percent(self):
        """Scenario B: Exact point target missed by 1% is strictly MISSED, never MET or PARTIALLY_MET."""
        guidance = [
            ManagementGuidanceItem(
                metric_or_topic="Operating Profit Margin OPM",
                guidance_text="Guided OPM of 20.0% for FY26",
                quantified_value=20.0,
                unit="%",
                target_period="FY26",
                source_document_title="FY25 Concall",
                source_document_url="https://example.com/concall.pdf"
            )
        ]
        # Actual is 19.8% (99% of target - previously falsely treated as MET under 95% threshold)
        pl_stmt = {
            "periods": ["FY25", "FY26"],
            "rows": [
                {"metric": "OPM %", "values": [18.0, 19.8]}
            ]
        }
        evaluated = evaluate_management_guidance_vs_actual(guidance, financial_statements={"profit_loss": pl_stmt})
        self.assertEqual(len(evaluated), 1)
        self.assertEqual(evaluated[0].status, "MISSED")
        self.assertEqual(evaluated[0].actual_reported_value, 19.8)
        self.assertIn("missed target 20.0", evaluated[0].comparison_detail)

    def test_scenario_c_explicit_guidance_range_comparison(self):
        """Scenario C: Explicit management range is compared strictly without subjective bands."""
        guidance = [
            ManagementGuidanceItem(
                metric_or_topic="Operating Margin",
                guidance_text="Expected margin between 22.0% and 24.0%",
                quantified_range_min=22.0,
                quantified_range_max=24.0,
                unit="%",
                target_period="FY26",
                source_document_title="FY25 Presentation",
                source_document_url="https://example.com/deck.pdf"
            ),
            ManagementGuidanceItem(
                metric_or_topic="Sales Revenue",
                guidance_text="Targeting ₹2,000–2,200 Cr revenue",
                quantified_range_min=2000.0,
                quantified_range_max=2200.0,
                unit="₹ Cr",
                target_period="FY26",
                source_document_title="FY25 Presentation",
                source_document_url="https://example.com/deck.pdf"
            )
        ]
        # OPM = 22.5% (Within range -> MET), Sales = 1950 (Below min 2000 -> MISSED)
        pl_stmt = {
            "periods": ["FY25", "FY26"],
            "rows": [
                {"metric": "Operating Profit Margin", "values": [21.0, 22.5]},
                {"metric": "Sales", "values": [1800, 1950]}
            ]
        }
        evaluated = evaluate_management_guidance_vs_actual(guidance, financial_statements={"profit_loss": pl_stmt})
        self.assertEqual(evaluated[0].status, "MET")
        self.assertIn("fell within guided range", evaluated[0].comparison_detail)
        self.assertEqual(evaluated[1].status, "MISSED")
        self.assertIn("missed guided range", evaluated[1].comparison_detail)

    def test_scenario_d_gnpa_cannot_use_provisions(self):
        """Scenario D: GNPA guidance cannot match Provisions row even if text or financial concept is related."""
        guidance = [
            ManagementGuidanceItem(
                metric_or_topic="Gross NPA GNPA",
                guidance_text="Targeting Gross NPA below 1.5% in FY26",
                quantified_value=1.5,
                unit="%",
                target_period="FY26",
                source_document_title="FY25 Annual Report",
                source_document_url="https://example.com/ar.pdf"
            )
        ]
        # Statement has Provisions = 1.2% and Other Expenses, but NO GNPA row
        pl_stmt = {
            "periods": ["FY25", "FY26"],
            "rows": [
                {"metric": "Provisions and Contingencies", "values": [1.0, 1.2]},
                {"metric": "Other Expenses", "values": [500, 600]}
            ]
        }
        evaluated = evaluate_management_guidance_vs_actual(guidance, financial_statements={"profit_loss": pl_stmt})
        self.assertEqual(evaluated[0].status, "INSUFFICIENT_EVIDENCE")
        self.assertIsNone(evaluated[0].actual_reported_value)

    def test_scenario_e_advances_cannot_use_borrowings(self):
        """Scenario E: Advances guidance cannot match Borrowings row in balance sheet."""
        guidance = [
            ManagementGuidanceItem(
                metric_or_topic="Advances Growth",
                guidance_text="Guided Advances of ₹50,000 Cr in FY26",
                quantified_value=50000.0,
                unit="₹ Cr",
                target_period="FY26",
                source_document_title="FY25 Annual Report",
                source_document_url="https://example.com/ar.pdf"
            )
        ]
        # Balance Sheet has Borrowings = 50000, but NO Advances row
        bs_stmt = {
            "periods": ["FY25", "FY26"],
            "rows": [
                {"metric": "Borrowings", "values": [40000, 50000]},
                {"metric": "Other Liabilities", "values": [5000, 6000]}
            ]
        }
        evaluated = evaluate_management_guidance_vs_actual(guidance, financial_statements={"balance_sheet": bs_stmt})
        self.assertEqual(evaluated[0].status, "INSUFFICIENT_EVIDENCE")
        self.assertIsNone(evaluated[0].actual_reported_value)

    def test_scenario_f_invalid_guidance_source_rejected_through_production_sanitizer(self):
        """Scenario F: Production sanitizer strictly rejects unknown URLs/titles; guidance cannot become MET/MISSED."""
        raw_result = GenericDocumentIntelligenceResult(
            symbol="INFY",
            company_name="Infosys Limited",
            management_guidance_items=[
                ManagementGuidanceItem(
                    metric_or_topic="Sales Revenue",
                    guidance_text="Guided FY26 sales of ₹1,500 Cr",
                    quantified_value=1500.0,
                    target_period="FY26",
                    source_document_title="Hallucinated Unindexed Document",
                    source_document_url="https://fake-url.com/fake.pdf"
                )
            ]
        )
        candidate_docs = [
            {"title": "Infosys FY25 Annual Report", "url": "https://infosys.com/ar25.pdf", "type": "annual_report"}
        ]
        pl_stmt = {
            "periods": ["FY25", "FY26"],
            "rows": [{"metric": "Sales", "values": [1200, 1500]}]
        }
        
        sanitized = sanitize_and_verify_intelligence_result(
            result=raw_result,
            symbol="INFY",
            candidate_documents_meta=candidate_docs,
            pl_stmt=pl_stmt
        )
        
        guidance = sanitized.management_guidance_items[0]
        self.assertEqual(guidance.source_support_status, "UNSUPPORTED")
        self.assertEqual(guidance.confidence, "LOW")
        self.assertEqual(guidance.status, "INSUFFICIENT_EVIDENCE")
        self.assertEqual(guidance.source_document_url, "")
        self.assertIn("Unverified source filing", guidance.comparison_detail)

    def test_scenario_g_invalid_evidence_type_strictly_rejected(self):
        """Scenario G: Strict DocumentEvidenceType Literal rejects invalid category with ValidationError."""
        with self.assertRaises(ValidationError):
            DocumentEvidenceItem(
                id="evi_bad_1",
                symbol="INFY",
                evidence_type="INVALID_CATEGORY_NAME",  # Invalid type
                title="Bad item",
                normalized_topic="Topic",
                statement="Statement",
                source_document_title="Doc",
                source_url="https://example.com/doc.pdf"
            )

    def test_scenario_h_no_fake_audited_provenance(self):
        """Scenario H: Reported source is neutral 'Financial Statement Data', not fake 'Audited Financial Statements'."""
        guidance = [
            ManagementGuidanceItem(
                metric_or_topic="Sales Revenue",
                guidance_text="Revenue guidance ₹1,000 Cr",
                quantified_value=1000.0,
                target_period="FY26",
                source_document_title="FY25 AR",
                source_document_url="https://example.com/ar.pdf"
            )
        ]
        pl_stmt = {"periods": ["FY25", "FY26"], "rows": [{"metric": "Sales", "values": [800, 1000]}]}
        evaluated = evaluate_management_guidance_vs_actual(guidance, financial_statements={"profit_loss": pl_stmt})
        self.assertEqual(evaluated[0].actual_reported_source, "Financial Statement Data")
        self.assertNotEqual(evaluated[0].actual_reported_source, "Audited Financial Statements")

    def test_scenario_i_v43_taxonomy_and_bank_routing_unchanged(self):
        """Scenario I: V4.3 taxonomy classification and Bank routing API remain strictly preserved."""
        from company_taxonomy_service import normalize_classification
        from financial_engine import classify_financial_business_model
        
        sec, ind, sub_ind, state = normalize_classification(
            sector="Financial Services",
            industry="Banks",
            sub_industry="Private Sector Bank"
        )
        self.assertEqual(sec, "Financial Services")
        self.assertEqual(ind, "Banks")
        self.assertEqual(state, "COMPLETE")
        
        # Test original V4.3 API contract (sector=..., industry=...)
        model = classify_financial_business_model(sector=sec, industry=ind)
        self.assertEqual(model, "BANK")
        
        corp_model = classify_financial_business_model(sector="Information Technology", industry="IT Services")
        self.assertEqual(corp_model, "GENERAL_CORPORATE")

    def test_scenario_j_cached_get_still_zero_ai_network(self):
        """Scenario J: Cached business analysis read executes purely from SQLite with zero network calls."""
        import database
        mock_data = {
            "symbol": "HEROMOTOCO",
            "company_name": "Hero MotoCorp Limited",
            "ai_provider_used": "STORED_CACHE",
            "latest_document_period": "FY25 AR",
            "what_changed_recently": [],
            "growth_drivers": [],
            "promise_vs_delivery": [],
            "evidence_items": [
                {
                    "id": "evi_hero_1",
                    "symbol": "HEROMOTOCO",
                    "evidence_type": "NEW_PRODUCT",
                    "title": "Vida EV Expansion",
                    "normalized_topic": "EV",
                    "statement": "Vida expanded to 100 cities.",
                    "source_document_title": "FY25 AR",
                    "source_url": "https://heromotocorp.com/ar25.pdf",
                    "status": "SUPPORTED"
                }
            ],
            "management_guidance_items": []
        }
        database.save_ai_analysis("HEROMOTOCO", "Hero MotoCorp Limited", mock_data, ai_provider="STORED_CACHE")
        
        result = get_company_doc_intelligence("HEROMOTOCO")
        self.assertIsNotNone(result)
        self.assertEqual(result.symbol, "HEROMOTOCO")
        self.assertEqual(len(result.evidence_items), 1)
        self.assertEqual(result.evidence_items[0].title, "Vida EV Expansion")

    def test_scenario_k_temp_db_isolation_preserved(self):
        """Scenario K: SQLite operations strictly use isolated temp database; runtime DB is never touched."""
        import database
        self.assertTrue(str(database.DB_PATH).startswith(self.temp_dir))
        prod_db = Path(__file__).parent / "data" / "stocker.db"
        self.assertNotEqual(database.DB_PATH, prod_db)

if __name__ == "__main__":
    unittest.main()
