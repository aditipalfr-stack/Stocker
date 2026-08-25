from typing import List, Dict, Any, Optional
import math
from models import (
    FinancialStatement, KeyRatios, ProjectionAssumption,
    YearlyProjection, ProjectionResult
)
from financial_engine import get_row_values

def run_projections(
    ratios: KeyRatios,
    pl: FinancialStatement,
    bs: FinancialStatement,
    cf: FinancialStatement,
    assumptions: Optional[ProjectionAssumption] = None,
    scenario_type: str = "Base Case"
) -> ProjectionResult:
    y_periods = pl.periods
    y_sales = get_row_values(pl, "Sales") or get_row_values(pl, "Revenue")
    y_opm = get_row_values(pl, "OPM %") or get_row_values(pl, "OPM")
    y_pat = get_row_values(pl, "Net Profit") or get_row_values(pl, "PAT")
    y_dep = get_row_values(pl, "Depreciation")
    y_int = get_row_values(pl, "Interest")
    
    # 1. Historical baselines
    latest_sales = 0.0
    valid_opms = []
    for p in y_periods:
        if y_sales.get(p):
            latest_sales = y_sales[p]
        if y_opm.get(p) is not None:
            valid_opms.append(y_opm[p])
            
    hist_opm_median = round(sum(valid_opms[-5:]) / len(valid_opms[-5:]), 2) if len(valid_opms) >= 3 else (valid_opms[-1] if valid_opms else 18.0)
    
    # 3-year historical sales CAGR
    hist_sales_cagr = 12.0
    if len(y_periods) >= 4:
        s_start = y_sales.get(y_periods[-4])
        s_end = y_sales.get(y_periods[-1])
        if s_start and s_end and s_start > 0 and s_end > 0:
            hist_sales_cagr = round(((s_end / s_start) ** (1.0 / 3.0) - 1.0) * 100.0, 2)
            
    # Shares outstanding in Cr
    current_price = ratios.current_price if ratios.current_price > 0 else 100.0
    market_cap_cr = ratios.market_cap_cr if ratios.market_cap_cr > 0 else 1000.0
    shares_outstanding_cr = market_cap_cr / current_price  # in Cr shares
    if shares_outstanding_cr <= 0:
        shares_outstanding_cr = 1.0
        
    # Net Debt
    borrowings = get_row_values(bs, "Borrowings")
    other_assets = get_row_values(bs, "Other Assets")
    investments = get_row_values(bs, "Investments")
    latest_bs_p = bs.periods[-1] if bs.periods else ""
    debt = borrowings.get(latest_bs_p, 0.0) or 0.0
    cash_inv = (investments.get(latest_bs_p, 0.0) or 0.0)
    net_debt = debt - cash_inv
    
    # Historical ratios for depreciation & interest
    latest_dep = y_dep.get(y_periods[-1], 0.0) or 0.0 if y_periods else 0.0
    latest_int = y_int.get(y_periods[-1], 0.0) or 0.0 if y_periods else 0.0
    dep_rate = (latest_dep / latest_sales) if latest_sales > 0 else 0.04
    int_rate = (latest_int / latest_sales) if latest_sales > 0 else 0.02

    # If no assumptions provided, use default
    if assumptions is None:
        assumptions = ProjectionAssumption(
            revenue_growth_rate_pct=max(hist_sales_cagr, 8.0),
            target_opm_pct=hist_opm_median,
            capex_pct_of_sales=5.0,
            effective_tax_rate_pct=25.0,
            terminal_growth_rate_pct=5.0,
            discount_rate_wacc_pct=12.0,
            target_exit_pe=max(min(ratios.stock_pe, 45.0), 18.0) if ratios.stock_pe > 0 else 22.0
        )
        
    # Apply scenario adjustments if specified
    growth_rate = assumptions.revenue_growth_rate_pct
    opm_rate = assumptions.target_opm_pct
    capex_rate = assumptions.capex_pct_of_sales
    tax_rate = assumptions.effective_tax_rate_pct
    wacc = assumptions.discount_rate_wacc_pct / 100.0
    terminal_g = assumptions.terminal_growth_rate_pct / 100.0
    exit_pe = assumptions.target_exit_pe
    
    # Prevent WACC <= terminal_g
    if wacc <= terminal_g:
        wacc = terminal_g + 0.04

    # 2. Build 5-Year Forward Projection
    projections: List[YearlyProjection] = []
    pv_fcf_sum = 0.0
    prev_rev = latest_sales
    
    # Starting year naming
    start_fy = 2026
    
    for yr in range(1, 6):
        fy_name = f"FY{start_fy + yr - 1}E"
        proj_rev = round(prev_rev * (1.0 + growth_rate / 100.0), 1)
        prev_rev = proj_rev
        
        proj_ebitda = round(proj_rev * (opm_rate / 100.0), 1)
        proj_dep = round(proj_rev * dep_rate, 1)
        proj_ebit = max(0.0, proj_ebitda - proj_dep)
        
        # Interest decreases slightly as debt is paid
        proj_int = round(latest_int * max(0.2, (1.0 - (yr - 1) * 0.1)), 1)
        proj_pbt = max(0.0, proj_ebit - proj_int)
        proj_tax = round(proj_pbt * (tax_rate / 100.0), 1)
        proj_pat = round(proj_pbt - proj_tax, 1)
        
        proj_eps = round(proj_pat / shares_outstanding_cr, 2)
        
        # CFO ~ PAT + Depreciation - minor WC drag
        proj_cfo = round(proj_pat + proj_dep * 0.9, 1)
        proj_capex = round(proj_rev * (capex_rate / 100.0), 1)
        proj_fcf = round(proj_cfo - proj_capex, 1)
        
        # Discount FCF
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
        scenario_type=scenario_type
    )

