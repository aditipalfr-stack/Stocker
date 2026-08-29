import re
import os
import json
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any
from bs4 import BeautifulSoup
import requests

import database
from models import DocumentItem, DocumentLinks, DocumentDiscoveryDiagnostics

BSE_SCRIP_CODES: Dict[str, str] = {
    "RELIANCE": "500325",
    "TCS": "532540",
    "INFY": "500209",
    "LT": "500510",
    "HDFCBANK": "500180",
    "ICICIBANK": "532174",
    "BHARTIARTL": "532454",
    "TATAMOTORS": "500570",
    "TMPV": "500570",
    "HINDUNILVR": "500696",
    "ITC": "500875",
    "TATASTEEL": "500470",
    "SBIN": "500112",
    "KOTAKBANK": "500247",
    "AXISBANK": "532215",
    "MARUTI": "532500",
    "SUNPHARMA": "524715",
    "WIPRO": "507685",
    "HCLTECH": "532281",
    "BAJFINANCE": "500034"
}

COMPANY_IR_DOMAINS: Dict[str, Dict[str, str]] = {
    "RELIANCE": {
        "domain": "ril.com",
        "ir_url": "https://www.ril.com/investors",
        "ar_prefix": "https://www.ril.com/download/annual-reports",
        "presentation_prefix": "https://www.ril.com/download/investor-presentations"
    },
    "TCS": {
        "domain": "tcs.com",
        "ir_url": "https://www.tcs.com/investor-relations",
        "ar_prefix": "https://www.tcs.com/content/dam/tcs/investor-relations/financial-statements",
        "presentation_prefix": "https://www.tcs.com/investor-relations/investor-presentations"
    },
    "INFY": {
        "domain": "infosys.com",
        "ir_url": "https://www.infosys.com/investors.html",
        "ar_prefix": "https://www.infosys.com/investors/reports-filings/annual-report",
        "presentation_prefix": "https://www.infosys.com/investors/presentations"
    },
    "LT": {
        "domain": "larsentoubro.com",
        "ir_url": "https://www.larsentoubro.com/corporate/investor-services/",
        "ar_prefix": "https://www.larsentoubro.com/annual-reports",
        "presentation_prefix": "https://www.larsentoubro.com/investor-presentations"
    },
    "HDFCBANK": {
        "domain": "hdfcbank.com",
        "ir_url": "https://www.hdfcbank.com/personal/about-us/investor-relations",
        "ar_prefix": "https://www.hdfcbank.com/annual-reports",
        "presentation_prefix": "https://www.hdfcbank.com/quarterly-results"
    },
    "BHARTIARTL": {
        "domain": "airtel.in",
        "ir_url": "https://www.airtel.in/about-bharti/equity",
        "ar_prefix": "https://www.airtel.in/about-bharti/equity/results-reports/annual-reports",
        "presentation_prefix": "https://www.airtel.in/about-bharti/equity/results-reports/quarterly-results"
    },
    "HINDUNILVR": {
        "domain": "hul.co.in",
        "ir_url": "https://www.hul.co.in/investor-relations/",
        "ar_prefix": "https://www.hul.co.in/investor-relations/annual-reports/",
        "presentation_prefix": "https://www.hul.co.in/investor-relations/quarterly-results/"
    }
}

def format_filing_date(date_str: str) -> Optional[str]:
    """Formats raw exchange timestamp (e.g. '2026-08-21T14:30:00' or '21-Aug-2026') into '21 Aug 2026'."""
    if not date_str:
        return None
    s = date_str.strip()
    
    # Format 1: ISO date like '2026-08-21' or '2026-08-21T14:30:00'
    m_iso = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m_iso:
        try:
            from datetime import datetime
            dt = datetime(int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3)))
            return dt.strftime("%d %b %Y")
        except Exception:
            pass

    # Format 2: '21-Aug-2026' or '21/Aug/2026'
    m_text = re.search(r"(\d{1,2})[-/ ]+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[-/ ]+(\d{4})", s, re.IGNORECASE)
    if m_text:
        day = m_text.group(1).zfill(2)
        month = m_text.group(2).capitalize()
        year = m_text.group(3)
        return f"{day} {month} {year}"

    # Format 3: '21/08/2026' or '21-08-2026'
    m_dmy = re.search(r"(\d{1,2})[-/](\d{1,2})[-/](\d{4})", s)
    if m_dmy:
        try:
            from datetime import datetime
            dt = datetime(int(m_dmy.group(3)), int(m_dmy.group(2)), int(m_dmy.group(1)))
            return dt.strftime("%d %b %Y")
        except Exception:
            pass
            
    return extract_period_or_date(s)

