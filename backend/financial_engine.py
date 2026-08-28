from typing import Dict, List, Any, Optional
import math
import re
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
    # 7. Comprehensive Formula & Calculation Transparency (Plain English & Inputs)
    # -------------------------------------------------------------------------
    last_p = y_periods[-1] if y_periods else ""
    p_3y = y_periods[-4] if len(y_periods) >= 4 else ""
    
    last_sales = y_sales.get(last_p) if last_p else None
    base_sales_3y = y_sales.get(p_3y) if p_3y else None
    last_pat = y_pat.get(last_p) if last_p else None
    base_pat_3y = y_pat.get(p_3y) if p_3y else None
    
    latest_fcf_item = fcf_trends[-1] if fcf_trends else {}
    latest_cfo = latest_fcf_item.get("reported_cfo_cr")
    latest_capex = latest_fcf_item.get("capex_cr")
    latest_fcf = latest_fcf_item.get("stocker_derived_fcf_cr")
    latest_capex_meth = latest_fcf_item.get("capex_methodology", "Unavailable")
    
    latest_q_trend = analytics["quarterly_analysis"]["trends"][-1] if analytics["quarterly_analysis"]["trends"] else {}
    
    analytics["formula_transparency"] = {
        "sales_cagr_3yr": {
            "metric_name": "Sales 3-Year CAGR",
            "value": analytics["growth_rates"].get("sales_cagr_3yr"),
            "formula": "((Sales_Latest / Sales_3Yr_Ago) ^ (1/3) - 1) × 100",
            "inputs": {
                "Latest Sales (₹ Cr)": last_sales,
                "Sales 3 Years Ago (₹ Cr)": base_sales_3y,
                "Latest Period": last_p,
                "Base Period": p_3y
            },
            "source": "Audited Profit & Loss Statement (Screener.in)",
            "explanation": f"Revenue grew at a compounded annual growth rate of {analytics['growth_rates'].get('sales_cagr_3yr')}% from ₹{base_sales_3y:,.0f} Cr ({p_3y}) to ₹{last_sales:,.0f} Cr ({last_p})." if (last_sales and base_sales_3y) else "Historical 3-year P&L data insufficient."
        },
        "pat_cagr_3yr": {
            "metric_name": "Profit (PAT) 3-Year CAGR",
            "value": analytics["growth_rates"].get("pat_cagr_3yr"),
            "formula": "((PAT_Latest / PAT_3Yr_Ago) ^ (1/3) - 1) × 100",
            "inputs": {
                "Latest PAT (₹ Cr)": last_pat,
                "PAT 3 Years Ago (₹ Cr)": base_pat_3y,
                "Latest Period": last_p,
                "Base Period": p_3y
            },
            "source": "Audited Profit & Loss Statement (Screener.in)",
            "explanation": f"Net profit compounded at {analytics['growth_rates'].get('pat_cagr_3yr')}% per annum from ₹{base_pat_3y:,.0f} Cr ({p_3y}) to ₹{last_pat:,.0f} Cr ({last_p})." if (last_pat and base_pat_3y and last_pat > 0 and base_pat_3y > 0) else "PAT CAGR calculation requires positive base and terminal net profit."
        },
        "cfo_to_pat_5yr": {
            "metric_name": "5-Year CFO to PAT Conversion %",
            "value": cfo_to_pat_5yr,
            "formula": "(Cumulative 5-Year CFO / Cumulative 5-Year PAT) × 100",
            "inputs": {
                "Cumulative 5Y CFO (₹ Cr)": round(cum_5y_cfo, 1),
                "Cumulative 5Y PAT (₹ Cr)": round(cum_5y_pat, 1),
                "Period Range": f"{y_periods[-5]} to {y_periods[-1]}" if len(y_periods) >= 5 else "Last 5 Years"
            },
            "source": "Audited Cash Flow & Profit/Loss Statements",
            "explanation": f"The company converted {cfo_to_pat_5yr}% of its accounting net profit into actual operational cash flow over the last 5 financial years ({conv_quality})." if cfo_to_pat_5yr else "Cash flow conversion data incomplete."
        },
        "free_cash_flow": {
            "metric_name": "Free Cash Flow (FCF)",
            "value": latest_fcf,
            "formula": "FCF = CFO - Capex",
            "inputs": {
                "Reported CFO (₹ Cr)": latest_cfo,
                "Capex (₹ Cr)": latest_capex,
                "Capex Methodology": latest_capex_meth,
                "Period": last_p
            },
            "source": "Audited Cash Flow Statement / Balance Sheet Gross Block Reconciliation",
            "explanation": f"In {last_p}, operating cash flow was ₹{latest_cfo:,.0f} Cr and capital expenditure was ₹{latest_capex:,.0f} Cr ({latest_capex_meth}), resulting in ₹{latest_fcf:,.0f} Cr of free cash flow." if (latest_cfo is not None and latest_capex is not None and latest_fcf is not None) else "FCF requires reliable CFO and Capex figures."
        },
        "debt_to_equity": {
            "metric_name": "Debt to Equity Ratio",
            "value": debt_eq,
            "formula": "Total Borrowings / Total Net Worth (Equity + Reserves)",
            "inputs": {
                "Total Borrowings (₹ Cr)": latest_bs.get("borrowings_cr"),
                "Total Equity (₹ Cr)": latest_bs.get("total_equity_cr"),
                "Period": latest_bs.get("period")
            },
            "source": "Audited Balance Sheet (Screener.in)",
            "explanation": f"The company has ₹{debt_eq} of debt for every ₹1.00 of shareholder equity."
        },
        "latest_yoy_sales_growth": {
            "metric_name": "Latest Quarter YoY Sales Growth",
            "value": latest_q_trend.get("sales_growth_yoy_pct"),
            "formula": "((Sales_Q_Latest - Sales_Q_Prior_Year) / Sales_Q_Prior_Year) × 100",
            "inputs": {
                "Latest Quarter Sales (₹ Cr)": latest_q_trend.get("sales"),
                "Quarter": latest_q_trend.get("period")
            },
            "source": "Quarterly Financial Results",
            "explanation": f"Quarterly sales grew {latest_q_trend.get('sales_growth_yoy_pct')}% year-over-year in {latest_q_trend.get('period')}." if latest_q_trend.get("sales_growth_yoy_pct") is not None else "YoY quarter comparison pending."
        }
    }
    
    return analytics

