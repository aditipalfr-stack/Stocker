"""
Stocker Phase 2A — Financial Truth Service
==========================================

This module implements the deterministic Canonical Financial Truth Layer for Stocker.
It reconciles standardized Screener statements with official exchange verification records:
- Evaluates curated quarterly and annual metrics
- Selects the canonical truth value deterministically
- Exposes discrepancies explicitly without silent overrides
- Preserves NOT_COMPARABLE evidence across mismatched scopes without borrowing numbers
- Enforces fail-closed unit and currency preservation
- Computes comprehensive verification coverage metrics
- Manages version invalidation & deterministic local recomputation (zero network calls)
- Persists canonical facts into SQLite and provides query helpers for downstream consumers
"""

import os
import re
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple

from models import (
    CanonicalFinancialFact,
    VerificationCoverageSummary,
    FinancialTruthContainer,
    FinancialVerificationItem,
    FinancialStatement,
    FinancialRow
)
import database
from official_financial_service import normalize_period, normalize_metric_name

# Curated High-Value Target Metrics for Phase 2A
CURATED_QUARTERLY_METRICS = [
    ("REVENUE", "Revenue / Sales", "₹ Cr"),
    ("OPERATING_PROFIT", "Operating Profit", "₹ Cr"),
    ("OPM_PCT", "Operating Profit Margin %", "%"),
    ("NET_PROFIT", "Net Profit / PAT", "₹ Cr"),
    ("BASIC_EPS", "Basic EPS", "₹ / Share"),
]

CURATED_ANNUAL_METRICS = [
    ("REVENUE", "Revenue / Sales", "₹ Cr"),
    ("OPERATING_PROFIT", "Operating Profit", "₹ Cr"),
    ("NET_PROFIT", "Net Profit / PAT", "₹ Cr"),
    ("BASIC_EPS", "Basic EPS", "₹ / Share"),
    ("CFO", "Cash from Operations", "₹ Cr"),
    ("BORROWINGS", "Borrowings / Debt", "₹ Cr"),
    ("FIXED_ASSETS", "Fixed Assets", "₹ Cr"),
    ("CWIP", "Capital Work in Progress", "₹ Cr"),
]

# Helper to extract statement rows from either dict or FinancialStatement model
def _get_stmt_rows(stmt_obj: Any) -> List[Any]:
    if not stmt_obj:
        return []
    if isinstance(stmt_obj, dict):
        return stmt_obj.get("rows", [])
    return getattr(stmt_obj, "rows", []) or []

def _get_stmt_periods(stmt_obj: Any) -> List[str]:
    if not stmt_obj:
        return []
    if isinstance(stmt_obj, dict):
        return stmt_obj.get("periods", [])
    return getattr(stmt_obj, "periods", []) or []

def _extract_metric_values(stmt_obj: Any, target_metric: str) -> Dict[str, Optional[float]]:
    """
    Extracts values across periods for a given canonical metric from a statement.
    """
    rows = _get_stmt_rows(stmt_obj)
    target_lower = target_metric.lower().strip()
    
    for row in rows:
        m_name = ""
        values = {}
        if isinstance(row, dict):
            m_name = row.get("metric", "")
            values = row.get("values", {})
        else:
            m_name = getattr(row, "metric", "") or ""
            values = getattr(row, "values", {}) or {}
            
        clean_name = m_name.lower().strip()
        
        # Match quarterly/annual metrics cleanly
        is_match = False
        if target_lower == "revenue" and clean_name in ("sales", "revenue", "revenue from operations", "sales +"):
            is_match = True
        elif target_lower == "operating_profit" and clean_name in ("operating profit", "operating profit +"):
            is_match = True
        elif target_lower == "opm_pct" and clean_name in ("opm %", "opm", "operating profit margin"):
            is_match = True
        elif target_lower == "net_profit" and clean_name in ("net profit", "net profit +", "profit after tax", "pat"):
            is_match = True
        elif target_lower == "basic_eps" and clean_name in ("eps in rs", "basic eps", "eps (rs)"):
            is_match = True
        elif target_lower == "cfo" and any(term in clean_name for term in ["cash from operating activity", "operating activity", "cash flow from operations"]):
            is_match = True
        elif target_lower == "borrowings" and clean_name in ("borrowings", "borrowings +", "total debt", "debt"):
            is_match = True
        elif target_lower == "fixed_assets" and clean_name in ("fixed assets", "fixed assets +", "gross block", "net block"):
            is_match = True
        elif target_lower == "cwip" and clean_name in ("cwip", "capital work in progress", "capital work-in-progress"):
            is_match = True
            
        if is_match:
            return values
            
    return {}