def extract_period_or_date(text: str) -> Optional[str]:
    """Extracts exact Date (e.g. '24 Jul 2026'), Month-Year with Quarter (e.g. 'Jun 2026 (Q1 FY27)'), or Fiscal Year."""
    if not text:
        return None
    
    # 1. Exact Date with Day Month Year (e.g. '24 Jul 2026', '24-07-2026', '2026-07-24')
    d_match = re.search(r"\b(\d{1,2})[-/ ]+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[-/ ]+(\d{4})\b", text, re.IGNORECASE)
    if d_match:
        day = d_match.group(1).zfill(2)
        month = d_match.group(2).capitalize()
        year = d_match.group(3)
        return f"{day} {month} {year}"
        
    iso_date = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", text)
    if iso_date:
        return f"{iso_date.group(3)}/{iso_date.group(2)}/{iso_date.group(1)}"

    # 2. Date with Day Month (e.g. '18 Aug', '24 Jul' in recent announcements)
    d_match_short = re.search(r"\b(\d{1,2})[-/ ]+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\b", text, re.IGNORECASE)
    if d_match_short:
        day = d_match_short.group(1).zfill(2)
        month = d_match_short.group(2).capitalize()
        return f"{day} {month} 2026"

    # 3. Month & Year pattern (e.g. 'Jun 2026', 'Mar 2026', 'December 2025')
    m_match = re.search(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s*(\d{4})\b", text, re.IGNORECASE)
    if m_match:
        month = m_match.group(1).capitalize()
        year = int(m_match.group(2))
        yr_short = str(year)[2:]
        next_yr_short = str(year + 1)[2:]
        
        # Standard Indian Financial Year Quarter Mapping
        if month in ("Jun", "June"):
            return f"Jun {year} (Q1 FY{next_yr_short})"
        elif month in ("Sep", "Sept", "September"):
            return f"Sep {year} (Q2 FY{next_yr_short})"
        elif month in ("Dec", "December"):
            return f"Dec {year} (Q3 FY{next_yr_short})"
        elif month in ("Mar", "March"):
            return f"Mar {year} (Q4 FY{yr_short})"
        else:
            return f"{month} {year}"

    # 4. Quarter pattern (e.g. 'Q1 FY27' or 'Q4 FY26')
    q_match = re.search(r"(Q[1-4])\s*(?:FY)?\s*['\"]?(\d{2,4})", text, re.IGNORECASE)
    if q_match:
        quarter = q_match.group(1).upper()
        yr = q_match.group(2)
        if len(yr) == 4:
            yr = yr[2:]
        return f"{quarter} FY{yr}"

    # 5. FY pattern (e.g. 'FY 2025-26' or 'FY26')
    fy_match = re.search(r"FY\s*['\"]?(\d{2,4})(?:-(\d{2,4}))?", text, re.IGNORECASE)
    if fy_match:
        yr = fy_match.group(1)
        if len(yr) == 2:
            yr = f"20{yr}"
        return f"FY{yr}"
        
    y_match = re.search(r"\b(201\d|202\d)\b", text)
    if y_match:
        return f"FY{y_match.group(1)}"
        
    return None

from concurrent.futures import ThreadPoolExecutor

def verify_document_network_and_content(
    title: str,
    url: str,
    doc_type: str,
    symbol: str,
    check_network: bool = True
) -> Tuple[bool, Optional[int], str]:
    """
    True document validation:
    1. Rejects fake/placeholder URLs (ending with #documents or # or internal anchors).
    2. Enforces valid http/https URL and non-empty title.
    3. Rejects generic homepages.
    4. When check_network is True:
       - Sends HTTP GET stream request (first 512 bytes) with official headers.
       - Verifies HTTP 200 status code (rejects 404, 403, 500).
       - Confirms the response is NOT an HTML error/access-denied page disguised as a PDF.
       - Verifies PDF magic bytes (%PDF) for PDF documents.
       - Extracts exact file size in bytes from Content-Length.
    Returns: (is_valid: bool, file_size_bytes: Optional[int], status_reason: str)
    """
    if not url or not title:
        return False, None, "Empty URL or Title"
        
    url_clean = url.strip()
    if url_clean.endswith("#documents") or url_clean.endswith("#") or "/#/" in url_clean or url_clean.startswith("#"):
        return False, None, "Rejected: Fake placeholder or anchor link"
        
    if not url_clean.startswith("http://") and not url_clean.startswith("https://"):
        return False, None, "Rejected: Invalid protocol (must be http/https)"
        
    parsed = urlparse(url_clean)
    host = parsed.netloc.lower()
    
    # Generic homepages are not documents
    path = parsed.path.strip("/")
    if not path or path in ("", "index.html", "home", "company", "investors", "investor-relations"):
        return False, None, "Rejected: Generic homepage link"

    if not check_network:
        return True, None, "Passed Syntax Checks"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": f"https://{host}/" if host else "https://www.bseindia.com/"
    }

    try:
        with requests.get(url_clean, headers=headers, stream=True, timeout=6, allow_redirects=True) as resp:
            if resp.status_code != 200:
                return False, None, f"HTTP {resp.status_code} Error"
                
            content_type = resp.headers.get("Content-Type", "").lower()
            content_length = resp.headers.get("Content-Length")
            file_size = int(content_length) if content_length and content_length.isdigit() else None
            
            # Read first 512 bytes
            chunk = resp.raw.read(512)
            
            # Check if an HTML error page is returned instead of a filing
            if b"<html" in chunk.lower() or b"<!doctype html" in chunk.lower() or b"<title>404" in chunk.lower() or b"access denied" in chunk.lower():
                # Allow only if it's an announcement web page on BSE/NSE
                if doc_type != "announcement" or "pdf" in url_clean.lower():
                    return False, None, "Rejected: HTML error page returned instead of document"
                    
            # For PDF documents, verify magic bytes (%PDF)
            is_pdf = url_clean.lower().endswith(".pdf") or ".pdf" in url_clean.lower() or "pdf" in content_type
            if is_pdf and doc_type in ("annual_report", "concall_transcript", "presentation"):
                if not chunk.startswith(b"%PDF") and b"%PDF" not in chunk[:128]:
                    return False, None, "Rejected: File missing valid %PDF magic header"
                    
            return True, file_size, "Verified Live Document"
    except requests.exceptions.Timeout:
        return False, None, "Connection timed out during validation"
    except Exception as e:
        return False, None, f"Network validation failed: {str(e)[:40]}"

