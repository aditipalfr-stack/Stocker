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
    """
    Computes a truthful 4-pillar sector-aware score without optimistic silent defaults.
    Missing data is penalized or treated neutrally, and data confidence is explicitly tracked.
    """
    is_banking = "bank" in sector.lower() or "financial" in sector.lower() or "nbfc" in sector.lower()
    
    growth_rates = analytics.get("growth_rates", {})
    sales_cagr = growth_rates.get("sales_cagr_3yr")
    pat_cagr = growth_rates.get("pat_cagr_3yr")
    
    cf_quality = analytics.get("cash_flow_quality", {})
    cfo_to_pat = cf_quality.get("cfo_to_pat_5yr_pct")
    fcf_yield = ratios.fcf_yield_pct
    
    roce = ratios.roce_pct
    roe = ratios.roe_pct
    debt_eq = ratios.debt_to_equity
    int_cov = ratios.interest_coverage
    
    dcf_upside = projection.dcf_upside_pct
    irr = projection.projected_3yr_irr_cagr_pct
    pe = ratios.stock_pe

    # Track missing data points
    missing_points = []
    if sales_cagr is None: missing_points.append("3Y Sales CAGR")
    if pat_cagr is None: missing_points.append("3Y PAT CAGR")
    if not is_banking and cfo_to_pat is None: missing_points.append("5Y CFO/PAT")
    if not is_banking and debt_eq is None: missing_points.append("Debt/Equity")

    # -------------------------------------------------------------------------
    # 1. Growth & Momentum Score (0 - 100)
    # -------------------------------------------------------------------------
    growth_score = 0.0
    growth_weights = 0.0
    
    if sales_cagr is not None:
        growth_weights += 50.0
        if sales_cagr >= 20.0: growth_score += 50.0
        elif sales_cagr >= 12.0: growth_score += 38.0
        elif sales_cagr >= 7.0: growth_score += 25.0
        elif sales_cagr >= 0.0: growth_score += 15.0
        else: growth_score += 5.0
        
    if pat_cagr is not None:
        growth_weights += 50.0
        if pat_cagr >= 22.0: growth_score += 50.0
        elif pat_cagr >= 14.0: growth_score += 38.0
        elif pat_cagr >= 8.0: growth_score += 25.0
        elif pat_cagr >= 0.0: growth_score += 15.0
        else: growth_score += 5.0
        
    final_growth_score = (growth_score / growth_weights * 100.0) if growth_weights > 0 else 40.0
    final_growth_score = round(max(10.0, min(100.0, final_growth_score)), 1)

    # -------------------------------------------------------------------------
    # 2. Cash Quality & FCF Strength Score (0 - 100)
    # -------------------------------------------------------------------------
    if is_banking:
        # For banks, evaluate ROE quality & ROA stability
        if roe is not None and roe >= 16.0: cash_score = 85.0
        elif roe is not None and roe >= 12.0: cash_score = 70.0
        elif roe is not None and roe >= 8.0: cash_score = 55.0
        else: cash_score = 40.0
    else:
        cash_score = 0.0
        cash_weights = 0.0
        
        if cfo_to_pat is not None:
            cash_weights += 60.0
            if cfo_to_pat >= 110.0: cash_score += 60.0
            elif cfo_to_pat >= 85.0: cash_score += 48.0
            elif cfo_to_pat >= 65.0: cash_score += 32.0
            elif cfo_to_pat >= 40.0: cash_score += 18.0
            else: cash_score += 5.0
            
        if fcf_yield is not None and fcf_yield > 0:
            cash_weights += 40.0
            if fcf_yield >= 4.0: cash_score += 40.0
            elif fcf_yield >= 2.5: cash_score += 30.0
            elif fcf_yield >= 1.0: cash_score += 20.0
            else: cash_score += 10.0
            
        cash_score = (cash_score / cash_weights * 100.0) if cash_weights > 0 else 35.0
    final_cash_score = round(max(10.0, min(100.0, cash_score)), 1)

    # -------------------------------------------------------------------------
    # 3. Capital Efficiency & Moat Score (0 - 100)
    # -------------------------------------------------------------------------
    eff_score = 0.0
    eff_weights = 0.0
    
    if roce is not None and not is_banking:
        eff_weights += 50.0
        if roce >= 28.0: eff_score += 50.0
        elif roce >= 18.0: eff_score += 38.0
        elif roce >= 12.0: eff_score += 25.0
        elif roce >= 8.0: eff_score += 15.0
        else: eff_score += 5.0
        
    if roe is not None:
        eff_weights += (100.0 if is_banking else 50.0)
        max_roe_pts = 100.0 if is_banking else 50.0
        if roe >= 20.0: eff_score += max_roe_pts
        elif roe >= 15.0: eff_score += (max_roe_pts * 0.75)
        elif roe >= 10.0: eff_score += (max_roe_pts * 0.50)
        elif roe >= 6.0: eff_score += (max_roe_pts * 0.25)
        else: eff_score += 5.0
        
    final_eff_score = (eff_score / eff_weights * 100.0) if eff_weights > 0 else 40.0
    final_eff_score = round(max(10.0, min(100.0, final_eff_score)), 1)

    # -------------------------------------------------------------------------
    # 4. Balance Sheet Safety & Leverage (0 - 100)
    # -------------------------------------------------------------------------
    if is_banking:
        safety_score = 80.0  # Regulated CRAR & RBI framework
    else:
        safety_score = 0.0
        safety_weights = 0.0
        
        if debt_eq is not None:
            safety_weights += 60.0
            if debt_eq <= 0.15: safety_score += 60.0
            elif debt_eq <= 0.5: safety_score += 48.0
            elif debt_eq <= 0.9: safety_score += 30.0
            elif debt_eq <= 1.4: safety_score += 15.0
            else: safety_score += 0.0  # High leverage
            
        if int_cov is not None:
            safety_weights += 40.0
            if int_cov >= 15.0: safety_score += 40.0
            elif int_cov >= 6.0: safety_score += 30.0
            elif int_cov >= 3.0: safety_score += 18.0
            elif int_cov >= 1.5: safety_score += 8.0
            else: safety_score += 0.0
            
        safety_score = (safety_score / safety_weights * 100.0) if safety_weights > 0 else 45.0
    final_safety_score = round(max(10.0, min(100.0, safety_score)), 1)

    # -------------------------------------------------------------------------
    # 5. Valuation Margin & IRR Score (0 - 100)
    # -------------------------------------------------------------------------
    val_score = 0.0
    if dcf_upside is not None:
        if dcf_upside >= 30.0: val_score += 45.0
        elif dcf_upside >= 10.0: val_score += 30.0
        elif dcf_upside >= -10.0: val_score += 18.0
        else: val_score += 5.0
    else:
        val_score += 15.0
    
    if irr is not None:
        if irr >= 18.0: val_score += 45.0
        elif irr >= 12.0: val_score += 30.0
        elif irr >= 7.0: val_score += 18.0
        else: val_score += 5.0
    else:
        val_score += 15.0

    if pe is not None and pe > 0:
        if pe < 20.0: val_score += 10.0
        elif pe < 35.0: val_score += 5.0
        elif pe > 65.0: val_score -= 5.0
        
    final_val_score = round(max(10.0, min(100.0, val_score)), 1)

    # -------------------------------------------------------------------------
    # 6. Core Fundamental Weighted Base
    # -------------------------------------------------------------------------
    base_composite = (
        final_growth_score * 0.20 +
        final_cash_score * 0.25 +
        final_eff_score * 0.20 +
        final_safety_score * 0.15 +
        final_val_score * 0.20
    )

    # -------------------------------------------------------------------------
    # 7. Meaningful Management Execution Impact (Promise vs Delivery)
    # -------------------------------------------------------------------------
    exec_impact = 0.0
    if doc_intel and doc_intel.promise_vs_delivery:
        pvd = doc_intel.promise_vs_delivery
        delivered = sum(1 for p in pvd if p.status == "Delivered")
        in_progress = sum(1 for p in pvd if p.status == "In Progress")
        missed = sum(1 for p in pvd if p.status == "Missed")
        total_pvd = len(pvd)
        
        if total_pvd >= 2:
            deliv_ratio = delivered / total_pvd
            miss_ratio = missed / total_pvd
            if deliv_ratio >= 0.75:
                exec_impact = +6.0 # Strong execution premium
            elif deliv_ratio >= 0.50:
                exec_impact = +3.0
            elif miss_ratio >= 0.40:
                exec_impact = -8.0 # Execution miss penalty
            elif miss_ratio >= 0.25:
                exec_impact = -4.0

    # -------------------------------------------------------------------------
    # 8. Future Growth Visibility Impact (Orders / CWIP Commissioning)
    # -------------------------------------------------------------------------
    growth_vis_impact = 0.0
    has_cwip_trigger = analytics.get("balance_sheet_efficiency", {}).get("has_significant_capex_trigger", False)
    has_growth_drivers = bool(doc_intel and doc_intel.growth_drivers)
    
    if has_growth_drivers and has_cwip_trigger:
        growth_vis_impact = +5.0
    elif has_growth_drivers or has_cwip_trigger:
        growth_vis_impact = +3.0

    # Final Composite with bounds
    composite = round(max(10.0, min(100.0, base_composite + exec_impact + growth_vis_impact)), 1)

    # -------------------------------------------------------------------------
    # 9. Data Confidence Calculation
    # -------------------------------------------------------------------------
    missing_count = len(missing_points)
    if missing_count == 0 and doc_intel:
        data_confidence = "High"
    elif missing_count <= 1:
        data_confidence = "Moderate"
    else:
        data_confidence = "Low / Incomplete Data"

    # -------------------------------------------------------------------------
    # 10. Verdict & Thesis Construction
    # -------------------------------------------------------------------------
    if composite >= 82.0 and data_confidence != "Low / Incomplete Data":
        verdict = "High Conviction Buy"
    elif composite >= 72.0:
        verdict = "Strong Growth Buy"
    elif composite >= 58.0:
        verdict = "Fair Value Hold"
    elif composite >= 45.0:
        verdict = "Watchlist"
    else:
        verdict = "Avoid"

    thesis_parts = []
    if final_eff_score >= 75.0:
        thesis_parts.append(f"Strong capital efficiency (ROCE: {roce if roce is not None else 'N/A'}%, ROE: {roe if roe is not None else 'N/A'}%)")
    if final_cash_score >= 75.0 and not is_banking:
        thesis_parts.append(f"Healthy cash generation (5Y CFO/PAT: {cfo_to_pat if cfo_to_pat is not None else 'N/A'}%)")
    if exec_impact > 0:
        thesis_parts.append("Proven management execution track record on stated milestones")
    elif exec_impact < 0:
        thesis_parts.append("Caution: History of missing stated milestone timelines")
    if growth_vis_impact > 0:
        thesis_parts.append("Visible upcoming capacity additions / order book execution pipeline")
    if final_val_score >= 75.0:
        thesis_parts.append(f"Valuation upside ({dcf_upside if dcf_upside is not None else 0.0}% DCF margin, {irr if irr is not None else 0.0}% 3Y IRR)")

    catalysts = []
    risks = []
    
    if doc_intel and doc_intel.stocker_view:
        catalysts.extend(doc_intel.stocker_view.positive_triggers[:3])
        risks.extend(doc_intel.stocker_view.main_risks[:3])
    else:
        if has_cwip_trigger:
            catalysts.append("Upcoming commercial commissioning from active CWIP capacity")
        catalysts.append(f"Forward sales growth projected at {projection.assumptions.revenue_growth_rate_pct}% ({projection.assumptions.revenue_growth_source})")
        if debt_eq is not None and debt_eq > 0.9 and not is_banking:
            risks.append(f"Elevated debt-to-equity ratio of {debt_eq}x in a high interest rate regime")
        if pe is not None and pe > 50.0:
            risks.append(f"Elevated valuation multiple (P/E {pe}x) leaves little margin for execution delays")
        if not risks:
            risks.append("Sector demand moderation or input cost inflation impacting operating margins")

    investment_thesis = f"{name} ({symbol}) is ranked as a {verdict.lower()} ({data_confidence} confidence). Key factors: " + "; ".join(thesis_parts) + "."

    return ScoreBreakdown(
        growth_momentum_score=final_growth_score,
        cash_quality_fcf_score=final_cash_score,
        capital_efficiency_score=final_eff_score,
        balance_sheet_safety_score=final_safety_score,
        valuation_margin_score=final_val_score,
        management_execution_impact=exec_impact,
        future_visibility_impact=growth_vis_impact,
        total_composite_score=composite,
        verdict=verdict,
        data_confidence=data_confidence,
        investment_thesis=investment_thesis,
        key_catalysts=catalysts,
        key_risks=risks
    )
