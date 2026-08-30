"""
=============================================================================
Stocker Official Financial Verification Engine (Phase B)
=============================================================================
Provides deterministic normalization, authoritative metric comparison,
and provenance tracking between Screener.in standardized statements
and official corporate filings / exchange outcomes (NSE / BSE / IR).

Key Responsibilities:
1. Period Normalization (e.g. 'Jun 2026' == 'Q1 FY27' == '30-Jun-2026' -> '2026-Q1')
2. Scope Alignment (Consolidated vs Standalone)
3. Unit & Scale Standardization (₹ Lakh / ₹ Million / ₹ Cr -> ₹ Cr)
4. Metric Alias Mapping (Revenue, Operating Profit, PBT, PAT, EPS)
5. Deterministic Tolerance & Discrepancy Evaluation
6. Complete Provenance & Persistence
=============================================================================
"""

import re
import math
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

import database
from authoritative_identity import resolve_and_upgrade_company_identity, lookup_authoritative_exchange_identity

# Canonical metric definitions supported in Phase B
CANONICAL_METRICS = ["REVENUE", "OPERATING_PROFIT", "PBT", "PAT", "EPS"]

# Canonical metric mapping dictionary
METRIC_ALIAS_MAP: Dict[str, str] = {
    # Revenue / Sales
    "sales": "REVENUE",
    "revenue": "REVENUE",
    "revenue from operations": "REVENUE",
    "net sales": "REVENUE",
    "total income from operations": "REVENUE",
    "income from operations": "REVENUE",
    
    # Operating Profit / EBITDA
    "operating profit": "OPERATING_PROFIT",
    "operating profit (ebitda)": "OPERATING_PROFIT",
    "ebitda": "OPERATING_PROFIT",
    "pbitda": "OPERATING_PROFIT",
    "operating profit before depreciation": "OPERATING_PROFIT",
    
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
    "profit attributable to owners": "PAT",
    
    # EPS
    "eps in rs": "EPS",
    "basic eps": "EPS",
    "diluted eps": "EPS",
    "eps": "EPS",
    "earnings per share": "EPS"
}

def normalize_period(period_str: str) -> Tuple[str, str]:
    """
    Normalizes diverse reporting period strings into canonical sortable keys.
    Examples:
    - 'Jun 2026', 'Q1 FY27', 'Quarter ended 30 June 2026', '30-Jun-2026' -> ('Jun 2026', '2026-Q1')
    - 'Sep 2026', 'Q2 FY27', 'Quarter ended 30 September 2026' -> ('Sep 2026', '2026-Q2')
    - 'Dec 2025', 'Q3 FY26', 'Quarter ended 31 December 2025' -> ('Dec 2025', '2025-Q3')
    - 'Mar 2026', 'Q4 FY26', 'Quarter ended 31 March 2026' -> ('Mar 2026', '2026-Q4')
    - 'FY26', 'Year ended 31 March 2026', '12M FY26' -> ('FY26', '2026-FY')
    
    Returns:
        (display_period, canonical_period_key)
    """
    if not period_str:
        return ("", "")
        
    p = period_str.strip()
    p_lower = p.lower()
    
    # 1. Full Year / Annual phrases (e.g. 'Year ended 31 March 2026', 'FY26', '12M FY26', 'FY 2026')
    if any(term in p_lower for term in ["year ended", "full year", "12m", "annual", "full-year"]) or p_lower.startswith("fy"):
        yr_match = re.search(r"(\d{4})", p_lower)
        if yr_match:
            fy_yr = int(yr_match.group(1))
            return (f"FY{str(fy_yr)[-2:]}", f"{fy_yr}-FY")
        fy_2d = re.search(r"fy\s*(\d{2})", p_lower)
        if fy_2d:
            fy_yr = int(fy_2d.group(1)) + 2000
            return (f"FY{str(fy_yr)[-2:]}", f"{fy_yr}-FY")

    # 2. Fiscal Quarter notation (e.g. 'Q1 FY27', 'Q1FY27', 'Q1 2027')
    q_fy_match = re.search(r"q([1-4])\s*(?:fy)?\s*(\d{2,4})", p_lower)
    if q_fy_match:
        q_num = int(q_fy_match.group(1))
        raw_yr = int(q_fy_match.group(2))
        fy_yr = raw_yr + 2000 if raw_yr < 100 else raw_yr
        
        # FY27 Q1 corresponds to Jun 2026 calendar year (FY - 1 for Q1, Q2, Q3)
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
        
    # 4. Fallback: clean string
    return (p, p.upper())
        
    # 4. Fallback: clean string
    return (p, p.upper())

def normalize_metric_name(raw_metric: str) -> Optional[str]:
    """Maps arbitrary filing line items to canonical metric identifier."""
    if not raw_metric:
        return None
    clean = re.sub(r"[\(\)\[\],.:]", " ", raw_metric.lower()).strip()
    clean = re.sub(r"\s+", " ", clean)
    
    # Direct alias lookup
    if clean in METRIC_ALIAS_MAP:
        return METRIC_ALIAS_MAP[clean]
        
    # Substring matching
    for alias, canon in METRIC_ALIAS_MAP.items():
        if alias in clean:
            return canon
            
    return None