def _find_verification_match(
    v_map: Dict[Tuple[str, str, str], Dict[str, Any]],
    raw_v_records: List[Dict[str, Any]],
    canonical_metric: str,
    canonical_period: str,
    statement_scope: str
) -> Optional[Dict[str, Any]]:
    """
    Deterministic verification record matching:
    1. Exact match by (canonical_metric, canonical_period, statement_scope) preferred.
    2. Fallback: If no exact scope match, look for a record matching same (metric, period)
       under a different scope that was flagged as NOT_COMPARABLE or different scope.
    """
    # 1. Exact match
    exact = v_map.get((canonical_metric, canonical_period, statement_scope))
    if exact:
        return exact
        
    # 2. Mismatched scope inspection (e.g. statement is Consolidated, official is Standalone)
    for r in raw_v_records:
        m = r.get("canonical_metric", "")
        p = r.get("canonical_period", "")
        s = (r.get("scope") or "").capitalize()
        if m == canonical_metric and p == canonical_period:
            if s and s != statement_scope:
                return {
                    **r,
                    "status": "NOT_COMPARABLE",
                    "provenance_note": f"Official statutory filing available under {s} scope, which is not directly comparable with {statement_scope} reported statement."
                }
            elif r.get("status") == "NOT_COMPARABLE":
                return r

    return None

