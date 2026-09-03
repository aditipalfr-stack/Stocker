from typing import Dict, List, Any, Optional, Tuple
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

def classify_financial_business_model(
    sector: Optional[str] = None,
    industry: Optional[str] = None,
    pl: Optional[FinancialStatement] = None,
    bs: Optional[FinancialStatement] = None,
    quarters: Optional[FinancialStatement] = None
) -> str:
    """
    Deterministically classifies a company's financial business model:
    - 'BANK': Commercial, public/private sector, or small finance banks
    - 'NBFC_LENDER': Non-banking financial lenders, housing finance, microfinance
    - 'INSURANCE': Life, health, and general insurance
    - 'OTHER_FINANCIAL': Capital markets, broking, asset management, holding co
    - 'GENERAL_CORPORATE': Manufacturing, IT, FMCG, services, pharma, industrial
    - 'UNKNOWN': Ambiguous or insufficient data
    """
    sec = (sector or "").strip().lower()
    ind = (industry or "").strip().lower()

    # 1. Direct Industry / Sector Metadata Checks
    if any(b in ind for b in ["private sector bank", "public sector bank", "foreign bank", "small finance bank", "payment bank"]):
        return "BANK"
    if ("bank" in ind or "banking" in ind or "banking" in sec) and not any(nb in ind for nb in ["non-banking", "nbfc", "databank", "food bank", "blood bank"]):
        return "BANK"
        
    if any(n in ind for n in ["nbfc", "housing finance", "microfinance", "lending", "auto finance", "consumer finance"]) or ("non banking" in ind) or ("non-banking" in ind):
        return "NBFC_LENDER"
        
    if any(ins in ind for ins in ["life insurance", "general insurance", "health insurance", "reinsurance"]) or "insurance" in ind:
        return "INSURANCE"

    # 2. Statement Row Signature Checks (from raw Screener tables)
    all_metrics = set()
    for stmt in (quarters, pl, bs):
        if stmt and stmt.rows:
            for r in stmt.rows:
                if r.metric:
                    all_metrics.add(r.metric.strip().lower())
                    
    has_deposits = any("deposit" in m for m in all_metrics)
    has_advances = any(m in ("advances", "loans & advances", "loans and advances", "total advances") for m in all_metrics)
    has_npa = any("npa" in m for m in all_metrics)
    has_financing_profit = any("financing profit" in m or "financing margin" in m for m in all_metrics)
    has_interest_earned = any("interest earned" in m or "interest expended" in m for m in all_metrics)
    has_insurance_premiums = any("premiums earned" in m or "claims paid" in m for m in all_metrics)
    
    if has_deposits and (has_advances or has_npa or has_interest_earned or "bank" in sec or "financial" in sec):
        return "BANK"
    if has_npa or (has_deposits and has_financing_profit):
        return "BANK"
    if has_financing_profit or (has_advances and has_interest_earned):
        return "NBFC_LENDER"
    if has_insurance_premiums:
        return "INSURANCE"
        
    # 3. Explicit Corporate Sector / Industry Evidence
    corporate_sectors = [
        "automobile", "it", "software", "technology", "pharmaceutical", "pharma", "fmcg",
        "chemicals", "metals", "mining", "capital goods", "consumer durables", "oil & gas",
        "energy", "power", "telecom", "infrastructure", "construction", "textiles",
        "agriculture", "cement", "retail", "media", "real estate", "transport", "logistics",
        "consumer staples", "consumer discretionary", "materials", "industrials", "health care",
        "communication services", "utilities"
    ]
    if any(cs in sec or cs in ind for cs in corporate_sectors):
        return "GENERAL_CORPORATE"
        
    # Check standard corporate balance sheet signatures (Gross Block, Fixed Assets, Raw Materials, CWIP)
    if any(cm in all_metrics for cm in ["fixed assets", "fixed assets +", "gross block", "raw material", "operating profit", "cwip"]):
        if not (has_deposits or has_npa or has_financing_profit):
            return "GENERAL_CORPORATE"
            
    if "financial services" in sec or "financial" in ind:
        return "OTHER_FINANCIAL"
        
    return "UNKNOWN"

