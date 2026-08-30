"""
=============================================================================
Stocker Official Financial Verification Engine (Phase B)
=============================================================================
Provides deterministic normalization, authoritative metric comparison,
and provenance tracking between Screener.in standardized statements
and official corporate filings / exchange outcomes (NSE / BSE / IR).

Key Responsibilities:
1. Multi-Format Official Extraction:
   - XBRL / XML (Ind-AS official SEBI/MCA/NSE/BSE taxonomy)
   - Official Financial Result PDFs (Deterministic table/text extraction)
   - HTML Result Tables
   - Structured JSON APIs
2. Scope Grounding: Scope (Consolidated vs Standalone) extracted from filing body.
   If unknown -> NOT_COMPARABLE.
3. Unit Grounding: Level of rounding (₹ Cr, ₹ Lakh, ₹ Million) extracted from filing.
   If unknown -> INSUFFICIENT_EVIDENCE.
4. Period Grounding: Quarter / FY extracted from filing statement dates.
5. Conservative Metric Mapping: Only safe primary operating metrics verified:
   - Revenue from Operations / Sales
   - PAT / Net Profit
   - Basic / Diluted EPS
   - PBT
   (EBITDA / Operating Profit intentionally deferred for safety).
6. Clean Status Discrimination:
   - OFFICIAL_SOURCE_MISSING: No official filing exists.
   - INSUFFICIENT_EVIDENCE: Official filing exists but unsupported format or missing unit/scope.
   - NOT_COMPARABLE: Scope or Period mismatch.
   - VERIFIED / DISCREPANCY: Full alignment and tolerance check.
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
SAFE_CANONICAL_METRICS = ["REVENUE", "PBT", "PAT", "EPS"]

# Conservative Metric Mapping Dictionary (Safe unambiguous labels only)
CONSERVATIVE_METRIC_MAP: Dict[str, str] = {
    # Revenue / Sales
    "revenue from operations": "REVENUE",
    "net sales": "REVENUE",
    "sales": "REVENUE",
    "revenue": "REVENUE",
    "total income from operations": "REVENUE",
    "income from operations": "REVENUE",
    "revenuefromoperations": "REVENUE",
    "incomefromoperations": "REVENUE",
    
    # PBT
    "profit before tax": "PBT",
    "pbt": "PBT",
    "profit before exceptional items and tax": "PBT",
    "profit before tax and exceptional items": "PBT",
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
    
    # EPS
    "eps in rs": "EPS",
    "basic eps": "EPS",
    "diluted eps": "EPS",
    "eps": "EPS",
    "earnings per share": "EPS",
    "basicearningslosspershare": "EPS",
    "dilutedearningslosspershare": "EPS"
}

# Ambiguous line items that must NOT be mapped to canonical metrics
AMBIGUOUS_METRIC_KEYWORDS = [
    "ebit", "pbit", "ebitda", "operating profit", "operating profit before depreciation",
    "profit attributable to non-controlling", "exceptional items", "other income"
]

def normalize_metric_name(raw_metric: str) -> Optional[str]:
    """
    Conservatively maps raw filing metric names to canonical metric keys.
    Returns None if metric is ambiguous or deferred (e.g. EBITDA/Operating Profit).
    """
    if not raw_metric:
        return None
    clean = re.sub(r"[\(\)\[\],.:]", " ", raw_metric.lower()).strip()
    clean = re.sub(r"\s+", " ", clean)
    clean_no_space = re.sub(r"\s+", "", clean)
    
    # Reject ambiguous / deferred line items
    for amb in AMBIGUOUS_METRIC_KEYWORDS:
        if clean == amb or f" {amb} " in f" {clean} " or clean_no_space == re.sub(r"\s+", "", amb):
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

    # 3. Standard Month Year (e.g. 'Jun 2026', 'Quarter ended 30 June 2026', '30-Jun-2026')
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
    official_unit: str = "₹ Cr"
) -> Dict[str, Any]:
    """
    Evaluates Screener.in value against Official filing value with deterministic rules:
    - Scope alignment (Consolidated vs Standalone -> NOT_COMPARABLE)
    - Scope unknown -> NOT_COMPARABLE
    - Unit unknown -> INSUFFICIENT_EVIDENCE
    - Period alignment (e.g. 2026-Q1 vs 2026-Q2 -> NOT_COMPARABLE)
    - Mathematical tolerance: Δ <= max(abs_tolerance, official_value * pct_tolerance)
      - abs_tolerance: 1.0 (₹1 Cr) for financial totals, 0.05 for EPS
      - pct_tolerance: 0.5% (0.005) for financial totals, 1.0% for EPS
    """
    norm_scr_scope = (screener_scope or "Consolidated").capitalize().strip()
    norm_off_scope = (official_scope or "Unknown").capitalize().strip()
    
    # 1. Scope Unknown or Scope Mismatch
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
        
    # 2. Unit Unknown
    if official_unit in ("Unknown", "unknown", None, ""):
        return {
            "status": "INSUFFICIENT_EVIDENCE",
            "variance_abs": None,
            "variance_pct": None,
            "tolerance_used": None,
            "notes": "Cannot verify: Unit of measurement could not be deterministically established from official filing."
        }
        
    # 3. Period Mismatch
    if screener_period_key and official_period_key and screener_period_key != official_period_key:
        return {
            "status": "NOT_COMPARABLE",
            "variance_abs": None,
            "variance_pct": None,
            "tolerance_used": None,
            "notes": f"Period mismatch: Screener period ({screener_period_key}) does not align with official filing ({official_period_key})."
        }
    if official_period_key in ("Unknown", "unknown", ""):
        return {
            "status": "NOT_COMPARABLE",
            "variance_abs": None,
            "variance_pct": None,
            "tolerance_used": None,
            "notes": "Cannot verify: Reporting period could not be confidently determined from official filing."
        }
        
    # 4. Missing Value checks
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
        
    # 5. Tolerance calculation
    if canonical_metric == "EPS":
        abs_tolerance = 0.05
        pct_tolerance = 0.01 # 1% for EPS
    else:
        abs_tolerance = 1.0 # ₹1 Cr absolute tolerance
        pct_tolerance = 0.005 # 0.5% relative tolerance
        
    tolerance_allowed = max(abs_tolerance, abs(official_val) * pct_tolerance)
    variance_abs = round(abs(screener_val - official_val), 4)
    variance_pct = round((variance_abs / abs(official_val)) * 100, 2) if official_val != 0 else 0.0
    
    # 6. Verification Status
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
# DETERMINISTIC OFFICIAL FILING PARSERS (XBRL/XML, PDF, HTML, JSON)
# =============================================================================

def parse_official_xbrl_xml(
    xml_data: bytes,
    filing_ref: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Deterministically parses official Ind-AS XBRL XML corporate filing results.
    Extracts scope, reporting period, level of rounding unit, and safe financial rows.
    """
    doc = dict(filing_ref)
    doc["extraction_method"] = "official_xbrl_xml"
    table_rows: List[Dict[str, Any]] = []
    
    try:
        root = ET.fromstring(xml_data)
        
        # 1. Extract Scope (Consolidated vs Standalone)
        scope = "Unknown"
        for elem in root.iter():
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if tag in ("NatureOfReportStandaloneConsolidated", "NatureOfReport") and elem.text:
                t_val = elem.text.strip().capitalize()
                if "Consolidated" in t_val:
                    scope = "Consolidated"
                elif "Standalone" in t_val:
                    scope = "Standalone"
                break
        doc["scope"] = scope
        
        # 2. Extract Reporting Period Date
        period_str = filing_ref.get("reporting_period", "")
        for elem in root.iter():
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if tag in ("PeriodEndDate", "DateOfEndOfFinancialYear", "QuarterEnded") and elem.text:
                raw_date = elem.text.strip()
                # Parse date like 2026-06-30
                if re.match(r"\d{4}-\d{2}-\d{2}", raw_date):
                    parts = raw_date.split("-")
                    yr = parts[0]
                    mo = parts[1]
                    mo_map = {"03": "31 March", "06": "30 June", "09": "30 September", "12": "31 December"}
                    if mo in mo_map:
                        period_str = f"Quarter ended {mo_map[mo]} {yr}"
                break
        doc["reporting_period"] = period_str
        
        # 3. Extract Level of Rounding (Unit)
        unit = "Unknown"
        for elem in root.iter():
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if tag in ("LevelOfRounding", "UnitOfMeasurement") and elem.text:
                u_text = elem.text.strip().lower()
                if "crore" in u_text or "cr" in u_text:
                    unit = "₹ Cr"
                elif "lakh" in u_text:
                    unit = "₹ Lakhs"
                elif "million" in u_text or "mn" in u_text:
                    unit = "₹ Millions"
                elif "thousand" in u_text:
                    unit = "₹ Thousands"
                elif "rupee" in u_text or "single" in u_text or "exact" in u_text:
                    unit = "₹ Rupees"
                break
        doc["unit"] = unit
        
        # 4. Extract Safe Canonical Line Items
        for elem in root.iter():
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            canon_m = normalize_metric_name(tag)
            if canon_m and elem.text:
                try:
                    num_val = float(elem.text.strip())
                    table_rows.append({
                        "metric": tag,
                        "value": num_val
                    })
                except Exception:
                    pass
                    
        doc["financial_table"] = table_rows
    except Exception:
        doc["financial_table"] = []
        
    return doc