def build_financial_truth_for_stock(
    symbol: str,
    stock_data: Dict[str, Any],
    verification_records: Optional[List[Any]] = None,
    verification_summary: Optional[Dict[str, Any]] = None,
    persist: bool = True
) -> FinancialTruthContainer:
    """
    Constructs the canonical financial truth container for a stock.
    Reconciles standardized Screener statements against official exchange verification records.
    """
    clean_sym = symbol.upper().strip()
    now_iso = datetime.now(timezone.utc).isoformat()
    if isinstance(stock_data, str):
        try:
            stock_data = json.loads(stock_data)
        except Exception:
            pass
            
    statement_scope = (stock_data.get("statement_type") or "consolidated").capitalize()
    input_fin_version = stock_data.get("fetched_at") or now_iso
    
    # 1. Fetch verification records if not supplied
    if verification_records is None:
        raw_v_records = database.get_financial_verification_records(clean_sym, limit=100)
    else:
        raw_v_records = [r.model_dump() if hasattr(r, "model_dump") else (r.dict() if hasattr(r, "dict") else r) for r in verification_records]
        
    if verification_summary is None:
        verification_summary = database.get_financial_verification_summary(clean_sym)
        
    verif_version = verification_summary.get("last_verified_at") if verification_summary else None
    
    # Map verification records by (canonical_metric, canonical_period, scope)
    v_map: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    for r in raw_v_records:
        m = r.get("canonical_metric", "")
        p = r.get("canonical_period", "")
        s = (r.get("scope") or statement_scope).capitalize()
        if m and p:
            v_map[(m, p, s)] = r

    facts: List[CanonicalFinancialFact] = []
    
    # 2. Process Quarterly Metrics
    quarters_stmt = stock_data.get("quarters")
    quarters_periods = _get_stmt_periods(quarters_stmt)
    
    for p_str in quarters_periods:
        disp_p, canon_p = normalize_period(p_str)
        if not canon_p or canon_p == "Unknown":
            continue
            
        for c_metric, d_metric, default_unit in CURATED_QUARTERLY_METRICS:
            val_dict = _extract_metric_values(quarters_stmt, c_metric)
            scr_val = val_dict.get(p_str)
            
            # Lookup official verification match (with scope fallback)
            v_rec = _find_verification_match(v_map, raw_v_records, c_metric, canon_p, statement_scope)
            
            fact = _evaluate_canonical_fact(
                symbol=clean_sym,
                canonical_metric=c_metric,
                display_metric=d_metric,
                period=p_str,
                canonical_period=canon_p,
                scope=statement_scope,
                default_unit=default_unit,
                screener_val=scr_val,
                v_rec=v_rec,
                screener_url=stock_data.get("source_url") or f"https://www.screener.in/company/{clean_sym}/",
                computed_at=now_iso
            )
            facts.append(fact)

    # 3. Process Annual Metrics
    pl_stmt = stock_data.get("profit_loss") or stock_data.get("profit_and_loss")
    bs_stmt = stock_data.get("balance_sheet")
    cf_stmt = stock_data.get("cash_flow")
    pl_periods = _get_stmt_periods(pl_stmt)
    
    for p_str in pl_periods:
        # Ignore TTM for annual facts
        if p_str.strip().upper() == "TTM":
            continue
            
        # Annual periods formatted as FYyy
        annual_p_arg = "FY" + p_str.split()[-1][-2:] if len(p_str.split()) > 1 else p_str
        disp_p, canon_p = normalize_period(annual_p_arg)
        if not canon_p or canon_p == "Unknown":
            continue
            
        for c_metric, d_metric, default_unit in CURATED_ANNUAL_METRICS:
            # Select appropriate statement
            if c_metric in ("REVENUE", "OPERATING_PROFIT", "NET_PROFIT", "BASIC_EPS"):
                val_dict = _extract_metric_values(pl_stmt, c_metric)
            elif c_metric == "CFO":
                val_dict = _extract_metric_values(cf_stmt, c_metric)
            elif c_metric in ("BORROWINGS", "FIXED_ASSETS", "CWIP"):
                val_dict = _extract_metric_values(bs_stmt, c_metric)
            else:
                val_dict = {}
                
            scr_val = val_dict.get(p_str)
            v_rec = _find_verification_match(v_map, raw_v_records, c_metric, canon_p, statement_scope)
            
            fact = _evaluate_canonical_fact(
                symbol=clean_sym,
                canonical_metric=c_metric,
                display_metric=d_metric,
                period=disp_p,
                canonical_period=canon_p,
                scope=statement_scope,
                default_unit=default_unit,
                screener_val=scr_val,
                v_rec=v_rec,
                screener_url=stock_data.get("source_url") or f"https://www.screener.in/company/{clean_sym}/",
                computed_at=now_iso
            )
            facts.append(fact)

    # 4. Also check for any official records that might have SCREENER_VALUE_MISSING
    for key, v_rec in v_map.items():
        c_m, c_p, s_scope = key
        # Check if already in facts
        already_added = any(f.canonical_metric == c_m and f.canonical_period == c_p and f.scope == s_scope for f in facts)
        if not already_added:
            display_name = c_m.replace("_", " ").title()
            fact = _evaluate_canonical_fact(
                symbol=clean_sym,
                canonical_metric=c_m,
                display_metric=display_name,
                period=v_rec.get("period", c_p),
                canonical_period=c_p,
                scope=s_scope,
                default_unit=v_rec.get("unit", "₹ Cr"),
                screener_val=None,
                v_rec=v_rec,
                screener_url=stock_data.get("source_url") or f"https://www.screener.in/company/{clean_sym}/",
                computed_at=now_iso
            )
            facts.append(fact)

    # 5. Compute Verification Coverage Summary
    total_target = len(facts)
    verified_count = sum(1 for f in facts if f.verification_status == "VERIFIED")
    discrepancy_count = sum(1 for f in facts if f.verification_status == "DISCREPANCY")
    not_comparable_count = sum(1 for f in facts if f.verification_status == "NOT_COMPARABLE")
    insufficient_evidence_count = sum(1 for f in facts if f.verification_status == "INSUFFICIENT_EVIDENCE")
    official_source_missing_count = sum(1 for f in facts if f.verification_status == "OFFICIAL_SOURCE_MISSING")
    screener_value_missing_count = sum(1 for f in facts if f.verification_status == "SCREENER_VALUE_MISSING")
    unverified_count = sum(1 for f in facts if f.verification_status == "UNVERIFIED")
    
    coverage_pct = round((verified_count / total_target) * 100, 1) if total_target > 0 else 0.0
    
    if discrepancy_count > 0:
        overall_truth_state = "DISCREPANCY"
    elif verified_count == total_target and total_target > 0:
        overall_truth_state = "VERIFIED"
    elif verified_count > 0:
        overall_truth_state = "PARTIAL"
    else:
        overall_truth_state = "UNVERIFIED"

    coverage = VerificationCoverageSummary(
        symbol=clean_sym,
        target_facts_count=total_target,
        officially_verified_count=verified_count,
        discrepancy_count=discrepancy_count,
        not_comparable_count=not_comparable_count,
        insufficient_evidence_count=insufficient_evidence_count,
        official_source_missing_count=official_source_missing_count,
        screener_value_missing_count=screener_value_missing_count,
        unverified_count=unverified_count,
        coverage_pct=coverage_pct,
        overall_truth_state=overall_truth_state
    )

    container = FinancialTruthContainer(
        symbol=clean_sym,
        facts=facts,
        coverage=coverage,
        discrepancies_count=discrepancy_count,
        verified_count=verified_count,
        unverified_count=unverified_count,
        last_computed_at=now_iso,
        input_financial_version=input_fin_version,
        verification_version=verif_version
    )

    # 6. Persist to SQLite if requested
    if persist:
        try:
            facts_dicts = [f.model_dump() for f in facts]
            coverage_dict = coverage.model_dump()
            database.save_canonical_financial_facts(
                symbol=clean_sym,
                facts=facts_dicts,
                coverage_summary=coverage_dict,
                input_financial_version=input_fin_version,
                verification_version=verif_version,
                computed_at=now_iso
            )
        except Exception as e:
            print(f"Notice: Canonical financial truth persistence note for {clean_sym}: {e}")

    return container

