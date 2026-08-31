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

def get_company_doc_intelligence(
    symbol: str, 
    financial_analytics: Optional[Dict[str, Any]] = None,
    include_document_summaries: bool = True
) -> Optional[CompanyDocumentIntelligence]:
    clean_sym = symbol.upper().strip()
    
    # Priority 1: Check SQLite database cache
    db_data = database.get_cached_ai_analysis(clean_sym)
    if db_data and (db_data.get("promise_vs_delivery") or db_data.get("growth_drivers") or db_data.get("plan_vs_reality")):
        try:
            if include_document_summaries:
                doc_sums = database.get_document_summaries(clean_sym)
                if doc_sums and not db_data.get("document_summaries"):
                    db_data["document_summaries"] = list(doc_sums.values())
            else:
                db_data["document_summaries"] = []
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
                if include_document_summaries:
                    doc_sums = database.get_document_summaries(clean_sym)
                    if doc_sums and not data.get("document_summaries"):
                        data["document_summaries"] = list(doc_sums.values())
                else:
                    data["document_summaries"] = []
                doc_intel = CompanyDocumentIntelligence(**data)
                _apply_financial_cross_check(doc_intel, financial_analytics)
                return doc_intel
        except Exception as e:
            print(f"Notice: Could not load generated intelligence for {clean_sym}: {e}")
            
    # If not yet generated, return None (NO mock sample fallback!)
    return None

def _apply_financial_cross_check(doc_intel: CompanyDocumentIntelligence, financial_analytics: Optional[Dict[str, Any]]) -> None:
    """Enriches document intelligence with deterministic audited financial analytics."""
    if not financial_analytics:
        return
    cf_quality = financial_analytics.get("cash_flow_quality", {})
    cfo_pat = cf_quality.get("cfo_to_pat_5yr_pct")
    cum_cfo = cf_quality.get("cumulative_5y_cfo_cr")
    cum_pat = cf_quality.get("cumulative_5y_pat_cr")
    cum_fcf = cf_quality.get("cumulative_5y_fcf_cr")
    
    bs_eff = financial_analytics.get("balance_sheet_efficiency", {})
    cwip_pct = bs_eff.get("latest_cwip_to_net_block_pct")
    debt_eq = bs_eff.get("latest_debt_to_equity")
    
    growth = financial_analytics.get("growth_rates", {})
    sales_3y = growth.get("sales_cagr_3yr")
    pat_3y = growth.get("pat_cagr_3yr")

    if cfo_pat is not None:
        audit_parts = []
        if cum_cfo is not None and cum_pat is not None:
            audit_parts.append(f"5-Year Cumulative CFO of ₹{cum_cfo:,.0f} Cr vs PAT of ₹{cum_pat:,.0f} Cr ({cfo_pat:.1f}% cash conversion ratio).")
        elif cum_cfo is not None:
            audit_parts.append(f"5-Year Cumulative CFO of ₹{cum_cfo:,.0f} Cr ({cfo_pat:.1f}% cash conversion ratio).")
        else:
            audit_parts.append(f"5-Year CFO/PAT cash conversion ratio of {cfo_pat:.1f}%.")
            
        if debt_eq is not None and cwip_pct is not None:
            audit_parts.append(f"Balance Sheet Debt/Equity stands at {debt_eq}x with CWIP at {cwip_pct:.1f}% of fixed assets.")
        elif debt_eq is not None:
            audit_parts.append(f"Balance Sheet Debt/Equity stands at {debt_eq}x.")
        elif cwip_pct is not None:
            audit_parts.append(f"CWIP stands at {cwip_pct:.1f}% of fixed assets.")
            
        if sales_3y is not None:
            audit_parts.append(f"Reported 3-Year Sales CAGR is {sales_3y:.1f}%.")
            
        doc_intel.risks_and_cash.reported_numbers_comparison = "REPORTED NUMBERS AUDIT: " + " ".join(audit_parts)

    # Deterministically enrich Capital Allocation if not populated
    if doc_intel.capital_allocation:
        if not doc_intel.capital_allocation.capex_efficiency and (cwip_pct is not None or cum_fcf is not None):
            if cwip_pct is not None and cum_fcf is not None:
                fcf_txt = f"CWIP stands at {cwip_pct:.1f}% of net block with 5-Year cumulative FCF of ₹{cum_fcf:,.0f} Cr"
                if cum_cfo is not None:
                    fcf_txt += f" (after reinvesting ₹{(cum_cfo - cum_fcf):,.0f} Cr in capital assets)."
                else:
                    fcf_txt += "."
                doc_intel.capital_allocation.capex_efficiency = fcf_txt
            elif cwip_pct is not None:
                doc_intel.capital_allocation.capex_efficiency = f"CWIP stands at {cwip_pct:.1f}% of net block."
            elif cum_fcf is not None:
                fcf_txt = f"5-Year cumulative FCF of ₹{cum_fcf:,.0f} Cr"
                if cum_cfo is not None:
                    fcf_txt += f" (after reinvesting ₹{(cum_cfo - cum_fcf):,.0f} Cr in capital assets)."
                else:
                    fcf_txt += "."
                doc_intel.capital_allocation.capex_efficiency = fcf_txt
                
        if not doc_intel.capital_allocation.shareholder_returns and cfo_pat is not None:
            conv_qual = cf_quality.get("cash_conversion_quality", "Adequate")
            ret_text = f"5-Year CFO/PAT conversion is {cfo_pat:.1f}% ({conv_qual} quality)."
            if debt_eq is not None:
                ret_text += f" Debt-to-Equity is {debt_eq}x."
            doc_intel.capital_allocation.shareholder_returns = ret_text

    # Deterministically enrich Governance / Accounting Watch working capital note
    if doc_intel.governance_watch:
        wc_audit = financial_analytics.get("working_capital_audit", {})
        debtor_days = wc_audit.get("debtor_days")
        inv_days = wc_audit.get("inventory_days")
        if not doc_intel.governance_watch.working_capital_anomalies and (debtor_days is not None or inv_days is not None):
            doc_intel.governance_watch.working_capital_anomalies = (
                f"Working capital cycle: Debtor Days ~{debtor_days if debtor_days is not None else 'N/A'} days, "
                f"Inventory Days ~{inv_days if inv_days is not None else 'N/A'} days."
            )

