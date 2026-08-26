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
from data_seed import COMPANY_METADATA

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
            
        values: Dict[str, Optional[float]] = {}
        for idx, td in enumerate(td_tags[1:]):
            if idx < len(periods):
                p = periods[idx]
                values[p] = parse_num(td.text)
                
        rows.append(FinancialRow(metric=metric_name, values=values))
        
    return FinancialStatement(periods=periods, rows=rows)

def parse_screener_ratios(soup: BeautifulSoup) -> KeyRatios:
    ratios_dict = {
        "market_cap_cr": 0.0,
        "current_price": 0.0,
        "high_low": "",
        "stock_pe": 0.0,
        "book_value": 0.0,
        "dividend_yield_pct": 0.0,
        "roce_pct": 0.0,
        "roe_pct": 0.0,
        "face_value": 1.0,
        "debt_to_equity": 0.0,
        "interest_coverage": 0.0,
        "fcf_yield_pct": 0.0,
        "sales_growth_3yr_cagr": 0.0,
        "profit_growth_3yr_cagr": 0.0
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
                    ratios_dict["market_cap_cr"] = parse_num(val_text) or 0.0
                elif "current price" in name:
                    ratios_dict["current_price"] = parse_num(val_text) or 0.0
                elif "high / low" in name:
                    ratios_dict["high_low"] = val_text
                elif "stock p/e" in name:
                    ratios_dict["stock_pe"] = parse_num(val_text) or 0.0
                elif "book value" in name:
                    ratios_dict["book_value"] = parse_num(val_text) or 0.0
                elif "dividend yield" in name:
                    ratios_dict["dividend_yield_pct"] = parse_num(val_text) or 0.0
                elif "roce" in name:
                    ratios_dict["roce_pct"] = parse_num(val_text) or 0.0
                elif "roe" in name:
                    ratios_dict["roe_pct"] = parse_num(val_text) or 0.0
                elif "face value" in name:
                    ratios_dict["face_value"] = parse_num(val_text) or 1.0
                elif "debt to equity" in name:
                    ratios_dict["debt_to_equity"] = parse_num(val_text) or 0.0
                    
    return KeyRatios(**ratios_dict)

from document_sourcing import execute_document_sourcing_waterfall

def parse_screener_documents(soup: BeautifulSoup, symbol: str, source_url: str, company_name: str = "") -> DocumentLinks:
    return execute_document_sourcing_waterfall(symbol, company_name or symbol, screener_soup=soup)

def fetch_screener_html(symbol: str) -> Optional[Tuple[str, str, str]]:
    """
    Fetches the live HTML from Screener.in.
    Returns (html_content, source_url, statement_type) or None.
    Preference:
    1. https://www.screener.in/company/{symbol}/consolidated/
    2. https://www.screener.in/company/{symbol}/
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
            if resp.status_code == 200 and len(resp.text) > 3000 and "quarters" in resp.text:
                return resp.text, cons_url, "consolidated"
        except Exception as e:
            print(f"Error fetching {cons_url}: {e}")

        # Try Standalone
        std_url = f"https://www.screener.in/company/{sym}/"
        try:
            resp = requests.get(std_url, headers=headers, timeout=12)
            if resp.status_code == 200 and len(resp.text) > 3000 and "quarters" in resp.text:
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
                    if resp.status_code == 200 and len(resp.text) > 3000:
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
    data["cash_flow"] = FinancialStatement(**data["cash_flow"])
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
    
    # Sync re-classified documents into SQLite source_documents index
    clean_sym = data.get("symbol", "").upper().strip()
    if clean_sym:
        all_docs = ar_list + cc_list + ppt_list + ann_list
        if all_docs:
            try:
                database.save_source_documents(clean_sym, all_docs)
            except Exception:
                pass
                
    return data

def serialize_stock_data(stock_data: Dict[str, Any]) -> Dict[str, Any]:
    """Serializes stock data dictionary to clean JSON-serializable structure."""
    return {
        "symbol": stock_data["symbol"],
        "name": stock_data["name"],
        "sector": stock_data["sector"],
        "industry": stock_data["industry"],
        "about": stock_data["about"],
        "source_name": stock_data.get("source_name", "Screener.in"),
        "source_url": stock_data.get("source_url", ""),
        "statement_type": stock_data.get("statement_type", "consolidated"),
        "fetched_at": stock_data.get("fetched_at", ""),
        "ratios": stock_data["ratios"].model_dump() if hasattr(stock_data["ratios"], "model_dump") else stock_data["ratios"],
        "quarters": stock_data["quarters"].model_dump() if hasattr(stock_data["quarters"], "model_dump") else stock_data["quarters"],
        "profit_loss": stock_data["profit_loss"].model_dump() if hasattr(stock_data["profit_loss"], "model_dump") else stock_data["profit_loss"],
        "balance_sheet": stock_data["balance_sheet"].model_dump() if hasattr(stock_data["balance_sheet"], "model_dump") else stock_data["balance_sheet"],
        "cash_flow": stock_data["cash_flow"].model_dump() if hasattr(stock_data["cash_flow"], "model_dump") else stock_data["cash_flow"],
        "concall_insights": [c.model_dump() if hasattr(c, "model_dump") else c for c in stock_data.get("concall_insights", [])],
        "annual_report_insights": [a.model_dump() if hasattr(a, "model_dump") else a for a in stock_data.get("annual_report_insights", [])],
        "documents": stock_data["documents"].model_dump() if hasattr(stock_data["documents"], "model_dump") else stock_data["documents"]
    }

def fetch_stock_from_screener(symbol: str, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
    """
    Ingests exact raw financial statement data from Screener.in.
    Priority:
    1. Valid fresh cache (within 12 hours) if force_refresh is False
    2. Live Screener.in scrape
    3. Expired cache (as fallback if live scrape fails)
    
    SEED_STOCKS is NEVER used as a source of truth for financial statements.
    """
    clean_sym = symbol.upper().strip()
    os.makedirs(CACHE_DIR, exist_ok=True)
    
    cached_entry = None
    # 1. Check local cache freshness
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                cache = json.load(f)
                if clean_sym in cache:
                    cached_entry = cache[clean_sym]
                    if not force_refresh:
                        fetched_at_str = cached_entry.get("fetched_at")
                        if fetched_at_str:
                            try:
                                fetched_dt = datetime.fromisoformat(fetched_at_str.replace("Z", "+00:00"))
                                age_seconds = (datetime.now(timezone.utc) - fetched_dt).total_seconds()
                                if age_seconds < CACHE_TTL_SECONDS:
                                    # Fresh cache hit!
                                    return hydrate_stock_data(cached_entry)
                            except Exception:
                                pass
        except Exception as e:
            print(f"Error reading cache for {clean_sym}: {e}")

    # 2. Live Scraper from Screener.in
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

    # Metadata enrichment from static COMPANY_METADATA if available
    meta = COMPANY_METADATA.get(clean_sym, {})
    sector = meta.get("sector", "Broad Market")
    industry = meta.get("industry", "Indian Equities")
    if not about_text and "about" in meta:
        about_text = meta["about"]
    elif not about_text:
        about_text = f"{company_name} is a listed company in the Indian stock market."

    concall_insights: List[ConcallInsight] = []
    ar_insights: List[AnnualReportInsight] = []
    fetched_at = datetime.now(timezone.utc).isoformat()
    
    stock_data = {
        "symbol": clean_sym,
        "name": company_name,
        "sector": sector,
        "industry": industry,
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
        "documents": documents
    }
    
    # Save to Cache
    try:
        cache_data = {}
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, "r") as f:
                cache_data = json.load(f)
                
        cache_data[clean_sym] = serialize_stock_data(stock_data)
        with open(CACHE_FILE, "w") as f:
            json.dump(cache_data, f, indent=2)
    except Exception as e:
        print(f"Error updating cache for {clean_sym}: {e}")
        
    return stock_data