def parse_official_pdf_document(
    pdf_bytes: bytes,
    filing_ref: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Deterministically parses official PDF outcome filings using pypdf text extraction.
    Locates statement table, identifies scope, unit, period, and safe metric line items.
    """
    doc = dict(filing_ref)
    doc["extraction_method"] = "official_pdf_deterministic"
    table_rows: List[Dict[str, Any]] = []
    
    try:
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        full_text = ""
        for page in reader.pages:
            t = page.extract_text() or ""
            full_text += t + "\n"
            
        text_lower = full_text.lower()
        
        # 1. Determine Scope
        scope = "Unknown"
        if "consolidated financial results" in text_lower or "statement of consolidated" in text_lower:
            scope = "Consolidated"
        elif "standalone financial results" in text_lower or "statement of standalone" in text_lower:
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
            elif "thousand" in u_word:
                unit = "₹ Thousands"
        doc["unit"] = unit
        
        # 3. Determine Period
        period_str = filing_ref.get("reporting_period", "")
        period_match = re.search(r"(?:quarter|three\s*months|year|12\s*months)\s*ended\s*(\d{1,2}(?:st|nd|rd|th)?\s+[a-zA-Z]+\s+\d{4})", text_lower)
        if period_match:
            period_str = f"Quarter ended {period_match.group(1).title()}"
        doc["reporting_period"] = period_str
        
        # 4. Extract Safe Line Items from PDF Text
        # Look for lines containing metric name followed by numeric figures
        lines = full_text.split("\n")
        for line in lines:
            line_clean = line.strip()
            if not line_clean:
                continue
                
            canon_m = normalize_metric_name(line_clean.split("  ")[0] if "  " in line_clean else line_clean[:40])
            if canon_m:
                # Find all numbers on this line
                nums = re.findall(r"[-+]?[0-9,]+(?:\.[0-9]+)?", line_clean)
                if nums:
                    try:
                        # Latest reported quarter/period figure is usually first column
                        val_str = nums[0].replace(",", "")
                        num_val = float(val_str)
                        table_rows.append({
                            "metric": line_clean[:50].strip(),
                            "value": num_val
                        })
                    except Exception:
                        pass
                        
        doc["financial_table"] = table_rows
    except Exception:
        doc["financial_table"] = []
        
    return doc

def parse_official_html_table(
    html_data: bytes,
    filing_ref: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Deterministically parses official HTML financial result announcements with BeautifulSoup.
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
        
        # 3. Locate Financial Result Table & Rows
        tables = soup.find_all("table")
        for table in tables:
            for row in table.find_all("tr"):
                cells = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
                if len(cells) >= 2:
                    m_label = cells[0]
                    canon_m = normalize_metric_name(m_label)
                    if canon_m:
                        num_str = cells[1].replace(",", "")
                        try:
                            num_val = float(num_str)
                            table_rows.append({
                                "metric": m_label,
                                "value": num_val
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
                        "scope": "Consolidated" if "consolidated" in desc.lower() else ("Standalone" if "standalone" in desc.lower() else "Unknown"),
                        "source_name": "NSE Corporate Filing",
                        "source_url": full_url or url,
                        "actual_source_url": full_url or url,
                        "unit": "₹ Cr",
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
    Supports XBRL/XML, PDF, HTML, and JSON payloads.
    """
    if not filing_ref:
        return None
        
    # If filing already contains extracted table rows (from mock fixture or structured API)
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
                
            # Format 4: JSON REST Response
            elif "application/json" in content_type or source_url.endswith(".json"):
                parsed_json = json.loads(raw_bytes.decode("utf-8"))
                filing_doc = dict(filing_ref)
                filing_doc["financial_table"] = parsed_json.get("rows", [])
                filing_doc["extraction_method"] = "official_json_api"
                return filing_doc
    except Exception:
        pass
        
    # If format is unsupported or network request failed
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
    scope = filing_doc.get("scope", "Unknown")
    period_raw = filing_doc.get("reporting_period", "")
    disp_period, canon_period = normalize_period(period_raw)
    raw_unit = filing_doc.get("unit", "₹ Cr")
    source_url = filing_doc.get("source_url") or filing_doc.get("actual_source_url")
    source_name = filing_doc.get("source_name", "NSE Filing")
    doc_id = filing_doc.get("document_id") or filing_doc.get("document_title")
    ext_method = filing_doc.get("extraction_method", "deterministic")
    
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
                "raw_unit": raw_unit,
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
    
    # 2. Extract Screener reported metrics with actual statement scope
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
        summary["unavailable_reason"] = "Official filing was retrieved but contains unsupported formatting or missing numerical tables."
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
        off_unit = off.get("raw_unit", "₹ Cr")
        
        # Find matching Screener candidates for this metric
        scr_candidates = screener_metrics.get(off_canon_m, [])
        
        matching_scr = None
        for cand in scr_candidates:
            if cand["canonical_period"] == off_canon_p:
                matching_scr = cand
                break
                
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
            official_period_key=off_canon_p,
            official_unit=off_unit
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
