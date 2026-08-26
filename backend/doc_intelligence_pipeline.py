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
from llm_service import summarize_single_document_with_llm

def _extract_statement_table(statement_data: Any) -> Tuple[List[str], Dict[str, List[Any]]]:
    """Extracts periods/years list and metric->values mapping from either dict or FinancialStatement model."""
    if not statement_data:
        return [], {}
        
    periods: List[str] = []
    rows_dict: Dict[str, List[Any]] = {}
    
    # Check if Pydantic model
    if hasattr(statement_data, "periods") and hasattr(statement_data, "rows"):
        periods = list(statement_data.periods)
        for r in statement_data.rows:
            metric_name = getattr(r, "metric", "")
            vals = getattr(r, "values", {})
            if metric_name and isinstance(vals, dict):
                rows_dict[metric_name] = [vals.get(p) for p in periods]
        return periods, rows_dict
        
    if isinstance(statement_data, dict):
        periods = statement_data.get("periods") or statement_data.get("years") or []
        raw_rows = statement_data.get("rows", {})
        
        if isinstance(raw_rows, dict):
            return periods, raw_rows
        elif isinstance(raw_rows, list):
            for item in raw_rows:
                if isinstance(item, dict):
                    m = item.get("metric")
                    v = item.get("values")
                    if m and isinstance(v, dict):
                        rows_dict[m] = [v.get(p) for p in periods]
                    elif m and isinstance(v, list):
                        rows_dict[m] = v
            return periods, rows_dict
            
    return periods, rows_dict

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
        
    pl_data = data.get("profit_loss") or data.get("profit_and_loss")
    bs_data = data.get("balance_sheet")
    cf_data = data.get("cash_flow")
    q_data = data.get("quarters")
    
    lines = [f"=== AUDITED 10-YEAR FINANCIAL STATEMENTS ({clean_sym}) ==="]
    
    # 1. Annual P&L Summary
    pl_years, pl_rows = _extract_statement_table(pl_data)
    if pl_years:
        sales = pl_rows.get("Sales", []) or pl_rows.get("Revenue", [])
        op = pl_rows.get("Operating Profit", []) or pl_rows.get("EBITDA", [])
        opm = pl_rows.get("OPM %", []) or pl_rows.get("OPM", [])
        pat = pl_rows.get("Net Profit", []) or pl_rows.get("PAT", [])
        eps = pl_rows.get("EPS in Rs", []) or pl_rows.get("EPS", [])
        
        lines.append("\n[Annual Performance (₹ in Crores)]")
        header = f"{'Metric':<18} | " + " | ".join(f"{str(y):>8}" for y in pl_years[-6:])
        lines.append(header)
        lines.append("-" * len(header))
        if sales: lines.append(f"{'Sales':<18} | " + " | ".join(f"{str(v or '-'):>8}" for v in sales[-6:]))
        if op: lines.append(f"{'EBITDA':<18} | " + " | ".join(f"{str(v or '-'):>8}" for v in op[-6:]))
        if opm: lines.append(f"{'OPM %':<18} | " + " | ".join(f"{str(v or '-'):>8}" for v in opm[-6:]))
        if pat: lines.append(f"{'Net Profit':<18} | " + " | ".join(f"{str(v or '-'):>8}" for v in pat[-6:]))
        if eps: lines.append(f"{'EPS (₹)':<18} | " + " | ".join(f"{str(v or '-'):>8}" for v in eps[-6:]))
        
    # 2. Cash Flow Summary
    cf_years, cf_rows = _extract_statement_table(cf_data)
    if cf_years:
        cfo = cf_rows.get("Cash from Operating Activity", []) or cf_rows.get("Operating Cash Flow", []) or cf_rows.get("CFO", [])
        if cfo:
            lines.append("\n[Operating Cash Flow (CFO)]")
            lines.append(f"{'CFO (₹ Cr)':<18} | " + " | ".join(f"{str(v or '-'):>8}" for v in cfo[-6:]))

    # 3. Balance Sheet Capex & Debt
    bs_years, bs_rows = _extract_statement_table(bs_data)
    if bs_years:
        borrowings = bs_rows.get("Borrowings", [])
        cwip = bs_rows.get("CWIP", [])
        fixed_assets = bs_rows.get("Fixed Assets", [])
        lines.append("\n[Balance Sheet & Capex]")
        if borrowings: lines.append(f"{'Borrowings':<18} | " + " | ".join(f"{str(v or '-'):>8}" for v in borrowings[-6:]))
        if fixed_assets: lines.append(f"{'Fixed Assets':<18} | " + " | ".join(f"{str(v or '-'):>8}" for v in fixed_assets[-6:]))
        if cwip: lines.append(f"{'CWIP (Work-in-Prog)':<18} | " + " | ".join(f"{str(v or '-'):>8}" for v in cwip[-6:]))

    # 4. Recent Quarters
    q_periods, q_rows = _extract_statement_table(q_data)
    if q_periods:
        q_sales = q_rows.get("Sales", []) or q_rows.get("Revenue", [])
        q_opm = q_rows.get("OPM %", []) or q_rows.get("OPM", [])
        q_pat = q_rows.get("Net Profit", []) or q_rows.get("PAT", [])
        lines.append("\n[Recent 6 Quarters Trend]")
        lines.append(f"{'Quarter':<18} | " + " | ".join(f"{str(q):>8}" for q in q_periods[-6:]))
        if q_sales: lines.append(f"{'Qtr Sales':<18} | " + " | ".join(f"{str(v or '-'):>8}" for v in q_sales[-6:]))
        if q_opm: lines.append(f"{'Qtr OPM %':<18} | " + " | ".join(f"{str(v or '-'):>8}" for v in q_opm[-6:]))
        if q_pat: lines.append(f"{'Qtr PAT':<18} | " + " | ".join(f"{str(v or '-'):>8}" for v in q_pat[-6:]))
        
    return "\n".join(lines)

