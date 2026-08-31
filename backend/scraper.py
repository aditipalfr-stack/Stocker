import os
import json
import re
import time
from datetime import datetime, timezone
import requests
from bs4 import BeautifulSoup
from typing import Dict, Any, Optional, List, Tuple

import database
from models import (
    KeyRatios, FinancialStatement, FinancialRow,
    ConcallInsight, AnnualReportInsight, DocumentLinks, DocumentItem
)

CACHE_DIR = os.path.join(os.path.dirname(__file__), "data")
CACHE_FILE = os.path.join(CACHE_DIR, "stocks_cache.json")
CACHE_TTL_SECONDS = 12 * 3600  # 12 hours cache freshness

# Common ticker alias mapping for corporate renames / demergers
TICKER_ALIASES: Dict[str, List[str]] = {
    "TATAMOTORS": ["TMPV", "TMCV", "TATAMOTORS"],
}

def clean_metric_name(text: str) -> str:
    if not text:
        return ""
    # Remove non-breaking spaces, +, and collapse whitespace
    text = text.replace("\xa0", " ").replace("+", "").strip()
    text = re.sub(r"\s+", " ", text)
    return text

def parse_num(val_str: Optional[str]) -> Optional[float]:
    if not val_str:
        return None
    val_str = val_str.strip().replace(",", "").replace("%", "").replace("₹", "").replace("Rs.", "").replace("Cr.", "").replace("Cr", "").strip()
    if not val_str or val_str in ("-", "--", "N/A", "NA", "None", "null"):
        return None
    try:
        # Check parentheses for negative numbers e.g. (1,234)
        if val_str.startswith("(") and val_str.endswith(")"):
            return -float(val_str[1:-1].strip())
        return float(val_str)
    except Exception:
        return None

NON_RAW_CASH_FLOW_METRICS = {
    "free cash flow",
    "cfo/op",
    "cfo / op",
    "cfo/pat",
    "cfo / pat"
}

def parse_screener_table(soup: BeautifulSoup, section_id: str) -> Optional[FinancialStatement]:
    section = soup.find("section", {"id": section_id})
    if not section:
        return None
    table = section.find("table")
    if not table:
        return None
        
    # Periods (thead th)
    thead = table.find("thead")
    if not thead:
        return None
    th_tags = thead.find_all("th")
    periods = [th.text.strip() for th in th_tags[1:] if th.text.strip()]
    if not periods:
        return None
        
    tbody = table.find("tbody")
    if not tbody:
        return None
        
    rows: List[FinancialRow] = []
    for tr in tbody.find_all("tr"):
        td_tags = tr.find_all("td")
        if not td_tags:
            continue
            
        raw_metric = td_tags[0].text
        metric_name = clean_metric_name(raw_metric)
        
        # Skip auxiliary or empty rows
        if not metric_name or metric_name.lower() in ("raw pdf", "notes", "download"):
            continue
            
        # Ensure non-raw injected rows from Screener do not pollute raw cash flow statement
        if section_id == "cash-flow" and metric_name.lower().strip() in NON_RAW_CASH_FLOW_METRICS:
            continue
            
        values: Dict[str, Optional[float]] = {}
        for idx, td in enumerate(td_tags[1:]):
            if idx < len(periods):
                p = periods[idx]
                values[p] = parse_num(td.text)
                
        rows.append(FinancialRow(metric=metric_name, values=values))
        
    return FinancialStatement(periods=periods, rows=rows)

def parse_screener_ratios(soup: BeautifulSoup) -> KeyRatios:
    ratios_dict = {
        "market_cap_cr": None,
        "current_price": None,
        "high_low": "",
        "stock_pe": None,
        "book_value": None,
        "dividend_yield_pct": None,
        "roce_pct": None,
        "roe_pct": None,
        "face_value": None,
        "industry_pe": None,
        "debt_to_equity": None,
        "interest_coverage": None,
        "fcf_yield_pct": None,
        "sales_growth_3yr_cagr": None,
        "profit_growth_3yr_cagr": None
    }
    
    top_ratios = soup.find("ul", {"id": "top-ratios"})
    if top_ratios:
        for li in top_ratios.find_all("li"):
            name_el = li.find("span", {"class": "name"})
            val_el = li.find("span", {"class": "nowrap value"}) or li.find("span", {"class": "number"}) or li.find("span", {"class": "value"})
            if name_el and val_el:
                name = name_el.text.strip().lower()
                val_text = val_el.text.strip()
                if "market cap" in name:
                    ratios_dict["market_cap_cr"] = parse_num(val_text)
                elif "current price" in name:
                    ratios_dict["current_price"] = parse_num(val_text)
                elif "high / low" in name:
                    ratios_dict["high_low"] = val_text
                elif "stock p/e" in name:
                    ratios_dict["stock_pe"] = parse_num(val_text)
                elif "book value" in name:
                    ratios_dict["book_value"] = parse_num(val_text)
                elif "dividend yield" in name:
                    ratios_dict["dividend_yield_pct"] = parse_num(val_text)
                elif "roce" in name:
                    ratios_dict["roce_pct"] = parse_num(val_text)
                elif "roe" in name:
                    ratios_dict["roe_pct"] = parse_num(val_text)
                elif "face value" in name:
                    ratios_dict["face_value"] = parse_num(val_text)
                elif "debt to equity" in name:
                    ratios_dict["debt_to_equity"] = parse_num(val_text)
                    
    return KeyRatios(**ratios_dict)

