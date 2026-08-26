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

def download_and_extract_pdf(pdf_url: str) -> List[Tuple[int, str]]:
    """
    Downloads a PDF document from a direct URL and extracts text page-by-page.
    Uses local file cache based on URL hash to avoid redundant network downloads.
    """
    url_hash = hashlib.md5(pdf_url.encode()).hexdigest()
    cache_file = PDF_CACHE_DIR / f"{url_hash}.json"
    
    if cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return [(item["page"], item["text"]) for item in data]
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
        
    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(cache_list, f)
    except Exception:
        pass
        
    return pages

def select_relevant_sections(
    all_pages: List[Tuple[int, str]],
    is_full_annual_report: bool = False,
    max_pages_to_select: int = 40
) -> Tuple[List[Tuple[int, str]], Dict[int, List[str]]]:
    """Filters high-signal pages from heavy filings based on fundamental themes."""
    total_pages = len(all_pages)
    
    if not is_full_annual_report and total_pages <= 50:
        return all_pages, {p: ["Full Document"] for p, _ in all_pages}
        
    selected_page_indices: Set[int] = set()
    page_reasons: Dict[int, List[str]] = {}
    
    compiled_patterns = {
        theme: [re.compile(r"\b" + re.escape(kw) + r"\b", re.IGNORECASE) for kw in kws]
        for theme, kws in FUNDAMENTAL_THEMES.items()
    }
    
    for page_num, text in all_pages:
        for theme, patterns in compiled_patterns.items():
            if any(p.search(text) for p in patterns):
                selected_page_indices.add(page_num)
                page_reasons.setdefault(page_num, []).append(theme)
                
    # Add adjacent context pages
    context_pages = set()
    for p in selected_page_indices:
        if p > 1:
            context_pages.add(p - 1)
        if p < total_pages:
            context_pages.add(p + 1)
            
    final_selected_indices = selected_page_indices.union(context_pages)
    
    if len(final_selected_indices) > max_pages_to_select:
        scored_pages = sorted(
            list(selected_page_indices),
            key=lambda p: len(page_reasons.get(p, [])),
            reverse=True
        )
        kept_indices = set(scored_pages[:max_pages_to_select])
        final_selected_indices = kept_indices
        
    sorted_pages = [
        (p, text) for p, text in all_pages if p in final_selected_indices
    ]
    
    return sorted_pages, page_reasons

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
    Compiles multi-document corpus and calls Gemini 2.0.
    """
    clean_sym = symbol.upper().strip()
    print(f"\n==================================================")
    print(f"  RUNNING MULTI-DOCUMENT AI PIPELINE: {company_name} ({clean_sym})")
    print(f"==================================================")
    
    # 1. Select the target multi-document set
    selected_docs: List[DocumentItem] = []
    
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
    latest_pages_raw = download_and_extract_pdf(latest_doc_url)
    latest_sel, _ = select_relevant_sections(latest_pages_raw, is_full_annual_report=(len(latest_pages_raw) > 50))
    all_latest_pages.extend(latest_sel)
    
    # Ingest recent concalls into latest context
    for cc in recent_concalls:
        if cc.url != latest_doc_url:
            print(f"  • Ingesting Concall: {cc.title}")
            try:
                cc_pages = download_and_extract_pdf(cc.url)
                all_latest_pages.extend(cc_pages[:25])
            except Exception as e:
                print(f"    ⚠️ Failed to download concall {cc.url}: {e}")

    # Extract older baseline doc for Promise vs Delivery
    if older_doc_url and older_doc_url != latest_doc_url:
        print(f"  • Ingesting Historical Baseline Document: {older_doc_title}")
        try:
            older_pages_raw = download_and_extract_pdf(older_doc_url)
            older_sel, _ = select_relevant_sections(older_pages_raw, is_full_annual_report=(len(older_pages_raw) > 50))
            all_older_pages.extend(older_sel)
        except Exception as e:
            print(f"    ⚠️ Failed to download older doc {older_doc_url}: {e}")

    # 3. LLM Inference
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
            "stocker_view": {"overall_takeaway": msg, "positive_triggers": [], "main_risks": [], "what_to_watch": []}
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
        older_pages=all_older_pages if all_older_pages else None
    )
    
    if not success or not result:
        raise RuntimeError(f"Multi-document AI extraction failed: {message}")
        
    result.extraction_timestamp = datetime.now(timezone.utc).isoformat()
    output_dict = result.model_dump()
    
    if save_output:
        out_file = GENERATED_DIR / f"{clean_sym}.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(output_dict, f, indent=2)
        print(f"  ✓ Saved multi-document AI extracted intelligence to: {out_file}")
        
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