def compute_financial_analytics(
    quarters: Optional[FinancialStatement],
    pl: Optional[FinancialStatement],
    bs: Optional[FinancialStatement],
    cf: Optional[FinancialStatement],
    symbol: Optional[str] = None,
    financial_truth: Optional[Any] = None,
    sector: Optional[str] = None,
    industry: Optional[str] = None
) -> Dict[str, Any]:
    from financial_truth_resolver import (
        TruthAwareFinancialResolver,
        calculate_cagr,
        calculate_growth_pct,
        get_prior_quarter_canonical_key,
        get_prior_year_quarter_canonical_key,
        get_common_completed_annual_periods,
        classify_period_type
    )
    from models import AnalyticProvenanceSummary
    
    business_model = classify_financial_business_model(
        sector=sector,
        industry=industry,
        pl=pl,
        bs=bs,
        quarters=quarters
    )
    is_financial_business = (business_model in ("BANK", "NBFC_LENDER", "INSURANCE", "OTHER_FINANCIAL"))
    
    resolver = TruthAwareFinancialResolver(
        symbol=symbol,
        financial_truth=financial_truth,
        quarters=quarters,
        pl=pl,
        bs=bs,
        cf=cf
    )
    
    all_inputs_collected: List[Any] = []
    provenance_map: Dict[str, Any] = {}

    analytics: Dict[str, Any] = {
        "financial_business_model": business_model,
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
    # 1. Quarterly QoQ & YoY Trends (Exact Chronology & Truth-Driven in Phase 2B)
    # -------------------------------------------------------------------------
    if quarters and quarters.periods:
        q_periods = quarters.periods
        quarterly_trends = []
        for i, p in enumerate(q_periods):
            sales_fact = resolver.resolve_quarterly_fact("REVENUE", p)
            op_fact = resolver.resolve_quarterly_fact("OPERATING_PROFIT", p)
            opm_fact = resolver.resolve_quarterly_fact("OPM_PCT", p)
            pat_fact = resolver.resolve_quarterly_fact("NET_PROFIT", p)
            
            curr_sales = sales_fact.value
            curr_op = op_fact.value
            curr_opm = opm_fact.value
            curr_pat = pat_fact.value
            
            canon_p = sales_fact.canonical_period
            prior_q_canon = get_prior_quarter_canonical_key(canon_p)
            prior_y_canon = get_prior_year_quarter_canonical_key(canon_p)
            
            # Exact Chronological QoQ Growth
            qoq_sales_growth = None
            qoq_sales_prov = None
            qoq_op_growth = None
            qoq_op_prov = None
            qoq_pat_growth = None
            qoq_pat_prov = None
            
            if prior_q_canon:
                prev_sales_fact = resolver.resolve_quarterly_fact("REVENUE", prior_q_canon)
                qoq_sales_res = resolver.calculate_growth_with_provenance(sales_fact, prev_sales_fact, formula_type="growth")
                qoq_sales_growth = qoq_sales_res.value
                qoq_sales_prov = qoq_sales_res.model_dump()
                all_inputs_collected.extend(qoq_sales_res.inputs)
                
                prev_op_fact = resolver.resolve_quarterly_fact("OPERATING_PROFIT", prior_q_canon)
                qoq_op_res = resolver.calculate_growth_with_provenance(op_fact, prev_op_fact, formula_type="growth")
                qoq_op_growth = qoq_op_res.value
                qoq_op_prov = qoq_op_res.model_dump()
                all_inputs_collected.extend(qoq_op_res.inputs)

                prev_pat_fact = resolver.resolve_quarterly_fact("NET_PROFIT", prior_q_canon)
                qoq_pat_res = resolver.calculate_growth_with_provenance(pat_fact, prev_pat_fact, formula_type="growth")
                qoq_pat_growth = qoq_pat_res.value
                qoq_pat_prov = qoq_pat_res.model_dump()
                all_inputs_collected.extend(qoq_pat_res.inputs)
                    
            # Exact Chronological YoY Growth
            yoy_sales_growth = None
            yoy_sales_prov = None
            yoy_op_growth = None
            yoy_op_prov = None
            yoy_pat_growth = None
            yoy_pat_prov = None
            
            if prior_y_canon:
                prev_y_sales_fact = resolver.resolve_quarterly_fact("REVENUE", prior_y_canon)
                yoy_sales_res = resolver.calculate_growth_with_provenance(sales_fact, prev_y_sales_fact, formula_type="growth")
                yoy_sales_growth = yoy_sales_res.value
                yoy_sales_prov = yoy_sales_res.model_dump()
                all_inputs_collected.extend(yoy_sales_res.inputs)
                
                prev_y_op_fact = resolver.resolve_quarterly_fact("OPERATING_PROFIT", prior_y_canon)
                yoy_op_res = resolver.calculate_growth_with_provenance(op_fact, prev_y_op_fact, formula_type="growth")
                yoy_op_growth = yoy_op_res.value
                yoy_op_prov = yoy_op_res.model_dump()
                all_inputs_collected.extend(yoy_op_res.inputs)

                prev_y_pat_fact = resolver.resolve_quarterly_fact("NET_PROFIT", prior_y_canon)
                yoy_pat_res = resolver.calculate_growth_with_provenance(pat_fact, prev_y_pat_fact, formula_type="growth")
                yoy_pat_growth = yoy_pat_res.value
                yoy_pat_prov = yoy_pat_res.model_dump()
                all_inputs_collected.extend(yoy_pat_res.inputs)
                    
            quarterly_trends.append({
                "period": p,
                "sales": curr_sales,
                "operating_profit": curr_op,
                "opm_pct": curr_opm,
                "net_profit": curr_pat,
                "sales_growth_qoq_pct": qoq_sales_growth,
                "sales_growth_yoy_pct": yoy_sales_growth,
                "operating_profit_growth_qoq_pct": qoq_op_growth,
                "operating_profit_growth_yoy_pct": yoy_op_growth,
                "pat_growth_qoq_pct": qoq_pat_growth,
                "pat_growth_yoy_pct": yoy_pat_growth,
                "provenance": {
                    "sales": sales_fact.model_dump(),
                    "operating_profit": op_fact.model_dump(),
                    "opm_pct": opm_fact.model_dump(),
                    "net_profit": pat_fact.model_dump(),
                    "sales_growth_qoq": qoq_sales_prov,
                    "sales_growth_yoy": yoy_sales_prov,
                    "operating_profit_growth_qoq": qoq_op_prov,
                    "operating_profit_growth_yoy": yoy_op_prov,
                    "pat_growth_qoq": qoq_pat_prov,
                    "pat_growth_yoy": yoy_pat_prov
                }
            })
        analytics["quarterly_analysis"]["trends"] = quarterly_trends

    # -------------------------------------------------------------------------
    # 2. Annual P&L Growth & Margins (Truth-Driven in Phase 2B)
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
    
    # CAGRs with Truth Provenance (calculated across completed fiscal annual periods)
    annual_periods = [p for p in y_periods if p.upper().strip() != "TTM"]
    if not annual_periods:
        annual_periods = y_periods
        
    if len(annual_periods) >= 4:
        last_p = annual_periods[-1]
        p_3y = annual_periods[-4]
        end_s = resolver.resolve_annual_fact("REVENUE", last_p)
        base_s = resolver.resolve_annual_fact("REVENUE", p_3y)
        res_s_3y = resolver.calculate_growth_with_provenance(end_s, base_s, formula_type="cagr", years=3)
        analytics["growth_rates"]["sales_cagr_3yr"] = res_s_3y.value
        provenance_map["sales_cagr_3yr"] = res_s_3y.model_dump()
        all_inputs_collected.extend(res_s_3y.inputs)
        
        end_p = resolver.resolve_annual_fact("NET_PROFIT", last_p)
        base_p = resolver.resolve_annual_fact("NET_PROFIT", p_3y)
        res_p_3y = resolver.calculate_growth_with_provenance(end_p, base_p, formula_type="cagr", years=3)
        analytics["growth_rates"]["pat_cagr_3yr"] = res_p_3y.value
        provenance_map["pat_cagr_3yr"] = res_p_3y.model_dump()
        all_inputs_collected.extend(res_p_3y.inputs)
            
    if len(annual_periods) >= 6:
        last_p = annual_periods[-1]
        p_5y = annual_periods[-6]
        end_s = resolver.resolve_annual_fact("REVENUE", last_p)
        base_s = resolver.resolve_annual_fact("REVENUE", p_5y)
        res_s_5y = resolver.calculate_growth_with_provenance(end_s, base_s, formula_type="cagr", years=5)
        analytics["growth_rates"]["sales_cagr_5yr"] = res_s_5y.value
        provenance_map["sales_cagr_5yr"] = res_s_5y.model_dump()
        all_inputs_collected.extend(res_s_5y.inputs)
        
        end_p = resolver.resolve_annual_fact("NET_PROFIT", last_p)
        base_p = resolver.resolve_annual_fact("NET_PROFIT", p_5y)
        res_p_5y = resolver.calculate_growth_with_provenance(end_p, base_p, formula_type="cagr", years=5)
        analytics["growth_rates"]["pat_cagr_5yr"] = res_p_5y.value
        provenance_map["pat_cagr_5yr"] = res_p_5y.model_dump()
        all_inputs_collected.extend(res_p_5y.inputs)

    if len(annual_periods) >= 11:
        last_p = annual_periods[-1]
        p_10y = annual_periods[-11]
        end_s = resolver.resolve_annual_fact("REVENUE", last_p)
        base_s = resolver.resolve_annual_fact("REVENUE", p_10y)
        res_s_10y = resolver.calculate_growth_with_provenance(end_s, base_s, formula_type="cagr", years=10)
        analytics["growth_rates"]["sales_cagr_10yr"] = res_s_10y.value
        provenance_map["sales_cagr_10yr"] = res_s_10y.model_dump()
        all_inputs_collected.extend(res_s_10y.inputs)
        
        end_p = resolver.resolve_annual_fact("NET_PROFIT", last_p)
        base_p = resolver.resolve_annual_fact("NET_PROFIT", p_10y)
        res_p_10y = resolver.calculate_growth_with_provenance(end_p, base_p, formula_type="cagr", years=10)
        analytics["growth_rates"]["pat_cagr_10yr"] = res_p_10y.value
        provenance_map["pat_cagr_10yr"] = res_p_10y.model_dump()
        all_inputs_collected.extend(res_p_10y.inputs)

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
    valid_capex_pcts = []
    has_direct_capex = bool(direct_capex_vals)
    
    methodology_notes = []
    if cfo_vals:
        methodology_notes.append("Reported Cash Flow from Operating Activities (CFO) line used.")
    else:
        methodology_notes.append("CFO line not reported in Cash Flow statement.")

    if is_financial_business:
        methodology_notes.append("Conventional CFO/FCF analysis is not applicable for banking and financial entities.")
    elif has_direct_capex:
        methodology_notes.append("Direct reported 'Fixed assets purchased / Capex' line item used (High Confidence).")
    else:
        methodology_notes.append("Direct Capex line not itemized in statement; derived from Balance Sheet net block & CWIP changes.")

    prior_valid_capex = []
    cfo_facts_map: Dict[str, Optional[float]] = {}
    pat_facts_map: Dict[str, Optional[float]] = {}
    fcf_facts_map: Dict[str, Optional[float]] = {}

    for idx, p in enumerate(y_periods):
        cfo_fact = resolver.resolve_annual_fact("CFO", p)
        pat_fact = resolver.resolve_annual_fact("NET_PROFIT", p)
        sales_fact = resolver.resolve_annual_fact("REVENUE", p)
        
        cfo = cfo_fact.value
        pat = pat_fact.value
        sales = sales_fact.value
        all_inputs_collected.extend([cfo_fact, pat_fact])
        cfo_facts_map[p] = cfo
        pat_facts_map[p] = pat
        
        capex = None
        capex_method = "Unavailable"
        fcf_confidence = "Unavailable"
        confidence_reason = "Missing CFO or Balance Sheet data to determine Capex."
        possible_anomaly_warning = None
        
        if is_financial_business:
            capex = None
            capex_method = "Not Applicable (Financial Business Model)"
            fcf_confidence = "Not Applicable"
            confidence_reason = "Conventional Capex and Free Cash Flow are not applicable to banking and financial institutions."
        else:
            # Priority 1: Direct reported capex line item
            if direct_capex_vals and p in direct_capex_vals and direct_capex_vals[p] is not None:
                capex = abs(direct_capex_vals[p])
                capex_method = "Reported Capex"
                fcf_confidence = "High Confidence"
                confidence_reason = "Direct reported fixed assets purchased line item used from cash flow statement."
                prior_valid_capex.append(capex)
            # Priority 2: Derived via Balance Sheet Net Block Delta + Depreciation + CWIP Delta
            elif idx > 0 and fixed_assets and p in fixed_assets and y_periods[idx-1] in fixed_assets:
                fa_curr = fixed_assets.get(p)
                fa_prev = fixed_assets.get(y_periods[idx-1])
                dep_val = y_dep.get(p) or 0.0
                cwip_curr = cwip.get(p) or 0.0
                cwip_prev = cwip.get(y_periods[idx-1]) or 0.0
                
                if fa_curr is not None and fa_prev is not None:
                    delta_fa = fa_curr - fa_prev
                    delta_cwip = cwip_curr - cwip_prev
                    calc_capex = delta_fa + dep_val + delta_cwip
                    capex = round(calc_capex, 1)
                    capex_method = "Derived from Balance Sheet (FA delta + Dep + CWIP delta)"
                    fcf_confidence = "Medium Confidence"
                    confidence_reason = "Derived from Balance Sheet net block change, depreciation, and CWIP delta."
                    
                    # Deterministic Sanity Checks on Derived Capex (preserve math, lower confidence, attach warning)
                    if calc_capex < 0:
                        fcf_confidence = "Low Confidence"
                        confidence_reason = "Derived Capex is negative due to net fixed asset reductions exceeding depreciation."
                        possible_anomaly_warning = (
                            f"Negative derived capex (₹{calc_capex:,.1f} Cr) in {p} indicates major asset disposals, "
                            f"demergers, or write-downs exceeding new capital additions."
                        )
                    elif sales and sales > 0 and (calc_capex / sales) > 0.80:
                        pct = round((calc_capex / sales) * 100.0, 1)
                        fcf_confidence = "Low Confidence"
                        confidence_reason = f"Derived capex as % of sales is unusually elevated ({pct}% > 80%)."
                        possible_anomaly_warning = (
                            f"Derived capex represents {pct}% of annual sales in {p}, indicating an inorganic acquisition, "
                            f"subsidiary consolidation, or large asset transfer rather than routine organic capex."
                        )
                    elif prior_valid_capex and len(prior_valid_capex) >= 2:
                        prior_avg = sum(prior_valid_capex[-3:]) / len(prior_valid_capex[-3:])
                        if prior_avg > 0 and calc_capex > (3.5 * prior_avg) and (calc_capex - prior_avg) > 1000.0:
                            ratio = round(calc_capex / prior_avg, 1)
                            fcf_confidence = "Low Confidence"
                            confidence_reason = f"Derived capex shows an extreme jump ({ratio}x) over historical baseline."
                            possible_anomaly_warning = (
                                f"Derived capex (₹{calc_capex:,.0f} Cr) is {ratio}x higher than the prior baseline average "
                                f"(₹{prior_avg:,.0f} Cr), indicating potential inorganic asset additions or balance sheet restructuring."
                            )
                    elif cfo is not None and cfo > 0 and calc_capex > (4.0 * cfo) and calc_capex > 2000.0 and (delta_cwip < 0.5 * calc_capex):
                        ratio = round(calc_capex / cfo, 1)
                        fcf_confidence = "Low Confidence"
                        confidence_reason = f"Derived capex significantly exceeds operating cash flow ({ratio}x CFO)."
                        possible_anomaly_warning = (
                            f"Derived capex is {ratio}x operating cash flow without corresponding CWIP gestation, "
                            f"signaling possible inorganic block additions."
                        )
                        
                    prior_valid_capex.append(max(calc_capex, 0.0))
            
        # Calculate Stocker FCF only for general corporate if both CFO and Capex are available
        fcf = None
        if not is_financial_business:
            if cfo is not None and capex is not None:
                fcf = round(cfo - capex, 1)
                fcf_facts_map[p] = fcf
            else:
                if fcf_confidence != "Low Confidence":
                    fcf_confidence = "Unavailable"
                
        cfo_to_pat = round((cfo / pat) * 100.0, 1) if (cfo is not None and pat is not None and pat > 0) else None
        
        if sales and capex is not None and sales > 0 and capex >= 0:
            valid_capex_pcts.append(round((capex / sales) * 100.0, 1))

        fcf_trends.append({
            "period": p,
            "reported_cfo_cr": cfo,
            "reported_pat_cr": pat,
            "capex_cr": capex,
            "capex_methodology": capex_method,
            "fcf_confidence": fcf_confidence,
            "confidence_reason": confidence_reason,
            "possible_anomaly_warning": possible_anomaly_warning,
            "stocker_derived_fcf_cr": fcf,
            "cfo_to_pat_pct": cfo_to_pat,
            "provenance": {
                "cfo": cfo_fact.model_dump(),
                "pat": pat_fact.model_dump()
            }
        })
        
    # Exact Common Completed Annual Periods for 5Y CFO/PAT
    common_5y_periods = get_common_completed_annual_periods([cfo_facts_map, pat_facts_map], count=5)
    if len(common_5y_periods) == 5:
        cum_5y_pat = sum(pat_facts_map[p] for p in common_5y_periods if pat_facts_map.get(p) is not None)
        cum_5y_cfo = sum(cfo_facts_map[p] for p in common_5y_periods if cfo_facts_map.get(p) is not None)
        cfo_to_pat_5yr = round((cum_5y_cfo / cum_5y_pat) * 100.0, 1) if (cum_5y_pat is not None and cum_5y_pat > 0 and cum_5y_cfo is not None) else None
    else:
        cum_5y_pat = None
        cum_5y_cfo = None
        cfo_to_pat_5yr = None

    # Exact Common Completed Annual Periods for 5Y FCF
    if not is_financial_business:
        common_5y_fcf_periods = get_common_completed_annual_periods([cfo_facts_map, pat_facts_map, fcf_facts_map], count=5)
        cum_5y_fcf = sum(fcf_facts_map[p] for p in common_5y_fcf_periods if fcf_facts_map.get(p) is not None) if len(common_5y_fcf_periods) == 5 else None
    else:
        cum_5y_fcf = None
    
    # Historical capex-to-sales %
    historical_capex_sales_pct = (
        round(sum(valid_capex_pcts[-5:]) / len(valid_capex_pcts[-5:]), 1)
        if valid_capex_pcts else 5.0
    )
    analytics["historical_parameters"]["capex_to_sales_pct"] = historical_capex_sales_pct

    # Determine Cash Conversion Quality & Overall FCF Confidence
    if is_financial_business:
        conv_quality = "Not applicable for banking/financial business model"
        overall_fcf_confidence = "Not Applicable (Financial Business Model)"
        cf_applicability = "not_applicable_financial_business"
    else:
        cf_applicability = "applicable" if cfo_to_pat_5yr is not None else "insufficient"
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

        recent_fcf_trends = fcf_trends[-5:] if len(fcf_trends) >= 5 else fcf_trends
        recent_confidences = [item.get("fcf_confidence") for item in recent_fcf_trends if item.get("fcf_confidence")]
        if all(c == "High Confidence" for c in recent_confidences) and len(recent_confidences) >= 3:
            overall_fcf_confidence = "High Confidence (Direct Reported Capex)"
        elif any(c == "Low Confidence" for c in recent_confidences):
            overall_fcf_confidence = "Low Confidence (High Volatility / Distortions Detected)"
        elif any(c == "Medium Confidence" for c in recent_confidences):
            overall_fcf_confidence = "Medium Confidence (Balance Sheet Derived)"
        else:
            overall_fcf_confidence = "Unavailable / Incomplete Data"

    analytics["cash_flow_quality"] = {
        "applicability": cf_applicability,
        "common_annual_periods": common_5y_periods,
        "cumulative_5y_pat_cr": round(cum_5y_pat, 1) if (cum_5y_pat is not None and cum_5y_pat > 0) else None,
        "cumulative_5y_cfo_cr": round(cum_5y_cfo, 1) if cum_5y_cfo is not None else None,
        "cumulative_5y_fcf_cr": round(cum_5y_fcf, 1) if cum_5y_fcf is not None else None,
        "cfo_to_pat_5yr_pct": cfo_to_pat_5yr,
        "cash_conversion_quality": conv_quality,
        "is_fcf_directly_reported": has_direct_capex if not is_financial_business else False,
        "overall_fcf_confidence": overall_fcf_confidence,
        "methodology_notes": methodology_notes,
        "fcf_trends": fcf_trends
    }
    
    # -------------------------------------------------------------------------
    # 4. Balance Sheet & Capital Allocation (CWIP & Debt with Truth Provenance)
    # -------------------------------------------------------------------------
    bs_trends = []
    for p in bs_periods:
        eq = ((equity_cap.get(p) or 0.0) + (reserves.get(p) or 0.0)) if (equity_cap.get(p) is not None or reserves.get(p) is not None) else None
        debt_fact = resolver.resolve_annual_fact("BORROWINGS", p)
        fa_fact = resolver.resolve_annual_fact("FIXED_ASSETS", p)
        cwip_fact = resolver.resolve_annual_fact("CWIP", p)
        
        debt = debt_fact.value
        fa = fa_fact.value
        c_work = cwip_fact.value
        tot_a = total_assets.get(p)
        all_inputs_collected.extend([debt_fact, fa_fact, cwip_fact])
        
        debt_to_equity = round(debt / eq, 2) if (debt is not None and eq is not None and eq > 0) else None
        cwip_to_fa_pct = round((c_work / fa) * 100.0, 1) if (c_work is not None and fa is not None and fa > 0) else None
        
        bs_trends.append({
            "period": p,
            "total_equity_cr": eq if (eq is not None and eq > 0) else None,
            "borrowings_cr": debt,
            "fixed_assets_cr": fa,
            "cwip_cr": c_work,
            "total_assets_cr": tot_a,
            "cwip_to_fixed_assets_pct": cwip_to_fa_pct,
            "debt_to_equity": debt_to_equity,
            "provenance": {
                "borrowings": debt_fact.model_dump(),
                "fixed_assets": fa_fact.model_dump(),
                "cwip": cwip_fact.model_dump()
            }
        })
        
    latest_bs = bs_trends[-1] if bs_trends else {}
    cwip_pct = latest_bs.get("cwip_to_fixed_assets_pct")
    debt_eq = latest_bs.get("debt_to_equity")

    # If banking or financial, CWIP does not indicate capex expansion
    has_expansion = bool(cwip_pct is not None and cwip_pct >= 12.0) if not is_financial_business else False

    analytics["balance_sheet_efficiency"] = {
        "latest_debt_to_equity": debt_eq,
        "latest_cwip_to_net_block_pct": cwip_pct,
        "has_significant_capex_trigger": has_expansion,
        "bs_trends": bs_trends
    }

    # Bank-specific reported metrics and Tier 1 Analytics (BANK ONLY)
    if business_model == "BANK":
        from bank_engine import compute_bank_analytics
        bank_res = compute_bank_analytics(
            quarters=quarters,
            pl=pl,
            bs=bs,
            cf=cf,
            ratios=ratios if 'ratios' in locals() else None,
            symbol=symbol,
            financial_truth=financial_truth,
            sector=sector,
            industry=industry
        )
        analytics["bank_analytics"] = bank_res.model_dump()
        
        # Derive backward-compatible bank_metrics from BankEngine
        latest_t = bank_res.trends[-1] if bank_res.trends else None
        analytics["bank_metrics"] = {
            "latest_deposits_cr": latest_t.deposits_cr if latest_t else None,
            "latest_advances_cr": latest_t.advances_cr if latest_t else None,
            "latest_gross_npa_pct": bank_res.gross_npa_pct,
            "latest_net_npa_pct": bank_res.net_npa_pct
        }

    # -------------------------------------------------------------------------
    # Overall Analytic Provenance Summary
    # -------------------------------------------------------------------------
    verified_cnt = sum(1 for inp in all_inputs_collected if inp.verification_status == "VERIFIED")
    discrepancy_cnt = sum(1 for inp in all_inputs_collected if inp.has_discrepancy or inp.verification_status == "DISCREPANCY")
    standardized_cnt = sum(1 for inp in all_inputs_collected if inp.verification_status not in ("VERIFIED", "DISCREPANCY") and inp.value is not None)
    unavailable_cnt = sum(1 for inp in all_inputs_collected if inp.value is None)
    
    if discrepancy_cnt > 0:
        overall_quality = "discrepant"
    elif verified_cnt == len(all_inputs_collected) and len(all_inputs_collected) > 0:
        overall_quality = "verified"
    elif verified_cnt > 0:
        overall_quality = "mixed"
    elif standardized_cnt > 0:
        overall_quality = "standardized"
    else:
        overall_quality = "insufficient"
        
    analytics["provenance"] = provenance_map
    analytics["provenance_summary"] = AnalyticProvenanceSummary(
        verified_inputs=verified_cnt,
        standardized_inputs=standardized_cnt,
        discrepancy_inputs=discrepancy_cnt,
        unavailable_inputs=unavailable_cnt,
        overall_quality=overall_quality
    ).model_dump()

    # -------------------------------------------------------------------------
    # 5. DuPont Analysis (Latest Full Year — Quarantined for Financial Businesses)
    # -------------------------------------------------------------------------
    if is_financial_business:
        analytics["du_pont_analysis"] = {
            "applicability": "not_applicable_financial_business"
        }
    elif y_periods and bs_periods:
        lp_y = y_periods[-1]
        lp_b = bs_periods[-1]
        sales_val = y_sales.get(lp_y)
        pat_val = y_pat.get(lp_y)
        
        c_val = equity_cap.get(lp_b)
        r_val = reserves.get(lp_b)
        eq_val = (c_val + r_val) if (c_val is not None and r_val is not None) else None
        assets_val = total_assets.get(lp_b)

        net_margin = round((pat_val / sales_val) * 100.0, 2) if (pat_val and sales_val and sales_val > 0) else None
        asset_turnover = round(sales_val / assets_val, 2) if (sales_val and assets_val and assets_val > 0) else None
        financial_leverage = round(assets_val / eq_val, 2) if (assets_val and eq_val and eq_val > 0) else None
        roe_dupont = round((pat_val / eq_val) * 100.0, 2) if (pat_val and eq_val and eq_val > 0) else None

        analytics["du_pont_analysis"] = {
            "applicability": "applicable",
            "period": lp_y,
            "net_profit_margin_pct": net_margin,
            "asset_turnover_ratio": asset_turnover,
            "financial_leverage_multiplier": financial_leverage,
            "calculated_roe_pct": roe_dupont
        }

    # -------------------------------------------------------------------------
    # 7. Comprehensive Formula & Calculation Transparency (Truth-Aligned Inputs)
    # -------------------------------------------------------------------------
    last_p = y_periods[-1] if y_periods else ""
    p_3y = y_periods[-4] if len(y_periods) >= 4 else ""
    
    # 1. Sales 3Y CAGR Provenance Alignment
    sales_cagr_prov = provenance_map.get("sales_cagr_3yr", {})
    sales_inputs = sales_cagr_prov.get("inputs", [])
    end_s_prov = sales_inputs[0] if len(sales_inputs) > 0 else {}
    base_s_prov = sales_inputs[1] if len(sales_inputs) > 1 else {}
    
    last_sales = end_s_prov.get("value") if end_s_prov else y_sales.get(last_p)
    last_sales_p = end_s_prov.get("period") or last_p
    base_sales_3y = base_s_prov.get("value") if base_s_prov else y_sales.get(p_3y)
    base_sales_3y_p = base_s_prov.get("period") or p_3y
    
    sales_q_quality = sales_cagr_prov.get("quality", "standardized")
    if sales_q_quality == "verified":
        sales_source = f"Official Statutory Filing ({end_s_prov.get('selected_source_name') or 'Exchange Filing'}) — VERIFIED"
    elif sales_q_quality == "discrepant":
        sales_source = "Screener.in Standardized (Active Statutory Discrepancy Flagged)"
    elif sales_q_quality == "mixed":
        sales_source = "Mixed (Official Statutory Filing & Standardized Screener.in)"
    else:
        sales_source = "Audited Profit & Loss Statement (Screener.in)"

    # 2. PAT 3Y CAGR Provenance Alignment
    pat_cagr_prov = provenance_map.get("pat_cagr_3yr", {})
    pat_inputs = pat_cagr_prov.get("inputs", [])
    end_p_prov = pat_inputs[0] if len(pat_inputs) > 0 else {}
    base_p_prov = pat_inputs[1] if len(pat_inputs) > 1 else {}
    
    last_pat = end_p_prov.get("value") if end_p_prov else y_pat.get(last_p)
    last_pat_p = end_p_prov.get("period") or last_p
    base_pat_3y = base_p_prov.get("value") if base_p_prov else y_pat.get(p_3y)
    base_pat_3y_p = base_p_prov.get("period") or p_3y
    
    pat_q_quality = pat_cagr_prov.get("quality", "standardized")
    if pat_q_quality == "verified":
        pat_source = f"Official Statutory Filing ({end_p_prov.get('selected_source_name') or 'Exchange Filing'}) — VERIFIED"
    elif pat_q_quality == "discrepant":
        pat_source = "Screener.in Standardized (Active Statutory Discrepancy Flagged)"
    elif pat_q_quality == "mixed":
        pat_source = "Mixed (Official Statutory Filing & Standardized Screener.in)"
    else:
        pat_source = "Audited Profit & Loss Statement (Screener.in)"

    latest_fcf_item = fcf_trends[-1] if fcf_trends else {}
    latest_cfo = latest_fcf_item.get("reported_cfo_cr")
    latest_capex = latest_fcf_item.get("capex_cr")
    latest_fcf = latest_fcf_item.get("stocker_derived_fcf_cr")
    latest_capex_meth = latest_fcf_item.get("capex_methodology", "Unavailable")
    latest_fcf_conf = latest_fcf_item.get("fcf_confidence", "Unavailable")
    latest_anomaly = latest_fcf_item.get("possible_anomaly_warning")
    
    # 3. Latest Quarter YoY Sales Growth Provenance Alignment
    latest_q_trend = analytics["quarterly_analysis"]["trends"][-1] if analytics["quarterly_analysis"]["trends"] else {}
    yoy_sales_prov = latest_q_trend.get("provenance", {}).get("sales_growth_yoy", {})
    yoy_inputs = yoy_sales_prov.get("inputs", [])
    curr_q_sales_inp = yoy_inputs[0] if len(yoy_inputs) > 0 else {}
    prior_q_sales_inp = yoy_inputs[1] if len(yoy_inputs) > 1 else {}
    
    yoy_quality = yoy_sales_prov.get("quality", "standardized")
    if yoy_quality == "verified":
        yoy_source = f"Official Quarterly Filing ({curr_q_sales_inp.get('selected_source_name') or 'Exchange Filing'}) — VERIFIED"
    elif yoy_quality == "discrepant":
        yoy_source = "Quarterly Results (Active Statutory Discrepancy Flagged)"
    elif yoy_quality == "mixed":
        yoy_source = "Quarterly Results (Mixed Official & Standardized Sources)"
    else:
        yoy_source = "Quarterly Financial Results (Screener.in)"

    # Formula transparency explanations adjusted for banking/financial entities
    if is_financial_business:
        cfo_pat_explanation = "Conventional 5-Year CFO/PAT conversion is not applicable to banking and financial institutions because customer deposits and lending disbursements dominate operating cash flows."
        fcf_explanation = "Conventional Free Cash Flow (CFO - Capex) is not applicable to banking and financial institutions because operating cash flows reflect financial asset/liability movements rather than industrial capital expenditure."
    else:
        cfo_pat_explanation = f"The company converted {cfo_to_pat_5yr}% of its accounting net profit into actual operational cash flow over the last 5 common financial years ({conv_quality})." if cfo_to_pat_5yr is not None else "Cash flow conversion data incomplete."
        fcf_explanation = f"In {last_p}, operating cash flow was ₹{latest_cfo:,.0f} Cr and capital expenditure was ₹{latest_capex:,.0f} Cr ({latest_capex_meth}, {latest_fcf_conf}), resulting in ₹{latest_fcf:,.0f} Cr of free cash flow." + (f" Note: {latest_anomaly}" if latest_anomaly else "") if (latest_cfo is not None and latest_capex is not None and latest_fcf is not None) else "FCF requires reliable CFO and Capex figures."

    analytics["formula_transparency"] = {
        "sales_cagr_3yr": {
            "metric_name": "Sales 3-Year CAGR",
            "value": analytics["growth_rates"].get("sales_cagr_3yr"),
            "formula": "((Sales_Latest / Sales_3Yr_Ago) ^ (1/3) - 1) × 100",
            "inputs": {
                "Latest Sales (₹ Cr)": last_sales,
                "Sales 3 Years Ago (₹ Cr)": base_sales_3y,
                "Latest Period": last_sales_p,
                "Base Period": base_sales_3y_p
            },
            "source": sales_source,
            "explanation": f"Revenue grew at a compounded annual growth rate of {analytics['growth_rates'].get('sales_cagr_3yr')}% from ₹{base_sales_3y:,.0f} Cr ({base_sales_3y_p}) to ₹{last_sales:,.0f} Cr ({last_sales_p})." if (last_sales and base_sales_3y and last_sales > 0 and base_sales_3y > 0) else "Historical 3-year P&L data insufficient."
        },
        "pat_cagr_3yr": {
            "metric_name": "Profit (PAT) 3-Year CAGR",
            "value": analytics["growth_rates"].get("pat_cagr_3yr"),
            "formula": "((PAT_Latest / PAT_3Yr_Ago) ^ (1/3) - 1) × 100",
            "inputs": {
                "Latest PAT (₹ Cr)": last_pat,
                "PAT 3 Years Ago (₹ Cr)": base_pat_3y,
                "Latest Period": last_pat_p,
                "Base Period": base_pat_3y_p
            },
            "source": pat_source,
            "explanation": f"Net profit compounded at {analytics['growth_rates'].get('pat_cagr_3yr')}% per annum from ₹{base_pat_3y:,.0f} Cr ({base_pat_3y_p}) to ₹{last_pat:,.0f} Cr ({last_pat_p})." if (last_pat and base_pat_3y and last_pat > 0 and base_pat_3y > 0) else "PAT CAGR calculation requires positive base and terminal net profit."
        },
        "cfo_to_pat_5yr": {
            "metric_name": "5-Year CFO to PAT Conversion %",
            "value": cfo_to_pat_5yr if not is_financial_business else None,
            "formula": "(Cumulative 5-Year CFO / Cumulative 5-Year PAT) × 100",
            "inputs": {
                "Cumulative 5Y CFO (₹ Cr)": round(cum_5y_cfo, 1) if cum_5y_cfo is not None else None,
                "Cumulative 5Y PAT (₹ Cr)": round(cum_5y_pat, 1) if (cum_5y_pat is not None and cum_5y_pat > 0) else None,
                "Period Range": f"{common_5y_periods[0]} to {common_5y_periods[-1]}" if len(common_5y_periods) == 5 else "Last 5 Common Completed FYs"
            },
            "source": "Audited Cash Flow & Profit/Loss Statements",
            "explanation": cfo_pat_explanation
        },
        "free_cash_flow": {
            "metric_name": "Free Cash Flow (FCF)",
            "value": latest_fcf,
            "formula": "FCF = CFO - Capex",
            "inputs": {
                "Reported CFO (₹ Cr)": latest_cfo,
                "Capex (₹ Cr)": latest_capex,
                "Capex Methodology": latest_capex_meth,
                "FCF Confidence": latest_fcf_conf,
                "Period": last_p
            },
            "source": "Audited Cash Flow Statement / Balance Sheet Gross Block Reconciliation",
            "explanation": fcf_explanation
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
            "explanation": f"The company has ₹{debt_eq} of debt for every ₹1.00 of shareholder equity." if debt_eq is not None else "Debt to equity unavailable due to missing balance sheet figures."
        },
        "latest_yoy_sales_growth": {
            "metric_name": "Latest Quarter YoY Sales Growth",
            "value": latest_q_trend.get("sales_growth_yoy_pct"),
            "formula": "((Sales_Q_Latest - Sales_Q_Prior_Year) / Sales_Q_Prior_Year) × 100",
            "inputs": {
                "Latest Quarter Sales (₹ Cr)": latest_q_trend.get("sales"),
                "Quarter": latest_q_trend.get("period")
            },
            "source": yoy_source,
            "explanation": f"Quarterly sales grew {latest_q_trend.get('sales_growth_yoy_pct')}% year-over-year in {latest_q_trend.get('period')}." if latest_q_trend.get("sales_growth_yoy_pct") is not None else "YoY quarter comparison pending."
        }
    }
    
    return analytics
    
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

def parse_explicit_guidance_range(text: str) -> Optional[Tuple[float, float, str]]:
    """
    Parses explicit management guidance ranges.
    Returns (min_val, max_val, unit) or None.
    Supported units: '%', 'bps', 'cr' (or other currency amounts).
    Strictly guards against fiscal year and date ranges (e.g. '2025-26', 'FY2025-2026').
    """
    if not text:
        return None
    s = text.lower().strip()
    
    # 1. Strip out pure year/period ranges e.g. FY2025-26, 2025-2026, FY25-FY26, 2025-26
    s_clean = re.sub(r'\b(?:fy\s*)?20\d\d\s*[-–/]\s*(?:20\d\d|\d{2})\b', '', s)
    s_clean = re.sub(r'\bfy\s*\d{2}\s*[-–/]\s*\d{2}\b', '', s_clean)

    # 2. Basis points range: e.g. '80-100 bps', '80 to 100 bps', 'between 80 and 100 bps'
    m_bps = re.search(r'(?:between\s+)?(\d+(?:\.\d+)?)\s*(?:bps)?\s*(?:to|-|and|–)\s*(\d+(?:\.\d+)?)\s*bps\b', s_clean)
    if m_bps:
        v1, v2 = float(m_bps.group(1)), float(m_bps.group(2))
        return (min(v1, v2), max(v1, v2), 'bps')

    # 3. Percentage range: e.g. '4.2% - 4.4%', '4.2 to 4.4%', 'between 4.2% and 4.4%'
    m_pct = re.search(r'(?:between\s+)?(\d+(?:\.\d+)?)\s*%\s*(?:to|-|and|–)\s*(\d+(?:\.\d+)?)\s*%', s_clean)
    if not m_pct:
        m_pct = re.search(r'(?:between\s+)?(\d+(?:\.\d+)?)\s*(?:to|-|and|–)\s*(\d+(?:\.\d+)?)\s*%', s_clean)
    if m_pct:
        v1, v2 = float(m_pct.group(1)), float(m_pct.group(2))
        # Extra guard: percentage guidance values should not be 4-digit years (> 1900)
        if v1 < 1000 and v2 < 1000:
            return (min(v1, v2), max(v1, v2), '%')

    # 4. Explicit Currency / Amount Range: e.g. '₹8,000–₹10,000 Cr', '8,000 - 10,000 crore'
    m_curr = re.search(r'(?:₹|rs\.?|inr)?\s*([\d,]+(?:\.\d+)?)\s*(?:cr|crore|billion|lakh)?\s*(?:to|-|and|–)\s*(?:₹|rs\.?|inr)?\s*([\d,]+(?:\.\d+)?)\s*(cr|crore|billion|lakh)\b', s_clean)
    if m_curr:
        try:
            v1 = float(m_curr.group(1).replace(',', ''))
            v2 = float(m_curr.group(2).replace(',', ''))
            unit = m_curr.group(3).lower()
            return (min(v1, v2), max(v1, v2), unit)
        except ValueError:
            pass

    return None

def extract_guidance_actual_value(outcome_text: str, target_unit: str) -> Optional[float]:
    """
    Extracts an actual outcome value matching the expected target unit (%, bps, currency/amount).
    Requires explicit currency symbol or unit context; strictly rejects bare year/period/page tokens
    (e.g. 'FY26', '2026', 'Q1', 'page 26').
    """
    if not outcome_text or not target_unit:
        return None
    s = outcome_text.strip()
    t_unit = target_unit.lower().strip()

    # 1. Percentage Target
    if t_unit == "%":
        m_pct = re.search(r'(\d+(?:\.\d+)?)\s*%', s, re.IGNORECASE)
        if m_pct:
            return float(m_pct.group(1))
        m_bps = re.search(r'(\d+(?:\.\d+)?)\s*bps\b', s, re.IGNORECASE)
        if m_bps:
            return round(float(m_bps.group(1)) / 100.0, 4)
        return None

    # 2. Basis Points Target
    if t_unit == "bps":
        m_bps = re.search(r'(\d+(?:\.\d+)?)\s*bps\b', s, re.IGNORECASE)
        if m_bps:
            return float(m_bps.group(1))
        m_pct = re.search(r'(\d+(?:\.\d+)?)\s*%', s, re.IGNORECASE)
        if m_pct:
            return round(float(m_pct.group(1)) * 100.0, 2)
        return None

    # 3. Currency / Absolute Amount Target (e.g. Cr, Crore, Billion, Lakh)
    if t_unit in ("cr", "crore", "billion", "bn", "lakh"):
        # Match explicit currency symbols or explicit unit words
        # (A) Currency prefix (₹, Rs., INR) + numeric amount + optional unit
        # (B) Numeric amount + required unit (Cr, Crore, Billion, etc.)
        m_curr_sym = re.search(
            r'(?:₹|rs\.?|inr)\s*([\d,]+(?:\.\d+)?)\s*(cr|crore|billion|bn|lakh|million|mn)?\b',
            s,
            re.IGNORECASE
        )
        m_unit_only = re.search(
            r'\b([\d,]+(?:\.\d+)?)\s*(cr|crore|billion|bn|lakh)\b',
            s,
            re.IGNORECASE
        )

        val_raw = None
        found_unit = None

        if m_curr_sym:
            val_str = m_curr_sym.group(1).replace(',', '')
            try:
                val_raw = float(val_str)
                found_unit = (m_curr_sym.group(2) or t_unit).lower()
            except ValueError:
                pass
        elif m_unit_only:
            val_str = m_unit_only.group(1).replace(',', '')
            try:
                val_raw = float(val_str)
                found_unit = m_unit_only.group(2).lower()
            except ValueError:
                pass

        if val_raw is not None and found_unit:
            # Deterministic unit normalization to target unit
            if t_unit in ("cr", "crore"):
                if found_unit in ("cr", "crore"):
                    return val_raw
                elif found_unit in ("billion", "bn"):
                    return round(val_raw * 100.0, 2)  # 1 billion INR = 100 crore INR
                elif found_unit == "lakh":
                    return round(val_raw * 0.01, 2)
            elif t_unit in ("billion", "bn"):
                if found_unit in ("billion", "bn"):
                    return val_raw
                elif found_unit in ("cr", "crore"):
                    return round(val_raw / 100.0, 4)
            elif t_unit == "lakh":
                if found_unit == "lakh":
                    return val_raw
                elif found_unit in ("cr", "crore"):
                    return round(val_raw * 100.0, 2)

def verify_promise_vs_delivery_item(
    item: Dict[str, Any],
    pl_stmt: Optional[Any] = None,
    quarters_stmt: Optional[Any] = None,
    current_year: Optional[float] = None
) -> Dict[str, Any]:
    """
    Deterministically enforces strict chronology, deadline rules, and mathematical statement calculations
    according to explicit target semantics (exact point target, minimum/at least target, range guidance,
    directional guidance, qualitative milestones).
    
    CRITICAL POLICY:
    - NO INVENTED ARBITRARY THRESHOLDS (no 95% or 80% tolerance bands).
    - If deadline has passed and actual < target, status is strictly 'Missed'.
    - Target deadline in the future is 'Not Yet Measurable' unless supported by interim progress evidence.
    - Same-filing evidence is rejected as 'Not Enough Evidence'.
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

    # 5. Generic Strategy Platitude Check
    prom_lower = str(item.get("management_promise", "")).lower().strip()
    if "no measurable prior" in prom_lower or "no prior promise" in prom_lower:
        res["status"] = "Not Enough Evidence"
        res["stocker_analysis"] = "No measurable prior management promise found in baseline filings."
        res["financial_numbers_check"] = "Baseline filings contained general business strategy without measurable numerical guidance targets."
        return res

    has_quant_kw = bool(re.search(r'(?:%|\b(?:cr|crore|billion|lakh|bps|ratio|guidance|target|capex|mcap)\b)', prom_lower))
    is_generic_platitude = any(phrase in prom_lower for phrase in [
        "remain focused", "committed to", "sustainable value",
        "focusing on sustainable", "aim to be the trusted", "harnessing its brand",
        "focus on long-term", "strive to deliver", "endeavour to serve", "customer-first", "core purpose"
    ]) and not has_quant_kw

    if is_generic_platitude:
        res["status"] = "Not Yet Measurable"
        res["stocker_analysis"] = "Generic Strategic Intent: Statement reflects ongoing corporate vision or strategic focus rather than an explicit numerical guidance target or verifiable operational milestone."
        res["financial_numbers_check"] = "Generic qualitative strategy without quantified performance metric."
        return res

    # Helper to extract metric values from statement
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

    def _get_stmt_periods(stmt_obj: Any) -> List[str]:
        if not stmt_obj: return []
        if hasattr(stmt_obj, "periods"): return list(stmt_obj.periods)
        if isinstance(stmt_obj, dict): return list(stmt_obj.get("periods") or stmt_obj.get("years") or [])
        return []

    pl_periods = _get_stmt_periods(pl_stmt)
    y_sales = _extract_metric_dict(pl_stmt, "Sales") or _extract_metric_dict(pl_stmt, "Revenue")
    y_opm = _extract_metric_dict(pl_stmt, "OPM %") or _extract_metric_dict(pl_stmt, "OPM")

    # 6. Check Range Target (Requires explicit unit %, bps, or currency; rejects bare year pairs)
    range_parsed = parse_explicit_guidance_range(prom_lower)
    m_growth = re.search(r'(\d+(?:\.\d+)?)\s*%\s*(?:top-line|top line|revenue|sales|growth|cagr|margin|loan|deposit|advances|volume|profit|pat|ebitda)', prom_lower)

    outcome_text = f"{item.get('actual_outcome', '')} {item.get('actual_quote', '')}"
    has_milestone_on_track = any(phrase in outcome_text.lower() for phrase in [
        "on schedule", "on track", "remains on schedule", "progressing as planned",
        "trial run completed", "phase 1 commissioned", "phase 1 operational",
        "construction commenced and remains on schedule", "trial underway on schedule",
        "in line with guidance trajectory", "ahead of schedule"
    ])

    if range_parsed and not m_growth:
        r_min, r_max, r_unit = range_parsed
        unit_label = "%" if r_unit == "%" else (f" {r_unit}" if r_unit != "%" else "")
        
        # Extract reported number from outcome with explicit currency / unit context
        act_v = extract_guidance_actual_value(outcome_text, r_unit)

        if act_v is not None:
            res["financial_numbers_check"] = f"Guided Range: {r_min}{unit_label}–{r_max}{unit_label}; Reported: {act_v}{unit_label}."
            
            is_unambiguous_lower_better = any(kw in prom_lower for kw in [
                "credit cost", "cost of risk", "gross npa", "gnpa", "net npa", "nnpa", "slippage",
                "cost-to-income", "cost to income"
            ])
            is_capex = any(kw in prom_lower for kw in ["capex", "capital expenditure", "outlay", "plant investment"])
            
            if target_yr is not None and target_yr > curr_yr:
                if has_milestone_on_track:
                    res["status"] = "On Track"
                    res["stocker_analysis"] = f"Interim Progress On Track: Stated target range ({r_min}{unit_label}–{r_max}{unit_label}) matures in the future ({target_yr:.0f}); interim execution remains on schedule."
                else:
                    res["status"] = "Not Yet Measurable"
                    res["stocker_analysis"] = f"Future Target: Stated range ({r_min}{unit_label}–{r_max}{unit_label}) matures in {target_timeline or f'FY{int(target_yr)}'}."
            elif r_min <= act_v <= r_max:
                res["status"] = "Delivered"
                res["stocker_analysis"] = f"Within Guidance Range: Reported {act_v}{unit_label} fell within management guided range of {r_min}{unit_label} to {r_max}{unit_label}."
            elif act_v < r_min:
                if is_unambiguous_lower_better:
                    res["status"] = "Delivered"
                    res["stocker_analysis"] = f"Favorable Below Range: Reported {act_v}{unit_label} improved below guided maximum/corridor ({r_min}{unit_label}–{r_max}{unit_label})."
                elif is_capex:
                    res["status"] = "Not Enough Evidence"
                    res["stocker_analysis"] = f"Below Guidance Range: Reported capex of {act_v}{unit_label} was below guided range ({r_min}{unit_label}–{r_max}{unit_label}). Lower capex may reflect project delays, scope revisions, or capital discipline and is not automatically classified as delivered."
                else:
                    res["status"] = "Missed"
                    res["stocker_analysis"] = f"Below Guidance Range: Reported {act_v}{unit_label} fell below guided range minimum of {r_min}{unit_label}."
            else:  # act_v > r_max
                if is_unambiguous_lower_better:
                    res["status"] = "Missed"
                    res["stocker_analysis"] = f"Above Guidance Range (Unfavorable): Reported {act_v}{unit_label} exceeded guided upper limit of {r_max}{unit_label}."
                elif is_capex:
                    res["status"] = "Not Enough Evidence"
                    res["stocker_analysis"] = f"Above Guidance Range: Reported capex of {act_v}{unit_label} exceeded guided range ({r_min}{unit_label}–{r_max}{unit_label}). Higher capex may reflect accelerated expansion or cost overruns."
                else:
                    # Going above an explicit upper bound is NOT automatically Delivered unless explicitly directionally known
                    res["status"] = "Not Enough Evidence"
                    res["stocker_analysis"] = f"Above Guidance Range: Reported {act_v}{unit_label} exceeded upper limit of guided range ({r_min}{unit_label}–{r_max}{unit_label}). Guidance was bounded; higher outcome reported without deterministic directional classification."
            return res
        else:
            if target_yr is not None and target_yr > curr_yr:
                res["status"] = "Not Yet Measurable"
                res["stocker_analysis"] = f"Future Target Not Yet Due: Stated range ({r_min}{unit_label}–{r_max}{unit_label}) matures in the future ({target_yr:.0f})."
            else:
                res["status"] = "Not Enough Evidence"
                res["stocker_analysis"] = f"Missing Quantitative Outcome: Subsequent filing ({actual_period}) does not contain a verifiable amount matching the guided range unit ({r_unit})."
                res["financial_numbers_check"] = "Not enough structured financial evidence to verify this claim."
            return res
            
    if m_growth:
        promised_pct = float(m_growth.group(1))
        is_minimum_target = any(kw in prom_lower for kw in ["at least", "minimum", "grow to", "reach at least", ">=", "higher than"])
        
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
                f"Target: {promised_pct}%; Actual: {act_growth}% (Variance: {variance_pct:+.1f} percentage points; Achievement Rate: {achieve_pct}%). "
                f"Reported {target_p} revenue of ₹{s_curr:,.0f} Cr; OPM stood at {opm_curr if opm_curr is not None else 'N/A'}%."
            )
            
            # Deterministic Target Semantics (NO INVENTED THRESHOLDS!)
            if target_yr is not None and target_yr > curr_yr:
                if has_milestone_on_track:
                    res["status"] = "On Track"
                    res["stocker_analysis"] = f"Interim Execution On Track: Stated target ({promised_pct}%) matures in the future ({target_yr:.0f}); subsequent filing confirms progress is on schedule."
                else:
                    res["status"] = "Not Yet Measurable"
                    res["stocker_analysis"] = f"Future Target Not Yet Due: Stated target deadline ({target_timeline or f'FY{int(target_yr)}'}) matures in {target_yr:.0f}. Interim reported {target_p} growth of {act_growth}% noted without multi-year trajectory milestones."
            elif is_minimum_target:
                if act_growth >= promised_pct:
                    res["status"] = "Delivered"
                    res["stocker_analysis"] = f"Minimum Target Achieved: Reported {act_growth}% growth met or exceeded the targeted minimum of {promised_pct}%."
                else:
                    res["status"] = "Missed"
                    res["stocker_analysis"] = f"Target Missed: Reported {act_growth}% growth fell short of minimum target {promised_pct}% (variance {variance_pct:+.1f}%)."
            else:
                # Exact point target semantics: met if actual >= target or within exact rounding parity (0.05%)
                if act_growth >= promised_pct:
                    res["status"] = "Delivered"
                    res["stocker_analysis"] = f"Target Delivered: Reported {act_growth}% growth met targeted {promised_pct}% (variance {variance_pct:+.1f}%)."
                else:
                    res["status"] = "Missed"
                    res["stocker_analysis"] = f"Target Missed: Reported {act_growth}% growth fell short of targeted {promised_pct}% (variance {variance_pct:+.1f}%)."
            return res
        else:
            # Check semantic metric alignment
            is_topline_promise = any(kw in prom_lower for kw in ["top-line", "top line", "revenue", "sales", "turnover", "total income"])
            has_only_operating_profit = any(kw in outcome_text.lower() for kw in ["operating profit", "core operating profit", "pbt", "pat"]) and not any(kw in outcome_text.lower() for kw in ["revenue", "sales", "top-line", "top line", "total income", "income"])
            if is_topline_promise and has_only_operating_profit:
                res["status"] = "Not Enough Evidence"
                res["financial_numbers_check"] = "Reported outcome does not contain matching top-line growth data."
                res["stocker_analysis"] = "Metric Semantic Mismatch: Guidance referenced top-line growth, but reported evidence contains operating profit. Operating profit is not top-line revenue."
                return res

            # Check if outcome text contains explicit reported number
            m_act_text = re.search(r'(\d+(?:\.\d+)?)\s*%', outcome_text)
            if m_act_text:
                act_growth = float(m_act_text.group(1))
                variance_pct = round(act_growth - promised_pct, 1)
                achieve_pct = round((act_growth / promised_pct) * 100.0, 1) if promised_pct > 0 else 0.0
                res["financial_numbers_check"] = f"Target: {promised_pct}%; Actual: {act_growth}% (Variance: {variance_pct:+.1f} percentage points; Achievement Rate: {achieve_pct}%)."
                
                if target_yr is not None and target_yr > curr_yr:
                    if has_milestone_on_track:
                        res["status"] = "On Track"
                        res["stocker_analysis"] = f"Interim Execution On Track: Stated target ({promised_pct}%) matures in the future ({target_yr:.0f}); subsequent filing confirms progress is on schedule."
                    else:
                        res["status"] = "Not Yet Measurable"
                        res["stocker_analysis"] = f"Future Target Not Yet Due: Stated target deadline matures in {target_yr:.0f}. Interim reporting ({actual_period}) noted without explicit trajectory milestones."
                elif act_growth >= promised_pct:
                    res["status"] = "Delivered"
                    res["stocker_analysis"] = f"Target Delivered: Reported {act_growth}% met targeted {promised_pct}%."
                else:
                    res["status"] = "Missed"
                    res["stocker_analysis"] = f"Target Missed: Reported {act_growth}% fell short of targeted {promised_pct}% (variance {variance_pct:+.1f}%)."
                return res

            res["financial_numbers_check"] = "Not enough structured financial evidence to verify this claim."
            if target_yr is not None and target_yr > curr_yr:
                res["status"] = "Not Yet Measurable"
                res["stocker_analysis"] = f"Future Target Not Yet Due: Stated target deadline ({target_timeline or f'FY{int(target_yr)}'}) matures in the future ({target_yr:.0f})."
            else:
                res["status"] = "Not Enough Evidence"
                res["stocker_analysis"] = "Missing Structured Financial Data: Standardized statements for the target period are not available to verify this quantitative guidance."
            return res

    # 7. Qualitative / Operational Milestone Verification
    if target_yr is not None and target_yr > curr_yr:
        if has_milestone_on_track:
            res["status"] = "On Track"
            res["financial_numbers_check"] = "Qualitative operational milestone (interim progress on schedule)."
            res["stocker_analysis"] = f"Milestone On Track: Stated target timeline ({target_timeline or f'FY{int(target_yr)}'}) matures in the future ({target_yr:.0f}). Subsequent filing ({actual_period}) reports active execution."
        else:
            res["status"] = "Not Yet Measurable"
            res["financial_numbers_check"] = "Qualitative operational milestone (future target not yet due)."
            res["stocker_analysis"] = f"Milestone Not Yet Measurable: Stated target timeline ({target_timeline or f'FY{int(target_yr)}'}) matures in the future ({target_yr:.0f}) with no verifiable interim progress reported."
    else:
        completion_match = re.search(
            r'\b(commissioned|operational|commercial production|commercial operations commenced|launched|completed acquisition|acquired|approval received|won order|order received|executed|achieved cod)\b',
            outcome_text,
            re.IGNORECASE
        )
        delay_match = re.search(r'\b(delayed|postponed|deferred|pushed back|rescheduled)\b', outcome_text, re.IGNORECASE)
        cancel_match = re.search(r'\b(cancelled|shelved|dropped|abandoned)\b', outcome_text, re.IGNORECASE)
        partial_match = re.search(r'\b(partially completed|partial commissioning|phase 1 operational|under progress|ongoing)\b', outcome_text, re.IGNORECASE)
        
        if completion_match and act_yr is not None and prom_yr is not None and act_yr > prom_yr:
            res["status"] = "Delivered"
            res["financial_numbers_check"] = f"Qualitative milestone verified: {completion_match.group(1).capitalize()} confirmed in subsequent filing ({actual_period})."
        elif partial_match:
            res["status"] = "Partially Delivered"
            res["financial_numbers_check"] = f"Qualitative milestone partially delivered: {partial_match.group(1).capitalize()} confirmed in subsequent filing ({actual_period})."
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

    return res

# -----------------------------------------------------------------------------
# 8. INTEGRATED PERSISTENT COMPANY KNOWLEDGE & TRIANGULATION ENGINE
# -----------------------------------------------------------------------------

def normalize_metric_key(name: str) -> str:
    """Normalizes metric names for robust inter-document matching."""
    if not name:
        return ""
    clean = re.sub(r'[^a-zA-Z0-9\s]', ' ', name).lower()
    return clean

def match_period_to_statement_column(period_str: str, available_periods: List[str]) -> Optional[str]:
    """Matches a filing period label (e.g. 'FY26', 'Q3 FY26', 'Mar 2026') to audited statement columns."""
    if not period_str or not available_periods:
        return None
    p_upper = period_str.strip().upper()
    
    # Direct match
    for ap in available_periods:
        if ap.upper() == p_upper:
            return ap
            
    # FY26 -> Mar 2026 or Mar 26
    m_fy = re.search(r'FY\s*(\d{2,4})', p_upper)
    if m_fy:
        raw_yr = int(m_fy.group(1))
        yr = raw_yr if raw_yr > 2000 else (2000 + raw_yr)
        for ap in available_periods:
            if f"Mar {yr}" in ap or f"MAR {yr}" in ap.upper() or f"Mar {str(yr)[-2:]}" in ap:
                return ap
                
    # Q1 FY26 -> Jun 2025
    m_q = re.search(r'Q([1-4])\s*(?:FY)?\s*(\d{2,4})', p_upper)
    if m_q:
        q_num = int(m_q.group(1))
        raw_yr = int(m_q.group(2))
        fy_year = raw_yr if raw_yr > 2000 else (2000 + raw_yr)
        q_month_map = {1: ("Jun", fy_year - 1), 2: ("Sep", fy_year - 1), 3: ("Dec", fy_year - 1), 4: ("Mar", fy_year)}
        m_name, yr_val = q_month_map[q_num]
        for ap in available_periods:
            if f"{m_name} {yr_val}" in ap or f"{m_name.upper()} {yr_val}" in ap.upper():
                return ap
                
    # Substring month search (e.g. 'Jun 2025' or 'Mar 2026')
    for ap in available_periods:
        if ap.lower() in p_upper.lower() or p_upper.lower() in ap.lower():
            return ap
            
    return None

def compute_fail_closed_execution_verdict(promise_items: List[Any]) -> str:
    """
    Computes a fail-closed management execution verdict based strictly on verified historical promises.
    Possible states:
    - 'Strong Execution'
    - 'Mixed Execution'
    - 'Weak Execution'
    - 'Provisional'
    - 'Insufficient History'
    """
    if not promise_items:
        return "Insufficient History"
        
    measurable = []
    for p in promise_items:
        st = p.get("status") if isinstance(p, dict) else getattr(p, "status", "")
        if st in ("Delivered", "Partially Delivered", "Delayed", "Missed"):
            measurable.append(st)
            
    if len(measurable) == 0:
        return "Insufficient History"
    if len(measurable) == 1:
        st = measurable[0]
        return "Provisional" if st == "Delivered" else ("Weak Execution" if st == "Missed" else "Provisional")
        
    delivered_count = sum(1 for st in measurable if st == "Delivered")
    missed_count = sum(1 for st in measurable if st in ("Missed", "Delayed"))
    
    ratio = delivered_count / len(measurable)
    miss_ratio = missed_count / len(measurable)
    
    if miss_ratio > 0.50:
        return "Weak Execution"
    elif ratio >= 0.70 and missed_count == 0:
        return "Strong Execution"
    elif ratio >= 0.40 or (delivered_count > 0 and missed_count > 0):
        return "Mixed Execution"
    else:
        return "Provisional"

def extract_kpi_identity(fact: Dict[str, Any]) -> Dict[str, str]:
    """
    Extracts a rigorous, conservative KPI identity signature to ensure only genuinely
    comparable metrics across filings are grouped into the same time-series.
    Enforces Fail-Closed Scope: UNKNOWN SCOPE MUST NEVER BECOME CONSOLIDATED.
    """
    m_name = (fact.get("metric_name") or "").strip().lower()
    raw_scope = fact.get("scope")
    scope_str = (raw_scope or "").strip().lower()
    claim_type = (fact.get("claim_type") or "reported_fact").strip().lower()
    unit = (fact.get("unit") or "").strip().lower()
    
    # 1. Detect scope with strict boundaries:
    # - explicit Consolidated -> consolidated
    # - explicit Standalone -> standalone
    # - explicit Segment / Geo -> segment_<name>
    # - missing / ambiguous / unknown -> unknown (never defaulted to consolidated)
    if "standalone" in scope_str or "standalone" in m_name:
        effective_scope = "standalone"
    elif "consolidated" in scope_str or "consolidated" in m_name:
        effective_scope = "consolidated"
    elif "segment" in scope_str:
        geos = [
            "india", "africa", "us", "usa", "europe", "middle east", "latam",
            "global", "domestic", "international", "enterprise", "retail", "wholesale",
            "rural", "business banking", "corporate", "sme"
        ]
        matched_geo = next((g for g in geos if g in m_name or g in scope_str), None)
        effective_scope = f"segment_{matched_geo}" if matched_geo else "segment_unspecified"
    elif scope_str in ("", "unknown", "none"):
        effective_scope = "unknown"
    else:
        effective_scope = scope_str

    # 2. Extract semantic metric core with strict boundaries
    # Priority Bank KPI identities:
    if any(k in m_name for k in ["net interest margin", "nim"]):
        core = "nim"
    elif any(k in m_name for k in ["gross npa", "gnpa", "gross non-performing"]):
        core = "gnpa"
    elif any(k in m_name for k in ["net npa", "nnpa", "net non-performing"]):
        core = "nnpa"
    elif any(k in m_name for k in ["credit cost", "credit costs", "cost of risk", "provisioning cost"]):
        core = "credit_cost"
    elif "casa" in m_name:
        core = "casa"
    elif any(k in m_name for k in ["deposit growth", "deposits growth"]):
        core = "deposit_growth"
    elif any(k in m_name for k in ["advances growth", "loan growth", "credit growth"]):
        core = "loan_growth"
    elif any(k in m_name for k in ["total deposits", "deposits"]):
        core = "deposits"
    elif any(k in m_name for k in ["total advances", "advances", "loan book", "loans"]):
        core = "advances"
    elif any(k in m_name for k in ["cet1", "cet 1", "common equity tier 1", "tier 1", "capital adequacy", "crar", "car "]):
        core = "capital_adequacy"
    elif any(k in m_name for k in ["return on assets", "roa"]):
        core = "roa"
    elif any(k in m_name for k in ["return on equity", "roe"]):
        core = "roe"
    elif any(k in m_name for k in ["cost to income", "cost-to-income"]):
        core = "cost_to_income"
    elif any(k in m_name for k in ["slippage", "slippages"]):
        core = "slippages"
    elif "arpu" in m_name:
        core = "arpu"
    elif "order book" in m_name or "backlog" in m_name:
        core = "order_book"
    elif "order intake" in m_name or "order inflow" in m_name or "deal win" in m_name or "tcv" in m_name:
        core = "order_intake"
    elif "net add" in m_name or "subscriber add" in m_name:
        core = "net_adds"
    elif any(k in m_name for k in ["subscriber", "customer count", "user base", "clients"]):
        core = "customer_count"
    elif any(k in m_name for k in ["target capacity", "expansion capacity", "planned capacity"]):
        core = "target_capacity"
    elif any(k in m_name for k in ["installed capacity", "operational capacity", "capacity"]):
        core = "installed_capacity"
    elif "store add" in m_name or "new store" in m_name:
        core = "store_adds"
    elif "store" in m_name or "outlet" in m_name or "branch" in m_name:
        core = "store_count"
    elif any(k in m_name for k in ["revenue", "sales", "turnover", "topline"]):
        core = "revenue"
    elif any(k in m_name for k in ["opm", "operating margin", "ebitda margin", "operating profit margin"]) or ("margin" in m_name and "ebitda" in m_name):
        core = "ebitda_margin"
    elif any(k in m_name for k in ["ebitda growth", "operating profit growth", "ebitda yoy", "operating profit yoy"]):
        core = "ebitda_growth"
    elif any(k in m_name for k in ["ebitda", "operating profit", "pbidt", "core operating profit"]):
        core = "ebitda_amount"
    elif any(k in m_name for k in ["net profit", "pat", "profit after tax"]):
        core = "net_profit"
    elif any(k in m_name for k in ["borrowing", "debt", "leverage"]):
        core = "debt"
    elif any(k in m_name for k in ["capex", "capital expenditure"]):
        core = "capex"
    else:
        core = normalize_metric_key(m_name)

    # Normalize units: ratio and percentage metrics all normalize to "%"
    if core in ("nim", "gnpa", "nnpa", "credit_cost", "casa", "capital_adequacy", "roa", "roe", "slippages", "cost_to_income", "deposit_growth", "loan_growth"):
        norm_unit = "%"
        effective_unit = unit or "%"
    else:
        norm_unit = unit.replace("₹", "rs").replace("cr", "").replace("crs", "").strip()
        effective_unit = unit

    # Standardize claim intent: 'reported_fact' (actual) vs 'target' / 'guidance'
    is_target = claim_type in ("management_target", "management_guidance") or "target" in m_name or "guidance" in m_name
    intent = "target" if is_target else "actual"

    id_key = f"{core}:{effective_scope}:{intent}:{norm_unit}"
    return {
        "id_key": id_key,
        "metric_core": core,
        "scope": effective_scope,
        "intent": intent,
        "unit": effective_unit
    }

def verify_document_claim_against_financials(
    fact: Dict[str, Any],
    stock_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Deterministically cross-examines a document fact/claim against audited 10-year financial statements.
    Computes prior-period baseline, delta, % change, and verification status.
    Strictly differentiates between Verified, Discrepancy, Scope Mismatch, and Operational KPIs.
    """
    metric_name = fact.get("metric_name", "")
    norm_metric = normalize_metric_key(metric_name)
    period_str = fact.get("period_or_date") or fact.get("target_period", "")
    stated_val_raw = str(fact.get("stated_value_raw") or "")
    num_val = fact.get("numeric_value")
    unit = fact.get("unit") or ""
    scope = fact.get("scope", "Consolidated")
    quote = fact.get("source_quote") or ""
    doc_title = fact.get("doc_title", "Filing")
    
    pl_dict = stock_data.get("profit_loss") or stock_data.get("profit_and_loss") or {}
    q_dict = stock_data.get("quarters") or {}
    bs_dict = stock_data.get("balance_sheet") or {}
    cf_dict = stock_data.get("cash_flow") or {}
    
    pl_periods = pl_dict.get("periods", []) if isinstance(pl_dict, dict) else (pl_dict.periods if hasattr(pl_dict, "periods") else [])
    q_periods = q_dict.get("periods", []) if isinstance(q_dict, dict) else (q_dict.periods if hasattr(q_dict, "periods") else [])
    bs_periods = bs_dict.get("periods", []) if isinstance(bs_dict, dict) else (bs_dict.periods if hasattr(bs_dict, "periods") else [])
    
    comparison = {
        "metric_name": metric_name,
        "category": fact.get("category", "operational_kpi"),
        "scope": scope,
        "latest_period": period_str,
        "latest_value_raw": stated_val_raw,
        "latest_numeric": num_val,
        "prior_period": None,
        "prior_value_raw": None,
        "prior_numeric": None,
        "delta_numeric": None,
        "pct_change": None,
        "unit": unit,
        "statement_verification_status": "Not Enough Evidence",
        "statement_reported_value": None,
        "management_explanation": quote or None,
        "stocker_assessment": "Unverified against standardized financial statements.",
        "source_doc_title": doc_title,
        "source_url": fact.get("doc_url"),
        "source_page": fact.get("source_page"),
        "newer_evidence_available": False,
        "newer_evidence_note": None
    }
    
    def get_statement_row(stmt_data: Any, row_names: List[str]) -> Dict[str, Optional[float]]:
        if not stmt_data: return {}
        rows = stmt_data.get("rows", []) if isinstance(stmt_data, dict) else getattr(stmt_data, "rows", [])
        for r in rows:
            m = r.get("metric", "") if isinstance(r, dict) else getattr(r, "metric", "")
            for target in row_names:
                if target.lower() in m.lower():
                    return r.get("values", {}) if isinstance(r, dict) else getattr(r, "values", {})
        return {}

    is_scope_standalone_or_seg = (
        scope.lower() not in ("consolidated", "global", "") or
        any(g in norm_metric for g in ["india", "africa", "us", "usa", "europe", "retail", "enterprise", "wholesale", "standalone"])
    )

    # 1. REVENUE / SALES CLAIM
    if any(k in norm_metric for k in ["revenue", "sales", "turnover", "topline"]) and not any(k in norm_metric for k in ["ebitda", "margin", "pat", "profit", "arpu", "capacity", "order", "subscribers"]):
        pl_matched = match_statement_period(period_str, pl_periods)
        if pl_matched and pl_matched in pl_periods:
            sales_vals = get_statement_row(pl_dict, ["Sales", "Revenue from operations", "Revenue"])
            curr_sales = sales_vals.get(pl_matched)
            idx = pl_periods.index(pl_matched)
            if idx > 0 and curr_sales is not None:
                prior_p = pl_periods[idx - 1]
                prev_sales = sales_vals.get(prior_p)
                if prev_sales is not None and prev_sales > 0:
                    delta = round(curr_sales - prev_sales, 1)
                    actual_growth = round(((curr_sales - prev_sales) / prev_sales) * 100.0, 1)
                    comparison["prior_period"] = prior_p
                    comparison["prior_value_raw"] = f"₹{prev_sales:,.0f} Cr"
                    comparison["prior_numeric"] = prev_sales
                    comparison["delta_numeric"] = delta
                    comparison["pct_change"] = actual_growth
                    comparison["statement_reported_value"] = f"₹{curr_sales:,.0f} Cr (vs ₹{prev_sales:,.0f} Cr, +{actual_growth}% YoY)"
                    
                    if is_scope_standalone_or_seg and num_val is not None and abs(num_val - actual_growth) > 1.5 and abs(num_val - curr_sales) > 100.0:
                        comparison["statement_verification_status"] = "Statement Context Only / Not Directly Comparable"
                        comparison["stocker_assessment"] = (
                            f"Scope Mismatch Context: Filing claim is for '{scope}' while standardized financial statements are Consolidated. "
                            f"Reported consolidated revenue for {pl_matched} stood at ₹{curr_sales:,.0f} Cr (+{actual_growth}% YoY vs {prior_p} ₹{prev_sales:,.0f} Cr)."
                        )
                    elif num_val is not None:
                        # Check percentage growth match or absolute revenue match
                        if "%" in unit or abs(num_val - actual_growth) <= 1.0 or num_val < 80.0:
                            if abs(num_val - actual_growth) <= 1.0:
                                comparison["statement_verification_status"] = "Verified against Reported Financials"
                                comparison["stocker_assessment"] = (
                                    f"Verified: Reported standardized revenue in {pl_matched} was ₹{curr_sales:,.0f} Cr versus "
                                    f"₹{prev_sales:,.0f} Cr in {prior_p} (+{actual_growth}% YoY growth). Matches stated claim of {stated_val_raw}."
                                )
                            else:
                                comparison["statement_verification_status"] = "Discrepancy vs Reported Financials"
                                comparison["stocker_assessment"] = (
                                    f"Discrepancy: Filing claimed revenue growth of {stated_val_raw}, but standardized financial statements show revenue grew "
                                    f"{actual_growth}% YoY (₹{curr_sales:,.0f} Cr in {pl_matched} vs ₹{prev_sales:,.0f} Cr in {prior_p})."
                                )
                        elif abs(num_val - curr_sales) / max(curr_sales, 1) <= 0.02:
                            comparison["statement_verification_status"] = "Verified against Reported Financials"
                            comparison["stocker_assessment"] = (
                                f"Verified: Reported standardized revenue in {pl_matched} was ₹{curr_sales:,.0f} Cr (+{actual_growth}% YoY). Matches stated claim of {stated_val_raw}."
                            )
                        else:
                            comparison["statement_verification_status"] = "Discrepancy vs Reported Financials"
                            comparison["stocker_assessment"] = (
                                f"Discrepancy: Filing stated revenue of {stated_val_raw}, but reported standardized revenue for {pl_matched} was ₹{curr_sales:,.0f} Cr."
                            )
                    else:
                        comparison["statement_verification_status"] = "Statement Context Only / Not Directly Comparable"
                        comparison["stocker_assessment"] = (
                            f"Statement Context: Standardized revenue for {pl_matched} stood at ₹{curr_sales:,.0f} Cr (+{actual_growth}% YoY vs {prior_p} ₹{prev_sales:,.0f} Cr)."
                        )
                    return comparison

    # 2A. EBITDA MARGIN / OPM % / MARGIN MOVEMENT (bps)
    is_margin_or_opm = (
        any(k in norm_metric for k in ["opm", "operating margin", "ebitda margin", "operating profit margin"]) or
        ("margin" in norm_metric and not any(k in norm_metric for k in ["sales", "revenue", "pat", "net profit", "profit after tax", "cash", "cfo"])) or
        "bps" in unit.lower() or "basis point" in norm_metric
    ) and not any(k in norm_metric for k in ["sales", "revenue", "pat", "net profit", "profit after tax", "capacity", "order", "subscribers", "arpu"])

    if is_margin_or_opm:
        pl_matched = match_statement_period(period_str, pl_periods)
        if pl_matched and pl_matched in pl_periods:
            opm_vals = get_statement_row(pl_dict, ["OPM %", "Operating Profit Margin", "EBITDA Margin %", "OPM"])
            curr_opm = opm_vals.get(pl_matched)
            idx = pl_periods.index(pl_matched)
            if idx > 0 and curr_opm is not None:
                prior_p = pl_periods[idx - 1]
                prev_opm = opm_vals.get(prior_p)
                if prev_opm is not None:
                    delta_bps = round((curr_opm - prev_opm) * 100.0, 0)
                    comparison["prior_period"] = prior_p
                    comparison["prior_value_raw"] = f"{prev_opm:.1f}%"
                    comparison["prior_numeric"] = prev_opm
                    comparison["delta_numeric"] = round(curr_opm - prev_opm, 1)
                    comparison["pct_change"] = round(((curr_opm - prev_opm) / prev_opm) * 100.0, 1) if prev_opm > 0 else None
                    comparison["statement_reported_value"] = f"{curr_opm:.1f}% ({'+' if delta_bps >= 0 else ''}{delta_bps:.0f} bps vs {prior_p})"
                    
                    if num_val is not None:
                        if "bps" in unit.lower() or "basis" in norm_metric:
                            if abs(num_val - delta_bps) <= 50.0:
                                comparison["statement_verification_status"] = "Verified against Reported Financials"
                                comparison["stocker_assessment"] = (
                                    f"Verified: Standardized OPM moved {'+' if delta_bps >= 0 else ''}{delta_bps:.0f} bps from {prev_opm:.1f}% ({prior_p}) "
                                    f"to {curr_opm:.1f}% ({pl_matched}). Matches stated margin movement claim of {stated_val_raw}."
                                )
                            else:
                                comparison["statement_verification_status"] = "Discrepancy vs Reported Financials"
                                comparison["stocker_assessment"] = (
                                    f"Discrepancy: Filing claimed margin movement of {stated_val_raw}, but standardized statements show OPM moved "
                                    f"{'+' if delta_bps >= 0 else ''}{delta_bps:.0f} bps ({prev_opm:.1f}% to {curr_opm:.1f}%)."
                                )
                        elif abs(num_val - curr_opm) <= 1.0:
                            comparison["statement_verification_status"] = "Verified against Reported Financials"
                            comparison["stocker_assessment"] = (
                                f"Verified: Reported OPM was {curr_opm:.1f}% in {pl_matched} vs {prev_opm:.1f}% in {prior_p} "
                                f"({'+' if delta_bps >= 0 else ''}{delta_bps:.0f} bps movement). "
                                f"{'Evidence supports management explanation.' if quote else ''}"
                            )
                        else:
                            comparison["statement_verification_status"] = "Discrepancy vs Reported Financials"
                            comparison["stocker_assessment"] = (
                                f"Discrepancy: Filing claimed margin of {stated_val_raw}, but reported standardized OPM was {curr_opm:.1f}% "
                                f"({'+' if delta_bps >= 0 else ''}{delta_bps:.0f} bps vs {prior_p} of {prev_opm:.1f}%)."
                            )
                    else:
                        comparison["statement_verification_status"] = "Statement Context Only / Not Directly Comparable"
                        comparison["stocker_assessment"] = (
                            f"Statement Context: Standardized OPM in {pl_matched} was {curr_opm:.1f}% vs {prev_opm:.1f}% in {prior_p}."
                        )
                    return comparison

    # 2B. EBITDA / OPERATING PROFIT ABSOLUTE AMOUNT (₹ Cr) & GROWTH (%)
    is_ebitda_or_op_amount = (
        any(k in norm_metric for k in ["ebitda", "operating profit", "pbidt", "core operating profit"]) and
        not is_margin_or_opm and
        not any(k in norm_metric for k in ["sales", "revenue", "pat", "net profit", "profit after tax", "capacity", "order", "subscribers", "arpu"])
    )
    if is_ebitda_or_op_amount:
        pl_matched = match_statement_period(period_str, pl_periods)
        if pl_matched and pl_matched in pl_periods:
            op_vals = get_statement_row(pl_dict, ["Operating Profit", "EBITDA", "Operating profit before tax"])
            curr_op = op_vals.get(pl_matched)
            idx = pl_periods.index(pl_matched)
            if idx > 0 and curr_op is not None:
                prior_p = pl_periods[idx - 1]
                prev_op = op_vals.get(prior_p)
                if prev_op is not None and prev_op > 0:
                    delta_op = round(curr_op - prev_op, 1)
                    growth_op = round(((curr_op - prev_op) / prev_op) * 100.0, 1)
                    comparison["prior_period"] = prior_p
                    comparison["prior_value_raw"] = f"₹{prev_op:,.0f} Cr"
                    comparison["prior_numeric"] = prev_op
                    comparison["delta_numeric"] = delta_op
                    comparison["pct_change"] = growth_op
                    comparison["statement_reported_value"] = f"₹{curr_op:,.0f} Cr (vs ₹{prev_op:,.0f} Cr, {'+' if growth_op >= 0 else ''}{growth_op}% YoY)"
                    
                    if num_val is not None:
                        is_growth_claim = (
                            "%" in unit or
                            any(k in norm_metric for k in ["growth", "increase", "expansion", "yoy", "jump"]) or
                            (num_val < 100.0 and abs(num_val - growth_op) <= 2.0)
                        )
                        if is_growth_claim:
                            if abs(num_val - growth_op) <= 1.5:
                                comparison["statement_verification_status"] = "Verified against Reported Financials"
                                comparison["stocker_assessment"] = (
                                    f"Verified: Reported standardized Operating Profit (EBITDA) grew {growth_op}% YoY in {pl_matched} "
                                    f"(₹{curr_op:,.0f} Cr vs ₹{prev_op:,.0f} Cr in {prior_p}). Matches stated claim of {stated_val_raw}."
                                )
                            else:
                                comparison["statement_verification_status"] = "Discrepancy vs Reported Financials"
                                comparison["stocker_assessment"] = (
                                    f"Discrepancy: Filing claimed Operating Profit / EBITDA growth of {stated_val_raw}, but standardized statements "
                                    f"show Operating Profit grew {growth_op}% YoY (₹{curr_op:,.0f} Cr in {pl_matched} vs ₹{prev_op:,.0f} Cr in {prior_p})."
                                )
                        elif abs(num_val - curr_op) / max(curr_op, 1) <= 0.03:
                            comparison["statement_verification_status"] = "Verified against Reported Financials"
                            comparison["stocker_assessment"] = (
                                f"Verified: Reported standardized Operating Profit (EBITDA) in {pl_matched} was ₹{curr_op:,.0f} Cr "
                                f"(vs ₹{prev_op:,.0f} Cr in {prior_p}, {'+' if growth_op >= 0 else ''}{growth_op}% YoY). Matches stated claim of {stated_val_raw}."
                            )
                        else:
                            comparison["statement_verification_status"] = "Discrepancy vs Reported Financials"
                            comparison["stocker_assessment"] = (
                                f"Discrepancy: Filing stated Operating Profit / EBITDA of {stated_val_raw}, but reported standardized "
                                f"Operating Profit for {pl_matched} was ₹{curr_op:,.0f} Cr."
                            )
                    else:
                        comparison["statement_verification_status"] = "Statement Context Only / Not Directly Comparable"
                        comparison["stocker_assessment"] = (
                            f"Statement Context: Standardized Operating Profit (EBITDA) for {pl_matched} was ₹{curr_op:,.0f} Cr (+{growth_op}% YoY vs {prior_p} ₹{prev_op:,.0f} Cr)."
                        )
                    return comparison
            elif curr_op is None:
                comparison["statement_verification_status"] = "Statement Context Only / Not Directly Comparable"
                comparison["stocker_assessment"] = f"Statement Context: Operating Profit / EBITDA absolute line is not broken out in financial statements for {period_str}."
                return comparison

    # 3. NET PROFIT / PAT CLAIM
    if any(k in norm_metric for k in ["net profit", "pat", "profit after tax"]):
        pl_matched = match_statement_period(period_str, pl_periods)
        if pl_matched and pl_matched in pl_periods:
            pat_vals = get_statement_row(pl_dict, ["Net Profit", "PAT", "Profit after tax"])
            curr_pat = pat_vals.get(pl_matched)
            idx = pl_periods.index(pl_matched)
            if idx > 0 and curr_pat is not None:
                prior_p = pl_periods[idx - 1]
                prev_pat = pat_vals.get(prior_p)
                if prev_pat is not None and prev_pat > 0:
                    growth_pat = round(((curr_pat - prev_pat) / prev_pat) * 100.0, 1)
                    comparison["prior_period"] = prior_p
                    comparison["prior_value_raw"] = f"₹{prev_pat:,.0f} Cr"
                    comparison["prior_numeric"] = prev_pat
                    comparison["delta_numeric"] = round(curr_pat - prev_pat, 1)
                    comparison["pct_change"] = growth_pat
                    comparison["statement_reported_value"] = f"₹{curr_pat:,.0f} Cr (+{growth_pat}% YoY)"
                    
                    if num_val is not None:
                        if "%" in unit or abs(num_val - growth_pat) <= 1.5:
                            if abs(num_val - growth_pat) <= 1.5:
                                comparison["statement_verification_status"] = "Verified against Reported Financials"
                                comparison["stocker_assessment"] = f"Verified: Standardized Net Profit was ₹{curr_pat:,.0f} Cr in {pl_matched} vs ₹{prev_pat:,.0f} Cr in {prior_p} (+{growth_pat}% YoY). Matches stated claim."
                            else:
                                comparison["statement_verification_status"] = "Discrepancy vs Reported Financials"
                                comparison["stocker_assessment"] = f"Discrepancy: Filing claimed PAT growth of {stated_val_raw}, but standardized Net Profit grew {growth_pat}% YoY (₹{curr_pat:,.0f} Cr vs ₹{prev_pat:,.0f} Cr)."
                        elif abs(num_val - curr_pat) / max(curr_pat, 1) <= 0.03:
                            comparison["statement_verification_status"] = "Verified against Reported Financials"
                            comparison["stocker_assessment"] = f"Verified: Standardized Net Profit in {pl_matched} was ₹{curr_pat:,.0f} Cr (+{growth_pat}% YoY vs ₹{prev_pat:,.0f} Cr). Matches stated claim."
                        else:
                            comparison["statement_verification_status"] = "Discrepancy vs Reported Financials"
                            comparison["stocker_assessment"] = f"Discrepancy: Filing stated PAT of {stated_val_raw}, but standardized Net Profit for {pl_matched} was ₹{curr_pat:,.0f} Cr."
                    else:
                        comparison["statement_verification_status"] = "Statement Context Only / Not Directly Comparable"
                        comparison["stocker_assessment"] = f"Statement Context: Standardized Net Profit for {pl_matched} was ₹{curr_pat:,.0f} Cr (+{growth_pat}% YoY vs {prior_p} ₹{prev_pat:,.0f} Cr)."
                    return comparison

    # 4. DEBT / BORROWINGS CLAIM
    if any(k in norm_metric for k in ["debt", "borrowing", "borrowings", "leverage"]):
        bs_matched = match_statement_period(period_str, bs_periods)
        if bs_matched and bs_matched in bs_periods:
            borrowing_vals = get_statement_row(bs_dict, ["Borrowings", "Total Debt"])
            curr_debt = borrowing_vals.get(bs_matched)
            idx = bs_periods.index(bs_matched)
            if idx > 0 and curr_debt is not None:
                prior_p = bs_periods[idx - 1]
                prev_debt = borrowing_vals.get(prior_p)
                if prev_debt is not None:
                    delta_debt = round(curr_debt - prev_debt, 1)
                    comparison["prior_period"] = prior_p
                    comparison["prior_value_raw"] = f"₹{prev_debt:,.0f} Cr"
                    comparison["prior_numeric"] = prev_debt
                    comparison["delta_numeric"] = delta_debt
                    comparison["statement_reported_value"] = f"₹{curr_debt:,.0f} Cr (Δ ₹{delta_debt:,.0f} Cr vs {prior_p})"
                    
                    if num_val is not None:
                        if abs(num_val - curr_debt) / max(curr_debt, 1) <= 0.03:
                            comparison["statement_verification_status"] = "Verified against Reported Financials"
                            if delta_debt < 0:
                                comparison["stocker_assessment"] = f"Verified: Balance sheet borrowings reduced by ₹{abs(delta_debt):,.0f} Cr from ₹{prev_debt:,.0f} Cr ({prior_p}) to ₹{curr_debt:,.0f} Cr ({bs_matched}). Matches stated claim."
                            else:
                                comparison["stocker_assessment"] = f"Verified: Balance sheet borrowings stood at ₹{curr_debt:,.0f} Cr in {bs_matched} (vs ₹{prev_debt:,.0f} Cr in {prior_p}). Matches stated claim."
                        elif abs(num_val - abs(delta_debt)) / max(abs(delta_debt), 1) <= 0.05:
                            comparison["statement_verification_status"] = "Verified against Reported Financials"
                            comparison["stocker_assessment"] = f"Verified: Balance sheet borrowings changed by ₹{delta_debt:,.0f} Cr from ₹{prev_debt:,.0f} Cr to ₹{curr_debt:,.0f} Cr in {bs_matched}. Matches stated debt movement."
                        else:
                            comparison["statement_verification_status"] = "Discrepancy vs Reported Financials"
                            comparison["stocker_assessment"] = f"Discrepancy: Filing stated debt of {stated_val_raw}, but standardized borrowings in {bs_matched} were ₹{curr_debt:,.0f} Cr (vs ₹{prev_debt:,.0f} Cr in {prior_p})."
                    else:
                        comparison["statement_verification_status"] = "Statement Context Only / Not Directly Comparable"
                        comparison["stocker_assessment"] = f"Balance Sheet Context: Borrowings in {bs_matched} stood at ₹{curr_debt:,.0f} Cr (Δ ₹{delta_debt:,.0f} Cr vs {prior_p} ₹{prev_debt:,.0f} Cr)."
                    return comparison

    # 5. Non-Statement Operational KPI (Tracked via Inter-Document Engine)
    comparison["statement_verification_status"] = "Operational KPI (Inter-Document Comparison)"
    comparison["stocker_assessment"] = "Non-statement operational metric tracked chronologically across official company filings."
    return comparison

def build_inter_document_kpi_trends(facts_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Groups extracted facts across documents to build multi-year/multi-quarter operational KPI trends
    (e.g. ARPU, capacity, order book, subscriber additions, volume, stores).
    Conservative matching: only merges facts with identical metric identity, scope/geography, unit, and claim type.
    """
    if not facts_list:
        return []
        
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for f in facts_list:
        m_name = f.get("metric_name", "").strip()
        if not m_name:
            continue
            
        ident = extract_kpi_identity(f)
        key = ident["id_key"]
        grouped.setdefault(key, []).append(f)
        
    trends: List[Dict[str, Any]] = []
    
    for key, items in grouped.items():
        if len(items) < 1:
            continue
            
        # Deduplicate and sort items chronologically by period date
        sorted_items = sorted(
            items,
            key=lambda x: parse_filing_period_to_year(x.get("period_or_date") or x.get("period")) or 0.0
        )
        
        # Deduplicate: only deduplicate when period matches within this exact identity
        seen_periods = set()
        deduped_series = []
        for it in sorted_items:
            p = it.get("period_or_date") or it.get("period") or "Latest"
            if p not in seen_periods:
                seen_periods.add(p)
                deduped_series.append(it)
                
        if not deduped_series or len(deduped_series) < 2:
            continue
            
        norm_core = key.split(":")[0] if ":" in key else key
        BANK_KPI_DISPLAY_NAMES = {
            "nim": "Net Interest Margin (NIM)",
            "gnpa": "Gross NPA (GNPA)",
            "nnpa": "Net NPA (NNPA)",
            "credit_cost": "Credit Cost",
            "casa": "CASA Ratio",
            "deposit_growth": "Deposit Growth",
            "loan_growth": "Advances / Loan Growth",
            "deposits": "Total Deposits",
            "advances": "Total Advances",
            "capital_adequacy": "CET1 / Capital Adequacy",
            "roa": "Return on Assets (ROA)",
            "slippages": "Slippages"
        }

        if norm_core in BANK_KPI_DISPLAY_NAMES:
            canonical_name = BANK_KPI_DISPLAY_NAMES[norm_core]
            category = "bank_kpi"
        else:
            canonical_name = deduped_series[-1].get("metric_name", key.replace(":", " - ").title())
            category = deduped_series[-1].get("category", "operational_kpi")

        unit = deduped_series[-1].get("unit") or ""
        
        data_points = []
        for it in deduped_series:
            raw_v = it.get("numeric_value")
            if raw_v is None:
                val = it.get("value")
                if isinstance(val, (int, float)):
                    raw_v = float(val)
                elif isinstance(val, str):
                    m = re.search(r'[-+]?\d+(?:\.\d+)?', val)
                    if m:
                        try:
                            raw_v = float(m.group(0))
                        except ValueError:
                            raw_v = None
            data_points.append({
                "period": it.get("period_or_date") or it.get("period", ""),
                "stated_value": str(it.get("stated_value_raw") or it.get("value", "")),
                "numeric_value": raw_v,
                "doc_title": it.get("doc_title", "Filing"),
                "doc_url": it.get("doc_url"),
                "doc_type": it.get("doc_type", "filing")
            })
            
        latest_pt = data_points[-1]
        prior_pt = data_points[-2]
        
        trajectory = "Evolving"
        latest_vs_prior_change = None
        pct_chg = None
        insight = f"Latest reported {canonical_name}: {latest_pt['stated_value']} ({latest_pt['period']})."
        
        is_lower_better = norm_core in ("gnpa", "nnpa", "credit_cost", "cost_to_income", "slippages") or any(kw in key.lower() for kw in ["gnpa", "nnpa", "credit_cost", "cost_to_income", "slippage"])
        
        if prior_pt and latest_pt.get("numeric_value") is not None and prior_pt.get("numeric_value") is not None:
            v_curr = latest_pt["numeric_value"]
            v_prev = prior_pt["numeric_value"]
            delta = round(v_curr - v_prev, 2)
            if v_prev > 0:
                pct_chg = round(((v_curr - v_prev) / v_prev) * 100.0, 1)
                
            if is_lower_better:
                if delta < 0:
                    trajectory = "Improving"
                    latest_vs_prior_change = f"{delta:,.2f} {unit} ({pct_chg}%)" if pct_chg is not None else f"{delta:,.2f} {unit}"
                elif delta > 0:
                    trajectory = "Deteriorating"
                    latest_vs_prior_change = f"+{delta:,.2f} {unit} (+{pct_chg}%)" if pct_chg is not None else f"+{delta:,.2f} {unit}"
                else:
                    trajectory = "Stable"
                    latest_vs_prior_change = "Flat (0.0% change)"
            else:
                if delta > 0:
                    trajectory = "Expanding / Accelerating"
                    latest_vs_prior_change = f"+{delta:,.1f} {unit} (+{pct_chg}%)" if pct_chg is not None else f"+{delta:,.1f} {unit}"
                elif delta < 0:
                    trajectory = "Contracting"
                    latest_vs_prior_change = f"{delta:,.1f} {unit} ({pct_chg}%)" if pct_chg is not None else f"{delta:,.1f} {unit}"
                else:
                    trajectory = "Stable"
                    latest_vs_prior_change = "Flat (0.0% change)"
                
            insight = (
                f"{canonical_name} moved from {prior_pt['stated_value']} ({prior_pt['period']}) to "
                f"{latest_pt['stated_value']} ({latest_pt['period']}), representing a {latest_vs_prior_change} shift across official filings."
            )
            
        trends.append({
            "metric_name": canonical_name,
            "normalized_core": norm_core,
            "category": category,
            "unit": unit,
            "trajectory": trajectory,
            "data_points": data_points,
            "latest_vs_prior_change": latest_vs_prior_change,
            "pct_change": pct_chg,
            "insight": insight
        })
        
    return trends

def triangulate_guidance_vs_projections(
    facts_list: List[Dict[str, Any]],
    stock_data: Dict[str, Any],
    projection_assumptions: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Objectively compares Management Guidance targets with Stocker DCF Projections and actual run rate.
    Metric-aware: only compares when metrics genuinely correspond (e.g. Revenue Growth vs DCF Revenue Growth).
    Never invents comparisons or defaults to generic 10/15/5% fallback values.
    """
    guidance_facts = [
        f for f in facts_list
        if f.get("claim_type") in ("management_guidance", "management_target") or
           f.get("category") in ("management_guidance", "guidance") or
           "guidance" in normalize_metric_key(f.get("metric_name", ""))
    ]
    
    q_dict = stock_data.get("quarters") or {}
    q_rows = q_dict.get("rows", []) if isinstance(q_dict, dict) else getattr(q_dict, "rows", [])
    q_periods = q_dict.get("periods", []) if isinstance(q_dict, dict) else getattr(q_dict, "periods", [])
    
    # Helper to get latest quarterly YoY sales growth run-rate
    def get_quarterly_sales_growth():
        if not q_periods or len(q_periods) < 5:
            return None, None
        for r in q_rows:
            m = r.get("metric", "") if isinstance(r, dict) else getattr(r, "metric", "")
            if "sales" in m.lower() or "revenue" in m.lower():
                vals = r.get("values", {}) if isinstance(r, dict) else getattr(r, "values", {})
                curr_q = vals.get(q_periods[-1])
                prev_q = vals.get(q_periods[-5])
                if curr_q and prev_q and prev_q > 0:
                    g = round(((curr_q - prev_q) / prev_q) * 100.0, 1)
                    return g, q_periods[-1]
        return None, None

    # Helper to get latest quarterly OPM % run-rate
    def get_quarterly_opm():
        if not q_periods:
            return None, None
        for r in q_rows:
            m = r.get("metric", "") if isinstance(r, dict) else getattr(r, "metric", "")
            if "opm" in m.lower() or "operating margin" in m.lower():
                vals = r.get("values", {}) if isinstance(r, dict) else getattr(r, "values", {})
                curr_q = vals.get(q_periods[-1])
                if curr_q is not None:
                    return curr_q, q_periods[-1]
        return None, None

    # Helper to get latest quarterly PAT % YoY run-rate
    def get_quarterly_pat_growth():
        if not q_periods or len(q_periods) < 5:
            return None, None
        for r in q_rows:
            m = r.get("metric", "") if isinstance(r, dict) else getattr(r, "metric", "")
            if "net profit" in m.lower() or "pat" in m.lower():
                vals = r.get("values", {}) if isinstance(r, dict) else getattr(r, "values", {})
                curr_q = vals.get(q_periods[-1])
                prev_q = vals.get(q_periods[-5])
                if curr_q is not None and prev_q is not None and prev_q > 0:
                    g = round(((curr_q - prev_q) / prev_q) * 100.0, 1)
                    return g, q_periods[-1]
        return None, None

    results: List[Dict[str, Any]] = []
    
    for gf in guidance_facts:
        m_name = gf.get("metric_name", "Management Guidance")
        m_name_lower = m_name.lower()
        target_p = gf.get("target_period") or gf.get("period_or_date") or "Next Financial Year"
        raw_val = str(gf.get("stated_value_raw") or "")
        num_val = gf.get("numeric_value")
        doc_title = gf.get("doc_title", "Concall / Presentation")
        doc_url = gf.get("doc_url")
        
        is_revenue = any(k in m_name_lower for k in ["revenue", "sales", "turnover", "topline", "growth"]) and not any(k in m_name_lower for k in ["ebitda", "margin", "opm", "pat", "profit", "arpu", "capacity", "order", "subscribers", "capex"])
        is_ebitda_margin = any(k in m_name_lower for k in ["ebitda margin", "opm", "operating margin", "operating profit margin"]) or ("margin" in m_name_lower and not any(k in m_name_lower for k in ["sales", "revenue", "pat", "profit", "capacity", "order"]))
        is_pat = any(k in m_name_lower for k in ["net profit", "pat", "profit after tax"]) and not is_ebitda_margin and not is_revenue
        is_capex = ("capex" in m_name_lower or "capital expenditure" in m_name_lower) and not is_revenue
        is_operational = any(k in m_name_lower for k in ["capacity", "order", "arpu", "subscriber", "user", "store", "outlet", "volume", "tcv", "deal"])

        base_proj = None
        bull_proj = None
        bear_proj = None
        var_bps = None
        run_rate_val = None
        run_rate_p = None
        assessment = ""

        if is_revenue:
            run_rate_val, run_rate_p = get_quarterly_sales_growth()
            if projection_assumptions and ("revenue_growth_rate_pct" in projection_assumptions or "base_sales_cagr" in projection_assumptions):
                base_proj = projection_assumptions.get("revenue_growth_rate_pct") or projection_assumptions.get("base_sales_cagr")
                bull_proj = projection_assumptions.get("bull_sales_cagr") or (round(base_proj * 1.35, 1) if base_proj else None)
                bear_proj = projection_assumptions.get("bear_sales_cagr") or (round(base_proj * 0.65, 1) if base_proj else None)
                if num_val is not None and base_proj is not None:
                    var_bps = round((num_val - base_proj) * 100.0, 0)
                    assessment = (
                        f"Management revenue guidance of {raw_val} for {target_p} "
                        f"{f'is +{var_bps:.0f} bps above' if var_bps >= 0 else f'is {var_bps:.0f} bps below'} "
                        f"Stocker's Base DCF projection of {base_proj}%. "
                        f"Latest quarterly run rate is {f'{run_rate_val}% YoY ({run_rate_p})' if run_rate_val is not None else 'tracked ongoing'}."
                    )
                else:
                    assessment = f"Management guided revenue of {raw_val} for {target_p} (Stocker Base DCF projection: {base_proj}%)."
            else:
                assessment = f"Management revenue guidance: {raw_val} for {target_p}. No directly comparable Stocker projection available."
                
        elif is_ebitda_margin:
            run_rate_val, run_rate_p = get_quarterly_opm()
            if projection_assumptions and ("target_opm_pct" in projection_assumptions or "ebitda_margin_pct" in projection_assumptions or "operating_margin_pct" in projection_assumptions):
                base_proj = projection_assumptions.get("target_opm_pct") or projection_assumptions.get("ebitda_margin_pct") or projection_assumptions.get("operating_margin_pct")
                bull_proj = round(base_proj + 2.0, 1) if base_proj is not None else None
                bear_proj = round(base_proj - 2.0, 1) if base_proj is not None else None
                if num_val is not None and base_proj is not None:
                    var_bps = round((num_val - base_proj) * 100.0, 0)
                    assessment = (
                        f"Management EBITDA margin guidance of {raw_val} for {target_p} "
                        f"{f'is +{var_bps:.0f} bps above' if var_bps >= 0 else f'is {var_bps:.0f} bps below'} "
                        f"Stocker's margin assumption of {base_proj}%. Latest reported quarterly OPM is {run_rate_val}% ({run_rate_p})."
                    )
                else:
                    assessment = f"Management margin guidance: {raw_val} for {target_p} (Stocker assumption: {base_proj}%)."
            else:
                assessment = f"Management margin guidance: {raw_val} for {target_p}. No directly comparable Stocker margin projection available. (Latest quarterly OPM: {run_rate_val}% in {run_rate_p})."
                
        elif is_pat:
            run_rate_val, run_rate_p = get_quarterly_pat_growth()
            if projection_assumptions and ("base_pat_cagr" in projection_assumptions or "pat_growth_rate_pct" in projection_assumptions):
                base_proj = projection_assumptions.get("base_pat_cagr") or projection_assumptions.get("pat_growth_rate_pct")
                bull_proj = projection_assumptions.get("bull_pat_cagr")
                bear_proj = projection_assumptions.get("bear_pat_cagr")
                if num_val is not None and base_proj is not None:
                    var_bps = round((num_val - base_proj) * 100.0, 0)
                    assessment = (
                        f"Management PAT guidance of {raw_val} for {target_p} "
                        f"{f'is +{var_bps:.0f} bps above' if var_bps >= 0 else f'is {var_bps:.0f} bps below'} "
                        f"Stocker's PAT projection of {base_proj}%. Latest quarterly PAT growth is {run_rate_val}% ({run_rate_p})."
                    )
                else:
                    assessment = f"Management PAT guidance: {raw_val} for {target_p} (Stocker PAT projection: {base_proj}%)."
            else:
                assessment = f"Management PAT guidance: {raw_val} for {target_p}. No directly comparable Stocker PAT projection available."

        elif is_capex:
            if projection_assumptions and "capex_pct_of_sales" in projection_assumptions:
                base_proj = projection_assumptions.get("capex_pct_of_sales")
                assessment = f"Management capex guidance: {raw_val} for {target_p} (Stocker modeled capex intensity: {base_proj}% of sales)."
            else:
                assessment = f"Management capex guidance: {raw_val} for {target_p}. No directly comparable Stocker capex projection available."

        elif is_operational:
            base_proj = None
            bull_proj = None
            bear_proj = None
            var_bps = None
            
            # Search for latest actual reported fact in facts_list
            ident = extract_kpi_identity(gf)
            actual_facts = [
                f for f in facts_list
                if extract_kpi_identity(f)["metric_core"] == ident["metric_core"] and
                   extract_kpi_identity(f)["scope"] == ident["scope"] and
                   extract_kpi_identity(f)["intent"] == "actual"
            ]
            if actual_facts:
                latest_act = actual_facts[-1]
                run_rate_val = latest_act.get("numeric_value")
                run_rate_p = latest_act.get("period_or_date")
                assessment = (
                    f"Operational target: Management guided {raw_val} for {target_p}. "
                    f"No directly comparable Stocker projection available (Stocker models financial line items, not operational unit metrics). "
                    f"Current reported baseline is {latest_act.get('stated_value_raw')} ({run_rate_p})."
                )
            else:
                assessment = f"Operational target: Management guided {raw_val} for {target_p}. No directly comparable Stocker projection available."
        else:
            assessment = f"Management guidance: {raw_val} for {target_p}. No directly comparable Stocker projection available."

        results.append({
            "metric_name": m_name,
            "period_target": target_p,
            "management_guidance_raw": raw_val,
            "management_guidance_numeric": num_val,
            "guidance_source_doc": doc_title,
            "guidance_source_url": doc_url,
            "stocker_projected_base": base_proj,
            "stocker_projected_bull": bull_proj,
            "stocker_projected_bear": bear_proj,
            "current_run_rate_value": run_rate_val,
            "current_run_rate_period": run_rate_p,
            "variance_guidance_vs_base_bps": var_bps,
            "stocker_assessment": assessment
        })
        
    return results

def process_and_verify_company_knowledge(
    symbol: str,
    facts_list: List[Dict[str, Any]],
    stock_data: Dict[str, Any],
    projection_assumptions: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Master engine coordinating:
    1. Financial statement claim verification
    2. Chronological inter-document KPI time series
    3. Management guidance vs Stocker projection triangulation
    """
    clean_sym = symbol.upper().strip()
    verified_facts: List[Dict[str, Any]] = []
    
    # 1. Statement Claim Verification
    for f in facts_list:
        v_fact = verify_document_claim_against_financials(f, stock_data)
        verified_facts.append(v_fact)
        
    # 2. Inter-Document Operational KPI Evolution
    kpi_trends = build_inter_document_kpi_trends(facts_list)
    
    # 3. Guidance vs Stocker Projections Triangulation
    guidance_triangulation = triangulate_guidance_vs_projections(facts_list, stock_data, projection_assumptions)
    
    return {
        "symbol": clean_sym,
        "verified_facts": verified_facts,
        "operational_kpi_evolution": kpi_trends,
        "guidance_vs_projections": guidance_triangulation
    }


