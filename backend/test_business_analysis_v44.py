import sys
import os
import json
import tempfile
import shutil
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
from typing import Dict, Any
from pydantic import ValidationError

# Ensure path includes libs and backend
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "libs"))

from doc_intelligence_models import (
    BusinessAnalysisResult, BusinessOutlookResult, DocumentEvidenceItem,
    ManagementGuidanceItem, PromiseVsDeliveryItem, GrowthDriver, StockerView,
    RecentChange, RisksAndCashIssues, DemandMomentum
)
from doc_intelligence_engine import (
    get_company_doc_intelligence,
    evaluate_management_guidance_vs_actual,
    _apply_financial_cross_check
)
from doc_intelligence_pipeline import (
    run_multi_document_ai_pipeline,
    deduplicate_synthesized_findings
)
from llm_service import (
    sanitize_citation,
    sanitize_and_verify_intelligence_result,
    GenericDocumentIntelligenceResult
)
from financial_engine import verify_promise_vs_delivery_item
from models import DocumentLinks, DocumentItem
import database

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

    def test_scenario_l_staleness_not_invented_without_current_docs(self):
        """Scenario L: Cached analysis without current_docs preserves persisted status or returns neutral not_checked."""
        import database
        # 1. Analysis with persisted "fresh"
        mock_data_fresh = {
            "symbol": "TCS",
            "company_name": "Tata Consultancy Services",
            "ai_provider_used": "STORED",
            "source_documents_hash": "abc123hash",
            "analysis_version": "2.0",
            "staleness_status": "fresh",
            "what_changed_recently": [],
            "growth_drivers": [],
            "promise_vs_delivery": [],
            "evidence_items": [
                {
                    "id": "evi_tcs_1",
                    "symbol": "TCS",
                    "evidence_type": "DEMAND_DRIVER",
                    "title": "Cloud Migration",
                    "normalized_topic": "Cloud",
                    "statement": "Large cloud deal ramped.",
                    "source_document_title": "FY25 AR",
                    "source_url": "https://tcs.com/ar25.pdf",
                    "status": "SUPPORTED"
                }
            ],
            "management_guidance_items": []
        }
        database.save_ai_analysis("TCS", "Tata Consultancy Services", mock_data_fresh, ai_provider="STORED")

        # Staleness check without current_docs returns (False, "not_checked")
        is_stale, reason = database.check_business_analysis_staleness("TCS", current_docs=None)
        self.assertFalse(is_stale)
        self.assertEqual(reason, "not_checked")

        # get_company_doc_intelligence with current_docs=None preserves persisted "fresh"
        intel_fresh = get_company_doc_intelligence("TCS", current_docs=None)
        self.assertIsNotNone(intel_fresh)
        self.assertEqual(intel_fresh.staleness_status, "fresh")

        # 2. Analysis without persisted staleness_status -> returns neutral "not_checked" (NOT "fresh" or "stale")
        mock_data_no_status = {
            "symbol": "INFY",
            "company_name": "Infosys Limited",
            "ai_provider_used": "STORED",
            "source_documents_hash": "xyz987hash",
            "analysis_version": "2.0",
            "evidence_items": [
                {
                    "id": "evi_infy_1",
                    "symbol": "INFY",
                    "evidence_type": "DEMAND_DRIVER",
                    "title": "AI Suite",
                    "normalized_topic": "AI",
                    "statement": "Topaz AI deals expanding.",
                    "source_document_title": "FY25 AR",
                    "source_url": "https://infosys.com/ar25.pdf",
                    "status": "SUPPORTED"
                }
            ]
        }
        database.save_ai_analysis("INFY", "Infosys Limited", mock_data_no_status, ai_provider="STORED")
        intel_no_status = get_company_doc_intelligence("INFY", current_docs=None)
        self.assertIsNotNone(intel_no_status)
        self.assertEqual(intel_no_status.staleness_status, "not_checked")

        # 3. Supplying genuinely changed current_docs triggers stale
        new_docs = [{"title": "Q1 FY26 Concall", "url": "https://tcs.com/q1fy26.pdf", "period": "Q1 FY26"}]
        is_stale_new, reason_new = database.check_business_analysis_staleness("TCS", current_docs=new_docs)
        self.assertTrue(is_stale_new)
        self.assertIn("source_documents_changed", reason_new)

        intel_stale = get_company_doc_intelligence("TCS", current_docs=new_docs)
        self.assertIsNotNone(intel_stale)
        self.assertEqual(intel_stale.staleness_status, "stale")

    def test_scenario_m_capex_guidance_cannot_use_cwip_or_fixed_assets(self):
        """Scenario M: Capex guidance strictly rejects CWIP and Fixed Assets closing balances."""
        guidance = [
            ManagementGuidanceItem(
                metric_or_topic="Capex Investment Outlay",
                guidance_text="Targeting ₹3,000 Cr capex in FY26",
                quantified_value=3000.0,
                unit="₹ Cr",
                target_period="FY26",
                source_document_title="FY25 Annual Report",
                source_document_url="https://example.com/ar.pdf"
            )
        ]

        # Case 1: Statement with only Balance Sheet (CWIP = 2500, Fixed Assets = 15000)
        bs_stmt = {
            "periods": ["FY25", "FY26"],
            "rows": [
                {"metric": "Capital Work in Progress", "values": [2000, 2500]},
                {"metric": "Fixed Assets", "values": [12000, 15000]}
            ]
        }
        evaluated_bs = evaluate_management_guidance_vs_actual(guidance, financial_statements={"balance_sheet": bs_stmt})
        self.assertEqual(evaluated_bs[0].status, "INSUFFICIENT_EVIDENCE")
        self.assertIsNone(evaluated_bs[0].actual_reported_value)

        # Case 2: Statement with Cash Flow (Fixed Assets Purchased = 3200) -> valid match
        cf_stmt = {
            "periods": ["FY25", "FY26"],
            "rows": [
                {"metric": "Fixed Assets Purchased", "values": [2500, 3200]}
            ]
        }
        evaluated_cf = evaluate_management_guidance_vs_actual(
            guidance,
            financial_statements={"balance_sheet": bs_stmt, "cash_flow": cf_stmt}
        )
        self.assertEqual(evaluated_cf[0].status, "MET")
        self.assertEqual(evaluated_cf[0].actual_reported_value, 3200.0)
        self.assertEqual(evaluated_cf[0].actual_reported_source, "Financial Statement Data")

    def test_scenario_n_casa_ratio_cannot_map_to_deposits(self):
        """Scenario N: CASA ratio guidance must NOT compare against Total Deposits row."""
        guidance = [
            ManagementGuidanceItem(
                metric_or_topic="CASA Ratio",
                guidance_text="Targeting CASA ratio of 45%",
                quantified_value=45.0,
                unit="%",
                target_period="FY26",
                source_document_title="FY25 Concall",
                source_document_url="https://example.com/concall.pdf"
            )
        ]

        # Case 1: Bank Balance Sheet with only Deposits / Total Deposits
        bs_stmt = {
            "periods": ["FY25", "FY26"],
            "rows": [
                {"metric": "Deposits", "values": [180000, 200000]},
                {"metric": "Total Deposits", "values": [180000, 200000]}
            ]
        }
        evaluated = evaluate_management_guidance_vs_actual(guidance, financial_statements={"balance_sheet": bs_stmt})
        self.assertEqual(evaluated[0].status, "INSUFFICIENT_EVIDENCE")
        self.assertIsNone(evaluated[0].actual_reported_value)

        # Case 2: Statement with explicit CASA % row
        pl_stmt = {
            "periods": ["FY25", "FY26"],
            "rows": [
                {"metric": "CASA %", "values": [42.0, 46.2]}
            ]
        }
        evaluated_casa = evaluate_management_guidance_vs_actual(
            guidance,
            financial_statements={"profit_loss": pl_stmt, "balance_sheet": bs_stmt}
        )
        self.assertEqual(evaluated_casa[0].status, "MET")
        self.assertEqual(evaluated_casa[0].actual_reported_value, 46.2)

    def test_scenario_o_deterministic_evidence_and_guidance_ids(self):
        """Scenario O: Fallback IDs are stable SHA-256 hashes deterministic across process restarts."""
        import database
        evi_item = {
            "evidence_type": "CAPACITY_EXPANSION",
            "title": "New Semiconductor Fab",
            "normalized_topic": "Semiconductor",
            "statement": "Approved ₹10,000 Cr outlay for Fab 1.",
            "source_url": "https://example.com/fab.pdf"
        }
        id1 = database.generate_deterministic_evidence_id("TATACOMM", evi_item)
        id2 = database.generate_deterministic_evidence_id("TATACOMM", evi_item)
        self.assertEqual(id1, id2)
        self.assertTrue(id1.startswith("evi_TATACOMM_"))

        guidance_item = {
            "metric_or_topic": "Revenue Growth",
            "target_period": "FY26",
            "guidance_text": "Targeting 20% topline growth",
            "source_document_title": "Investor Presentation"
        }
        g_id1 = database.generate_deterministic_guidance_id("TATACOMM", guidance_item)
        g_id2 = database.generate_deterministic_guidance_id("TATACOMM", guidance_item)
        self.assertEqual(g_id1, g_id2)
        self.assertTrue(g_id1.startswith("mgi_TATACOMM_"))

    def test_scenario_q_llm_json_evidence_resilience(self):
        """Scenario Q: Raw LLM output without symbol or id in evidence items parses cleanly."""
        raw_llm_dict = {
            "symbol": "INFY",
            "company_name": "Infosys Limited",
            "evidence_items": [
                {
                    "id": "evi_1",
                    "evidence_type": "CAPEX_PLAN",
                    "title": "Cloud Expansion",
                    "normalized_topic": "Capex",
                    "statement": "Investing ₹3,000 Cr in AI data centers.",
                    "source_document_title": "FY25 Annual Report",
                    "confidence": "HIGH"
                },
                {
                    "evidence_type": "DEMAND_DRIVER",
                    "title": "Large Deal TCV",
                    "normalized_topic": "Revenue",
                    "statement": "Signed $2.5B in net new large deals.",
                    "source_document_title": "Q3 FY26 Concall",
                    "confidence": "HIGH"
                }
            ],
            "management_guidance_items": [
                {
                    "metric_or_topic": "Constant Currency Revenue Growth",
                    "guidance_text": "FY26 revenue growth guided between 4% and 5%",
                    "quantified_range_min": 4.0,
                    "quantified_range_max": 5.0,
                    "unit": "%",
                    "target_period": "FY26",
                    "source_document_title": "Q3 FY26 Presentation"
                }
            ]
        }
        res = BusinessOutlookResult(**raw_llm_dict)
        self.assertEqual(len(res.evidence_items), 2)
        self.assertEqual(res.evidence_items[0].symbol, "INFY")
        self.assertEqual(res.evidence_items[1].symbol, "INFY")
        self.assertEqual(res.evidence_items[0].evidence_type, "CAPEX_PLAN")
        self.assertEqual(res.evidence_items[1].evidence_type, "DEMAND_DRIVER")
        self.assertEqual(len(res.management_guidance_items), 1)
        self.assertEqual(res.management_guidance_items[0].quantified_range_max, 5.0)

    # =========================================================================
    # A. WHAT CHANGED TESTS
    # =========================================================================

    def test_what_changed_latest_vs_prior_period_comparison(self):
        """What Changed item includes direction, period comparison, and plain English explanation."""
        change = RecentChange(
            headline="NIM Core Expansion Moderation",
            category="Margins / Funding Costs",
            detail="NIM expanded to 4.36% from 4.32% QoQ, but 8 bps came from non-recurring tax-refund interest.",
            direction="MIXED",
            period_comparison="Q1 FY27 vs Q4 FY26",
            is_one_off=True,
            why_it_matters="Underlying core NIM was 4.28%, indicating headline margin expansion overstates core momentum.",
            source_doc="Q1 FY27 Concall Transcript",
            source_url="https://bse.com/cc_q1fy27.pdf",
            source_page=8
        )
        self.assertEqual(change.direction, "MIXED")
        self.assertEqual(change.period_comparison, "Q1 FY27 vs Q4 FY26")
        self.assertTrue(change.is_one_off)
        self.assertIn("Underlying core NIM was 4.28%", change.why_it_matters)

    def test_what_changed_one_off_effect_identified_in_sanitization(self):
        """Sanitizer automatically detects tax-refund interest / exceptional item as one-off."""
        raw_res = GenericDocumentIntelligenceResult(
            symbol="TESTBANK",
            company_name="Test Bank",
            latest_document_period="Q1 FY27",
            what_changed_recently=[
                RecentChange(
                    headline="NIM Headline Increase",
                    category="Margins / Funding Costs",
                    detail="Reported NIM was 4.36% with 8 bps from tax refund interest.",
                    source_url="https://bse.com/cc.pdf"
                )
            ]
        )
        candidate_docs = [{"title": "Q1 FY27 Concall", "url": "https://bse.com/cc.pdf", "type": "concall_transcript"}]
        database.save_cached_document_pages("TESTBANK", "https://bse.com/cc.pdf", [(8, "Reported NIM was 4.36% with 8 bps from tax refund interest.")])

        sanitized = sanitize_and_verify_intelligence_result(
            result=raw_res,
            symbol="TESTBANK",
            candidate_documents_meta=candidate_docs,
            latest_doc_url="https://bse.com/cc.pdf",
            financial_business_model="BANK"
        )
        self.assertEqual(len(sanitized.what_changed_recently), 1)
        self.assertTrue(sanitized.what_changed_recently[0].is_one_off)
        self.assertEqual(sanitized.what_changed_recently[0].source_page, 8)

    # =========================================================================
    # B. GROWTH DRIVERS TESTS
    # =========================================================================

    def test_growth_driver_one_off_not_mislabeled_structural(self):
        """A one-off gain or tax reversal is labeled as One-off Driver, not Structural Driver."""
        driver = GrowthDriver(
            driver_title="Tax Provision Write-back",
            driver_type="One-off Driver",
            description="One-time tax provision write-back of ₹4.46B boosted PAT.",
            is_one_off=True,
            execution_status="Completed",
            source_url="https://bse.com/cc.pdf"
        )
        self.assertTrue(driver.is_one_off)
        self.assertEqual(driver.driver_type, "One-off Driver")

    def test_growth_driver_bank_routing(self):
        """Bank drivers focus on loan mix, deposits, CASA, and NIM, excluding industrial FCF/CWIP."""
        raw_res = GenericDocumentIntelligenceResult(
            symbol="TESTBANK",
            company_name="Test Bank",
            latest_document_period="Q1 FY27",
            growth_drivers=[
                GrowthDriver(
                    driver_title="Rural and Business Banking Loan Acceleration",
                    driver_type="Structural Driver",
                    description="Rural portfolio grew 35.4% YoY and Business Banking grew 28.2% YoY driving 19.6% total loan growth.",
                    source_url="https://bse.com/cc.pdf"
                ),
                GrowthDriver(
                    driver_title="Industrial CWIP Commissioning",
                    driver_type="Capacity / Plant",
                    description="Gross block expansion and working capital cycle reduction.",
                    source_url="https://bse.com/cc.pdf"
                )
            ]
        )
        candidate_docs = [{"title": "Q1 Concall", "url": "https://bse.com/cc.pdf", "type": "concall_transcript"}]
        database.save_cached_document_pages("TESTBANK", "https://bse.com/cc.pdf", [(3, "Rural portfolio grew 35.4% YoY and Business Banking grew 28.2% YoY.")])

        sanitized = sanitize_and_verify_intelligence_result(
            result=raw_res,
            symbol="TESTBANK",
            candidate_documents_meta=candidate_docs,
            latest_doc_url="https://bse.com/cc.pdf",
            financial_business_model="BANK"
        )
        # Bank sanitizer should reject the industrial CWIP/working-capital driver
        self.assertEqual(len(sanitized.growth_drivers), 1)
        self.assertIn("Rural and Business Banking", sanitized.growth_drivers[0].driver_title)

    # =========================================================================
    # C. PROMISE VS DELIVERY TESTS (EXACT TARGET SEMANTICS, NO 95/80 TOLERANCE)
    # =========================================================================

    def test_promise_vs_delivery_exact_target_missed_without_tolerance(self):
        """Exact point target 10% with 9.4% actual is MISSED (no invented 95% tolerance)."""
        item = {
            "area": "Revenue Growth",
            "management_promise": "Targeted 10% revenue growth in FY26",
            "promised_in_period": "FY25",
            "actual_outcome": "Reported revenue of ₹1,094 Cr in FY26",
            "actual_in_period": "FY26",
            "source_url_promise": "https://bse.com/ar25.pdf",
            "source_url_actual": "https://bse.com/ar26.pdf"
        }
        pl_stmt = {
            "periods": ["FY25", "FY26"],
            "rows": [
                {"metric": "Sales", "values": [1000, 1094]}
            ]
        }
        res = verify_promise_vs_delivery_item(item, pl_stmt=pl_stmt, quarters_stmt=None, current_year=2026.5)
        self.assertEqual(res["status"], "Missed")
        self.assertIn("Target: 10.0%; Actual: 9.4%", res["financial_numbers_check"])
        self.assertIn("Variance: -0.6 percentage points", res["financial_numbers_check"])
        self.assertIn("Achievement Rate: 94.0%", res["financial_numbers_check"])
        self.assertIn("Target Missed", res["stocker_analysis"])

    def test_promise_vs_delivery_exact_target_delivered(self):
        """Exact point target 10% with 10.0% actual is DELIVERED."""
        item = {
            "area": "Revenue Growth",
            "management_promise": "Targeted 10% revenue growth in FY26",
            "promised_in_period": "FY25",
            "actual_outcome": "Reported revenue of ₹1,100 Cr in FY26",
            "actual_in_period": "FY26",
            "source_url_promise": "https://bse.com/ar25.pdf",
            "source_url_actual": "https://bse.com/ar26.pdf"
        }
        pl_stmt = {
            "periods": ["FY25", "FY26"],
            "rows": [
                {"metric": "Sales", "values": [1000, 1100]}
            ]
        }
        res = verify_promise_vs_delivery_item(item, pl_stmt=pl_stmt, quarters_stmt=None, current_year=2026.5)
        self.assertEqual(res["status"], "Delivered")
        self.assertIn("Target Delivered", res["stocker_analysis"])

    def test_promise_vs_delivery_minimum_target_delivered(self):
        """'At least 10%' target with 10.2% actual is DELIVERED."""
        item = {
            "area": "Revenue Growth",
            "management_promise": "Management targeted at least 10% revenue growth in FY26",
            "promised_in_period": "FY25",
            "actual_outcome": "Reported revenue of ₹1,102 Cr in FY26",
            "actual_in_period": "FY26",
            "source_url_promise": "https://bse.com/ar25.pdf",
            "source_url_actual": "https://bse.com/ar26.pdf"
        }
        pl_stmt = {
            "periods": ["FY25", "FY26"],
            "rows": [
                {"metric": "Sales", "values": [1000, 1102]}
            ]
        }
        res = verify_promise_vs_delivery_item(item, pl_stmt=pl_stmt, quarters_stmt=None, current_year=2026.5)
        self.assertEqual(res["status"], "Delivered")
        self.assertIn("Minimum Target Achieved", res["stocker_analysis"])

    def test_promise_vs_delivery_range_target_within_range(self):
        """Range guidance 'between 4.2% and 4.4%' with 4.36% actual is DELIVERED (within range)."""
        item = {
            "area": "NIM Guidance",
            "management_promise": "NIM expected between 4.2% and 4.4% in FY26",
            "promised_in_period": "FY25",
            "actual_outcome": "Reported NIM was 4.36% in FY26",
            "actual_in_period": "FY26",
            "source_url_promise": "https://bse.com/ar25.pdf",
            "source_url_actual": "https://bse.com/ar26.pdf"
        }
        res = verify_promise_vs_delivery_item(item, pl_stmt=None, quarters_stmt=None, current_year=2026.5)
        self.assertEqual(res["status"], "Delivered")
        self.assertIn("Within Guidance Range", res["stocker_analysis"])

    def test_promise_vs_delivery_range_target_below_range_missed(self):
        """Range guidance '4.2% - 4.4%' with 4.1% actual is MISSED (below range)."""
        item = {
            "area": "NIM Guidance",
            "management_promise": "NIM expected 4.2% - 4.4% in FY26",
            "promised_in_period": "FY25",
            "actual_outcome": "Reported NIM of 4.10% in FY26",
            "actual_in_period": "FY26",
            "source_url_promise": "https://bse.com/ar25.pdf",
            "source_url_actual": "https://bse.com/ar26.pdf"
        }
        res = verify_promise_vs_delivery_item(item, pl_stmt=None, quarters_stmt=None, current_year=2026.5)
        self.assertEqual(res["status"], "Missed")
        self.assertIn("Below Guidance Range", res["stocker_analysis"])

    def test_promise_vs_delivery_range_target_above_range_not_automatically_delivered(self):
        """NIM range 4.2% - 4.4% with 4.50% actual is NOT automatically Delivered (bounded range)."""
        item = {
            "area": "NIM Guidance",
            "management_promise": "NIM expected between 4.2% and 4.4% in FY26",
            "promised_in_period": "FY25",
            "actual_outcome": "Reported NIM of 4.50% in FY26",
            "actual_in_period": "FY26",
            "source_url_promise": "https://bse.com/ar25.pdf",
            "source_url_actual": "https://bse.com/ar26.pdf"
        }
        res = verify_promise_vs_delivery_item(item, pl_stmt=None, quarters_stmt=None, current_year=2026.5)
        self.assertNotEqual(res["status"], "Delivered")
        self.assertIn("Above Guidance Range", res["stocker_analysis"])

    def test_range_parser_unit_tightening_and_year_guards(self):
        """Range parser requires explicit metric units (%, bps, currency) and rejects bare year/period ranges."""
        from financial_engine import parse_explicit_guidance_range
        # 1. FY2025-2026 strategy -> NOT range guidance
        self.assertIsNone(parse_explicit_guidance_range("FY2025-2026 corporate strategy"))
        # 2. Annual Report 2025-26 -> NOT range guidance
        self.assertIsNone(parse_explicit_guidance_range("Annual Report 2025-26"))
        self.assertIsNone(parse_explicit_guidance_range("FY25-26 targets"))
        # 3. NIM 4.2%-4.4% -> valid range
        self.assertEqual(parse_explicit_guidance_range("NIM 4.2%-4.4%"), (4.2, 4.4, "%"))
        self.assertEqual(parse_explicit_guidance_range("between 4.2% and 4.4%"), (4.2, 4.4, "%"))
        # 4. Credit cost 80-100 bps -> valid range
        self.assertEqual(parse_explicit_guidance_range("Credit cost 80-100 bps"), (80.0, 100.0, "bps"))
        # Currency range
        self.assertEqual(parse_explicit_guidance_range("Capex of ₹8,000–₹10,000 Cr"), (8000.0, 10000.0, "cr"))

    def test_promise_vs_delivery_capex_below_range_not_automatically_delivered(self):
        """Capex below guided range (₹6,000 Cr vs ₹8,000-₹10,000 Cr) is NOT automatically Delivered."""
        item = {
            "area": "Capital Expenditure",
            "management_promise": "Targeted capex of ₹8,000–₹10,000 Cr in FY26",
            "promised_in_period": "FY25",
            "actual_outcome": "Reported capex was ₹6,000 Cr in FY26",
            "actual_in_period": "FY26",
            "source_url_promise": "https://bse.com/ar25.pdf",
            "source_url_actual": "https://bse.com/ar26.pdf"
        }
        res = verify_promise_vs_delivery_item(item, pl_stmt=None, quarters_stmt=None, current_year=2026.5)
        self.assertNotEqual(res["status"], "Delivered")
        self.assertIn("Below Guidance Range", res["stocker_analysis"])

    def test_promise_vs_delivery_credit_cost_below_range_favorable_delivered(self):
        """Credit cost below range (0.60% vs 0.8%-1.0%) is deterministically favorable (Delivered)."""
        item = {
            "area": "Credit Cost Guidance",
            "management_promise": "Credit cost expected 0.8% - 1.0% in FY26",
            "promised_in_period": "FY25",
            "actual_outcome": "Reported credit cost of 0.60% in FY26",
            "actual_in_period": "FY26",
            "source_url_promise": "https://bse.com/ar25.pdf",
            "source_url_actual": "https://bse.com/ar26.pdf"
        }
        res = verify_promise_vs_delivery_item(item, pl_stmt=None, quarters_stmt=None, current_year=2026.5)
        self.assertEqual(res["status"], "Delivered")
        self.assertIn("Favorable Below Range", res["stocker_analysis"])

    def test_currency_actual_extraction_context_and_units(self):
        """Actual currency/absolute value extraction requires explicit currency/unit context and normalizes units."""
        from financial_engine import extract_guidance_actual_value

        # 1. FY26 capex was ₹6,000 Cr -> 6000
        self.assertEqual(extract_guidance_actual_value("FY26 capex was ₹6,000 Cr", "cr"), 6000.0)

        # 2. FY2026 capex was ₹9,000 Cr -> 9000
        self.assertEqual(extract_guidance_actual_value("FY2026 capex was ₹9,000 Cr", "cr"), 9000.0)

        # 3. FY26 without an amount -> no actual extracted (None)
        self.assertIsNone(extract_guidance_actual_value("FY26 capex planning was initiated without final spending", "cr"))

        # 4. unrelated number before amount does not win
        self.assertEqual(extract_guidance_actual_value("In Q1 FY26 across 26 facilities, capex was ₹6,000 Cr", "cr"), 6000.0)

        # 5. incompatible currency units fail closed unless deterministic conversion exists
        # Incompatible USD fails closed
        self.assertIsNone(extract_guidance_actual_value("FY26 capex was $50 million", "cr"))
        # ₹60 billion deterministically converts to 6000 Cr (1 billion INR = 100 Cr INR)
        self.assertEqual(extract_guidance_actual_value("FY26 capex was ₹60 billion", "cr"), 6000.0)
        # 600,000 lakh converts to 6000 Cr
        self.assertEqual(extract_guidance_actual_value("FY26 capex was 600000 lakh", "cr"), 6000.0)

    def test_promise_vs_delivery_capex_fy26_amount_parsing(self):
        """FY26 capex was ₹6,000 Cr parses 6000 Cr, not 26."""
        item = {
            "area": "Capital Expenditure",
            "management_promise": "Targeted capex of ₹8,000–₹10,000 Cr in FY26",
            "promised_in_period": "FY25",
            "actual_outcome": "FY26 capex was ₹6,000 Cr",
            "actual_in_period": "FY26",
            "source_url_promise": "https://bse.com/ar25.pdf",
            "source_url_actual": "https://bse.com/ar26.pdf"
        }
        res = verify_promise_vs_delivery_item(item, pl_stmt=None, quarters_stmt=None, current_year=2026.5)
        self.assertIn("Reported: 6000.0 cr", res["financial_numbers_check"])
        self.assertNotIn("Reported: 26", res["financial_numbers_check"])

    def test_promise_vs_delivery_range_cost_metric_above_range_missed(self):
        """Credit Cost range 0.8% - 1.0% with 1.20% actual is MISSED (unfavorable cost overrun)."""
        item = {
            "area": "Credit Cost Guidance",
            "management_promise": "Credit cost expected 0.8% - 1.0% in FY26",
            "promised_in_period": "FY25",
            "actual_outcome": "Reported credit cost of 1.20% in FY26",
            "actual_in_period": "FY26",
            "source_url_promise": "https://bse.com/ar25.pdf",
            "source_url_actual": "https://bse.com/ar26.pdf"
        }
        res = verify_promise_vs_delivery_item(item, pl_stmt=None, quarters_stmt=None, current_year=2026.5)
        self.assertEqual(res["status"], "Missed")
        self.assertIn("Above Guidance Range (Unfavorable)", res["stocker_analysis"])

    def test_promise_vs_delivery_future_target_no_interim_not_yet_measurable(self):
        """Future target (FY28) without interim evidence is Not Yet Measurable, NOT On Track."""
        item = {
            "area": "Capacity Expansion",
            "management_promise": "Targeting 20% growth by FY28",
            "promised_in_period": "FY25",
            "target_timeline": "FY28",
            "actual_outcome": "Project planning underway",
            "actual_in_period": "FY26",
            "source_url_promise": "https://bse.com/ar25.pdf",
            "source_url_actual": "https://bse.com/ar26.pdf"
        }
        res = verify_promise_vs_delivery_item(item, pl_stmt=None, quarters_stmt=None, current_year=2026.5)
        self.assertEqual(res["status"], "Not Yet Measurable")
        self.assertIn("Future Target Not Yet Due", res["stocker_analysis"])

    def test_promise_vs_delivery_future_growth_weak_interim_not_on_track(self):
        """Target 20% revenue growth by FY28 with only 'Revenue grew 3%' in FY26 is Not Yet Measurable (NOT On Track)."""
        item = {
            "area": "Revenue Growth",
            "management_promise": "Targeting 20% revenue growth by FY28",
            "promised_in_period": "FY25",
            "target_timeline": "FY28",
            "actual_outcome": "Revenue grew 3% in FY26",
            "actual_in_period": "FY26",
            "source_url_promise": "https://bse.com/ar25.pdf",
            "source_url_actual": "https://bse.com/ar26.pdf"
        }
        res = verify_promise_vs_delivery_item(item, pl_stmt=None, quarters_stmt=None, current_year=2026.5)
        self.assertEqual(res["status"], "Not Yet Measurable")
        self.assertIn("Future Target Not Yet Due", res["stocker_analysis"])

    def test_promise_vs_delivery_future_target_with_interim_on_track(self):
        """Future target (FY28) with supported interim progress in subsequent filing is On Track."""
        item = {
            "area": "Operational Milestone",
            "management_promise": "Targeting commissioning of new facility by FY28",
            "promised_in_period": "FY25",
            "target_timeline": "FY28",
            "actual_outcome": "Phase 1 construction commenced and trial underway on schedule",
            "actual_in_period": "FY26",
            "source_url_promise": "https://bse.com/ar25.pdf",
            "source_url_actual": "https://bse.com/ar26.pdf"
        }
        res = verify_promise_vs_delivery_item(item, pl_stmt=None, quarters_stmt=None, current_year=2026.5)
        self.assertEqual(res["status"], "On Track")
        self.assertIn("Milestone On Track", res["stocker_analysis"])

    def test_promise_vs_delivery_same_filing_rejected(self):
        """Same filing promise + outcome is rejected as Not Enough Evidence."""
        item = {
            "area": "Operating Margin",
            "management_promise": "Targeted margin of 22%",
            "promised_in_period": "Q1 FY27",
            "actual_outcome": "Reported margin was 22.5%",
            "actual_in_period": "Q1 FY27",
            "source_url_promise": "https://bse.com/cc_q1.pdf",
            "source_url_actual": "https://bse.com/cc_q1.pdf"
        }
        res = verify_promise_vs_delivery_item(item, pl_stmt=None, quarters_stmt=None, current_year=2026.5)
        self.assertEqual(res["status"], "Not Enough Evidence")
        self.assertIn("Evidence from Same Filing", res["stocker_analysis"])

    def test_promise_vs_delivery_generic_strategy_statement_rejected(self):
        """Generic strategy statement ('focus on sustainable growth') is not treated as a delivered promise."""
        item = {
            "area": "Corporate Strategy",
            "management_promise": "We remain focused on sustainable value creation and harnessing its brand strengths",
            "promised_in_period": "FY25",
            "actual_outcome": "Bank continued to expand market share",
            "actual_in_period": "FY26",
            "source_url_promise": "https://bse.com/ar25.pdf",
            "source_url_actual": "https://bse.com/ar26.pdf"
        }
        res = verify_promise_vs_delivery_item(item, pl_stmt=None, quarters_stmt=None, current_year=2026.5)
        self.assertEqual(res["status"], "Not Yet Measurable")
        self.assertIn("Generic Strategic Intent", res["stocker_analysis"])

    def test_promise_vs_delivery_no_prior_promise_clean_fallback(self):
        """When no prior measurable guidance was found, returns clean explanatory item without fabrication."""
        raw_res = GenericDocumentIntelligenceResult(
            symbol="TESTBANK",
            company_name="Test Bank",
            latest_document_period="Q1 FY27",
            promise_vs_delivery=[]
        )
        sanitized = sanitize_and_verify_intelligence_result(
            result=raw_res,
            symbol="TESTBANK",
            candidate_documents_meta=[],
            latest_doc_url="https://bse.com/ar26.pdf",
            financial_business_model="BANK"
        )
        self.assertEqual(len(sanitized.promise_vs_delivery), 1)
        self.assertEqual(sanitized.promise_vs_delivery[0].status, "Not Enough Evidence")
        self.assertIn("No measurable prior management promise found", sanitized.promise_vs_delivery[0].management_promise)

    def test_no_hardcoded_95_80_achievement_thresholds_in_codebase(self):
        """Ensures that invented 95% / 80% tolerance band checks do not exist in backend/financial_engine.py."""
        from pathlib import Path
        code = (Path(__file__).parent / "financial_engine.py").read_text()
        self.assertNotIn("achieve_pct >= 95", code)
        self.assertNotIn("achieve_pct >= 80", code)
        self.assertNotIn("achieve_pct < 80", code)

    # =========================================================================
    # D. RISKS & STOCKER VIEW TESTS
    # =========================================================================

    def test_risks_view_structured_items_with_metric(self):
        """Risk items include severity, is_current_or_potential, and metric_to_watch."""
        risks = RisksAndCashIssues(
            debt_and_capex_burden="CET-1 ratio at 16.19% as of June 30, 2026.",
            margin_and_cost_pressures="NIM pressure from higher cost of term deposits.",
            regulatory_or_legal_headwinds=["RBI transition to ECL guidelines"],
            risk_items=[
                {
                    "risk_title": "ECL Accounting Transition",
                    "risk_category": "Regulatory / Legal",
                    "severity": "MEDIUM",
                    "is_current_or_potential": "POTENTIAL",
                    "evidence_statement": "New RBI ECL norms may increase transitional credit provisioning across the banking sector.",
                    "metric_to_watch": "Credit Cost % and Provision Coverage Ratio (PCR) in subsequent quarters",
                    "source_url": "https://bse.com/cc.pdf",
                    "source_page": 17
                }
            ]
        )
        self.assertEqual(len(risks.risk_items), 1)
        self.assertEqual(risks.risk_items[0]["severity"], "MEDIUM")
        self.assertEqual(risks.risk_items[0]["is_current_or_potential"], "POTENTIAL")
        self.assertIn("Credit Cost %", risks.risk_items[0]["metric_to_watch"])

    def test_stocker_view_no_buy_sell_recommendations(self):
        """Stocker View sanitization purges any accidental Buy/Sell words from investor summary."""
        raw_res = GenericDocumentIntelligenceResult(
            symbol="TESTBANK",
            company_name="Test Bank",
            latest_document_period="Q1 FY27",
            stocker_view=StockerView(
                execution_verdict="Strong Execution",
                investor_summary="The bank exhibits high-teen loan growth. We maintain a Strong Buy rating."
            )
        )
        sanitized = sanitize_and_verify_intelligence_result(
            result=raw_res,
            symbol="TESTBANK",
            financial_business_model="BANK"
        )
        self.assertNotIn("Strong Buy", sanitized.stocker_view.investor_summary)
        self.assertIn("Watchlist / Neutral Stance", sanitized.stocker_view.investor_summary)

    # =========================================================================
    # E. REDUNDANCY & CROSS-VIEW SUPPRESSION TESTS
    # =========================================================================

    def test_redundancy_suppression_cross_views(self):
        """Cross-view deduplication suppresses verbatim duplicate statements across What Changed and Growth Drivers."""
        raw_dict = {
            "what_changed_recently": [
                {
                    "headline": "Rural loan growth accelerated to 35.4% YoY",
                    "detail": "Rural loan growth accelerated to 35.4% YoY driven by gold loans and Kisan Credit Cards.",
                    "category": "Demand / Volumes"
                }
            ],
            "growth_drivers": [
                {
                    "driver_title": "Rural loan growth accelerated to 35.4% YoY",
                    "description": "Rural loan growth accelerated to 35.4% YoY driven by gold loans and Kisan Credit Cards.",
                    "driver_type": "Structural Driver"
                },
                {
                    "driver_title": "Business Banking Expansion",
                    "description": "Business banking grew 28.2% YoY across 200+ micromarkets.",
                    "driver_type": "Structural Driver"
                }
            ]
        }
        deduped = deduplicate_synthesized_findings(raw_dict)
        # Duplicate in growth_drivers should be suppressed
        self.assertEqual(len(deduped["what_changed_recently"]), 1)
        self.assertEqual(len(deduped["growth_drivers"]), 1)
        self.assertEqual(deduped["growth_drivers"][0]["driver_title"], "Business Banking Expansion")

    # =========================================================================
    # G. V4.4 QA-HARDENING PASS VERIFICATION TESTS
    # =========================================================================

    def test_fail_closed_execution_verdict_insufficient_history(self):
        """Zero verifiable promises must strictly evaluate to 'Insufficient History'."""
        from financial_engine import compute_fail_closed_execution_verdict
        verdict = compute_fail_closed_execution_verdict([])
        self.assertEqual(verdict, "Insufficient History")

    def test_fail_closed_execution_verdict_provisional(self):
        """A single verifiable promise is marked as 'Provisional'."""
        from financial_engine import compute_fail_closed_execution_verdict
        items = [
            {"status": "Delivered", "management_promise": "Achieve 15% loan growth"}
        ]
        verdict = compute_fail_closed_execution_verdict(items)
        self.assertEqual(verdict, "Provisional")

    def test_fail_closed_execution_verdict_strong_and_weak(self):
        """Multiple delivered promises yield 'Strong Execution', while >50% missed yields 'Weak Execution'."""
        from financial_engine import compute_fail_closed_execution_verdict
        strong_items = [
            {"status": "Delivered", "management_promise": "Grow NIM"},
            {"status": "Delivered", "management_promise": "Keep credit cost <50 bps"},
            {"status": "Delivered", "management_promise": "Open 50 branches"}
        ]
        self.assertEqual(compute_fail_closed_execution_verdict(strong_items), "Strong Execution")

        weak_items = [
            {"status": "Missed", "management_promise": "Grow deposit base by 20%"},
            {"status": "Missed", "management_promise": "Expand ROA to 2.5%"},
            {"status": "Delivered", "management_promise": "Open 50 branches"}
        ]
        self.assertEqual(compute_fail_closed_execution_verdict(weak_items), "Weak Execution")

    def test_topline_semantic_mismatch_operating_profit_rejected(self):
        """Operating profit cannot substitute for top-line guidance."""
        item = {
            "area": "Top-Line Revenue",
            "management_promise": "Management guided 15% top-line revenue growth in FY26",
            "promised_in_period": "FY25",
            "actual_outcome": "Reported operating profit expanded by 18% in FY26",
            "actual_in_period": "FY26",
            "source_url_promise": "https://bse.com/ar25.pdf",
            "source_url_actual": "https://bse.com/ar26.pdf"
        }
        res = verify_promise_vs_delivery_item(item, pl_stmt=None, quarters_stmt=None, current_year=2026.5)
        self.assertEqual(res["status"], "Not Enough Evidence")
        self.assertIn("Metric Semantic Mismatch", res["stocker_analysis"])

    def test_bank_kpi_identity_and_evolution_trajectory_requires_two_periods(self):
        """Inter-document KPI trends strictly require >=2 periods and omit single data points."""
        from financial_engine import build_inter_document_kpi_trends

        # Single period: omitted
        single_doc_facts = [
            {"metric_name": "Net Interest Margin (NIM)", "value": 4.36, "unit": "%", "period_or_date": "Q1 FY26"}
        ]
        trends = build_inter_document_kpi_trends(single_doc_facts)
        self.assertEqual(len(trends), 0)

        # Two periods: trend generated
        multi_doc_facts = [
            {"metric_name": "NIM", "value": 4.36, "unit": "%", "period_or_date": "Q1 FY26"},
            {"metric_name": "Net Interest Margin", "value": 4.25, "unit": "%", "period_or_date": "Q2 FY26"}
        ]
        trends_multi = build_inter_document_kpi_trends(multi_doc_facts)
        self.assertEqual(len(trends_multi), 1)
        self.assertEqual(trends_multi[0]["normalized_core"], "nim")
        self.assertEqual(len(trends_multi[0]["data_points"]), 2)
        self.assertEqual(trends_multi[0]["trajectory"], "Contracting")

    def test_bank_kpi_lower_is_better_trajectory_directionality(self):
        """For lower-is-better metrics (GNPA, NNPA, Credit Cost), decreasing values are 'Improving'."""
        from financial_engine import build_inter_document_kpi_trends

        gnpa_facts = [
            {"metric_name": "Gross NPA", "value": 2.15, "unit": "%", "period_or_date": "Q1 FY26"},
            {"metric_name": "GNPA Ratio", "value": 1.97, "unit": "%", "period_or_date": "Q2 FY26"}
        ]
        trends = build_inter_document_kpi_trends(gnpa_facts)
        self.assertEqual(len(trends), 1)
        self.assertEqual(trends[0]["trajectory"], "Improving")

    def test_1_fresh_remote_fetch_with_matching_hash_produces_current_content_verified(self):
        """Fresh remote fetch (REMOTE_FETCH) with matching content hash & versions sets CURRENT_CONTENT_VERIFIED."""
        import doc_intelligence_pipeline
        sym = "TESTSYM_CACHE_REMOTE_OK"
        doc = DocumentItem(
            ticker=sym,
            title="Q1 FY26 Earnings Call Transcript",
            url="https://bse.com/cc_q1_remote.pdf",
            doc_type="concall_transcript",
            period_or_date="Q1 FY26"
        )
        sample_pages = [(1, "Official transcript text for Q1 FY26. Management reports 18% loan growth.")]
        content_hash = database.compute_document_content_hash(sample_pages)

        # Pre-seed cache with matching content hash & current versions
        database.save_document_summary(
            sym, doc.url, doc.title,
            {"key_takeaways": ["18% loan growth in Q1 FY26"]},
            doc_key=doc.doc_key,
            doc_type=doc.doc_type,
            period_or_date=doc.period_or_date,
            content_hash=content_hash,
            extraction_schema_version="4.4",
            extraction_prompt_version="4.4.1"
        )

        # Mock download returning provenance: (pages, "REMOTE_FETCH", True)
        with unittest.mock.patch("doc_intelligence_pipeline.download_and_extract_pdf_with_provenance", return_value=(sample_pages, "REMOTE_FETCH", True)), \
             unittest.mock.patch("doc_intelligence_pipeline.summarize_single_document_with_llm") as mock_llm:
            summary = doc_intelligence_pipeline.get_or_generate_document_summary(sym, "Test Corp", doc)
            mock_llm.assert_not_called()
            self.assertEqual(summary["key_takeaways"], ["18% loan growth in Q1 FY26"])
            self.assertEqual(doc.cache_status, "CURRENT_CONTENT_VERIFIED")
            self.assertEqual(summary["cache_status"], "CURRENT_CONTENT_VERIFIED")

    def test_2_local_cached_pages_only_produces_current_version_content_unchecked(self):
        """When only local page cache is used (not remote verified), matching cache produces CURRENT_VERSION_CONTENT_UNCHECKED."""
        import doc_intelligence_pipeline
        sym = "TESTSYM_CACHE_LOCAL_ONLY"
        doc = DocumentItem(
            ticker=sym,
            title="Q1 FY26 Earnings Call Transcript",
            url="https://bse.com/cc_q1_local.pdf",
            doc_type="concall_transcript",
            period_or_date="Q1 FY26"
        )
        sample_pages = [(1, "Local cached transcript text for Q1 FY26.")]
        content_hash = database.compute_document_content_hash(sample_pages)

        database.save_document_summary(
            sym, doc.url, doc.title,
            {"key_takeaways": ["Local cached takeaway"]},
            doc_key=doc.doc_key,
            doc_type=doc.doc_type,
            period_or_date=doc.period_or_date,
            content_hash=content_hash,
            extraction_schema_version="4.4",
            extraction_prompt_version="4.4.1"
        )

        # Mock download returning provenance: (pages, "LOCAL_PAGE_CACHE", False)
        with unittest.mock.patch("doc_intelligence_pipeline.download_and_extract_pdf_with_provenance", return_value=(sample_pages, "LOCAL_PAGE_CACHE", False)), \
             unittest.mock.patch("doc_intelligence_pipeline.summarize_single_document_with_llm") as mock_llm:
            summary = doc_intelligence_pipeline.get_or_generate_document_summary(sym, "Test Corp", doc)
            # Reused without making LLM call
            mock_llm.assert_not_called()
            self.assertEqual(summary["key_takeaways"], ["Local cached takeaway"])
            self.assertEqual(doc.cache_status, "CURRENT_VERSION_CONTENT_UNCHECKED")
            self.assertEqual(summary["cache_status"], "CURRENT_VERSION_CONTENT_UNCHECKED")

    def test_3_remote_content_changed_rejects_cache_and_reextracts(self):
        """When remote document content changes (different hash), cached summary is rejected and re-extracted via LLM."""
        import doc_intelligence_pipeline
        sym = "TESTSYM_CACHE_CHANGED"
        doc = DocumentItem(
            ticker=sym,
            title="Q1 FY26 Investor Presentation",
            url="https://bse.com/ppt_q1.pdf",
            doc_type="presentation",
            period_or_date="Q1 FY26"
        )
        old_pages = [(1, "Old presentation draft.")]
        old_hash = database.compute_document_content_hash(old_pages)
        database.save_document_summary(
            sym, doc.url, doc.title,
            {"key_takeaways": ["Old draft takeaway"]},
            content_hash=old_hash,
            extraction_schema_version="4.4",
            extraction_prompt_version="4.4.1"
        )

        # New PDF text content from fresh remote fetch
        new_pages = [(1, "Updated revised presentation. NIM expanded to 4.45%.")]
        new_hash = database.compute_document_content_hash(new_pages)
        self.assertNotEqual(old_hash, new_hash)

        with unittest.mock.patch("doc_intelligence_pipeline.download_and_extract_pdf_with_provenance", return_value=(new_pages, "REMOTE_FETCH", True)), \
             unittest.mock.patch("doc_intelligence_pipeline.summarize_single_document_with_llm") as mock_llm:
            mock_llm.return_value = {
                "doc_title": doc.title,
                "doc_url": doc.url,
                "doc_type": doc.doc_type,
                "period_or_date": doc.period_or_date,
                "key_takeaways": ["NIM expanded to 4.45%"]
            }
            summary = doc_intelligence_pipeline.get_or_generate_document_summary(sym, "Test Corp", doc)
            # LLM was called due to content hash mismatch
            mock_llm.assert_called_once()
            self.assertEqual(summary["key_takeaways"], ["NIM expanded to 4.45%"])
            self.assertEqual(summary["content_hash"], new_hash)
            self.assertEqual(doc.cache_status, "CURRENT_CONTENT_VERIFIED")

    def test_4_legacy_hash_missing_labeled_legacy_stale(self):
        """Legacy cached summary rows without content_hash are labeled LEGACY_STALE."""
        sym = "TESTSYM_LEGACY_NULL_HASH"
        url = "https://bse.com/legacy_doc.pdf"
        title = "Legacy Document"

        # Insert summary with null content_hash
        conn = database.get_db_connection()
        try:
            with conn:
                conn.execute("""
                    INSERT OR REPLACE INTO ai_document_summaries (
                        doc_url, symbol, doc_title, summary_json, generated_at,
                        content_hash, extraction_schema_version, extraction_prompt_version
                    ) VALUES (?, ?, ?, ?, ?, NULL, '4.4', '4.4.1')
                """, (url, sym, title, json.dumps({"key_takeaways": ["Legacy bullet"]}), "2026-01-01T00:00:00Z"))
        finally:
            conn.close()

        summaries = database.get_document_summaries(sym)
        self.assertIn(url, summaries)
        self.assertEqual(summaries[url]["cache_status"], "LEGACY_STALE")

    def test_5_local_cache_never_independently_produces_current_content_verified(self):
        """Local cache alone must NEVER claim CURRENT_CONTENT_VERIFIED."""
        import doc_intelligence_pipeline
        sym = "TESTSYM_LOCAL_NEVER_VERIFIED"
        doc = DocumentItem(
            ticker=sym,
            title="Q1 FY26 Concall",
            url="https://bse.com/local_only.pdf",
            doc_type="concall_transcript",
            period_or_date="Q1 FY26"
        )
        pages = [(1, "Offline cached text.")]
        c_hash = database.compute_document_content_hash(pages)
        database.save_document_summary(
            sym, doc.url, doc.title,
            {"key_takeaways": ["Fact"]},
            content_hash=c_hash,
            extraction_schema_version="4.4",
            extraction_prompt_version="4.4.1"
        )

        with unittest.mock.patch("doc_intelligence_pipeline.download_and_extract_pdf_with_provenance", return_value=(pages, "LOCAL_PAGE_CACHE", False)):
            summary = doc_intelligence_pipeline.get_or_generate_document_summary(sym, "Test Corp", doc)
            self.assertNotEqual(summary.get("cache_status"), "CURRENT_CONTENT_VERIFIED")
            self.assertEqual(summary.get("cache_status"), "CURRENT_VERSION_CONTENT_UNCHECKED")
            self.assertNotEqual(doc.cache_status, "CURRENT_CONTENT_VERIFIED")
            self.assertEqual(doc.cache_status, "CURRENT_VERSION_CONTENT_UNCHECKED")

    def test_6_local_cached_pages_with_stale_prompt_and_fresh_llm_extraction(self):
        """Fresh LLM extraction on local cached pages must produce CURRENT_VERSION_CONTENT_UNCHECKED, not verified."""
        import doc_intelligence_pipeline
        sym = "TESTSYM_LOCAL_PROMPT_BUMP"
        doc = DocumentItem(
            ticker=sym,
            title="Q2 FY26 Earnings Call Transcript",
            url="https://bse.com/cc_q2_local_stale_prompt.pdf",
            doc_type="concall_transcript",
            period_or_date="Q2 FY26"
        )
        sample_pages = [(1, "Local cached transcript text from last month.")]
        content_hash = database.compute_document_content_hash(sample_pages)

        # Pre-seed DB cache with older prompt version "4.0.0"
        database.save_document_summary(
            sym, doc.url, doc.title,
            {"key_takeaways": ["Old prompt summary"]},
            doc_key=doc.doc_key,
            doc_type=doc.doc_type,
            period_or_date=doc.period_or_date,
            content_hash=content_hash,
            extraction_schema_version="4.4",
            extraction_prompt_version="4.0.0"  # Older prompt triggers new extraction
        )

        with unittest.mock.patch("doc_intelligence_pipeline.download_and_extract_pdf_with_provenance", return_value=(sample_pages, "LOCAL_PAGE_CACHE", False)), \
             unittest.mock.patch("doc_intelligence_pipeline.summarize_single_document_with_llm") as mock_llm:
            mock_llm.return_value = {
                "doc_title": doc.title,
                "doc_url": doc.url,
                "doc_type": doc.doc_type,
                "period_or_date": doc.period_or_date,
                "key_takeaways": ["Fresh extraction takeaway"]
            }
            summary = doc_intelligence_pipeline.get_or_generate_document_summary(sym, "Test Corp", doc)
            mock_llm.assert_called_once()
            self.assertEqual(summary["key_takeaways"], ["Fresh extraction takeaway"])
            # Fresh extraction on unverified local pages must NOT upgrade to CURRENT_CONTENT_VERIFIED
            self.assertEqual(doc.cache_status, "CURRENT_VERSION_CONTENT_UNCHECKED")
            self.assertEqual(summary["cache_status"], "CURRENT_VERSION_CONTENT_UNCHECKED")

    def test_7_remote_fetched_pages_with_fresh_llm_extraction(self):
        """Fresh LLM extraction on newly fetched remote pages produces CURRENT_CONTENT_VERIFIED."""
        import doc_intelligence_pipeline
        sym = "TESTSYM_REMOTE_FRESH_LLM"
        doc = DocumentItem(
            ticker=sym,
            title="Q2 FY26 Earnings Call Transcript",
            url="https://bse.com/cc_q2_remote_new.pdf",
            doc_type="concall_transcript",
            period_or_date="Q2 FY26"
        )
        sample_pages = [(1, "Newly fetched remote transcript text.")]
        content_hash = database.compute_document_content_hash(sample_pages)

        with unittest.mock.patch("doc_intelligence_pipeline.download_and_extract_pdf_with_provenance", return_value=(sample_pages, "REMOTE_FETCH", True)), \
             unittest.mock.patch("doc_intelligence_pipeline.summarize_single_document_with_llm") as mock_llm:
            mock_llm.return_value = {
                "doc_title": doc.title,
                "doc_url": doc.url,
                "doc_type": doc.doc_type,
                "period_or_date": doc.period_or_date,
                "key_takeaways": ["Remote fresh takeaway"]
            }
            summary = doc_intelligence_pipeline.get_or_generate_document_summary(sym, "Test Corp", doc)
            mock_llm.assert_called_once()
            self.assertEqual(summary["key_takeaways"], ["Remote fresh takeaway"])
            self.assertEqual(doc.cache_status, "CURRENT_CONTENT_VERIFIED")
            self.assertEqual(summary["cache_status"], "CURRENT_CONTENT_VERIFIED")

    def test_8_earnings_presentation_selection_conditions_and_exclusions(self):
        """Test Defect 1: Presentation qualifying conditions (A, B, C), event linkage, and strict exclusions."""
        from doc_intelligence_pipeline import select_default_document_working_set
        from models import DocumentLinks, DocumentItem
        import database

        sym = "ICICIBANK"
        docs = DocumentLinks(
            annual_reports=[
                DocumentItem(ticker=sym, title="ICICI Bank Annual Report 2025-26", url="https://icici.bank.in/ar26.pdf", doc_type="annual_report", period_or_date="FY26"),
                DocumentItem(ticker=sym, title="ICICI Bank Annual Report 2024-25", url="https://icici.bank.in/ar25.pdf", doc_type="annual_report", period_or_date="FY25")
            ],
            regulatory_filings=[
                DocumentItem(ticker=sym, title="ICICI Bank Form 20-F 2026", url="https://sec.gov/20f26.pdf", doc_type="sec_filing", period_or_date="FY26")
            ],
            concalls=[
                DocumentItem(ticker=sym, title="ICICI Bank Concall Q1 FY27 Transcript", url="https://icici.bank.in/cc_q1_fy27.pdf", doc_type="concall_transcript", period_or_date="Q1 FY27"),
                DocumentItem(ticker=sym, title="ICICI Bank Concall Q4 FY26 Transcript", url="https://icici.bank.in/cc_q4_fy26.pdf", doc_type="concall_transcript", period_or_date="Q4 FY26"),
                DocumentItem(ticker=sym, title="ICICI Bank Concall Q3 FY26 Transcript", url="https://icici.bank.in/cc_q3_fy26.pdf", doc_type="concall_transcript", period_or_date="Q3 FY26"),
                DocumentItem(ticker=sym, title="ICICI Bank Concall Q2 FY26 Transcript", url="https://icici.bank.in/cc_q2_fy26.pdf", doc_type="concall_transcript", period_or_date="Q2 FY26")
            ],
            presentations=[
                # 1. Condition A: Explicit quarter ended in title
                DocumentItem(ticker=sym, title="ICICI Bank: Investor Presentation for quarter ended June 30, 2026", url="https://icici.bank.in/ppt_q1_fy27.pdf", doc_type="presentation", period_or_date="June 30, 2026"),
                # 2. Condition B: IR quarterly-results context
                DocumentItem(ticker=sym, title="Performance Review Q4 FY26 Presentation", url="https://icici.bank.in/quarterly-results/ppt_q4_fy26.pdf", doc_type="presentation", period_or_date="Q4 FY26", discovery_source="Company IR"),
                # 3. Condition C: Event-linked to Q3 FY26
                DocumentItem(ticker=sym, title="Investor Presentation Q3 FY26", url="https://icici.bank.in/ppt_q3_fy26.pdf", doc_type="presentation", period_or_date="Q3 FY26"),
                # 4. Condition A/C: Q2 FY26 presentation
                DocumentItem(ticker=sym, title="Financial Results Presentation for quarter ended September 30, 2025", url="https://icici.bank.in/ppt_q2_fy26.pdf", doc_type="presentation", period_or_date="30 Sep 2025"),
                # Exclusions:
                DocumentItem(ticker=sym, title="Notice and Presentation for 32nd AGM", url="https://icici.bank.in/agm_ppt.pdf", doc_type="presentation", period_or_date="FY26"),
                DocumentItem(ticker=sym, title="Debt Investor Presentation 2026", url="https://icici.bank.in/debt_ppt.pdf", doc_type="presentation", period_or_date="FY26"),
                DocumentItem(ticker=sym, title="Generic Corporate Profile Presentation", url="https://icici.bank.in/corporate.pdf", doc_type="presentation", period_or_date="")
            ],
            material_announcements=[]
        )

        ws = select_default_document_working_set(docs)
        selected_ppts = [d for d in ws if database.normalize_document_type(d.doc_type, d.title) == "presentation"]
        self.assertEqual(len(selected_ppts), 4)

        selected_titles = [d.title for d in selected_ppts]
        self.assertIn("ICICI Bank: Investor Presentation for quarter ended June 30, 2026", selected_titles)
        self.assertIn("Performance Review Q4 FY26 Presentation", selected_titles)
        self.assertIn("Investor Presentation Q3 FY26", selected_titles)
        self.assertIn("Financial Results Presentation for quarter ended September 30, 2025", selected_titles)

        # Confirm exclusions are NOT selected
        self.assertNotIn("Notice and Presentation for 32nd AGM", selected_titles)
        self.assertNotIn("Debt Investor Presentation 2026", selected_titles)
        self.assertNotIn("Generic Corporate Profile Presentation", selected_titles)

    def test_9_icicibank_oct2025_multi_candidate_alternate_recovery(self):
        """Test Defect 2: Multi-candidate retry loop skips 404 candidate and uses next valid candidate."""
        import doc_intelligence_pipeline
        sym = "ICICIBANK"
        doc = DocumentItem(
            ticker=sym,
            title="Earnings Call Transcript Q2 FY26 - October 18, 2025",
            url="https://www.icicibank.com/managed-assets/docs/investor/earnings-call-transcript-q2-2026.pdf",
            doc_type="concall_transcript",
            period_or_date="October 18, 2025"
        )

        dead_url = "https://www.icicibank.com/managed-assets/docs/investor/earnings-call-transcript-q2-2026.pdf"
        bse_url = "https://www.bseindia.com/xml-data/corpfiling/AttachLive/icici_q2_transcript_2025.pdf"
        valid_official_url = "https://www.icici.bank.in/about-us/investor-relations/q2-fy26-transcript.pdf"

        # Pre-seed DB with BSE alternate candidate
        database.save_source_documents(sym, [
            DocumentItem(ticker=sym, title="ICICI Bank Transcript Q2 FY26", url=bse_url, doc_type="concall_transcript", period_or_date="Q2 FY26", discovery_source="BSE India")
        ])

        def fake_download(url, symbol=None):
            if "icicibank.com" in url:
                raise Exception("HTTP 404 Not Found")
            elif "icici.bank.in" in url:
                return ([(1, "ICICI Bank Q2 FY26 Earnings Call Transcript Official Text")], "REMOTE_FETCH", True)
            elif "bseindia.com" in url:
                return ([(1, "ICICI Bank Q2 FY26 Concall Transcript BSE Text")], "REMOTE_FETCH", True)
            raise Exception("HTTP 404")

        with patch("doc_intelligence_pipeline.download_and_extract_pdf_with_provenance", side_effect=fake_download), \
             patch("document_sourcing.discover_substantive_alternate_candidates", return_value=[
                 DocumentItem(ticker=sym, title="ICICI Concall Q2 FY26", url=valid_official_url, doc_type="concall_transcript", period_or_date="Q2 FY26", discovery_source="Company IR")
             ]), \
             patch("doc_intelligence_pipeline.summarize_single_document_with_llm") as mock_sum:
            mock_sum.return_value = {
                "doc_title": doc.title,
                "doc_url": valid_official_url,
                "doc_type": "concall_transcript",
                "period_or_date": "Q2 FY26",
                "key_takeaways": ["Q2 FY26 Concall takeaway"]
            }

            summary = doc_intelligence_pipeline.get_or_generate_document_summary(sym, "ICICI Bank Limited", doc)
            self.assertEqual(summary.get("status"), "success")
            self.assertIn("Q2 FY26 Concall takeaway", summary.get("key_takeaways", []))
            self.assertIn(dead_url, doc.source_aliases)

    def test_10_bank_kpi_evolution_multi_period_assembly(self):
        """Test Defect 3: Deterministic bank KPI multi-period normalization and trend assembly."""
        from financial_engine import extract_kpi_identity, build_inter_document_kpi_trends

        facts = [
            # NIM
            {"metric_name": "Domestic NIM", "numeric_value": 4.40, "unit": "%", "period_or_date": "Q1 FY26"},
            {"metric_name": "Net Interest Margin", "numeric_value": 4.36, "unit": "percent", "period_or_date": "Q2 FY26"},
            {"metric_name": "NIM", "numeric_value": 4.25, "unit": "%", "period_or_date": "Q3 FY26"},
            # GNPA
            {"metric_name": "Gross NPA", "numeric_value": 2.30, "unit": "%", "period_or_date": "Q1 FY26"},
            {"metric_name": "GNPA Ratio", "numeric_value": 2.15, "unit": "%", "period_or_date": "Q2 FY26"},
            {"metric_name": "GNPA", "numeric_value": 1.97, "unit": "%", "period_or_date": "Q3 FY26"},
            # CASA
            {"metric_name": "CASA Ratio", "numeric_value": 42.5, "unit": "%", "period_or_date": "Q1 FY26"},
            {"metric_name": "CASA", "numeric_value": 43.6, "unit": "percent", "period_or_date": "Q2 FY26"},
            # Credit Cost
            {"metric_name": "Credit Cost", "numeric_value": 0.45, "unit": "%", "period_or_date": "Q1 FY26"},
            {"metric_name": "Cost of Risk", "numeric_value": 0.35, "unit": "%", "period_or_date": "Q2 FY26"}
        ]

        trends = build_inter_document_kpi_trends(facts)
        metric_names = [t["metric_name"] for t in trends]
        self.assertGreaterEqual(len(trends), 4)
        self.assertIn("Net Interest Margin (NIM)", metric_names)
        self.assertIn("Gross NPA (GNPA)", metric_names)
        self.assertIn("CASA Ratio", metric_names)
        self.assertIn("Credit Cost", metric_names)

        # Verify GNPA improving (lower is better: 2.30 -> 1.97 is Improving)
        gnpa_trend = next(t for t in trends if t["metric_name"] == "Gross NPA (GNPA)")
        self.assertEqual(gnpa_trend["trajectory"], "Improving")

    def test_11_moat_insufficient_evidence_fail_closed(self):
        """Test Defect 5: Moat type fails closed to INSUFFICIENT_EVIDENCE when evidence is absent."""
        from doc_intelligence_models import CompetitivePosition
        from llm_service import sanitize_and_verify_intelligence_result, GenericDocumentIntelligenceResult

        raw_res = GenericDocumentIntelligenceResult(
            symbol="ICICIBANK",
            company_name="ICICI Bank",
            what_changed_recently=[],
            growth_drivers=[],
            promise_vs_delivery=[],
            demand_momentum=None,
            risks_and_cash=None,
            stocker_view=None,
            competitive_position=CompetitivePosition(
                moat_type="Narrow / Evolving",
                key_advantages=[],
                competitive_threats=[]
            )
        )

        sanitized = sanitize_and_verify_intelligence_result(
            result=raw_res,
            symbol="ICICIBANK",
            financial_business_model="BANK"
        )
        self.assertEqual(sanitized.competitive_position.moat_type, "INSUFFICIENT_EVIDENCE")

    def test_12_separation_of_management_narrative_from_observed_causality(self):
        """Test Defect 6: Sanitizes promotional causality linking growth to management slogans."""
        from llm_service import sanitize_and_verify_intelligence_result, GenericDocumentIntelligenceResult
        from doc_intelligence_models import GrowthDriver, RecentChange, StockerView

        raw_res = GenericDocumentIntelligenceResult(
            symbol="ICICIBANK",
            company_name="ICICI Bank",
            what_changed_recently=[
                RecentChange(
                    headline="PBT Growth",
                    category="Margins / Funding Costs",
                    direction="POSITIVE",
                    period_comparison="Q1 FY27 vs Q1 FY26",
                    detail="Strong operating performance demonstrates successful execution of the 360-degree customer-centric strategy across branch networks."
                )
            ],
            growth_drivers=[
                GrowthDriver(
                    driver_title="Customer 360",
                    driver_type="Management Action",
                    description="PBT growth of 20.9% demonstrates the success of the 360-degree customer-centric approach."
                )
            ],
            promise_vs_delivery=[],
            demand_momentum=None,
            risks_and_cash=None,
            stocker_view=StockerView(
                investor_summary="The quarter demonstrates successful execution of the 360-degree customer-centric strategy."
            )
        )

        sanitized = sanitize_and_verify_intelligence_result(
            result=raw_res,
            symbol="ICICIBANK",
            financial_business_model="BANK"
        )

        self.assertNotIn("demonstrates successful execution of", sanitized.what_changed_recently[0].detail)
        self.assertNotIn("demonstrates the success of", sanitized.growth_drivers[0].description)
        self.assertNotIn("demonstrates successful execution of", sanitized.stocker_view.investor_summary)

    def test_13_announcement_working_set_event_family_diversity(self):
        """Test Defect 7: Enforces announcement event-family diversity and supersedes intimation with outcome."""
        from doc_intelligence_pipeline import select_default_document_working_set
        from models import DocumentLinks, DocumentItem
        import database

        sym = "ICICIBANK"
        docs = DocumentLinks(
            annual_reports=[],
            regulatory_filings=[],
            concalls=[],
            presentations=[],
            material_announcements=[
                # Related credit ratings
                DocumentItem(ticker=sym, title="Credit Rating update by CRISIL 24 Aug 2026", url="https://bse.com/ann_cr1.pdf", doc_type="announcement", period_or_date="2026-08-24"),
                DocumentItem(ticker=sym, title="Credit Rating reaffirmation by CRISIL 18 Aug 2026", url="https://bse.com/ann_cr2.pdf", doc_type="announcement", period_or_date="2026-08-18"),
                DocumentItem(ticker=sym, title="Credit Rating review by CRISIL 24 Jul 2026", url="https://bse.com/ann_cr3.pdf", doc_type="announcement", period_or_date="2026-07-24"),
                # Related board meeting intimation + outcome for same fund raise
                DocumentItem(ticker=sym, title="Prior Intimation of Board Meeting for Fund Raising 18 Aug 2026", url="https://bse.com/ann_bm_int.pdf", doc_type="announcement", period_or_date="2026-08-18"),
                DocumentItem(ticker=sym, title="Outcome of Board Meeting for Fund Raising 21 Aug 2026", url="https://bse.com/ann_bm_out.pdf", doc_type="announcement", period_or_date="2026-08-21"),
                # Other material events
                DocumentItem(ticker=sym, title="Acquisition of Equity Stake in FinTech Subsidiary", url="https://bse.com/ann_acq.pdf", doc_type="announcement", period_or_date="2026-08-10"),
                DocumentItem(ticker=sym, title="Regulatory compliance update from RBI", url="https://bse.com/ann_reg.pdf", doc_type="announcement", period_or_date="2026-08-05")
            ]
        )

        ws = select_default_document_working_set(docs)
        selected_anns = [d for d in ws if database.normalize_document_type(d.doc_type, d.title) == "material_announcements"]
        self.assertLessEqual(len(selected_anns), 5)

        selected_titles = [d.title for d in selected_anns]
        # Only 1 credit rating should be selected
        rating_count = sum(1 for t in selected_titles if "Credit Rating" in t)
        self.assertEqual(rating_count, 1)

        # Outcome must be selected and supersedes intimation
        self.assertIn("Outcome of Board Meeting for Fund Raising 21 Aug 2026", selected_titles)
        self.assertNotIn("Prior Intimation of Board Meeting for Fund Raising 18 Aug 2026", selected_titles)

        # Acquisition and regulatory should be selected due to family diversity
        self.assertIn("Acquisition of Equity Stake in FinTech Subsidiary", selected_titles)
        self.assertIn("Regulatory compliance update from RBI", selected_titles)

if __name__ == "__main__":
    unittest.main()