def validate_document_candidate(
    title: str,
    url: str,
    doc_type: str,
    symbol: str
) -> Tuple[bool, str]:
    """Fast pre-validation syntax check."""
    is_valid, _, reason = verify_document_network_and_content(title, url, doc_type, symbol, check_network=False)
    return is_valid, reason

def classify_document_title(raw_title: str, company_name: str = "", period: Optional[str] = None) -> Tuple[str, str]:
    """
    Strict fundamental classification of filing titles:
    Returns (doc_type, formatted_title)
    doc_type is one of: 'annual_report', 'concall_transcript', 'presentation', 'announcement', 'general'
    """
    if not raw_title:
        return "general", ""
    lower_t = raw_title.lower().strip()
    
    # 1. Negative Guards: Explicit Capital calls / rights notices / routine corporate intimations
    is_capital_call = any(k in lower_t for k in [
        "partly paid", "call money", "share call", "first and final call", 
        "reminder notice", "allotment of", "conversion of partly", "paid-up",
        "forfeiture of shares", "right issue", "rights issue"
    ])
    is_routine_notice = any(k in lower_t for k in [
        "loss of share", "duplicate share", "trading window", "closure of trading",
        "newspaper publication", "loss of certificate"
    ])
    
    # 2. Annual Reports & Integrated Filings
    if not is_capital_call and any(k in lower_t for k in [
        "annual report", "integrated report", "integrated annual report", 
        "business responsibility and sustainability", "brsr", "annual accounts"
    ]):
        formatted_title = raw_title
        if company_name and len(raw_title) <= 20:
            formatted_title = f"{company_name} {raw_title}"
        return "annual_report", formatted_title
        
    # 3. Earnings Conference Call Transcripts (Strict - no generic 'call' word matches!)
    is_concall = not is_capital_call and (
        "earnings call" in lower_t or
        "conference call" in lower_t or
        "concall" in lower_t or
        "earnings conference" in lower_t or
        "call transcript" in lower_t or
        ("transcript" in lower_t and not any(w in lower_t for w in ["share", "transfer", "notice", "court", "tribunal"]))
    )
    if is_concall:
        formatted_title = raw_title
        if raw_title.lower() in ("transcript", "concall transcript", "earnings call"):
            formatted_title = f"{company_name} {period or ''} Earnings Call Transcript".strip()
        return "concall_transcript", formatted_title

    # 4. Investor Presentations & Quarterly Decks
    is_ppt = any(k in lower_t for k in [
        "investor presentation", "earnings presentation", "investor deck", 
        "analyst presentation", "quarterly presentation", "investor update"
    ]) or (("presentation" in lower_t or "ppt" in lower_t) and not is_capital_call)
    if is_ppt:
        formatted_title = raw_title
        if raw_title.lower() in ("presentation", "ppt", "investor presentation"):
            formatted_title = f"{company_name} {period or ''} Investor Presentation".strip()
        return "presentation", formatted_title

    # 5. Material Exchange Announcements & Corporate Actions
    if is_capital_call or is_routine_notice or any(k in lower_t for k in [
        "announcement", "outcome", "board meeting", "filing", "regulation 30", 
        "press release", "media release", "acquisition", "order", "contract", 
        "intimation", "disclosure", "resignation", "appointment", "update", "clarification"
    ]):
        return "announcement", raw_title
        
    return "general", raw_title

