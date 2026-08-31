"""
Stocker Phase 2B — Financial Truth Resolver
===========================================

Deterministic financial series and fact resolver layer for the analytics engine.
Resolves financial values with provenance tracking:
- Loads canonical truth facts once per stock calculation (zero repeated DB queries)
- Maps canonical truth facts by (canonical_metric, canonical_period, scope)
- Enforces fail-closed truth policy:
  - VERIFIED -> official canonical value
  - UNVERIFIED / OFFICIAL_SOURCE_MISSING -> standardized Screener value
  - DISCREPANCY -> continuity standardized value, propagates has_discrepancy=True
  - NOT_COMPARABLE / INSUFFICIENT_EVIDENCE -> standardized value if present with warning
  - SCREENER_VALUE_MISSING -> None (do not substitute official value into standardized time series)
- Computes deterministic growth/CAGR with analytic input quality classification:
  - all VERIFIED -> "verified"
  - any DISCREPANCY -> "discrepant"
  - mix of VERIFIED and standardized -> "mixed"
  - all standardized -> "standardized"
  - missing input -> "insufficient"
"""

from typing import Dict, List, Optional, Any, Tuple
import math
from models import (
    CanonicalFinancialFact,
    FinancialTruthContainer,
    AnalyticInputProvenance,
    AnalyticValueWithProvenance,
    AnalyticProvenanceSummary,
    FinancialStatement
)
from official_financial_service import normalize_period, normalize_metric_name

def calculate_cagr(start_val: Optional[float], end_val: Optional[float], years: float) -> Optional[float]:
    if start_val is None or end_val is None or start_val <= 0 or end_val <= 0 or years <= 0:
        return None
    try:
        return round(((end_val / start_val) ** (1.0 / years) - 1.0) * 100.0, 2)
    except Exception:
        return None

def calculate_growth_pct(curr_val: Optional[float], prev_val: Optional[float]) -> Optional[float]:
    if curr_val is None or prev_val is None or prev_val == 0:
        return None
    try:
        return round(((curr_val - prev_val) / abs(prev_val)) * 100.0, 2)
    except Exception:
        return None

