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
    # F. SOURCE CITATION SAFETY TESTS
    # =========================================================================

    def test_source_citation_safety_unmapped_url_rejected(self):
        """Hallucinated or unmapped document URLs are rejected and set to empty/unsupported."""
        candidate_docs = [{"title": "Official Annual Report FY26", "url": "https://bse.com/ar26.pdf"}]
        
        url, title = sanitize_citation("https://random-blog.com/fake.pdf", "Official Annual Report FY26", candidate_docs)
        # Title match recovers verified official URL
        self.assertEqual(url, "https://bse.com/ar26.pdf")
        
        # Completely unknown URL and title is rejected
        url_fake, title_fake = sanitize_citation("https://hallucinated.com/doc.pdf", "Nonexistent Document", candidate_docs)
        self.assertIsNone(url_fake)
        self.assertIsNone(title_fake)

if __name__ == "__main__":
    unittest.main()