# -----------------------------------------------------------------------------
# CHRONOLOGICAL & MATHEMATICAL PROMISE VS DELIVERY VERIFICATION HELPERS
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
# CHRONOLOGICAL & MATHEMATICAL PROMISE VS DELIVERY VERIFICATION HELPERS
# -----------------------------------------------------------------------------

def parse_filing_period_to_year(period_str: Optional[str]) -> Optional[float]:
    """
    Parses filing periods, fiscal quarters, calendar months, and exact dates
    into a continuous float year index for strict chronological verification.
    
    Equivalences:
      - 'Q1 FY25' and 'Jun 2024' -> 2024.458 (Q1 ending June 2024)
      - 'Q2 FY25' and 'Sep 2024' -> 2024.708 (Q2 ending September 2024)
      - 'Q3 FY25' and 'Dec 2024' -> 2024.958 (Q3 ending December 2024)
      - 'Q4 FY25' and 'Mar 2025' -> 2025.208 (Q4 ending March 2025)
      - 'FY24' / 'FY2024' -> 2024.25 (Audited full-year results ending March 2024)
      - 'FY25' / 'FY2025' -> 2025.25
      - 'FY26' / 'FY2026' -> 2026.25
      - '24 Jul 2026' -> 2026.565
      - 'July 2026' -> 2026.540
    """
    if not period_str or not isinstance(period_str, str):
        return None
    s = period_str.strip().upper()
    
    MONTHS_MAP = {
        "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
        "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12
    }
    
    # 1. Exact Date (e.g. '24 Jul 2026', '24-07-2026', '2026-07-24', '24/07/2026')
    m_exact = re.search(r'\b(\d{1,2})[-/ ]+(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*[-/ ]+(\d{4})\b', s)
    if m_exact:
        d = int(m_exact.group(1))
        m = MONTHS_MAP.get(m_exact.group(2)[:3], 6)
        y = int(m_exact.group(3))
        return round(y + (m - 1) / 12.0 + d / 365.0, 4)
        
    m_iso = re.search(r'\b(20\d\d)-(\d{2})-(\d{2})\b', s)
    if m_iso:
        y, m, d = int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3))
        return round(y + (m - 1) / 12.0 + d / 365.0, 4)
        
    m_dmy = re.search(r'\b(\d{1,2})[-/](\d{1,2})[-/](20\d\d)\b', s)
    if m_dmy:
        d, m, y = int(m_dmy.group(1)), int(m_dmy.group(2)), int(m_dmy.group(3))
        return round(y + (m - 1) / 12.0 + d / 365.0, 4)

    # 2. Fiscal Quarter (e.g. 'Q1 FY25', 'Q2 FY2026', 'Q3 FY24', 'Q4 FY25')
    m_q_fy = re.search(r'Q([1-4])\s*(?:FY)?\s*(\d{2,4})', s)
    if m_q_fy:
        q_num = int(m_q_fy.group(1))
        raw_yr = int(m_q_fy.group(2))
        fy_year = raw_yr if raw_yr > 2000 else (2000 + raw_yr)
        
        # In Indian FY (Apr-Mar):
        # Q1 FYxx ends in June (fy_year - 1) -> Month 6
        # Q2 FYxx ends in Sept (fy_year - 1) -> Month 9
        # Q3 FYxx ends in Dec (fy_year - 1)  -> Month 12
        # Q4 FYxx ends in Mar (fy_year)      -> Month 3
        if q_num == 1:
            return round((fy_year - 1) + (6 - 1) / 12.0 + 15 / 365.0, 4)  # 2024.458
        elif q_num == 2:
            return round((fy_year - 1) + (9 - 1) / 12.0 + 15 / 365.0, 4)  # 2024.708
        elif q_num == 3:
            return round((fy_year - 1) + (12 - 1) / 12.0 + 15 / 365.0, 4) # 2024.958
        elif q_num == 4:
            return round(fy_year + (3 - 1) / 12.0 + 15 / 365.0, 4)        # 2025.208

    # 3. Month and Year (e.g. 'Jun 2024', 'September 2025', 'Jul 2026')
    m_my = re.search(r'\b(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*\s*(20\d\d)\b', s)
    if m_my:
        m = MONTHS_MAP.get(m_my.group(1)[:3], 6)
        y = int(m_my.group(2))
        return round(y + (m - 1) / 12.0 + 15 / 365.0, 4)

    # 4. Fiscal Year (e.g. 'FY24', 'FY2025', 'FY 26')
    m_fy = re.search(r'FY\s*(\d{2,4})', s)
    if m_fy:
        raw_yr = int(m_fy.group(1))
        fy_year = raw_yr if raw_yr > 2000 else (2000 + raw_yr)
        return round(fy_year + (3 - 1) / 12.0 + 15 / 365.0, 4) # 2024.208

    # 5. Plain 4-digit Year (e.g. '2026', '2027')
    m_yr4 = re.search(r'\b(20\d\d)\b', s)
    if m_yr4:
        y = int(m_yr4.group(1))
        return float(y)

    return None

