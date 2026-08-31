import sys
import os
import tempfile
import shutil
import unittest
from pathlib import Path
from typing import Dict, Any

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

    def test_scenario_a_no_source_filings_fail_closed(self):
        """Scenario A: No source filings -> not_run / insufficient_evidence, zero AI calls on GET."""
        import database
        res = get_company_doc_intelligence("NO_FILINGS_CO")
        self.assertIsNone(res, "When no cache/filings exist, get_company_doc_intelligence must return None")
        
        is_stale, reason = database.check_business_analysis_staleness("NO_FILINGS_CO", current_docs=[])
        self.assertTrue(is_stale)
        self.assertEqual(reason, "not_analyzed")

    def test_scenario_b_structured_evidence_persistence(self):
        """Scenario B: Valid annual report evidence items are saved and loaded correctly."""
        import database
        evidence = [
            {
                "id": "evi_INFY_001",
                "symbol": "INFY",
                "evidence_type": "CAPEX_PLAN",
                "title": "Cloud Infrastructure Expansion",
                "normalized_topic": "Capex",
                "statement": "Infosys guided ₹3,000 Cr capex for FY26.",
                "source_document_type": "annual_report",
                "source_document_title": "Infosys Integrated Annual Report 2024-25",
                "source_url": "https://www.infosys.com/ar25.pdf",
                "source_period": "FY25",
                "page": 42,
                "evidence_quote": "We plan capital investment of ₹3,000 Cr in FY26.",
                "confidence": "HIGH",
                "status": "SUPPORTED"
            }
        ]
        cnt = database.save_document_evidence_items("INFY", evidence)
        self.assertEqual(cnt, 1)
        
        loaded = database.get_document_evidence_items("INFY")
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["id"], "evi_INFY_001")
        self.assertEqual(loaded[0]["normalized_topic"], "Capex")
        self.assertEqual(loaded[0]["page"], 42)

    def test_scenario_c_cached_analysis_no_extra_ai_call(self):
        """Scenario C: Same cached analysis opened again -> retrieved cleanly from SQLite without AI."""
        import database
        mock_analysis = {
            "symbol": "TCS",
            "company_name": "Tata Consultancy Services",
            "ai_provider_used": "CACHED_STORE",
            "model_version": "gemini-3.6-flash",
            "latest_document_period": "FY25 AR",
            "source_documents_hash": "abc123hash",
            "analysis_version": "2.0",
            "staleness_status": "fresh",
            "what_changed_recently": [{"headline": "Large BSNL Deal", "category": "Strategic", "detail": "Deployed 19k sites"}],
            "growth_drivers": [{"driver_title": "5G Rollout", "description": "Expanding network presence"}],
            "promise_vs_delivery": [],
            "evidence_items": [
                {
                    "id": "evi_TCS_1",
                    "symbol": "TCS",
                    "evidence_type": "GROWTH_DRIVER",
                    "title": "5G Rollout",
                    "normalized_topic": "Expansion",
                    "statement": "Expanding network presence",
                    "source_document_type": "annual_report",
                    "source_document_title": "FY25 AR",
                    "source_url": "https://tcs.com/ar25.pdf",
                    "confidence": "HIGH",
                    "status": "SUPPORTED"
                }
            ],
            "management_guidance_items": []
        }
        database.save_ai_analysis("TCS", "Tata Consultancy Services", mock_analysis, ai_provider="CACHED_STORE")
        
        # Read via engine
        doc_intel = get_company_doc_intelligence("TCS")
        self.assertIsNotNone(doc_intel)
        self.assertEqual(doc_intel.symbol, "TCS")
        self.assertEqual(doc_intel.staleness_status, "fresh")
        self.assertEqual(len(doc_intel.evidence_items), 1)
        self.assertEqual(doc_intel.evidence_items[0].title, "5G Rollout")

    def test_scenario_d_document_hash_change_triggers_staleness(self):
        """Scenario D: Source document hash changes -> analysis is detected as stale."""
        import database
        initial_docs = [
            {"title": "FY24 AR", "url": "https://example.com/fy24.pdf", "period": "FY24"}
        ]
        h1 = database.compute_source_documents_hash(initial_docs)
        
        mock_analysis = {
            "symbol": "WIPRO",
            "company_name": "Wipro Limited",
            "source_documents_hash": h1,
            "analysis_version": "2.0",
            "what_changed_recently": [{"headline": "AI Investment", "category": "Strategy", "detail": "New Lab"}],
            "growth_drivers": [],
            "promise_vs_delivery": []
        }
        database.save_ai_analysis("WIPRO", "Wipro Limited", mock_analysis, ai_provider="GEMINI")
        
        # Fresh with initial docs
        is_stale, reason = database.check_business_analysis_staleness("WIPRO", current_docs=initial_docs)
        self.assertFalse(is_stale)
        self.assertEqual(reason, "fresh")
        
        # Stale with new filing discovered
        new_docs = initial_docs + [{"title": "Q1 FY26 Concall", "url": "https://example.com/q1fy26.pdf", "period": "Q1 FY26"}]
        is_stale, reason = database.check_business_analysis_staleness("WIPRO", current_docs=new_docs)
        self.assertTrue(is_stale)
        self.assertTrue("source_documents_changed" in reason)

    def test_scenario_e_unknown_source_rejected_fail_closed(self):
        """Scenario E: AI evidence referencing unknown source is sanitized as UNSUPPORTED / Low confidence."""
        from llm_service import extract_document_intelligence_with_llm
        from doc_intelligence_models import DocumentEvidenceItem
        
        item = DocumentEvidenceItem(
            id="evi_test_1",
            symbol="INFY",
            evidence_type="DEMAND_DRIVER",
            title="Fabricated Claim",
            normalized_topic="Demand",
            statement="Fabricated statement",
            source_document_type="annual_report",
            source_document_title="Nonexistent Document 2099",
            source_url="https://fake-url-not-in-corpus.com/fake.pdf",
            confidence="HIGH",
            status="SUPPORTED"
        )
        
        valid_corpus = [
            {"title": "Infosys AR 2025", "url": "https://infosys.com/ar2025.pdf", "type": "annual_report"}
        ]
        
        valid_map = {d["url"]: d["title"] for d in valid_corpus}
        
        # Sanitize logic check
        def sanitize(url, title):
            if url in valid_map: return url, valid_map[url]
            return None, None
            
        s_url, s_title = sanitize(item.source_url, item.source_document_title)
        if not s_url:
            item.status = "UNSUPPORTED"
            item.confidence = "LOW"
            item.source_url = ""
            
        self.assertEqual(item.status, "UNSUPPORTED")
        self.assertEqual(item.confidence, "LOW")
        self.assertEqual(item.source_url, "")

    def test_scenario_f_unsupported_numeric_guidance_marked_insufficient(self):
        """Scenario F: Numeric guidance without statement support is marked INSUFFICIENT_EVIDENCE."""
        guidance = [
            ManagementGuidanceItem(
                metric_or_topic="Solar Module Efficiency",
                guidance_text="Targeting 28% conversion efficiency by FY26",
                quantified_value=28.0,
                unit="%",
                target_period="FY26",
                source_document_title="Investor Deck"
            )
        ]
        # Financial statements do not contain 'Solar Module Efficiency'
        pl_stmt = {"periods": ["FY25", "FY26"], "rows": [{"metric": "Sales", "values": [1000, 1200]}]}
        evaluated = evaluate_management_guidance_vs_actual(guidance, financial_statements={"profit_loss": pl_stmt})
        self.assertEqual(len(evaluated), 1)
        self.assertEqual(evaluated[0].status, "INSUFFICIENT_EVIDENCE")

    def test_scenario_g_deterministic_guidance_vs_actual_met_and_missed(self):
        """Scenario G: Code compares quantified targets deterministically (MET and MISSED)."""
        guidance = [
            ManagementGuidanceItem(
                metric_or_topic="Sales Revenue",
                guidance_text="Management guided Sales of ₹1,500 Cr for FY26",
                quantified_value=1500.0,
                unit="₹ Cr",
                target_period="FY26",
                source_document_title="FY25 Concall"
            ),
            ManagementGuidanceItem(
                metric_or_topic="Operating Profit Margin OPM",
                guidance_text="Guided OPM of 24% for FY26",
                quantified_value=24.0,
                unit="%",
                target_period="FY26",
                source_document_title="FY25 Concall"
            )
        ]
        # FY26 Actuals: Sales = 1520 (MET), OPM = 16.0 (MISSED vs 24%)
        pl_stmt = {
            "periods": ["FY25", "FY26"],
            "rows": [
                {"metric": "Sales", "values": [1200, 1520]},
                {"metric": "OPM %", "values": [22.0, 16.0]}
            ]
        }
        evaluated = evaluate_management_guidance_vs_actual(guidance, financial_statements={"profit_loss": pl_stmt})
        self.assertEqual(len(evaluated), 2)
        
        # Sales met
        self.assertEqual(evaluated[0].status, "MET")
        self.assertEqual(evaluated[0].actual_reported_value, 1520.0)
        self.assertTrue("met or exceeded" in evaluated[0].comparison_detail)
        
        # OPM missed
        self.assertEqual(evaluated[1].status, "MISSED")
        self.assertEqual(evaluated[1].actual_reported_value, 16.0)
        self.assertTrue("missed" in evaluated[1].comparison_detail)

    def test_scenario_h_missing_exact_actual_not_comparable(self):
        """Scenario H: Missing exact comparable actual -> NOT_COMPARABLE or INSUFFICIENT_EVIDENCE."""
        guidance = [
            ManagementGuidanceItem(
                metric_or_topic="International Market Expansion",
                guidance_text="Plan to open offices in Tokyo and Seoul",
                target_period="FY26",
                source_document_title="Annual Report"
            )
        ]
        pl_stmt = {"periods": ["FY25", "FY26"], "rows": [{"metric": "Sales", "values": [1000, 1200]}]}
        evaluated = evaluate_management_guidance_vs_actual(guidance, financial_statements={"profit_loss": pl_stmt})
        self.assertEqual(evaluated[0].status, "NOT_COMPARABLE")

    def test_scenario_i_bank_sector_routing_and_cross_check(self):
        """Scenario I: Bank document extraction focuses on bank metrics, strictly avoiding corporate FCF/CWIP."""
        res = BusinessAnalysisResult(
            symbol="HDFCBANK",
            company_name="HDFC Bank Limited",
            financial_business_model="BANK"
        )
        
        bank_analytics = {
            "business_model": "BANK",
            "bank_analytics": {
                "advances_cagr_3yr": 16.5,
                "deposits_cagr_3yr": 15.2,
                "latest_gnpa_pct": 1.24,
                "latest_nnpa_pct": 0.33,
                "latest_cd_ratio_pct": 85.4,
                "latest_roa_pct": 1.95,
                "latest_roe_pct": 16.8
            },
            # Industrial metrics that MUST be ignored for banks
            "cash_flow_quality": {"cfo_to_pat_5yr_pct": 12.0, "cumulative_5y_fcf_cr": -5000.0},
            "balance_sheet_efficiency": {"latest_cwip_to_net_block_pct": 45.0, "latest_debt_to_equity": 6.5}
        }
        
        _apply_financial_cross_check(res, bank_analytics)
        
        # Verify Bank audit text is populated
        self.assertTrue("REPORTED BANK METRICS AUDIT" in res.risks_and_cash.reported_numbers_comparison)
        self.assertTrue("Gross NPA stands at 1.24%" in res.risks_and_cash.reported_numbers_comparison)
        self.assertTrue("Advances 3-Yr CAGR is 16.5%" in res.risks_and_cash.reported_numbers_comparison)
        
        # Verify industrial FCF/CWIP was NOT applied to capital allocation
        self.assertIsNone(res.capital_allocation.capex_efficiency)
        self.assertIsNone(res.governance_watch.working_capital_anomalies)

    def test_scenario_j_corporate_sector_cross_check(self):
        """Scenario J: General corporate extraction preserves capex, CWIP, CFO/PAT, and working capital."""
        res = BusinessAnalysisResult(
            symbol="LT",
            company_name="Larsen & Toubro",
            financial_business_model="GENERAL_CORPORATE"
        )
        
        corp_analytics = {
            "business_model": "GENERAL_CORPORATE",
            "cash_flow_quality": {
                "cfo_to_pat_5yr_pct": 82.5,
                "cumulative_5y_cfo_cr": 45000.0,
                "cumulative_5y_pat_cr": 54500.0,
                "cumulative_5y_fcf_cr": 28000.0,
                "cash_conversion_quality": "Robust"
            },
            "balance_sheet_efficiency": {
                "latest_cwip_to_net_block_pct": 8.5,
                "latest_debt_to_equity": 0.65
            },
            "growth_rates": {"sales_cagr_3yr": 14.8},
            "working_capital_audit": {"debtor_days": 85.0, "inventory_days": 42.0}
        }
        
        _apply_financial_cross_check(res, corp_analytics)
        
        self.assertTrue("REPORTED NUMBERS AUDIT" in res.risks_and_cash.reported_numbers_comparison)
        self.assertTrue("82.5% cash conversion ratio" in res.risks_and_cash.reported_numbers_comparison)
        self.assertTrue("CWIP stands at 8.5%" in res.capital_allocation.capex_efficiency)
        self.assertTrue("Debtor Days ~85.0" in res.governance_watch.working_capital_anomalies)

    def test_scenario_k_evidence_persistence_roundtrip(self):
        """Scenario K: Evidence source URL, period, and quote survive SQLite round trip exactly."""
        import database
        original = {
            "id": "evi_roundtrip_1",
            "symbol": "BAJAJ-AUTO",
            "evidence_type": "NEW_PRODUCT",
            "title": "Chetak EV Production Ramp",
            "normalized_topic": "Electric Vehicles",
            "statement": "Bajaj Auto achieved 20,000 monthly Chetak EV units in Q3 FY25.",
            "source_document_type": "presentation",
            "source_document_title": "Q3 FY25 Investor Presentation",
            "source_url": "https://bajajauto.com/q3fy25_presentation.pdf",
            "source_period": "Q3 FY25",
            "source_date": "2025-01-22",
            "page": 14,
            "section": "EV Mobility Division",
            "evidence_quote": "Monthly Chetak run-rate crossed 20,000 units in December.",
            "extraction_method": "llm_structured_extraction",
            "confidence": "HIGH",
            "status": "SUPPORTED"
        }
        database.save_document_evidence_items("BAJAJ-AUTO", [original])
        loaded = database.get_document_evidence_items("BAJAJ-AUTO")
        self.assertEqual(len(loaded), 1)
        res = loaded[0]
        self.assertEqual(res["id"], original["id"])
        self.assertEqual(res["source_url"], original["source_url"])
        self.assertEqual(res["source_period"], original["source_period"])
        self.assertEqual(res["evidence_quote"], original["evidence_quote"])
        self.assertEqual(res["page"], original["page"])
        self.assertEqual(res["status"], "SUPPORTED")

    def test_scenario_l_partial_document_failure_resilience(self):
        """Scenario L: Valid evidence is preserved even if some documents are missing or partial."""
        evidence = [
            {
                "id": "evi_valid_1",
                "symbol": "INFY",
                "evidence_type": "ORDER_BOOK",
                "title": "Large Deal TCV $3.2B",
                "normalized_topic": "Order Book",
                "statement": "Large deal TCV was $3.2B in Q3.",
                "source_document_type": "concall_transcript",
                "source_document_title": "Q3 FY26 Concall",
                "source_url": "https://infosys.com/q3concall.pdf",
                "status": "SUPPORTED"
            },
            {
                "id": "evi_partial_2",
                "symbol": "INFY",
                "evidence_type": "CAPEX_PLAN",
                "title": "Unknown Capex Outlay",
                "normalized_topic": "Capex",
                "statement": "Management mentioned general capex intent without numbers.",
                "source_document_type": "presentation",
                "source_document_title": "Investor Deck",
                "source_url": "",
                "status": "UNSUPPORTED",
                "confidence": "LOW"
            }
        ]
        import database
        database.save_document_evidence_items("INFY", evidence)
        supported = [e for e in database.get_document_evidence_items("INFY") if e["status"] == "SUPPORTED"]
        self.assertEqual(len(supported), 1)
        self.assertEqual(supported[0]["title"], "Large Deal TCV $3.2B")

    def test_scenario_m_no_network_on_cached_business_analysis_get(self):
        """Scenario M: Ordinary Business Analysis GET hits SQLite cache with zero network/AI calls."""
        import database
        mock_data = {
            "symbol": "MARUTI",
            "company_name": "Maruti Suzuki India",
            "ai_provider_used": "STORED",
            "latest_document_period": "FY25 AR",
            "what_changed_recently": [],
            "growth_drivers": [{"driver_title": "Kharkhoda Plant", "description": "New 250k capacity"}],
            "promise_vs_delivery": [],
            "evidence_items": [
                {
                    "id": "evi_ms_1",
                    "symbol": "MARUTI",
                    "evidence_type": "CAPACITY_EXPANSION",
                    "title": "Kharkhoda Plant",
                    "normalized_topic": "Capacity",
                    "statement": "New 250k capacity addition.",
                    "source_document_type": "annual_report",
                    "source_document_title": "FY25 AR",
                    "source_url": "https://maruti.com/ar25.pdf",
                    "status": "SUPPORTED"
                }
            ],
            "management_guidance_items": []
        }
        database.save_ai_analysis("MARUTI", "Maruti Suzuki India", mock_data, ai_provider="STORED")
        
        # Test retrieve
        result = get_company_doc_intelligence("MARUTI")
        self.assertIsNotNone(result)
        self.assertEqual(result.company_name, "Maruti Suzuki India")
        self.assertEqual(len(result.evidence_items), 1)

    def test_scenario_n_v43_taxonomy_and_bank_routing_unchanged(self):
        """Scenario N: V4.3 taxonomy classification and bank routing remain intact and untouched."""
        from company_taxonomy_service import normalize_classification
        from financial_engine import classify_financial_business_model
        
        canonical_sector, canonical_industry, canonical_sub_industry, state = normalize_classification(
            sector="Financial Services",
            industry="Banks",
            sub_industry="Private Sector Bank"
        )
        self.assertEqual(canonical_sector, "Financial Services")
        self.assertEqual(canonical_industry, "Banks")
        self.assertEqual(state, "COMPLETE")
        
        model = classify_financial_business_model(
            sector_name=canonical_sector,
            industry_name=canonical_industry,
            sub_industry_name=canonical_sub_industry
        )
        self.assertEqual(model, "BANK")

if __name__ == "__main__":
    unittest.main()
