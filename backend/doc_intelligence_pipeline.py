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

def format_financials_for_prompt(symbol: str, stock_data: Optional[Dict[str, Any]] = None) -> str:
    """Formats 10-year P&L, Balance Sheet, Cash Flow, and Quarters into a clean prompt context table."""
    clean_sym = symbol.upper().strip()
    data = stock_data or database.get_stock_cache(clean_sym)
    if not data:
        try:
            data = fetch_stock_from_screener(clean_sym, force_refresh=False)
        except Exception:
            data = None

    if not data:
        return "Standardized financial statements not available in database."

    pl_data = data.get("profit_loss") or data.get("profit_and_loss")
    bs_data = data.get("balance_sheet")
    cf_data = data.get("cash_flow")
    q_data = data.get("quarters")

    lines = [f"=== STANDARDIZED 10-YEAR FINANCIAL STATEMENTS ({clean_sym}) ==="]

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

    # 2. Balance Sheet Summary
    bs_years, bs_rows = _extract_statement_table(bs_data)
    if bs_years:
        eq = bs_rows.get("Equity Capital", []) or bs_rows.get("Share Capital", [])
        res = bs_rows.get("Reserves", [])
        borr = bs_rows.get("Borrowings", []) or bs_rows.get("Total Debt", [])
        fa = bs_rows.get("Fixed Assets", [])
        cwip = bs_rows.get("CWIP", [])
        tot_a = bs_rows.get("Total Assets", [])

        lines.append("\n[Balance Sheet Position (₹ in Crores)]")
        header = f"{'Metric':<18} | " + " | ".join(f"{str(y):>8}" for y in bs_years[-6:])
        lines.append(header)
        lines.append("-" * len(header))
        if eq: lines.append(f"{'Equity Capital':<18} | " + " | ".join(f"{str(v or '-'):>8}" for v in eq[-6:]))
        if res: lines.append(f"{'Reserves':<18} | " + " | ".join(f"{str(v or '-'):>8}" for v in res[-6:]))
        if borr: lines.append(f"{'Borrowings':<18} | " + " | ".join(f"{str(v or '-'):>8}" for v in borr[-6:]))
        if fa: lines.append(f"{'Fixed Assets':<18} | " + " | ".join(f"{str(v or '-'):>8}" for v in fa[-6:]))
        if cwip: lines.append(f"{'CWIP':<18} | " + " | ".join(f"{str(v or '-'):>8}" for v in cwip[-6:]))
        if tot_a: lines.append(f"{'Total Assets':<18} | " + " | ".join(f"{str(v or '-'):>8}" for v in tot_a[-6:]))

    # 3. Cash Flow Generation
    cf_years, cf_rows = _extract_statement_table(cf_data)
    if cf_years:
        cfo = cf_rows.get("Cash from Operating Activity", []) or cf_rows.get("CFO", [])
        cfi = cf_rows.get("Cash from Investing Activity", []) or cf_rows.get("CFI", [])
        cff = cf_rows.get("Cash from Financing Activity", []) or cf_rows.get("CFF", [])
        fa_purch = cf_rows.get("Fixed assets purchased", []) or cf_rows.get("Capex", [])

        lines.append("\n[Cash Flow Generation (₹ in Crores)]")
        header = f"{'Metric':<18} | " + " | ".join(f"{str(y):>8}" for y in cf_years[-6:])
        lines.append(header)
        lines.append("-" * len(header))
        if cfo: lines.append(f"{'Cash from Ops':<18} | " + " | ".join(f"{str(v or '-'):>8}" for v in cfo[-6:]))
        if fa_purch: lines.append(f"{'Capex Outlay':<18} | " + " | ".join(f"{str(v or '-'):>8}" for v in fa_purch[-6:]))
        if cfi: lines.append(f"{'Cash from Inv':<18} | " + " | ".join(f"{str(v or '-'):>8}" for v in cfi[-6:]))
        if cff: lines.append(f"{'Cash from Fin':<18} | " + " | ".join(f"{str(v or '-'):>8}" for v in cff[-6:]))

    # 4. Recent Quarterly Trend
    q_periods, q_rows = _extract_statement_table(q_data)
    if q_periods:
        q_sales = q_rows.get("Sales", []) or q_rows.get("Revenue", [])
        q_op = q_rows.get("Operating Profit", []) or q_rows.get("EBITDA", [])
        q_opm = q_rows.get("OPM %", []) or q_rows.get("OPM", [])
        q_pat = q_rows.get("Net Profit", []) or q_rows.get("PAT", [])

        lines.append("\n[Recent Quarterly Performance (₹ in Crores)]")
        header = f"{'Metric':<18} | " + " | ".join(f"{str(q):>8}" for q in q_periods[-6:])
        lines.append(header)
        lines.append("-" * len(header))
        if q_sales: lines.append(f"{'Qtr Sales':<18} | " + " | ".join(f"{str(v or '-'):>8}" for v in q_sales[-6:]))
        if q_op: lines.append(f"{'Qtr EBITDA':<18} | " + " | ".join(f"{str(v or '-'):>8}" for v in q_op[-6:]))
        if q_opm: lines.append(f"{'Qtr OPM %':<18} | " + " | ".join(f"{str(v or '-'):>8}" for v in q_opm[-6:]))
        if q_pat: lines.append(f"{'Qtr PAT':<18} | " + " | ".join(f"{str(v or '-'):>8}" for v in q_pat[-6:]))

    return "\n".join(lines)

# Backward-compatibility alias
format_audited_financials_for_prompt = format_financials_for_prompt