def discover_documents_screener(
    soup: BeautifulSoup, 
    symbol: str, 
    company_name: str,
    from_date_dt: Optional[datetime] = None
) -> List[DocumentItem]:
    """
    Stage 1: Discover verified documents from Screener.in's document sections.
    In incremental mode (from_date_dt is provided), skips filings older than the date window.
    """
    found: List[DocumentItem] = []
    doc_section = soup.find(id="documents")
    if not doc_section:
        return found
        
    from_yr = None
    if from_date_dt:
        from_yr = from_date_dt.year + (from_date_dt.month - 1) / 12.0 + from_date_dt.day / 365.0
        
    for a in doc_section.find_all("a", href=True):
        raw_title = re.sub(r"\s+", " ", a.text).strip()
        raw_title = re.sub(r"\s*from\s+bse\s*", "", raw_title, flags=re.IGNORECASE).strip()
        href = a["href"].strip()
        if not raw_title or not href:
            continue
            
        if not href.startswith("http"):
            href = f"https://www.screener.in{href}"
            
        parsed = urlparse(href)
        host = parsed.netloc.lower()
        is_pdf = href.lower().endswith(".pdf") or ".pdf" in href.lower()
        
        # Check period from anchor or parent element (e.g. <li> or <tr>)
        period = extract_period_or_date(raw_title)
        if not period:
            parent_el = a.find_parent(["li", "tr", "div"])
            if parent_el:
                period = extract_period_or_date(parent_el.text)
        
        # In incremental mode, skip filings with an explicit date older than the safety window
        if from_yr and period:
            try:
                from financial_engine import parse_filing_period_to_year
                p_yr = parse_filing_period_to_year(period)
                if p_yr is not None and p_yr < (from_yr - 0.05):
                    continue
            except Exception:
                pass
                
        doc_type, formatted_title = classify_document_title(raw_title, company_name, period)
        is_valid, _ = validate_document_candidate(formatted_title, href, doc_type, symbol)
        
        found.append(DocumentItem(
            ticker=symbol,
            company_name=company_name,
            title=formatted_title,
            name=formatted_title,
            url=href,
            doc_type=doc_type,
            period_or_date=period,
            discovery_source="Screener.in",
            actual_source_host=host or "screener.in",
            actual_source_url=href,
            is_direct_pdf=is_pdf,
            validation_status="Valid" if is_valid else "Invalid"
        ))
        
    return found

def discover_documents_bse_fallback(
    symbol: str, 
    company_name: str, 
    needed_types: List[str],
    from_date_str: Optional[str] = None,
    to_date_str: Optional[str] = None
) -> List[DocumentItem]:
    """Stage 2: Discover direct exchange filings from BSE India within the date window."""
    found: List[DocumentItem] = []
    scrip_code = BSE_SCRIP_CODES.get(symbol.upper().strip())
    if not scrip_code:
        return found
        
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.bseindia.com/"
    }
    
    prev_d = from_date_str or ""
    to_d = to_date_str or ""
    api_url = f"https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w?pageno=1&strCat=-1&strPrevDate={prev_d}&strScrip={scrip_code}&strSearch=P&strToDate={to_d}&strType=C"
    
    try:
        resp = requests.get(api_url, headers=headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            table = data.get("Table", [])
            for item in table:
                headline = item.get("NEWSSUB", "") or item.get("HEADLINE", "")
                attach_name = item.get("ATTACHMENTNAME", "")
                dt = item.get("NEWS_DT", "")
                
                if not attach_name or not headline:
                    continue
                    
                direct_url = f"https://www.bseindia.com/xml-data/corpfiling/AttachHis/{attach_name}"
                is_pdf = direct_url.lower().endswith(".pdf")
                period = format_filing_date(dt) or extract_period_or_date(headline)
                
                doc_type, formatted_title = classify_document_title(headline, company_name, period)
                if doc_type == "general":
                    doc_type = "announcement"
                    
                if needed_types and doc_type not in needed_types and "announcement" not in needed_types:
                    continue
                    
                is_valid, _ = validate_document_candidate(formatted_title, direct_url, doc_type, symbol)
                if is_valid:
                    found.append(DocumentItem(
                        ticker=symbol,
                        company_name=company_name,
                        title=formatted_title[:120],
                        name=formatted_title[:120],
                        url=direct_url,
                        doc_type=doc_type,
                        period_or_date=period,
                        discovery_source="BSE India",
                        actual_source_host="bseindia.com",
                        actual_source_url=direct_url,
                        is_direct_pdf=is_pdf,
                        validation_status="Valid"
                    ))
    except Exception:
        pass
        
    return found

def discover_documents_nse_fallback(
    symbol: str, 
    company_name: str, 
    needed_types: List[str],
    from_date_str: Optional[str] = None,
    to_date_str: Optional[str] = None
) -> List[DocumentItem]:
    """Stage 3: Discover verified direct exchange filings from NSE India within the date window."""
    found: List[DocumentItem] = []
    clean_sym = symbol.upper().strip()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.nseindia.com/"
    }
    
    if from_date_str and to_date_str:
        api_url = f"https://www.nseindia.com/api/corporate-announcements?index=equities&symbol={clean_sym}&from_date={from_date_str}&to_date={to_date_str}"
    else:
        api_url = f"https://www.nseindia.com/api/corporate-announcements?index=equities&symbol={clean_sym}"
        
    try:
        session = requests.Session()
        session.get("https://www.nseindia.com", headers=headers, timeout=4)
        resp = session.get(api_url, headers=headers, timeout=4)
        if resp.status_code == 200:
            items = resp.json()
            if isinstance(items, list):
                for item in items:
                    desc = item.get("desc", "") or item.get("an_dt", "")
                    attach_file = item.get("attchmntFile", "")
                    dt = item.get("an_dt", "")
                    
                    if not desc or not attach_file:
                        continue
                    pdf_url = attach_file if attach_file.startswith("http") else f"https://archives.nseindia.com/corporate/{attach_file}"
                    period = format_filing_date(dt) or extract_period_or_date(desc)
                    
                    doc_type, formatted_title = classify_document_title(desc, company_name, period)
                    if doc_type == "general":
                        doc_type = "announcement"
                        
                    is_valid, _ = validate_document_candidate(formatted_title, pdf_url, doc_type, symbol)
                    if is_valid:
                        found.append(DocumentItem(
                            ticker=symbol,
                            company_name=company_name,
                            title=formatted_title[:120],
                            name=formatted_title[:120],
                            url=pdf_url,
                            doc_type=doc_type,
                            period_or_date=period,
                            discovery_source="NSE India",
                            actual_source_host="nseindia.com",
                            actual_source_url=pdf_url,
                            is_direct_pdf=pdf_url.lower().endswith(".pdf"),
                            validation_status="Valid"
                        ))
    except Exception:
        pass
    return found

