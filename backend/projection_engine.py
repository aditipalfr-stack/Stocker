from typing import List, Dict, Any, Optional
import math
from models import (
    FinancialStatement, KeyRatios, ProjectionAssumption,
    YearlyProjection, ProjectionResult
)
from financial_engine import get_row_values
from doc_intelligence_models import BusinessOutlookResult

def derive_projection_assumptions(
    ratios: KeyRatios,
    pl: Optional[FinancialStatement],
    bs: Optional[FinancialStatement],
    analytics: Dict[str, Any],
    doc_intel: Optional[BusinessOutlookResult] = None,
    user_override: Optional[ProjectionAssumption] = None
) -> ProjectionAssumption:
    """
    Combines:
    1. Historical Baseline (CAGRs, median margins, historical tax and capex rates)
    2. Forward Business Drivers (from Document Intelligence: order book, capacity additions, guided targets)
    3. Management Execution Track Record
    4. Explicit Source Labels for every assumption
    """
    if user_override:
        user_override.revenue_growth_source = "User Override"
        user_override.opm_source = "User Override"
        user_override.capex_source = "User Override"
        user_override.tax_source = "User Override"
        user_override.exit_pe_source = "User Override"
        return user_override

    hist_params = analytics.get("historical_parameters", {})
    growth_rates = analytics.get("growth_rates", {})
    
    # 1. Historical Baselines
    hist_sales_cagr = growth_rates.get("sales_cagr_3yr")
    if hist_sales_cagr is None:
        hist_sales_cagr = ratios.sales_growth_3yr_cagr or 10.0
    hist_sales_cagr = max(-10.0, min(50.0, hist_sales_cagr))

    hist_opm_median = hist_params.get("opm_median_pct", 18.0)
    hist_capex_pct = hist_params.get("capex_to_sales_pct", 5.0)
    hist_tax_rate = hist_params.get("effective_tax_rate_pct", 25.0)
    
    stock_pe = ratios.stock_pe if (ratios.stock_pe and 5.0 <= ratios.stock_pe <= 100.0) else 22.0

    # 2. Integrate Forward Document Intelligence Drivers
    forward_drivers = []
    derived_growth = hist_sales_cagr
    growth_source = "Historical 3-Year CAGR"
    derived_opm = hist_opm_median
    opm_source = "Historical Median (P&L)"
    confidence = "Moderate"

    if doc_intel:
        # Check Execution Track Record
        pvd = doc_intel.promise_vs_delivery or []
        delivered_count = sum(1 for p in pvd if p.status == "Delivered")
        missed_count = sum(1 for p in pvd if p.status == "Missed")
        total_pvd = len(pvd)

        # Check Growth Drivers & Capacity/Order Book
        growth_drivers_list = doc_intel.growth_drivers or []
        for g in growth_drivers_list:
            if g.driver_title:
                forward_drivers.append(f"{g.driver_title} ({g.driver_type}): {g.execution_status}")

        # Check Sector-Specific Signals
        dm = doc_intel.demand_momentum
        if dm and dm.company_specific_metrics:
            for m in dm.company_specific_metrics:
                forward_drivers.append(f"{m.get('metric')}: {m.get('value')}")

        # Signal 1: Order Book / Capacity Expansion Impact
        has_major_expansion = any(
            "capacity" in str(g.description).lower() or "order" in str(g.description).lower() or "expansion" in str(g.driver_type).lower()
            for g in growth_drivers_list
        )
        
        has_high_cwip = analytics.get("balance_sheet_efficiency", {}).get("has_significant_capex_trigger", False)

        if has_major_expansion or has_high_cwip:
            if total_pvd >= 2 and (delivered_count / total_pvd) >= 0.6:
                # Strong execution + verified capex/orders -> boost growth projection slightly towards forward capacity
                boost = 2.0 if derived_growth < 15.0 else 1.0
                derived_growth = round(derived_growth + boost, 1)
                growth_source = "Forward Expansion & Order Backlog + Strong Execution"
                confidence = "High"
            else:
                growth_source = "Historical Baseline with Ongoing CWIP Deployment"
                confidence = "Moderate"

        # Signal 2: Capex Tapering / Capital Intensity Normalization
        # If document intelligence confirms peak capex rollout is tapering (e.g. pan-India 5G completed):
        recent_changes_text = str(doc_intel.what_changed_recently).lower()
        if "tapering" in recent_changes_text or "completed" in recent_changes_text:
            if hist_capex_pct > 10.0:
                hist_capex_pct = 8.5
                forward_drivers.append("Capex Normalization: 5G rollout completed; capital intensity tapering to maintenance/steady state")

        # Signal 3: Margin Guidance / Cost Pressure
        rc = doc_intel.risks_and_cash
        if rc and rc.margin_and_cost_pressures and "compress" in rc.margin_and_cost_pressures.lower():
            derived_opm = max(5.0, round(derived_opm - 1.0, 1))
            opm_source = "Historical Median adjusted for Stated Input Cost Pressure"
        elif total_pvd >= 2 and delivered_count == total_pvd:
            # Consistent delivery supports stable/expanding margin
            opm_source = "Historical Median supported by Stated Operating Leverage"
            confidence = "High"

    # Set boundaries
    derived_growth = round(max(3.0, min(35.0, derived_growth)), 1)
    derived_opm = round(max(4.0, min(65.0, derived_opm)), 1)
    hist_capex_pct = round(max(1.0, min(25.0, hist_capex_pct)), 1)
    hist_tax_rate = round(max(15.0, min(35.0, hist_tax_rate)), 1)
    exit_pe = round(max(10.0, min(50.0, stock_pe)), 1)

    return ProjectionAssumption(
        revenue_growth_rate_pct=derived_growth,
        revenue_growth_source=growth_source,
        target_opm_pct=derived_opm,
        opm_source=opm_source,
        capex_pct_of_sales=hist_capex_pct,
        capex_source="Company Historical Average (Capex / Sales)",
        effective_tax_rate_pct=hist_tax_rate,
        tax_source="Company Historical Effective Tax Rate (Tax / PBT)",
        terminal_growth_rate_pct=5.0,
        discount_rate_wacc_pct=12.0,
        target_exit_pe=exit_pe,
        exit_pe_source="Normalized Historical P/E Multiple",
        projection_confidence=confidence,
        forward_drivers_used=forward_drivers[:4]
    )