def verify_promise_vs_delivery_item(
    item: Dict[str, Any],
    pl_stmt: Optional[Any] = None,
    quarters_stmt: Optional[Any] = None,
    current_year: Optional[float] = None
) -> Dict[str, Any]:
    """
    Deterministically enforces strict chronology, deadline rules, and mathematical statement calculations:
    1. Dynamic Runtime Year: Computes continuous float year from datetime.now(timezone.utc) if current_year is not passed.
    2. Same Filing / Same Event Guard: A promise and outcome citing the same document/URL cannot prove delivery.
    3. Strict Chronology Assertion: Requires act_yr > prom_yr. Backwards or equal dates are downgraded to 'Not Enough Evidence'.
    4. Code is the Absolute Authority for status and financial_numbers_check:
       - Numerical guidance with structured data -> exact code calculation of achievement % and variance.
       - Numerical guidance without structured data -> 'Not Enough Evidence', financial_numbers_check overwritten.
       - Target deadline in future -> 'In Progress'.
       - Qualitative milestone with verified completion event -> 'Delivered'.
       - Qualitative milestone without clear proof -> 'Not Enough Evidence'.
    """
    res = dict(item)
    
    # 1. Dynamic Runtime Current Year (Never hardcoded!)
    if current_year is None:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        curr_yr = now.year + (now.month - 1) / 12.0 + now.day / 365.0
    else:
        curr_yr = float(current_year)
        
    promise_period = item.get("promised_in_period")
    actual_period = item.get("actual_in_period")
    target_timeline = item.get("target_timeline") or item.get("management_promise")
    
    url_prom = (item.get("source_url_promise") or "").strip().rstrip("/")
    url_act = (item.get("source_url_actual") or "").strip().rstrip("/")
    
    # 2. Missing Citations Guard
    if not url_prom or not url_act:
        res["status"] = "Not Enough Evidence"
        res["stocker_analysis"] = "Missing Document Citations: Required filing source URLs are not verified."
        res["financial_numbers_check"] = "Not enough structured financial evidence to verify this claim."
        return res

    # 3. Same Filing / Same Event Guard
    if url_prom == url_act:
        res["status"] = "Not Enough Evidence"
        res["stocker_analysis"] = "Evidence from Same Filing: A promise and its delivered outcome cannot be verified from the same source document without an independent subsequent filing."
        res["financial_numbers_check"] = "Not enough structured financial evidence to verify this claim."
        return res
        
    prom_yr = parse_filing_period_to_year(promise_period)
    act_yr = parse_filing_period_to_year(actual_period)
    target_yr = parse_filing_period_to_year(target_timeline)
    
    # 4. Strict Chronology Check (act_yr must be strictly > prom_yr)
    if prom_yr is not None and act_yr is not None:
        if act_yr <= prom_yr:
            res["status"] = "Not Enough Evidence"
            res["stocker_analysis"] = f"Chronological Mismatch: Outcome period ({actual_period}) does not occur strictly after the guidance baseline ({promise_period}). Evidence rejected by Stocker chronological verification."
            res["financial_numbers_check"] = "Not enough structured financial evidence to verify this claim."
            return res

    # Helper to extract metric values from statement (supports Pydantic model or dict)
    def _extract_metric_dict(stmt_obj: Any, metric_name: str) -> Dict[str, Optional[float]]:
        if not stmt_obj:
            return {}
        if hasattr(stmt_obj, "rows"):
            return get_row_values(stmt_obj, metric_name)
        if isinstance(stmt_obj, dict):
            periods = stmt_obj.get("periods") or stmt_obj.get("years") or []
            rows = stmt_obj.get("rows") or []
            target = metric_name.strip().lower()
            if isinstance(rows, list):
                for r in rows:
                    if isinstance(r, dict):
                        m = r.get("metric", "").strip().lower()
                        if target in m or m in target:
                            v = r.get("values", {})
                            if isinstance(v, dict):
                                return v
                            elif isinstance(v, list) and len(v) == len(periods):
                                return {periods[i]: v[i] for i in range(len(periods))}
            elif isinstance(rows, dict):
                for m_k, v_list in rows.items():
                    if target in m_k.lower() or m_k.lower() in target:
                        if isinstance(v_list, list) and len(v_list) == len(periods):
                            return {periods[i]: v_list[i] for i in range(len(periods))}
        return {}

    # Helper to extract periods list
    def _get_stmt_periods(stmt_obj: Any) -> List[str]:
        if not stmt_obj: return []
        if hasattr(stmt_obj, "periods"): return list(stmt_obj.periods)
        if isinstance(stmt_obj, dict): return list(stmt_obj.get("periods") or stmt_obj.get("years") or [])
        return []

    # 5. Check if Numerical Guidance Promise
    pl_periods = _get_stmt_periods(pl_stmt)
    y_sales = _extract_metric_dict(pl_stmt, "Sales") or _extract_metric_dict(pl_stmt, "Revenue")
    y_opm = _extract_metric_dict(pl_stmt, "OPM %") or _extract_metric_dict(pl_stmt, "OPM")
    
    m_growth = re.search(r'(\d+(?:\.\d+)?)\s*%\s*(?:revenue|sales|growth|cagr|margin)', item.get("management_promise", ""), re.IGNORECASE)
    
    if m_growth:
        promised_pct = float(m_growth.group(1))
        
        # Match target year period or latest period in P&L
        target_p = None
        if actual_period and actual_period in pl_periods:
            target_p = actual_period
        else:
            for p in pl_periods:
                p_yr = parse_filing_period_to_year(p)
                if p_yr and act_yr and abs(p_yr - act_yr) < 0.3:
                    target_p = p
                    break
        if not target_p and pl_periods:
            target_p = pl_periods[-1]
            
        p_idx = pl_periods.index(target_p) if target_p in pl_periods else len(pl_periods) - 1
        p_prev = pl_periods[p_idx - 1] if p_idx > 0 else None
        
        s_curr = y_sales.get(target_p) if target_p else None
        s_prev = y_sales.get(p_prev) if p_prev else None
        opm_curr = y_opm.get(target_p) if target_p else None
        
        if s_curr and s_prev and s_prev > 0:
            act_growth = round(((s_curr - s_prev) / s_prev) * 100.0, 1)
            achieve_pct = round((act_growth / promised_pct) * 100.0, 1) if promised_pct > 0 else 0.0
            variance_pct = round(act_growth - promised_pct, 1)
            
            res["financial_numbers_check"] = (
                f"Promised {promised_pct}% revenue growth; audited {target_p} reported revenue of ₹{s_curr:,.0f} Cr "
                f"reflects {act_growth}% YoY growth (Achievement Rate: {achieve_pct}% of guidance; variance {variance_pct:+.1f}%). "
                f"Audited OPM stood at {opm_curr if opm_curr is not None else 'N/A'}%."
            )
            
            # Deterministic Status Assignment
            if target_yr is not None and target_yr > curr_yr:
                res["status"] = "In Progress"
            elif achieve_pct >= 90.0:
                res["status"] = "Delivered"
            elif achieve_pct < 85.0:
                res["status"] = "Missed"
            else:
                res["status"] = "In Progress"
        else:
            # Structured statements missing or inconclusive: do NOT keep AI numbers or assume Delivered
            res["financial_numbers_check"] = "Not enough structured financial evidence to verify this claim."
            if target_yr is not None and target_yr > curr_yr:
                res["status"] = "In Progress"
            else:
                res["status"] = "Not Enough Evidence"
                res["stocker_analysis"] = "Missing Structured Financial Data: Audited statements for the target period are not available to verify this quantitative guidance."
    else:
        # 6. Qualitative / Operational Milestone Verification
        outcome_text = f"{item.get('actual_outcome', '')} {item.get('actual_quote', '')}"
        
        if target_yr is not None and target_yr > curr_yr:
            res["status"] = "In Progress"
            res["financial_numbers_check"] = "Qualitative operational milestone (tracked in progress)."
            res["stocker_analysis"] = f"Milestone In Progress: Stated target timeline ({target_timeline or f'FY{int(target_yr)}'}) matures in the future ({target_yr:.0f}). Ongoing execution tracked against interim audited progress."
        else:
            # Simple, robust structured keyword matching
            completion_match = re.search(
                r'\b(commissioned|operational|commercial production|commercial operations commenced|launched|completed acquisition|acquired|approval received|won order|order received|executed|achieved cod)\b',
                outcome_text,
                re.IGNORECASE
            )
            delay_match = re.search(r'\b(delayed|postponed|deferred|pushed back|rescheduled)\b', outcome_text, re.IGNORECASE)
            cancel_match = re.search(r'\b(cancelled|shelved|dropped|abandoned)\b', outcome_text, re.IGNORECASE)
            
            if completion_match and act_yr is not None and prom_yr is not None and act_yr > prom_yr:
                res["status"] = "Delivered"
                res["financial_numbers_check"] = f"Qualitative milestone verified: {completion_match.group(1).capitalize()} confirmed in subsequent filing ({actual_period})."
            elif delay_match:
                res["status"] = "Delayed"
                res["financial_numbers_check"] = f"Qualitative milestone delayed: {delay_match.group(1).capitalize()} reported in subsequent filing ({actual_period})."
            elif cancel_match:
                res["status"] = "Missed"
                res["financial_numbers_check"] = f"Qualitative milestone missed: {cancel_match.group(1).capitalize()} reported in subsequent filing ({actual_period})."
            else:
                res["status"] = "Not Enough Evidence"
                res["stocker_analysis"] = f"Uncertain Qualitative Evidence: Subsequent filing ({actual_period}) does not contain verifiable completion proof for this milestone."
                res["financial_numbers_check"] = "Not enough structured financial evidence to verify this claim."

    # 7. Final Target Deadline Protection (Always overrides!)
    if target_yr is not None and target_yr > curr_yr:
        res["status"] = "In Progress"
        if not res.get("stocker_analysis") or "Missed" in res.get("stocker_analysis", "") or "Delivered" in res.get("stocker_analysis", ""):
            res["stocker_analysis"] = f"Milestone In Progress: Stated target timeline ({target_timeline or f'FY{int(target_yr)}'}) matures in the future ({target_yr:.0f}). Ongoing execution tracked against interim audited progress."
            
    return res