def calculate_announcement_materiality(title: str, text: str = "") -> Tuple[int, str]:
    """
    Evaluates corporate announcements for financial and operational materiality.
    Returns (score, reason).
    High materiality items (score >= 10) enter the default AI working set (up to 3-5).
    Routine items (score < 10) are retained in the archive only.
    """
    combined = f"{title or ''} {text or ''}".lower()

    # 1. Immediate Exclusions / Routine compliance (Score 0)
    if any(k in combined for k in [
        "trading window", "newspaper publication", "loss of share", "duplicate share",
        "allotment of esop", "esop / esps", "esps", "schedule of analyst",
        "intimation of analyst meet", "investor meet intimation", "investor meet",
        "scrutinizer", "postal ballot", "general meeting intimation", "procedural"
    ]):
        return (0, "Routine procedural / compliance announcement")

    if any(k in combined for k in ["acquisition", "amalgamation", "merger", "takeover", "slump sale", "divestment"]):
        return (30, "M&A / Acquisition / Divestment")
    if any(k in combined for k in ["penalty", "regulatory action", "rbi order", "sebi order", "adjudication", "warning letter"]):
        return (25, "Regulatory action / Penalty / Order")
    if any(k in combined for k in ["credit rating", "rating action", "rating upgrade", "rating downgrade"]):
        return (25, "Credit rating action")
    if any(k in combined for k in ["outcome of board meeting", "outcome of the board meeting", "board meeting outcome"]):
        return (20, "Board meeting outcome / Key corporate action")
    if any(k in combined for k in ["order win", "contract win", "bagged order", "major contract", "award of contract"]):
        return (20, "Major contract / Order win")
    if any(k in combined for k in ["fund raise", "qip", "bonds", "notes issuance", "senior notes", "capital raise", "rights issue", "preferential issue"]):
        return (20, "Capital raise / Debt financing")
    if any(k in combined for k in [
        "appointment of managing director", "resignation of managing director",
        "appointment of ceo", "resignation of ceo",
        "appointment of cfo", "resignation of cfo",
        "appointment of executive director", "resignation of executive director",
        "key managerial personnel"
    ]):
        return (20, "C-Suite executive management change")
    if any(k in combined for k in ["capacity", "capex", "commissioning", "new plant", "new unit", "commercial production"]):
        return (20, "Major Capex / Capacity addition")
    if any(k in combined for k in ["litigation", "court order", "nclt", "arbitration", "stay order"]):
        return (15, "Material litigation / Court order")
    if any(k in combined for k in ["profit warning", "material update", "business update"]):
        return (15, "Material business update")

    # Default for other announcements
    return (5, "General corporate disclosure")

