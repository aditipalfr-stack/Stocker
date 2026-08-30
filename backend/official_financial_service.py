"""
=============================================================================
Stocker Official Financial Verification Engine (Phase B)
=============================================================================
Provides deterministic normalization, authoritative metric comparison,
and provenance tracking between Screener.in standardized statements
and official corporate filings / exchange outcomes (NSE / BSE / IR).

Key Responsibilities:
1. Real Official Source Discovery & Fetch Adapters
2. Strict Scope Alignment (Consolidated vs Standalone -> NOT_COMPARABLE)
3. Strict Period Alignment (Quarter / FY Mismatch -> NOT_COMPARABLE)
4. Conservative Metric Mapping (No aggressive or ambiguous merging)
5. Deterministic Unit & Scale Standardization (₹ Lakh / ₹ Million -> ₹ Cr)
6. Deterministic Tolerance & Discrepancy Evaluation
7. Clean Unavailable Handling (OFFICIAL_SOURCE_MISSING when official data absent)
=============================================================================
"""

import re
import math
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

import database
from authoritative_identity import resolve_and_upgrade_company_identity, lookup_authoritative_identity

# Official Exchange Corporate Filing Endpoints
NSE_CORPORATE_ANNOUNCEMENTS_URL = "https://www.nseindia.com/api/corporate-announcements?index=equities&symbol={symbol}"
BSE_CORPORATE_ANNOUNCEMENTS_URL = "https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w?strCat=-1&strPrevDate=&strScrip={bse_code}"

EXCHANGE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/"
}

# Supported Canonical Metrics
CANONICAL_METRICS = ["REVENUE", "OPERATING_PROFIT", "PBT", "PAT", "EPS"]

# Conservative Metric Mapping Dictionary
# Only line items that are unambiguously equivalent are mapped to canonical metrics.
CONSERVATIVE_METRIC_MAP: Dict[str, str] = {
    # Revenue / Sales
    "revenue from operations": "REVENUE",
    "net sales": "REVENUE",
    "sales": "REVENUE",
    "revenue": "REVENUE",
    "total income from operations": "REVENUE",
    "income from operations": "REVENUE",
    
    # Operating Profit / EBITDA (Explicit equivalence only)
    "operating profit": "OPERATING_PROFIT",
    "operating profit (ebitda)": "OPERATING_PROFIT",
    "ebitda": "OPERATING_PROFIT",
    "pbitda": "OPERATING_PROFIT",
    
    # PBT
    "profit before tax": "PBT",
    "pbt": "PBT",
    "profit before exceptional items and tax": "PBT",
    "profit before tax and exceptional items": "PBT",
    
    # PAT / Net Profit
    "net profit": "PAT",
    "profit after tax": "PAT",
    "pat": "PAT",
    "profit for the period": "PAT",
    "net profit for the period": "PAT",
    
    # EPS
    "eps in rs": "EPS",
    "basic eps": "EPS",
    "diluted eps": "EPS",
    "eps": "EPS",
    "earnings per share": "EPS"
}

# Ambiguous line items that must NOT be blindly mapped to canonical metrics
AMBIGUOUS_METRIC_KEYWORDS = [
    "ebit", "pbit", "operating profit before depreciation",
    "profit attributable to non-controlling", "exceptional items"
]

def normalize_metric_name(raw_metric: str) -> Optional[str]:
    """
    Conservatively maps raw filing metric names to canonical metric keys.
    Returns None if metric is ambiguous or incompatible.
    """
    if not raw_metric:
        return None
    clean = re.sub(r"[\(\)\[\],.:]", " ", raw_metric.lower()).strip()
    clean = re.sub(r"\s+", " ", clean)
    
    # Reject known ambiguous terms if not accompanied by explicit EBITDA/OP labels
    for amb in AMBIGUOUS_METRIC_KEYWORDS:
        if clean == amb or (amb in clean and "ebitda" not in clean and "operating profit" not in clean):
            return None
            
    # Direct lookup
    if clean in CONSERVATIVE_METRIC_MAP:
        return CONSERVATIVE_METRIC_MAP[clean]
        
    # Substring matching for exact known aliases
    for alias, canon in CONSERVATIVE_METRIC_MAP.items():
        if alias == clean or f" {alias} " in f" {clean} ":
            return canon
            
    return None

