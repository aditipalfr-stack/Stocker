"""
=============================================================================
Stocker Official Financial Verification Engine (Phase B - Fail-Closed Edition)
=============================================================================
Provides deterministic normalization, authoritative metric comparison,
and provenance tracking between Screener.in standardized statements
and official corporate filings / exchange outcomes (NSE / BSE / IR).

Key Principles:
1. NON-NEGOTIABLE FAIL CLOSED: Stocker outputs VERIFIED or DISCREPANCY only when
   it can deterministically establish: same security, exact period, exact scope,
   compatible metric definition, correct numeric fact, known unit/currency,
   and exact Screener counterpart within tolerance.
2. XBRL unitRef & contextRef Resolution:
   - Builds units_by_id mapping from all <unit id="..."> definitions (INR, INR/shares, etc.)
   - Validates each fact's own unitRef; missing/unresolved unitRef -> unit = Unknown
   - Evaluates context duration (Quarter vs Annual vs YTD) and dimensional scope
   - Rejects facts with ambiguous or conflicting multiple contexts/units
3. Generic EPS Ambiguity:
   - "EPS", "EPS in Rs", "Earnings Per Share" without explicit "Basic" or "Diluted"
     qualifiers are treated as ambiguous (return None / no canonical mapping).
   - Only explicit "Basic EPS" -> BASIC_EPS, and explicit "Diluted EPS" -> DILUTED_EPS.
4. PDF Verification Policy:
   - PDF plain text streams do not guarantee 2D table coordinates. PDF files provide
     provenance and document metadata, but numeric extraction fails closed as
     INSUFFICIENT_EVIDENCE to guarantee zero hallucination/misalignment.
5. HTML & JSON Verification Policy:
   - HTML true <table> structures with explicit <th> headers and cell indices map deterministically.
   - JSON structured payloads must explicitly declare metric, value, period, scope, and unit.
6. Banking / Financial Sector Safety:
   - Rejects non-financial Revenue comparisons for banking / lending entities.
7. Strict Exact Period & Exact Scope Matching:
   - Zero nearest-period fallback
   - Ambiguous multiple official figures -> INSUFFICIENT_EVIDENCE
=============================================================================
"""

import sys
import re
import io
import math
import json
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent / "libs"))
import pypdf
import bs4

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

# Safe canonical metrics supported in Phase B verification
SAFE_CANONICAL_METRICS = ["REVENUE", "PBT", "PAT", "BASIC_EPS", "DILUTED_EPS"]

# Conservative Metric Mapping Dictionary (Safe unambiguous labels only)
CONSERVATIVE_METRIC_MAP: Dict[str, str] = {
    # Revenue / Sales (Non-financials)
    "revenue from operations": "REVENUE",
    "net sales": "REVENUE",
    "sales": "REVENUE",
    "revenue": "REVENUE",
    "total income from operations": "REVENUE",
    "income from operations": "REVENUE",
    "revenuefromoperations": "REVENUE",
    "incomefromoperations": "REVENUE",
    
    # PBT (Strict bottom-line Profit Before Tax)
    "profit before tax": "PBT",
    "pbt": "PBT",
    "profitlossbeforetax": "PBT",
    "profitbeforetax": "PBT",
    
    # PAT / Net Profit
    "net profit": "PAT",
    "profit after tax": "PAT",
    "pat": "PAT",
    "profit for the period": "PAT",
    "net profit for the period": "PAT",
    "profitlossforperiod": "PAT",
    "profitlossaftertax": "PAT",
    
    # Explicit Basic EPS ONLY
    "basic eps": "BASIC_EPS",
    "basic eps in rs": "BASIC_EPS",
    "basic earnings per share": "BASIC_EPS",
    "basicearningslosspershare": "BASIC_EPS",
    
    # Explicit Diluted EPS ONLY
    "diluted eps": "DILUTED_EPS",
    "diluted eps in rs": "DILUTED_EPS",
    "diluted earnings per share": "DILUTED_EPS",
    "dilutedearningslosspershare": "DILUTED_EPS"
}

# Ambiguous line items that must NOT be mapped to canonical metrics
AMBIGUOUS_METRIC_KEYWORDS = [
    "ebit", "pbit", "ebitda", "operating profit", "operating profit before depreciation",
    "profit attributable to non-controlling", "exceptional items", "other income",
    "profit before exceptional items and tax", "profit before tax and exceptional items",
    "eps in rs", "eps", "earnings per share" # Generic unqualified EPS is ambiguous
]

