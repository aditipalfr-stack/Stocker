import os
import re
import json
import io
import requests
from typing import List, Tuple, Dict, Any, Optional
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

def download_and_extract_pdf(pdf_url: str) -> List[Tuple[int, str]]:
    """
    Downloads a PDF document from a direct URL and extracts text page-by-page.
    Returns a list of tuples: [(page_number, page_text), ...]
    """
    resp = requests.get(pdf_url, headers=HEADERS, timeout=35)
    if resp.status_code != 200:
        raise ValueError(f"Failed to download PDF from {pdf_url}. Status code: {resp.status_code}")
        
    reader = pypdf.PdfReader(io.BytesIO(resp.content))
    pages: List[Tuple[int, str]] = []
    for idx, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        clean_text = re.sub(r"[ \t]+", " ", text)
        pages.append((idx + 1, clean_text))
        
    return pages

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
    save_output: bool = True
) -> Dict[str, Any]:
    """
    End-to-end generic document intelligence pipeline for ANY company.
    1. Downloads latest PDF and extracts text by page.
    2. Downloads older PDF (if provided) for Plan vs Reality comparison.
    3. Feeds text into LLM service (Gemini / OpenAI).
    4. If no LLM key is configured, honestly returns status without hallucinating.
    5. Saves structured facts to backend/data/doc_intelligence_generated/{SYMBOL}.json.
    """
    clean_sym = symbol.upper().strip()
    print(f"\n[Pipeline] Ingesting documents for {company_name} ({clean_sym})...")
    
    # Step 1: Download & extract latest PDF
    print(f"  • Downloading latest document: {latest_doc_title} ({latest_doc_url})")
    latest_pages = download_and_extract_pdf(latest_doc_url)
    print(f"  • Extracted {len(latest_pages)} pages from latest document.")
    
    # Step 2: Download & extract older PDF (if provided)
    older_pages = None
    if older_doc_url:
        print(f"  • Downloading baseline comparison document: {older_doc_title} ({older_doc_url})")
        older_pages = download_and_extract_pdf(older_doc_url)
        print(f"  • Extracted {len(older_pages)} pages from baseline document.")

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
            "latest_document": {"title": latest_doc_title, "url": latest_doc_url, "pages_extracted": len(latest_pages)},
            "older_document": {"title": older_doc_title, "url": older_doc_url, "pages_extracted": len(older_pages) if older_pages else 0}
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
        latest_pages=latest_pages,
        older_doc_title=older_doc_title,
        older_doc_url=older_doc_url,
        older_pages=older_pages
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
