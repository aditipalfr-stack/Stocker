import os
import re
import json
import io
import hashlib
import requests
from typing import List, Tuple, Dict, Any, Optional, Set
from pathlib import Path
import pypdf
from datetime import datetime, timezone

from doc_intelligence_models import (
    BusinessOutlookResult, WhatChangedItem, GrowthDriverItem,
    PromiseVsDeliveryItem, DemandMomentum, RisksAndCash, StockerView
)
from models import DocumentLinks, DocumentItem
from llm_service import extract_document_intelligence_with_llm, is_llm_available, get_available_llm_provider

GENERATED_DIR = Path(__file__).parent / "data" / "doc_intelligence_generated"
GENERATED_DIR.mkdir(parents=True, exist_ok=True)

PDF_CACHE_DIR = Path(__file__).parent / "data" / "pdf_cache"
PDF_CACHE_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.bseindia.com/"
}

# Generic fundamental themes and keywords (strictly company-agnostic)
FUNDAMENTAL_THEMES: Dict[str, List[str]] = {
    "mda_and_strategy": [
        "Management Discussion and Analysis", "Operating Performance",
        "Strategic Priorities", "Strategic Outlook", "Future Outlook", "Chairman's Statement"
    ],
    "capex_and_cwip": [
        "Capital Work-in-Progress", "Capital Work in Progress", "CWIP",
        "Property, Plant and Equipment", "Gross Block", "Capital Expenditure", "Commissioning", "Capacity Expansion"
    ],
    "demand_and_orders": [
        "Order Book", "Order Inflow", "Contract Value", "Customer Base",
        "Subscribers", "Volume Growth", "Market Share", "Pricing Realization"
    ],
    "cash_and_liquidity": [
        "Cash Flow from Operating Activities", "Statement of Cash Flows",
        "Operating Cash Flow", "Free Cash Flow", "Capital Allocation"
    ],
    "working_capital_audit": [
        "Inventories", "Trade Receivables", "Days Sales Outstanding",
        "DSO", "Trade Payables", "Working Capital Changes"
    ],
    "debt_and_borrowings": [
        "Borrowings", "Net Debt", "Debt to Equity", "Credit Rating",
        "Finance Costs", "Maturity Profile"
    ],
    "segment_performance": [
        "Segment Reporting", "Segment Revenue", "Segment Results", "Segment Assets"
    ],
    "risks_and_bottlenecks": [
        "Risk Management", "Principal Risks", "Material Uncertainties", "Supply Chain Disruptions"
    ]
}

import database
from scraper import fetch_stock_from_screener