def discover_documents_company_ir_fallback(
    symbol: str, 
    company_name: str, 
    needed_types: List[str],
    from_date_dt: Optional[datetime] = None
) -> List[DocumentItem]:
    """
    Stage 4: Discover verified documents directly from live Company Investor Relations websites.
    NEVER creates guessed/synthetic URLs. Only parses real anchor tags from the live IR page.
    In incremental mode (from_date_dt is provided), processes only the newest entries and stops
    when filings fall before the cutoff window (preserving 5-day safety overlap).
    """
    found: List[DocumentItem] = []
    ir_info = COMPANY_IR_DOMAINS.get(symbol.upper())
    if not ir_info:
        return found
        
    ir_url = ir_info.get("ir_url")
    if not ir_url:
        return found
        
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        resp = requests.get(ir_url, headers=headers, timeout=6)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            
            # Filter candidate anchors to relevant filing links (PDFs or filing keywords)
            candidate_anchors: List[Tuple[str, str]] = []
            for a in soup.find_all("a", href=True):
                text = a.text.strip()
                href = a["href"].strip()
                if not href or not text or len(text) < 3:
                    continue
                combined_lower = f"{text} {href}".lower()
                if (href.lower().endswith(".pdf") or 
                    any(kw in combined_lower for kw in ["report", "annual", "presentation", "transcript", "concall", "investor", "financial", "result", "quarter"])):
                    candidate_anchors.append((text, href))
            
            # In incremental mode, limit scan to the newest 20 relevant filing anchors
            scan_anchors = candidate_anchors[:20] if from_date_dt else candidate_anchors
            
            from_yr = None
            if from_date_dt:
                from_yr = from_date_dt.year + (from_date_dt.month - 1) / 12.0 + from_date_dt.day / 365.0
                
            for text, href in scan_anchors:
                # Resolve relative URL
                if href.startswith("/"):
                    parsed_domain = urlparse(ir_url)
                    href = f"{parsed_domain.scheme}://{parsed_domain.netloc}{href}"
                elif not href.startswith("http"):
                    href = f"{ir_url.rstrip('/')}/{href}"
                    
                period = extract_period_or_date(text) or extract_period_or_date(href)
                
                # Check if this filing is strictly older than the incremental date cutoff
                if from_yr and period:
                    try:
                        from financial_engine import parse_filing_period_to_year
                        p_yr = parse_filing_period_to_year(period)
                        if p_yr is not None and p_yr < (from_yr - 0.05):
                            # Filing is prior to recent window; skip older historical entries
                            continue
                    except Exception:
                        pass
                        
                doc_type, formatted_title = classify_document_title(text, company_name, period)
                if doc_type in ("annual_report", "presentation", "concall_transcript") and (not needed_types or doc_type in needed_types):
                    is_valid, _ = validate_document_candidate(formatted_title, href, doc_type, symbol)
                    if is_valid:
                        parsed_h = urlparse(href)
                        found.append(DocumentItem(
                            ticker=symbol,
                            company_name=company_name,
                            title=formatted_title[:120],
                            name=formatted_title[:120],
                            url=href,
                            doc_type=doc_type,
                            period_or_date=period,
                            discovery_source="Company IR",
                            actual_source_host=parsed_h.netloc.lower(),
                            actual_source_url=href,
                            is_direct_pdf=href.lower().endswith(".pdf"),
                            validation_status="Valid"
                        ))
    except Exception:
        pass
        
    return found

