# test_canonical_source_filings_v44.py
# Tests Canonical Document Identity, Filing Summary Association, and Truthful AI Status

import unittest
import json
import sqlite3
import os
from unittest.mock import patch, MagicMock

import database
import main
from models import DocumentItem, DocumentLinks, SourceFilingsResponse
import doc_intelligence_pipeline

class TestCanonicalSourceFilingsV44(unittest.TestCase):
    def setUp(self):
        database.init_db()
        # Clean test records
        conn = database.get_db_connection()
        try:
            with conn:
                conn.execute("DELETE FROM source_documents WHERE symbol = 'TESTSYM';")
                conn.execute("DELETE FROM ai_document_summaries WHERE symbol = 'TESTSYM';")
                conn.execute("DELETE FROM ai_analysis_cache WHERE symbol = 'TESTSYM';")
        finally:
            conn.close()

    def tearDown(self):
        conn = database.get_db_connection()
        try:
            with conn:
                conn.execute("DELETE FROM source_documents WHERE symbol = 'TESTSYM';")
                conn.execute("DELETE FROM ai_document_summaries WHERE symbol = 'TESTSYM';")
                conn.execute("DELETE FROM ai_analysis_cache WHERE symbol = 'TESTSYM';")
        finally:
            conn.close()

    def test_scenario_a_same_document_different_representation_canonical_resolution(self):
        """
        A. SAME DOCUMENT, DIFFERENT REPRESENTATION
        Canonical filing: URL A = persisted BSE/exchange document.
        Legacy/Screener representation: URL B = equivalent representation of same filing.
        Expected: displayed canonical filing has its summary via canonical key/unambiguous identity.
        """
        sym = "TESTSYM"
        # 1. Canonical source document in database (from BSE discovery)
        bse_url = "https://www.bseindia.com/stockinfo/AnnPdfOpen.aspx?Pname=TESTSYM_AR_2026.pdf#page=1"
        doc = DocumentItem(
            ticker=sym,
            company_name="Test Corp",
            title="TESTSYM Annual Report FY26",
            url=bse_url,
            doc_type="annual_report",
            period_or_date="FY26",
            discovery_source="BSE"
        )
        database.save_source_documents(sym, [doc])

        # 2. AI analysis was run using Screener/direct link representation
        screener_url = "https://www.screener.in/company/TESTSYM/annual-reports/2026/"
        summary_payload = {
            "doc_title": "TESTSYM Annual Report 2026",
            "doc_url": screener_url,
            "doc_type": "annual_report",
            "period_or_date": "FY26",
            "key_takeaways": ["Revenue expanded 18% YoY", "Margins improved by 140 bps"],
            "management_tone": "Optimistic"
        }
        database.save_document_summary(sym, screener_url, "TESTSYM Annual Report 2026", summary_payload, doc_type="annual_report", period_or_date="FY26")

        # 3. Request source filings for TESTSYM
        resp = main.get_stock_source_filings(sym)
        docs = resp["documents"]
        summaries = resp["summaries"]

        # Find the canonical AR
        self.assertEqual(len(docs["annual_reports"]), 1)
        canonical_doc = docs["annual_reports"][0]
        
        # Verify canonical URL was sanitized and doc_key exists
        self.assertTrue(canonical_doc["doc_key"])
        self.assertEqual(canonical_doc["ai_status"], "AI_ANALYZED")

        # Verify summary lookup resolves for the displayed filing
        summary_match = summaries.get(canonical_doc["doc_key"]) or summaries.get(canonical_doc["url"]) or summaries.get(database.compute_canonical_semantic_key(sym, "annual_report", "FY26"))
        self.assertIsNotNone(summary_match)
        self.assertIn("Revenue expanded 18% YoY", summary_match["key_takeaways"])

    def test_scenario_b_exact_same_url_works_normally(self):
        """
        B. EXACT SAME URL
        Works normally with direct URL matching and canonical doc_key.
        """
        sym = "TESTSYM"
        url = "https://www.bseindia.com/stockinfo/AnnPdfOpen.aspx?Pname=Exact_URL_Doc.pdf"
        doc = DocumentItem(
            ticker=sym,
            company_name="Test Corp",
            title="TESTSYM Concall Transcript Q1 FY26",
            url=url,
            doc_type="concall_transcript",
            period_or_date="Q1 FY26",
            discovery_source="BSE"
        )
        database.save_source_documents(sym, [doc])
        summary_payload = {
            "doc_title": "TESTSYM Concall Transcript Q1 FY26",
            "doc_url": url,
            "doc_type": "concall_transcript",
            "period_or_date": "Q1 FY26",
            "key_takeaways": ["Order book reached record levels"],
            "management_tone": "Confident"
        }
        database.save_document_summary(sym, url, doc.title, summary_payload, doc_type="concall_transcript", period_or_date="Q1 FY26")

        resp = main.get_stock_source_filings(sym)
        concalls = resp["documents"]["concalls"]
        self.assertEqual(len(concalls), 1)
        self.assertEqual(concalls[0]["ai_status"], "AI_ANALYZED")
        self.assertIn(url, resp["summaries"])

    def test_scenario_c_different_filings_with_similar_titles_do_not_cross_attach(self):
        """
        C. DIFFERENT FILINGS WITH SIMILAR TITLES
        Summary for FY26 must NOT cross-attach to FY25 filing.
        """
        sym = "TESTSYM"
        doc_fy26 = DocumentItem(
            ticker=sym,
            company_name="Test Corp",
            title="TESTSYM Annual Report FY26",
            url="https://bse.com/TESTSYM_FY26.pdf",
            doc_type="annual_report",
            period_or_date="FY26"
        )
        doc_fy25 = DocumentItem(
            ticker=sym,
            company_name="Test Corp",
            title="TESTSYM Annual Report FY25",
            url="https://bse.com/TESTSYM_FY25.pdf",
            doc_type="annual_report",
            period_or_date="FY25"
        )
        database.save_source_documents(sym, [doc_fy26, doc_fy25])

        # Summary saved ONLY for FY26
        summary_payload_fy26 = {
            "doc_title": "TESTSYM Annual Report FY26",
            "doc_url": doc_fy26.url,
            "doc_type": "annual_report",
            "period_or_date": "FY26",
            "key_takeaways": ["FY26 Growth drivers executed"],
            "management_tone": "Confident"
        }
        database.save_document_summary(sym, doc_fy26.url, doc_fy26.title, summary_payload_fy26, doc_type="annual_report", period_or_date="FY26")

        resp = main.get_stock_source_filings(sym)
        ars = resp["documents"]["annual_reports"]
        
        ar_26 = next(a for a in ars if a["period_or_date"] == "FY26")
        ar_25 = next(a for a in ars if a["period_or_date"] == "FY25")

        self.assertEqual(ar_26["ai_status"], "AI_ANALYZED")
        self.assertNotEqual(ar_25["ai_status"], "AI_ANALYZED")

    def test_scenario_d_not_selected_document_status_after_company_analysis(self):
        """
        D. NOT-SELECTED DOCUMENT
        Document is displayed but was outside current AI working set.
        Expected status: NOT_SELECTED (not 'Run Analysis' and not 'AI_ANALYZED').
        """
        sym = "TESTSYM"
        core_doc = DocumentItem(
            ticker=sym,
            company_name="Test Corp",
            title="TESTSYM Annual Report FY26",
            url="https://bse.com/core_ar26.pdf",
            doc_type="annual_report",
            period_or_date="FY26"
        )
        extra_announcement = DocumentItem(
            ticker=sym,
            company_name="Test Corp",
            title="TESTSYM Routine Factory Holiday Notice",
            url="https://bse.com/ann_routine.pdf",
            doc_type="announcement",
            period_or_date="2025-01-01"
        )
        database.save_source_documents(sym, [core_doc, extra_announcement])

        # Save AI summary for core_doc
        database.save_document_summary(sym, core_doc.url, core_doc.title, {
            "doc_title": core_doc.title,
            "doc_url": core_doc.url,
            "key_takeaways": ["Key core takeaway"]
        })

        # Save Company-level AI analysis cache to mark analysis as executed
        database.save_ai_analysis(
            symbol=sym,
            company_name="Test Corp",
            intelligence_data={
                "what_changed_recently": [{"statement": "Expansion announced"}],
                "growth_drivers": [{"title": "Cloud"}],
                "promise_vs_delivery": []
            },
            ai_provider="GEMINI",
            source_docs_count=1
        )

        resp = main.get_stock_source_filings(sym)
        self.assertTrue(resp["has_company_analysis"])
        
        ars = resp["documents"]["annual_reports"]
        anns = resp["documents"]["material_announcements"]

        self.assertEqual(ars[0]["ai_status"], "AI_ANALYZED")
        self.assertEqual(anns[0]["ai_status"], "NOT_SELECTED")

    def test_scenario_e_failed_document_status(self):
        """
        E. FAILED DOCUMENT
        If extraction attempt fails, status is PROCESSING_FAILED and does not borrow another summary.
        """
        sym = "TESTSYM"
        corrupt_doc = DocumentItem(
            ticker=sym,
            company_name="Test Corp",
            title="TESTSYM Corrupted Transcript",
            url="https://bse.com/corrupted.pdf",
            doc_type="concall_transcript",
            period_or_date="Q2 FY26"
        )
        database.save_source_documents(sym, [corrupt_doc])

        failed_summary = {
            "doc_title": corrupt_doc.title,
            "doc_url": corrupt_doc.url,
            "doc_type": "concall_transcript",
            "period_or_date": "Q2 FY26",
            "status": "failed",
            "error": "PDF stream ended unexpectedly",
            "key_takeaways": []
        }
        database.save_document_summary(sym, corrupt_doc.url, corrupt_doc.title, failed_summary, doc_type="concall_transcript", period_or_date="Q2 FY26")

        resp = main.get_stock_source_filings(sym)
        concalls = resp["documents"]["concalls"]
        self.assertEqual(len(concalls), 1)
        self.assertEqual(concalls[0]["ai_status"], "PROCESSING_FAILED")
        self.assertIn("PDF stream ended unexpectedly", concalls[0]["ai_failure_reason"])

if __name__ == '__main__':
    unittest.main()