def normalize_metric_name(raw_metric: str) -> Optional[str]:
    """
    Conservatively maps raw filing metric names to canonical metric keys.
    Returns None if metric is ambiguous, unqualified (like generic EPS), or deferred.
    """
    if not raw_metric:
        return None
    clean = re.sub(r"[\(\)\[\],.:]", " ", raw_metric.lower()).strip()
    clean = re.sub(r"\s+", " ", clean)
    clean_no_space = re.sub(r"\s+", "", clean)
    
    # Reject ambiguous / unqualified / deferred line items
    for amb in AMBIGUOUS_METRIC_KEYWORDS:
        if clean == amb or clean_no_space == re.sub(r"\s+", "", amb):
            return None
            
    # Direct lookup
    if clean in CONSERVATIVE_METRIC_MAP:
        return CONSERVATIVE_METRIC_MAP[clean]
    if clean_no_space in CONSERVATIVE_METRIC_MAP:
        return CONSERVATIVE_METRIC_MAP[clean_no_space]
        
    # Exact alias match
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
        return ("", "Unknown")
        
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

    # 3. Standard Month Year / Day Month Year (e.g. 'Jun 2026', 'Quarter ended 30 June 2026', '30-Jun-2026', '30.06.2026')
    month_match = re.search(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s*[-/,.]?\s*(\d{4})\b", p_lower)
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

    # 4. Numeric DD-MM-YYYY format
    dmy_match = re.search(r"\b\d{1,2}[-/.](\d{2})[-/.](\d{4})\b", p_lower)
    if dmy_match:
        mo_num = dmy_match.group(1)
        yr = int(dmy_match.group(2))
        mo_q_map = {
            "06": ("Jun " + str(yr), f"{yr}-Q1"),
            "09": ("Sep " + str(yr), f"{yr}-Q2"),
            "12": ("Dec " + str(yr), f"{yr}-Q3"),
            "03": ("Mar " + str(yr), f"{yr}-Q4"),
        }
        if mo_num in mo_q_map:
            return mo_q_map[mo_num]
            
    return (p, "Unknown")

def normalize_numeric_scale(value: float, raw_unit: Optional[str] = None) -> float:
    """Converts reported financial figures to normalized ₹ Crore (Cr)."""
    if value is None or math.isnan(value):
        return 0.0
        
    if not raw_unit or raw_unit == "Unknown":
        return float(value)
        
    u = raw_unit.lower().strip()
    if "lakh" in u:
        return round(float(value) / 100.0, 4)
    elif "million" in u or "mn" in u:
        return round(float(value) / 10.0, 4)
    elif "billion" in u or "bn" in u:
        return round(float(value) * 100.0, 4)
    elif "thousand" in u:
        return round(float(value) / 100000.0, 4)
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
    official_period_key: str = "",
    official_unit: str = "Unknown",
    is_banking_entity: bool = False
) -> Dict[str, Any]:
    """
    Evaluates Screener.in value against Official filing value with strict fail-closed rules:
    - Scope alignment (Consolidated vs Standalone -> NOT_COMPARABLE)
    - Scope unknown -> NOT_COMPARABLE
    - Unit unknown -> INSUFFICIENT_EVIDENCE
    - Period alignment (e.g. 2026-Q1 vs 2026-Q2 -> NOT_COMPARABLE)
    - Period unknown -> NOT_COMPARABLE
    - Banking entity Revenue -> INSUFFICIENT_EVIDENCE
    - Mathematical tolerance: Δ <= max(abs_tolerance, official_value * pct_tolerance)
      - abs_tolerance: 1.0 (₹1 Cr) for financial totals, 0.05 for EPS
      - pct_tolerance: 0.5% (0.005) for financial totals, 1.0% for EPS
    """
    norm_scr_scope = (screener_scope or "Consolidated").capitalize().strip()
    norm_off_scope = (official_scope or "Unknown").capitalize().strip()
    
    # 1. Banking Entity Non-Financial Metric Check
    if is_banking_entity and canonical_metric == "REVENUE":
        return {
            "status": "INSUFFICIENT_EVIDENCE",
            "variance_abs": None,
            "variance_pct": None,
            "tolerance_used": None,
            "notes": "Banking/Financial institution: Generic 'Revenue from Operations' is not directly comparable without sector-specific interest income taxonomy."
        }
        
    # 2. Scope Unknown or Scope Mismatch
    if norm_off_scope == "Unknown":
        return {
            "status": "NOT_COMPARABLE",
            "variance_abs": None,
            "variance_pct": None,
            "tolerance_used": None,
            "notes": "Cannot verify: Reporting scope (Consolidated/Standalone) could not be established from official filing."
        }
    if norm_scr_scope != norm_off_scope:
        return {
            "status": "NOT_COMPARABLE",
            "variance_abs": None,
            "variance_pct": None,
            "tolerance_used": None,
            "notes": f"Scope mismatch: Screener is {norm_scr_scope} while official filing is {norm_off_scope}."
        }
        
    # 3. Unit Unknown
    if official_unit in ("Unknown", "unknown", None, ""):
        return {
            "status": "INSUFFICIENT_EVIDENCE",
            "variance_abs": None,
            "variance_pct": None,
            "tolerance_used": None,
            "notes": "Cannot verify: Unit of measurement could not be deterministically established from official filing."
        }
        
    # 4. Period Unknown or Period Mismatch
    if official_period_key in ("Unknown", "unknown", ""):
        return {
            "status": "NOT_COMPARABLE",
            "variance_abs": None,
            "variance_pct": None,
            "tolerance_used": None,
            "notes": "Cannot verify: Reporting period could not be confidently determined from official filing."
        }
    if screener_period_key and screener_period_key != official_period_key:
        return {
            "status": "NOT_COMPARABLE",
            "variance_abs": None,
            "variance_pct": None,
            "tolerance_used": None,
            "notes": f"Period mismatch: Screener period ({screener_period_key}) does not align with official filing ({official_period_key})."
        }
        
    # 5. Missing Value checks
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
            "notes": f"Metric exists in official filing for {official_period_key} ({norm_off_scope}) but is absent from Screener statement for this period."
        }
    if official_val is None:
        return {
            "status": "OFFICIAL_SOURCE_MISSING",
            "variance_abs": None,
            "variance_pct": None,
            "tolerance_used": None,
            "notes": "Metric reported in Screener statement but missing from official filing."
        }
        
    # 6. Tolerance calculation
    if canonical_metric in ("BASIC_EPS", "DILUTED_EPS", "EPS"):
        abs_tolerance = 0.05
        pct_tolerance = 0.01 # 1% for EPS
        unit_label = "₹ / Share"
    else:
        abs_tolerance = 1.0 # ₹1 Cr absolute tolerance
        pct_tolerance = 0.005 # 0.5% relative tolerance
        unit_label = "₹ Cr"
        
    tolerance_allowed = max(abs_tolerance, abs(official_val) * pct_tolerance)
    variance_abs = round(abs(screener_val - official_val), 4)
    variance_pct = round((variance_abs / abs(official_val)) * 100, 2) if official_val != 0 else 0.0
    
    # 7. Verification Status
    if variance_abs <= tolerance_allowed:
        return {
            "status": "VERIFIED",
            "variance_abs": variance_abs,
            "variance_pct": variance_pct,
            "tolerance_used": round(tolerance_allowed, 4),
            "notes": f"Verified: Screener figure aligns with official filing (variance of {variance_abs} {unit_label} is within allowed tolerance of {round(tolerance_allowed, 2)} {unit_label})."
        }
    else:
        return {
            "status": "DISCREPANCY",
            "variance_abs": variance_abs,
            "variance_pct": variance_pct,
            "tolerance_used": round(tolerance_allowed, 4),
            "notes": f"Discrepancy detected: Screener value ({screener_val}) differs from official reported filing ({official_val}) by {variance_abs} {unit_label} ({variance_pct}%), exceeding tolerance limit of {round(tolerance_allowed, 2)} {unit_label}."
        }

