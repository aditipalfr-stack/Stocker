from typing import Dict, List, Any, Optional
import math
from models import FinancialStatement, FinancialRow

def calculate_cagr(start_val: float, end_val: float, years: float) -> Optional[float]:
    if start_val <= 0 or end_val <= 0 or years <= 0:
        return None
    try:
        return round(((end_val / start_val) ** (1.0 / years) - 1.0) * 100.0, 2)
    except Exception:
        return None

def get_row_values(stmt: FinancialStatement, metric_name: str) -> Dict[str, Optional[float]]:
    for row in stmt.rows:
        if row.metric.strip().lower() == metric_name.strip().lower():
            return row.values
    # Fallback fuzzy match
    target = metric_name.strip().lower()
    for row in stmt.rows:
        r_met = row.metric.strip().lower()
        if target in r_met or r_met in target:
            return row.values
    return {}

def compute_financial_analytics(quarters: FinancialStatement, pl: FinancialStatement, bs: FinancialStatement, cf: FinancialStatement) -> Dict[str, Any]:
    analytics = {
        "quarterly_analysis": {},
        "annual_analysis": {},
        "cash_flow_quality": {},
        "balance_sheet_efficiency": {},
        "working_capital_audit": {},
        "du_pont_analysis": {},
        "forensic_checklist": {},
        "growth_rates": {}
    }
    
    # 1. Quarterly QoQ & YoY Trends
    q_periods = quarters.periods
    q_sales = get_row_values(quarters, "Sales") or get_row_values(quarters, "Revenue")
    q_op = get_row_values(quarters, "Operating Profit") or get_row_values(quarters, "EBITDA")
    q_opm = get_row_values(quarters, "OPM %") or get_row_values(quarters, "OPM")
    q_pat = get_row_values(quarters, "Net Profit") or get_row_values(quarters, "PAT")
    
    quarterly_trends = []
    for i, p in enumerate(q_periods):
        curr_sales = q_sales.get(p)
        curr_op = q_op.get(p)
        curr_opm = q_opm.get(p)
        curr_pat = q_pat.get(p)
        
        # QoQ
        qoq_sales_growth = None
        qoq_pat_growth = None
        if i > 0 and curr_sales is not None and q_periods[i-1] in q_sales:
            prev_s = q_sales[q_periods[i-1]]
            if prev_s and prev_s > 0:
                qoq_sales_growth = round(((curr_sales - prev_s) / prev_s) * 100.0, 2)
                
        if i > 0 and curr_pat is not None and q_periods[i-1] in q_pat:
            prev_p = q_pat[q_periods[i-1]]
            if prev_p and prev_p != 0:
                qoq_pat_growth = round(((curr_pat - prev_p) / abs(prev_p)) * 100.0, 2)
                
        # YoY (4 quarters back)
        yoy_sales_growth = None
        yoy_pat_growth = None
        if i >= 4 and curr_sales is not None and q_periods[i-4] in q_sales:
            prev_y_s = q_sales[q_periods[i-4]]
            if prev_y_s and prev_y_s > 0:
                yoy_sales_growth = round(((curr_sales - prev_y_s) / prev_y_s) * 100.0, 2)
                
        if i >= 4 and curr_pat is not None and q_periods[i-4] in q_pat:
            prev_y_p = q_pat[q_periods[i-4]]
            if prev_y_p and prev_y_p != 0:
                yoy_pat_growth = round(((curr_pat - prev_y_p) / abs(prev_y_p)) * 100.0, 2)
                
        quarterly_trends.append({
            "period": p,
            "sales": curr_sales,
            "operating_profit": curr_op,
            "opm_pct": curr_opm,
            "net_profit": curr_pat,
            "sales_growth_qoq_pct": qoq_sales_growth,
            "sales_growth_yoy_pct": yoy_sales_growth,
            "pat_growth_qoq_pct": qoq_pat_growth,
            "pat_growth_yoy_pct": yoy_pat_growth
        })
    analytics["quarterly_analysis"]["trends"] = quarterly_trends
    
    # 2. Annual P&L Growth & Margins
    y_periods = pl.periods
    y_sales = get_row_values(pl, "Sales") or get_row_values(pl, "Revenue")
    y_op = get_row_values(pl, "Operating Profit") or get_row_values(pl, "EBITDA")
    y_opm = get_row_values(pl, "OPM %") or get_row_values(pl, "OPM")
    y_pat = get_row_values(pl, "Net Profit") or get_row_values(pl, "PAT")
    y_eps = get_row_values(pl, "EPS in Rs") or get_row_values(pl, "EPS")
    
    # CAGRs
    if len(y_periods) >= 4:
        last_p = y_periods[-1]
        p_3y = y_periods[-4]
        if y_sales.get(p_3y) and y_sales.get(last_p):
            analytics["growth_rates"]["sales_cagr_3yr"] = calculate_cagr(y_sales[p_3y], y_sales[last_p], 3)
        if y_pat.get(p_3y) and y_pat.get(last_p):
            analytics["growth_rates"]["pat_cagr_3yr"] = calculate_cagr(y_pat[p_3y], y_pat[last_p], 3)
            
    if len(y_periods) >= 6:
        last_p = y_periods[-1]
        p_5y = y_periods[-6]
        if y_sales.get(p_5y) and y_sales.get(last_p):
            analytics["growth_rates"]["sales_cagr_5yr"] = calculate_cagr(y_sales[p_5y], y_sales[last_p], 5)
        if y_pat.get(p_5y) and y_pat.get(last_p):
            analytics["growth_rates"]["pat_cagr_5yr"] = calculate_cagr(y_pat[p_5y], y_pat[last_p], 5)

    if len(y_periods) >= 11:
        last_p = y_periods[-1]
        p_10y = y_periods[-11]
        if y_sales.get(p_10y) and y_sales.get(last_p):
            analytics["growth_rates"]["sales_cagr_10yr"] = calculate_cagr(y_sales[p_10y], y_sales[last_p], 10)
        if y_pat.get(p_10y) and y_pat.get(last_p):
            analytics["growth_rates"]["pat_cagr_10yr"] = calculate_cagr(y_pat[p_10y], y_pat[last_p], 10)

    # 3. Cash Flow Quality & FCF
    cfo_vals = get_row_values(cf, "Cash from Operating Activity") or get_row_values(cf, "Cash from Operations")
    cfi_vals = get_row_values(cf, "Cash from Investing Activity")
    fixed_assets_purchased = get_row_values(cf, "Fixed assets purchased") or get_row_values(cf, "Capex")
    
    fcf_trends = []
    cum_5y_pat = 0.0
    cum_5y_cfo = 0.0
    cum_5y_fcf = 0.0
    
    last_5_periods = y_periods[-5:] if len(y_periods) >= 5 else y_periods
    for p in y_periods:
        cfo = cfo_vals.get(p, 0.0) or 0.0
        pat = y_pat.get(p, 0.0) or 0.0
        
        # Capex from direct line or CFI
        capex = fixed_assets_purchased.get(p)
        if capex is None:
            cfi = cfi_vals.get(p, 0.0) or 0.0
            capex = abs(cfi) if cfi < 0 else 0.0
        else:
            capex = abs(capex)
            
        fcf = cfo - capex
        cfo_to_pat = round((cfo / pat) * 100.0, 2) if pat > 0 else None
        
        if p in last_5_periods:
            cum_5y_pat += pat
            cum_5y_cfo += cfo
            cum_5y_fcf += fcf
            
        fcf_trends.append({
            "period": p,
            "cfo_cr": cfo,
            "pat_cr": pat,
            "capex_cr": capex,
            "fcf_cr": fcf,
            "cfo_to_pat_pct": cfo_to_pat
        })
        
    cfo_to_pat_5yr = round((cum_5y_cfo / cum_5y_pat) * 100.0, 2) if cum_5y_pat > 0 else 0.0
    
    analytics["cash_flow_quality"] = {
        "cumulative_5y_pat_cr": round(cum_5y_pat, 1),
        "cumulative_5y_cfo_cr": round(cum_5y_cfo, 1),
        "cumulative_5y_fcf_cr": round(cum_5y_fcf, 1),
        "cfo_to_pat_5yr_pct": cfo_to_pat_5yr,
        "is_cash_conversion_superior": cfo_to_pat_5yr >= 80.0,
        "fcf_trends": fcf_trends
    }
    
    # 4. Balance Sheet & Capital Allocation (CWIP & Debt)
    borrowings = get_row_values(bs, "Borrowings")
    reserves = get_row_values(bs, "Reserves")
    equity_cap = get_row_values(bs, "Equity Capital")
    fixed_assets = get_row_values(bs, "Fixed Assets")
    cwip = get_row_values(bs, "CWIP")
    other_assets = get_row_values(bs, "Other Assets")
    total_assets = get_row_values(bs, "Total Assets")
    
    bs_trends = []
    for p in bs.periods:
        eq = (equity_cap.get(p, 0.0) or 0.0) + (reserves.get(p, 0.0) or 0.0)
        debt = borrowings.get(p, 0.0) or 0.0
        fa = fixed_assets.get(p, 0.0) or 0.0
        c_work = cwip.get(p, 0.0) or 0.0
        tot_a = total_assets.get(p, 0.0) or 0.0
        
        debt_to_equity = round(debt / eq, 2) if eq > 0 else 0.0
        cwip_to_fa_pct = round((c_work / fa) * 100.0, 2) if fa > 0 else 0.0
        
        bs_trends.append({
            "period": p,
            "total_equity_cr": eq,
            "borrowings_cr": debt,
            "fixed_assets_cr": fa,
            "cwip_cr": c_work,
            "total_assets_cr": tot_a,
            "cwip_to_fixed_assets_pct": cwip_to_fa_pct,
            "debt_to_equity": debt_to_equity
        })
        
    latest_bs = bs_trends[-1] if bs_trends else {}
    cwip_pct = latest_bs.get("cwip_to_fixed_assets_pct", 0.0) or 0.0
    debt_eq = latest_bs.get("debt_to_equity", 0.0) or 0.0

    analytics["balance_sheet_efficiency"] = {
        "latest_debt_to_equity": debt_eq,
        "latest_cwip_to_net_block_pct": cwip_pct,
        "has_significant_capex_trigger": cwip_pct >= 12.0,
        "bs_trends": bs_trends
    }

    # 5. DuPont Analysis (Latest Year)
    if y_periods and bs.periods:
        lp_y = y_periods[-1]
        lp_b = bs.periods[-1]
        sales_val = y_sales.get(lp_y, 0.0) or 0.0
        pat_val = y_pat.get(lp_y, 0.0) or 0.0
        eq_val = (equity_cap.get(lp_b, 0.0) or 0.0) + (reserves.get(lp_b, 0.0) or 0.0)
        assets_val = total_assets.get(lp_b, 0.0) or (eq_val + (borrowings.get(lp_b, 0.0) or 0.0))

        net_margin = round((pat_val / sales_val) * 100.0, 2) if sales_val > 0 else 0.0
        asset_turnover = round(sales_val / assets_val, 2) if assets_val > 0 else 0.0
        financial_leverage = round(assets_val / eq_val, 2) if eq_val > 0 else 1.0
        roe_dupont = round((pat_val / eq_val) * 100.0, 2) if eq_val > 0 else 0.0

        analytics["du_pont_analysis"] = {
            "period": lp_y,
            "net_profit_margin_pct": net_margin,
            "asset_turnover_ratio": asset_turnover,
            "financial_leverage_multiplier": financial_leverage,
            "calculated_roe_pct": roe_dupont
        }

    # 6. Forensic Checklist & Early Warning Signals
    pat_3y_cagr = analytics["growth_rates"].get("pat_cagr_3yr")
    sales_3y_cagr = analytics["growth_rates"].get("sales_cagr_3yr")
    
    analytics["forensic_checklist"] = {
        "cash_flow_health": "Superior" if cfo_to_pat_5yr >= 100.0 else ("Adequate" if cfo_to_pat_5yr >= 75.0 else "Weak"),
        "cfo_to_pat_5yr_pct": cfo_to_pat_5yr,
        "debt_burden_level": "Safe" if debt_eq < 0.8 else ("Moderate" if debt_eq < 1.5 else "High Leverage"),
        "cwip_capex_catalyst": cwip_pct >= 12.0,
        "sales_growth_sustainable": (sales_3y_cagr is not None and sales_3y_cagr >= 10.0),
        "earnings_quality_flag": "High" if (cfo_to_pat_5yr >= 80.0 and debt_eq < 1.0) else "Moderate / Watch"
    }
    
    return analytics
