from typing import Dict, List, Any, Optional
from models import KeyRatios, ProjectionResult, ScoreBreakdown
from doc_intelligence_models import BusinessOutlookResult

def compute_stock_score(
    symbol: str,
    name: str,
    ratios: KeyRatios,
    analytics: Dict[str, Any],
    projection: ProjectionResult,
    sector: str = "",
    doc_intel: Optional[BusinessOutlookResult] = None
) -> ScoreBreakdown:
    # 1. Growth & Momentum (20%)
    sales_cagr = analytics.get("growth_rates", {}).get("sales_cagr_3yr") or ratios.sales_growth_3yr_cagr or 10.0
    pat_cagr = analytics.get("growth_rates", {}).get("pat_cagr_3yr") or ratios.profit_growth_3yr_cagr or 12.0
    
    growth_score = 50.0
    if sales_cagr >= 20.0:
        growth_score += 25.0
    elif sales_cagr >= 12.0:
        growth_score += 15.0
    elif sales_cagr >= 7.0:
        growth_score += 5.0
    else:
        growth_score -= 10.0
        
    if pat_cagr >= 22.0:
        growth_score += 25.0
    elif pat_cagr >= 15.0:
        growth_score += 15.0
    elif pat_cagr >= 8.0:
        growth_score += 5.0
    else:
        growth_score -= 10.0
    growth_score = max(10.0, min(100.0, growth_score))

    # 2. Cash Quality & FCF Strength (25%)
    cf_quality = analytics.get("cash_flow_quality", {})
    cfo_to_pat = cf_quality.get("cfo_to_pat_5yr_pct", 85.0)
    fcf_yield = ratios.fcf_yield_pct or 2.5
    
    is_banking = "bank" in sector.lower() or "financial" in sector.lower()
    
    if is_banking:
        cash_score = 80.0 if ratios.roe_pct >= 15.0 else 65.0
    else:
        cash_score = 40.0
        if cfo_to_pat >= 110.0:
            cash_score += 35.0
        elif cfo_to_pat >= 85.0:
            cash_score += 25.0
        elif cfo_to_pat >= 65.0:
            cash_score += 15.0
        else:
            cash_score -= 10.0
            
        if fcf_yield >= 4.0:
            cash_score += 25.0
        elif fcf_yield >= 2.5:
            cash_score += 18.0
        elif fcf_yield >= 1.0:
            cash_score += 10.0
    cash_score = max(10.0, min(100.0, cash_score))

    # 3. Capital Efficiency & Moat (20%)
    roce = ratios.roce_pct
    roe = ratios.roe_pct
    
    eff_score = 30.0
    if roce >= 30.0:
        eff_score += 35.0
    elif roce >= 20.0:
        eff_score += 25.0
    elif roce >= 14.0:
        eff_score += 15.0
    else:
        eff_score += 5.0
        
    if roe >= 22.0:
        eff_score += 35.0
    elif roe >= 16.0:
        eff_score += 25.0
    elif roe >= 11.0:
        eff_score += 15.0
    else:
        eff_score += 5.0
    eff_score = max(10.0, min(100.0, eff_score))

    # 4. Balance Sheet Safety & Capex Trigger (15%)
    debt_eq = ratios.debt_to_equity or 0.0
    int_cov = ratios.interest_coverage or 10.0
    cwip_trigger = analytics.get("balance_sheet_efficiency", {}).get("has_significant_capex_trigger", False)
    
    if is_banking:
        safety_score = 85.0
    else:
        safety_score = 50.0
        if debt_eq <= 0.1:
            safety_score += 30.0
        elif debt_eq <= 0.5:
            safety_score += 20.0
        elif debt_eq <= 1.0:
            safety_score += 5.0
        else:
            safety_score -= 20.0
            
        if int_cov >= 15.0:
            safety_score += 20.0
        elif int_cov >= 6.0:
            safety_score += 12.0
        elif int_cov >= 3.0:
            safety_score += 5.0
        else:
            safety_score -= 15.0
            
    if cwip_trigger:
        safety_score = min(100.0, safety_score + 5.0)  # Growth pipeline bonus
    safety_score = max(10.0, min(100.0, safety_score))

    # 5. Valuation Margin & IRR (20%)
    dcf_upside = projection.dcf_upside_pct
    irr = projection.projected_3yr_irr_cagr_pct
    pe = ratios.stock_pe
    
    val_score = 40.0
    if dcf_upside >= 35.0:
        val_score += 30.0
    elif dcf_upside >= 15.0:
        val_score += 20.0
    elif dcf_upside >= 0.0:
        val_score += 10.0
    else:
        val_score -= 10.0
        
    if irr >= 20.0:
        val_score += 30.0
    elif irr >= 14.0:
        val_score += 20.0
    elif irr >= 9.0:
        val_score += 10.0
    else:
        val_score -= 5.0
    val_score = max(10.0, min(100.0, val_score))

    # Composite Score
    composite = round(
        growth_score * 0.20 +
        cash_score * 0.25 +
        eff_score * 0.20 +
        safety_score * 0.15 +
        val_score * 0.20,
        1
    )

    # Management Execution Alignment Bonus / Penalty
    if doc_intel and doc_intel.promise_vs_delivery:
        delivered = sum(1 for p in doc_intel.promise_vs_delivery if p.status == "Delivered")
        missed = sum(1 for p in doc_intel.promise_vs_delivery if p.status == "Missed")
        total = len(doc_intel.promise_vs_delivery)
        if total >= 2:
            if (delivered / total) >= 0.75:
                composite = min(100.0, round(composite + 2.0, 1))
            elif (missed / total) >= 0.5:
                composite = max(10.0, round(composite - 4.0, 1))

    # Verdict & Investment Thesis Generation
    catalysts = []
    risks = []
    
    if composite >= 82.0:
        verdict = "High Conviction Buy"
    elif composite >= 72.0:
        verdict = "Strong Growth Buy"
    elif composite >= 60.0:
        verdict = "Fair Value Hold"
    elif composite >= 48.0:
        verdict = "Watchlist"
    else:
        verdict = "Avoid"

    thesis_parts = []
    if eff_score >= 80.0:
        thesis_parts.append(f"Industry-leading capital efficiency (ROCE: {roce}%, ROE: {roe}%)")
    if cash_score >= 80.0 and not is_banking:
        thesis_parts.append(f"exceptional cash conversion (CFO/PAT: {cfo_to_pat}%, FCF Yield: {fcf_yield}%)")
    if growth_score >= 75.0:
        thesis_parts.append(f"strong revenue momentum ({sales_cagr}% 3Y CAGR)")
    if val_score >= 75.0:
        thesis_parts.append(f"attractive valuation headroom ({dcf_upside}% DCF upside, {irr}% projected 3Y IRR)")
        
    if cwip_trigger:
        catalysts.append("Upcoming commercial commissioning from active CWIP projects expanding capacity")
    catalysts.append(f"Projected {projection.assumptions.revenue_growth_rate_pct}% forward sales growth with {projection.assumptions.target_opm_pct}% operating margins")
    catalysts.append(f"Exit multiple potential of {projection.assumptions.target_exit_pe}x P/E delivering estimated {projection.target_price_upside_pct}% target return")
    
    if debt_eq > 0.8 and not is_banking:
        risks.append(f"Elevated debt-to-equity ratio of {debt_eq}x in a high-rate regime")
    if pe > 45.0:
        risks.append(f"Premium valuation (P/E {pe}x) leaves little room for earnings misses")
    if cfo_to_pat < 70.0 and not is_banking:
        risks.append("Cash conversion lag due to working capital expansion or inventory buildup")
    if not risks:
        risks.append("Broader macroeconomic demand slowdown or unexpected margin compression from raw material price shocks")

    investment_thesis = f"{name} ({symbol}) represents a {verdict.lower()} candidate. Key pillars: " + "; ".join(thesis_parts) + "."

    return ScoreBreakdown(
        growth_momentum_score=growth_score,
        cash_quality_fcf_score=cash_score,
        capital_efficiency_score=eff_score,
        balance_sheet_safety_score=safety_score,
        valuation_margin_score=val_score,
        total_composite_score=composite,
        verdict=verdict,
        investment_thesis=investment_thesis,
        key_catalysts=catalysts,
        key_risks=risks
    )
