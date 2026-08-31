"""
=============================================================================
Stocker Research Lifecycle Service
=============================================================================
Derives the deterministic, evidence-based lifecycle status for any company
in accordance with docs/STOCKER_ENGINEERING_CONTRACT.md.
"""

from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

import database
from models import ResearchLifecycleStatus


def get_research_lifecycle_status(symbol: str) -> ResearchLifecycleStatus:
    """
    Computes the canonical research lifecycle status for a given symbol.
    Uses actual persistence and verification state without optimistic guesses.
    """
    clean_sym = symbol.upper().strip()
    notes: List[str] = []

    # 1. IDENTITY STATE
    # - officially_verified: verified against authoritative exchange / master data
    # - resolved: canonical record present in company_registry
    # - unresolved: not found in local registry
    reg = database.get_company_by_symbol(clean_sym)
    if reg:
        if reg.get("identity_verified_at") or reg.get("source") in ["nse_master", "bse_master", "mca_official"]:
            identity_state = "officially_verified"
            notes.append("Authoritative exchange security identity confirmed.")
        else:
            identity_state = "resolved"
            notes.append("Canonical company identity resolved in registry.")
    else:
        identity_state = "unresolved"
        notes.append("Unregistered or ambiguous company identity.")

    # 2. FINANCIAL DATA & CACHE STATE
    # - ready: valid persisted financial statements present and fresh
    # - stale: statements older than standard freshness window (90 days)
    # - missing: no statements cached/stored
    # - error: malformed or partial data
    cached = database.get_stock_cache(clean_sym)
    fin_updated_at: Optional[str] = None
    financial_data_state = "missing"
    has_statements = False

    if cached and isinstance(cached, dict):
        has_pl = bool(cached.get("profit_loss") or cached.get("profit_and_loss"))
        has_bs = bool(cached.get("balance_sheet"))
        has_cf = bool(cached.get("cash_flow"))
        has_q = bool(cached.get("quarters"))
        fin_updated_at = cached.get("fetched_at")

        if has_pl and has_bs and has_cf and has_q:
            has_statements = True
            # Check age for genuine staleness (90 days)
            is_old = False
            if fin_updated_at:
                try:
                    f_dt = datetime.fromisoformat(fin_updated_at.replace("Z", "+00:00"))
                    age_days = (datetime.now(timezone.utc) - f_dt).total_seconds() / 86400.0
                    if age_days > 90.0:
                        is_old = True
                except Exception:
                    pass
            if is_old:
                financial_data_state = "stale"
                notes.append("Financial statements are older than standard freshness window.")
            else:
                financial_data_state = "ready"
                notes.append("Standardized reported financial statements ingested.")
        elif has_pl or has_bs or has_cf or has_q:
            financial_data_state = "error"
            notes.append("Malformed or incomplete financial statements present.")
    else:
        notes.append("Financial statement ingestion has not been run.")

    # 3. DETERMINISTIC ANALYSIS STATE
    # - ready: ratios, margins, CAGRs, working capital can be computed from statements
    # - not_ready: statements not available
    if has_statements:
        deterministic_analysis_state = "ready"
        notes.append("Deterministic financial analytics computed from statements.")
    else:
        deterministic_analysis_state = "not_ready"

    # 4. OFFICIAL FINANCIAL VERIFICATION STATE
    # - verified: latest results verified against official XBRL/PDF filings with 0 material discrepancies
    # - discrepancy: official filings exist but diverge from reported figures
    # - partial: some metrics verified or not comparable
    # - not_run: no official verification records exist
    ver_summary = database.get_financial_verification_summary(clean_sym)
    if ver_summary and ver_summary.get("total_metrics_checked", 0) > 0:
        ov = ver_summary.get("overall_status", "").upper()
        if ov == "VERIFIED":
            official_verification_state = "verified"
            notes.append("Financial results reconciled with official exchange filings.")
        elif ov == "DISCREPANCY":
            official_verification_state = "discrepancy"
            notes.append("Material discrepancies detected against official exchange filings.")
        else:
            official_verification_state = "partial"
            notes.append(f"Official verification status: {ov}.")
    else:
        official_verification_state = "not_run"

    # 5. SOURCE FILINGS STATE
    # - ready: discovered and indexed in source_documents table
    # - partial: discovery run but few/incomplete documents
    # - not_searched: no document discovery performed
    # - error: discovery failed
    db_docs = database.get_source_documents(clean_sym)
    filing_count = len(db_docs) if db_docs else 0
    sync_state = database.get_document_sync_state(clean_sym, category="all")
    filings_checked_at: Optional[str] = sync_state.get("last_checked_at") if sync_state else None

    if filing_count > 0:
        source_filings_state = "ready"
        notes.append(f"{filing_count} source documents indexed in repository.")
    elif sync_state:
        source_filings_state = "partial"
        notes.append("Source filing discovery executed; no new filings indexed.")
    else:
        source_filings_state = "not_searched"
        notes.append("Document discovery waterfall has not been run.")

    # 6. BUSINESS ANALYSIS STATE
    # - ready: valid AI business analysis and executive thesis extracted and persisted
    # - running: analysis currently underway
    # - stale: business analysis was extracted before latest financial statements
    # - not_run: no deep fundamental analysis executed yet
    ba_updated_at: Optional[str] = None
    business_analysis_state = "not_run"

    try:
        from doc_intelligence_engine import get_company_doc_intelligence
        doc_intel = get_company_doc_intelligence(clean_sym, include_document_summaries=False)
        if doc_intel and getattr(doc_intel, "promise_vs_delivery", None) is not None:
            has_ai_content = bool(
                doc_intel.promise_vs_delivery or
                doc_intel.what_changed_recently or
                doc_intel.growth_drivers
            )
            if has_ai_content:
                ba_updated_at = doc_intel.extraction_timestamp
                # Check if business analysis is older than newly ingested financials
                if fin_updated_at and ba_updated_at and ba_updated_at < fin_updated_at:
                    business_analysis_state = "stale"
                    notes.append("Business Analysis exists but is older than recent financial statement ingestion.")
                else:
                    business_analysis_state = "ready"
                    notes.append("Deep AI Business Analysis & Management Execution track record ready.")
    except Exception as e:
        notes.append(f"Business Analysis lookup notice: {e}")

    # 7. PROJECTION STATE & 8. INVESTMENT SCORE STATE
    # - evidence_enriched: DCF valuation incorporates verified guidance & business drivers from Business Analysis
    # - historical_only: DCF based on historical financial trends & baseline assumptions
    # - stale: Business Analysis was updated but projections have not incorporated new evidence
    # - unavailable: insufficient financial data
    proj_rec = database.get_projection_computation_state(clean_sym)
    projection_updated_at: Optional[str] = proj_rec.get("computed_at") if proj_rec else fin_updated_at

    if has_statements:
        if business_analysis_state in ("ready", "stale"):
            # Check if projection was actually computed with the current Business Analysis version
            if proj_rec and proj_rec.get("doc_intel_version") and proj_rec.get("doc_intel_version") == ba_updated_at:
                projection_state = "evidence_enriched"
                investment_score_state = "evidence_enriched"
                notes.append("Evidence-enriched DCF scenario model incorporating forward guidance.")
            else:
                projection_state = "stale"
                investment_score_state = "provisional"
                notes.append("Projection is pending recomputation following new Business Analysis evidence.")
        else:
            if financial_data_state == "ready":
                projection_state = "historical_only"
                notes.append("Historical-only baseline projection from financial statements.")
                # Check if missing fundamental ratios make score incomplete
                cached_ratios = cached.get("ratios", {}) if cached else {}
                if isinstance(cached_ratios, dict) and (cached_ratios.get("stock_pe") is None or cached_ratios.get("roce_pct") is None):
                    investment_score_state = "incomplete"
                    notes.append("Incomplete investment score due to missing fundamental ratio inputs.")
                else:
                    investment_score_state = "provisional"
                    notes.append("Provisional investment score derived from financial statements.")
            else:
                projection_state = "unavailable"
                investment_score_state = "unavailable"
                notes.append("Insufficient financial data for DCF valuation modeling.")
    else:
        projection_state = "unavailable"
        investment_score_state = "unavailable"
        notes.append("Insufficient financial data for DCF valuation modeling.")

    return ResearchLifecycleStatus(
        symbol=clean_sym,
        identity=identity_state,
        financial_data=financial_data_state,
        deterministic_analysis=deterministic_analysis_state,
        official_verification=official_verification_state,
        source_filings=source_filings_state,
        business_analysis=business_analysis_state,
        projection=projection_state,
        investment_score=investment_score_state,
        filing_count=filing_count,
        financial_data_updated_at=fin_updated_at,
        filings_checked_at=filings_checked_at,
        business_analysis_updated_at=ba_updated_at,
        projection_updated_at=projection_updated_at,
        notes=notes
    )