def parse_screener_taxonomy_metadata(soup: BeautifulSoup) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Extract only explicitly labelled Screener sector/industry metadata.

    The parser intentionally fails closed.  It does not infer classification from
    company names, peer names, or arbitrary page text.
    """
    sector: Optional[str] = None
    industry: Optional[str] = None
    sub_industry: Optional[str] = None

    # Screener exposes a deterministic market-taxonomy breadcrumb in the peer
    # section. Path depth is the hierarchy; index membership links use /company/
    # and are intentionally ignored.
    market_labels: List[str] = []
    for anchor in soup.select("#peers a[href^='/market/']"):
        label = clean_metric_name(anchor.get_text(" ", strip=True))
        if label and (not market_labels or label != market_labels[-1]):
            market_labels.append(label)
    if market_labels:
        sector = market_labels[0]
        industry = market_labels[1] if len(market_labels) > 1 else None
        sub_industry = market_labels[2] if len(market_labels) > 2 else None
        if industry and industry.lower() == sector.lower() and len(market_labels) > 2:
            industry = market_labels[2]
            sub_industry = market_labels[3] if len(market_labels) > 3 else None

    candidates = soup.select("#peers .sub, #peers p, .company-info .sub, [data-sector], [data-industry]")
    for node in candidates:
        if not sector and node.get("data-sector"):
            sector = clean_metric_name(node.get("data-sector"))
        if not industry and node.get("data-industry"):
            industry = clean_metric_name(node.get("data-industry"))
        text = clean_metric_name(node.get_text(" ", strip=True))
        if not sector:
            match = re.search(r"\bSector\s*:\s*(.+?)(?=\s+Industry\s*:|$)", text, re.IGNORECASE)
            if match:
                sector = match.group(1).strip(" -|,")
        if not industry:
            match = re.search(r"\bIndustry\s*:\s*(.+)$", text, re.IGNORECASE)
            if match:
                industry = match.group(1).strip(" -|,")
    return sector or None, industry or None, sub_industry or None

def parse_screener_documents(soup: BeautifulSoup, symbol: str, source_url: str = "", company_name: str = "") -> DocumentLinks:
    """
    Extracts lightweight document links directly from Screener HTML WITHOUT invoking
    the expensive external discovery waterfall (BSE, NSE, Company IR, network validation).
    Full external discovery is performed explicitly via /api/stocks/{symbol}/discover-filings.
    """
    clean_sym = symbol.upper().strip()
    from document_sourcing import discover_documents_screener
    try:
        screener_docs = discover_documents_screener(soup, clean_sym, company_name or clean_sym)
    except Exception as e:
        print(f"Notice: Screener document extraction note for {clean_sym}: {e}")
        screener_docs = []
        
    doc_links = DocumentLinks()
    for d in screener_docs:
        dt = (d.doc_type or "").lower()
        if "annual" in dt:
            doc_links.annual_reports.append(d)
        elif "concall" in dt:
            doc_links.concalls.append(d)
        elif "presentation" in dt:
            doc_links.presentations.append(d)
        elif "announcement" in dt:
            doc_links.material_announcements.append(d)
    return doc_links

def _is_usable_screener_html(html_text: str) -> bool:
    """Verifies that fetched Screener HTML contains usable quarters and profit-loss tables."""
    if not html_text or len(html_text) < 3000:
        return False
    try:
        sp = BeautifulSoup(html_text, "html.parser")
        q = parse_screener_table(sp, "quarters")
        pl = parse_screener_table(sp, "profit-loss")
        return bool(q and pl and q.periods and pl.periods and q.rows and pl.rows)
    except Exception:
        return False

def fetch_screener_html(symbol: str) -> Optional[Tuple[str, str, str]]:
    """
    Fetches the live HTML from Screener.in.
    Returns (html_content, source_url, statement_type) or None.
    Preference:
    1. https://www.screener.in/company/{symbol}/consolidated/ (if quarters & P&L populated)
    2. https://www.screener.in/company/{symbol}/ (standalone fallback)
    3. Screener Search API fallback for renamed tickers / aliases
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5"
    }
    
    symbols_to_try = [symbol]
    if symbol in TICKER_ALIASES:
        symbols_to_try = TICKER_ALIASES[symbol] + symbols_to_try

    for sym in symbols_to_try:
        # Try Consolidated
        cons_url = f"https://www.screener.in/company/{sym}/consolidated/"
        try:
            resp = requests.get(cons_url, headers=headers, timeout=12)
            if resp.status_code == 200 and _is_usable_screener_html(resp.text):
                return resp.text, cons_url, "consolidated"
        except Exception as e:
            print(f"Error fetching {cons_url}: {e}")

        # Try Standalone
        std_url = f"https://www.screener.in/company/{sym}/"
        try:
            resp = requests.get(std_url, headers=headers, timeout=12)
            if resp.status_code == 200 and _is_usable_screener_html(resp.text):
                return resp.text, std_url, "standalone"
        except Exception as e:
            print(f"Error fetching {std_url}: {e}")

    # Try Search API fallback
    try:
        search_url = f"https://www.screener.in/api/company/search/?q={symbol}"
        search_resp = requests.get(search_url, headers=headers, timeout=8)
        if search_resp.status_code == 200:
            results = search_resp.json()
            if results and isinstance(results, list) and len(results) > 0:
                rel_url = results[0].get("url", "")
                if rel_url:
                    full_url = f"https://www.screener.in{rel_url}" if not rel_url.startswith("http") else rel_url
                    resp = requests.get(full_url, headers=headers, timeout=12)
                    if resp.status_code == 200 and _is_usable_screener_html(resp.text):
                        stype = "consolidated" if "consolidated" in full_url else "standalone"
                        return resp.text, full_url, stype
    except Exception as e:
        print(f"Error resolving search for {symbol}: {e}")

    return None