def execute_document_sourcing_waterfall(
    symbol: str,
    company_name: str,
    screener_soup: Optional[BeautifulSoup] = None
) -> DocumentLinks:
    """
    Executes the multi-source waterfall with TRUE network & content validation:
    1. Screener.in (Primary Discovery Layer)
    2. BSE India (Direct Exchange Filings Fallback)
    3. NSE India (Exchange Announcements Fallback)
    4. Company IR (Official Live Repository Fallback - No Guessed URLs)
    5. Parallel Network & PDF Signature Validation
    6. SQLite Index Persistence in source_documents
    """
    clean_sym = symbol.upper().strip()
    all_raw_docs: List[DocumentItem] = []
    fallback_sources_used: List[str] = []
    invalid_links_count = 0
    
    # 0. Check previous sync state to establish Date-Window for Incremental Refresh
    sync_state = database.get_document_sync_state(clean_sym, category="all")
    last_checked_at = sync_state.get("last_checked_at") if sync_state else None
    
    from_date_dt: Optional[datetime] = None
    from_date_bse: Optional[str] = None
    to_date_bse: Optional[str] = None
    from_date_nse: Optional[str] = None
    to_date_nse: Optional[str] = None
    
    if last_checked_at:
        try:
            last_dt = datetime.fromisoformat(last_checked_at.replace("Z", "+00:00"))
            overlap_days = 5  # Safety overlap window
            from_date_dt = last_dt - timedelta(days=overlap_days)
            from_date_bse = from_date_dt.strftime("%Y%m%d")
            to_date_bse = datetime.now(timezone.utc).strftime("%Y%m%d")
            from_date_nse = from_date_dt.strftime("%d-%m-%Y")
            to_date_nse = datetime.now(timezone.utc).strftime("%d-%m-%Y")
        except Exception:
            pass

    # 1. Primary Discovery: Screener.in
    if screener_soup:
        screener_docs = discover_documents_screener(screener_soup, clean_sym, company_name, from_date_dt=from_date_dt)
        all_raw_docs.extend(screener_docs)

    # Check category counts
    ar_count = sum(1 for d in all_raw_docs if d.doc_type == "annual_report")
    cc_count = sum(1 for d in all_raw_docs if d.doc_type == "concall_transcript")
    ppt_count = sum(1 for d in all_raw_docs if d.doc_type == "presentation")
    
    needed_types = []
    if ar_count < 3: needed_types.append("annual_report")
    if cc_count < 4: needed_types.append("concall_transcript")
    if ppt_count < 4: needed_types.append("presentation")
    needed_types.append("announcement")
    
    # 2. Stage 2: BSE India Fallback (Searching inside the date window)
    if needed_types:
        bse_docs = discover_documents_bse_fallback(
            clean_sym, 
            company_name, 
            needed_types,
            from_date_str=from_date_bse,
            to_date_str=to_date_bse
        )
        if bse_docs:
            fallback_sources_used.append("BSE India")
            all_raw_docs.extend(bse_docs)

    # 3. Stage 3: NSE India Fallback (Searching inside the date window)
    ann_count = sum(1 for d in all_raw_docs if d.doc_type == "announcement")
    if ann_count < 4:
        nse_docs = discover_documents_nse_fallback(
            clean_sym, 
            company_name, 
            ["announcement"],
            from_date_str=from_date_nse,
            to_date_str=to_date_nse
        )
        if nse_docs:
            fallback_sources_used.append("NSE India")
            all_raw_docs.extend(nse_docs)
                    
    # 4. Stage 4: Company IR Fallback (Real web parsing with incremental cutoff)
    ar_count = sum(1 for d in all_raw_docs if d.doc_type == "annual_report")
    if ar_count < 2:
        ir_docs = discover_documents_company_ir_fallback(clean_sym, company_name, ["annual_report", "presentation"], from_date_dt=from_date_dt)
        if ir_docs:
            fallback_sources_used.append("Company IR")
            all_raw_docs.extend(ir_docs)

    # Deduplicate by actual_source_url
    seen_urls = set()
    deduped_docs: List[DocumentItem] = []
    for doc in all_raw_docs:
        norm_url = doc.actual_source_url.strip().rstrip("/")
        if norm_url not in seen_urls:
            seen_urls.add(norm_url)
            deduped_docs.append(doc)

    # 5. Smart Incremental Validation: Skip unchanged, already-verified documents in SQLite
    known_db_docs = {d["url"]: d for d in database.get_source_documents(clean_sym)}
    
    docs_to_validate_network: List[DocumentItem] = []
    already_valid_docs: List[DocumentItem] = []
    
    for doc in deduped_docs:
        norm_url = doc.actual_source_url.strip()
        if norm_url in known_db_docs and known_db_docs[norm_url].get("is_valid") == 1:
            # Document is already known and verified in SQLite DB: SKIP network validation
            cached_row = known_db_docs[norm_url]
            doc.validation_status = "Valid"
            doc.file_size_bytes = cached_row.get("file_size_bytes")
            already_valid_docs.append(doc)
        else:
            # New or unverified document: queue for network validation
            docs_to_validate_network.append(doc)

    def _validate_document(doc: DocumentItem) -> DocumentItem:
        is_valid, size_bytes, _ = verify_document_network_and_content(
            title=doc.title,
            url=doc.url,
            doc_type=doc.doc_type,
            symbol=doc.ticker,
            check_network=True
        )
        doc.validation_status = "Valid" if is_valid else "Invalid"
        if size_bytes:
            doc.file_size_bytes = size_bytes
        return doc

    newly_validated_docs: List[DocumentItem] = []
    if docs_to_validate_network:
        with ThreadPoolExecutor(max_workers=min(8, len(docs_to_validate_network))) as executor:
            validated_candidates = list(executor.map(_validate_document, docs_to_validate_network))
        for doc in validated_candidates:
            if doc.validation_status == "Valid":
                newly_validated_docs.append(doc)
            else:
                invalid_links_count += 1
                
    # Persist any newly validated documents into SQLite source_documents table
    if newly_validated_docs:
        try:
            database.save_source_documents(clean_sym, newly_validated_docs)
        except Exception as e:
            print(f"Notice: Failed to persist source documents to SQLite for {clean_sym}: {e}")

    # Combine all valid documents (both previously known from DB and newly verified)
    all_valid_combined = already_valid_docs + newly_validated_docs
    
    # Also incorporate any known valid documents from SQLite that may not have been returned in the recent scrape
    seen_combined_urls = {d.url.strip() for d in all_valid_combined}
    for db_url, db_doc in known_db_docs.items():
        if db_url not in seen_combined_urls and db_doc.get("is_valid") == 1:
            all_valid_combined.append(DocumentItem(
                ticker=clean_sym,
                company_name=company_name,
                title=db_doc.get("title", ""),
                name=db_doc.get("title", ""),
                url=db_url,
                doc_type=db_doc.get("doc_type", "general"),
                period_or_date=db_doc.get("period_or_date"),
                discovery_source=db_doc.get("discovery_source", "SQLite Archive"),
                actual_source_host=db_doc.get("actual_source_host", "bseindia.com"),
                actual_source_url=db_url,
                is_direct_pdf=db_url.lower().endswith(".pdf"),
                validation_status="Valid"
            ))

    # Update sync state timestamp since external source check actually ran
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        database.update_document_sync_state(clean_sym, category="all", checked_at=now_iso)
    except Exception:
        pass

    # Group by category and limit to target history
    annual_reports = [d for d in all_valid_combined if d.doc_type == "annual_report"][:3]
    concalls = [d for d in all_valid_combined if d.doc_type == "concall_transcript"][:6]
    presentations = [d for d in all_valid_combined if d.doc_type == "presentation"][:6]
    announcements = [d for d in all_valid_combined if d.doc_type == "announcement"][:8]
    
    total_ai_ready = len(annual_reports) + len(concalls) + len(presentations) + len(announcements)
    overall_status = "Ready" if total_ai_ready >= 4 else ("Partial" if total_ai_ready > 0 else "Missing")
    
    diagnostics = DocumentDiscoveryDiagnostics(
        target_annual_reports_count=3,
        annual_reports_found=len(annual_reports),
        target_concalls_count=6,
        concalls_found=len(concalls),
        target_presentations_count=6,
        presentations_found=len(presentations),
        target_announcements_count=8,
        announcements_found=len(announcements),
        invalid_links_rejected=invalid_links_count,
        fallback_sources_used=fallback_sources_used,
        ai_ready_documents_count=total_ai_ready,
        overall_status=overall_status
    )
    
    return DocumentLinks(
        annual_reports=annual_reports,
        concalls=concalls,
        presentations=presentations,
        material_announcements=announcements,
        diagnostics=diagnostics,
        checked_at=now_iso
    )

