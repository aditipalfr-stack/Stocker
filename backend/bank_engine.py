"""
=============================================================================
Stocker Banking Analytics Engine (Tier 1)
=============================================================================
Deterministic, Truth-Aware Tier 1 Banking Analytics Engine.

Rules & Invariants:
- Uses ONLY raw standardized statement information already in Stocker.
- 100% deterministic local calculation. Zero AI, zero network calls.
- Fail-Closed exact period chronology (annual_completed only for FY metrics).
- Missing data is always None (rendered as —), never coerced to 0.0.
- Real 0.0 (e.g. Net NPA = 0.0%, Other Income = 0.0) is strictly preserved as 0.0.
- Equity requires direct Net Worth OR BOTH Equity Capital and Reserves present.
- Total Assets strictly requires direct Total Assets / Total Liabilities row.
- Average assets & average equity required for ROA & ROE (no ending-asset shortcuts).
- Average gross advances required for Credit Cost.
- Cost-to-income requires explicit bank-specific Operating Expenses and Net Income (with required Other Income).
- Neutral provenance wording ("Balance Sheet & P&L") without unsupported "Audited" claims.
- No hardcoded policy interpretation thresholds (e.g. GNPA > X = bad).
=============================================================================
"""

from typing import Dict, List, Any, Optional, Tuple
import math

from models import (
    FinancialStatement,
    FinancialRow,
    KeyRatios,
    BankAnalytics,
    BankTrendItem
)
from financial_truth_resolver import (
    classify_period_type,
    parse_period_year,
    get_common_completed_annual_periods,
    TruthAwareFinancialResolver
)

def _get_row_values(statement: Optional[FinancialStatement], candidate_metrics: List[str], exact_only: bool = False) -> Dict[str, Optional[float]]:
    """Helper to extract row values case-insensitively for matching candidates."""
    if not statement or not statement.rows:
        return {}
    
    cand_lower = [c.strip().lower() for c in candidate_metrics]
    for row in statement.rows:
        r_name = row.metric.strip().lower()
        if exact_only:
            if r_name in cand_lower:
                return {p: row.values.get(p) for p in statement.periods}
        else:
            if r_name in cand_lower or any(c in r_name for c in cand_lower):
                return {p: row.values.get(p) for p in statement.periods}
    return {}

def _get_completed_annual_periods(statement: Optional[FinancialStatement]) -> List[str]:
    """Returns chronologically sorted list of completed annual periods."""
    if not statement or not statement.periods:
        return []
    annual = [p for p in statement.periods if classify_period_type(p) == "annual_completed"]
    return sorted(annual, key=parse_period_year)