def assign_working_set_metadata(documents: DocumentLinks) -> List[DocumentItem]:
    """
    Authoritative Working Set Assignor:
    Evaluates and assigns auditable metadata (selected_for_ai, ai_priority, selection_reason)
    across all document categories according to Stocker's approved AI Working Set policy:
    1. Annual Reports: Latest 2 substantive Annual Reports (latest state + previous-year baseline)
    2. Regulatory Filings (20-F): Latest 1 unique substantive 20-F filing (if distinct from AR)
    3. Concalls: Latest 4 earnings quarters (analyst/investor transcripts prioritized; media calls in archive)
    4. Investor Presentations: Latest 4 earnings quarters (substantive presentations)
    5. Material Announcements: Maximum 3-5 high-materiality announcements (M&A, Capex, Reg/Rating/C-Suite)
    6. BRSR / ESG: 0 by default (archive only, on-demand/ESG escalation only)
    7. Routine notices / Wrappers: 0 (archive only)

    Returns the list of selected DocumentItems sorted by ai_priority (1..N).
    """
    selected_items: List[DocumentItem] = []
    priority_counter = 1

    def is_substantive_eligible(d: DocumentItem) -> bool:
        return (
            getattr(d, "ai_eligible", True)
            and not getattr(d, "is_wrapper", False)
            and getattr(d, "is_substantive", True)
            and getattr(d, "is_valid", 1) in (1, True, "1", "Valid")
        )

    # 1. ANNUAL REPORTS: Latest 2 substantive
    ars = documents.annual_reports or []
    substantive_ars = [d for d in ars if is_substantive_eligible(d)]
    for idx, d in enumerate(ars):
        if d in substantive_ars[:2]:
            d.selected_for_ai = True
            d.ai_priority = priority_counter
            priority_counter += 1
            if d == substantive_ars[0]:
                d.selection_reason = "Latest Annual Report"
            else:
                d.selection_reason = "Previous Annual Report baseline"
            selected_items.append(d)
        else:
            d.selected_for_ai = False
            d.ai_priority = None
            if getattr(d, "is_wrapper", False):
                d.selection_reason = "Wrapper notification; substantive report resolved"
            else:
                d.selection_reason = "Older Annual Report (on-demand archive)"

    # 2. REGULATORY ANNUAL FILINGS (20-F): Latest 1 unique
    regs = getattr(documents, "regulatory_annual_filings", None) or []
    substantive_regs = [d for d in regs if is_substantive_eligible(d)]
    selected_ar_urls = {d.url for d in selected_items if d.doc_type == "annual_report"}
    distinct_regs = [d for d in substantive_regs if d.url not in selected_ar_urls]
    for idx, d in enumerate(regs):
        if d in distinct_regs[:1]:
            d.selected_for_ai = True
            d.ai_priority = priority_counter
            priority_counter += 1
            d.selection_reason = "Latest Form 20-F regulatory filing"
            selected_items.append(d)
        else:
            d.selected_for_ai = False
            d.ai_priority = None
            if getattr(d, "is_wrapper", False):
                d.selection_reason = "Wrapper notification"
            elif d.url in selected_ar_urls:
                d.selection_reason = "Duplicate of selected Annual Report"
            else:
                d.selection_reason = "Older regulatory filing (on-demand archive)"

    # 3. CONCALL TRANSCRIPTS: Latest 4 DISTINCT earnings events (prefer substantive analyst/investor)
    ccs = documents.concalls or []
    sorted_ccs = sorted(ccs, key=lambda x: (getattr(x, "sort_timestamp", None) or "1970-01-01", x.title), reverse=True)

    seen_cc_events: Set[str] = set()
    selected_cc_urls: Set[str] = set()

    # First pass: pick ONE preferred substantive analyst/investor transcript per distinct event
    for d in sorted_ccs:
        if not is_substantive_eligible(d):
            continue
        subtype = getattr(d, "doc_subtype", None)
        if subtype == "media_call_transcript":
            continue

        ev_key = getattr(d, "event_key", None)
        effective_event = ev_key if (ev_key and not ev_key.endswith("_GENERIC")) else f"PHYSICAL_EVENT_{d.url}"

        if effective_event not in seen_cc_events and len(seen_cc_events) < 4:
            seen_cc_events.add(effective_event)
            selected_cc_urls.add(d.url)

    # Assign metadata to all concalls preserving chronological order
    for d in sorted_ccs:
        if d.url in selected_cc_urls:
            d.selected_for_ai = True
            d.ai_priority = priority_counter
            priority_counter += 1
            d.selection_reason = f"{d.period_or_date or 'Recent'} earnings conference call transcript"
            selected_items.append(d)
        elif getattr(d, "doc_subtype", None) == "media_call_transcript":
            d.selected_for_ai = False
            d.ai_priority = None
            d.selection_reason = "Media call retained in archive (analyst transcript prioritized for AI)"
        elif getattr(d, "is_wrapper", False):
            d.selected_for_ai = False
            d.ai_priority = None
            d.selection_reason = "Wrapper notification; substantive transcript resolved"
        else:
            ev_key = getattr(d, "event_key", None)
            effective_event = ev_key if (ev_key and not ev_key.endswith("_GENERIC")) else None
            d.selected_for_ai = False
            d.ai_priority = None
            if effective_event and effective_event in seen_cc_events:
                d.selection_reason = "Secondary transcript for already selected earnings quarter"
            else:
                d.selection_reason = "Older than default 4-quarter transcript window"

    # 4. INVESTOR PRESENTATIONS: Latest 4 DISTINCT earnings events (EARNINGS_PRESENTATION only)
    ppts = documents.presentations or []
    sorted_ppts = sorted(ppts, key=lambda x: (getattr(x, "sort_timestamp", None) or "1970-01-01", x.title), reverse=True)

    # Collect known earnings events from concalls & quarterly results
    known_earnings_events: Dict[str, str] = {}
    for cc in (documents.concalls or []):
        cc_ev = getattr(cc, "event_key", None)
        if not cc_ev or cc_ev.endswith("_GENERIC"):
            cc_sym = getattr(cc, "ticker", None) or getattr(cc, "symbol", None) or clean_sym
            cc_ev = database.derive_earnings_event_key(cc_sym, cc.period_or_date, cc.title)
        if cc_ev and not cc_ev.endswith("_GENERIC"):
            known_earnings_events[cc_ev] = cc.period_or_date or ""
    regs = getattr(documents, "regulatory_annual_filings", None) or getattr(documents, "regulatory_filings", None) or []
    for reg in regs:
        reg_ev = getattr(reg, "event_key", None)
        if not reg_ev or reg_ev.endswith("_GENERIC"):
            reg_sym = getattr(reg, "ticker", None) or getattr(reg, "symbol", None) or clean_sym
            reg_ev = database.derive_earnings_event_key(reg_sym, reg.period_or_date, reg.title)
        if reg_ev and not reg_ev.endswith("_GENERIC"):
            known_earnings_events[reg_ev] = reg.period_or_date or ""

    seen_ppt_events: Set[str] = set()
    selected_ppt_urls: Set[str] = set()

    for d in sorted_ppts:
        if not is_substantive_eligible(d):
            continue
        subtype = getattr(d, "doc_subtype", None) or database.derive_document_subtype("presentation", d.title, d.period_or_date)
        d.doc_subtype = subtype
        if subtype in ("agm_presentation", "investor_day_presentation", "debt_presentation"):
            continue

        ev_key = getattr(d, "event_key", None)
        if not ev_key or ev_key.endswith("_GENERIC"):
            sym = getattr(d, "ticker", None) or getattr(d, "symbol", None) or clean_sym
            derived_ev = database.derive_earnings_event_key(sym, d.period_or_date, d.title)
            if derived_ev and not derived_ev.endswith("_GENERIC"):
                ev_key = derived_ev
                d.event_key = ev_key

        # Presentation qualifies as earnings_presentation under Conditions A, B, or C:
        # A: explicit earnings / quarter in title/metadata
        cond_a = (subtype == "earnings_presentation")
        # B: Official Company IR / exchange quarterly-results context associates document with exact earnings quarter
        u_low = (getattr(d, "actual_source_url", None) or d.url or "").lower()
        disc_low = (getattr(d, "discovery_source", None) or "").lower()
        cond_b = any(kw in u_low for kw in ["quarterly-results", "quarterly_results", "earnings", "results-reports"]) or \
                 ("company ir" in disc_low and bool(ev_key and not ev_key.endswith("_GENERIC")))
        # C: Shares resolved exact earnings event with earnings transcript / quarterly results
        cond_c = bool(ev_key and not ev_key.endswith("_GENERIC") and ev_key in known_earnings_events)

        if cond_a or cond_b or cond_c:
            d.doc_subtype = "earnings_presentation"
            if not d.period_or_date and ev_key and ev_key in known_earnings_events:
                d.period_or_date = known_earnings_events[ev_key]
        else:
            continue

        # Must strictly have resolved non-generic event key (NO physical URL fallback)
        if not ev_key or ev_key.endswith("_GENERIC"):
            continue

        if ev_key not in seen_ppt_events and len(seen_ppt_events) < 4:
            seen_ppt_events.add(ev_key)
            selected_ppt_urls.add(d.url)

    for d in sorted_ppts:
        subtype = getattr(d, "doc_subtype", None) or database.derive_document_subtype("presentation", d.title, d.period_or_date)
        d.doc_subtype = subtype
        if d.url in selected_ppt_urls:
            d.selected_for_ai = True
            d.ai_priority = priority_counter
            priority_counter += 1
            d.selection_reason = f"{d.period_or_date or 'Recent'} earnings presentation"
            selected_items.append(d)
        elif subtype == "agm_presentation":
            d.selected_for_ai = False
            d.ai_priority = None
            d.selection_reason = "AGM presentation retained in archive (quarterly earnings presentation prioritized for AI)"
        elif subtype == "investor_day_presentation":
            d.selected_for_ai = False
            d.ai_priority = None
            d.selection_reason = "Strategy / Investor Day presentation retained in archive"
        elif subtype == "debt_presentation":
            d.selected_for_ai = False
            d.ai_priority = None
            d.selection_reason = "Debt / Fixed Income presentation retained in archive (quarterly earnings presentation prioritized for AI)"
        elif subtype in ("other_presentation", "unknown_presentation"):
            d.selected_for_ai = False
            d.ai_priority = None
            d.selection_reason = "General / unresolved presentation retained in archive (requires quarterly earnings event resolution for AI working set)"
        elif getattr(d, "is_wrapper", False):
            d.selected_for_ai = False
            d.ai_priority = None
            d.selection_reason = "Wrapper notification"
        else:
            ev_key = getattr(d, "event_key", None)
            effective_event = ev_key if (ev_key and not ev_key.endswith("_GENERIC")) else None
            d.selected_for_ai = False
            d.ai_priority = None
            if not effective_event:
                d.selection_reason = "Unresolved earnings event presentation retained in archive"
            elif effective_event in seen_ppt_events:
                d.selection_reason = "Secondary presentation for already selected earnings quarter"
            else:
                d.selection_reason = "Older than default 4-quarter presentation window"

    # 5. ANNOUNCEMENTS: Max 5 High-Materiality DISTINCT EVENTS (Ranked deterministically by score desc, date desc, stable key)
    # Enforce event-family diversity and supersede board intimation with board outcome
    anns = documents.material_announcements or []
    scored_anns = []

    def _classify_ann_event_family(title: str) -> str:
        t = (title or "").lower()
        if "rating" in t or "credit rating" in t:
            return "RATING_ACTION"
        if any(k in t for k in ["fund raising", "fund raise", "raising of funds", "capital raise", "ncd", "bond"]):
            return "FUND_RAISE"
        if "board meeting" in t or "outcome of" in t:
            return "BOARD_MEETING"
        if any(k in t for k in ["acquisition", "amalgamation", "merger", "slump sale", "joint venture"]):
            return "MA_ACQUISITION"
        if any(k in t for k in ["order", "contract", "award", "agreement"]):
            return "ORDER_CONTRACT"
        if any(k in t for k in ["regulatory", "rbi", "sebi", "penalty", "inspection"]):
            return "REGULATORY_LEGAL"
        return "GENERAL_DISCLOSURE"

    for d in anns:
        score, reason = calculate_announcement_materiality(d.title)
        sort_ts = getattr(d, "sort_timestamp", None) or getattr(d, "period_or_date", "") or "1970-01-01"
        stable_key = getattr(d, "doc_key", None) or d.url or d.title or ""
        # Assign materiality metadata on document item
        d.materiality_score = score
        d.materiality_level = "HIGH" if score >= 10 else ("MEDIUM" if score >= 5 else "ROUTINE")
        d.materiality_reason = reason

        # Determine distinct material event identity
        sym = getattr(d, "ticker", "") or getattr(d, "symbol", "") or clean_sym
        event_key = database.derive_announcement_event_key(sym, d.title, d.period_or_date)
        family = _classify_ann_event_family(d.title)
        scored_anns.append((d, score, reason, sort_ts, stable_key, event_key, family))

    # Filter eligible high-materiality announcements (score >= 10)
    high_mat_anns = [
        item for item in scored_anns
        if item[1] >= 10 and is_substantive_eligible(item[0])
    ]

    # Sort deterministically:
    # 1. materiality score descending
    # 2. publication / sort timestamp descending
    # 3. stable key tie-break
    high_mat_anns.sort(
        key=lambda x: (x[1], x[3], x[4]),
        reverse=True
    )

    # Event-family diversity and intimation supersession:
    # - If a board outcome is present for fund-raising or board action, it supersedes earlier prior intimation
    has_board_outcome = any(
        "outcome" in item[0].title.lower() for item in high_mat_anns
    )

    selected_high_mat_docs = []
    selected_high_mat_urls = set()
    seen_ann_events: Set[str] = set()
    family_counts: Dict[str, int] = {}

    for item in high_mat_anns:
        doc_obj, score, reason, sort_ts, stable_key, ev_key, family = item
        t_low = doc_obj.title.lower()

        # Intimation supersession: discard prior intimation if substantive outcome is available
        if has_board_outcome and any(k in t_low for k in ["prior intimation", "intimation of board", "intimation under regulation 29"]):
            continue

        # Cap rating actions to at most 1 slot in the 5-slot working set to ensure event diversity
        if family == "RATING_ACTION" and family_counts.get("RATING_ACTION", 0) >= 1:
            continue

        # Cap fund raise / board meeting to at most 1 slot
        if family in ("FUND_RAISE", "BOARD_MEETING") and (family_counts.get("FUND_RAISE", 0) + family_counts.get("BOARD_MEETING", 0)) >= 2:
            continue

        if ev_key not in seen_ann_events and len(selected_high_mat_docs) < 5:
            seen_ann_events.add(ev_key)
            family_counts[family] = family_counts.get(family, 0) + 1
            selected_high_mat_docs.append(item)
            selected_high_mat_urls.add(doc_obj.url)

    # Assign priority in ranked materiality order
    for d, score, reason, sort_ts, stable_key, ev_key, family in selected_high_mat_docs:
        d.selected_for_ai = True
        d.ai_priority = priority_counter
        priority_counter += 1
        d.selection_reason = f"High-materiality: {reason}"
        selected_items.append(d)

    # Mark unselected announcements
    for d, score, reason, sort_ts, stable_key, ev_key, family in scored_anns:
        if d.url not in selected_high_mat_urls:
            d.selected_for_ai = False
            d.ai_priority = None
            if score < 10:
                d.selection_reason = f"Routine announcement: {reason}"
            elif ev_key in seen_ann_events:
                d.selection_reason = "Follow-up disclosure for already selected material event"
            else:
                d.selection_reason = "Beyond top 5 distinct material announcement events"

    # 6. BRSR / ESG: 0 by default (archive only)
    brsrs = getattr(documents, "brsr_reports", None) or []
    for d in brsrs:
        d.selected_for_ai = False
        d.ai_priority = None
        d.selection_reason = "BRSR excluded from default AI working set (on-demand / ESG escalated only)"

    # 7. OTHER GENERAL FILINGS: 0 by default
    others = getattr(documents, "other_filings", None) or []
    for d in others:
        d.selected_for_ai = False
        d.ai_priority = None
        d.selection_reason = "General corporate filing (archive only)"

    # Also synchronize all_documents
    if getattr(documents, "all_documents", None):
        for d in documents.all_documents:
            matched = next((s for s in selected_items if getattr(s, "doc_key", None) == getattr(d, "doc_key", None) or s.url == d.url), None)
            if matched:
                d.selected_for_ai = True
                d.ai_priority = matched.ai_priority
                d.selection_reason = matched.selection_reason
            elif not getattr(d, "selection_reason", None):
                cat_doc = next((
                    item for item in (ars + regs + ccs + ppts + anns + brsrs + others)
                    if getattr(item, "doc_key", None) == getattr(d, "doc_key", None) or item.url == d.url
                ), None)
                if cat_doc:
                    d.selected_for_ai = getattr(cat_doc, "selected_for_ai", False)
                    d.ai_priority = getattr(cat_doc, "ai_priority", None)
                    d.selection_reason = getattr(cat_doc, "selection_reason", None)

    selected_items.sort(key=lambda x: x.ai_priority or 999)
    return selected_items

