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
                conn.execute("DELETE FROM source_documents WHERE symbol LIKE 'TEST%';")
                conn.execute("DELETE FROM ai_document_summaries WHERE symbol LIKE 'TEST%';")
                conn.execute("DELETE FROM ai_analysis_cache WHERE symbol LIKE 'TEST%';")
                conn.execute("DELETE FROM document_pages_cache WHERE symbol LIKE 'TEST%';")
        finally:
            conn.close()

    def tearDown(self):
        conn = database.get_db_connection()
        try:
            with conn:
                conn.execute("DELETE FROM source_documents WHERE symbol LIKE 'TEST%';")
                conn.execute("DELETE FROM ai_document_summaries WHERE symbol LIKE 'TEST%';")
                conn.execute("DELETE FROM ai_analysis_cache WHERE symbol LIKE 'TEST%';")
                conn.execute("DELETE FROM document_pages_cache WHERE symbol LIKE 'TEST%';")
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
                DocumentItem(ticker="TESTSYM", title="Investor Presentation Q1 FY27", url="https://bse.com/ppt1.pdf", doc_type="presentation", period_or_date="Q1 FY27")
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
                DocumentItem(ticker="TESTSYM", title="Investor Presentation Q1 FY27", url="https://bse.com/ppt1.pdf", doc_type="presentation", period_or_date="Q1 FY27")
            ],
            brsr_reports=[
                DocumentItem(ticker="TESTSYM", title="BRSR 2026", url="https://bse.com/brsr26.pdf", doc_type="brsr_esg", period_or_date="18 Jul 2026")
            ]
        )
        ws = doc_intelligence_pipeline.select_default_document_working_set(doc_links)
        types = [d.doc_type for d in ws]

        self.assertIn("annual_report", types)
        self.assertIn("regulatory_annual_filing", types)
        self.assertIn("concall_transcript", types)
        self.assertIn("presentation", types)
        # BRSR is 0 by default in working set
        self.assertNotIn("brsr_esg", types)
        self.assertFalse(doc_links.brsr_reports[0].selected_for_ai)

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

    # =========================================================================
    # 20 DETERMINISTIC REGRESSION TESTS FOR PARTS A - E
    # =========================================================================

    def test_1_unknown_fy_annual_reports_do_not_merge(self):
        """1. Unknown FY annual reports with different URLs do NOT merge."""
        sym = "TESTSYM_A1"
        docs = [
            DocumentItem(ticker=sym, title="Annual Report A", url="https://bse.com/ar_unk1.pdf", doc_type="annual_report", period_or_date=None),
            DocumentItem(ticker=sym, title="Annual Report B", url="https://bse.com/ar_unk2.pdf", doc_type="annual_report", period_or_date=None),
            DocumentItem(ticker=sym, title="Annual Report C", url="https://bse.com/ar_unk3.pdf", doc_type="annual_report", period_or_date=None),
        ]
        database.save_source_documents(sym, docs)
        resp = main.get_stock_source_filings(sym)
        self.assertEqual(len(resp["documents"]["annual_reports"]), 3)

    def test_2_unknown_event_concalls_do_not_merge(self):
        """2. Unknown event concalls with different URLs do NOT merge."""
        sym = "TESTSYM_A2"
        docs = [
            DocumentItem(ticker=sym, title="Concall Transcript A", url="https://bse.com/cc_unk1.pdf", doc_type="concall_transcript", period_or_date=None),
            DocumentItem(ticker=sym, title="Concall Transcript B", url="https://bse.com/cc_unk2.pdf", doc_type="concall_transcript", period_or_date=None),
        ]
        database.save_source_documents(sym, docs)
        resp = main.get_stock_source_filings(sym)
        self.assertEqual(len(resp["documents"]["concalls"]), 2)

    def test_3_media_call_and_analyst_call_same_quarter_remain_separate(self):
        """3. Media call + analyst call same quarter remain separate."""
        sym = "TESTSYM_A3"
        docs = [
            DocumentItem(ticker=sym, title="Transcripts of Media Call Q1 FY27", url="https://bse.com/media_q1.pdf", doc_type="concall_transcript", period_or_date="Q1 FY27"),
            DocumentItem(ticker=sym, title="Earnings Call Transcript with Analysts Q1 FY27", url="https://bse.com/analyst_q1.pdf", doc_type="concall_transcript", period_or_date="Q1 FY27"),
        ]
        database.save_source_documents(sym, docs)
        resp = main.get_stock_source_filings(sym)
        ccs = resp["documents"]["concalls"]
        self.assertEqual(len(ccs), 2)
        subtypes = {c["doc_subtype"] for c in ccs}
        self.assertIn("media_call_transcript", subtypes)
        self.assertIn("analyst_investor_transcript", subtypes)

    def test_4_same_analyst_transcript_from_screener_and_bse_merges(self):
        """4. Same analyst transcript from Screener+BSE merges into 1 canonical document."""
        sym = "TESTSYM_A4"
        docs = [
            DocumentItem(ticker=sym, title="TESTSYM Jul 2026 Earnings Call Transcript", url="https://bse.com/substantive_transcript.pdf", doc_type="concall_transcript", period_or_date="Jul 2026", discovery_source="Screener.in"),
            DocumentItem(ticker=sym, title="Transcripts of Earnings Call with Analysts and Investors Q1 FY27", url="https://bse.com/substantive_transcript.pdf", doc_type="concall_transcript", period_or_date="23 Jul 2026", discovery_source="BSE India"),
        ]
        database.save_source_documents(sym, docs)
        resp = main.get_stock_source_filings(sym)
        self.assertEqual(len(resp["documents"]["concalls"]), 1)
        self.assertEqual(len(resp["documents"]["concalls"][0]["discovered_sources"]), 2)

    def test_5_wrapper_notification_excluded_from_ai(self):
        """5. Wrapper notification is marked is_wrapper=True and ai_eligible=False."""
        sym = "TESTSYM_A5"
        doc = DocumentItem(ticker=sym, title="Audio Recording of Earnings Call for Q1 FY27", url="https://bse.com/audio_rec.pdf", doc_type="concall_transcript", period_or_date="Q1 FY27")
        database.save_source_documents(sym, [doc])
        resp = main.get_stock_source_filings(sym)
        c = resp["documents"]["concalls"][0]
        self.assertTrue(c["is_wrapper"])
        self.assertFalse(c["ai_eligible"])

    def test_6_underlying_substantive_transcript_selected(self):
        """6. Substantive transcript is selected for AI."""
        sym = "TESTSYM_A6"
        doc = DocumentItem(ticker=sym, title="TESTSYM Q1 FY27 Analyst Transcript", url="https://bse.com/real_transcript.pdf", doc_type="concall_transcript", period_or_date="Q1 FY27")
        database.save_source_documents(sym, [doc])
        resp = main.get_stock_source_filings(sym)
        c = resp["documents"]["concalls"][0]
        self.assertTrue(c["selected_for_ai"])
        self.assertTrue(c["is_substantive"])

    def test_7_latest_2_annual_reports_selected(self):
        """7. Latest 2 annual reports selected in AI working set."""
        sym = "TESTSYM_A7"
        docs = [
            DocumentItem(ticker=sym, title="Annual Report 2026", url="https://bse.com/ar26.pdf", doc_type="annual_report", period_or_date="FY2026"),
            DocumentItem(ticker=sym, title="Annual Report 2025", url="https://bse.com/ar25.pdf", doc_type="annual_report", period_or_date="FY2025"),
        ]
        database.save_source_documents(sym, docs)
        resp = main.get_stock_source_filings(sym)
        ars = resp["documents"]["annual_reports"]
        self.assertTrue(ars[0]["selected_for_ai"])
        self.assertTrue(ars[1]["selected_for_ai"])

    def test_8_third_older_annual_report_not_selected(self):
        """8. Third older annual report not selected in default AI working set."""
        sym = "TESTSYM_A8"
        docs = [
            DocumentItem(ticker=sym, title="Annual Report 2026", url="https://bse.com/ar26.pdf", doc_type="annual_report", period_or_date="FY2026"),
            DocumentItem(ticker=sym, title="Annual Report 2025", url="https://bse.com/ar25.pdf", doc_type="annual_report", period_or_date="FY2025"),
            DocumentItem(ticker=sym, title="Annual Report 2024", url="https://bse.com/ar24.pdf", doc_type="annual_report", period_or_date="FY2024"),
        ]
        database.save_source_documents(sym, docs)
        resp = main.get_stock_source_filings(sym)
        ars = resp["documents"]["annual_reports"]
        self.assertTrue(ars[0]["selected_for_ai"])
        self.assertTrue(ars[1]["selected_for_ai"])
        self.assertFalse(ars[2]["selected_for_ai"])
        self.assertIn("Older Annual Report", ars[2]["selection_reason"])

    def test_9_latest_4_quarter_transcripts_selected(self):
        """9. Latest 4 quarter transcripts selected in AI working set."""
        sym = "TESTSYM_A9"
        docs = [
            DocumentItem(ticker=sym, title=f"Concall Q{q} FY26", url=f"https://bse.com/cc_q{q}.pdf", doc_type="concall_transcript", period_or_date=f"Q{q} FY26")
            for q in [4, 3, 2, 1]
        ]
        database.save_source_documents(sym, docs)
        resp = main.get_stock_source_filings(sym)
        ccs = resp["documents"]["concalls"]
        self.assertEqual(len(ccs), 4)
        for c in ccs:
            self.assertTrue(c["selected_for_ai"])

    def test_10_fifth_oldest_transcript_not_selected(self):
        """10. Fifth-oldest transcript not selected in default AI working set."""
        sym = "TESTSYM_A10"
        docs = [
            DocumentItem(ticker=sym, title=f"Concall Transcript #{i}", url=f"https://bse.com/cc_{i}.pdf", doc_type="concall_transcript", period_or_date=f"Q{((5-i)%4)+1} FY{26 if i < 4 else 25}")
            for i in range(1, 6)
        ]
        database.save_source_documents(sym, docs)
        resp = main.get_stock_source_filings(sym)
        ccs = resp["documents"]["concalls"]
        self.assertEqual(len(ccs), 5)
        self.assertTrue(ccs[0]["selected_for_ai"])
        self.assertTrue(ccs[1]["selected_for_ai"])
        self.assertTrue(ccs[2]["selected_for_ai"])
        self.assertTrue(ccs[3]["selected_for_ai"])
        self.assertFalse(ccs[4]["selected_for_ai"])
        self.assertIn("Older than default 4-quarter", ccs[4]["selection_reason"])

    def test_11_latest_4_presentations_selected(self):
        """11. Latest 4 presentations selected in default AI working set."""
        sym = "TESTSYM_A11"
        docs = [
            DocumentItem(ticker=sym, title=f"Presentation Deck #{i}", url=f"https://bse.com/ppt_{i}.pdf", doc_type="presentation", period_or_date=f"Q{((5-i)%4)+1} FY26")
            for i in range(1, 6)
        ]
        database.save_source_documents(sym, docs)
        resp = main.get_stock_source_filings(sym)
        ppts = resp["documents"]["presentations"]
        self.assertTrue(ppts[0]["selected_for_ai"])
        self.assertTrue(ppts[1]["selected_for_ai"])
        self.assertTrue(ppts[2]["selected_for_ai"])
        self.assertTrue(ppts[3]["selected_for_ai"])
        self.assertFalse(ppts[4]["selected_for_ai"])

    def test_12_brsr_excluded_by_default(self):
        """12. BRSR is excluded by default from AI working set."""
        sym = "TESTSYM_A12"
        doc = DocumentItem(ticker=sym, title="Business Responsibility and Sustainability Reporting (BRSR)", url="https://bse.com/brsr.pdf", doc_type="brsr_esg", period_or_date="FY2026")
        database.save_source_documents(sym, [doc])
        resp = main.get_stock_source_filings(sym)
        b = resp["documents"]["brsr_reports"][0]
        self.assertFalse(b["selected_for_ai"])
        self.assertIn("BRSR excluded", b["selection_reason"])

    def test_13_unique_latest_20f_selected(self):
        """13. Unique latest 20-F selected in AI working set."""
        sym = "TESTSYM_A13"
        doc = DocumentItem(ticker=sym, title="Filing Of Form 20-F For The Year Ended March 31, 2026", url="https://bse.com/20f_unique.pdf", doc_type="regulatory_annual_filing", period_or_date="20 Jul 2026")
        database.save_source_documents(sym, [doc])
        resp = main.get_stock_source_filings(sym)
        r = resp["documents"]["regulatory_annual_filings"][0]
        self.assertTrue(r["selected_for_ai"])
        self.assertEqual(r["selection_reason"], "Latest Form 20-F regulatory filing")

    def test_14_material_announcement_max_limit_respected(self):
        """14. Material announcement max limit (top 5) respected."""
        sym = "TESTSYM_A14"
        docs = [
            DocumentItem(ticker=sym, title=f"Announcement: Acquisition of Subsidiary #{i}", url=f"https://bse.com/mna_{i}.pdf", doc_type="announcement", period_or_date=f"{10+i} Aug 2026")
            for i in range(1, 8)
        ]
        database.save_source_documents(sym, docs)
        resp = main.get_stock_source_filings(sym)
        anns = resp["documents"]["material_announcements"]
        selected = [a for a in anns if a["selected_for_ai"]]
        self.assertLessEqual(len(selected), 5)

    def test_15_routine_announcements_excluded(self):
        """15. Routine announcements (trading window, duplicate shares) excluded from AI."""
        sym = "TESTSYM_A15"
        docs = [
            DocumentItem(ticker=sym, title="Intimation of Closure of Trading Window", url="https://bse.com/tw.pdf", doc_type="announcement", period_or_date="30 Jun 2026"),
            DocumentItem(ticker=sym, title="Loss of Share Certificates and Issue of Duplicate", url="https://bse.com/dup.pdf", doc_type="announcement", period_or_date="15 Jul 2026"),
            DocumentItem(ticker=sym, title="Newspaper Publication of Financial Results", url="https://bse.com/np.pdf", doc_type="announcement", period_or_date="20 Jul 2026"),
        ]
        database.save_source_documents(sym, docs)
        resp = main.get_stock_source_filings(sym)
        for a in resp["documents"]["material_announcements"]:
            self.assertFalse(a["selected_for_ai"])
            self.assertIn("Routine", a["selection_reason"])

    def test_16_promise_vs_delivery_current_vs_prior_year_evidence(self):
        """16. Promise vs delivery uses current vs prior-year evidence without auto-fetching FY21-FY23."""
        sym = "TESTSYM_A16"
        doc_links = DocumentLinks(
            annual_reports=[
                DocumentItem(ticker=sym, title="Annual Report 2026", url="https://bse.com/ar26.pdf", doc_type="annual_report", period_or_date="FY2026"),
                DocumentItem(ticker=sym, title="Annual Report 2025", url="https://bse.com/ar25.pdf", doc_type="annual_report", period_or_date="FY2025"),
            ]
        )
        ws = doc_intelligence_pipeline.select_default_document_working_set(doc_links)
        self.assertEqual(len(ws), 2)
        self.assertEqual(ws[0].title, "Annual Report 2026")
        self.assertEqual(ws[1].title, "Annual Report 2025")

    def test_17_incremental_run_reuses_existing_document_summaries(self):
        """17. Incremental run reuses existing document summaries from SQLite without LLM calls."""
        sym = "TESTSYM_A17"
        url = "https://bse.com/cached_transcript.pdf"
        doc = DocumentItem(ticker=sym, title="Concall Transcript Q1 FY26", url=url, doc_type="concall_transcript", period_or_date="Q1 FY26")
        summary_payload = {
            "doc_title": doc.title,
            "doc_url": url,
            "doc_type": "concall_transcript",
            "period_or_date": "Q1 FY26",
            "key_takeaways": ["Net profit up 15%"],
            "management_tone": "Confident"
        }
        sample_pages = [(1, "Official transcript text: Net profit up 15%.")]
        c_hash = database.compute_document_content_hash(sample_pages)
        database.save_cached_document_pages(sym, url, sample_pages)
        database.save_document_summary(
            sym, url, doc.title, summary_payload,
            doc_type="concall_transcript", period_or_date="Q1 FY26", content_hash=c_hash
        )

        # Calling get_or_generate_document_summary should return the cached summary immediately
        summary = doc_intelligence_pipeline.get_or_generate_document_summary(sym, "Test Corp", doc)
        self.assertEqual(summary["key_takeaways"], ["Net profit up 15%"])
        self.assertEqual(summary["management_tone"], "Confident")

    def test_18_new_document_causes_only_new_tier1_summary_generation(self):
        """18. If 1 doc is cached and 1 doc is not, cached doc is reused."""
        sym = "TESTSYM_A18"
        url_cached = "https://bse.com/cached.pdf"
        sample_pages = [(1, "Official text: Cached fact.")]
        c_hash = database.compute_document_content_hash(sample_pages)
        database.save_cached_document_pages(sym, url_cached, sample_pages)
        database.save_document_summary(
            sym, url_cached, "Cached Doc",
            {"key_takeaways": ["Cached fact"], "management_tone": "Neutral"},
            content_hash=c_hash
        )

        doc_cached = DocumentItem(ticker=sym, title="Cached Doc", url=url_cached, doc_type="concall_transcript", period_or_date="Q1 FY26")
        res = doc_intelligence_pipeline.get_or_generate_document_summary(sym, "Test Corp", doc_cached)
        self.assertEqual(res["key_takeaways"], ["Cached fact"])

    def test_19_selected_for_ai_matches_individually_summarized(self):
        """19. selected_for_ai exactly matches documents in select_default_document_working_set."""
        sym = "TESTSYM_A19"
        doc_links = DocumentLinks(
            annual_reports=[DocumentItem(ticker=sym, title="AR 2026", url="http://a/1", doc_type="annual_report", period_or_date="FY2026")],
            concalls=[DocumentItem(ticker=sym, title="CC Q1", url="http://a/2", doc_type="concall_transcript", period_or_date="Q1 FY27")],
            brsr_reports=[DocumentItem(ticker=sym, title="BRSR 2026", url="http://a/3", doc_type="brsr_esg", period_or_date="FY2026")]
        )
        ws = doc_intelligence_pipeline.select_default_document_working_set(doc_links)
        ws_urls = {d.url for d in ws}
        self.assertIn("http://a/1", ws_urls)
        self.assertIn("http://a/2", ws_urls)
        self.assertNotIn("http://a/3", ws_urls)
        self.assertTrue(doc_links.annual_reports[0].selected_for_ai)
        self.assertTrue(doc_links.concalls[0].selected_for_ai)
        self.assertFalse(doc_links.brsr_reports[0].selected_for_ai)

    def test_20_company_synthesis_does_not_duplicate_identical_kpi_findings(self):
        """20. Company synthesis does not duplicate identical verified KPI findings."""
        raw_output = {
            "verified_facts": [
                {"fact": "Loan book grew 19.6% year-on-year", "source": "Concall Transcript"},
                {"fact": "Loan book grew 19.6% year-on-year", "source": "Investor Presentation"}
            ],
            "what_changed_recently": [
                "Net interest margin expanded to 4.36%",
                "Net interest margin expanded to 4.36%"
            ]
        }
        deduped = doc_intelligence_pipeline.deduplicate_synthesized_findings(raw_output)
        self.assertEqual(len(deduped["verified_facts"]), 1)
        self.assertEqual(len(deduped["what_changed_recently"]), 1)

    # =========================================================================
    # ADDITIONAL TESTS FOR SELECT_RELEVANT_SECTIONS, 4 DISTINCT EVENTS, RANKING
    # =========================================================================

    def test_21_select_relevant_sections_short_document(self):
        """Short document (<=50 pages) returns all pages and valid tuple."""
        short_pages = [(i, f"Page text content {i}") for i in range(1, 30)]
        pages, reasons = doc_intelligence_pipeline.select_relevant_sections(short_pages, is_full_annual_report=False)
        self.assertIsInstance(pages, list)
        self.assertIsInstance(reasons, dict)
        self.assertEqual(len(pages), 29)
        self.assertEqual(reasons[1], ["Full Document"])

    def test_22_select_relevant_sections_long_document_with_themes(self):
        """Long document with matched themes returns matched pages + adjacent context."""
        long_pages = [(i, f"Routine page text {i}") for i in range(1, 100)]
        long_pages[24] = (25, "Management Discussion and Analysis. Capital expenditure and margin guidance.")
        pages, reasons = doc_intelligence_pipeline.select_relevant_sections(long_pages, is_full_annual_report=True, max_pages_to_select=10)
        self.assertIsInstance(pages, list)
        self.assertIsInstance(reasons, dict)
        page_nums = [p for p, _ in pages]
        self.assertIn(25, page_nums)
        # Adjacent context pages (24, 26) should be included
        self.assertIn(24, page_nums)
        self.assertIn(26, page_nums)
        self.assertLessEqual(len(pages), 10)

    def test_23_select_relevant_sections_max_pages_cap(self):
        """Max-pages-to-select cap is strictly enforced on dense documents."""
        dense_pages = [
            (i, f"Revenue guidance EBITDA margin Capex growth driver risk factor litigation debt {i}")
            for i in range(1, 120)
        ]
        pages, reasons = doc_intelligence_pipeline.select_relevant_sections(dense_pages, is_full_annual_report=True, max_pages_to_select=15)
        self.assertLessEqual(len(pages), 15)

    def test_24_select_relevant_sections_no_matches_fallback(self):
        """Document with no keyword matches falls back gracefully to initial pages without failing."""
        blank_pages = [(i, f"Lorem ipsum dolor sit amet {i}") for i in range(1, 80)]
        pages, reasons = doc_intelligence_pipeline.select_relevant_sections(blank_pages, is_full_annual_report=True, max_pages_to_select=20)
        self.assertIsInstance(pages, list)
        self.assertIsInstance(reasons, dict)
        self.assertEqual(len(pages), 20)
        self.assertEqual(pages[0][0], 1)

    def test_25_concall_selection_latest_4_distinct_events(self):
        """Two transcripts for same Q1 event + Q2, Q3, Q4, Q5 selects latest 4 DISTINCT events (Q1, Q2, Q3, Q4)."""
        sym = "TESTSYM_CC4"
        docs = [
            DocumentItem(ticker=sym, title="Concall Transcript Q1 FY27 - Version A", url="https://bse.com/cc_q1_a.pdf", doc_type="concall_transcript", period_or_date="Jul 2026"),
            DocumentItem(ticker=sym, title="Concall Transcript Q1 FY27 - Version B", url="https://bse.com/cc_q1_b.pdf", doc_type="concall_transcript", period_or_date="Jul 2026"),
            DocumentItem(ticker=sym, title="Concall Transcript Q4 FY26", url="https://bse.com/cc_q4.pdf", doc_type="concall_transcript", period_or_date="Apr 2026"),
            DocumentItem(ticker=sym, title="Concall Transcript Q3 FY26", url="https://bse.com/cc_q3.pdf", doc_type="concall_transcript", period_or_date="Jan 2026"),
            DocumentItem(ticker=sym, title="Concall Transcript Q2 FY26", url="https://bse.com/cc_q2.pdf", doc_type="concall_transcript", period_or_date="Oct 2025"),
            DocumentItem(ticker=sym, title="Concall Transcript Q1 FY26", url="https://bse.com/cc_q1_old.pdf", doc_type="concall_transcript", period_or_date="Jul 2025"),
        ]
        database.save_source_documents(sym, docs)
        resp = main.get_stock_source_filings(sym)
        ccs = resp["documents"]["concalls"]
        selected = [c for c in ccs if c["selected_for_ai"]]

        # Must select exactly 4 distinct quarters: Q1 FY27 (one version), Q4 FY26, Q3 FY26, Q2 FY26
        self.assertEqual(len(selected), 4)
        selected_periods = [c["period_or_date"] for c in selected]
        self.assertEqual(selected_periods.count("Jul 2026"), 1)
        self.assertIn("Apr 2026", selected_periods)
        self.assertIn("Jan 2026", selected_periods)
        self.assertIn("Oct 2025", selected_periods)
        self.assertNotIn("Jul 2025", selected_periods)

    def test_26_presentation_selection_latest_4_distinct_events(self):
        """Two presentations for same Q1 event + Q2, Q3, Q4, Q5 selects latest 4 DISTINCT events."""
        sym = "TESTSYM_PPT4"
        docs = [
            DocumentItem(ticker=sym, title="Investor Deck Q1 FY27 - Main", url="https://bse.com/ppt_q1_1.pdf", doc_type="presentation", period_or_date="Jul 2026"),
            DocumentItem(ticker=sym, title="Investor Deck Q1 FY27 - Factsheet", url="https://bse.com/ppt_q1_2.pdf", doc_type="presentation", period_or_date="Jul 2026"),
            DocumentItem(ticker=sym, title="Investor Deck Q4 FY26", url="https://bse.com/ppt_q4.pdf", doc_type="presentation", period_or_date="Apr 2026"),
            DocumentItem(ticker=sym, title="Investor Deck Q3 FY26", url="https://bse.com/ppt_q3.pdf", doc_type="presentation", period_or_date="Jan 2026"),
            DocumentItem(ticker=sym, title="Investor Deck Q2 FY26", url="https://bse.com/ppt_q2.pdf", doc_type="presentation", period_or_date="Oct 2025"),
            DocumentItem(ticker=sym, title="Investor Deck Q1 FY26", url="https://bse.com/ppt_q1_old.pdf", doc_type="presentation", period_or_date="Jul 2025"),
        ]
        database.save_source_documents(sym, docs)
        resp = main.get_stock_source_filings(sym)
        ppts = resp["documents"]["presentations"]
        selected = [p for p in ppts if p["selected_for_ai"]]

        self.assertEqual(len(selected), 4)
        selected_periods = [p["period_or_date"] for p in selected]
        self.assertEqual(selected_periods.count("Jul 2026"), 1)
        self.assertIn("Apr 2026", selected_periods)
        self.assertIn("Jan 2026", selected_periods)
        self.assertIn("Oct 2025", selected_periods)
        self.assertNotIn("Jul 2025", selected_periods)

    def test_27_material_announcements_ranked_by_materiality_score(self):
        """Score 30 M&A outranks score 15 litigation even if litigation appears earlier in input list."""
        sym = "TESTSYM_ANN_RANK"
        docs = [
            DocumentItem(ticker=sym, title="Announcement: Material Litigation Update", url="https://bse.com/litigation.pdf", doc_type="announcement", period_or_date="20 Aug 2026"),
            DocumentItem(ticker=sym, title="Announcement: Routine Corporate Notice", url="https://bse.com/routine1.pdf", doc_type="announcement", period_or_date="19 Aug 2026"),
            DocumentItem(ticker=sym, title="Announcement: Major Acquisition and Merger of Subsidiary", url="https://bse.com/mna.pdf", doc_type="announcement", period_or_date="10 Aug 2026"),
            DocumentItem(ticker=sym, title="Announcement: Credit Rating Upgraded", url="https://bse.com/rating.pdf", doc_type="announcement", period_or_date="05 Aug 2026"),
        ]
        database.save_source_documents(sym, docs)
        resp = main.get_stock_source_filings(sym)
        anns = resp["documents"]["material_announcements"]
        selected = [a for a in anns if a["selected_for_ai"]]
        selected.sort(key=lambda x: x["ai_priority"])

        # M&A (Score 30) should be prioritized ahead of Credit Rating (Score 25) and Litigation (Score 15)
        self.assertEqual(selected[0]["url"], "https://bse.com/mna.pdf")
        self.assertEqual(selected[1]["url"], "https://bse.com/rating.pdf")
        self.assertEqual(selected[2]["url"], "https://bse.com/litigation.pdf")
        # Routine notice must not be selected
        routine = next(a for a in anns if a["url"] == "https://bse.com/routine1.pdf")
        self.assertFalse(routine["selected_for_ai"])

    def test_28_real_excerpt_path_unpacking(self):
        """Regression test verifying select_relevant_sections unpacks without error in pipeline flow."""
        sym = "TESTSYM_UNPACK"
        test_pages = [(1, "Management Discussion and Analysis. Capex plan of 500 Cr."), (2, "Financial statements balance sheet.")]
        database.save_cached_document_pages(sym, "https://bse.com/sample_ar.pdf", test_pages)

        pages, reasons = doc_intelligence_pipeline.select_relevant_sections(test_pages, is_full_annual_report=False)
        self.assertIsInstance(pages, list)
        self.assertIsInstance(reasons, dict)
        self.assertEqual(len(pages), 2)

        # Test full get_or_generate_document_summary path with mocked LLM to ensure unpacking works end-to-end
        doc = DocumentItem(ticker=sym, title="Sample AR", url="https://bse.com/sample_ar.pdf", doc_type="annual_report", period_or_date="FY2026")

        with unittest.mock.patch("doc_intelligence_pipeline.download_and_extract_pdf", return_value=test_pages), \
             unittest.mock.patch("doc_intelligence_pipeline.summarize_single_document_with_llm") as mock_llm:
            mock_llm.return_value = {
                "doc_title": "Sample AR",
                "doc_url": doc.url,
                "doc_type": "annual_report",
                "period_or_date": "FY2026",
                "key_takeaways": ["Capex plan of 500 Cr."],
                "management_tone": "Optimistic"
            }
            summary = doc_intelligence_pipeline.get_or_generate_document_summary(sym, "Test Corp", doc)
            self.assertEqual(summary["key_takeaways"], ["Capex plan of 500 Cr."])
            self.assertTrue(mock_llm.called)

    def test_29_presentation_subtyping_agm_and_investor_day_excluded_from_working_set(self):
        """Presentations subtype AGM / Investor Day are excluded from default 4-slot working set."""
        sym = "TESTSYM_PPT_SUB"
        docs = [
            DocumentItem(ticker=sym, title="Earnings Presentation Q1 FY26", url="https://bse.com/ppt_q1.pdf", doc_type="presentation", period_or_date="Q1 FY26"),
            DocumentItem(ticker=sym, title="Investor Presentation Q2 FY26", url="https://bse.com/ppt_q2.pdf", doc_type="presentation", period_or_date="Q2 FY26"),
            DocumentItem(ticker=sym, title="Annual General Meeting (AGM) Presentation 2026", url="https://bse.com/agm.pdf", doc_type="presentation", period_or_date="FY26"),
            DocumentItem(ticker=sym, title="Investor Day & Strategy Presentation", url="https://bse.com/strategy.pdf", doc_type="presentation", period_or_date="2026")
        ]
        database.save_source_documents(sym, docs)
        resp = main.get_stock_source_filings(sym)
        ppts = resp["documents"]["presentations"]

        q1 = next(p for p in ppts if p["url"] == "https://bse.com/ppt_q1.pdf")
        q2 = next(p for p in ppts if p["url"] == "https://bse.com/ppt_q2.pdf")
        agm = next(p for p in ppts if p["url"] == "https://bse.com/agm.pdf")
        strat = next(p for p in ppts if p["url"] == "https://bse.com/strategy.pdf")

        self.assertTrue(q1["selected_for_ai"])
        self.assertTrue(q2["selected_for_ai"])
        self.assertFalse(agm["selected_for_ai"])
        self.assertIn("AGM presentation retained in archive", agm["selection_reason"])
        self.assertFalse(strat["selected_for_ai"])
        self.assertIn("Strategy / Investor Day presentation retained in archive", strat["selection_reason"])

    def test_30_announcement_event_clustering_and_deduplication(self):
        """Announcements cluster by canonical event key and limit to max 5 distinct events in working set."""
        sym = "TESTSYM_ANN_CLUST"
        # 3 filings belonging to the same board meeting event
        docs = [
            DocumentItem(ticker=sym, title="Outcome Of Board Meeting Held On 20 Oct 2025", url="https://bse.com/bm1.pdf", doc_type="announcement", period_or_date="20 Oct 2025"),
            DocumentItem(ticker=sym, title="Board Meeting Outcome - Financial Results", url="https://bse.com/bm2.pdf", doc_type="announcement", period_or_date="20 Oct 2025"),
            DocumentItem(ticker=sym, title="Announcement Under Reg 30: Credit Rating Upgraded", url="https://bse.com/rating.pdf", doc_type="announcement", period_or_date="15 Nov 2025"),
        ]
        database.save_source_documents(sym, docs)
        resp = main.get_stock_source_filings(sym)
        anns = resp["documents"]["material_announcements"]
        selected = [a for a in anns if a["selected_for_ai"]]

        # Only 1 board meeting outcome is selected; credit rating is also selected (2 distinct events)
        self.assertEqual(len(selected), 2)
        bm_selected = [a for a in selected if "Board Meeting" in a["title"]]
        self.assertEqual(len(bm_selected), 1)

    def test_31_alternate_source_recovery_on_failed_convenience_url(self):
        """When downloading convenience URL fails (e.g. 403), pipeline falls back to substantive alternative."""
        sym = "TESTSYM_ALT_REC"
        doc_failed = DocumentItem(
            ticker=sym,
            title="Concall Transcript Q2 FY26",
            url="https://screener.in/fail403.pdf",
            doc_type="concall_transcript",
            period_or_date="Q2 FY26",
            discovery_source="Screener"
        )
        doc_substantive = DocumentItem(
            ticker=sym,
            title="Official Concall Transcript Q2 FY26",
            url="https://bse.com/official_substantive.pdf",
            doc_type="concall_transcript",
            period_or_date="Q2 FY26",
            discovery_source="BSE"
        )
        database.save_source_documents(sym, [doc_failed, doc_substantive])

        def mock_download(url, *args, **kwargs):
            if "fail403" in url:
                return []
            return [(1, "Official substantive conference call text. Revenue grew 16%.")]

        with unittest.mock.patch("doc_intelligence_pipeline.download_and_extract_pdf", side_effect=mock_download), \
             unittest.mock.patch("doc_intelligence_pipeline.summarize_single_document_with_llm") as mock_llm:
            mock_llm.return_value = {
                "doc_title": "Official Concall Transcript Q2 FY26",
                "doc_url": doc_substantive.url,
                "doc_type": "concall_transcript",
                "period_or_date": "Q2 FY26",
                "key_takeaways": ["Revenue grew 16%"],
                "management_tone": "Optimistic"
            }
            summary = doc_intelligence_pipeline.get_or_generate_document_summary(sym, "Test Corp", doc_failed)
            self.assertEqual(summary["key_takeaways"], ["Revenue grew 16%"])
            # Verified that source aliases recorded the failed convenience URL
            self.assertIn(doc_failed.url, summary.get("source_aliases", []))

    def test_32_generic_investor_presentation_without_quarter_classified_other_and_excluded(self):
        """Generic 'Investor Presentation' without quarter or earnings evidence is other_presentation and excluded from working set."""
        sym = "TESTSYM_PPT_GENERIC"
        docs = [
            DocumentItem(ticker=sym, title="Investor Presentation", url="https://bse.com/gen_ppt.pdf", doc_type="presentation", period_or_date=""),
            DocumentItem(ticker=sym, title="Corporate Presentation", url="https://bse.com/corp_ppt.pdf", doc_type="presentation", period_or_date=""),
            DocumentItem(ticker=sym, title="Q1 FY27 Investor Presentation", url="https://bse.com/q1_fy27.pdf", doc_type="presentation", period_or_date="Q1 FY27")
        ]
        database.save_source_documents(sym, docs)
        resp = main.get_stock_source_filings(sym)
        ppts = resp["documents"]["presentations"]

        gen = next(p for p in ppts if p["url"] == "https://bse.com/gen_ppt.pdf")
        corp = next(p for p in ppts if p["url"] == "https://bse.com/corp_ppt.pdf")
        q1 = next(p for p in ppts if p["url"] == "https://bse.com/q1_fy27.pdf")

        self.assertEqual(gen["doc_subtype"], "other_presentation")
        self.assertFalse(gen["selected_for_ai"])
        self.assertIn("General / unresolved presentation retained in archive", gen["selection_reason"])

        self.assertEqual(corp["doc_subtype"], "investor_day_presentation")
        self.assertFalse(corp["selected_for_ai"])

        self.assertEqual(q1["doc_subtype"], "earnings_presentation")
        self.assertTrue(q1["selected_for_ai"])

    def test_33_unresolved_physical_url_cannot_occupy_quarterly_slot(self):
        """Presentations with unresolved / generic events cannot occupy quarterly slots."""
        sym = "TESTSYM_PPT_NO_SLOT"
        docs = [
            DocumentItem(ticker=sym, title="Investor Presentation Presentation", url="https://bse.com/deck_unres.pdf", doc_type="presentation", period_or_date="")
        ]
        database.save_source_documents(sym, docs)
        resp = main.get_stock_source_filings(sym)
        ppts = resp["documents"]["presentations"]
        self.assertEqual(len(ppts), 1)
        self.assertFalse(ppts[0]["selected_for_ai"])

    def test_34_exactly_four_distinct_resolved_earnings_events_selected(self):
        """Working set selects exactly latest 4 distinct resolved quarters when 6 are available."""
        sym = "TESTSYM_PPT_6Q"
        docs = [
            DocumentItem(ticker=sym, title="Earnings Presentation Q1 FY25", url="https://bse.com/ppt_25q1.pdf", doc_type="presentation", period_or_date="Q1 FY25"),
            DocumentItem(ticker=sym, title="Earnings Presentation Q2 FY25", url="https://bse.com/ppt_25q2.pdf", doc_type="presentation", period_or_date="Q2 FY25"),
            DocumentItem(ticker=sym, title="Earnings Presentation Q3 FY25", url="https://bse.com/ppt_25q3.pdf", doc_type="presentation", period_or_date="Q3 FY25"),
            DocumentItem(ticker=sym, title="Earnings Presentation Q4 FY25", url="https://bse.com/ppt_25q4.pdf", doc_type="presentation", period_or_date="Q4 FY25"),
            DocumentItem(ticker=sym, title="Earnings Presentation Q1 FY26", url="https://bse.com/ppt_26q1.pdf", doc_type="presentation", period_or_date="Q1 FY26"),
            DocumentItem(ticker=sym, title="Earnings Presentation Q2 FY26", url="https://bse.com/ppt_26q2.pdf", doc_type="presentation", period_or_date="Q2 FY26"),
        ]
        database.save_source_documents(sym, docs)
        resp = main.get_stock_source_filings(sym)
        ppts = resp["documents"]["presentations"]
        selected = [p for p in ppts if p["selected_for_ai"]]
        self.assertEqual(len(selected), 4)
        selected_quarters = {p["period_or_date"] for p in selected}
        # The 4 newest quarters are selected
        self.assertEqual(selected_quarters, {"Q2 FY26", "Q1 FY26", "Q4 FY25", "Q3 FY25"})

    def test_35_alternate_source_recovery_via_on_demand_adapter_discovery(self):
        """When downloading convenience URL fails and DB has no alternate, on-demand adapter discovers and extracts the official filing."""
        import doc_intelligence_pipeline
        sym = "ICICIBANK"
        doc_failed = DocumentItem(
            ticker=sym,
            title="Concall Transcript Q2 FY26",
            url="https://screener.in/icici_fail403.pdf",
            doc_type="concall_transcript",
            period_or_date="Q2 FY26",
            discovery_source="Screener"
        )
        # Only doc_failed is initially stored in DB
        database.save_source_documents(sym, [doc_failed])

        discovered_alternate = DocumentItem(
            ticker=sym,
            title="Official ICICI Bank Earnings Conference Call Transcript Q2-2026",
            url="https://www.icicibank.com/managed-assets/docs/investor/earnings-call-transcript-q2-2026.pdf",
            doc_type="concall_transcript",
            period_or_date="Q2 FY26",
            discovery_source="Company IR Direct"
        )

        def mock_download(url, *args, **kwargs):
            if "icici_fail403" in url:
                return []
            return [(1, "Official ICICI conference call text. NIM at 4.25%, Advances grew 15%.")]

        with unittest.mock.patch("doc_intelligence_pipeline.download_and_extract_pdf", side_effect=mock_download), \
             unittest.mock.patch("document_sourcing.discover_substantive_alternate_source", return_value=discovered_alternate) as mock_disc, \
             unittest.mock.patch("doc_intelligence_pipeline.summarize_single_document_with_llm") as mock_llm:
            mock_llm.return_value = {
                "doc_title": discovered_alternate.title,
                "doc_url": discovered_alternate.url,
                "doc_type": "concall_transcript",
                "period_or_date": "Q2 FY26",
                "key_takeaways": ["NIM at 4.25%", "Advances grew 15%"]
            }
            summary = doc_intelligence_pipeline.get_or_generate_document_summary(sym, "ICICI Bank Ltd", doc_failed)
            mock_disc.assert_called_once()
            self.assertEqual(summary["key_takeaways"], ["NIM at 4.25%", "Advances grew 15%"])
            self.assertIn(doc_failed.url, summary.get("source_aliases", []))
            self.assertEqual(summary["status"], "success")

    def test_36_alternate_source_recovery_rejects_wrong_event_or_quarter(self):
        """Alternate discovery rejects candidates matching wrong event/quarter."""
        import document_sourcing
        sym = "TESTSYM_WRONG_Q"
        wrong_quarter_doc = DocumentItem(
            ticker=sym,
            title="Earnings Transcript Q4 FY24",  # Wrong quarter for Q2 FY26
            url="https://bse.com/wrong_q4.pdf",
            doc_type="concall_transcript",
            period_or_date="Q4 FY24",
            discovery_source="BSE"
        )

        def mock_bse(s, scrip, docs):
            docs.concalls = [wrong_quarter_doc]

        with unittest.mock.patch("document_sourcing.discover_documents_bse_fallback", side_effect=mock_bse):
            cand = document_sourcing.discover_substantive_alternate_source(
                symbol=sym,
                company_name="Test Corp",
                doc_type="concall_transcript",
                doc_subtype="earnings_transcript",
                period_or_date="Q2 FY26",
                failed_url="https://screener.in/fail.pdf"
            )
            self.assertIsNone(cand)

    def test_37_alternate_source_recovery_rejects_wrapper_notices(self):
        """Alternate discovery rejects 1-page wrapper notices."""
        import document_sourcing
        sym = "TESTSYM_WRAP"
        wrapper_doc = DocumentItem(
            ticker=sym,
            title="Audio Recording Link and Intimation of Concall",
            url="https://bse.com/wrapper.pdf",
            doc_type="concall_transcript",
            period_or_date="Q2 FY26",
            discovery_source="BSE"
        )

        def mock_bse(s, scrip, docs):
            docs.concalls = [wrapper_doc]

        with unittest.mock.patch("document_sourcing.discover_documents_bse_fallback", side_effect=mock_bse):
            cand = document_sourcing.discover_substantive_alternate_source(
                symbol=sym,
                company_name="Test Corp",
                doc_type="concall_transcript",
                doc_subtype="earnings_transcript",
                period_or_date="Q2 FY26",
                failed_url="https://screener.in/fail.pdf"
            )
            self.assertIsNone(cand)

    def test_38_alternate_source_recovery_failure_sets_failed_status(self):
        """When alternate discovery yields nothing, get_or_generate_document_summary returns failed status."""
        import doc_intelligence_pipeline
        sym = "TESTSYM_FAIL_ALL"
        doc_failed = DocumentItem(
            ticker=sym,
            title="Concall Transcript Q2 FY26",
            url="https://screener.in/fail_completely.pdf",
            doc_type="concall_transcript",
            period_or_date="Q2 FY26",
            discovery_source="Screener"
        )

        with unittest.mock.patch("doc_intelligence_pipeline.download_and_extract_pdf", return_value=[]), \
             unittest.mock.patch("document_sourcing.discover_substantive_alternate_source", return_value=None):
            summary = doc_intelligence_pipeline.get_or_generate_document_summary(sym, "Test Corp", doc_failed)
            self.assertEqual(summary["status"], "failed")
            self.assertEqual(summary["key_takeaways"], [])

if __name__ == '__main__':
    unittest.main()