def normalize_period(period_str: str) -> Tuple[str, str]:
    """
    Normalizes diverse reporting period strings into canonical sortable keys.
    Examples:
    - 'Jun 2026', 'Q1 FY27', 'Quarter ended 30 June 2026', '30-Jun-2026' -> ('Jun 2026', '2026-Q1')
    - 'Sep 2026', 'Q2 FY27', 'Quarter ended 30 September 2026' -> ('Sep 2026', '2026-Q2')
    - 'Dec 2025', 'Q3 FY26', 'Quarter ended 31 December 2025' -> ('Dec 2025', '2025-Q3')
    - 'Mar 2026', 'Q4 FY26', 'Quarter ended 31 March 2026' -> ('Mar 2026', '2026-Q4')
    - 'FY26', 'Year ended 31 March 2026', '12M FY26' -> ('FY26', '2026-FY')
    """
    if not period_str:
        return ("", "")
        
    p = period_str.strip()
    p_lower = p.lower()
    
    # 1. Full Year / Annual phrases
    if any(term in p_lower for term in ["year ended", "full year", "12m", "annual", "full-year"]) or p_lower.startswith("fy"):
        yr_match = re.search(r"(\d{4})", p_lower)
        if yr_match:
            fy_yr = int(yr_match.group(1))
            return (f"FY{str(fy_yr)[-2:]}", f"{fy_yr}-FY")
        fy_2d = re.search(r"fy\s*(\d{2})", p_lower)
        if fy_2d:
            fy_yr = int(fy_2d.group(1)) + 2000
            return (f"FY{str(fy_yr)[-2:]}", f"{fy_yr}-FY")

    # 2. Fiscal Quarter notation (e.g. 'Q1 FY27', 'Q1FY27')
    q_fy_match = re.search(r"q([1-4])\s*(?:fy)?\s*(\d{2,4})", p_lower)
    if q_fy_match:
        q_num = int(q_fy_match.group(1))
        raw_yr = int(q_fy_match.group(2))
        fy_yr = raw_yr + 2000 if raw_yr < 100 else raw_yr
        
        if q_num == 1:
            cal_yr = fy_yr - 1
            return (f"Jun {cal_yr}", f"{cal_yr}-Q1")
        elif q_num == 2:
            cal_yr = fy_yr - 1
            return (f"Sep {cal_yr}", f"{cal_yr}-Q2")
        elif q_num == 3:
            cal_yr = fy_yr - 1
            return (f"Dec {cal_yr}", f"{cal_yr}-Q3")
        elif q_num == 4:
            cal_yr = fy_yr
            return (f"Mar {cal_yr}", f"{cal_yr}-Q4")

    # 3. Standard Month Year (e.g. 'Jun 2026', 'Quarter ended 30 June 2026')
    month_match = re.search(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s*[-/,]?\s*(\d{4})\b", p_lower)
    if month_match:
        m = month_match.group(1)[:3].title()
        yr = int(month_match.group(2))
        
        q_map = {
            "Jun": ("Jun " + str(yr), f"{yr}-Q1"),
            "Sep": ("Sep " + str(yr), f"{yr}-Q2"),
            "Dec": ("Dec " + str(yr), f"{yr}-Q3"),
            "Mar": ("Mar " + str(yr), f"{yr}-Q4"),
        }
        if m in q_map:
            return q_map[m]
        return (f"{m} {yr}", f"{yr}-{m.upper()}")
        
    return (p, p.upper())

def normalize_numeric_scale(value: float, raw_unit: Optional[str] = None) -> float:
    """Converts reported financial figures to normalized ₹ Crore (Cr)."""
    if value is None or math.isnan(value):
        return 0.0
        
    if not raw_unit:
        return float(value)
        
    u = raw_unit.lower().strip()
    if "lakh" in u:
        return round(float(value) / 100.0, 4)
    elif "million" in u or "mn" in u:
        return round(float(value) / 10.0, 4)
    elif "billion" in u or "bn" in u:
        return round(float(value) * 100.0, 4)
    elif "rupee" in u and "crore" not in u and "lakh" not in u:
        return round(float(value) / 10000000.0, 4)
        
    return float(value)

def compare_financial_metric(
    screener_val: Optional[float],
    official_val: Optional[float],
    canonical_metric: str,
    screener_scope: str = "Consolidated",
    official_scope: str = "Consolidated",
    screener_period_key: str = "",
    official_period_key: str = ""
) -> Dict[str, Any]:
    """
    Evaluates Screener.in value against Official filing value with deterministic rules:
    - Scope alignment (Consolidated vs Standalone)
    - Period alignment (e.g. 2026-Q1 vs 2026-Q2)
    - Mathematical tolerance: Δ <= max(abs_tolerance, official_value * pct_tolerance)
      - abs_tolerance: 1.0 (₹1 Cr) for financial totals, 0.05 for EPS
      - pct_tolerance: 0.5% (0.005) for financial totals, 1.0% for EPS
    """
    norm_scr_scope = (screener_scope or "Consolidated").capitalize().strip()
    norm_off_scope = (official_scope or "Consolidated").capitalize().strip()
    
    # 1. Scope Mismatch -> NOT_COMPARABLE
    if norm_scr_scope != norm_off_scope:
        return {
            "status": "NOT_COMPARABLE",
            "variance_abs": None,
            "variance_pct": None,
            "tolerance_used": None,
            "notes": f"Scope mismatch: Screener is {norm_scr_scope} while official filing is {norm_off_scope}."
        }
        
    # 2. Period Mismatch -> NOT_COMPARABLE
    if screener_period_key and official_period_key and screener_period_key != official_period_key:
        return {
            "status": "NOT_COMPARABLE",
            "variance_abs": None,
            "variance_pct": None,
            "tolerance_used": None,
            "notes": f"Period mismatch: Screener period ({screener_period_key}) does not align with official filing ({official_period_key})."
        }
        
    # 3. Missing Value checks
    if screener_val is None and official_val is None:
        return {
            "status": "INSUFFICIENT_EVIDENCE",
            "variance_abs": None,
            "variance_pct": None,
            "tolerance_used": None,
            "notes": "Both Screener and Official figures are missing."
        }
    if screener_val is None:
        return {
            "status": "SCREENER_VALUE_MISSING",
            "variance_abs": None,
            "variance_pct": None,
            "tolerance_used": None,
            "notes": "Metric exists in official filing but is absent from Screener statement."
        }
    if official_val is None:
        return {
            "status": "OFFICIAL_SOURCE_MISSING",
            "variance_abs": None,
            "variance_pct": None,
            "tolerance_used": None,
            "notes": "Metric reported in Screener statement but missing from official filing."
        }
        
    # 4. Tolerance calculation
    if canonical_metric == "EPS":
        abs_tolerance = 0.05
        pct_tolerance = 0.01 # 1% for EPS
    else:
        abs_tolerance = 1.0 # ₹1 Cr absolute tolerance
        pct_tolerance = 0.005 # 0.5% relative tolerance
        
    tolerance_allowed = max(abs_tolerance, abs(official_val) * pct_tolerance)
    variance_abs = round(abs(screener_val - official_val), 4)
    variance_pct = round((variance_abs / abs(official_val)) * 100, 2) if official_val != 0 else 0.0
    
    # 5. Verification Status
    if variance_abs <= tolerance_allowed:
        unit_label = "₹" if canonical_metric == "EPS" else "₹ Cr"
        return {
            "status": "VERIFIED",
            "variance_abs": variance_abs,
            "variance_pct": variance_pct,
            "tolerance_used": round(tolerance_allowed, 4),
            "notes": f"Verified: Screener figure aligns with official filing (variance of {variance_abs} {unit_label} is within allowed tolerance of {round(tolerance_allowed, 2)} {unit_label})."
        }
    else:
        unit_label = "₹" if canonical_metric == "EPS" else "₹ Cr"
        return {
            "status": "DISCREPANCY",
            "variance_abs": variance_abs,
            "variance_pct": variance_pct,
            "tolerance_used": round(tolerance_allowed, 4),
            "notes": f"Discrepancy detected: Screener value ({screener_val}) differs from official reported filing ({official_val}) by {variance_abs} {unit_label} ({variance_pct}%), exceeding tolerance limit of {round(tolerance_allowed, 2)} {unit_label}."
        }

# =============================================================================
# REAL OFFICIAL FINANCIAL RESULT DISCOVERY & FETCH ADAPTERS
# =============================================================================

def discover_official_financial_results(
    symbol: str,
    timeout: int = 5
) -> List[Dict[str, Any]]:
    """
    Discovers latest official financial outcome filings from exchange repositories.
    Returns structured filing candidate references:
    - document_title
    - document_type
    - reporting_period
    - filing_date
    - scope
    - source_name
    - source_url
    - actual_source_url
    - retrieved_at
    """
    clean_sym = symbol.strip().upper()
    now_iso = datetime.now(timezone.utc).isoformat()
    discovered_filings: List[Dict[str, Any]] = []
    
    # Query official NSE corporate announcements endpoint
    url = NSE_CORPORATE_ANNOUNCEMENTS_URL.format(symbol=clean_sym)
    try:
        req = urllib.request.Request(url, headers=EXCHANGE_HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
            
            items = data if isinstance(data, list) else data.get("data", [])
            for item in items:
                desc = item.get("desc", "") or item.get("subject", "") or ""
                # Look for financial result outcomes
                if any(kw in desc.lower() for kw in ["financial results", "outcome of board meeting", "financial statement"]):
                    att_url = item.get("attmnt", "") or item.get("attachment", "") or ""
                    full_url = f"https://nsearchives.nseindia.com/corporate/{att_url}" if att_url and not att_url.startswith("http") else att_url
                    
                    discovered_filings.append({
                        "symbol": clean_sym,
                        "document_title": desc,
                        "document_type": "official_financial_result",
                        "reporting_period": item.get("period", ""),
                        "filing_date": item.get("date", ""),
                        "scope": "Consolidated" if "consolidated" in desc.lower() else "Standalone",
                        "source_name": "NSE Corporate Filing",
                        "source_url": full_url or url,
                        "actual_source_url": full_url or url,
                        "retrieved_at": now_iso
                    })
    except Exception:
        # If exchange network fails, return empty list safely
        pass
        
    return discovered_filings

def fetch_official_financial_result(
    symbol: str,
    filing_ref: Dict[str, Any],
    timeout: int = 5
) -> Optional[Dict[str, Any]]:
    """
    Fetches and parses structured financial results from official filing candidate.
    Returns structured filing document containing machine-readable financial table.
    """
    if not filing_ref:
        return None
        
    # If filing already contains extracted table rows (from structured API / mock)
    if "financial_table" in filing_ref or "rows" in filing_ref:
        return filing_ref
        
    # Real network retrieval & structured table parsing from official source URL
    source_url = filing_ref.get("source_url") or filing_ref.get("actual_source_url")
    if not source_url:
        return None
        
    try:
        req = urllib.request.Request(source_url, headers=EXCHANGE_HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            content_type = response.headers.get("Content-Type", "")
            raw_data = response.read()
            
            # If JSON result outcome
            if "application/json" in content_type:
                parsed_json = json.loads(raw_data.decode("utf-8"))
                filing_doc = dict(filing_ref)
                filing_doc["financial_table"] = parsed_json.get("rows", [])
                return filing_doc
    except Exception:
        pass
        
    return None

def extract_official_filing_metrics(
    symbol: str,
    filing_doc: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Extracts structured financial result line items from official filing payload.
    """
    extracted_items = []
    scope = filing_doc.get("scope", "Consolidated")
    period_raw = filing_doc.get("reporting_period", "")
    disp_period, canon_period = normalize_period(period_raw)
    raw_unit = filing_doc.get("unit", "₹ Cr")
    source_url = filing_doc.get("source_url") or filing_doc.get("actual_source_url")
    source_name = filing_doc.get("source_name", "NSE Filing")
    doc_id = filing_doc.get("document_id") or filing_doc.get("document_title")
    
    line_items = filing_doc.get("financial_table") or filing_doc.get("rows") or []
    for row in line_items:
        raw_name = row.get("metric") or row.get("line_item") or row.get("name") or ""
        canon_m = normalize_metric_name(raw_name)
        if not canon_m:
            continue
            
        raw_val = row.get("value")
        if raw_val is None:
            continue
            
        try:
            num_val = float(raw_val)
            norm_val = normalize_numeric_scale(num_val, raw_unit) if canon_m != "EPS" else float(num_val)
            
            extracted_items.append({
                "metric_name": raw_name,
                "canonical_metric": canon_m,
                "period": disp_period,
                "canonical_period": canon_period,
                "scope": scope,
                "official_value": norm_val,
                "unit": "₹ / Share" if canon_m == "EPS" else "₹ Cr",
                "currency": "INR",
                "official_source_url": source_url,
                "official_source_name": source_name,
                "official_document_id": doc_id
            })
        except Exception:
            continue
            
    return extracted_items

# =============================================================================
# MASTER FINANCIAL VERIFICATION PIPELINE
# =============================================================================

def run_official_financial_verification(
    symbol: str,
    screener_stock_data: Optional[Dict[str, Any]] = None,
    official_filing_docs: Optional[List[Dict[str, Any]]] = None,
    use_live_exchange: bool = True
) -> Dict[str, Any]:
    """
    Master Financial Verification Pipeline:
    1. Upgrades authoritative identity from official exchange sources.
    2. Gathers Screener statements preserving actual source scope and periods.
    3. Discovers and fetches official filing reports from official exchange endpoints.
    4. Deterministically compares every key reported figure against Screener.
    5. If official data cannot be obtained, returns OFFICIAL_SOURCE_MISSING (no fake verified).
    6. Persists verification records and returns aggregated summary.
    """
    clean_sym = symbol.strip().upper()
    now_iso = datetime.now(timezone.utc).isoformat()
    
    # 1. Authoritative Identity Resolution & Upgrade
    resolve_and_upgrade_company_identity(clean_sym, use_live_exchange=use_live_exchange)
    
    # 2. Extract Screener reported metrics with actual statement scope
    # screener_metrics: canon_metric -> list of dicts with {"value", "scope", "period_display", "canonical_period"}
    screener_metrics: Dict[str, List[Dict[str, Any]]] = {}
    screener_source_url = ""
    
    if screener_stock_data:
        screener_source_url = screener_stock_data.get("source_url", "")
        scr_statement_scope = screener_stock_data.get("statement_type", "consolidated").capitalize()
        
        # Quarterly statements
        quarters = screener_stock_data.get("quarters", {})
        for row in quarters.get("rows", []):
            m_name = row.get("metric", "")
            canon_m = normalize_metric_name(m_name)
            if not canon_m:
                continue
            values = row.get("values", {})
            for p_str, val in values.items():
                if val is not None:
                    disp_p, canon_p = normalize_period(p_str)
                    if canon_p:
                        try:
                            if canon_m not in screener_metrics:
                                screener_metrics[canon_m] = []
                            screener_metrics[canon_m].append({
                                "value": float(val),
                                "scope": scr_statement_scope,
                                "period_display": disp_p,
                                "canonical_period": canon_p
                            })
                        except Exception:
                            pass
                            
        # Annual Profit & Loss statements
        pl = screener_stock_data.get("profit_loss", {})
        for row in pl.get("rows", []):
            m_name = row.get("metric", "")
            canon_m = normalize_metric_name(m_name)
            if not canon_m:
                continue
            values = row.get("values", {})
            for p_str, val in values.items():
                if val is not None:
                    disp_p, canon_p = normalize_period("FY" + p_str.split()[-1][-2:] if len(p_str.split()) > 1 else p_str)
                    if canon_p:
                        try:
                            if canon_m not in screener_metrics:
                                screener_metrics[canon_m] = []
                            screener_metrics[canon_m].append({
                                "value": float(val),
                                "scope": scr_statement_scope,
                                "period_display": disp_p,
                                "canonical_period": canon_p
                            })
                        except Exception:
                            pass

    # 3. Discover & Fetch Official Result Filings
    official_filings_to_process = list(official_filing_docs or [])
    if not official_filings_to_process and use_live_exchange:
        discovered = discover_official_financial_results(clean_sym)
        for disc in discovered:
            fetched_doc = fetch_official_financial_result(clean_sym, disc)
            if fetched_doc:
                official_filings_to_process.append(fetched_doc)
                
    # 4. If NO official filings can be obtained: Return OFFICIAL_SOURCE_MISSING
    if not official_filings_to_process:
        summary = database.get_financial_verification_summary(clean_sym)
        summary["overall_status"] = "OFFICIAL_SOURCE_MISSING"
        summary["unavailable_reason"] = "Official exchange financial results or filings could not be retrieved from NSE/BSE."
        return {
            "symbol": clean_sym,
            "summary": summary,
            "records": []
        }
        
    # 5. Extract line items from official filings
    official_items: List[Dict[str, Any]] = []
    for fdoc in official_filings_to_process:
        extracted = extract_official_filing_metrics(clean_sym, fdoc)
        official_items.extend(extracted)
        
    if not official_items:
        summary = database.get_financial_verification_summary(clean_sym)
        summary["overall_status"] = "OFFICIAL_SOURCE_MISSING"
        summary["unavailable_reason"] = "Official filing was retrieved but contained no compatible financial statement tables."
        return {
            "symbol": clean_sym,
            "summary": summary,
            "records": []
        }

    # 6. Perform deterministic metric comparison
    verification_records: List[Dict[str, Any]] = []
    for off in official_items:
        off_canon_p = off["canonical_period"]
        off_canon_m = off["canonical_metric"]
        off_scope = off["scope"]
        off_val = off["official_value"]
        
        # Find matching Screener candidates for this metric
        scr_candidates = screener_metrics.get(off_canon_m, [])
        
        # Find exact period match in Screener
        matching_scr = None
        for cand in scr_candidates:
            if cand["canonical_period"] == off_canon_p:
                matching_scr = cand
                break
                
        # If no exact period match, pick nearest available for period mismatch demonstration
        if not matching_scr and scr_candidates:
            matching_scr = scr_candidates[0]
            
        scr_val = matching_scr["value"] if matching_scr else None
        scr_scope = matching_scr["scope"] if matching_scr else "Consolidated"
        scr_canon_p = matching_scr["canonical_period"] if matching_scr else off_canon_p
        
        comp_res = compare_financial_metric(
            screener_val=scr_val,
            official_val=off_val,
            canonical_metric=off_canon_m,
            screener_scope=scr_scope,
            official_scope=off_scope,
            screener_period_key=scr_canon_p,
            official_period_key=off_canon_p
        )
        
        rec = {
            "symbol": clean_sym,
            "metric_name": off["metric_name"],
            "canonical_metric": off_canon_m,
            "period": off["period"],
            "canonical_period": off_canon_p,
            "scope": off_scope,
            "screener_value": scr_val,
            "official_value": off_val,
            "variance_abs": comp_res["variance_abs"],
            "variance_pct": comp_res["variance_pct"],
            "unit": off["unit"],
            "currency": "INR",
            "status": comp_res["status"],
            "tolerance_used": comp_res["tolerance_used"],
            "screener_source_url": screener_source_url,
            "official_source_url": off.get("official_source_url"),
            "official_source_name": off.get("official_source_name", "NSE Filing"),
            "official_document_id": off.get("official_document_id"),
            "notes": comp_res["notes"],
            "verified_at": now_iso
        }
        verification_records.append(rec)
        
    # 7. Persist verification records to database
    if verification_records:
        database.save_financial_verification_records(verification_records)
        
    # 8. Retrieve updated aggregated summary
    summary = database.get_financial_verification_summary(clean_sym)
    return {
        "symbol": clean_sym,
        "summary": summary,
        "records": verification_records
    }