def run_projections(
    ratios: KeyRatios,
    pl: Optional[FinancialStatement],
    bs: Optional[FinancialStatement],
    cf: Optional[FinancialStatement],
    analytics: Optional[Dict[str, Any]] = None,
    doc_intel: Optional[BusinessOutlookResult] = None,
    assumptions: Optional[ProjectionAssumption] = None,
    scenario_type: str = "Base Case"
) -> ProjectionResult:
    y_periods = pl.periods if pl else []
    y_sales = get_row_values(pl, "Sales") or get_row_values(pl, "Revenue")
    y_dep = get_row_values(pl, "Depreciation")
    y_int = get_row_values(pl, "Interest")
    
    # 1. Historical Baselines
    latest_sales = 0.0
    for p in y_periods:
        if y_sales.get(p):
            latest_sales = y_sales[p]
            
    if latest_sales <= 0:
        latest_sales = ratios.market_cap_cr / max(ratios.stock_pe, 1.0) if ratios.market_cap_cr > 0 else 1000.0

    y_pat = get_row_values(pl, "Net Profit") or get_row_values(pl, "PAT")
    latest_pat = y_pat.get(y_periods[-1], 0.0) or 0.0 if y_periods else 0.0
    hist_net_margin = (latest_pat / latest_sales) if (latest_sales > 0 and latest_pat > 0) else 0.12

    # Identify banking & financial institutions
    is_banking = False
    if pl and pl.rows:
        for r in pl.rows:
            if "financing profit" in r.metric.lower() or "interest earned" in r.metric.lower():
                is_banking = True
                break

    # 3-year historical sales CAGR
    hist_sales_cagr = 10.0
    if len(y_periods) >= 4:
        s_start = y_sales.get(y_periods[-4])
        s_end = y_sales.get(y_periods[-1])
        if s_start and s_end and s_start > 0 and s_end > 0:
            hist_sales_cagr = round(((s_end / s_start) ** (1.0 / 3.0) - 1.0) * 100.0, 1)

    y_opm = get_row_values(pl, "OPM %") or get_row_values(pl, "OPM")
    valid_opms = [y_opm[p] for p in y_periods if y_opm.get(p) is not None]
    hist_opm_median = round(sum(valid_opms[-5:]) / len(valid_opms[-5:]), 1) if valid_opms else 18.0

    # Shares outstanding calculation
    current_price = ratios.current_price if ratios.current_price > 0 else 100.0
    market_cap_cr = ratios.market_cap_cr if ratios.market_cap_cr > 0 else 1000.0
    shares_outstanding_cr = market_cap_cr / current_price  # e.g. 17.63 Lakh Cr / 1303 = 1353 Cr shares
    if shares_outstanding_cr <= 0:
        shares_outstanding_cr = 1.0
        
    # Net Debt
    borrowings = get_row_values(bs, "Borrowings")
    investments = get_row_values(bs, "Investments")
    latest_bs_p = bs.periods[-1] if (bs and bs.periods) else ""
    debt = borrowings.get(latest_bs_p, 0.0) or 0.0
    cash_inv = (investments.get(latest_bs_p, 0.0) or 0.0)
    net_debt = debt - cash_inv if not is_banking else 0.0
    
    # Historical depreciation & interest rate %
    latest_dep = y_dep.get(y_periods[-1], 0.0) or 0.0 if y_periods else 0.0
    latest_int = y_int.get(y_periods[-1], 0.0) or 0.0 if y_periods else 0.0
    dep_rate = (latest_dep / latest_sales) if latest_sales > 0 else 0.04
    int_rate = (latest_int / latest_sales) if latest_sales > 0 else 0.02

    # If no assumptions provided, derive dynamically from evidence
    if assumptions is None:
        assumptions = derive_projection_assumptions(
            ratios=ratios,
            pl=pl,
            bs=bs,
            analytics=analytics or {},
            doc_intel=doc_intel
        )
        
    growth_rate = assumptions.revenue_growth_rate_pct
    opm_rate = assumptions.target_opm_pct
    # Cap forward ongoing capex rate at 12.0% for DCF terminal sustainability
    capex_rate = min(12.0, assumptions.capex_pct_of_sales) if not is_banking else 2.0
    tax_rate = assumptions.effective_tax_rate_pct
    wacc = assumptions.discount_rate_wacc_pct / 100.0
    terminal_g = assumptions.terminal_growth_rate_pct / 100.0
    exit_pe = assumptions.target_exit_pe
    
    if wacc <= terminal_g:
        wacc = terminal_g + 0.04

    # 2. Build 5-Year Forward Projection
    projections: List[YearlyProjection] = []
    pv_fcf_sum = 0.0
    prev_rev = latest_sales
    start_fy = 2026
    
    for yr in range(1, 6):
        fy_name = f"FY{start_fy + yr - 1}E"
        proj_rev = round(prev_rev * (1.0 + growth_rate / 100.0), 1)
        prev_rev = proj_rev
        
        if is_banking:
            proj_ebitda = round(proj_rev * (opm_rate / 100.0), 1)
            proj_dep = round(proj_rev * dep_rate, 1)
            proj_ebit = proj_ebitda
            proj_int = 0.0
            proj_pbt = round(proj_rev * (hist_net_margin / max(0.01, (1.0 - (tax_rate / 100.0)))), 1)
            proj_tax = round(proj_pbt * (tax_rate / 100.0), 1)
            proj_pat = round(proj_rev * hist_net_margin, 1)
            proj_cfo = proj_pat
            proj_capex = round(proj_rev * 0.015, 1)
            proj_fcf = round(proj_cfo - proj_capex, 1)
        else:
            proj_ebitda = round(proj_rev * (opm_rate / 100.0), 1)
            proj_dep = round(proj_rev * dep_rate, 1)
            proj_ebit = max(0.0, proj_ebitda - proj_dep)
            proj_int = round(latest_int * max(0.2, (1.0 - (yr - 1) * 0.08)), 1)
            proj_pbt = max(0.0, proj_ebit - proj_int)
            proj_tax = round(proj_pbt * (tax_rate / 100.0), 1)
            proj_pat = round(proj_pbt - proj_tax, 1)
            proj_cfo = round(proj_pat + proj_dep * 0.85, 1)
            proj_capex = round(proj_rev * (capex_rate / 100.0), 1)
            proj_fcf = round(proj_cfo - proj_capex, 1)
        
        proj_eps = round(proj_pat / shares_outstanding_cr, 2)
        
        discount_factor = (1.0 + wacc) ** yr
        pv_fcf_sum += (proj_fcf / discount_factor)
        
        projections.append(YearlyProjection(
            year=fy_name,
            revenue_cr=proj_rev,
            opm_pct=opm_rate,
            ebitda_cr=proj_ebitda,
            depreciation_cr=proj_dep,
            interest_cr=proj_int,
            pbt_cr=proj_pbt,
            tax_cr=proj_tax,
            pat_cr=proj_pat,
            eps=proj_eps,
            cfo_cr=proj_cfo,
            capex_cr=proj_capex,
            fcf_cr=proj_fcf
        ))
        
    # 3. Terminal Value & DCF Valuation
    terminal_fcf = projections[-1].fcf_cr * (1.0 + terminal_g)
    terminal_value = terminal_fcf / (wacc - terminal_g)
    pv_terminal_value = terminal_value / ((1.0 + wacc) ** 5)
    
    enterprise_value = pv_fcf_sum + pv_terminal_value
    equity_value = enterprise_value - (net_debt if net_debt > 0 else net_debt * 0.5)
    dcf_fair_value = round(equity_value / shares_outstanding_cr, 2)
    dcf_upside = round(((dcf_fair_value - current_price) / current_price) * 100.0, 1)
    
    # 4. Exit Multiple Valuation (Year 3 Target Price)
    yr3_eps = projections[2].eps
    target_price_exit_pe = round(yr3_eps * exit_pe, 2)
    target_price_upside = round(((target_price_exit_pe - current_price) / current_price) * 100.0, 1)
    
    # 3-Yr Expected IRR (CAGR)
    if target_price_exit_pe > 0 and current_price > 0:
        irr = round(((target_price_exit_pe / current_price) ** (1.0 / 3.0) - 1.0) * 100.0, 1)
    else:
        irr = 0.0

    return ProjectionResult(
        assumptions=assumptions,
        historical_revenue_cagr_3yr=hist_sales_cagr,
        historical_opm_median=hist_opm_median,
        projections=projections,
        dcf_fair_value_per_share=dcf_fair_value,
        dcf_upside_pct=dcf_upside,
        target_price_exit_pe=target_price_exit_pe,
        target_price_upside_pct=target_price_upside,
        projected_3yr_irr_cagr_pct=irr,
        scenario_type=scenario_type,
        data_quality="High" if (analytics and analytics.get("forensic_checklist", {}).get("data_confidence") == "High") else "Moderate"
    )