class TruthAwareFinancialResolver:
    """
    In-memory fast lookup resolver for canonical financial facts and standardized statements.
    Builds an index once per stock computation (0 network calls, 0 repeated DB lookups).
    """
    def __init__(
        self,
        symbol: Optional[str] = None,
        financial_truth: Optional[FinancialTruthContainer] = None,
        quarters: Optional[FinancialStatement] = None,
        pl: Optional[FinancialStatement] = None,
        bs: Optional[FinancialStatement] = None,
        cf: Optional[FinancialStatement] = None,
        scope: str = "Consolidated"
    ):
        self.symbol = (symbol or "").upper().strip()
        self.financial_truth = financial_truth
        self.scope = scope.capitalize() if scope else "Consolidated"
        self.quarters = quarters
        self.pl = pl
        self.bs = bs
        self.cf = cf
        
        # Indexed map: (canonical_metric, canonical_period, scope) -> CanonicalFinancialFact
        self.facts_map: Dict[Tuple[str, str, str], CanonicalFinancialFact] = {}
        if self.financial_truth and hasattr(self.financial_truth, "facts"):
            for f in self.financial_truth.facts:
                key = (f.canonical_metric, f.canonical_period, f.scope)
                self.facts_map[key] = f

    def resolve_quarterly_fact(self, canonical_metric: str, period_str: str) -> AnalyticInputProvenance:
        """
        Resolves a quarterly financial fact with provenance.
        period_str: e.g. "Jun 2026" or "2026-Q1"
        """
        disp_p, canon_p = normalize_period(period_str)
        if not canon_p or canon_p == "Unknown":
            canon_p = period_str
            disp_p = period_str
            
        c_metric = normalize_metric_name(canonical_metric) or canonical_metric.upper().strip()
        
        # 1. Check in-memory canonical truth facts
        fact = self.facts_map.get((c_metric, canon_p, self.scope))
        if fact:
            # Enforce truth policy
            has_disc = (fact.verification_status == "DISCREPANCY")
            return AnalyticInputProvenance(
                canonical_metric=c_metric,
                period=fact.period or disp_p,
                canonical_period=fact.canonical_period or canon_p,
                scope=fact.scope or self.scope,
                value=fact.value,
                source_type=fact.selected_source_type,
                verification_status=fact.verification_status,
                selected_source_name=fact.selected_source_name,
                selected_source_url=fact.selected_source_url,
                confidence=fact.confidence,
                has_discrepancy=has_disc
            )
            
        # 2. Standardized raw statement fallback
        raw_val = self._extract_raw_statement_value(self.quarters, c_metric, period_str)
        return AnalyticInputProvenance(
            canonical_metric=c_metric,
            period=disp_p,
            canonical_period=canon_p,
            scope=self.scope,
            value=raw_val,
            source_type="screener" if raw_val is not None else "unavailable",
            verification_status="UNVERIFIED",
            selected_source_name="Screener.in Standardized",
            selected_source_url=None,
            confidence="Moderate" if raw_val is not None else "Unverified",
            has_discrepancy=False
        )

    def resolve_annual_fact(self, canonical_metric: str, period_str: str) -> AnalyticInputProvenance:
        """
        Resolves an annual financial fact with provenance.
        period_str: e.g. "Mar 2026", "FY26", "2026-FY"
        """
        annual_p_arg = "FY" + period_str.split()[-1][-2:] if len(period_str.split()) > 1 else period_str
        disp_p, canon_p = normalize_period(annual_p_arg)
        if not canon_p or canon_p == "Unknown":
            canon_p = period_str
            disp_p = period_str
            
        c_metric = normalize_metric_name(canonical_metric) or canonical_metric.upper().strip()
        
        # 1. Check in-memory canonical truth facts
        fact = self.facts_map.get((c_metric, canon_p, self.scope))
        if fact:
            has_disc = (fact.verification_status == "DISCREPANCY")
            return AnalyticInputProvenance(
                canonical_metric=c_metric,
                period=fact.period or disp_p,
                canonical_period=fact.canonical_period or canon_p,
                scope=fact.scope or self.scope,
                value=fact.value,
                source_type=fact.selected_source_type,
                verification_status=fact.verification_status,
                selected_source_name=fact.selected_source_name,
                selected_source_url=fact.selected_source_url,
                confidence=fact.confidence,
                has_discrepancy=has_disc
            )
            
        # 2. Standardized raw statement fallback
        stmt = None
        if c_metric in ("REVENUE", "OPERATING_PROFIT", "NET_PROFIT", "BASIC_EPS"):
            stmt = self.pl
        elif c_metric == "CFO":
            stmt = self.cf
        elif c_metric in ("BORROWINGS", "FIXED_ASSETS", "CWIP"):
            stmt = self.bs
            
        raw_val = self._extract_raw_statement_value(stmt, c_metric, period_str)
        return AnalyticInputProvenance(
            canonical_metric=c_metric,
            period=disp_p,
            canonical_period=canon_p,
            scope=self.scope,
            value=raw_val,
            source_type="screener" if raw_val is not None else "unavailable",
            verification_status="UNVERIFIED",
            selected_source_name="Screener.in Standardized",
            selected_source_url=None,
            confidence="Moderate" if raw_val is not None else "Unverified",
            has_discrepancy=False
        )

    def _extract_raw_statement_value(self, stmt: Optional[FinancialStatement], canonical_metric: str, period_str: str) -> Optional[float]:
        if not stmt or not stmt.rows:
            return None
            
        for row in stmt.rows:
            m_clean = row.metric.strip().lower()
            target_lower = canonical_metric.lower()
            
            is_match = False
            if target_lower == "revenue" and m_clean in ("sales", "revenue", "revenue from operations", "sales +"):
                is_match = True
            elif target_lower == "operating_profit" and m_clean in ("operating profit", "operating profit +", "ebitda"):
                is_match = True
            elif target_lower == "opm_pct" and m_clean in ("opm %", "opm", "operating profit margin"):
                is_match = True
            elif target_lower == "net_profit" and m_clean in ("net profit", "net profit +", "pat", "profit after tax"):
                is_match = True
            elif target_lower == "basic_eps" and m_clean in ("eps in rs", "basic eps", "eps (rs)"):
                is_match = True
            elif target_lower == "cfo" and any(t in m_clean for t in ["cash from operating activity", "operating activity", "cash from operations"]):
                is_match = True
            elif target_lower == "borrowings" and m_clean in ("borrowings", "borrowings +", "total debt", "debt"):
                is_match = True
            elif target_lower == "fixed_assets" and m_clean in ("fixed assets", "fixed assets +", "gross block", "net block"):
                is_match = True
            elif target_lower == "cwip" and m_clean in ("cwip", "capital work in progress", "capital work-in-progress"):
                is_match = True
                
            if is_match:
                if period_str in row.values:
                    return row.values[period_str]
                for p_k, p_v in row.values.items():
                    if p_k.strip().lower() == period_str.strip().lower():
                        return p_v
        return None

    def calculate_growth_with_provenance(
        self,
        curr_input: AnalyticInputProvenance,
        prev_input: AnalyticInputProvenance,
        formula_type: str = "growth", # "growth" | "cagr"
        years: float = 1.0
    ) -> AnalyticValueWithProvenance:
        """
        Computes deterministic growth/CAGR with full provenance and input quality classification.
        """
        inputs = [curr_input, prev_input]
        has_disc = any(inp.has_discrepancy for inp in inputs)
        
        # Check if any input is missing
        if curr_input.value is None or prev_input.value is None:
            return AnalyticValueWithProvenance(
                value=None,
                quality="insufficient",
                has_discrepancy=has_disc,
                inputs=inputs
            )
            
        # Compute value
        val = None
        if formula_type == "cagr":
            val = calculate_cagr(prev_input.value, curr_input.value, years)
        else:
            val = calculate_growth_pct(curr_input.value, prev_input.value)
            
        if val is None:
            return AnalyticValueWithProvenance(
                value=None,
                quality="insufficient",
                has_discrepancy=has_disc,
                inputs=inputs
            )
            
        # Determine deterministic quality
        # 1. Any discrepancy -> "discrepant"
        if has_disc or any(inp.verification_status == "DISCREPANCY" for inp in inputs):
            quality = "discrepant"
        # 2. All inputs verified -> "verified"
        elif all(inp.verification_status == "VERIFIED" for inp in inputs):
            quality = "verified"
        # 3. Mix of verified and unverified/standardized -> "mixed"
        elif any(inp.verification_status == "VERIFIED" for inp in inputs):
            quality = "mixed"
        # 4. Standardized Screener
        else:
            quality = "standardized"
            
        return AnalyticValueWithProvenance(
            value=val,
            quality=quality,
            has_discrepancy=has_disc,
            inputs=inputs
        )

