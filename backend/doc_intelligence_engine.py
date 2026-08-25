import os
import json
from pathlib import Path
from typing import Optional, Dict, Any

from doc_intelligence_models import (
    CompanyDocumentIntelligence, PlanVsRealityItem,
    GrowthPipelineItem, DemandAndOrders, CashAndProblems
)

DOC_INTEL_DIR = Path(__file__).parent / "data" / "doc_intelligence"

def get_company_doc_intelligence(symbol: str, financial_analytics: Optional[Dict[str, Any]] = None) -> Optional[CompanyDocumentIntelligence]:
    clean_sym = symbol.upper().strip()
    file_path = DOC_INTEL_DIR / f"{clean_sym}.json"
    
    if not file_path.exists():
        # Return structured "Not enough data" object instead of fabricating fake data
        return None
        
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        doc_intel = CompanyDocumentIntelligence(**data)
        
        # Cross-check with actual numerical financial analytics if provided
        if financial_analytics:
            cf_quality = financial_analytics.get("cash_flow_quality", {})
            cfo_pat = cf_quality.get("cfo_to_pat_5yr_pct")
            cum_cfo = cf_quality.get("cumulative_5y_cfo_cr")
            cum_pat = cf_quality.get("cumulative_5y_pat_cr")
            
            bs_eff = financial_analytics.get("balance_sheet_efficiency", {})
            cwip_pct = bs_eff.get("latest_cwip_to_net_block_pct")
            debt_eq = bs_eff.get("latest_debt_to_equity")
            
            # Enrich the financial cross-check dynamically
            if cfo_pat is not None:
                doc_intel.cash_and_problems.financial_cross_check = (
                    f"Financial Statement Cross-Check: 5-Year Cumulative CFO of ₹{cum_cfo:,.0f} Cr vs "
                    f"PAT of ₹{cum_pat:,.0f} Cr yields a {cfo_pat:.1f}% cash conversion ratio. "
                    f"Latest Debt/Equity is {debt_eq}x with CWIP at {cwip_pct:.1f}% of fixed assets."
                )
                
        return doc_intel
    except Exception as e:
        print(f"Error loading document intelligence for {clean_sym}: {e}")
        return None