def generate_scenario_suite(
    ratios: KeyRatios,
    pl: Optional[FinancialStatement],
    bs: Optional[FinancialStatement],
    cf: Optional[FinancialStatement],
    analytics: Optional[Dict[str, Any]] = None,
    doc_intel: Optional[BusinessOutlookResult] = None
) -> Dict[str, Any]:
    """Generates Base, Bull, and Bear scenarios side-by-side grounded in evidence."""
    base_res = run_projections(
        ratios=ratios,
        pl=pl,
        bs=bs,
        cf=cf,
        analytics=analytics,
        doc_intel=doc_intel,
        scenario_type="Base Case"
    )
    
    # Bull Case: Stated forward catalysts deliver on time (+3% revenue growth, +1.5% OPM leverage, +15% exit PE)
    bull_assump = ProjectionAssumption(
        revenue_growth_rate_pct=base_res.assumptions.revenue_growth_rate_pct + 3.0,
        revenue_growth_source="Bull: Accelerated Commissioning & Volume Ramp-up",
        target_opm_pct=base_res.assumptions.target_opm_pct + 1.5,
        opm_source="Bull: Operating Leverage Expansion",
        capex_pct_of_sales=base_res.assumptions.capex_pct_of_sales,
        capex_source=base_res.assumptions.capex_source,
        effective_tax_rate_pct=base_res.assumptions.effective_tax_rate_pct,
        tax_source=base_res.assumptions.tax_source,
        terminal_growth_rate_pct=base_res.assumptions.terminal_growth_rate_pct + 0.5,
        discount_rate_wacc_pct=base_res.assumptions.discount_rate_wacc_pct - 0.5,
        target_exit_pe=round(base_res.assumptions.target_exit_pe * 1.15, 1),
        exit_pe_source="Bull: 15% Multiple Re-rating on Target Delivery",
        projection_confidence=base_res.assumptions.projection_confidence,
        forward_drivers_used=base_res.assumptions.forward_drivers_used
    )
    bull_res = run_projections(
        ratios=ratios,
        pl=pl,
        bs=bs,
        cf=cf,
        analytics=analytics,
        doc_intel=doc_intel,
        assumptions=bull_assump,
        scenario_type="Bull Case"
    )
    
    # Bear Case: Capex delays, raw material inflation (-4% revenue growth, -2.0% OPM contraction, -20% exit PE)
    bear_assump = ProjectionAssumption(
        revenue_growth_rate_pct=max(3.0, base_res.assumptions.revenue_growth_rate_pct - 4.0),
        revenue_growth_source="Bear: Execution Delay / Demand Slowdown",
        target_opm_pct=max(5.0, base_res.assumptions.target_opm_pct - 2.0),
        opm_source="Bear: Input Cost Headwind & Pricing Pressure",
        capex_pct_of_sales=base_res.assumptions.capex_pct_of_sales,
        capex_source=base_res.assumptions.capex_source,
        effective_tax_rate_pct=base_res.assumptions.effective_tax_rate_pct,
        tax_source=base_res.assumptions.tax_source,
        terminal_growth_rate_pct=max(3.0, base_res.assumptions.terminal_growth_rate_pct - 1.0),
        discount_rate_wacc_pct=base_res.assumptions.discount_rate_wacc_pct + 1.0,
        target_exit_pe=round(base_res.assumptions.target_exit_pe * 0.8, 1),
        exit_pe_source="Bear: 20% Multiple De-rating on Execution Miss",
        projection_confidence=base_res.assumptions.projection_confidence,
        forward_drivers_used=base_res.assumptions.forward_drivers_used
    )
    bear_res = run_projections(
        ratios=ratios,
        pl=pl,
        bs=bs,
        cf=cf,
        analytics=analytics,
        doc_intel=doc_intel,
        assumptions=bear_assump,
        scenario_type="Bear Case"
    )
    
    return {
        "base_case": base_res,
        "bull_case": bull_res,
        "bear_case": bear_res,
        "current_price": ratios.current_price,
        "valuation_bridge": {
            "bear_target": bear_res.target_price_exit_pe,
            "base_target": base_res.target_price_exit_pe,
            "bull_target": bull_res.target_price_exit_pe,
            "fair_value_dcf": base_res.dcf_fair_value_per_share
        }
    }