def select_default_document_working_set(documents: DocumentLinks) -> List[DocumentItem]:
    """
    Selects the standard visible/default document history:
    - Annual Reports: latest 3 financial years
    - Concall Transcripts: latest 6 quarters
    - Investor Presentations: latest 6 quarters
    - Material Announcements: latest 12 months (up to 8 material items, filtering routine procedural notices)
    """
    selected: List[DocumentItem] = []
    if documents.annual_reports:
        selected.extend(documents.annual_reports[:3])
    if documents.concalls:
        selected.extend(documents.concalls[:6])
    if documents.presentations:
        selected.extend(documents.presentations[:6])
    if documents.material_announcements:
        # Filter for materiality: avoid routine loss of shares or trading window notices
        material_only = []
        for ann in documents.material_announcements:
            t_lower = ann.title.lower()
            if not any(r in t_lower for r in ["loss of share", "duplicate share", "trading window", "newspaper publication"]):
                material_only.append(ann)
        selected.extend(material_only[:8] if material_only else documents.material_announcements[:8])
    return selected

def fetch_historical_evidence_document(
    symbol: str, 
    doc_type: str, 
    period_or_year: str,
    all_available_documents: Optional[DocumentLinks] = None,
    company_name: str = ""
) -> Optional[DocumentItem]:
    """
    Retrieves an older document on demand (e.g. FY21/FY22 Annual Report or older Concall)
    when Promise vs Delivery or long-term capex verification requires historical evidence.
    Executes live waterfall discovery if not already present in memory or SQLite.
    """
    clean_sym = symbol.upper().strip()
    
    # 1. Search in all_available_documents if provided
    if all_available_documents:
        pool = []
        if doc_type in ("annual_report", "annual_reports", "ar"):
            pool = all_available_documents.annual_reports
        elif doc_type in ("concall", "concalls", "transcript", "concall_transcript"):
            pool = all_available_documents.concalls
        elif doc_type in ("presentation", "presentations", "ppt"):
            pool = all_available_documents.presentations
        else:
            pool = all_available_documents.material_announcements
            
        for doc in pool:
            if period_or_year.lower() in (doc.period_or_date or "").lower() or period_or_year.lower() in (doc.title or "").lower():
                return doc
                
    # 2. Check SQLite source_documents table
    conn = database.get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT title, url, doc_type, period_or_date, discovery_source, actual_source_host
            FROM source_documents
            WHERE symbol = ? AND (doc_type LIKE ? OR doc_type = ?) AND (period_or_date LIKE ? OR title LIKE ?)
            ORDER BY id DESC LIMIT 1
        """, (clean_sym, f"%{doc_type}%", doc_type, f"%{period_or_year}%", f"%{period_or_year}%"))
        row = cur.fetchone()
        if row:
            return DocumentItem(
                ticker=clean_sym,
                company_name=company_name or clean_sym,
                title=row["title"],
                name=row["title"],
                url=row["url"],
                doc_type=row["doc_type"],
                period_or_date=row["period_or_date"],
                discovery_source=row["discovery_source"],
                actual_source_host=row["actual_source_host"],
                is_direct_pdf=True,
                validation_status="Valid"
            )
    finally:
        conn.close()
        
    # 3. Live On-Demand Discovery Waterfall via document_sourcing
    try:
        import document_sourcing
        discovered = document_sourcing.discover_historical_document(
            clean_sym, company_name or clean_sym, doc_type, period_or_year
        )
        if discovered:
            return discovered
    except Exception as e:
        print(f"Notice: Live historical document discovery error for {clean_sym}: {e}")
        
    return None

def get_or_generate_document_summary(symbol: str, company_name: str, doc: DocumentItem) -> Dict[str, Any]:
    """
    Retrieves the document's cached AI summary from SQLite or extracts and generates it via Gemini.
    Reuses stored summaries to minimize repeated LLM token costs.
    """
    clean_sym = symbol.upper().strip()
    
    # 1. Check SQLite cache
    cached = database.get_document_summary(doc.url)
    if cached and cached.get("key_takeaways"):
        return cached
        
    # 2. Download and extract pages
    try:
        pages = download_and_extract_pdf(doc.url, symbol=clean_sym)
    except Exception as e:
        print(f"    ⚠️ Could not extract text for {doc.title}: {e}")
        return {}
        
    if not pages:
        return {}
        
    # 3. Select high-signal pages for summarization
    is_ar = (doc.doc_type == "annual_report" or len(pages) > 40)
    selected_pages, _ = select_relevant_sections(
        pages, 
        is_full_annual_report=is_ar,
        max_pages_to_select=20 if is_ar else 15
    )
    
    # 4. Generate AI summary
    summary = summarize_single_document_with_llm(
        symbol=clean_sym,
        company_name=company_name,
        doc_title=doc.title,
        doc_url=doc.url,
        doc_type=doc.doc_type,
        period_or_date=doc.period_or_date,
        pages=selected_pages
    )
    
    if summary:
        database.save_document_summary(clean_sym, doc.url, doc.title, summary)
        return summary
        
    return {}

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
    historical_baseline_doc: Optional[DocumentItem] = None,
    save_output: bool = True
) -> Dict[str, Any]:
    """
    Two-Tier Document Intelligence Pipeline:
    1. Tier 1: Per-Document Summarization with SQLite Caching.
    2. Tier 2: Company-Level Synthesis with strict multi-document attribution,
       10-year audited financial statement triangulation, and on-demand historical evidence.
    """
    clean_sym = symbol.upper().strip()
    print(f"\n==================================================")
    print(f"  RUNNING MULTI-DOCUMENT AI PIPELINE: {company_name} ({clean_sym})")
    print(f"==================================================")
    
    # 1. Select the target default working set (3Y AR, 6Q CC, 6Q PPT, 8 Ann)
    candidate_docs = select_default_document_working_set(documents)
    
    # If a specific historical baseline doc is requested for Promise vs Delivery, prepend or include it
    if historical_baseline_doc and historical_baseline_doc.url not in [d.url for d in candidate_docs]:
        candidate_docs.append(historical_baseline_doc)
        
    if not candidate_docs:
        raise ValueError(f"No valid source documents found for {clean_sym}")

    # Identify primary latest and baseline documents
    latest_ar = next((d for d in candidate_docs if d.doc_type == "annual_report"), candidate_docs[0])
    older_ar = historical_baseline_doc or (documents.annual_reports[1] if len(documents.annual_reports) > 1 else None)
    
    latest_doc_title = latest_ar.title
    latest_doc_url = latest_ar.url
    older_doc_title = older_ar.title if older_ar else None
    older_doc_url = older_ar.url if older_ar else None

    # 2. Tier 1: Generate or retrieve Per-Document AI Summaries (Cached in SQLite)
    print(f"  • Generating/Retrieving Per-Document AI Summaries for {len(candidate_docs)} filings...")
    doc_summaries_list: List[Dict[str, Any]] = []
    
    for doc in candidate_docs:
        print(f"    - Processing [{doc.doc_type}]: {doc.title}")
        doc_sum = get_or_generate_document_summary(clean_sym, company_name, doc)
        if doc_sum:
            doc_summaries_list.append(doc_sum)

    # 3. Extract and compile tagged excerpt chunks from primary documents
    print(f"  • Assembling Multi-Document Tagged Context...")
    tagged_chunks: List[str] = []
    
    # Documents selected for primary excerpt chunks
    selected_for_excerpts: List[DocumentItem] = []
    if latest_ar: selected_for_excerpts.append(latest_ar)
    if older_ar and older_ar.url != latest_doc_url: selected_for_excerpts.append(older_ar)
    # Add top 2 concalls and 1 presentation
    concalls_to_include = [d for d in candidate_docs if d.doc_type == "concall_transcript"][:2]
    selected_for_excerpts.extend(concalls_to_include)
    ppts_to_include = [d for d in candidate_docs if d.doc_type == "presentation"][:1]
    selected_for_excerpts.extend(ppts_to_include)
    
    for idx, doc in enumerate(selected_for_excerpts):
        try:
            pages = download_and_extract_pdf(doc.url, symbol=clean_sym)
            is_ar = (doc.doc_type == "annual_report" or len(pages) > 40)
            sel_pages, _ = select_relevant_sections(pages, is_full_annual_report=is_ar, max_pages_to_select=18 if is_ar else 12)
            
            for p_num, p_text in sel_pages:
                if p_text.strip():
                    tagged_chunks.append(
                        f"=== [DOC #{idx+1} | Title: {doc.title} | Type: {doc.doc_type} | Period: {doc.period_or_date or 'N/A'} | URL: {doc.url} | Page {p_num}] ===\n{p_text.strip()}\n"
                    )
        except Exception as e:
            print(f"    ⚠️ Failed to extract excerpts for {doc.title}: {e}")

    tagged_all_documents_text = "\n".join(tagged_chunks)

    # 4. Compile Audited Financials Summary
    financial_statements_text = format_audited_financials_for_prompt(clean_sym)
    
    candidate_meta = [
        {"title": d.title, "url": d.url, "type": d.doc_type, "period": d.period_or_date}
        for d in candidate_docs
    ]

    # 5. LLM Inference / Company-Level Synthesis
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
            "document_summaries": doc_summaries_list
        }
        return status_res

    print(f"  • Invoking Gemini for Company-Level Institutional Synthesis...")
    success, result, message = extract_document_intelligence_with_llm(
        symbol=clean_sym,
        company_name=company_name,
        latest_doc_title=latest_doc_title,
        latest_doc_url=latest_doc_url,
        latest_pages=[],
        older_doc_title=older_doc_title,
        older_doc_url=older_doc_url,
        older_pages=[],
        financial_statements_summary=financial_statements_text,
        candidate_documents_meta=candidate_meta,
        precomputed_document_summaries=doc_summaries_list,
        tagged_all_documents_text=tagged_all_documents_text
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
        
        # Save legacy JSON file for backward-compatibility
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
    """Compatibility wrapper that runs the multi-document pipeline."""
    docs = DocumentLinks(
        annual_reports=[DocumentItem(title=latest_doc_title, url=latest_doc_url, doc_type="annual_report" if is_annual_report else "concall_transcript")]
    )
    if older_doc_url:
        docs.annual_reports.append(DocumentItem(title=older_doc_title or "Baseline Doc", url=older_doc_url, doc_type="annual_report"))
        
    return run_multi_document_ai_pipeline(symbol, company_name, docs, save_output=save_output)
