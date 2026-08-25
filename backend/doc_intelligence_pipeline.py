import os
import re
import json
import io
import requests
from typing import List, Tuple, Dict, Any, Optional, Set
from pathlib import Path
import pypdf
from datetime import datetime, timezone

from doc_intelligence_models import (
    GenericDocumentIntelligenceResult, GenericPlanVsRealityItem,
    GenericGrowthPipelineItem, GenericDemandAndOrders, GenericCashAndProblems
)
from llm_service import extract_document_intelligence_with_llm, is_llm_available, get_available_llm_provider

GENERATED_DIR = Path(__file__).parent / "data" / "doc_intelligence_generated"
GENERATED_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
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
    "auditor_opinion": [
        "Independent Auditor's Report", "Basis for Opinion",
        "Emphasis of Matter", "Key Audit Matters", "KAM", "Internal Financial Controls"
    ],
    "contingent_and_related_party": [
        "Contingent Liabilities", "Related Party Disclosures",
        "Related Party Transactions", "Disputed Demands", "Commitments"
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
    Extracts text from ALL pages without arbitrary early stopping.
    Returns a list of tuples: [(page_number, page_text), ...]
    """
    resp = requests.get(pdf_url, headers=HEADERS, timeout=45)
    if resp.status_code != 200:
        raise ValueError(f"Failed to download PDF from {pdf_url}. Status code: {resp.status_code}")
        
    reader = pypdf.PdfReader(io.BytesIO(resp.content))
    pages: List[Tuple[int, str]] = []
    for idx, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        clean_text = re.sub(r"[ \t]+", " ", text)
        pages.append((idx + 1, clean_text))
        
    return pages

def select_relevant_sections(
    all_pages: List[Tuple[int, str]],
    is_full_annual_report: bool = False,
    max_pages_to_select: int = 45
) -> Tuple[List[Tuple[int, str]], Dict[int, List[str]]]:
    """
    Intelligently filters high-signal pages from a full annual report:
    1. If short/medium document (e.g. concall transcript <= 55 pages), returns ALL pages.
    2. If heavy full annual report (> 55 pages), indexes all pages by fundamental themes,
       includes adjacent context pages [p-1, p, p+1], and deduplicates overlapping chunks.
    Returns (selected_pages_list, selection_reasons_dict).
    """
    total_pages = len(all_pages)
    
    # For concalls and shorter filings, analyze full document
    if not is_full_annual_report and total_pages <= 55:
        reasons = {p_num: ["Full Concall / Presentation Analysis"] for p_num, _ in all_pages}
        return all_pages, reasons

    # For heavy annual reports: generic fundamental theme scoring
    scored_pages: Dict[int, List[str]] = {}
    for p_num, text in all_pages:
        reasons = []
        for theme_name, keywords in FUNDAMENTAL_THEMES.items():
            for kw in keywords:
                if re.search(r"\b" + re.escape(kw) + r"\b", text, re.IGNORECASE):
                    reasons.append(f"{theme_name}: '{kw}'")
                    break
        if reasons:
            scored_pages[p_num] = reasons

    # Priority selection of top pages across diverse themes
    selected_page_numbers: Set[int] = set()
    
    # Ensure at least one representative section for each fundamental theme
    for theme_name in FUNDAMENTAL_THEMES.keys():
        theme_candidates = [
            p for p, reasons in scored_pages.items()
            if any(r.startswith(theme_name) for r in reasons)
        ]
        for p in theme_candidates[:3]:  # Top 3 pages per theme
            selected_page_numbers.add(p)
            # Add surrounding context
            if p > 1:
                selected_page_numbers.add(p - 1)
            if p < total_pages:
                selected_page_numbers.add(p + 1)

    # Sort and cap to max_pages_to_select
    sorted_p_nums = sorted(list(selected_page_numbers))[:max_pages_to_select]
    
    selected_pages = [(p, all_pages[p - 1][1]) for p in sorted_p_nums]
    selection_reasons = {p: scored_pages.get(p, ["Context page"]) for p in sorted_p_nums}
    
    return selected_pages, selection_reasons

def find_supporting_snippet(pages: List[Tuple[int, str]], target_page: int, keywords: List[str]) -> Tuple[bool, str]:
    """
    Validates whether supporting text exists on the specified page and returns a short excerpt.
    """
    if target_page < 1 or target_page > len(pages):
        return False, "Page number out of range"
        
    page_text = pages[target_page - 1][1]
    matches = [k for k in keywords if re.search(re.escape(k), page_text, re.IGNORECASE)]
    
    if matches:
        m = re.search(re.escape(matches[0]), page_text, re.IGNORECASE)
        if m:
            start = max(0, m.start() - 50)
            end = min(len(page_text), m.end() + 120)
            snippet = "..." + page_text[start:end].replace("\n", " ").strip() + "..."
            return True, snippet
            
    return False, "Keywords not found on specified page"

def run_generic_document_pipeline(
    symbol: str,
    company_name: str,
    latest_doc_url: str,
    latest_doc_title: str,
    older_doc_url: Optional[str] = None,
    older_doc_title: Optional[str] = None,
    is_annual_report: bool = False,
    pre_extracted_latest_pages: Optional[List[Tuple[int, str]]] = None,
    pre_extracted_older_pages: Optional[List[Tuple[int, str]]] = None,
    save_output: bool = True
) -> Dict[str, Any]:
    clean_sym = symbol.upper().strip()
    print(f"\n[Pipeline] Ingesting documents for {company_name} ({clean_sym})...")
    
    # Step 1: Extract or reuse latest PDF pages
    if pre_extracted_latest_pages:
        all_latest_pages = pre_extracted_latest_pages
        print(f"  • Using pre-extracted {len(all_latest_pages)} pages for latest document.")
    else:
        print(f"  • Downloading latest document: {latest_doc_title} ({latest_doc_url})")
        all_latest_pages = download_and_extract_pdf(latest_doc_url)
        print(f"  • Extracted ALL {len(all_latest_pages)} pages from latest document.")
        
    total_latest_pages = len(all_latest_pages)
    
    # Select relevant sections for LLM context
    selected_latest_pages, selection_reasons = select_relevant_sections(
        all_latest_pages,
        is_full_annual_report=(is_annual_report or total_latest_pages > 55)
    )
    print(f"  • Selected {len(selected_latest_pages)} relevant high-signal pages across key themes.")
    
    # Step 2: Download & extract older baseline PDF (if provided)
    selected_older_pages = None
    older_doc_stats = {}
    if older_doc_url:
        print(f"  • Downloading baseline comparison document: {older_doc_title} ({older_doc_url})")
        all_older_pages = download_and_extract_pdf(older_doc_url)
        total_older_pages = len(all_older_pages)
        print(f"  • Extracted ALL {total_older_pages} pages from baseline document.")
        selected_older_pages, _ = select_relevant_sections(
            all_older_pages,
            is_full_annual_report=(total_older_pages > 55)
        )
        older_doc_stats = {
            "title": older_doc_title,
            "url": older_doc_url,
            "total_pages": total_older_pages,
            "pages_analyzed": len(selected_older_pages)
        }

    # Step 3: LLM Inference
    if not is_llm_available():
        msg = (
            "AI Analysis Unavailable: No LLM API key detected in the environment. "
            "To enable live AI document extraction, please set either GEMINI_API_KEY (for Google Gemini) "
            "or OPENAI_API_KEY (for OpenAI) in your environment."
        )
        print(f"  ⚠️ {msg}")
        
        status_result = {
            "symbol": clean_sym,
            "company_name": company_name,
            "status": "ai_unavailable",
            "message": msg,
            "required_env_vars": ["GEMINI_API_KEY", "OPENAI_API_KEY"],
            "latest_document": {
                "title": latest_doc_title,
                "url": latest_doc_url,
                "total_pages": total_latest_pages,
                "pages_selected_for_analysis": len(selected_latest_pages),
                "selected_page_numbers": [p for p, _ in selected_latest_pages],
                "selection_themes": {str(p): reasons for p, reasons in selection_reasons.items() if reasons != ["Context page"][:1]}
            },
            "older_document": older_doc_stats
        }
        
        if save_output:
            out_file = GENERATED_DIR / f"{clean_sym}.json"
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(status_result, f, indent=2)
        return status_result

    # If LLM is available, run extraction
    success, result, message = extract_document_intelligence_with_llm(
        symbol=clean_sym,
        company_name=company_name,
        latest_doc_title=latest_doc_title,
        latest_doc_url=latest_doc_url,
        latest_pages=selected_latest_pages,
        older_doc_title=older_doc_title,
        older_doc_url=older_doc_url,
        older_pages=selected_older_pages
    )
    
    if not success or not result:
        raise RuntimeError(f"Document extraction failed: {message}")
        
    result.extraction_timestamp = datetime.now(timezone.utc).isoformat()
    output_dict = result.model_dump()
    
    if save_output:
        out_file = GENERATED_DIR / f"{clean_sym}.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(output_dict, f, indent=2)
        print(f"  ✓ Saved AI extracted intelligence to: {out_file}")
        
    return output_dict