def discover_historical_document(
    symbol: str, 
    company_name: str, 
    doc_type: str, 
    period_or_year: str
) -> Optional[DocumentItem]:
    """
    On-Demand True Historical Document Discovery:
    When Promise vs Delivery or a multi-year capex verification requires an older filing
    (e.g., FY21/FY22 Annual Report or older Concall) that is not in the default working set,
    this function performs targeted live waterfall discovery across trusted archives:
    1. BSE Dedicated Historical Annual Reports Archive API (10-15 year archive)
    2. BSE Paginated Corporate Announcements API (pages 1-4)
    3. Company IR Historical Repository (official company investor pages)
    Stop as soon as a correctly validated document is found.
    """
    clean_sym = symbol.upper().strip()
    target_clean = period_or_year.lower().strip().replace("fy", "20")
    scrip_code = BSE_SCRIP_CODES.get(clean_sym)
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.bseindia.com/"
    }

    # 1. Target: Annual Reports via BSE Dedicated Historical Archive API
    if scrip_code and doc_type in ("annual_report", "annual_reports", "ar"):
        bse_ar_url = f"https://api.bseindia.com/BseIndiaAPI/api/AnnualReport/w?strScripCode={scrip_code}"
        try:
            resp = requests.get(bse_ar_url, headers=headers, timeout=6)
            if resp.status_code == 200:
                data = resp.json()
                items = data if isinstance(data, list) else data.get("Table", [])
                for item in items:
                    yr = str(item.get("YEAR", "") or item.get("FinYear", "") or "")
                    attach = item.get("ATTACHMENTNAME", "") or item.get("URL", "")
                    heading = item.get("HEADING", "") or f"{company_name} Annual Report {yr}"
                    
                    if not attach:
                        continue
                        
                    # Match target year (e.g. '2021', '21', 'FY21')
                    if target_clean in yr.lower() or target_clean in heading.lower() or period_or_year.lower() in yr.lower():
                        direct_url = attach if attach.startswith("http") else f"https://www.bseindia.com/bseplus/AnnualReport/{scrip_code}/{attach}"
                        is_valid, size, _ = verify_document_network_and_content(heading, direct_url, "annual_report", clean_sym, check_network=True)
                        if is_valid:
                            doc = DocumentItem(
                                ticker=clean_sym,
                                company_name=company_name,
                                title=f"{company_name} Annual Report {yr}".strip(),
                                name=f"{company_name} Annual Report {yr}".strip(),
                                url=direct_url,
                                doc_type="annual_report",
                                period_or_date=f"FY{yr[-2:] if len(yr) >= 2 else yr}",
                                discovery_source="BSE India Archive API",
                                actual_source_host="bseindia.com",
                                actual_source_url=direct_url,
                                is_direct_pdf=True,
                                validation_status="Valid",
                                file_size_bytes=size
                            )
                            database.save_source_documents(clean_sym, [doc])
                            return doc
        except Exception:
            pass

    # 2. Target: BSE Paginated Corporate Announcements (Pages 1 to 4)
    if scrip_code:
        for pageno in range(1, 5):
            api_url = f"https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w?pageno={pageno}&strCat=-1&strPrevDate=&strScrip={scrip_code}&strSearch=P&strToDate=&strType=C"
            try:
                resp = requests.get(api_url, headers=headers, timeout=6)
                if resp.status_code == 200:
                    data = resp.json()
                    table = data.get("Table", [])
                    if not table:
                        break
                    for item in table:
                        headline = item.get("NEWSSUB", "") or item.get("HEADLINE", "")
                        attach_name = item.get("ATTACHMENTNAME", "")
                        dt = item.get("NEWS_DT", "")
                        if not attach_name or not headline:
                            continue
                            
                        period = format_filing_date(dt) or extract_period_or_date(headline)
                        d_type, f_title = classify_document_title(headline, company_name, period)
                        
                        # Match doc_type and target year/period
                        if (d_type == doc_type or doc_type in d_type):
                            if target_clean in headline.lower() or (period and target_clean in period.lower()) or period_or_year.lower() in headline.lower():
                                direct_url = f"https://www.bseindia.com/xml-data/corpfiling/AttachHis/{attach_name}"
                                is_valid, size, _ = verify_document_network_and_content(f_title, direct_url, d_type, clean_sym, check_network=True)
                                if is_valid:
                                    doc = DocumentItem(
                                        ticker=clean_sym,
                                        company_name=company_name,
                                        title=f_title[:120],
                                        name=f_title[:120],
                                        url=direct_url,
                                        doc_type=d_type,
                                        period_or_date=period,
                                        discovery_source="BSE India Paginated Archive",
                                        actual_source_host="bseindia.com",
                                        actual_source_url=direct_url,
                                        is_direct_pdf=True,
                                        validation_status="Valid",
                                        file_size_bytes=size
                                    )
                                    database.save_source_documents(clean_sym, [doc])
                                    return doc
            except Exception:
                pass

    # 3. Target: Company IR Repository fallback
    ir_info = COMPANY_IR_DOMAINS.get(clean_sym)
    if ir_info:
        ir_url = ir_info.get("ir_url")
        if ir_url:
            try:
                ir_resp = requests.get(ir_url, headers=headers, timeout=6)
                if ir_resp.status_code == 200:
                    soup = BeautifulSoup(ir_resp.text, "html.parser")
                    for a in soup.find_all("a", href=True):
                        text = a.text.strip()
                        href = a["href"].strip()
                        if not href or not text or len(text) < 3:
                            continue
                        if href.startswith("/"):
                            parsed_domain = urlparse(ir_url)
                            href = f"{parsed_domain.scheme}://{parsed_domain.netloc}{href}"
                        elif not href.startswith("http"):
                            href = f"{ir_url.rstrip('/')}/{href}"
                            
                        period = extract_period_or_date(text) or extract_period_or_date(href)
                        d_type, f_title = classify_document_title(text, company_name, period)
                        if (d_type == doc_type or doc_type in d_type) and (target_clean in text.lower() or target_clean in href.lower()):
                            is_valid, size, _ = verify_document_network_and_content(f_title, href, d_type, clean_sym, check_network=True)
                            if is_valid:
                                parsed_h = urlparse(href)
                                doc = DocumentItem(
                                    ticker=clean_sym,
                                    company_name=company_name,
                                    title=f_title[:120],
                                    name=f_title[:120],
                                    url=href,
                                    doc_type=d_type,
                                    period_or_date=period,
                                    discovery_source="Company IR Archive",
                                    actual_source_host=parsed_h.netloc.lower(),
                                    actual_source_url=href,
                                    is_direct_pdf=href.lower().endswith(".pdf"),
                                    validation_status="Valid",
                                    file_size_bytes=size
                                )
                                database.save_source_documents(clean_sym, [doc])
                                return doc
            except Exception:
                pass
                
    return None