def _evaluate_canonical_fact(
    symbol: str,
    canonical_metric: str,
    display_metric: str,
    period: str,
    canonical_period: str,
    scope: str,
    default_unit: str,
    screener_val: Optional[float],
    v_rec: Optional[Dict[str, Any]],
    screener_url: str,
    computed_at: str
) -> CanonicalFinancialFact:
    """
    Evaluates truth selection deterministically for a single financial fact.
    Enforces the fail-closed verification contract:
    - VERIFIED -> canonical_value = official_value (High confidence, verified unit/currency)
    - DISCREPANCY -> canonical_value = screener_val (Low confidence, discrepancy exposed)
    - NOT_COMPARABLE / INSUFFICIENT_EVIDENCE / OFFICIAL_SOURCE_MISSING -> canonical_value = screener_val (No override)
    - SCREENER_VALUE_MISSING -> canonical_value = None (Unverified, never claim official selection)
    - UNVERIFIED -> canonical_value = screener_val
    """
    if v_rec:
        status = v_rec.get("status", "UNVERIFIED")
        off_val = v_rec.get("official_value")
        v_url = v_rec.get("official_source_url")
        v_source_name = v_rec.get("official_source_name") or "Official Statutory Filing (XBRL/PDF)"
        v_date = v_rec.get("verified_at")
        diff_abs = v_rec.get("variance_abs")
        diff_pct = v_rec.get("variance_pct")
        v_unit = v_rec.get("unit")
        v_curr = v_rec.get("currency")
        
        if status == "VERIFIED":
            fact_unit = v_unit or default_unit
            fact_curr = v_curr or "INR"
            return CanonicalFinancialFact(
                symbol=symbol,
                canonical_metric=canonical_metric,
                display_metric=display_metric,
                period=period,
                canonical_period=canonical_period,
                scope=scope,
                value=off_val,
                unit=fact_unit,
                currency=fact_curr,
                selected_source_type="official",
                selected_source_name=v_source_name,
                selected_source_url=v_url,
                screener_value=screener_val,
                official_value=off_val,
                verification_status="VERIFIED",
                difference_absolute=diff_abs,
                difference_pct=diff_pct,
                confidence="High",
                provenance_note=f"Officially reconciled against {v_source_name} within mathematical tolerance.",
                verified_at=v_date,
                computed_at=computed_at
            )
        elif status == "DISCREPANCY":
            fact_unit = v_unit or default_unit
            fact_curr = v_curr or "INR"
            return CanonicalFinancialFact(
                symbol=symbol,
                canonical_metric=canonical_metric,
                display_metric=display_metric,
                period=period,
                canonical_period=canonical_period,
                scope=scope,
                value=screener_val,
                unit=fact_unit,
                currency=fact_curr,
                selected_source_type="screener",
                selected_source_name="Screener.in (Discrepancy with Official Filing)",
                selected_source_url=screener_url,
                screener_value=screener_val,
                official_value=off_val,
                verification_status="DISCREPANCY",
                difference_absolute=diff_abs,
                difference_pct=diff_pct,
                confidence="Low",
                provenance_note=f"Material discrepancy detected: Screener={screener_val} vs Official={off_val}.",
                verified_at=v_date,
                computed_at=computed_at
            )
        elif status == "NOT_COMPARABLE":
            fact_unit = v_unit or default_unit
            fact_curr = v_curr or "INR"
            note = v_rec.get("provenance_note") or "Official filing available but scope or accounting standard is not directly comparable."
            return CanonicalFinancialFact(
                symbol=symbol,
                canonical_metric=canonical_metric,
                display_metric=display_metric,
                period=period,
                canonical_period=canonical_period,
                scope=scope,
                value=screener_val,
                unit=fact_unit,
                currency=fact_curr,
                selected_source_type="screener" if screener_val is not None else "unverified",
                selected_source_name="Screener.in" if screener_val is not None else None,
                selected_source_url=screener_url,
                screener_value=screener_val,
                official_value=off_val,
                verification_status="NOT_COMPARABLE",
                difference_absolute=None,
                difference_pct=None,
                confidence="Moderate" if screener_val is not None else "Unverified",
                provenance_note=note,
                verified_at=v_date,
                computed_at=computed_at
            )
        elif status == "INSUFFICIENT_EVIDENCE":
            fact_unit = v_unit if v_unit else "Unknown"
            fact_curr = v_curr if v_curr else "Unknown"
            return CanonicalFinancialFact(
                symbol=symbol,
                canonical_metric=canonical_metric,
                display_metric=display_metric,
                period=period,
                canonical_period=canonical_period,
                scope=scope,
                value=screener_val,
                unit=fact_unit,
                currency=fact_curr,
                selected_source_type="screener" if screener_val is not None else "unverified",
                selected_source_name="Screener.in" if screener_val is not None else None,
                selected_source_url=screener_url,
                screener_value=screener_val,
                official_value=off_val,
                verification_status="INSUFFICIENT_EVIDENCE",
                difference_absolute=None,
                difference_pct=None,
                confidence="Moderate" if screener_val is not None else "Unverified",
                provenance_note="Official source found but lacked unambiguous metric breakdown, currency proof, or unit proof.",
                verified_at=v_date,
                computed_at=computed_at
            )
        elif status == "OFFICIAL_SOURCE_MISSING":
            return CanonicalFinancialFact(
                symbol=symbol,
                canonical_metric=canonical_metric,
                display_metric=display_metric,
                period=period,
                canonical_period=canonical_period,
                scope=scope,
                value=screener_val,
                unit=default_unit,
                currency="INR",
                selected_source_type="screener" if screener_val is not None else "unverified",
                selected_source_name="Screener.in" if screener_val is not None else None,
                selected_source_url=screener_url,
                screener_value=screener_val,
                official_value=None,
                verification_status="OFFICIAL_SOURCE_MISSING",
                difference_absolute=None,
                difference_pct=None,
                confidence="Moderate" if screener_val is not None else "Unverified",
                provenance_note="Standardized reported figure from Screener.in; official exchange filing not discovered.",
                verified_at=v_date,
                computed_at=computed_at
            )
        elif status == "SCREENER_VALUE_MISSING":
            fact_unit = v_unit or default_unit
            fact_curr = v_curr or "INR"
            return CanonicalFinancialFact(
                symbol=symbol,
                canonical_metric=canonical_metric,
                display_metric=display_metric,
                period=period,
                canonical_period=canonical_period,
                scope=scope,
                value=None, # Usable canonical value remains None because value was not reconciled against Screener
                unit=fact_unit,
                currency=fact_curr,
                selected_source_type="unverified",
                selected_source_name=v_source_name if off_val is not None else None,
                selected_source_url=v_url,
                screener_value=None,
                official_value=off_val,
                verification_status="SCREENER_VALUE_MISSING",
                difference_absolute=None,
                difference_pct=None,
                confidence="Unverified",
                provenance_note=f"Official statutory figure reported in {v_source_name or 'filing'}, but could not be reconciled as no corresponding standardized row exists in Screener.",
                verified_at=v_date,
                computed_at=computed_at
            )

    # Default Unverified Fact
    return CanonicalFinancialFact(
        symbol=symbol,
        canonical_metric=canonical_metric,
        display_metric=display_metric,
        period=period,
        canonical_period=canonical_period,
        scope=scope,
        value=screener_val,
        unit=default_unit,
        currency="INR",
        selected_source_type="screener" if screener_val is not None else "unverified",
        selected_source_name="Screener.in" if screener_val is not None else None,
        selected_source_url=screener_url if screener_val is not None else None,
        screener_value=screener_val,
        official_value=None,
        verification_status="UNVERIFIED",
        difference_absolute=None,
        difference_pct=None,
        confidence="Unverified",
        provenance_note="Standardized reported statement data (assumed ₹ Cr / ₹ per Share based on Screener convention); official verification not yet executed.",
        verified_at=None,
        computed_at=computed_at
    )