def normalize_numeric_scale(value: float, raw_unit: Optional[str] = None) -> float:
    """
    Converts reported financial figures to normalized ₹ Crore (Cr).
    """
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
        
    # Default is already ₹ Cr
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
    - Period alignment
    - Mathematical tolerance: Δ <= max(abs_tolerance, official_value * pct_tolerance)
      - abs_tolerance: 1.0 (₹1 Cr) for financial totals, 0.05 for EPS
      - pct_tolerance: 0.5% (0.005)
    """
    # 1. Scope Mismatch -> NOT_COMPARABLE
    norm_scr_scope = screener_scope.capitalize().strip()
    norm_off_scope = official_scope.capitalize().strip()
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
        abs_tolerance = 1.0 # ₹1 Cr absolute tolerance for rounding
        pct_tolerance = 0.005 # 0.5% relative tolerance
        
    tolerance_allowed = max(abs_tolerance, abs(official_val) * pct_tolerance)
    variance_abs = round(abs(screener_val - official_val), 4)
    variance_pct = round((variance_abs / abs(official_val)) * 100, 2) if official_val != 0 else 0.0
    
    # 5. Determine Verification Status
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
# OFFICIAL FINANCIAL RESULT INGESTION & PIPELINE
# =============================================================================

def extract_official_filing_metrics(
    symbol: str,
    filing_doc: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Extracts structured financial result line items from official filing payload.
    Supports deterministic tables and machine-readable filing results.
    """
    extracted_items = []
    scope = filing_doc.get("scope", "Consolidated")
    period_raw = filing_doc.get("reporting_period", "")
    disp_period, canon_period = normalize_period(period_raw)
    raw_unit = filing_doc.get("unit", "₹ Cr")
    source_url = filing_doc.get("source_url")
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

def run_official_financial_verification(
    symbol: str,
    screener_stock_data: Optional[Dict[str, Any]] = None,
    official_filing_docs: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Master Financial Verification Pipeline (Phase B):
    1. Upgrades authoritative identity from official exchange masters.
    2. Gathers Screener standardized quarterly and annual financial statements.
    3. Normalizes official filing reports from NSE/BSE corporate filings.
    4. Deterministically compares every key reported figure against Screener.
    5. Persists verification records and returns aggregated summary.
    """
    clean_sym = symbol.strip().upper()
    now_iso = datetime.now(timezone.utc).isoformat()
    
    # 1. Authoritative Identity Resolution & Upgrade
    resolve_and_upgrade_company_identity(clean_sym)
    
    # 2. Extract Screener reported metrics from quarters & profit_loss
    screener_metrics: Dict[Tuple[str, str, str], float] = {} # (canonical_period, canonical_metric, scope) -> value
    screener_source_url = ""
    
    if screener_stock_data:
        screener_source_url = screener_stock_data.get("source_url", "")
        scr_scope = screener_stock_data.get("statement_type", "consolidated").capitalize()
        
        # Parse quarterly statements
        quarters = screener_stock_data.get("quarters", {})
        q_periods = quarters.get("periods", [])
        for row in quarters.get("rows", []):
            m_name = row.get("metric", "")
            canon_m = normalize_metric_name(m_name)
            if not canon_m:
                continue
            values = row.get("values", {})
            for p_str, val in values.items():
                if val is not None:
                    _, canon_p = normalize_period(p_str)
                    if canon_p:
                        try:
                            screener_metrics[(canon_p, canon_m, scr_scope)] = float(val)
                        except Exception:
                            pass
                            
        # Parse annual Profit & Loss statements
        pl = screener_stock_data.get("profit_loss", {})
        pl_periods = pl.get("periods", [])
        for row in pl.get("rows", []):
            m_name = row.get("metric", "")
            canon_m = normalize_metric_name(m_name)
            if not canon_m:
                continue
            values = row.get("values", {})
            for p_str, val in values.items():
                if val is not None:
                    # e.g. "Mar 2026" annual column in P&L
                    _, canon_p = normalize_period("FY" + p_str.split()[-1][-2:] if len(p_str.split()) > 1 else p_str)
                    if canon_p:
                        try:
                            screener_metrics[(canon_p, canon_m, scr_scope)] = float(val)
                        except Exception:
                            pass

    # 3. Extract and normalize official filing items
    official_items: List[Dict[str, Any]] = []
    if official_filing_docs:
        for fdoc in official_filing_docs:
            extracted = extract_official_filing_metrics(clean_sym, fdoc)
            official_items.extend(extracted)
            
    # 4. Perform deterministic metric comparison
    verification_records: List[Dict[str, Any]] = []
    seen_keys = set()
    
    # Process official items first
    for off in official_items:
        canon_p = off["canonical_period"]
        canon_m = off["canonical_metric"]
        scope = off["scope"]
        key = (canon_p, canon_m, scope)
        seen_keys.add(key)
        
        scr_val = screener_metrics.get(key)
        off_val = off["official_value"]
        
        comp_res = compare_financial_metric(
            screener_val=scr_val,
            official_val=off_val,
            canonical_metric=canon_m,
            screener_scope=scope,
            official_scope=scope,
            screener_period_key=canon_p,
            official_period_key=canon_p
        )
        
        rec = {
            "symbol": clean_sym,
            "metric_name": off["metric_name"],
            "canonical_metric": canon_m,
            "period": off["period"],
            "canonical_period": canon_p,
            "scope": scope,
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
        
    # 5. Persist to database
    if verification_records:
        database.save_financial_verification_records(verification_records)
        
    # 6. Retrieve summary
    summary = database.get_financial_verification_summary(clean_sym)
    return {
        "symbol": clean_sym,
        "summary": summary,
        "records": verification_records
    }