def compute_bank_analytics(
    quarters: Optional[FinancialStatement] = None,
    pl: Optional[FinancialStatement] = None,
    bs: Optional[FinancialStatement] = None,
    cf: Optional[FinancialStatement] = None,
    ratios: Optional[KeyRatios] = None,
    symbol: Optional[str] = None,
    financial_truth: Optional[Any] = None,
    sector: Optional[str] = None,
    industry: Optional[str] = None
) -> BankAnalytics:
    """
    Computes deterministic Tier 1 banking analytics from available financial statements.
    """
    resolver = TruthAwareFinancialResolver(
        symbol=symbol,
        financial_truth=financial_truth,
        quarters=quarters,
        pl=pl,
        bs=bs,
        cf=cf
    )
    
    unavailable_reasons: Dict[str, str] = {}
    provenance: Dict[str, Any] = {}

    # 1. Extract Balance Sheet Series
    dep_vals = _get_row_values(bs, ["deposits", "total deposits", "customer deposits"])
    adv_vals = _get_row_values(bs, ["advances", "loans & advances", "loans and advances", "total advances"])
    bor_vals = _get_row_values(bs, ["borrowings", "total borrowings"])
    
    # Equity Components (Fail Closed: Direct Net Worth OR BOTH Equity Capital & Reserves)
    direct_eq_vals = _get_row_values(bs, ["total equity", "shareholders funds", "shareholders' funds", "net worth"], exact_only=True)
    eq_cap_vals = _get_row_values(bs, ["equity capital", "share capital"], exact_only=True)
    res_vals = _get_row_values(bs, ["reserves", "total reserves"], exact_only=True)
    
    # Total Assets (Fail Closed: Direct Total Assets/Liabilities only, no partial synthesis)
    tot_assets_vals = _get_row_values(bs, ["total assets", "total liabilities"], exact_only=True)
    
    # 2. Extract P&L Series
    prov_vals = _get_row_values(pl, ["provisions", "provisions and contingencies", "provisions & contingencies"])
    
    # Explicit Bank-specific Operating Expenses (Total OpEx only, NOT partial Employee/Staff Cost)
    op_exp_vals = _get_row_values(pl, ["operating expenses", "operating expenditure"], exact_only=True)
    nii_vals = _get_row_values(pl, ["net interest income"], exact_only=True)
    other_inc_vals = _get_row_values(pl, ["other income"], exact_only=True)
    int_earned_vals = _get_row_values(pl, ["interest earned"], exact_only=True)
    int_exp_vals = _get_row_values(pl, ["interest expended", "interest expenses"], exact_only=True)
    
    # 3. Extract NPA Series (from Quarters, or fallback to P&L / BS)
    gnpa_q_vals = _get_row_values(quarters, ["gross npa %", "gross npa"], exact_only=True)
    nnpa_q_vals = _get_row_values(quarters, ["net npa %", "net npa"], exact_only=True)
    gnpa_pl_vals = _get_row_values(pl, ["gross npa %", "gross npa"], exact_only=True)
    nnpa_pl_vals = _get_row_values(pl, ["net npa %", "net npa"], exact_only=True)

    # Completed annual periods
    bs_annual_periods = _get_completed_annual_periods(bs)
    pl_annual_periods = _get_completed_annual_periods(pl)
    
    latest_bs_period = bs_annual_periods[-1] if bs_annual_periods else None
    latest_pl_period = pl_annual_periods[-1] if pl_annual_periods else None
    
    # Compute Fail-Closed Total Equity & Total Assets per BS period
    equity_map: Dict[str, Optional[float]] = {}
    assets_map: Dict[str, Optional[float]] = {}
    
    for p in bs_annual_periods:
        # A. Equity: Direct Net Worth if present
        d_eq = direct_eq_vals.get(p)
        if d_eq is not None:
            equity_map[p] = float(d_eq)
        else:
            # B. Both Equity Capital AND Reserves must be present (not None)
            c_val = eq_cap_vals.get(p)
            r_val = res_vals.get(p)
            if c_val is not None and r_val is not None:
                equity_map[p] = float(c_val) + float(r_val)
            else:
                equity_map[p] = None
            
        # C. Total Assets: Direct Total Assets/Liabilities only
        direct_a = tot_assets_vals.get(p)
        if direct_a is not None and direct_a > 0:
            assets_map[p] = float(direct_a)
        else:
            assets_map[p] = None

    # Resolve Truth-Aware PAT for latest PL period
    pat_facts_map: Dict[str, Any] = {}
    for p in pl_annual_periods:
        pat_fact = resolver.resolve_annual_fact("NET_PROFIT", p)
        pat_facts_map[p] = pat_fact

    # -------------------------------------------------------------------------
    # A. Deposit Growth (YoY & 3Y CAGR)
    # -------------------------------------------------------------------------
    dep_growth_yoy: Optional[float] = None
    dep_growth_3yr: Optional[float] = None
    
    if bs_annual_periods:
        curr_p = bs_annual_periods[-1]
        curr_yr = parse_period_year(curr_p)
        curr_dep = dep_vals.get(curr_p)
        
        # YoY: exact prior completed FY
        prior_p = next((p for p in reversed(bs_annual_periods[:-1]) if curr_yr - parse_period_year(p) == 1), None)
        if prior_p:
            prior_dep = dep_vals.get(prior_p)
            if (curr_dep is not None) and (prior_dep is not None and prior_dep > 0):
                dep_growth_yoy = round(((curr_dep - prior_dep) / prior_dep) * 100.0, 1)
                provenance["deposit_growth_yoy"] = {
                    "formula": "((Deposits_Latest / Deposits_Prior) - 1) * 100",
                    "latest_period": curr_p,
                    "prior_period": prior_p,
                    "latest_value": curr_dep,
                    "prior_value": prior_dep,
                    "source": "Screener.in Standardized Balance Sheet",
                    "verification_status": "STANDARDIZED"
                }
            else:
                unavailable_reasons["deposit_growth_yoy"] = "Prior-year completed annual deposit data is missing or zero"
        else:
            unavailable_reasons["deposit_growth_yoy"] = "Exact consecutive prior-year completed annual deposit period unavailable"
            
        # 3Y CAGR: exact 3-year prior completed FY
        base_p = next((p for p in reversed(bs_annual_periods[:-1]) if curr_yr - parse_period_year(p) == 3), None)
        if base_p:
            base_dep = dep_vals.get(base_p)
            if (curr_dep is not None and curr_dep > 0) and (base_dep is not None and base_dep > 0):
                dep_growth_3yr = round(((curr_dep / base_dep) ** (1.0 / 3.0) - 1.0) * 100.0, 1)
                provenance["deposit_growth_3yr"] = {
                    "formula": "((Deposits_Latest / Deposits_3Y_Base) ^ (1/3) - 1) * 100",
                    "latest_period": curr_p,
                    "base_period": base_p,
                    "latest_value": curr_dep,
                    "base_value": base_dep,
                    "source": "Screener.in Standardized Balance Sheet",
                    "verification_status": "STANDARDIZED"
                }
            else:
                unavailable_reasons["deposit_growth_3yr"] = "3Y base deposit value is missing or non-positive"
        else:
            unavailable_reasons["deposit_growth_3yr"] = "Exact 3-year prior completed annual deposit period unavailable"

    # -------------------------------------------------------------------------
    # B. Advances / Loan Book Growth (YoY & 3Y CAGR)
    # -------------------------------------------------------------------------
    adv_growth_yoy: Optional[float] = None
    adv_growth_3yr: Optional[float] = None
    
    if bs_annual_periods:
        curr_p = bs_annual_periods[-1]
        curr_yr = parse_period_year(curr_p)
        curr_adv = adv_vals.get(curr_p)
        
        # YoY: exact prior completed FY
        prior_p = next((p for p in reversed(bs_annual_periods[:-1]) if curr_yr - parse_period_year(p) == 1), None)
        if prior_p:
            prior_adv = adv_vals.get(prior_p)
            if (curr_adv is not None) and (prior_adv is not None and prior_adv > 0):
                adv_growth_yoy = round(((curr_adv - prior_adv) / prior_adv) * 100.0, 1)
                provenance["advances_growth_yoy"] = {
                    "formula": "((Advances_Latest / Advances_Prior) - 1) * 100",
                    "latest_period": curr_p,
                    "prior_period": prior_p,
                    "latest_value": curr_adv,
                    "prior_value": prior_adv,
                    "source": "Screener.in Standardized Balance Sheet",
                    "verification_status": "STANDARDIZED"
                }
            else:
                unavailable_reasons["advances_growth_yoy"] = "Prior-year completed annual advances data is missing or zero"
        else:
            unavailable_reasons["advances_growth_yoy"] = "Exact consecutive prior-year completed annual advances period unavailable"

        # 3Y CAGR: exact 3-year prior completed FY
        base_p = next((p for p in reversed(bs_annual_periods[:-1]) if curr_yr - parse_period_year(p) == 3), None)
        if base_p:
            base_adv = adv_vals.get(base_p)
            if (curr_adv is not None and curr_adv > 0) and (base_adv is not None and base_adv > 0):
                adv_growth_3yr = round(((curr_adv / base_adv) ** (1.0 / 3.0) - 1.0) * 100.0, 1)
                provenance["advances_growth_3yr"] = {
                    "formula": "((Advances_Latest / Advances_3Y_Base) ^ (1/3) - 1) * 100",
                    "latest_period": curr_p,
                    "base_period": base_p,
                    "latest_value": curr_adv,
                    "base_value": base_adv,
                    "source": "Screener.in Standardized Balance Sheet",
                    "verification_status": "STANDARDIZED"
                }
            else:
                unavailable_reasons["advances_growth_3yr"] = "3Y base advances value is missing or non-positive"
        else:
            unavailable_reasons["advances_growth_3yr"] = "Exact 3-year prior completed annual advances period unavailable"

    # -------------------------------------------------------------------------
    # C. Credit-to-Deposit (CD) Ratio
    # -------------------------------------------------------------------------
    cd_ratio: Optional[float] = None
    if latest_bs_period:
        latest_adv = adv_vals.get(latest_bs_period)
        latest_dep = dep_vals.get(latest_bs_period)
        if (latest_adv is not None) and (latest_dep is not None and latest_dep > 0):
            cd_ratio = round((latest_adv / latest_dep) * 100.0, 1)
            provenance["credit_deposit_ratio"] = {
                "formula": "(Advances / Deposits) * 100",
                "period": latest_bs_period,
                "advances_cr": latest_adv,
                "deposits_cr": latest_dep,
                "source": "Screener.in Standardized Balance Sheet",
                "verification_status": "STANDARDIZED"
            }
        else:
            unavailable_reasons["credit_deposit_ratio"] = "Deposits or Advances missing or Deposits is zero"

    # -------------------------------------------------------------------------
    # D. Return on Assets (ROA %) — Uses Average Total Assets
    # -------------------------------------------------------------------------
    roa_pct: Optional[float] = None
    if len(bs_annual_periods) >= 2 and latest_pl_period:
        curr_bs_p = bs_annual_periods[-1]
        prior_bs_p = bs_annual_periods[-2]
        curr_yr = parse_period_year(curr_bs_p)
        prior_yr = parse_period_year(prior_bs_p)
        pl_yr = parse_period_year(latest_pl_period)
        
        pat_fact = pat_facts_map.get(latest_pl_period)
        curr_pat = pat_fact.value if pat_fact else None
        curr_assets = assets_map.get(curr_bs_p)
        prior_assets = assets_map.get(prior_bs_p)
        
        if (
            (curr_yr == pl_yr) and 
            (curr_yr - prior_yr == 1) and 
            (curr_pat is not None) and 
            (curr_assets is not None and curr_assets > 0) and 
            (prior_assets is not None and prior_assets > 0)
        ):
            avg_assets = (curr_assets + prior_assets) / 2.0
            roa_pct = round((curr_pat / avg_assets) * 100.0, 2)
            provenance["roa"] = {
                "formula": "(PAT / Average_Total_Assets) * 100",
                "pat_period": latest_pl_period,
                "pat_cr": curr_pat,
                "pat_source": pat_fact.selected_source_name if (pat_fact and pat_fact.selected_source_name) else (pat_fact.source_type if pat_fact else "P&L"),
                "pat_verification_status": pat_fact.verification_status if pat_fact else "STANDARDIZED",
                "assets_latest_period": curr_bs_p,
                "assets_latest_cr": curr_assets,
                "assets_prior_period": prior_bs_p,
                "assets_prior_cr": prior_assets,
                "avg_assets_cr": avg_assets,
                "source": "Balance Sheet & P&L"
            }
        else:
            unavailable_reasons["roa"] = "ROA requires exact matching completed FY PAT and direct consecutive 2-year average Total Assets"
    else:
        unavailable_reasons["roa"] = "Fewer than 2 completed annual balance sheet periods or direct Total Assets unavailable"

    # -------------------------------------------------------------------------
    # E. Return on Equity (ROE %) — Uses Average Shareholder Equity
    # -------------------------------------------------------------------------
    roe_pct: Optional[float] = None
    if len(bs_annual_periods) >= 2 and latest_pl_period:
        curr_bs_p = bs_annual_periods[-1]
        prior_bs_p = bs_annual_periods[-2]
        curr_yr = parse_period_year(curr_bs_p)
        prior_yr = parse_period_year(prior_bs_p)
        pl_yr = parse_period_year(latest_pl_period)
        
        pat_fact = pat_facts_map.get(latest_pl_period)
        curr_pat = pat_fact.value if pat_fact else None
        curr_eq = equity_map.get(curr_bs_p)
        prior_eq = equity_map.get(prior_bs_p)
        
        if (
            (curr_yr == pl_yr) and 
            (curr_yr - prior_yr == 1) and 
            (curr_pat is not None) and 
            (curr_eq is not None and curr_eq > 0) and 
            (prior_eq is not None and prior_eq > 0)
        ):
            avg_eq = (curr_eq + prior_eq) / 2.0
            roe_pct = round((curr_pat / avg_eq) * 100.0, 2)
            provenance["roe"] = {
                "formula": "(PAT / Average_Shareholder_Equity) * 100",
                "pat_period": latest_pl_period,
                "pat_cr": curr_pat,
                "pat_source": pat_fact.selected_source_name if (pat_fact and pat_fact.selected_source_name) else (pat_fact.source_type if pat_fact else "P&L"),
                "pat_verification_status": pat_fact.verification_status if pat_fact else "STANDARDIZED",
                "equity_latest_period": curr_bs_p,
                "equity_latest_cr": curr_eq,
                "equity_prior_period": prior_bs_p,
                "equity_prior_cr": prior_eq,
                "avg_equity_cr": avg_eq,
                "source": "Balance Sheet & P&L"
            }
        else:
            unavailable_reasons["roe"] = "ROE requires exact matching completed FY PAT and consecutive 2-year average Shareholder Equity"
    else:
        unavailable_reasons["roe"] = "Fewer than 2 completed annual balance sheet periods available"

    # -------------------------------------------------------------------------
    # F. Gross NPA % and Net NPA % (Standardized / Canonical)
    # -------------------------------------------------------------------------
    gross_npa: Optional[float] = None
    net_npa: Optional[float] = None
    
    # Check latest quarterly period first, then P&L/BS
    q_periods = quarters.periods if (quarters and quarters.periods) else []
    latest_q_p = q_periods[-1] if q_periods else None
    
    if latest_q_p and gnpa_q_vals.get(latest_q_p) is not None:
        gross_npa = float(gnpa_q_vals[latest_q_p])
        provenance["gross_npa"] = {"period": latest_q_p, "source": "Quarterly Statement", "value": gross_npa, "verification_status": "STANDARDIZED"}
    elif latest_pl_period and gnpa_pl_vals.get(latest_pl_period) is not None:
        gross_npa = float(gnpa_pl_vals[latest_pl_period])
        provenance["gross_npa"] = {"period": latest_pl_period, "source": "Annual P&L", "value": gross_npa, "verification_status": "STANDARDIZED"}
    else:
        unavailable_reasons["gross_npa"] = "Gross NPA % row not found in current source statements"

    if latest_q_p and nnpa_q_vals.get(latest_q_p) is not None:
        net_npa = float(nnpa_q_vals[latest_q_p])
        provenance["net_npa"] = {"period": latest_q_p, "source": "Quarterly Statement", "value": net_npa, "verification_status": "STANDARDIZED"}
    elif latest_pl_period and nnpa_pl_vals.get(latest_pl_period) is not None:
        net_npa = float(nnpa_pl_vals[latest_pl_period])
        provenance["net_npa"] = {"period": latest_pl_period, "source": "Annual P&L", "value": net_npa, "verification_status": "STANDARDIZED"}
    else:
        unavailable_reasons["net_npa"] = "Net NPA % row not found in current source statements"

    # -------------------------------------------------------------------------
    # G. Credit Cost % — Provisions / Average Gross Advances
    # -------------------------------------------------------------------------
    credit_cost_pct: Optional[float] = None
    if len(bs_annual_periods) >= 2 and latest_pl_period:
        curr_bs_p = bs_annual_periods[-1]
        prior_bs_p = bs_annual_periods[-2]
        curr_yr = parse_period_year(curr_bs_p)
        prior_yr = parse_period_year(prior_bs_p)
        pl_yr = parse_period_year(latest_pl_period)
        
        curr_prov = prov_vals.get(latest_pl_period)
        curr_adv = adv_vals.get(curr_bs_p)
        prior_adv = adv_vals.get(prior_bs_p)
        
        if (
            (curr_yr == pl_yr) and 
            (curr_yr - prior_yr == 1) and 
            (curr_prov is not None) and 
            (curr_adv is not None and curr_adv > 0) and 
            (prior_adv is not None and prior_adv > 0)
        ):
            avg_adv = (curr_adv + prior_adv) / 2.0
            credit_cost_pct = round((curr_prov / avg_adv) * 100.0, 2)
            provenance["credit_cost"] = {
                "formula": "(Provisions / Average_Gross_Advances) * 100",
                "provisions_period": latest_pl_period,
                "provisions_cr": curr_prov,
                "advances_latest_period": curr_bs_p,
                "advances_latest_cr": curr_adv,
                "advances_prior_period": prior_bs_p,
                "advances_prior_cr": prior_adv,
                "avg_advances_cr": avg_adv,
                "source": "P&L Provisions and Balance Sheet Advances",
                "verification_status": "STANDARDIZED"
            }
        else:
            unavailable_reasons["credit_cost"] = "Credit cost requires exact Provisions and consecutive 2-year average Gross Advances"
    else:
        unavailable_reasons["credit_cost"] = "Provisions or consecutive balance sheet advances unavailable"

    # -------------------------------------------------------------------------
    # H. Cost-to-Income Ratio % (Strictly Fail-Closed on Ambiguous Rows)
    # -------------------------------------------------------------------------
    cost_to_income_pct: Optional[float] = None
    if latest_pl_period:
        # Check for explicit bank operating expenses (Total OpEx only)
        op_exp = op_exp_vals.get(latest_pl_period)
        
        # Net Income requires BOTH NII and Other Income, or ALL THREE IE, IX, Other Income (missing != 0.0)
        net_inc = None
        oth = other_inc_vals.get(latest_pl_period)
        nii = nii_vals.get(latest_pl_period)
        ie = int_earned_vals.get(latest_pl_period)
        ix = int_exp_vals.get(latest_pl_period)
        
        if (nii is not None) and (oth is not None):
            net_inc = nii + oth
        elif (ie is not None) and (ix is not None) and (oth is not None):
            net_inc = (ie - ix) + oth

        if (op_exp is not None and op_exp >= 0) and (net_inc is not None and net_inc > 0):
            cost_to_income_pct = round((op_exp / net_inc) * 100.0, 1)
            provenance["cost_to_income"] = {
                "formula": "(Operating_Expenses / Total_Net_Income) * 100",
                "period": latest_pl_period,
                "operating_expenses_cr": op_exp,
                "total_net_income_cr": net_inc,
                "source": "P&L Bank Operating Expenses & Net Income",
                "verification_status": "STANDARDIZED"
            }
        else:
            unavailable_reasons["cost_to_income"] = "Cost-to-income requires explicit Operating Expenses and Net Income line items in source statement"
    else:
        unavailable_reasons["cost_to_income"] = "Annual P&L statement unavailable"

    # -------------------------------------------------------------------------
    # I. Build Multi-Year Historical Bank Trends
    # -------------------------------------------------------------------------
    trends: List[BankTrendItem] = []
    
    # Iterate through all completed annual balance sheet periods
    for i, p in enumerate(bs_annual_periods):
        p_dep = dep_vals.get(p)
        p_adv = adv_vals.get(p)
        p_bor = bor_vals.get(p)
        p_eq = equity_map.get(p)
        p_assets = assets_map.get(p)
        
        pat_f = pat_facts_map.get(p)
        p_pat = pat_f.value if pat_f else None
        
        p_prov = prov_vals.get(p)
        p_op_exp = op_exp_vals.get(p)
        
        p_gnpa = gnpa_pl_vals.get(p)
        p_nnpa = nnpa_pl_vals.get(p)
        
        # CD Ratio
        p_cd = round((p_adv / p_dep) * 100.0, 1) if (p_adv is not None and p_dep is not None and p_dep > 0) else None
        
        # ROA, ROE, Credit Cost require prior year completed FY
        p_roa = None
        p_roe = None
        p_credit_cost = None
        
        if i > 0:
            prior_p = bs_annual_periods[i - 1]
            if parse_period_year(p) - parse_period_year(prior_p) == 1:
                prior_assets = assets_map.get(prior_p)
                prior_eq = equity_map.get(prior_p)
                prior_adv = adv_vals.get(prior_p)
                
                if (p_pat is not None) and (p_assets is not None and p_assets > 0) and (prior_assets is not None and prior_assets > 0):
                    avg_a = (p_assets + prior_assets) / 2.0
                    p_roa = round((p_pat / avg_a) * 100.0, 2)
                    
                if (p_pat is not None) and (p_eq is not None and p_eq > 0) and (prior_eq is not None and prior_eq > 0):
                    avg_e = (p_eq + prior_eq) / 2.0
                    p_roe = round((p_pat / avg_e) * 100.0, 2)
                    
                if (p_prov is not None) and (p_adv is not None and p_adv > 0) and (prior_adv is not None and prior_adv > 0):
                    avg_ad = (p_adv + prior_adv) / 2.0
                    p_credit_cost = round((p_prov / avg_ad) * 100.0, 2)
                    
        # Multi-period Cost-to-income
        p_c2i = None
        p_oth = other_inc_vals.get(p)
        p_nii = nii_vals.get(p)
        p_ie = int_earned_vals.get(p)
        p_ix = int_exp_vals.get(p)
        
        if p_op_exp is not None and p_op_exp >= 0:
            if (p_nii is not None) and (p_oth is not None):
                tot_net = p_nii + p_oth
                if tot_net > 0:
                    p_c2i = round((p_op_exp / tot_net) * 100.0, 1)
            elif (p_ie is not None) and (p_ix is not None) and (p_oth is not None):
                tot_net = (p_ie - p_ix) + p_oth
                if tot_net > 0:
                    p_c2i = round((p_op_exp / tot_net) * 100.0, 1)
        
        trends.append(BankTrendItem(
            period=p,
            deposits_cr=p_dep,
            advances_cr=p_adv,
            borrowings_cr=p_bor,
            cd_ratio_pct=p_cd,
            pat_cr=p_pat,
            total_assets_cr=p_assets,
            total_equity_cr=p_eq,
            roa_pct=p_roa,
            roe_pct=p_roe,
            gross_npa_pct=p_gnpa,
            net_npa_pct=p_nnpa,
            credit_cost_pct=p_credit_cost,
            cost_to_income_pct=p_c2i
        ))

    return BankAnalytics(
        applicability="applicable",
        latest_period=latest_bs_period or latest_pl_period,
        deposit_growth_yoy_pct=dep_growth_yoy,
        deposit_growth_3yr_cagr_pct=dep_growth_3yr,
        advances_growth_yoy_pct=adv_growth_yoy,
        advances_growth_3yr_cagr_pct=adv_growth_3yr,
        credit_deposit_ratio_pct=cd_ratio,
        roa_pct=roa_pct,
        roe_pct=roe_pct,
        gross_npa_pct=gross_npa,
        net_npa_pct=net_npa,
        cost_to_income_pct=cost_to_income_pct,
        credit_cost_pct=credit_cost_pct,
        trends=trends,
        provenance=provenance,
        unavailable_reasons=unavailable_reasons
    )
