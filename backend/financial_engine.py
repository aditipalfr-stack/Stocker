from typing import Dict, List, Any, Optional
import math
from models import FinancialStatement, FinancialRow

def calculate_cagr(start_val: Optional[float], end_val: Optional[float], years: float) -> Optional[float]:
    if start_val is None or end_val is None or start_val <= 0 or end_val <= 0 or years <= 0:
        return None
    try:
        return round(((end_val / start_val) ** (1.0 / years) - 1.0) * 100.0, 2)
    except Exception:
        return None

def get_row_values(stmt: Optional[FinancialStatement], metric_name: str) -> Dict[str, Optional[float]]:
    if not stmt or not stmt.rows:
        return {}
    target = metric_name.strip().lower()
    # Exact match first
    for row in stmt.rows:
        if row.metric.strip().lower() == target:
            return row.values
    # Fuzzy substring match
    for row in stmt.rows:
        r_met = row.metric.strip().lower()
        if target in r_met or r_met in target:
            return row.values
    return {}

def compute_financial_analytics(
    quarters: Optional[FinancialStatement],
    pl: Optional[FinancialStatement],
    bs: Optional[FinancialStatement],
    cf: Optional[FinancialStatement]
) -> Dict[str, Any]:
    analytics: Dict[str, Any] = {
        "quarterly_analysis": {"trends": []},
        "annual_analysis": {},
        "cash_flow_quality": {},
        "balance_sheet_efficiency": {},
        "working_capital_audit": {},
        "du_pont_analysis": {},
        "forensic_checklist": {},
        "growth_rates": {},
        "historical_parameters": {}
    }
    
    # -------------------------------------------------------------------------
    # 1. Quarterly QoQ & YoY Trends
    # -------------------------------------------------------------------------
    if quarters and quarters.periods:
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

    # -------------------------------------------------------------------------
    # 2. Annual P&L Growth & Margins
    # -------------------------------------------------------------------------
    y_periods = pl.periods if pl else []
    y_sales = get_row_values(pl, "Sales") or get_row_values(pl, "Revenue")
    y_op = get_row_values(pl, "Operating Profit") or get_row_values(pl, "EBITDA")
    y_opm = get_row_values(pl, "OPM %") or get_row_values(pl, "OPM")
    y_pat = get_row_values(pl, "Net Profit") or get_row_values(pl, "PAT")
    y_dep = get_row_values(pl, "Depreciation")
    y_int = get_row_values(pl, "Interest")
    y_pbt = get_row_values(pl, "Profit before tax") or get_row_values(pl, "PBT")
    y_tax = get_row_values(pl, "Tax %") or get_row_values(pl, "Tax")
    
    # CAGRs
    if len(y_periods) >= 4:
        last_p = y_periods[-1]
        p_3y = y_periods[-4]
        analytics["growth_rates"]["sales_cagr_3yr"] = calculate_cagr(y_sales.get(p_3y), y_sales.get(last_p), 3)
        analytics["growth_rates"]["pat_cagr_3yr"] = calculate_cagr(y_pat.get(p_3y), y_pat.get(last_p), 3)
            
    if len(y_periods) >= 6:
        last_p = y_periods[-1]
        p_5y = y_periods[-6]
        analytics["growth_rates"]["sales_cagr_5yr"] = calculate_cagr(y_sales.get(p_5y), y_sales.get(last_p), 5)
        analytics["growth_rates"]["pat_cagr_5yr"] = calculate_cagr(y_pat.get(p_5y), y_pat.get(last_p), 5)

    if len(y_periods) >= 11:
        last_p = y_periods[-1]
        p_10y = y_periods[-11]
        analytics["growth_rates"]["sales_cagr_10yr"] = calculate_cagr(y_sales.get(p_10y), y_sales.get(last_p), 10)
        analytics["growth_rates"]["pat_cagr_10yr"] = calculate_cagr(y_pat.get(p_10y), y_pat.get(last_p), 10)

    # Historical Effective Tax Rate calculation from P&L
    valid_tax_rates = []
    for p in y_periods:
        pbt_val = y_pbt.get(p)
        pat_val = y_pat.get(p)
        if pbt_val and pat_val and pbt_val > 0 and pbt_val > pat_val:
            calc_tax_rate = round(((pbt_val - pat_val) / pbt_val) * 100.0, 1)
            if 10.0 <= calc_tax_rate <= 40.0:
                valid_tax_rates.append(calc_tax_rate)
    
    historical_tax_rate = round(sum(valid_tax_rates[-5:]) / len(valid_tax_rates[-5:]), 1) if valid_tax_rates else 25.0
    analytics["historical_parameters"]["effective_tax_rate_pct"] = historical_tax_rate

    # Historical OPM median
    valid_opms = [y_opm[p] for p in y_periods if y_opm.get(p) is not None]
    hist_opm_median = round(sum(valid_opms[-5:]) / len(valid_opms[-5:]), 1) if len(valid_opms) >= 3 else (valid_opms[-1] if valid_opms else 18.0)
    analytics["historical_parameters"]["opm_median_pct"] = hist_opm_median

    # -------------------------------------------------------------------------
    # 3. Truthful Cash Flow Methodology & FCF Reconciliation
    # -------------------------------------------------------------------------
    # Check reported line items
    cfo_vals = get_row_values(cf, "Cash from Operating Activity") or get_row_values(cf, "Cash from Operations") or get_row_values(cf, "Net Cash flow from Operating Activities")
    direct_capex_vals = (
        get_row_values(cf, "Fixed assets purchased") or
        get_row_values(cf, "Purchase of fixed assets") or
        get_row_values(cf, "Purchase of property, plant and equipment") or
        get_row_values(cf, "Capital expenditure") or
        get_row_values(cf, "Capex")
    )
    
    bs_periods = bs.periods if bs else []
    fixed_assets = get_row_values(bs, "Fixed Assets")
    cwip = get_row_values(bs, "CWIP")
    borrowings = get_row_values(bs, "Borrowings")
    equity_cap = get_row_values(bs, "Equity Capital")
    reserves = get_row_values(bs, "Reserves")
    total_assets = get_row_values(bs, "Total Assets")
    other_assets = get_row_values(bs, "Other Assets")

    fcf_trends = []
    cum_5y_pat = 0.0
    cum_5y_cfo = 0.0
    cum_5y_fcf = 0.0
    valid_fcf_count = 0
    valid_capex_pcts = []
    
    last_5_periods = y_periods[-5:] if len(y_periods) >= 5 else y_periods
    has_direct_capex = bool(direct_capex_vals)
    
    methodology_notes = []
    if cfo_vals:
        methodology_notes.append("Reported Cash Flow from Operating Activities (CFO) line used.")
    else:
        methodology_notes.append("CFO line not reported in Cash Flow statement.")

    if has_direct_capex:
        methodology_notes.append("Direct reported 'Fixed assets purchased / Capex' line item used.")
    else:
        methodology_notes.append("Direct Capex line not itemized in statement; FCF marked as low-confidence/derived.")

    for idx, p in enumerate(y_periods):
        cfo = cfo_vals.get(p)
        pat = y_pat.get(p)
        sales = y_sales.get(p)
        
        capex = None
        capex_method = "Unavailable"
        
        if direct_capex_vals and p in direct_capex_vals and direct_capex_vals[p] is not None:
            capex = abs(direct_capex_vals[p])
            capex_method = "Reported Line Item"
        elif idx > 0 and fixed_assets and p in fixed_assets and y_periods[idx-1] in fixed_assets:
            # Derived via Balance Sheet Gross/Net Block Delta + Depreciation
            fa_curr = fixed_assets.get(p) or 0.0
            fa_prev = fixed_assets.get(y_periods[idx-1]) or 0.0
            dep_val = y_dep.get(p) or 0.0
            cwip_curr = cwip.get(p) or 0.0
            cwip_prev = cwip.get(y_periods[idx-1]) or 0.0
            
            delta_fa = fa_curr - fa_prev
            delta_cwip = cwip_curr - cwip_prev
            calc_capex = delta_fa + dep_val + delta_cwip
            if calc_capex >= 0:
                capex = round(calc_capex, 1)
                capex_method = "Derived from Balance Sheet (FA delta + Dep + CWIP delta)"
        
        # Calculate FCF only if both CFO and Capex are reliable numbers
        fcf = None
        if cfo is not None and capex is not None:
            fcf = round(cfo - capex, 1)
            
        cfo_to_pat = round((cfo / pat) * 100.0, 1) if (cfo is not None and pat is not None and pat > 0) else None
        
        if sales and capex is not None and sales > 0:
            valid_capex_pcts.append(round((capex / sales) * 100.0, 1))

        if p in last_5_periods:
            if pat is not None:
                cum_5y_pat += pat
            if cfo is not None:
                cum_5y_cfo += cfo
            if fcf is not None:
                cum_5y_fcf += fcf
                valid_fcf_count += 1
                
        fcf_trends.append({
            "period": p,
            "reported_cfo_cr": cfo,
            "reported_pat_cr": pat,
            "capex_cr": capex,
            "capex_methodology": capex_method,
            "stocker_derived_fcf_cr": fcf,
            "cfo_to_pat_pct": cfo_to_pat
        })
        
    cfo_to_pat_5yr = round((cum_5y_cfo / cum_5y_pat) * 100.0, 1) if cum_5y_pat > 0 and cum_5y_cfo != 0 else None
    
    # Historical capex-to-sales %
    historical_capex_sales_pct = (
        round(sum(valid_capex_pcts[-5:]) / len(valid_capex_pcts[-5:]), 1)
        if valid_capex_pcts else 5.0
    )
    analytics["historical_parameters"]["capex_to_sales_pct"] = historical_capex_sales_pct

    # Determine Cash Conversion Quality
    if cfo_to_pat_5yr is not None:
        if cfo_to_pat_5yr >= 100.0:
            conv_quality = "Superior (CFO exceeds PAT)"
        elif cfo_to_pat_5yr >= 75.0:
            conv_quality = "Adequate (Healthy Cash Conversion)"
        elif cfo_to_pat_5yr >= 50.0:
            conv_quality = "Moderate (Working Capital Drag)"
        else:
            conv_quality = "Weak (Significant Working Capital Lock-in)"
    else:
        conv_quality = "Inconclusive / Incomplete Data"

    analytics["cash_flow_quality"] = {
        "cumulative_5y_pat_cr": round(cum_5y_pat, 1) if cum_5y_pat > 0 else None,
        "cumulative_5y_cfo_cr": round(cum_5y_cfo, 1) if cum_5y_cfo != 0 else None,
        "cumulative_5y_fcf_cr": round(cum_5y_fcf, 1) if valid_fcf_count >= 3 else None,
        "cfo_to_pat_5yr_pct": cfo_to_pat_5yr,
        "cash_conversion_quality": conv_quality,
        "is_fcf_directly_reported": has_direct_capex,
        "methodology_notes": methodology_notes,
        "fcf_trends": fcf_trends
    }
    
    # -------------------------------------------------------------------------
    # 4. Balance Sheet & Capital Allocation (CWIP & Debt)
    # -------------------------------------------------------------------------
    bs_trends = []
    for p in bs_periods:
        eq = ((equity_cap.get(p) or 0.0) + (reserves.get(p) or 0.0))
        debt = borrowings.get(p)
        fa = fixed_assets.get(p)
        c_work = cwip.get(p) or 0.0
        tot_a = total_assets.get(p)
        
        debt_to_equity = round(debt / eq, 2) if (debt is not None and eq > 0) else None
        cwip_to_fa_pct = round((c_work / fa) * 100.0, 1) if (fa and fa > 0) else None
        
        bs_trends.append({
            "period": p,
            "total_equity_cr": eq if eq > 0 else None,
            "borrowings_cr": debt,
            "fixed_assets_cr": fa,
            "cwip_cr": c_work,
            "total_assets_cr": tot_a,
            "cwip_to_fixed_assets_pct": cwip_to_fa_pct,
            "debt_to_equity": debt_to_equity
        })
        
    latest_bs = bs_trends[-1] if bs_trends else {}
    cwip_pct = latest_bs.get("cwip_to_fixed_assets_pct") or 0.0
    debt_eq = latest_bs.get("debt_to_equity") or 0.0

    analytics["balance_sheet_efficiency"] = {
        "latest_debt_to_equity": debt_eq,
        "latest_cwip_to_net_block_pct": cwip_pct,
        "has_significant_capex_trigger": cwip_pct >= 12.0,
        "bs_trends": bs_trends
    }

    # -------------------------------------------------------------------------
    # 5. DuPont Analysis (Latest Full Year)
    # -------------------------------------------------------------------------
    if y_periods and bs_periods:
        lp_y = y_periods[-1]
        lp_b = bs_periods[-1]
        sales_val = y_sales.get(lp_y)
        pat_val = y_pat.get(lp_y)
        eq_val = ((equity_cap.get(lp_b) or 0.0) + (reserves.get(lp_b) or 0.0))
        assets_val = total_assets.get(lp_b) or (eq_val + (borrowings.get(lp_b) or 0.0))

        net_margin = round((pat_val / sales_val) * 100.0, 2) if (pat_val and sales_val and sales_val > 0) else None
        asset_turnover = round(sales_val / assets_val, 2) if (sales_val and assets_val and assets_val > 0) else None
        financial_leverage = round(assets_val / eq_val, 2) if (assets_val and eq_val and eq_val > 0) else None
        roe_dupont = round((pat_val / eq_val) * 100.0, 2) if (pat_val and eq_val and eq_val > 0) else None

        analytics["du_pont_analysis"] = {
            "period": lp_y,
            "net_profit_margin_pct": net_margin,
            "asset_turnover_ratio": asset_turnover,
            "financial_leverage_multiplier": financial_leverage,
            "calculated_roe_pct": roe_dupont
        }

    # -------------------------------------------------------------------------
    # 6. Forensic Checklist & Data Completeness
    # -------------------------------------------------------------------------
    pat_3y_cagr = analytics["growth_rates"].get("pat_cagr_3yr")
    sales_3y_cagr = analytics["growth_rates"].get("sales_cagr_3yr")
    
    # Calculate Data Completeness (Number of verified non-null core metrics)
    metrics_checked = [
        y_sales.get(y_periods[-1]) if y_periods else None,
        y_pat.get(y_periods[-1]) if y_periods else None,
        cfo_to_pat_5yr,
        debt_eq,
        sales_3y_cagr
    ]
    available_metrics = sum(1 for m in metrics_checked if m is not None)
    completeness_score = round((available_metrics / len(metrics_checked)) * 100.0, 0)
    data_confidence = "High" if completeness_score >= 80 else ("Moderate" if completeness_score >= 60 else "Low / Incomplete")

    analytics["forensic_checklist"] = {
        "cash_flow_health": conv_quality,
        "cfo_to_pat_5yr_pct": cfo_to_pat_5yr,
        "debt_burden_level": "Safe" if debt_eq < 0.8 else ("Moderate" if debt_eq < 1.5 else "High Leverage"),
        "cwip_capex_catalyst": cwip_pct >= 12.0,
        "sales_growth_sustainable": (sales_3y_cagr is not None and sales_3y_cagr >= 10.0),
        "data_completeness_pct": completeness_score,
        "data_confidence": data_confidence
    }
    
    return analytics
