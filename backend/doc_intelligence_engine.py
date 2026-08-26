import os
import json
from pathlib import Path
from typing import Optional, Dict, Any

from doc_intelligence_models import (
    CompanyDocumentIntelligence, PromiseVsDeliveryItem,
    GrowthDriver, DemandMomentum, RisksAndCashIssues, StockerView, RecentChange
)

DOC_INTEL_GENERATED_DIR = Path(__file__).parent / "data" / "doc_intelligence_generated"
DOC_INTEL_BASELINE_DIR = Path(__file__).parent / "data" / "doc_intelligence"

import database

def get_company_doc_intelligence(symbol: str, financial_analytics: Optional[Dict[str, Any]] = None) -> Optional[CompanyDocumentIntelligence]:
    clean_sym = symbol.upper().strip()
    
    # Priority 1: Check SQLite database cache
    db_data = database.get_cached_ai_analysis(clean_sym)
    if db_data and (db_data.get("promise_vs_delivery") or db_data.get("growth_drivers") or db_data.get("plan_vs_reality")):
        try:
            doc_intel = CompanyDocumentIntelligence(**db_data)
            _apply_financial_cross_check(doc_intel, financial_analytics)
            return doc_intel
        except Exception as e:
            print(f"Notice: Could not parse SQLite intelligence for {clean_sym}: {e}")

    # Priority 2: Check JSON file cache in doc_intelligence_generated
    gen_path = DOC_INTEL_GENERATED_DIR / f"{clean_sym}.json"
    if gen_path.exists():
        try:
            with open(gen_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("status") != "ai_unavailable" and (data.get("promise_vs_delivery") or data.get("growth_drivers") or data.get("plan_vs_reality")):
                doc_intel = CompanyDocumentIntelligence(**data)
                _apply_financial_cross_check(doc_intel, financial_analytics)
                return doc_intel
        except Exception as e:
            print(f"Notice: Could not load generated intelligence for {clean_sym}: {e}")
            
    # If not yet generated, return None (NO mock sample fallback!)
    return None

def _apply_financial_cross_check(doc_intel: CompanyDocumentIntelligence, financial_analytics: Optional[Dict[str, Any]]) -> None:
    """Enriches the document cash flow claim with actual mathematical statements if available."""
    if not financial_analytics:
        return
    cf_quality = financial_analytics.get("cash_flow_quality", {})
    cfo_pat = cf_quality.get("cfo_to_pat_5yr_pct")
    cum_cfo = cf_quality.get("cumulative_5y_cfo_cr", 0)
    cum_pat = cf_quality.get("cumulative_5y_pat_cr", 0)
    
    bs_eff = financial_analytics.get("balance_sheet_efficiency", {})
    cwip_pct = bs_eff.get("latest_cwip_to_net_block_pct", 0)
    debt_eq = bs_eff.get("latest_debt_to_equity", 0)
    
    growth = financial_analytics.get("growth_rates", {})
    sales_3y = growth.get("sales_cagr_3yr")
    pat_3y = growth.get("pat_cagr_3yr")

    if cfo_pat is not None:
        stmt_text = (
            f"REPORTED NUMBERS AUDIT: 5-Year Cumulative CFO of ₹{cum_cfo:,.0f} Cr vs "
            f"PAT of ₹{cum_pat:,.0f} Cr ({cfo_pat:.1f}% cash conversion ratio). "
            f"Balance Sheet Debt/Equity stands at {debt_eq}x with CWIP at {cwip_pct:.1f}% of fixed assets."
        )
        if sales_3y is not None:
            stmt_text += f" Reported 3-Year Sales CAGR is {sales_3y:.1f}%."
        doc_intel.risks_and_cash.reported_numbers_comparison = stmt_text