# =============================================================================
# VERSION INVALIDATION & RECOMPUTE GETTER
# =============================================================================

def get_or_recompute_financial_truth(symbol: str) -> Optional[FinancialTruthContainer]:
    """
    Lightweight deterministic helper to fetch or recompute Canonical Financial Truth.
    Compares:
      - Persisted input_financial_version vs current cached financial version (fetched_at)
      - Persisted verification_version vs current persisted verification summary (last_verified_at)
    If versions match and persisted truth exists: returns persisted truth immediately.
    If versions differ or truth missing: deterministically recomputes from local persisted inputs and updates SQLite.
    Zero external network calls.
    """
    clean_sym = symbol.upper().strip()
    stock_data = database.get_stock_cache(clean_sym)
    if not stock_data:
        return None
        
    if isinstance(stock_data, str):
        try:
            stock_data = json.loads(stock_data)
        except Exception:
            pass
            
    v_summary = database.get_financial_verification_summary(clean_sym)
    current_fin_version = stock_data.get("fetched_at")
    current_verif_version = v_summary.get("last_verified_at") if v_summary else None
    
    persisted = database.get_canonical_financial_facts(clean_sym)
    if persisted:
        persisted_fin_ver = persisted.get("input_financial_version")
        persisted_verif_ver = persisted.get("verification_version")
        if persisted_fin_ver == current_fin_version and persisted_verif_ver == current_verif_version:
            return FinancialTruthContainer(**persisted)
            
    # Deterministic local recomputation from persisted inputs
    return build_financial_truth_for_stock(
        symbol=clean_sym,
        stock_data=stock_data,
        verification_summary=v_summary,
        persist=True
    )