def select_default_document_working_set(documents: DocumentLinks) -> List[DocumentItem]:
    """
    Authoritative Working Set Selector:
    Returns exactly the documents marked selected_for_ai=True, sorted by ai_priority.
    """
    return assign_working_set_metadata(documents)

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
    Strictly verifies content hash against extracted document text to prevent stale cache reuse on changed PDF content.
    Implements deterministic Alternate Source Recovery (stored corpus + on-demand discovery) if convenience PDF download fails.
    """
    from llm_service import EXTRACTION_SCHEMA_VERSION, EXTRACTION_PROMPT_VERSION
    import document_sourcing

    clean_sym = symbol.upper().strip()
    doc_k = getattr(doc, "doc_key", None) or database.compute_canonical_document_key(clean_sym, doc.doc_type, doc.period_or_date, doc.url, doc.title)
    doc.doc_key = doc_k

    # 1. Download and extract pages with explicit provenance tracking
    pages = None
    content_source = "LOCAL_PAGE_CACHE"
    remote_verified = False
    download_err = None
    original_url = doc.url
    active_url = doc.url

    try:
        pages, content_source, remote_verified = download_and_extract_pdf_with_provenance(active_url, symbol=clean_sym)
    except Exception as e:
        download_err = e
        print(f"    ⚠️ Could not extract text for {doc.title} from {active_url}: {e}")

    # If initial URL download failed, attempt Alternate Source Recovery:
    # Gather candidates from BOTH stored database corpus and on-demand live discovery.
    # Try all candidates in preference order, continuing to the next candidate on 404/failure.
    if not pages:
        norm_dt = database.normalize_document_type(doc.doc_type, doc.title)
        subtype = getattr(doc, "doc_subtype", None) or database.derive_document_subtype(norm_dt, doc.title, doc.period_or_date)
        ev_key = getattr(doc, "event_key", None)

        candidates = []
        # 1. Stored DB alternates
        try:
            stored_alts = database.find_substantive_alternate_sources(
                symbol=clean_sym,
                doc_type=norm_dt,
                doc_subtype=subtype,
                event_key=ev_key,
                period_or_date=doc.period_or_date,
                failed_url=original_url
            )
            for sa in stored_alts:
                candidates.append({
                    "url": sa["url"],
                    "title": sa.get("title", doc.title),
                    "source": sa.get("discovery_source", "Stored Alternate")
                })
        except Exception as e_sa:
            print(f"    ⚠️ Error querying stored alternates: {e_sa}")

        # 2. On-demand live alternate filing discovery
        try:
            discovered_alts = document_sourcing.discover_substantive_alternate_candidates(
                symbol=clean_sym,
                company_name=company_name,
                doc_type=norm_dt,
                doc_subtype=subtype,
                period_or_date=doc.period_or_date,
                event_key=ev_key,
                failed_url=original_url
            )
            for da in discovered_alts:
                candidates.append({
                    "url": da.url,
                    "title": da.title,
                    "source": da.discovery_source or "Discovered Alternate"
                })
        except Exception as e_da:
            print(f"    ⚠️ Error in on-demand alternate discovery: {e_da}")

        # Deduplicate candidates while preserving order
        seen_cand_urls = set()
        deduped_candidates = []
        for c in candidates:
            c_u = (c["url"] or "").strip().rstrip("/")
            if c_u and c_u != original_url.strip().rstrip("/") and c_u not in seen_cand_urls:
                seen_cand_urls.add(c_u)
                deduped_candidates.append(c)

        # Sort candidates by preference:
        # 1. Current official company IR domain (e.g. icici.bank.in) -> pref 4
        # 2. BSE -> pref 3
        # 3. NSE -> pref 2
        # 4. Other IR domain -> pref 1
        def _cand_pref_score(c: Dict[str, Any]) -> int:
            u = c["url"].lower()
            if "bank.in" in u:
                return 4
            if "bseindia" in u or "bse.com" in u:
                return 3
            if "nseindia" in u:
                return 2
            if "icicibank.com" in u:
                return 1
            return 0

        deduped_candidates.sort(key=_cand_pref_score, reverse=True)

        # Robust loop: try each candidate in order. A 404 on an old URL does NOT stop us from trying BSE!
        for cand in deduped_candidates:
            alt_url = cand["url"]
            print(f"    🔄 Attempting Alternate Source Recovery for {doc.title}: {alt_url}")
            try:
                cand_pages, cand_source, cand_remote_verified = download_and_extract_pdf_with_provenance(alt_url, symbol=clean_sym)
                if cand_pages:
                    pages = cand_pages
                    content_source = cand_source
                    remote_verified = cand_remote_verified
                    active_url = alt_url
                    if not doc.source_aliases:
                        doc.source_aliases = []
                    if original_url not in doc.source_aliases:
                        doc.source_aliases.append(original_url)
                    if not doc.discovered_sources:
                        doc.discovered_sources = []
                    if cand["source"] not in doc.discovered_sources:
                        doc.discovered_sources.append(cand["source"])
                    print(f"    ✅ Alternate Source Recovery Succeeded for {doc.title} via {alt_url}")
                    # Persist successful candidate document to SQLite so future runs know the working canonical URL
                    cand_item = DocumentItem(
                        ticker=clean_sym,
                        title=cand.get("title") or doc.title,
                        url=alt_url,
                        doc_type=doc.doc_type,
                        period_or_date=doc.period_or_date,
                        discovery_source=cand.get("source") or "Alternate Recovery",
                        actual_source_url=alt_url,
                        validation_status="Valid"
                    )
                    database.save_source_documents(clean_sym, [cand_item])
                    break
            except Exception as e_alt:
                print(f"    ⚠️ Candidate alternate {alt_url} failed ({e_alt}). Continuing to next candidate...")
                download_err = e_alt

    if not pages:
        print(f"    ⚠️ Skipping summary for {doc.title}: No text extracted from {active_url}")
        failed_sum = {
            "doc_title": doc.title,
            "doc_url": doc.url,
            "doc_key": doc_k,
            "doc_type": doc.doc_type,
            "period_or_date": doc.period_or_date,
            "status": "failed",
            "error": f"Failed to download/extract PDF: {download_err or 'No pages found'}",
            "key_takeaways": []
        }
        database.save_document_summary(clean_sym, doc.url, doc.title, failed_sum, doc_key=doc_k, doc_type=doc.doc_type, period_or_date=doc.period_or_date)
        return failed_sum

    # 2. Compute deterministic content hash from extracted pages
    current_content_hash = database.compute_document_content_hash(pages)

    # 3. Check SQLite cache with exact content hash and extraction version verification
    cached = database.get_document_summary(
        active_url,
        doc_key=doc_k,
        symbol=clean_sym,
        doc_type=doc.doc_type,
        period_or_date=doc.period_or_date,
        expected_content_hash=current_content_hash,
        expected_schema_version=EXTRACTION_SCHEMA_VERSION,
        expected_prompt_version=EXTRACTION_PROMPT_VERSION
    )
    if cached and cached.get("key_takeaways"):
        cached["doc_key"] = doc_k
        cached["content_hash"] = current_content_hash
        doc.content_hash = current_content_hash

        # Provenance-aware cache status assignment:
        # Only label CURRENT_CONTENT_VERIFIED if remote resource was actually fetched/validated in this run.
        # If only previously cached extracted pages were available, mark CURRENT_VERSION_CONTENT_UNCHECKED.
        if remote_verified or content_source == "REMOTE_FETCH":
            cache_st = "CURRENT_CONTENT_VERIFIED"
        else:
            cache_st = "CURRENT_VERSION_CONTENT_UNCHECKED"

        doc.cache_status = cache_st
        cached["cache_status"] = cache_st
        if doc.source_aliases:
            cached["source_aliases"] = list(doc.source_aliases)
        if doc.discovered_sources:
            cached["discovered_sources"] = list(doc.discovered_sources)
        return cached

    # 4. Select high-signal pages for summarization
    is_ar = (doc.doc_type == "annual_report" or len(pages) > 40)
    selected_pages, _ = select_relevant_sections(
        pages,
        is_full_annual_report=is_ar,
        max_pages_to_select=20 if is_ar else 15
    )

    # 5. Generate AI summary
    try:
        summary = summarize_single_document_with_llm(
            symbol=clean_sym,
            company_name=company_name,
            doc_title=doc.title,
            doc_url=active_url,
            doc_type=doc.doc_type,
            period_or_date=doc.period_or_date,
            pages=selected_pages
        )
    except Exception as e:
        print(f"    ⚠️ Summarization LLM call failed for {doc.title}: {e}")
        failed_sum = {
            "doc_title": doc.title,
            "doc_url": doc.url,
            "doc_key": doc_k,
            "doc_type": doc.doc_type,
            "period_or_date": doc.period_or_date,
            "status": "failed",
            "error": f"AI extraction error: {e}",
            "key_takeaways": []
        }
        database.save_document_summary(clean_sym, doc.url, doc.title, failed_sum, doc_key=doc_k, doc_type=doc.doc_type, period_or_date=doc.period_or_date)
        return failed_sum

    if summary:
        summary["doc_key"] = doc_k
        summary["content_hash"] = current_content_hash
        summary["extraction_schema_version"] = EXTRACTION_SCHEMA_VERSION
        summary["extraction_prompt_version"] = EXTRACTION_PROMPT_VERSION
        summary["status"] = "success"

        # Provenance-aware cache status: An LLM extraction must NOT imply remote content verification
        # if the extraction was performed on local cached pages without live remote validation.
        if remote_verified or content_source == "REMOTE_FETCH":
            cache_st = "CURRENT_CONTENT_VERIFIED"
        else:
            cache_st = "CURRENT_VERSION_CONTENT_UNCHECKED"

        doc.content_hash = current_content_hash
        doc.cache_status = cache_st
        summary["cache_status"] = cache_st
        if doc.source_aliases:
            summary["source_aliases"] = list(doc.source_aliases)
        if doc.discovered_sources:
            summary["discovered_sources"] = list(doc.discovered_sources)
        database.save_document_summary(
            clean_sym,
            doc.url,
            doc.title,
            summary,
            doc_key=doc_k,
            doc_type=doc.doc_type,
            period_or_date=doc.period_or_date,
            content_hash=current_content_hash,
            extraction_schema_version=EXTRACTION_SCHEMA_VERSION,
            extraction_prompt_version=EXTRACTION_PROMPT_VERSION
        )
        return summary

    return {}

get_or_create_document_summary = get_or_generate_document_summary

def download_and_extract_pdf_with_provenance(
    pdf_url: str,
    symbol: str = "",
    force_remote_fetch: bool = False
) -> Tuple[List[Tuple[int, str]], str, bool]:
    """
    Downloads a PDF document from a direct URL and extracts text page-by-page.
    Returns:
        (pages, content_source, remote_verified)
    where:
        content_source: "REMOTE_FETCH" | "LOCAL_PAGE_CACHE"
        remote_verified: True if remote PDF content was actually fetched/validated in this run,
                         False if only local SQLite/disk cache was used without remote validation.
    """
    if not force_remote_fetch:
        cached_pages = database.get_cached_document_pages(pdf_url)
        if cached_pages:
            return cached_pages, "LOCAL_PAGE_CACHE", False

        url_hash = hashlib.md5(pdf_url.encode()).hexdigest()
        cache_file = PDF_CACHE_DIR / f"{url_hash}.json"

        if cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    pages = [(item["page"], item["text"]) for item in data]
                    if symbol:
                        database.save_cached_document_pages(symbol, pdf_url, pages)
                    return pages, "LOCAL_PAGE_CACHE", False
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
        url_hash = hashlib.md5(pdf_url.encode()).hexdigest()
        cache_file = PDF_CACHE_DIR / f"{url_hash}.json"
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(cache_list, f)
    except Exception:
        pass

    return pages, "REMOTE_FETCH", True

def download_and_extract_pdf(pdf_url: str, symbol: str = "") -> List[Tuple[int, str]]:
    """Legacy helper returning only pages for callers not needing explicit provenance."""
    pages, _, _ = download_and_extract_pdf_with_provenance(pdf_url, symbol=symbol)
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
        # If space remains, fill with adjacent context pages
        for p in list(kept_indices):
            if len(kept_indices) >= max_pages_to_select:
                break
            if (p - 1) in context_pages and (p - 1) not in kept_indices:
                kept_indices.add(p - 1)
            if len(kept_indices) < max_pages_to_select and (p + 1) in context_pages and (p + 1) not in kept_indices:
                kept_indices.add(p + 1)
        final_selected_indices = kept_indices

    if not final_selected_indices:
        # Fallback: keep first few pages if no keyword matched
        final_selected_indices = set(range(1, min(total_pages + 1, max_pages_to_select + 1)))
        for p in final_selected_indices:
            page_reasons.setdefault(p, []).append("General Document Excerpt")

    sorted_pages = [
        (p, text) for p, text in all_pages if p in final_selected_indices
    ]

    return sorted_pages, page_reasons

def deduplicate_synthesized_findings(output_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensures company-level synthesis does not repeat duplicate KPI findings or claims
    across the four Business Analysis views.
    Consolidates duplicate evidence items, verified facts, and cross-view redundancies.
    """
    if not output_dict or not isinstance(output_dict, dict):
        return output_dict

    # 1. Deduplicate verified_facts
    if "verified_facts" in output_dict and isinstance(output_dict["verified_facts"], list):
        seen_facts = set()
        deduped_facts = []
        for fact in output_dict["verified_facts"]:
            fact_str = str(fact.get("fact", "") if isinstance(fact, dict) else fact).strip()
            norm_stmt = re.sub(r'[^a-z0-9]', '', fact_str.lower())
            if norm_stmt and norm_stmt in seen_facts:
                continue
            if norm_stmt:
                seen_facts.add(norm_stmt)
            deduped_facts.append(fact)
        output_dict["verified_facts"] = deduped_facts

    # 2. Track cross-view normalized claims for redundancy suppression
    seen_cross_view_claims = set()

    # 2A. What Changed Recently
    if "what_changed_recently" in output_dict and isinstance(output_dict["what_changed_recently"], list):
        seen_changes = set()
        deduped_changes = []
        for item in output_dict["what_changed_recently"]:
            if isinstance(item, str):
                item_str = item.strip()
            elif isinstance(item, dict):
                item_str = f"{item.get('headline', '')} {item.get('detail', '')}".strip()
            else:
                item_str = f"{getattr(item, 'headline', '')} {getattr(item, 'detail', '')}".strip()
            norm_str = re.sub(r'[^a-z0-9]', '', item_str.lower())
            if norm_str and norm_str in seen_changes:
                continue
            if norm_str:
                seen_changes.add(norm_str)
                # Keep significant 5-word snippets in cross-view set
                for snippet in [norm_str[:40], norm_str[-40:]]:
                    if len(snippet) > 15:
                        seen_cross_view_claims.add(snippet)
            deduped_changes.append(item)
        output_dict["what_changed_recently"] = deduped_changes

    # 2B. Growth Drivers (Suppress identical text already in What Changed)
    if "growth_drivers" in output_dict and isinstance(output_dict["growth_drivers"], list):
        seen_drivers = set()
        deduped_drivers = []
        for item in output_dict["growth_drivers"]:
            if isinstance(item, str):
                item_str = item.strip()
            elif isinstance(item, dict):
                item_str = f"{item.get('driver_title', '')} {item.get('description', '')}".strip()
            else:
                item_str = f"{getattr(item, 'driver_title', '')} {getattr(item, 'description', '')}".strip()
            norm_str = re.sub(r'[^a-z0-9]', '', item_str.lower())
            if norm_str and (norm_str in seen_drivers or (len(norm_str) > 30 and norm_str[:40] in seen_cross_view_claims)):
                continue
            if norm_str:
                seen_drivers.add(norm_str)
                if len(norm_str) > 15:
                    seen_cross_view_claims.add(norm_str[:40])
            deduped_drivers.append(item)
        output_dict["growth_drivers"] = deduped_drivers

    # 2C. Promise vs Delivery
    if "promise_vs_delivery" in output_dict and isinstance(output_dict["promise_vs_delivery"], list):
        seen_promises = set()
        deduped_promises = []
        for item in output_dict["promise_vs_delivery"]:
            if isinstance(item, str):
                item_str = item.strip()
            elif isinstance(item, dict):
                item_str = f"{item.get('management_promise', '')} {item.get('actual_outcome', '')}".strip()
            else:
                item_str = f"{getattr(item, 'management_promise', '')} {getattr(item, 'actual_outcome', '')}".strip()
            norm_str = re.sub(r'[^a-z0-9]', '', item_str.lower())
            if norm_str and norm_str in seen_promises:
                continue
            if norm_str:
                seen_promises.add(norm_str)
            deduped_promises.append(item)
        output_dict["promise_vs_delivery"] = deduped_promises

    # 3. Deduplicate evidence_items
    if "evidence_items" in output_dict and isinstance(output_dict["evidence_items"], list):
        seen_evidence = set()
        deduped_evidence = []
        for ev in output_dict["evidence_items"]:
            if isinstance(ev, dict):
                ev_quote = str(ev.get("statement", "") or ev.get("fact", "") or ev.get("excerpt", "") or ev.get("title", "")).strip()
                norm_ev = re.sub(r'[^a-z0-9]', '', ev_quote.lower())
                if norm_ev and norm_ev in seen_evidence:
                    continue
                if norm_ev:
                    seen_evidence.add(norm_ev)
                deduped_evidence.append(ev)
            else:
                deduped_evidence.append(ev)
        output_dict["evidence_items"] = deduped_evidence

    return output_dict

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
       10-year standardized financial statement triangulation, and on-demand historical evidence.
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

    print(f"  Selected working set: {len(candidate_docs)} documents")

    # 2. Identify primary latest and baseline documents
    latest_ar = next((d for d in candidate_docs if d.doc_type == "annual_report"), None)
    if not latest_ar:
        latest_ar = next((d for d in candidate_docs if d.doc_type == "regulatory_annual_filing"), candidate_docs[0] if candidate_docs else None)

    older_ar = historical_baseline_doc
    if not older_ar and latest_ar:
        ar_candidates = [d for d in candidate_docs if d.doc_type == "annual_report" and getattr(d, "doc_key", None) != getattr(latest_ar, "doc_key", None) and d.url != latest_ar.url]
        older_ar = ar_candidates[0] if ar_candidates else None

    latest_doc_title = latest_ar.title if latest_ar else ""
    latest_doc_url = latest_ar.url if latest_ar else ""
    older_doc_title = older_ar.title if older_ar else None
    older_doc_url = older_ar.url if older_ar else None

    # 3. Tier 1: Generate or retrieve Per-Document AI Summaries (Cached in SQLite)
    # Tier-1 operates on EXACTLY the candidate_docs selected in the AI working set
    seen_summary_keys = set()
    deduped_core_summary_docs: List[DocumentItem] = []
    for d in candidate_docs:
        k = getattr(d, "doc_key", None) or database.compute_canonical_document_key(clean_sym, d.doc_type, d.period_or_date, d.url, d.title)
        d.doc_key = k
        if k not in seen_summary_keys and d.url not in seen_summary_keys:
            seen_summary_keys.add(k)
            seen_summary_keys.add(d.url)
            deduped_core_summary_docs.append(d)

    print(f"  • Generating/Retrieving Per-Document AI Summaries for {len(deduped_core_summary_docs)} AI Working Set filings...")
    doc_summaries_list: List[Dict[str, Any]] = []

    for doc in deduped_core_summary_docs:
        print(f"    - Processing [{doc.doc_type}]: {doc.title}")
        doc_sum = get_or_generate_document_summary(clean_sym, company_name, doc)
        if doc_sum and doc_sum.get("status") != "failed":
            doc_summaries_list.append(doc_sum)

    # 4. Extract and compile tagged excerpt chunks from primary documents
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

    # 5. Compile Standardized Financials Summary & Retrieve Structured Statements
    stock_data = database.get_stock_cache(clean_sym)
    if not stock_data:
        try:
            stock_data = fetch_stock_from_screener(clean_sym, force_refresh=False)
        except Exception:
            stock_data = {}

    financial_statements_text = format_financials_for_prompt(clean_sym, stock_data=stock_data)
    pl_stmt = (stock_data.get("profit_loss") or stock_data.get("profit_and_loss")) if stock_data else None
    quarters_stmt = stock_data.get("quarters") if stock_data else None
    bs_stmt = stock_data.get("balance_sheet") if stock_data else None
    cf_stmt = stock_data.get("cash_flow") if stock_data else None

    candidate_meta = [
        {"title": d.title, "url": d.url, "type": d.doc_type, "period": d.period_or_date}
        for d in candidate_docs
    ]

    # 5. Determine Sector Taxonomy & Business Model Routing
    from company_taxonomy_service import resolve_local_company_taxonomy
    from financial_engine import classify_financial_business_model

    tax_info = resolve_local_company_taxonomy(clean_sym, stock_data=stock_data)
    biz_model = classify_financial_business_model(
        sector=tax_info.get("sector"),
        industry=tax_info.get("industry")
    )
    docs_hash = database.compute_source_documents_hash(candidate_docs)

    # 6. LLM Inference / Company-Level Synthesis
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
            "document_summaries": doc_summaries_list,
            "verified_facts": [],
            "operational_kpi_evolution": [],
            "guidance_vs_projections": [],
            "evidence_items": [],
            "management_guidance_items": [],
            "source_documents_hash": docs_hash,
            "analysis_version": "2.0",
            "staleness_status": "not_analyzed",
            "financial_business_model": biz_model
        }
        return status_res

    print(f"  • Invoking Gemini for Company-Level Institutional Synthesis (Business Model: {biz_model})...")
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
        tagged_all_documents_text=tagged_all_documents_text,
        pl_stmt=pl_stmt,
        quarters_stmt=quarters_stmt,
        bs_stmt=bs_stmt,
        cf_stmt=cf_stmt,
        financial_business_model=biz_model
    )
    if not success or not result:
        raise RuntimeError(f"Multi-document AI extraction failed: {message}")

    result.extraction_timestamp = datetime.now(timezone.utc).isoformat()
    result.source_documents_hash = docs_hash
    result.analysis_version = "2.0"
    result.staleness_status = "fresh"
    output_dict = result.model_dump()
    output_dict = deduplicate_synthesized_findings(output_dict)

    # Save to SQLite Database
    if save_output:
        # 1. Save structured evidence items
        if output_dict.get("evidence_items"):
            database.save_document_evidence_items(clean_sym, output_dict["evidence_items"])

        # 2. Save structured management guidance items
        if output_dict.get("management_guidance_items"):
            database.save_management_guidance_items(clean_sym, output_dict["management_guidance_items"])

        # 3. Save full institutional analysis
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