def format_audited_financials_for_prompt(symbol: str) -> str:
    """Formats 10-year P&L, Balance Sheet, Cash Flow, and Quarters into a clean prompt context table."""
    clean_sym = symbol.upper().strip()
    data = database.get_stock_cache(clean_sym)
    if not data:
        try:
            data = fetch_stock_from_screener(clean_sym, force_refresh=False)
        except Exception:
            data = None
            
    if not data:
        return "Audited financial statements not available in database."
        
    pl = data.get("profit_and_loss", {})
    bs = data.get("balance_sheet", {})
    cf = data.get("cash_flow", {})
    quarters = data.get("quarters", {})
    
    lines = [f"=== AUDITED 10-YEAR FINANCIAL STATEMENTS ({clean_sym}) ==="]
    
    # 1. Annual P&L Summary
    pl_years = pl.get("years", [])
    if pl_years:
        sales = pl.get("rows", {}).get("Sales", [])
        op = pl.get("rows", {}).get("Operating Profit", [])
        opm = pl.get("rows", {}).get("OPM %", [])
        pat = pl.get("rows", {}).get("Net Profit", [])
        
        lines.append("\n[Annual Performance (₹ in Crores)]")
        header = f"{'Metric':<18} | " + " | ".join(f"{y:>8}" for y in pl_years[-6:])
        lines.append(header)
        lines.append("-" * len(header))
        if sales: lines.append(f"{'Sales':<18} | " + " | ".join(f"{str(v):>8}" for v in sales[-6:]))
        if op: lines.append(f"{'EBITDA':<18} | " + " | ".join(f"{str(v):>8}" for v in op[-6:]))
        if opm: lines.append(f"{'OPM %':<18} | " + " | ".join(f"{str(v):>8}" for v in opm[-6:]))
        if pat: lines.append(f"{'Net Profit':<18} | " + " | ".join(f"{str(v):>8}" for v in pat[-6:]))
        
    # 2. Cash Flow Summary
    cf_years = cf.get("years", [])
    if cf_years:
        cfo = cf.get("rows", {}).get("Cash from Operating Activity", []) or cf.get("rows", {}).get("Operating Cash Flow", [])
        if cfo:
            lines.append("\n[Operating Cash Flow (CFO)]")
            lines.append(f"{'CFO (₹ Cr)':<18} | " + " | ".join(f"{str(v):>8}" for v in cfo[-6:]))

    # 3. Balance Sheet Capex & Debt
    bs_years = bs.get("years", [])
    if bs_years:
        borrowings = bs.get("rows", {}).get("Borrowings", [])
        cwip = bs.get("rows", {}).get("CWIP", [])
        fixed_assets = bs.get("rows", {}).get("Fixed Assets", [])
        lines.append("\n[Balance Sheet & Capex]")
        if borrowings: lines.append(f"{'Borrowings':<18} | " + " | ".join(f"{str(v):>8}" for v in borrowings[-6:]))
        if fixed_assets: lines.append(f"{'Fixed Assets':<18} | " + " | ".join(f"{str(v):>8}" for v in fixed_assets[-6:]))
        if cwip: lines.append(f"{'CWIP (Work-in-Prog)':<18} | " + " | ".join(f"{str(v):>8}" for v in cwip[-6:]))

    # 4. Recent Quarters
    q_periods = quarters.get("quarters", [])
    if q_periods:
        q_sales = quarters.get("rows", {}).get("Sales", [])
        q_opm = quarters.get("rows", {}).get("OPM %", [])
        q_pat = quarters.get("rows", {}).get("Net Profit", [])
        lines.append("\n[Recent 6 Quarters Trend]")
        lines.append(f"{'Quarter':<18} | " + " | ".join(f"{q:>8}" for q in q_periods[-6:]))
        if q_sales: lines.append(f"{'Qtr Sales':<18} | " + " | ".join(f"{str(v):>8}" for v in q_sales[-6:]))
        if q_opm: lines.append(f"{'Qtr OPM %':<18} | " + " | ".join(f"{str(v):>8}" for v in q_opm[-6:]))
        if q_pat: lines.append(f"{'Qtr PAT':<18} | " + " | ".join(f"{str(v):>8}" for v in q_pat[-6:]))
        
    return "\n".join(lines)

def download_and_extract_pdf(pdf_url: str, symbol: str = "") -> List[Tuple[int, str]]:
    """
    Downloads a PDF document from a direct URL and extracts text page-by-page.
    Uses SQLite database page cache to avoid redundant downloads.
    """
    cached_pages = database.get_cached_document_pages(pdf_url)
    if cached_pages:
        return cached_pages
        
    url_hash = hashlib.md5(pdf_url.encode()).hexdigest()
    cache_file = PDF_CACHE_DIR / f"{url_hash}.json"
    
    if cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                pages = [(item["page"], item["text"]) for item in data]
                if symbol:
                    database.save_cached_document_pages(symbol, pdf_url, pages)
                return pages
        except Exception:
            pass
            
    resp = requests.get(pdf_url, headers=HEADERS, timeout=45)
    if resp.status_code != 200:
        raise ValueError(f"Failed to download PDF from {pdf_url}. Status code: {resp.status_code}")
        
    reader = pypdf.PdfReader(io.BytesIO(resp.content))
    pages: List[Tuple[int, str]] = []
    cache_list = []
    
    for idx, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        clean_text = re.sub(r"[ \t]+", " ", text)
        page_num = idx + 1
        pages.append((page_num, clean_text))
        cache_list.append({"page": page_num, "text": clean_text})
        
    if symbol:
        database.save_cached_document_pages(symbol, pdf_url, pages)
        
    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(cache_list, f)
    except Exception:
        pass
        
    return pages