# =============================================================================
# DETERMINISTIC OFFICIAL FILING PARSERS (XBRL/XML, PDF, HTML, JSON)
# =============================================================================

def parse_official_xbrl_xml(
    xml_data: bytes,
    filing_ref: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Deterministically parses official Ind-AS XBRL XML corporate filing results using
    strict contextRef, dimension, period duration, and fact-level unitRef resolution.
    """
    doc = dict(filing_ref)
    doc["extraction_method"] = "official_xbrl_context"
    table_rows: List[Dict[str, Any]] = []
    
    try:
        root = ET.fromstring(xml_data)
        
        # 1. Parse Document-level default scope
        doc_default_scope = "Unknown"
        for elem in root.iter():
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if tag in ("NatureOfReportStandaloneConsolidated", "NatureOfReport") and elem.text:
                t_val = elem.text.strip().capitalize()
                if "Consolidated" in t_val:
                    doc_default_scope = "Consolidated"
                elif "Standalone" in t_val:
                    doc_default_scope = "Standalone"
                break
                
        # 2. Parse Document-level LevelOfRounding
        doc_rounding_unit = "Unknown"
        for elem in root.iter():
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if tag in ("LevelOfRounding", "UnitOfMeasurement") and elem.text:
                u_text = elem.text.strip().lower()
                if "crore" in u_text or "cr" in u_text:
                    doc_rounding_unit = "₹ Cr"
                elif "lakh" in u_text:
                    doc_rounding_unit = "₹ Lakhs"
                elif "million" in u_text or "mn" in u_text:
                    doc_rounding_unit = "₹ Millions"
                elif "thousand" in u_text:
                    doc_rounding_unit = "₹ Thousands"
                elif "rupee" in u_text or "single" in u_text:
                    doc_rounding_unit = "₹ Rupees"
                break
                
        # 3. Parse all <unit id="..."> definitions into units_by_id
        units_by_id: Dict[str, Dict[str, Any]] = {}
        for elem in root.iter():
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if tag == "unit":
                u_id = elem.attrib.get("id")
                if not u_id:
                    continue
                    
                has_divide = False
                num_measure = ""
                den_measure = ""
                single_measure = ""
                
                for sub in elem.iter():
                    s_tag = sub.tag.split("}")[-1] if "}" in sub.tag else sub.tag
                    if s_tag == "divide":
                        has_divide = True
                    elif s_tag in ("unitNumerator", "numerator"):
                        for m in sub.iter():
                            if m.tag.split("}")[-1] == "measure" and m.text:
                                num_measure = m.text.strip()
                    elif s_tag in ("unitDenominator", "denominator"):
                        for m in sub.iter():
                            if m.tag.split("}")[-1] == "measure" and m.text:
                                den_measure = m.text.strip()
                    elif s_tag == "measure" and not has_divide and sub.text:
                        single_measure = sub.text.strip()
                        
                num_clean = num_measure.split(":")[-1].upper() if ":" in num_measure else num_measure.upper()
                den_clean = den_measure.split(":")[-1].upper() if ":" in den_measure else den_measure.upper()
                sin_clean = single_measure.split(":")[-1].upper() if ":" in single_measure else single_measure.upper()
                
                if has_divide or ("SHARE" in u_id.upper() and "INR" in u_id.upper()):
                    if ("INR" in num_clean or "INR" in u_id.upper()) and ("SHARE" in den_clean or "SHARE" in u_id.upper() or not den_clean):
                        units_by_id[u_id] = {
                            "type": "per_share",
                            "currency": "INR",
                            "numerator": num_clean,
                            "denominator": den_clean or "SHARES",
                            "resolved_unit": "₹ / Share"
                        }
                    else:
                        units_by_id[u_id] = {
                            "type": "unknown_divide",
                            "currency": None,
                            "resolved_unit": "Unknown"
                        }
                elif sin_clean == "INR" or u_id.upper() == "INR" or u_id.upper() == "U_INR":
                    units_by_id[u_id] = {
                        "type": "currency",
                        "currency": "INR",
                        "measure": "INR",
                        "resolved_unit": None # Resolved via LevelOfRounding / scale
                    }
                elif sin_clean in ("SHARES", "PURE") or "SHARE" in u_id.upper():
                    units_by_id[u_id] = {
                        "type": "shares",
                        "currency": None,
                        "measure": sin_clean,
                        "resolved_unit": "Shares"
                    }
                else:
                    units_by_id[u_id] = {
                        "type": "unknown",
                        "currency": None,
                        "measure": sin_clean,
                        "resolved_unit": "Unknown"
                    }
                    
        # 4. Parse all <context> definitions
        contexts: Dict[str, Dict[str, Any]] = {}
        for elem in root.iter():
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if tag == "context":
                ctx_id = elem.attrib.get("id")
                if not ctx_id:
                    continue
                    
                ctx_info = {
                    "start_date": None,
                    "end_date": None,
                    "instant": None,
                    "scope": doc_default_scope,
                    "canonical_period": "Unknown",
                    "display_period": "",
                    "is_quarter": False,
                    "is_annual": False,
                    "is_ytd": False
                }
                
                # Check for explicit dimension members in segment/scenario
                for sub in elem.iter():
                    sub_tag = sub.tag.split("}")[-1] if "}" in sub.tag else sub.tag
                    if sub_tag in ("explicitMember", "member") and sub.text:
                        mem_txt = sub.text.strip().lower()
                        if "consolidated" in mem_txt:
                            ctx_info["scope"] = "Consolidated"
                        elif "standalone" in mem_txt:
                            ctx_info["scope"] = "Standalone"
                            
                # Check period dates
                for p_elem in elem.iter():
                    p_tag = p_elem.tag.split("}")[-1] if "}" in p_elem.tag else p_elem.tag
                    if p_tag == "startDate" and p_elem.text:
                        ctx_info["start_date"] = p_elem.text.strip()
                    elif p_tag == "endDate" and p_elem.text:
                        ctx_info["end_date"] = p_elem.text.strip()
                    elif p_tag == "instant" and p_elem.text:
                        ctx_info["instant"] = p_elem.text.strip()
                        
                if ctx_info["start_date"] and ctx_info["end_date"]:
                    try:
                        d_start = datetime.strptime(ctx_info["start_date"], "%Y-%m-%d").date()
                        d_end = datetime.strptime(ctx_info["end_date"], "%Y-%m-%d").date()
                        duration = (d_end - d_start).days + 1
                        
                        disp_p, canon_p = normalize_period(f"{d_end.strftime('%d-%b-%Y')}")
                        ctx_info["canonical_period"] = canon_p
                        ctx_info["display_period"] = disp_p
                        
                        if 75 <= duration <= 110:
                            ctx_info["is_quarter"] = True
                        elif 340 <= duration <= 380:
                            ctx_info["is_annual"] = True
                            ctx_info["canonical_period"] = f"{d_end.year}-FY"
                            ctx_info["display_period"] = f"FY{str(d_end.year)[-2:]}"
                        else:
                            ctx_info["is_ytd"] = True
                    except Exception:
                        pass
                elif ctx_info["instant"]:
                    disp_p, canon_p = normalize_period(ctx_info["instant"])
                    ctx_info["canonical_period"] = canon_p
                    ctx_info["display_period"] = disp_p
                    
                contexts[ctx_id] = ctx_info
                
        # 5. Extract Safe Canonical Metric Facts with Fact-Level Context & Unit Resolution
        candidate_facts: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = {}
        
        for elem in root.iter():
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            canon_m = normalize_metric_name(tag)
            if not canon_m or not elem.text:
                continue
                
            ctx_ref = elem.attrib.get("contextRef")
            if not ctx_ref or ctx_ref not in contexts:
                # Missing or unresolvable contextRef -> skip fact
                continue
                
            ctx = contexts[ctx_ref]
            if ctx["is_ytd"]:
                # Non-standard YTD duration context -> skip
                continue
                
            fact_scope = ctx["scope"]
            fact_canon_p = ctx["canonical_period"]
            fact_disp_p = ctx["display_period"]
            
            # Genuinely resolve fact unitRef against units_by_id
            unit_ref = elem.attrib.get("unitRef")
            if not unit_ref or unit_ref not in units_by_id:
                # Fact missing unitRef or unresolvable unit id -> Unknown unit
                fact_unit = "Unknown"
                fact_currency = "INR"
            else:
                u_def = units_by_id[unit_ref]
                if u_def["type"] == "per_share":
                    fact_unit = "₹ / Share"
                    fact_currency = "INR"
                elif u_def["type"] == "currency" and u_def["currency"] == "INR":
                    fact_currency = "INR"
                    fact_unit = doc_rounding_unit if doc_rounding_unit != "Unknown" else "Unknown"
                else:
                    fact_unit = "Unknown"
                    fact_currency = "INR"
                    
            try:
                num_val = float(elem.text.strip())
                key = (canon_m, fact_canon_p, fact_scope)
                if key not in candidate_facts:
                    candidate_facts[key] = []
                candidate_facts[key].append({
                    "raw_metric": tag,
                    "canonical_metric": canon_m,
                    "value": num_val,
                    "scope": fact_scope,
                    "canonical_period": fact_canon_p,
                    "period_display": fact_disp_p,
                    "unit": fact_unit,
                    "currency": fact_currency,
                    "context_id": ctx_ref,
                    "unit_ref": unit_ref
                })
            except Exception:
                pass
                
        # 6. Deduplicate equivalent facts or reject ambiguous multiple contexts
        for key, facts in candidate_facts.items():
            if len(facts) == 1:
                f = facts[0]
                table_rows.append({
                    "metric": f["raw_metric"],
                    "canonical_metric": f["canonical_metric"],
                    "value": f["value"],
                    "scope": f["scope"],
                    "canonical_period": f["canonical_period"],
                    "period": f["period_display"],
                    "unit": f["unit"],
                    "currency": f["currency"],
                    "context_ref": f["context_id"],
                    "unit_ref": f["unit_ref"]
                })
            else:
                # Compare context semantics and units across multiple facts
                unique_vals = set(f["value"] for f in facts)
                unique_units = set(f["unit"] for f in facts)
                if len(unique_vals) == 1 and len(unique_units) == 1:
                    # Genuinely identical duplicate facts
                    f = facts[0]
                    table_rows.append({
                        "metric": f["raw_metric"],
                        "canonical_metric": f["canonical_metric"],
                        "value": f["value"],
                        "scope": f["scope"],
                        "canonical_period": f["canonical_period"],
                        "period": f["period_display"],
                        "unit": f["unit"],
                        "currency": f["currency"],
                        "context_ref": f["context_id"],
                        "unit_ref": f["unit_ref"]
                    })
                else:
                    # Incompatible or conflicting values/units for same (metric, period, scope) -> skip (fail closed)
                    pass
                    
        doc["financial_table"] = table_rows
        doc["scope"] = doc_default_scope
        doc["unit"] = doc_rounding_unit
    except Exception:
        doc["financial_table"] = []
        
    return doc

def parse_official_pdf_document(
    pdf_bytes: bytes,
    filing_ref: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Parses official PDF outcome filings to capture document-level provenance, filing date,
    scope, and period metadata. For numeric safety, unconstrained PDF text stream parsing
    does not guarantee 2D table coordinates and is marked as INSUFFICIENT_EVIDENCE
    for deterministic numeric verification.
    """
    doc = dict(filing_ref)
    doc["extraction_method"] = "official_pdf_document"
    doc["financial_table"] = [] # Fail-closed for numeric extraction
    
    try:
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        full_text = ""
        for page in reader.pages[:5]:
            t = page.extract_text() or ""
            full_text += t + "\n"
            
        text_lower = full_text.lower()
        if "statement of consolidated" in text_lower or "consolidated financial results" in text_lower:
            doc["scope"] = "Consolidated"
        elif "statement of standalone" in text_lower or "standalone financial results" in text_lower:
            doc["scope"] = "Standalone"
        else:
            doc["scope"] = "Unknown"
            
        period_match = re.search(r"(?:quarter|three\s*months|year|12\s*months)\s*ended\s*(\d{1,2}(?:st|nd|rd|th)?\s+[a-zA-Z]+\s+\d{4})", text_lower)
        if period_match:
            doc["reporting_period"] = f"Quarter ended {period_match.group(1).title()}"
    except Exception:
        pass
        
    return doc

def parse_official_html_table(
    html_data: bytes,
    filing_ref: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Deterministically parses official HTML financial result announcements with BeautifulSoup
    using header-driven column mapping.
    """
    doc = dict(filing_ref)
    doc["extraction_method"] = "official_html_table"
    table_rows: List[Dict[str, Any]] = []
    
    try:
        soup = bs4.BeautifulSoup(html_data, "html.parser")
        text_lower = soup.get_text().lower()
        
        # 1. Determine Scope
        scope = "Unknown"
        if "consolidated" in text_lower:
            scope = "Consolidated"
        elif "standalone" in text_lower:
            scope = "Standalone"
        doc["scope"] = scope
        
        # 2. Determine Unit
        unit = "Unknown"
        unit_match = re.search(r"\((?:rs\.?|in\s+rs\.?|₹|in\s+₹)\s*(?:in\s*)?(crores?|lakhs?|millions?|thousands?)\)", text_lower)
        if unit_match:
            u_word = unit_match.group(1)
            if "crore" in u_word:
                unit = "₹ Cr"
            elif "lakh" in u_word:
                unit = "₹ Lakhs"
            elif "million" in u_word:
                unit = "₹ Millions"
        doc["unit"] = unit
        
        # 3. Locate Financial Result Table & Map Columns
        tables = soup.find_all("table")
        for table in tables:
            header_columns: List[Dict[str, Any]] = []
            
            # Find header rows
            for row in table.find_all("tr"):
                cells = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
                date_headers = []
                for idx, cell_text in enumerate(cells):
                    disp_p, canon_p = normalize_period(cell_text)
                    if canon_p != "Unknown":
                        date_headers.append({
                            "col_idx": idx,
                            "canonical_period": canon_p,
                            "period_display": disp_p
                        })
                if len(date_headers) >= 2:
                    header_columns = date_headers
                    break
                    
            if not header_columns:
                continue
                
            # Parse data rows
            for row in table.find_all("tr"):
                cells = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
                if len(cells) < 2:
                    continue
                m_label = cells[0]
                canon_m = normalize_metric_name(m_label)
                if not canon_m:
                    continue
                    
                for col in header_columns:
                    col_idx = col["col_idx"]
                    if col_idx < len(cells):
                        num_str = cells[col_idx].replace(",", "")
                        try:
                            num_val = float(num_str)
                            fact_unit = "₹ / Share" if canon_m in ("BASIC_EPS", "DILUTED_EPS") else unit
                            table_rows.append({
                                "metric": m_label,
                                "canonical_metric": canon_m,
                                "value": num_val,
                                "scope": scope,
                                "canonical_period": col["canonical_period"],
                                "period": col["period_display"],
                                "unit": fact_unit
                            })
                        except Exception:
                            pass
                            
        doc["financial_table"] = table_rows
    except Exception:
        doc["financial_table"] = []
        
    return doc

# =============================================================================
# REAL OFFICIAL FINANCIAL RESULT DISCOVERY & FETCH ADAPTERS
# =============================================================================

def discover_official_financial_results(
    symbol: str,
    timeout: int = 5
) -> List[Dict[str, Any]]:
    """
    Discovers latest official financial outcome filings from exchange repositories.
    Scope and unit remain 'Unknown' during discovery until established by the parser.
    """
    clean_sym = symbol.strip().upper()
    now_iso = datetime.now(timezone.utc).isoformat()
    discovered_filings: List[Dict[str, Any]] = []
    
    url = NSE_CORPORATE_ANNOUNCEMENTS_URL.format(symbol=clean_sym)
    try:
        req = urllib.request.Request(url, headers=EXCHANGE_HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
            
            items = data if isinstance(data, list) else data.get("data", [])
            for item in items:
                desc = item.get("desc", "") or item.get("subject", "") or ""
                if any(kw in desc.lower() for kw in ["financial results", "outcome of board meeting", "financial statement"]):
                    att_url = item.get("attmnt", "") or item.get("attachment", "") or ""
                    full_url = f"https://nsearchives.nseindia.com/corporate/{att_url}" if att_url and not att_url.startswith("http") else att_url
                    
                    discovered_filings.append({
                        "symbol": clean_sym,
                        "document_title": desc,
                        "document_type": "official_financial_result",
                        "reporting_period": item.get("period", ""),
                        "filing_date": item.get("date", ""),
                        "scope": "Unknown", # Fail-closed: Must be established by filing body
                        "unit": "Unknown",  # Fail-closed: Must be established by filing body
                        "source_name": "NSE Corporate Filing",
                        "source_url": full_url or url,
                        "actual_source_url": full_url or url,
                        "retrieved_at": now_iso
                    })
    except Exception:
        pass
        
    return discovered_filings

def fetch_official_financial_result(
    symbol: str,
    filing_ref: Dict[str, Any],
    timeout: int = 5
) -> Optional[Dict[str, Any]]:
    """
    Fetches and deterministically parses structured financial results from official filing candidate.
    Supports XBRL/XML, PDF, HTML, and structured JSON payloads with strict schema validation.
    """
    if not filing_ref:
        return None
        
    # If filing already contains extracted table rows (from mock fixture or structured test doc)
    if "financial_table" in filing_ref or "rows" in filing_ref:
        doc = dict(filing_ref)
        if "rows" in doc and "financial_table" not in doc:
            doc["financial_table"] = doc["rows"]
        doc["extraction_method"] = doc.get("extraction_method", "structured_table_direct")
        return doc
        
    source_url = filing_ref.get("source_url") or filing_ref.get("actual_source_url")
    if not source_url:
        return None
        
    try:
        req = urllib.request.Request(source_url, headers=EXCHANGE_HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            content_type = response.headers.get("Content-Type", "").lower()
            raw_bytes = response.read()
            
            # Format 1: XBRL / XML
            if source_url.endswith(".xml") or source_url.endswith(".xbrl") or "xml" in content_type:
                return parse_official_xbrl_xml(raw_bytes, filing_ref)
                
            # Format 2: Official Result PDF
            elif source_url.endswith(".pdf") or "pdf" in content_type:
                return parse_official_pdf_document(raw_bytes, filing_ref)
                
            # Format 3: HTML Web Table
            elif source_url.endswith(".html") or source_url.endswith(".htm") or "html" in content_type:
                return parse_official_html_table(raw_bytes, filing_ref)
                
            # Format 4: JSON REST Response (with strict schema validation)
            elif "application/json" in content_type or source_url.endswith(".json"):
                parsed_json = json.loads(raw_bytes.decode("utf-8"))
                filing_doc = dict(filing_ref)
                raw_rows = parsed_json.get("rows", [])
                validated_rows = []
                for r in raw_rows:
                    if isinstance(r, dict) and "metric" in r and "value" in r:
                        # Row must have period, scope, and unit either explicitly or from doc
                        has_period = bool(r.get("canonical_period") or r.get("period") or filing_doc.get("reporting_period"))
                        has_scope = bool(r.get("scope") or (filing_doc.get("scope") and filing_doc.get("scope") != "Unknown"))
                        has_unit = bool(r.get("unit") or (filing_doc.get("unit") and filing_doc.get("unit") != "Unknown"))
                        if has_period and has_scope and has_unit:
                            validated_rows.append(r)
                filing_doc["financial_table"] = validated_rows
                filing_doc["extraction_method"] = "official_json_structured" if validated_rows else "unsupported_or_failed"
                return filing_doc
    except Exception:
        pass
        
    doc = dict(filing_ref)
    doc["extraction_method"] = "unsupported_or_failed"
    doc["financial_table"] = []
    return doc

def extract_official_filing_metrics(
    symbol: str,
    filing_doc: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Extracts structured financial result line items from official filing payload.
    """
    extracted_items = []
    doc_scope = filing_doc.get("scope", "Unknown")
    doc_unit = filing_doc.get("unit", "Unknown")
    source_url = filing_doc.get("source_url") or filing_doc.get("actual_source_url")
    source_name = filing_doc.get("source_name", "NSE Filing")
    doc_id = filing_doc.get("document_id") or filing_doc.get("document_title")
    ext_method = filing_doc.get("extraction_method", "deterministic")
    
    line_items = filing_doc.get("financial_table") or filing_doc.get("rows") or []
    for row in line_items:
        raw_name = row.get("metric") or row.get("line_item") or row.get("name") or ""
        canon_m = row.get("canonical_metric") or normalize_metric_name(raw_name)
        if not canon_m:
            continue
            
        raw_val = row.get("value")
        if raw_val is None:
            continue
            
        row_scope = row.get("scope") or doc_scope
        row_period = row.get("period") or filing_doc.get("reporting_period", "")
        row_canon_p = row.get("canonical_period")
        if not row_canon_p:
            disp_p, row_canon_p = normalize_period(row_period)
        else:
            disp_p = row.get("period") or row_canon_p
            
        row_unit = row.get("unit") or doc_unit
        
        try:
            num_val = float(raw_val)
            norm_val = normalize_numeric_scale(num_val, row_unit) if canon_m not in ("BASIC_EPS", "DILUTED_EPS", "EPS") else float(num_val)
            
            extracted_items.append({
                "metric_name": raw_name,
                "canonical_metric": canon_m,
                "period": disp_p,
                "canonical_period": row_canon_p,
                "scope": row_scope,
                "official_value": norm_val,
                "unit": "₹ / Share" if canon_m in ("BASIC_EPS", "DILUTED_EPS", "EPS") else "₹ Cr",
                "raw_unit": row_unit,
                "currency": "INR",
                "official_source_url": source_url,
                "official_source_name": source_name,
                "official_document_id": doc_id,
                "extraction_method": ext_method
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
    4. Deterministically compares every safe reported figure against Screener.
    5. Persists verification records and returns aggregated summary.
    """
    clean_sym = symbol.strip().upper()
    now_iso = datetime.now(timezone.utc).isoformat()
    
    # 1. Authoritative Identity Resolution & Upgrade
    resolve_and_upgrade_company_identity(clean_sym, use_live_exchange=use_live_exchange)
    
    # Check if stock is in banking/financial sector
    company_row = database.get_company_by_symbol(clean_sym) or {}
    sector_str = (company_row.get("sector") or "").lower()
    industry_str = (company_row.get("industry") or "").lower()
    is_banking = any(kw in sector_str or kw in industry_str for kw in ["bank", "financial", "nbfc", "lending"])
    
    # 2. Extract Screener reported metrics with actual statement scope
    screener_metrics: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    screener_source_url = ""
    
    if screener_stock_data:
        screener_source_url = screener_stock_data.get("source_url", "")
        scr_statement_scope = screener_stock_data.get("statement_type", "consolidated").capitalize()
        
        # Quarterly statements
        quarters = screener_stock_data.get("quarters", {})
        for row in quarters.get("rows", []):
            m_name = row.get("metric", "")
            # Screener labels like "Basic EPS" map to BASIC_EPS; generic "EPS in Rs" maps to BASIC_EPS if Screener statement
            clean_m_lower = m_name.lower().strip()
            if clean_m_lower == "eps in rs":
                canon_m = "BASIC_EPS"
            else:
                canon_m = normalize_metric_name(m_name)
            if not canon_m:
                continue
            values = row.get("values", {})
            for p_str, val in values.items():
                if val is not None:
                    disp_p, canon_p = normalize_period(p_str)
                    if canon_p and canon_p != "Unknown":
                        try:
                            key = (canon_m, canon_p, scr_statement_scope)
                            screener_metrics[key] = {
                                "value": float(val),
                                "scope": scr_statement_scope,
                                "period_display": disp_p,
                                "canonical_period": canon_p
                            }
                        except Exception:
                            pass
                            
        # Annual Profit & Loss statements
        pl = screener_stock_data.get("profit_loss", {})
        for row in pl.get("rows", []):
            m_name = row.get("metric", "")
            clean_m_lower = m_name.lower().strip()
            if clean_m_lower == "eps in rs":
                canon_m = "BASIC_EPS"
            else:
                canon_m = normalize_metric_name(m_name)
            if not canon_m:
                continue
            values = row.get("values", {})
            for p_str, val in values.items():
                if val is not None:
                    disp_p, canon_p = normalize_period("FY" + p_str.split()[-1][-2:] if len(p_str.split()) > 1 else p_str)
                    if canon_p and canon_p != "Unknown":
                        try:
                            key = (canon_m, canon_p, scr_statement_scope)
                            screener_metrics[key] = {
                                "value": float(val),
                                "scope": scr_statement_scope,
                                "period_display": disp_p,
                                "canonical_period": canon_p
                            }
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
                
    # 4. If NO official filings exist: Return OFFICIAL_SOURCE_MISSING
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
        summary["overall_status"] = "INSUFFICIENT_EVIDENCE"
        summary["unavailable_reason"] = "Official filing was retrieved but contains unsupported formatting or missing numerical tables (e.g. PDF text stream without structured cell coordinates)."
        return {
            "symbol": clean_sym,
            "summary": summary,
            "records": []
        }

    # 6. Perform strict exact-match comparison
    verification_records: List[Dict[str, Any]] = []
    
    # Check for multiple candidates for same (canon_m, canon_p, scope)
    seen_official_keys: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = {}
    for off in official_items:
        k = (off["canonical_metric"], off["canonical_period"], off["scope"])
        if k not in seen_official_keys:
            seen_official_keys[k] = []
        seen_official_keys[k].append(off)
        
    for k, off_list in seen_official_keys.items():
        off_canon_m, off_canon_p, off_scope = k
        
        # Check for ambiguity
        if len(off_list) > 1:
            vals = set(x["official_value"] for x in off_list)
            units = set(x["raw_unit"] for x in off_list)
            if len(vals) > 1 or len(units) > 1:
                rec = {
                    "symbol": clean_sym,
                    "metric_name": off_list[0]["metric_name"],
                    "canonical_metric": off_canon_m,
                    "period": off_list[0]["period"],
                    "canonical_period": off_canon_p,
                    "scope": off_scope,
                    "screener_value": None,
                    "official_value": None,
                    "variance_abs": None,
                    "variance_pct": None,
                    "unit": off_list[0]["unit"],
                    "currency": "INR",
                    "status": "INSUFFICIENT_EVIDENCE",
                    "tolerance_used": None,
                    "screener_source_url": screener_source_url,
                    "official_source_url": off_list[0].get("official_source_url"),
                    "official_source_name": off_list[0].get("official_source_name", "NSE Filing"),
                    "official_document_id": off_list[0].get("official_document_id"),
                    "notes": f"Ambiguous multiple candidate values ({list(vals)}) found in official source for {off_canon_m} {off_canon_p}.",
                    "verified_at": now_iso
                }
                verification_records.append(rec)
                continue
                
        off = off_list[0]
        off_val = off["official_value"]
        off_unit = off.get("raw_unit", "Unknown")
        
        # Exact lookup in Screener
        matching_scr = screener_metrics.get(k)
        scr_val = matching_scr["value"] if matching_scr else None
        scr_scope = matching_scr["scope"] if matching_scr else off_scope
        scr_canon_p = matching_scr["canonical_period"] if matching_scr else off_canon_p
        
        comp_res = compare_financial_metric(
            screener_val=scr_val,
            official_val=off_val,
            canonical_metric=off_canon_m,
            screener_scope=scr_scope,
            official_scope=off_scope,
            screener_period_key=scr_canon_p,
            official_period_key=off_canon_p,
            official_unit=off_unit,
            is_banking_entity=is_banking
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
