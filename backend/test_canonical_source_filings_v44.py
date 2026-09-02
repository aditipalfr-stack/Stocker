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
        canonical_c_url = concalls[0]["url"]
        self.assertIn(canonical_c_url, resp["summaries"])

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

    def test_scenario_f_duplicate_url_merging(self):
        """
        F. DUPLICATE PHYSICAL DOCUMENTS MERGING
        Two discovered records with the same canonical URL must merge into ONE canonical record,
        combining discovered sources and not double counting.
        """
        sym = "TESTSYM"
        doc_bse = DocumentItem(
            ticker=sym,
            company_name="Test Corp",
            title="Notice Of 32Nd AGM And Annual Report 2025-26",
            url="https://www.bseindia.com/xml-data/corpfiling/AttachHis/canonical_report.pdf",
            doc_type="annual_report",
            period_or_date="18 Jul 2026",
            discovery_source="BSE India"
        )
        doc_screener = DocumentItem(
            ticker=sym,
            company_name="Test Corp",
            title="Annual Report 2026",
            url="https://www.bseindia.com/xml-data/corpfiling/AttachHis/canonical_report.pdf",
            doc_type="annual_report",
            period_or_date="FY2026",
            discovery_source="Screener.in"
        )
        database.save_source_documents(sym, [doc_bse, doc_screener])

        resp = main.get_stock_source_filings(sym)
        ars = resp["documents"]["annual_reports"]
        all_docs = resp["documents"]["all_documents"]

        # Exactly 1 filing present
        self.assertEqual(len(ars), 1)
        self.assertEqual(len(all_docs), 1)

        # Discovered sources merged
        canonical_ar = ars[0]
        self.assertIn("BSE India", canonical_ar["discovered_sources"])
        self.assertIn("Screener.in", canonical_ar["discovered_sources"])
        # Preferred title is official/descriptive
        self.assertEqual(canonical_ar["title"], "Notice Of 32Nd AGM And Annual Report 2025-26")
        self.assertIn("Annual Report 2026", canonical_ar["source_aliases"])

    def test_scenario_g_canonical_url_fragment_normalization(self):
        """
        G. CANONICAL URL FRAGMENT NORMALIZATION
        URLs with fragments (#page=1) or search parameters merge cleanly.
        """
        sym = "TESTSYM"
        doc_with_hash = DocumentItem(
            ticker=sym,
            company_name="Test Corp",
            title="TESTSYM Investor Presentation Jul 2026",
            url="https://bseindia.com/filings/deck.pdf#page=1",
            doc_type="presentation",
            period_or_date="Jul 2026",
            discovery_source="BSE India"
        )
        doc_clean = DocumentItem(
            ticker=sym,
            company_name="Test Corp",
            title="Presentation",
            url="https://bseindia.com/filings/deck.pdf",
            doc_type="presentation",
            period_or_date="Jul 2026",
            discovery_source="Screener.in"
        )
        database.save_source_documents(sym, [doc_with_hash, doc_clean])

        resp = main.get_stock_source_filings(sym)
        ppts = resp["documents"]["presentations"]
        self.assertEqual(len(ppts), 1)
        self.assertEqual(ppts[0]["url"], "https://www.bseindia.com/filings/deck.pdf")
        self.assertEqual(ppts[0]["title"], "TESTSYM Investor Presentation Jul 2026")

    def test_scenario_h_form_20f_and_brsr_classification_and_working_set_priority(self):
        """
        H. CLASSIFICATION & AI WORKING SET PRIORITY
        Form 20-F is regulatory_annual_filing, BRSR is brsr_esg, Annual Report is annual_report.
        AI working set prioritizes AR > 20-F > Concalls > PPTs ahead of BRSR.
        """
        from document_sourcing import classify_document_title
        
        ar_type, _ = classify_document_title("Notice Of 32Nd Annual General Meeting And Annual Report 2025-26")
        brsr_type, _ = classify_document_title("Business Responsibility and Sustainability Reporting (BRSR)")
        f20_type, _ = classify_document_title("Filing Of Annual Report In The Form 20-F For The Year Ended March 31, 2026.")
        
        self.assertEqual(ar_type, "annual_report")
        self.assertEqual(brsr_type, "brsr_esg")
        self.assertEqual(f20_type, "regulatory_annual_filing")

        doc_links = DocumentLinks(
            annual_reports=[
                DocumentItem(ticker="TESTSYM", title="Annual Report FY26", url="https://bse.com/ar26.pdf", doc_type="annual_report", period_or_date="18 Jul 2026"),
                DocumentItem(ticker="TESTSYM", title="Annual Report FY25", url="https://bse.com/ar25.pdf", doc_type="annual_report", period_or_date="FY25")
            ],
            regulatory_annual_filings=[
                DocumentItem(ticker="TESTSYM", title="Form 20-F FY26", url="https://bse.com/20f.pdf", doc_type="regulatory_annual_filing", period_or_date="20 Jul 2026")
            ],
            concalls=[
                DocumentItem(ticker="TESTSYM", title="Concall Q1 FY27", url="https://bse.com/cc1.pdf", doc_type="concall_transcript", period_or_date="Q1 FY27")
            ],
            presentations=[
                DocumentItem(ticker="TESTSYM", title="Investor Presentation", url="https://bse.com/ppt1.pdf", doc_type="presentation", period_or_date="Jul 2026")
            ],
            brsr_reports=[
                DocumentItem(ticker="TESTSYM", title="BRSR 2026", url="https://bse.com/brsr26.pdf", doc_type="brsr_esg", period_or_date="18 Jul 2026")
            ]
        )

        working_set = doc_intelligence_pipeline.select_default_document_working_set(doc_links)
        ws_types = [d.doc_type for d in working_set]
        
        self.assertIn("annual_report", ws_types)
        self.assertIn("regulatory_annual_filing", ws_types)
        self.assertIn("concall_transcript", ws_types)
        self.assertIn("presentation", ws_types)

    def test_scenario_i_global_chronological_ordering(self):
        """
        I. GLOBAL CHRONOLOGICAL ORDERING
        Timeline is sorted strictly newest-first across all document types.
        """
        sym = "TESTSYM"
        items = [
            DocumentItem(ticker=sym, title="Older AR 2012", url="https://bse.com/ar12.pdf", doc_type="annual_report", period_or_date="FY2012"),
            DocumentItem(ticker=sym, title="Regulation 30 Announcement 24 Aug", url="https://bse.com/reg30.pdf", doc_type="announcement", period_or_date="24 Aug 2026"),
            DocumentItem(ticker=sym, title="Notice of AGM & AR 2026", url="https://bse.com/ar26.pdf", doc_type="annual_report", period_or_date="18 Jul 2026"),
            DocumentItem(ticker=sym, title="Form 20-F 2026", url="https://bse.com/20f26.pdf", doc_type="regulatory_annual_filing", period_or_date="20 Jul 2026"),
            DocumentItem(ticker=sym, title="Investor Presentation Jul 2026", url="https://bse.com/ppt.pdf", doc_type="presentation", period_or_date="Jul 2026"),
            DocumentItem(ticker=sym, title="Concall Q1 FY27", url="https://bse.com/cc.pdf", doc_type="concall_transcript", period_or_date="Q1 FY27"),
            DocumentItem(ticker=sym, title="AR 2025", url="https://bse.com/ar25.pdf", doc_type="annual_report", period_or_date="FY2025"),
            DocumentItem(ticker=sym, title="Undated General Notice", url="https://bse.com/notice.pdf", doc_type="general", period_or_date=None)
        ]
        database.save_source_documents(sym, items)

        resp = main.get_stock_source_filings(sym)
        all_docs = resp["documents"]["all_documents"]

        titles_in_order = [d["title"] for d in all_docs]
        expected_top = [
            "Regulation 30 Announcement 24 Aug", # 2026-08-24
            "Form 20-F 2026",                   # 2026-07-20
            "Notice of AGM & AR 2026",          # 2026-07-18
            "Investor Presentation Jul 2026",   # 2026-07-01
            "Concall Q1 FY27",                  # 2026-06-30
            "AR 2025",                          # 2025-03-31
            "Older AR 2012",                    # 2012-03-31
            "Undated General Notice"            # 1970-01-01
        ]
        self.assertEqual(titles_in_order, expected_top)

    def test_scenario_j_fy_only_dates_deterministic(self):
        """
        J. FY-ONLY DATES DETERMINISTIC SORTING
        FY dates sort deterministically without changing visible text or inventing dates.
        """
        ts_fy26 = database.parse_document_sort_timestamp("FY2026")
        ts_fy25 = database.parse_document_sort_timestamp("FY2025")
        ts_fy24 = database.parse_document_sort_timestamp("FY24")
        ts_none = database.parse_document_sort_timestamp(None)

        self.assertEqual(ts_fy26, "2026-03-31")
        self.assertEqual(ts_fy25, "2025-03-31")
        self.assertEqual(ts_fy24, "2024-03-31")
        self.assertEqual(ts_none, "1970-01-01")
        self.assertTrue(ts_fy26 > ts_fy25 > ts_fy24 > ts_none)

    def test_source_strategy_a_annual_report_duplicate(self):
        """
        A. ANNUAL REPORT DUPLICATE
        Screener FY26 annual report + BSE FY26 annual report for same FY
        Expected: 1 canonical Annual Report, 2 discovered sources.
        """
        sym = "TESTSYM"
        doc_screener = DocumentItem(
            ticker=sym,
            title="TESTSYM Annual Report 2026",
            url="https://www.bseindia.com/xml-data/corpfiling/AttachHis/ar_fy26_screener.pdf",
            doc_type="annual_report",
            period_or_date="FY2026",
            discovery_source="Screener.in"
        )
        doc_bse = DocumentItem(
            ticker=sym,
            title="Notice Of 32Nd Annual General Meeting And Annual Report 2025-26",
            url="https://www.bseindia.com/xml-data/corpfiling/AttachHis/ar_fy26_bse.pdf",
            doc_type="annual_report",
            period_or_date="18 Jul 2026",
            discovery_source="BSE India"
        )
        database.save_source_documents(sym, [doc_screener, doc_bse])

        resp = main.get_stock_source_filings(sym)
        ars = resp["documents"]["annual_reports"]
        self.assertEqual(len(ars), 1)
        self.assertIn("Screener.in", ars[0]["discovered_sources"])
        self.assertIn("BSE India", ars[0]["discovered_sources"])
        self.assertEqual(ars[0]["title"], "Notice Of 32Nd Annual General Meeting And Annual Report 2025-26")
        self.assertEqual(ars[0]["period_or_date"], "18 Jul 2026")

    def test_source_strategy_b_distinct_annual_and_20f(self):
        """
        B. DISTINCT ANNUAL + 20-F
        Same FY, different physical filings
        Expected: 2 canonical documents.
        """
        sym = "TESTSYM"
        doc_ar = DocumentItem(
            ticker=sym,
            title="Annual Report 2025-26",
            url="https://www.bseindia.com/xml-data/corpfiling/AttachHis/ar_2026.pdf",
            doc_type="annual_report",
            period_or_date="18 Jul 2026",
            discovery_source="BSE India"
        )
        doc_20f = DocumentItem(
            ticker=sym,
            title="Filing Of Annual Report In Form 20-F For Year Ended March 31, 2026",
            url="https://www.bseindia.com/xml-data/corpfiling/AttachHis/20f_2026.pdf",
            doc_type="regulatory_annual_filing",
            period_or_date="20 Jul 2026",
            discovery_source="BSE India"
        )
        database.save_source_documents(sym, [doc_ar, doc_20f])

        resp = main.get_stock_source_filings(sym)
        ars = resp["documents"]["annual_reports"]
        reg_20f = resp["documents"]["regulatory_annual_filings"]
        
        self.assertEqual(len(ars), 1)
        self.assertEqual(len(reg_20f), 1)
        self.assertEqual(ars[0]["doc_type"], "annual_report")
        self.assertEqual(reg_20f[0]["doc_type"], "regulatory_annual_filing")

    def test_source_strategy_c_screener_concall_plus_bse_wrapper(self):
        """
        C. SCREENER CONCALL + BSE WRAPPER
        Screener has substantive Q1 FY27 transcript.
        BSE filing is a notification linking to same event transcript.
        Expected: one substantive transcript for AI. BSE wrapper retained only as provenance.
        """
        sym = "TESTSYM"
        doc_screener_transcript = DocumentItem(
            ticker=sym,
            title="TESTSYM Jul 2026 Earnings Call Transcript",
            url="https://www.icici.bank.in/content/dam/transcript-for-earnings-call-held-on-july-18-2026.pdf",
            doc_type="concall_transcript",
            period_or_date="Jul 2026",
            discovery_source="Screener.in"
        )
        doc_bse_notification = DocumentItem(
            ticker=sym,
            title="Transcripts Of The Call With Media And Of Earnings Call With Analysts And Investors.",
            url="https://www.bseindia.com/xml-data/corpfiling/AttachHis/wrapper_notice.pdf",
            doc_type="concall_transcript",
            period_or_date="23 Jul 2026",
            discovery_source="BSE India",
            is_wrapper=True,
            is_substantive=False
        )
        database.save_source_documents(sym, [doc_screener_transcript, doc_bse_notification])

        resp = main.get_stock_source_filings(sym)
        ccs = resp["documents"]["concalls"]
        self.assertEqual(len(ccs), 1)
        # Substantive Screener transcript URL is selected
        self.assertEqual(ccs[0]["url"], "https://www.icici.bank.in/content/dam/transcript-for-earnings-call-held-on-july-18-2026.pdf")
        self.assertTrue(ccs[0]["ai_eligible"])
        self.assertIn("BSE India", ccs[0]["discovered_sources"])
        self.assertIn("Screener.in", ccs[0]["discovered_sources"])

    def test_source_strategy_d_bse_only_concall(self):
        """
        D. BSE-ONLY CONCALL
        BSE has a genuine transcript not present in Screener.
        Expected: included. Do not lose it because of Screener-first preference.
        """
        sym = "TESTSYM"
        doc_bse_concall = DocumentItem(
            ticker=sym,
            title="Earnings Call Transcript for Q2 FY27",
            url="https://www.bseindia.com/xml-data/corpfiling/AttachHis/bse_concall_q2fy27.pdf",
            doc_type="concall_transcript",
            period_or_date="24 Oct 2026",
            discovery_source="BSE India"
        )
        database.save_source_documents(sym, [doc_bse_concall])

        resp = main.get_stock_source_filings(sym)
        ccs = resp["documents"]["concalls"]
        self.assertEqual(len(ccs), 1)
        self.assertEqual(ccs[0]["url"], "https://www.bseindia.com/xml-data/corpfiling/AttachHis/bse_concall_q2fy27.pdf")
        self.assertEqual(ccs[0]["discovery_source"], "BSE India")

    def test_source_strategy_e_transcript_plus_presentation(self):
        """
        E. TRANSCRIPT + PRESENTATION
        Same event/date.
        Expected: both retained. Shared event identity allowed. Different document subtype.
        """
        sym = "TESTSYM"
        doc_transcript = DocumentItem(
            ticker=sym,
            title="TESTSYM Jul 2026 Earnings Call Transcript",
            url="https://www.icici.bank.in/transcripts/q1fy27.pdf",
            doc_type="concall_transcript",
            period_or_date="Jul 2026",
            discovery_source="Screener.in"
        )
        doc_presentation = DocumentItem(
            ticker=sym,
            title="TESTSYM Jul 2026 Investor Presentation",
            url="https://www.bseindia.com/xml-data/corpfiling/AttachHis/deck_q1fy27.pdf",
            doc_type="presentation",
            period_or_date="18 Jul 2026",
            discovery_source="BSE India"
        )
        database.save_source_documents(sym, [doc_transcript, doc_presentation])

        resp = main.get_stock_source_filings(sym)
        ccs = resp["documents"]["concalls"]
        ppts = resp["documents"]["presentations"]
        
        self.assertEqual(len(ccs), 1)
        self.assertEqual(len(ppts), 1)
        self.assertNotEqual(ccs[0]["doc_type"], ppts[0]["doc_type"])
        # Both share the same event key for Q1 FY27
        self.assertEqual(ccs[0]["event_key"], "event_TESTSYM_Q1FY27")
        self.assertEqual(ppts[0]["event_key"], "event_TESTSYM_Q1FY27")

    def test_source_strategy_f_duplicate_presentation(self):
        """
        F. DUPLICATE PRESENTATION
        Screener + BSE same presentation.
        Expected: one canonical presentation.
        """
        sym = "TESTSYM"
        doc_bse_ppt = DocumentItem(
            ticker=sym,
            title="Announcement under Regulation 30 (LODR)-Investor Presentation",
            url="https://www.bseindia.com/xml-data/corpfiling/AttachHis/881c8fc3-a4c2-40ff-bacf-d68efc0e3d7a.pdf",
            doc_type="presentation",
            period_or_date="18 Jul 2026",
            discovery_source="BSE India"
        )
        doc_screener_ppt = DocumentItem(
            ticker=sym,
            title="TESTSYM Jul 2026 Investor Presentation",
            url="https://www.bseindia.com/stockinfo/AnnPdfOpen.aspx?Pname=881c8fc3-a4c2-40ff-bacf-d68efc0e3d7a.pdf",
            doc_type="presentation",
            period_or_date="Jul 2026",
            discovery_source="Screener.in"
        )
        database.save_source_documents(sym, [doc_bse_ppt, doc_screener_ppt])

        resp = main.get_stock_source_filings(sym)
        ppts = resp["documents"]["presentations"]
        self.assertEqual(len(ppts), 1)
        self.assertIn("BSE India", ppts[0]["discovered_sources"])
        self.assertIn("Screener.in", ppts[0]["discovered_sources"])
        self.assertEqual(ppts[0]["period_or_date"], "18 Jul 2026")

    def test_source_strategy_g_brsr_priority(self):
        """
        G. BRSR PRIORITY
        Annual Report + transcript + presentation + unique 20-F + BRSR.
        Expected: BRSR lower in default AI working-set priority.
        """
        doc_links = DocumentLinks(
            annual_reports=[
                DocumentItem(ticker="TESTSYM", title="Annual Report FY26", url="https://bse.com/ar26.pdf", doc_type="annual_report", period_or_date="18 Jul 2026")
            ],
            regulatory_annual_filings=[
                DocumentItem(ticker="TESTSYM", title="Form 20-F FY26", url="https://bse.com/20f.pdf", doc_type="regulatory_annual_filing", period_or_date="20 Jul 2026")
            ],
            concalls=[
                DocumentItem(ticker="TESTSYM", title="Concall Q1 FY27", url="https://bse.com/cc1.pdf", doc_type="concall_transcript", period_or_date="Q1 FY27")
            ],
            presentations=[
                DocumentItem(ticker="TESTSYM", title="Investor Presentation", url="https://bse.com/ppt1.pdf", doc_type="presentation", period_or_date="Jul 2026")
            ],
            brsr_reports=[
                DocumentItem(ticker="TESTSYM", title="BRSR 2026", url="https://bse.com/brsr26.pdf", doc_type="brsr_esg", period_or_date="18 Jul 2026")
            ]
        )
        ws = doc_intelligence_pipeline.select_default_document_working_set(doc_links)
        types = [d.doc_type for d in ws]
        
        ar_idx = types.index("annual_report")
        reg_idx = types.index("regulatory_annual_filing")
        cc_idx = types.index("concall_transcript")
        ppt_idx = types.index("presentation")
        brsr_idx = types.index("brsr_esg")
        
        self.assertTrue(ar_idx < brsr_idx)
        self.assertTrue(reg_idx < brsr_idx)
        self.assertTrue(cc_idx < brsr_idx)
        self.assertTrue(ppt_idx < brsr_idx)

    def test_source_strategy_h_date_enrichment(self):
        """
        H. DATE ENRICHMENT
        Screener copy only says FY26.
        Equivalent BSE alias has exact publication date.
        Expected: canonical record uses exact date for sorting while preserving provenance.
        """
        sym = "TESTSYM"
        doc_screener = DocumentItem(
            ticker=sym,
            title="TESTSYM Annual Report 2026",
            url="https://www.bseindia.com/xml-data/corpfiling/AttachHis/ar_2026_both.pdf",
            doc_type="annual_report",
            period_or_date="FY2026",
            discovery_source="Screener.in"
        )
        doc_bse = DocumentItem(
            ticker=sym,
            title="Notice Of 32Nd Annual General Meeting And Annual Report 2025-26",
            url="https://www.bseindia.com/xml-data/corpfiling/AttachHis/ar_2026_both.pdf",
            doc_type="annual_report",
            period_or_date="18 Jul 2026",
            discovery_source="BSE India"
        )
        database.save_source_documents(sym, [doc_screener, doc_bse])

        resp = main.get_stock_source_filings(sym)
        canonical_ar = resp["documents"]["annual_reports"][0]
        
        self.assertEqual(canonical_ar["period_or_date"], "18 Jul 2026")
        self.assertEqual(canonical_ar["sort_timestamp"], "2026-07-18")
        self.assertIn("Screener.in", canonical_ar["discovered_sources"])
        self.assertIn("BSE India", canonical_ar["discovered_sources"])

if __name__ == '__main__':
    unittest.main()