def run_multi_document_ai_pipeline(
    symbol: str,
    company_name: str,
    documents: DocumentLinks,
    save_output: bool = True
) -> Dict[str, Any]:
    """
    Downloads and extracts from the verified multi-document set:
    - Latest Annual Report (and prior year for Promise vs Delivery)
    - Last 2-3 Concall Transcripts
    - Latest Investor Presentation
    - Material Announcements
    Triangulates with 10-year reported financial statements and calls Gemini.
    """
    clean_sym = symbol.upper().strip()
    print(f"\n==================================================")
    print(f"  RUNNING MULTI-DOCUMENT AI PIPELINE: {company_name} ({clean_sym})")
    print(f"==================================================")
    
    # 1. Select the target multi-document set
    latest_ar = documents.annual_reports[0] if documents.annual_reports else None
    older_ar = documents.annual_reports[1] if len(documents.annual_reports) > 1 else None
    
    recent_concalls = documents.concalls[:2]
    recent_ppt = documents.presentations[:1]
    recent_ann = documents.material_announcements[:2]
    
    candidate_docs = []
    if latest_ar: candidate_docs.append(latest_ar)
    if older_ar: candidate_docs.append(older_ar)
    candidate_docs.extend(recent_concalls)
    candidate_docs.extend(recent_ppt)
    candidate_docs.extend(recent_ann)
    
    if not candidate_docs:
        raise ValueError(f"No valid source documents found for {clean_sym}")

    # 2. Extract and compile multi-document text corpus
    latest_doc_title = latest_ar.title if latest_ar else (candidate_docs[0].title)
    latest_doc_url = latest_ar.url if latest_ar else (candidate_docs[0].url)
    older_doc_title = older_ar.title if older_ar else (recent_concalls[-1].title if len(recent_concalls) > 1 else None)
    older_doc_url = older_ar.url if older_ar else (recent_concalls[-1].url if len(recent_concalls) > 1 else None)

    all_latest_pages: List[Tuple[int, str]] = []
    all_older_pages: List[Tuple[int, str]] = []
    
    # Extract latest doc
    print(f"  • Ingesting Latest Document: {latest_doc_title}")
    latest_pages_raw = download_and_extract_pdf(latest_doc_url, symbol=clean_sym)
    latest_sel, _ = select_relevant_sections(
        latest_pages_raw, 
        is_full_annual_report=(len(latest_pages_raw) > 40),
        max_pages_to_select=25
    )
    all_latest_pages.extend(latest_sel)
    
    # Ingest recent concalls into latest context
    for cc in recent_concalls:
        if cc.url != latest_doc_url:
            print(f"  • Ingesting Concall: {cc.title}")
            try:
                cc_pages = download_and_extract_pdf(cc.url, symbol=clean_sym)
                cc_sel, _ = select_relevant_sections(
                    cc_pages,
                    is_full_annual_report=False,
                    max_pages_to_select=15
                )
                all_latest_pages.extend(cc_sel)
            except Exception as e:
                print(f"    ⚠️ Failed to download concall {cc.url}: {e}")

    # Extract older baseline doc for Promise vs Delivery
    if older_doc_url and older_doc_url != latest_doc_url:
        print(f"  • Ingesting Historical Baseline Document: {older_doc_title}")
        try:
            older_pages_raw = download_and_extract_pdf(older_doc_url, symbol=clean_sym)
            older_sel, _ = select_relevant_sections(
                older_pages_raw, 
                is_full_annual_report=(len(older_pages_raw) > 40),
                max_pages_to_select=15
            )
            all_older_pages.extend(older_sel)
        except Exception as e:
            print(f"    ⚠️ Failed to download older doc {older_doc_url}: {e}")

    # 3. Compile Audited Financials Summary
    financial_statements_text = format_audited_financials_for_prompt(clean_sym)
    
    candidate_meta = [
        {"title": d.title, "url": d.url, "type": d.doc_type, "period": d.period_or_date}
        for d in candidate_docs
    ]

    # 4. LLM Inference
    if not is_llm_available():
        msg = "AI Analysis Unavailable: Configure GEMINI_API_KEY in .env file."
        status_res = {
            "symbol": clean_sym,
            "company_name": company_name,
            "status": "ai_unavailable",
            "message": msg,
            "latest_document_period": "Not Analyzed",
            "older_document_period": "None",
            "source_documents": [d.model_dump() for d in candidate_docs],
            "what_changed_recently": [],
            "growth_drivers": [],
            "promise_vs_delivery": [],
            "demand_momentum": {"summary": "", "company_specific_metrics": []},
            "risks_and_cash": {"operational_bottlenecks": []},
            "stocker_view": {"overall_takeaway": msg, "positive_triggers": [], "main_risks": [], "what_to_watch": []},
            "document_summaries": []
        }
        return status_res

    success, result, message = extract_document_intelligence_with_llm(
        symbol=clean_sym,
        company_name=company_name,
        latest_doc_title=latest_doc_title,
        latest_doc_url=latest_doc_url,
        latest_pages=all_latest_pages,
        older_doc_title=older_doc_title,
        older_doc_url=older_doc_url,
        older_pages=all_older_pages if all_older_pages else None,
        financial_statements_summary=financial_statements_text,
        candidate_documents_meta=candidate_meta
    )
    
    if not success or not result:
        raise RuntimeError(f"Multi-document AI extraction failed: {message}")
        
    result.extraction_timestamp = datetime.now(timezone.utc).isoformat()
    output_dict = result.model_dump()
    
    # Save to SQLite Database
    if save_output:
        database.save_ai_analysis(
            symbol=clean_sym,
            company_name=company_name,
            intelligence_data=output_dict,
            ai_provider=output_dict.get("ai_provider_used", "GEMINI"),
            model_version=output_dict.get("model_version", "gemini-3.6-flash"),
            source_docs_count=len(candidate_docs)
        )
        
        # Save per-document summaries to SQLite
        for doc_sum in output_dict.get("document_summaries", []):
            if doc_sum.get("doc_url"):
                database.save_document_summary(
                    symbol=clean_sym,
                    doc_url=doc_sum["doc_url"],
                    doc_title=doc_sum.get("doc_title", "Corporate Filing"),
                    summary_data=doc_sum
                )
                
        # Also save legacy JSON file for backward-compatibility
        out_file = GENERATED_DIR / f"{clean_sym}.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(output_dict, f, indent=2)
        print(f"  ✓ Saved multi-document AI extracted intelligence to SQLite & {out_file}")
        
    return output_dict

def run_generic_document_pipeline(
    symbol: str,
    company_name: str,
    latest_doc_url: str,
    latest_doc_title: str,
    older_doc_url: Optional[str] = None,
    older_doc_title: Optional[str] = None,
    is_annual_report: bool = False,
    save_output: bool = True
) -> Dict[str, Any]:
    """Compatibility wrapper that runs the single/multi document pipeline."""
    docs = DocumentLinks(
        annual_reports=[DocumentItem(title=latest_doc_title, url=latest_doc_url, doc_type="annual_report" if is_annual_report else "concall_transcript")]
    )
    if older_doc_url:
        docs.annual_reports.append(DocumentItem(title=older_doc_title or "Baseline Doc", url=older_doc_url, doc_type="annual_report"))
        
    return run_multi_document_ai_pipeline(symbol, company_name, docs, save_output=save_output)
