import os
import json
import re
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

from doc_intelligence_models import (
    CompanyDocumentIntelligence, BusinessAnalysisResult, PromiseVsDeliveryItem,
    GrowthDriver, DemandMomentum, RisksAndCashIssues, StockerView, RecentChange,
    DocumentEvidenceItem, ManagementGuidanceItem
)

DOC_INTEL_GENERATED_DIR = Path(__file__).parent / "data" / "doc_intelligence_generated"
DOC_INTEL_BASELINE_DIR = Path(__file__).parent / "data" / "doc_intelligence"

import database

def get_company_doc_intelligence(
    symbol: str, 
    financial_analytics: Optional[Dict[str, Any]] = None,
    include_document_summaries: bool = True,
    current_docs: Optional[List[Any]] = None
) -> Optional[CompanyDocumentIntelligence]:
    clean_sym = symbol.upper().strip()
    
    # Priority 1: Check SQLite database cache
    db_data = database.get_cached_ai_analysis(clean_sym)
    if db_data and (db_data.get("promise_vs_delivery") or db_data.get("growth_drivers") or db_data.get("plan_vs_reality") or db_data.get("evidence_items")):
        try:
            if include_document_summaries:
                doc_sums = database.get_document_summaries(clean_sym)
                if doc_sums and not db_data.get("document_summaries"):
                    db_data["document_summaries"] = list(doc_sums.values())
            else:
                db_data["document_summaries"] = []
                
            # Populate persistent evidence and guidance items from tables if empty in JSON
            if not db_data.get("evidence_items"):
                ev_items = database.get_document_evidence_items(clean_sym)
                if ev_items:
                    db_data["evidence_items"] = ev_items
            if not db_data.get("management_guidance_items"):
                mg_items = database.get_management_guidance_items(clean_sym)
                if mg_items:
                    db_data["management_guidance_items"] = mg_items
                    
            if current_docs is not None:
                is_stale, stale_reason = database.check_business_analysis_staleness(clean_sym, current_docs=current_docs)
                if is_stale and stale_reason != "not_analyzed":
                    db_data["staleness_status"] = "stale"
                else:
                    db_data["staleness_status"] = "fresh"
            else:
                if not db_data.get("staleness_status"):
                    db_data["staleness_status"] = "not_checked"

            doc_intel = CompanyDocumentIntelligence(**db_data)
            _apply_financial_cross_check(doc_intel, financial_analytics)
            return doc_intel
        except Exception as e:
            print(f"Notice: Could not parse SQLite intelligence for {clean_sym}: {e}")

    # Priority 2: Check JSON file cache in doc_intelligence_generated
    gen_path = DOC_INTEL_GENERATED_DIR / f"{clean_sym}.json"
    if gen_path.exists():
        try:
            with open(gen_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("status") != "ai_unavailable" and (data.get("promise_vs_delivery") or data.get("growth_drivers") or data.get("plan_vs_reality") or data.get("evidence_items")):
                if include_document_summaries:
                    doc_sums = database.get_document_summaries(clean_sym)
                    if doc_sums and not data.get("document_summaries"):
                        data["document_summaries"] = list(doc_sums.values())
                else:
                    data["document_summaries"] = []
                doc_intel = CompanyDocumentIntelligence(**data)
                _apply_financial_cross_check(doc_intel, financial_analytics)
                return doc_intel
        except Exception as e:
            print(f"Notice: Could not load generated intelligence for {clean_sym}: {e}")
            
    # If not yet generated, return None (NO mock sample fallback!)
    return None

def _normalize_metric_key(m: str) -> str:
    return re.sub(r'[^a-z0-9% ]+', '', str(m).lower().strip())

def _extract_metric_from_statement(stmt_data: Any, canonical_aliases: List[str], target_period: str) -> Optional[float]:
    if not stmt_data:
        return None
        
    periods = []
    rows = []
    if isinstance(stmt_data, dict):
        periods = stmt_data.get("periods") or stmt_data.get("years") or []
        rows = stmt_data.get("rows") or []
    elif hasattr(stmt_data, "periods") and hasattr(stmt_data, "rows"):
        periods = stmt_data.periods
        rows = stmt_data.rows

    if not periods or not rows:
        return None

    # Match target period
    target_clean = target_period.upper().strip()
    matched_period = None
    for p in periods:
        p_clean = str(p).upper().strip()
        if p_clean == target_clean or target_clean in p_clean or p_clean in target_clean:
            matched_period = p
            break
            
    if not matched_period:
        # Try matching year digits (e.g. FY26 vs 2026 or Mar 2026)
        yr_m = re.search(r'(?:FY|20)?(\d{2,4})', target_clean)
        if yr_m:
            yr_str = yr_m.group(1)
            if len(yr_str) == 2:
                yr_str = "20" + yr_str
            for p in periods:
                if yr_str in str(p):
                    matched_period = p
                    break
                    
    if not matched_period:
        return None

    # Search rows for exact or strict canonical aliases (avoiding loose prefix matching)
    norm_aliases = [_normalize_metric_key(a) for a in canonical_aliases]
    for r in rows:
        if isinstance(r, dict):
            m_name = r.get("metric", "")
            vals = r.get("values", {})
        else:
            m_name = getattr(r, "metric", "")
            vals = getattr(r, "values", {})
            
        m_norm = _normalize_metric_key(str(m_name))
        for a_norm in norm_aliases:
            if m_norm == a_norm or m_norm in [a_norm + " %", a_norm + "%"] or a_norm in [m_norm + " %", m_norm + "%"]:
                if isinstance(vals, dict):
                    val = vals.get(matched_period)
                    if isinstance(val, (int, float)):
                        return float(val)
                elif isinstance(vals, list) and matched_period in periods:
                    idx = periods.index(matched_period)
                    if idx < len(vals) and isinstance(vals[idx], (int, float)):
                        return float(vals[idx])
    return None

CANONICAL_METRIC_DEFINITIONS = {
    "REVENUE": {
        "topic_keywords": ["revenue", "sales", "topline", "turnover"],
        "statement_metrics": ["sales", "revenue", "revenue from operations", "total revenue", "total income", "interest earned"],
        "source_stmt": "pl",
        "is_lower_better": False
    },
    "OPM": {
        "topic_keywords": ["opm", "operating profit margin", "ebitda margin", "operating margin"],
        "statement_metrics": ["opm", "opm %", "operating profit margin", "ebitda margin", "ebitda margin %"],
        "source_stmt": "pl",
        "is_lower_better": False
    },
    "NET_PROFIT": {
        "topic_keywords": ["net profit", "pat", "profit after tax", "bottomline"],
        "statement_metrics": ["net profit", "pat", "profit after tax"],
        "source_stmt": "pl",
        "is_lower_better": False
    },
    "CAPEX": {
        "topic_keywords": ["capex", "capital expenditure", "capital investment"],
        "statement_metrics": ["fixed assets purchased", "capital expenditure", "capex"],
        "source_stmt": "cf",
        "is_lower_better": False
    },
    "ADVANCES": {
        "topic_keywords": ["advances", "loan book", "loans & advances", "loans and advances", "loan growth", "gross advances", "total advances"],
        "statement_metrics": ["advances", "loans & advances", "loans and advances", "total advances"],
        "source_stmt": "bs",
        "is_lower_better": False
    },
    "DEPOSITS": {
        "topic_keywords": ["deposits", "deposit growth", "total deposits"],
        "statement_metrics": ["deposits", "total deposits"],
        "source_stmt": "bs",
        "is_lower_better": False
    },
    "CASA_RATIO": {
        "topic_keywords": ["casa", "casa ratio", "casa %", "current and savings"],
        "statement_metrics": ["casa %", "casa ratio", "casa percentage", "casa"],
        "source_stmt": "pl",
        "is_lower_better": False
    },
    "GNPA": {
        "topic_keywords": ["gnpa", "gross npa", "gross non performing", "gross non-performing"],
        "statement_metrics": ["gnpa %", "gross npa %", "gnpa", "gross npa"],
        "source_stmt": "pl",
        "is_lower_better": True
    },
    "NNPA": {
        "topic_keywords": ["nnpa", "net npa", "net non performing", "net non-performing"],
        "statement_metrics": ["nnpa %", "net npa %", "nnpa", "net npa"],
        "source_stmt": "pl",
        "is_lower_better": True
    },
    "COST_TO_INCOME": {
        "topic_keywords": ["cost to income", "cost-to-income", "cost/income"],
        "statement_metrics": ["cost to income %", "cost to income"],
        "source_stmt": "pl",
        "is_lower_better": True
    },
    "CREDIT_COST": {
        "topic_keywords": ["credit cost", "credit costs"],
        "statement_metrics": ["credit cost %", "credit cost"],
        "source_stmt": "pl",
        "is_lower_better": True
    }
}

def evaluate_management_guidance_vs_actual(
    guidance_items: List[ManagementGuidanceItem],
    financial_statements: Optional[Dict[str, Any]] = None,
    knowledge_facts: Optional[List[Dict[str, Any]]] = None,
    business_model: str = "GENERAL_CORPORATE"
) -> List[ManagementGuidanceItem]:
    """
    Deterministically compares management guidance targets against actual financial statements
    or verified knowledge facts without LLM arithmetic or invented policy thresholds.
    Assigns: MET, MISSED, NOT_YET_DUE, NOT_COMPARABLE, INSUFFICIENT_EVIDENCE.
    """
    if not guidance_items:
        return []
    
    pl_stmt = financial_statements.get("profit_loss") or financial_statements.get("profit_and_loss") if financial_statements else None
    quarters_stmt = financial_statements.get("quarters") if financial_statements else None
    bs_stmt = financial_statements.get("balance_sheet") if financial_statements else None
    cf_stmt = financial_statements.get("cash_flow") or financial_statements.get("cash_flows") if financial_statements else None
    
    # Determine latest completed period in statements
    latest_pl_period = None
    if pl_stmt:
        if hasattr(pl_stmt, "periods") and pl_stmt.periods:
            latest_pl_period = pl_stmt.periods[-1]
        elif isinstance(pl_stmt, dict) and pl_stmt.get("periods"):
            latest_pl_period = pl_stmt["periods"][-1]
        elif isinstance(pl_stmt, dict) and pl_stmt.get("years"):
            latest_pl_period = pl_stmt["years"][-1]
            
    evaluated_items: List[ManagementGuidanceItem] = []
    
    for g in guidance_items:
        item = g.model_copy()
        topic = (item.metric_or_topic or "").lower()
        target_p = item.target_period or ""
        
        # 1. Source-First Fail-Closed Check
        if getattr(item, "source_support_status", "SUPPORTED") == "UNSUPPORTED" or not item.source_document_title:
            item.status = "INSUFFICIENT_EVIDENCE"
            item.confidence = "LOW"
            item.comparison_detail = "Unverified source filing; guidance cannot be verified against actuals."
            evaluated_items.append(item)
            continue

        # 2. Check if target period is in the future
        target_yr_match = re.search(r'(?:FY|20)(\d{2,4})', target_p, re.IGNORECASE)
        latest_yr_match = re.search(r'(?:FY|20)(\d{2,4})', str(latest_pl_period), re.IGNORECASE) if latest_pl_period else None
        
        is_future = False
        if target_yr_match and latest_yr_match:
            try:
                t_yr = int(target_yr_match.group(1))
                if t_yr < 100: t_yr += 2000
                l_yr = int(latest_yr_match.group(1))
                if l_yr < 100: l_yr += 2000
                if t_yr > l_yr:
                    is_future = True
            except Exception:
                pass
                
        if is_future:
            item.status = "NOT_YET_DUE"
            item.comparison_detail = f"Target period ({target_p}) is forward-looking and has not yet been reported."
            evaluated_items.append(item)
            continue
            
        # 3. Canonical Metric Resolution
        matched_canonical = None
        for c_key, c_def in CANONICAL_METRIC_DEFINITIONS.items():
            if any(k in topic for k in c_def["topic_keywords"]):
                matched_canonical = c_def
                break
                
        actual_val = None
        actual_period = target_p
        is_lower_better = matched_canonical["is_lower_better"] if matched_canonical else False
        
        if matched_canonical:
            src = matched_canonical.get("source_stmt", "pl")
            if src == "pl":
                actual_val = _extract_metric_from_statement(pl_stmt, matched_canonical["statement_metrics"], target_p)
                if actual_val is None and quarters_stmt:
                    actual_val = _extract_metric_from_statement(quarters_stmt, matched_canonical["statement_metrics"], target_p)
                if actual_val is None and bs_stmt:
                    actual_val = _extract_metric_from_statement(bs_stmt, matched_canonical["statement_metrics"], target_p)
            elif src == "bs":
                actual_val = _extract_metric_from_statement(bs_stmt, matched_canonical["statement_metrics"], target_p)
            elif src == "cf":
                actual_val = _extract_metric_from_statement(cf_stmt, matched_canonical["statement_metrics"], target_p)

        # 4. Check knowledge facts if statement extraction did not find exact match
        if actual_val is None and knowledge_facts:
            for kf in knowledge_facts:
                kf_metric = str(kf.get("metric_name", "")).lower()
                kf_period = str(kf.get("period_or_date", "")).lower()
                if matched_canonical and any(m in kf_metric for m in matched_canonical["statement_metrics"]) and (target_p.lower() in kf_period or kf_period in target_p.lower()):
                    if kf.get("numeric_value") is not None:
                        actual_val = float(kf["numeric_value"])
                        actual_period = kf.get("period_or_date", target_p)
                        break

        target_num = item.quantified_value
        r_min = item.quantified_range_min
        r_max = item.quantified_range_max

        # 5. Objective Deterministic Comparison (No invented percentage thresholds)
        if actual_val is not None:
            item.actual_reported_value = actual_val
            item.actual_reported_period = actual_period
            item.actual_reported_source = "Financial Statement Data"
            
            if target_num is not None:
                variance = round(actual_val - target_num, 2)
                pct_var = round(((actual_val - target_num) / abs(target_num)) * 100.0, 2) if target_num != 0 else 0.0
                
                if is_lower_better:
                    if actual_val <= target_num:
                        item.status = "MET"
                        item.comparison_detail = f"Actual {actual_val} {item.unit or ''} achieved target (target <= {target_num} {item.unit or ''}, variance: {variance:+} {item.unit or ''}) in {actual_period}."
                    else:
                        item.status = "MISSED"
                        item.comparison_detail = f"Actual {actual_val} {item.unit or ''} missed target (target <= {target_num} {item.unit or ''}, variance: {variance:+} {item.unit or ''}) in {actual_period}."
                else:
                    if actual_val >= target_num:
                        item.status = "MET"
                        item.comparison_detail = f"Actual {actual_val} {item.unit or ''} met target {target_num} {item.unit or ''} (variance: {variance:+} {item.unit or ''}, {pct_var:+}% ) in {actual_period}."
                    else:
                        item.status = "MISSED"
                        item.comparison_detail = f"Actual {actual_val} {item.unit or ''} missed target {target_num} {item.unit or ''} (variance: {variance:+} {item.unit or ''}, {pct_var:+}% ) in {actual_period}."
                        
            elif r_min is not None or r_max is not None:
                if r_min is not None and r_max is not None:
                    if is_lower_better:
                        if actual_val <= r_max:
                            item.status = "MET"
                            item.comparison_detail = f"Actual {actual_val} {item.unit or ''} achieved guided range {r_min}–{r_max} {item.unit or ''} in {actual_period}."
                        else:
                            item.status = "MISSED"
                            item.comparison_detail = f"Actual {actual_val} {item.unit or ''} missed guided range {r_min}–{r_max} {item.unit or ''} in {actual_period}."
                    else:
                        if actual_val >= r_min and (r_max is None or actual_val <= r_max):
                            item.status = "MET"
                            item.comparison_detail = f"Actual {actual_val} {item.unit or ''} fell within guided range {r_min}–{r_max} {item.unit or ''} in {actual_period}."
                        elif actual_val > r_max:
                            item.status = "MET"
                            item.comparison_detail = f"Actual {actual_val} {item.unit or ''} exceeded guided range {r_min}–{r_max} {item.unit or ''} in {actual_period}."
                        else:
                            item.status = "MISSED"
                            item.comparison_detail = f"Actual {actual_val} {item.unit or ''} missed guided range {r_min}–{r_max} {item.unit or ''} in {actual_period}."
                elif r_min is not None:
                    if is_lower_better:
                        if actual_val <= r_min:
                            item.status = "MET"
                            item.comparison_detail = f"Actual {actual_val} {item.unit or ''} achieved guided ceiling <= {r_min} {item.unit or ''} in {actual_period}."
                        else:
                            item.status = "MISSED"
                            item.comparison_detail = f"Actual {actual_val} {item.unit or ''} exceeded guided ceiling <= {r_min} {item.unit or ''} in {actual_period}."
                    else:
                        if actual_val >= r_min:
                            item.status = "MET"
                            item.comparison_detail = f"Actual {actual_val} {item.unit or ''} met guided floor >= {r_min} {item.unit or ''} in {actual_period}."
                        else:
                            item.status = "MISSED"
                            item.comparison_detail = f"Actual {actual_val} {item.unit or ''} missed guided floor >= {r_min} {item.unit or ''} in {actual_period}."
                elif r_max is not None:
                    if is_lower_better:
                        if actual_val <= r_max:
                            item.status = "MET"
                            item.comparison_detail = f"Actual {actual_val} {item.unit or ''} achieved guided ceiling <= {r_max} {item.unit or ''} in {actual_period}."
                        else:
                            item.status = "MISSED"
                            item.comparison_detail = f"Actual {actual_val} {item.unit or ''} exceeded guided ceiling <= {r_max} {item.unit or ''} in {actual_period}."
                    else:
                        if actual_val >= r_max:
                            item.status = "MET"
                            item.comparison_detail = f"Actual {actual_val} {item.unit or ''} met guided target {r_max} {item.unit or ''} in {actual_period}."
                        else:
                            item.status = "MISSED"
                            item.comparison_detail = f"Actual {actual_val} {item.unit or ''} missed guided target {r_max} {item.unit or ''} in {actual_period}."
            else:
                item.status = "NOT_COMPARABLE"
                item.comparison_detail = "Qualitative commentary without quantified metric target."
        else:
            if not target_num and r_min is None and r_max is None:
                item.status = "NOT_COMPARABLE"
                item.comparison_detail = "Qualitative commentary without quantified metric target."
            else:
                item.status = "INSUFFICIENT_EVIDENCE"
                item.comparison_detail = f"Financial statements do not contain exact line-item disclosure for '{item.metric_or_topic}' in period '{target_p}'."
                
        evaluated_items.append(item)
        
    return evaluated_items

def _apply_financial_cross_check(doc_intel: CompanyDocumentIntelligence, financial_analytics: Optional[Dict[str, Any]]) -> None:
    """Enriches document intelligence with deterministic financial analytics in a sector-aware manner."""
    if not financial_analytics:
        return
        
    biz_model = financial_analytics.get("business_model") or "GENERAL_CORPORATE"
    is_bank = (biz_model == "BANK")
    is_financial = biz_model in ("BANK", "NBFC_LENDER", "INSURANCE", "OTHER_FINANCIAL")
    
    # ---------------------------------------------------------
    # 1. BANK SECTOR-SPECIFIC CROSS-CHECK
    # ---------------------------------------------------------
    if is_bank or financial_analytics.get("bank_analytics"):
        bank_an = financial_analytics.get("bank_analytics") or {}
        adv_cagr = bank_an.get("advances_cagr_3yr")
        dep_cagr = bank_an.get("deposits_cagr_3yr")
        gnpa = bank_an.get("latest_gnpa_pct")
        nnpa = bank_an.get("latest_nnpa_pct")
        cd_ratio = bank_an.get("latest_cd_ratio_pct")
        credit_cost = bank_an.get("latest_credit_cost_pct")
        c2i = bank_an.get("latest_cost_to_income_pct")
        roa = bank_an.get("latest_roa_pct")
        roe = bank_an.get("latest_roe_pct")
        
        audit_parts = []
        if adv_cagr is not None and dep_cagr is not None:
            audit_parts.append(f"Advances 3-Yr CAGR is {adv_cagr:.1f}% vs Deposits 3-Yr CAGR of {dep_cagr:.1f}%.")
        elif adv_cagr is not None:
            audit_parts.append(f"Advances 3-Yr CAGR is {adv_cagr:.1f}%.")
            
        if gnpa is not None:
            nnpa_str = f" with Net NPA at {nnpa:.2f}%" if nnpa is not None else ""
            audit_parts.append(f"Asset quality: Gross NPA stands at {gnpa:.2f}%{nnpa_str}.")
            
        if cd_ratio is not None:
            audit_parts.append(f"Credit-Deposit (CD) Ratio is {cd_ratio:.1f}%.")
            
        if roa is not None:
            roe_str = f" and ROE at {roe:.1f}%" if roe is not None else ""
            audit_parts.append(f"Return profile: ROA stands at {roa:.2f}%{roe_str}.")
            
        if audit_parts and doc_intel.risks_and_cash:
            doc_intel.risks_and_cash.reported_numbers_comparison = "REPORTED BANK METRICS AUDIT: " + " ".join(audit_parts)
            
        if doc_intel.capital_allocation:
            if roa is not None or roe is not None:
                doc_intel.capital_allocation.capital_deployed_vs_returns = (
                    (f"Bank return profile: ROA ~{roa:.2f}%" if roa is not None else "") +
                    (f", ROE ~{roe:.1f}%" if roe is not None else "")
                )
                
        # Banks do not receive industrial FCF / CWIP / Working capital anomalies
        return

    # ---------------------------------------------------------
    # 2. GENERAL CORPORATE CROSS-CHECK
    # ---------------------------------------------------------
    cf_quality = financial_analytics.get("cash_flow_quality", {})
    cfo_pat = cf_quality.get("cfo_to_pat_5yr_pct")
    cum_cfo = cf_quality.get("cumulative_5y_cfo_cr")
    cum_pat = cf_quality.get("cumulative_5y_pat_cr")
    cum_fcf = cf_quality.get("cumulative_5y_fcf_cr")
    
    bs_eff = financial_analytics.get("balance_sheet_efficiency", {})
    cwip_pct = bs_eff.get("latest_cwip_to_net_block_pct")
    debt_eq = bs_eff.get("latest_debt_to_equity")
    
    growth = financial_analytics.get("growth_rates", {})
    sales_3y = growth.get("sales_cagr_3yr")
    pat_3y = growth.get("pat_cagr_3yr")

    if cfo_pat is not None and doc_intel.risks_and_cash:
        audit_parts = []
        if cum_cfo is not None and cum_pat is not None:
            audit_parts.append(f"5-Year Cumulative CFO of ₹{cum_cfo:,.0f} Cr vs PAT of ₹{cum_pat:,.0f} Cr ({cfo_pat:.1f}% cash conversion ratio).")
        elif cum_cfo is not None:
            audit_parts.append(f"5-Year Cumulative CFO of ₹{cum_cfo:,.0f} Cr ({cfo_pat:.1f}% cash conversion ratio).")
        else:
            audit_parts.append(f"5-Year CFO/PAT cash conversion ratio of {cfo_pat:.1f}%.")
            
        if debt_eq is not None and cwip_pct is not None:
            audit_parts.append(f"Balance Sheet Debt/Equity stands at {debt_eq}x with CWIP at {cwip_pct:.1f}% of fixed assets.")
        elif debt_eq is not None:
            audit_parts.append(f"Balance Sheet Debt/Equity stands at {debt_eq}x.")
        elif cwip_pct is not None:
            audit_parts.append(f"CWIP stands at {cwip_pct:.1f}% of fixed assets.")
            
        if sales_3y is not None:
            audit_parts.append(f"Reported 3-Year Sales CAGR is {sales_3y:.1f}%.")
            
        doc_intel.risks_and_cash.reported_numbers_comparison = "REPORTED NUMBERS AUDIT: " + " ".join(audit_parts)

    # Deterministically enrich Capital Allocation if not populated
    if doc_intel.capital_allocation and not is_financial:
        if not doc_intel.capital_allocation.capex_efficiency and (cwip_pct is not None or cum_fcf is not None):
            if cwip_pct is not None and cum_fcf is not None:
                fcf_txt = f"CWIP stands at {cwip_pct:.1f}% of net block with 5-Year cumulative FCF of ₹{cum_fcf:,.0f} Cr"
                if cum_cfo is not None:
                    fcf_txt += f" (after reinvesting ₹{(cum_cfo - cum_fcf):,.0f} Cr in capital assets)."
                else:
                    fcf_txt += "."
                doc_intel.capital_allocation.capex_efficiency = fcf_txt
            elif cwip_pct is not None:
                doc_intel.capital_allocation.capex_efficiency = f"CWIP stands at {cwip_pct:.1f}% of net block."
            elif cum_fcf is not None:
                fcf_txt = f"5-Year cumulative FCF of ₹{cum_fcf:,.0f} Cr"
                if cum_cfo is not None:
                    fcf_txt += f" (after reinvesting ₹{(cum_cfo - cum_fcf):,.0f} Cr in capital assets)."
                else:
                    fcf_txt += "."
                doc_intel.capital_allocation.capex_efficiency = fcf_txt
                
        if not doc_intel.capital_allocation.shareholder_returns and cfo_pat is not None:
            conv_qual = cf_quality.get("cash_conversion_quality", "Adequate")
            ret_text = f"5-Year CFO/PAT conversion is {cfo_pat:.1f}% ({conv_qual} quality)."
            if debt_eq is not None:
                ret_text += f" Debt-to-Equity is {debt_eq}x."
            doc_intel.capital_allocation.shareholder_returns = ret_text

    # Deterministically enrich Governance / Accounting Watch working capital note
    if doc_intel.governance_watch and not is_financial:
        wc_audit = financial_analytics.get("working_capital_audit", {})
        debtor_days = wc_audit.get("debtor_days")
        inv_days = wc_audit.get("inventory_days")
        if not doc_intel.governance_watch.working_capital_anomalies and (debtor_days is not None or inv_days is not None):
            doc_intel.governance_watch.working_capital_anomalies = (
                f"Working capital cycle: Debtor Days ~{debtor_days if debtor_days is not None else 'N/A'} days, "
                f"Inventory Days ~{inv_days if inv_days is not None else 'N/A'} days."
            )