def hydrate_stock_data(cached_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Hydrates JSON cache dictionary into typed models and structures with dynamic re-classification."""
    from document_sourcing import classify_document_title
    data = dict(cached_dict)
    data["ratios"] = KeyRatios(**data["ratios"])
    data["quarters"] = FinancialStatement(**data["quarters"])
    data["profit_loss"] = FinancialStatement(**data["profit_loss"])
    data["balance_sheet"] = FinancialStatement(**data["balance_sheet"])
    
    # Filter out non-raw injected rows from cash flow statement
    cf_data = data["cash_flow"]
    if isinstance(cf_data, dict) and "rows" in cf_data:
        clean_cf_rows = [
            r for r in cf_data.get("rows", [])
            if clean_metric_name(r.get("metric", "") if isinstance(r, dict) else getattr(r, "metric", "")).lower().strip() not in NON_RAW_CASH_FLOW_METRICS
        ]
        cf_dict = dict(cf_data)
        cf_dict["rows"] = clean_cf_rows
        data["cash_flow"] = FinancialStatement(**cf_dict)
    elif hasattr(cf_data, "rows"):
        cf_data.rows = [
            r for r in cf_data.rows
            if clean_metric_name(getattr(r, "metric", "")).lower().strip() not in NON_RAW_CASH_FLOW_METRICS
        ]
        data["cash_flow"] = cf_data
    else:
        data["cash_flow"] = FinancialStatement(**cf_data)
        
    data["concall_insights"] = [ConcallInsight(**c) for c in data.get("concall_insights", [])]
    data["annual_report_insights"] = [AnnualReportInsight(**a) for a in data.get("annual_report_insights", [])]
    
    # Dynamically re-classify all documents to guarantee strict categorization
    raw_docs_dict = cached_dict.get("documents", {})
    all_raw_items: List[DocumentItem] = []
    if isinstance(raw_docs_dict, dict):
        for k in ["annual_reports", "concalls", "presentations", "material_announcements"]:
            for item in raw_docs_dict.get(k, []):
                all_raw_items.append(DocumentItem(**item) if isinstance(item, dict) else item)
                
    ar_list: List[DocumentItem] = []
    cc_list: List[DocumentItem] = []
    ppt_list: List[DocumentItem] = []
    ann_list: List[DocumentItem] = []
    seen_urls = set()
    
    company_name = data.get("name", "")
    for doc in all_raw_items:
        u = doc.url.strip()
        if u in seen_urls:
            continue
        seen_urls.add(u)
        
        dtype, ftitle = classify_document_title(doc.title, company_name, doc.period_or_date)
        doc.doc_type = dtype
        doc.title = ftitle
        if dtype == "annual_report":
            ar_list.append(doc)
        elif dtype == "concall_transcript":
            cc_list.append(doc)
        elif dtype == "presentation":
            ppt_list.append(doc)
        else:
            ann_list.append(doc)
            
    doc_links = DocumentLinks(
        annual_reports=ar_list[:3],
        concalls=cc_list[:6],
        presentations=ppt_list[:6],
        material_announcements=ann_list[:8]
    )
    data["documents"] = doc_links
    
    clean_sym = data.get("symbol", "").upper().strip()
    data["documents_checked_at"] = database.get_document_sources_checked_at(clean_sym) or cached_dict.get("documents_checked_at")
    return data

def serialize_stock_data(stock_data: Dict[str, Any]) -> Dict[str, Any]:
    """Serializes stock data dictionary to clean JSON-serializable structure."""
    docs = stock_data.get("documents")
    ratios = stock_data.get("ratios")
    quarters = stock_data.get("quarters")
    profit_loss = stock_data.get("profit_loss") or stock_data.get("profit_and_loss")
    balance_sheet = stock_data.get("balance_sheet")
    cash_flow = stock_data.get("cash_flow")
    
    return {
        "symbol": stock_data.get("symbol", ""),
        "name": stock_data.get("name", ""),
        "sector": stock_data.get("sector", "Unclassified"),
        "industry": stock_data.get("industry", "Unclassified"),
        "sub_industry": stock_data.get("sub_industry"),
        "source_sector": stock_data.get("source_sector"),
        "source_industry": stock_data.get("source_industry"),
        "source_sub_industry": stock_data.get("source_sub_industry"),
        "taxonomy_source": stock_data.get("taxonomy_source"),
        "about": stock_data.get("about", ""),
        "source_name": stock_data.get("source_name", "Screener.in"),
        "source_url": stock_data.get("source_url", ""),
        "statement_type": stock_data.get("statement_type", "consolidated"),
        "fetched_at": stock_data.get("fetched_at", ""),
        "documents_checked_at": stock_data.get("documents_checked_at") or database.get_document_sources_checked_at(stock_data.get("symbol", "")),
        "ratios": ratios.model_dump() if hasattr(ratios, "model_dump") else ratios,
        "quarters": quarters.model_dump() if hasattr(quarters, "model_dump") else quarters,
        "profit_loss": profit_loss.model_dump() if hasattr(profit_loss, "model_dump") else profit_loss,
        "balance_sheet": balance_sheet.model_dump() if hasattr(balance_sheet, "model_dump") else balance_sheet,
        "cash_flow": cash_flow.model_dump() if hasattr(cash_flow, "model_dump") else cash_flow,
        "concall_insights": [c.model_dump() if hasattr(c, "model_dump") else c for c in stock_data.get("concall_insights", [])],
        "annual_report_insights": [a.model_dump() if hasattr(a, "model_dump") else a for a in stock_data.get("annual_report_insights", [])],
        "documents": docs.model_dump() if hasattr(docs, "model_dump") else (docs or {})
    }

def fetch_stock_from_screener(symbol: str, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
    """
    Ingests exact raw financial statement data from Screener.in.
    Primary durable storage: SQLite stocks_cache table.
    Read priority:
    1. SQLite persisted stock cache (fresh within 12 hours) if force_refresh is False
    2. Legacy JSON cache (stocks_cache.json) if needed for backward compatibility
    3. Live Screener.in scrape
    4. Expired persisted cache (SQLite or JSON fallback if live scrape fails)
    
    SEED_STOCKS is NEVER used as a source of truth for financial statements.
    """
    clean_sym = symbol.upper().strip()
    os.makedirs(CACHE_DIR, exist_ok=True)
    
    cached_entry = None
    
    # 1. Primary Durable Cache: SQLite stocks_cache table
    try:
        sqlite_cached = database.get_stock_cache(clean_sym)
        if sqlite_cached and isinstance(sqlite_cached, dict):
            cached_entry = sqlite_cached
            if not force_refresh:
                fetched_at_str = cached_entry.get("fetched_at")
                if fetched_at_str:
                    try:
                        fetched_dt = datetime.fromisoformat(fetched_at_str.replace("Z", "+00:00"))
                        age_seconds = (datetime.now(timezone.utc) - fetched_dt).total_seconds()
                        if age_seconds < CACHE_TTL_SECONDS:
                            # Fresh SQLite cache hit!
                            return hydrate_stock_data(cached_entry)
                    except Exception:
                        pass
    except Exception as e:
        print(f"Notice: SQLite cache read note for {clean_sym}: {e}")

    # 2. Secondary / Legacy Cache: JSON stocks_cache.json
    if not cached_entry and os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                j_cache = json.load(f)
                if clean_sym in j_cache:
                    cached_entry = j_cache[clean_sym]
                    if not force_refresh:
                        fetched_at_str = cached_entry.get("fetched_at")
                        if fetched_at_str:
                            try:
                                fetched_dt = datetime.fromisoformat(fetched_at_str.replace("Z", "+00:00"))
                                age_seconds = (datetime.now(timezone.utc) - fetched_dt).total_seconds()
                                if age_seconds < CACHE_TTL_SECONDS:
                                    # Fresh JSON cache hit!
                                    return hydrate_stock_data(cached_entry)
                            except Exception:
                                pass
        except Exception as e:
            print(f"Error reading JSON cache for {clean_sym}: {e}")

    # 3. Live Scraper from Screener.in
    scrape_result = fetch_screener_html(clean_sym)
    if not scrape_result:
        # Fallback to expired cache if available
        if cached_entry:
            print(f"Warning: Live scrape failed for {clean_sym}. Using expired cache.")
            return hydrate_stock_data(cached_entry)
        return None

    html, source_url, statement_type = scrape_result
    soup = BeautifulSoup(html, "html.parser")
    
    # Company Name & About
    name_el = soup.find("h1") or soup.find("div", {"class": "show-from-tablet-landscape"})
    company_name = clean_metric_name(name_el.text) if name_el else clean_sym
    
    about_el = soup.find("div", {"class": "about"})
    about_text = clean_metric_name(about_el.text) if about_el else ""
    
    # Financial statements parsed exactly from live Screener tables
    quarters = parse_screener_table(soup, "quarters")
    pl = parse_screener_table(soup, "profit-loss")
    bs = parse_screener_table(soup, "balance-sheet")
    cf = parse_screener_table(soup, "cash-flow")
    ratios = parse_screener_ratios(soup)
    documents = parse_screener_documents(soup, clean_sym, source_url)
    
    if not quarters or not pl or not bs or not cf:
        print(f"Error: Incomplete financial statements parsed from Screener for {clean_sym}")
        if cached_entry:
            return hydrate_stock_data(cached_entry)
        return None

    source_sector, source_industry, source_sub_industry = parse_screener_taxonomy_metadata(soup)
    registry = database.get_company_by_symbol(clean_sym) or {}
    sector = source_sector or registry.get("sector") or "Unclassified"
    industry = source_industry or registry.get("industry") or "Unclassified"
    taxonomy_source = "screener_metadata" if (source_sector or source_industry or source_sub_industry) else (registry.get("source") or "unknown")
    if not about_text:
        about_text = f"{company_name} is a listed company in the Indian stock market."

    concall_insights: List[ConcallInsight] = []
    ar_insights: List[AnnualReportInsight] = []
    fetched_at = datetime.now(timezone.utc).isoformat()
    
    stock_data = {
        "symbol": clean_sym,
        "name": company_name,
        "sector": sector,
        "industry": industry,
        "source_sector": source_sector or registry.get("sector"),
        "source_industry": source_industry or registry.get("industry"),
        "source_sub_industry": source_sub_industry,
        "taxonomy_source": taxonomy_source,
        "about": about_text,
        "source_name": "Screener.in",
        "source_url": source_url,
        "statement_type": statement_type,
        "fetched_at": fetched_at,
        "ratios": ratios,
        "quarters": quarters,
        "profit_loss": pl,
        "balance_sheet": bs,
        "cash_flow": cf,
        "concall_insights": concall_insights,
        "annual_report_insights": ar_insights,
        "documents": documents,
        "documents_checked_at": getattr(documents, "checked_at", None) or database.get_document_sources_checked_at(clean_sym) or None
    }
    
    # Save to Durable Cache (SQLite primary, JSON secondary)
    serialized = serialize_stock_data(stock_data)
    try:
        database.save_stock_cache(clean_sym, company_name, sector, industry, serialized)
    except Exception as e_db:
        print(f"Notice: Database stock cache save notice for {clean_sym}: {e_db}")
        
    try:
        cache_data = {}
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, "r") as f:
                cache_data = json.load(f)
        cache_data[clean_sym] = serialized
        with open(CACHE_FILE, "w") as f:
            json.dump(cache_data, f, indent=2)
    except Exception as e:
        print(f"Error updating JSON cache for {clean_sym}: {e}")
        
    return stock_data