# =============================================================================
# DOWNSTREAM CONTRACT HELPERS (PHASE 2B PREPARATION)
# =============================================================================

def get_canonical_fact(
    symbol: str,
    metric: str,
    period: str,
    scope: str = "Consolidated"
) -> Optional[CanonicalFinancialFact]:
    """
    Retrieves a single CanonicalFinancialFact for a given symbol, metric, period, and scope.
    Ensures canonical truth is fresh first using get_or_recompute_financial_truth.
    """
    clean_sym = symbol.upper().strip()
    container = get_or_recompute_financial_truth(clean_sym)
    if not container:
        return None
    canon_m = normalize_metric_name(metric) or metric.upper().strip()
    raw = database.get_canonical_fact_by_key(clean_sym, canon_m, period, scope)
    if raw:
        return CanonicalFinancialFact(**raw)
    return None

def get_canonical_series(
    symbol: str,
    metric: str,
    scope: str = "Consolidated"
) -> List[CanonicalFinancialFact]:
    """
    Retrieves a chronological time series of CanonicalFinancialFacts for a given symbol, metric, and scope.
    Ensures canonical truth is fresh first using get_or_recompute_financial_truth.
    """
    clean_sym = symbol.upper().strip()
    container = get_or_recompute_financial_truth(clean_sym)
    if not container:
        return []
    canon_m = normalize_metric_name(metric) or metric.upper().strip()
    rows = database.get_canonical_facts_series(clean_sym, canon_m, scope)
    return [CanonicalFinancialFact(**r) for r in rows]

def has_material_verification_discrepancy(
    symbol: str,
    metric: Optional[str] = None,
    period: Optional[str] = None
) -> bool:
    """
    Checks if there is any active DISCREPANCY recorded for the company, optionally filtered by metric or period.
    Ensures canonical truth is fresh first using get_or_recompute_financial_truth.
    """
    clean_sym = symbol.upper().strip()
    container = get_or_recompute_financial_truth(clean_sym)
    if not container:
        return False
    for f in container.facts:
        if f.verification_status == "DISCREPANCY":
            if metric and (f.canonical_metric != metric.upper().strip() and f.display_metric != metric):
                continue
            if period and f.period != period and f.canonical_period != period:
                continue
            return True
    return False
