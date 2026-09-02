import os
import sys
import json
from pathlib import Path

# Add local libs directory to sys.path
libs_dir = str(Path(__file__).parent.parent / "libs")
if libs_dir not in sys.path:
    sys.path.insert(0, libs_dir)

try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
    else:
        load_dotenv()
except ImportError:
    pass

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from models import (
    StockSummary, StockDetail, ProjectionAssumption,
    ProjectionResult, ScoreBreakdown, DocumentLinks,
    CompanyRegistryItem, CompanySearchResult, CompanySearchResponse,
    AddCompanyRequest, AddCompanyResponse,
    FinancialVerificationItem, FinancialVerificationSummary, FinancialVerificationResponse,
    CanonicalFinancialFact, VerificationCoverageSummary, FinancialTruthContainer,
    ResearchLifecycleStatus, DiscoverFilingsResponse
)
import database
from data_seed import DEFAULT_UNIVERSE_SYMBOLS
from scraper import fetch_stock_from_screener
from financial_engine import compute_financial_analytics
from projection_engine import run_projections
from ranking_engine import compute_stock_score
from company_resolver import resolve_and_search_companies, resolve_canonical_company, normalize_symbol
from official_financial_service import run_official_financial_verification
from research_lifecycle_service import get_research_lifecycle_status
from company_taxonomy_service import (
    classify_and_persist_company,
    get_company_taxonomy,
    normalize_classification,
    resolve_local_company_taxonomy,
)
import doc_intelligence_pipeline

app = FastAPI(
    title="Stocker - Fundamental Stock Analysis & Decision Engine",
    description="Raw Screener Financials, QoQ/YoY Trends, Projections, Concall AI, and High-Conviction Stock Picking",
    version="1.0.0"
)

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def build_full_stock_detail(stock_data: Dict[str, Any], custom_assumptions: Optional[ProjectionAssumption] = None) -> StockDetail:
    if isinstance(stock_data.get("ratios"), dict) or isinstance(stock_data.get("quarters"), dict):
        from scraper import hydrate_stock_data
        stock_data = hydrate_stock_data(stock_data)
        
    symbol = stock_data["symbol"]
    name = stock_data["name"]
    try:
        taxonomy = resolve_local_company_taxonomy(symbol, stock_data)
    except Exception as taxonomy_error:
        print(f"Notice: Local taxonomy classification note for {symbol}: {taxonomy_error}")
        fallback_sector, fallback_industry, fallback_sub, fallback_state = normalize_classification(
            stock_data.get("sector"), stock_data.get("industry"), stock_data.get("sub_industry")
        )
        taxonomy = {
            "sector": fallback_sector,
            "industry": fallback_industry,
            "sub_industry": fallback_sub,
            "source": "unknown",
            "classification_method": "local_fallback",
            "confidence": "Unverified",
            "classification_state": fallback_state,
        }
    sector = taxonomy.get("sector", "Unclassified")
    industry = taxonomy.get("industry", "Unclassified")
    sub_industry = taxonomy.get("sub_industry")
    about = stock_data.get("about", "")
    source_name = stock_data.get("source_name", "Screener.in")
    source_url = stock_data.get("source_url", "")
    statement_type = stock_data.get("statement_type", "consolidated")
    fetched_at = stock_data.get("fetched_at", "")
    
    ratios = stock_data["ratios"]
    quarters = stock_data["quarters"]
    pl = stock_data["profit_loss"]
    bs = stock_data["balance_sheet"]
    cf = stock_data["cash_flow"]
    concall_insights = stock_data.get("concall_insights", [])
    ar_insights = stock_data.get("annual_report_insights", [])
    documents = stock_data.get("documents")
    
    # 1. Authoritative Financial Verification & Canonical Truth Layer (Phase 2A & 2B)
    verif_summary_dict = database.get_financial_verification_summary(symbol)
    verif_summary = FinancialVerificationSummary(**verif_summary_dict) if verif_summary_dict else None

    financial_truth = None
    try:
        from financial_truth_service import build_financial_truth_for_stock
        financial_truth = build_financial_truth_for_stock(
            symbol=symbol,
            stock_data=stock_data,
            verification_summary=verif_summary_dict
        )
    except Exception as e_truth:
        print(f"Notice: Canonical financial truth build note for {symbol}: {e_truth}")

    # 2. Financial Analytics (Truth-Driven & Safety Routed in Phase 2C)
    analytics = compute_financial_analytics(
        quarters=quarters,
        pl=pl,
        bs=bs,
        cf=cf,
        symbol=symbol,
        financial_truth=financial_truth,
        sector=sector,
        industry=industry
    )
    
    # 3. Document Intelligence (if available)
    doc_intel = get_company_doc_intelligence(symbol, financial_analytics=analytics)
    
    # 4. Projections & DCF Valuation (grounded in historical parameters + AI forward signals)
    projection = run_projections(
        ratios=ratios,
        pl=pl,
        bs=bs,
        cf=cf,
        analytics=analytics,
        doc_intel=doc_intel,
        assumptions=custom_assumptions
    )
    
    # 5. Multi-Factor Scoring & Thesis (with execution track record and confidence tracking)
    score = compute_stock_score(symbol, name, ratios, analytics, projection, sector=sector, doc_intel=doc_intel)

    # Record projection computation state (tracks doc_intel version used)
    doc_intel_version = getattr(doc_intel, "extraction_timestamp", None) if doc_intel else None
    database.record_projection_computation_state(
        symbol=symbol,
        fin_data_version=fetched_at,
        doc_intel_version=doc_intel_version
    )

    biz_model = analytics.get("financial_business_model", "GENERAL_CORPORATE")

    return StockDetail(
        symbol=symbol,
        name=name,
        sector=sector,
        industry=industry,
        sub_industry=sub_industry,
        taxonomy=taxonomy,
        about=about,
        ratios=ratios,
        quarters=quarters,
        profit_loss=pl,
        balance_sheet=bs,
        cash_flow=cf,
        concall_insights=concall_insights,
        annual_report_insights=ar_insights,
        documents=documents or DocumentLinks(),
        analytics=analytics,
        projection=projection,
        score=score,
        source_name=source_name,
        source_url=source_url,
        statement_type=statement_type,
        financial_business_model=biz_model,
        bank_analytics=analytics.get("bank_analytics") if biz_model == "BANK" else None,
        fetched_at=fetched_at,
        documents_checked_at=database.get_document_sources_checked_at(symbol) or stock_data.get("documents_checked_at"),
        verification_summary=verif_summary,
        financial_truth=financial_truth
    )

@app.get("/api/health")
def health_check():
    return {"status": "healthy", "service": "stocker-backend"}

@app.get("/api/stocks", response_model=List[StockSummary])
def get_all_stocks(sector: Optional[str] = None, min_score: Optional[float] = None):
    results: List[StockSummary] = []
    
    # 1. Retrieve persistent universe symbols strictly from database registry (in_universe=1 AND is_active=1)
    universe_symbols = database.get_universe_symbols(active_only=True)
    
    # Bootstrap fallback ONLY if registry has NEVER been initialized (0 total registered companies)
    if not universe_symbols:
        total_registry_count = database.get_company_registry_total_count()
        if total_registry_count == 0:
            try:
                database.seed_company_registry()
                universe_symbols = database.get_universe_symbols(active_only=True)
            except Exception:
                pass
            if not universe_symbols:
                universe_symbols = list(DEFAULT_UNIVERSE_SYMBOLS)
            
    details = []
    for sym in universe_symbols:
        data = fetch_stock_from_screener(sym, force_refresh=False)
        if data:
            detail = build_full_stock_detail(data)
            details.append(detail)
            
    # Sort by total composite score descending
    details.sort(key=lambda x: x.score.total_composite_score, reverse=True)
    
    for idx, d in enumerate(details):
        r = d.ratios
        sales_cagr = d.analytics.get("growth_rates", {}).get("sales_cagr_3yr")
        if sales_cagr is None:
            sales_cagr = r.sales_growth_3yr_cagr
        cfo_to_pat = d.analytics.get("cash_flow_quality", {}).get("cfo_to_pat_5yr_pct")
        
        summary = StockSummary(
            symbol=d.symbol,
            name=d.name,
            sector=d.sector,
            industry=d.industry,
            sub_industry=d.sub_industry,
            taxonomy=d.taxonomy,
            current_price=r.current_price,
            market_cap_cr=r.market_cap_cr,
            pe_ratio=r.stock_pe,
            roce_pct=r.roce_pct,
            roe_pct=r.roe_pct,
            fcf_yield_pct=r.fcf_yield_pct,
            sales_growth_3yr_pct=sales_cagr,
            cfo_to_pat_5yr_pct=cfo_to_pat,
            net_debt_to_equity=r.debt_to_equity,
            composite_score=d.score.total_composite_score,
            verdict=d.score.verdict,
            data_confidence=d.score.data_confidence,
            rank=idx + 1,
            is_top_conviction=(idx < 5 and d.score.total_composite_score >= 70.0),
            investment_thesis_short=d.score.investment_thesis,
            source_name=d.source_name,
            source_url=d.source_url,
            statement_type=d.statement_type,
            financial_business_model=d.financial_business_model,
            bank_analytics=d.bank_analytics if d.financial_business_model == "BANK" else None,
            fetched_at=d.fetched_at
        )
        
        if sector and sector.lower() not in summary.sector.lower():
            continue
        if min_score and summary.composite_score < min_score:
            continue
            
        results.append(summary)
        
    return results

# =============================================================================
# COMPANY REGISTRY & SEARCH / ADD APIS (PHASE A & V4.1)
# =============================================================================

@app.get("/api/companies/search", response_model=CompanySearchResponse)
def search_companies(q: str = Query(..., min_length=1, description="Company name, symbol, or partial ticker"), limit: int = 10):
    """
    Searches for listed companies by symbol, full/partial name, or aliases.
    Searches local registry first with automatic fallback to external discovery.
    """
    clean_q = q.strip()
    if not clean_q:
        return CompanySearchResponse(query=q, count=0, results=[])
        
    matches = resolve_and_search_companies(clean_q, limit=limit)
    search_results = [CompanySearchResult(**m) for m in matches]
    return CompanySearchResponse(
        query=clean_q,
        count=len(search_results),
        results=search_results
    )

def execute_add_company_to_universe(symbol_or_query: str) -> AddCompanyResponse:
    """
    Unified execution pipeline for adding or searching a company:
    1. Reconciles raw query against authoritative exchange master and local registry.
    2. Fails closed with 409 AMBIGUOUS_COMPANY on competing candidates.
    3. Fails closed with 404 on unverified / unresolved inputs.
    4. Ingests financial statements into primary durable SQLite storage.
    5. Returns AddCompanyResponse with full StockDetail and 8-dimension ResearchLifecycleStatus.
    """
    from company_resolver import resolve_proven_security_for_add
    clean_input = symbol_or_query.strip()
    if not clean_input:
        raise HTTPException(status_code=400, detail="Company symbol or query cannot be empty.")
        
    canonical_info, is_ambiguous, candidates = resolve_proven_security_for_add(clean_input)
    if is_ambiguous:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "AMBIGUOUS_COMPANY",
                "message": f"Multiple listed securities match query '{clean_input}'. Please select a specific candidate.",
                "candidates": [
                    {
                        "symbol": c.get("symbol"),
                        "company_name": c.get("company_name"),
                        "nse_symbol": c.get("nse_symbol"),
                        "bse_code": c.get("bse_code"),
                        "match_score": c.get("match_score")
                    } for c in candidates[:6]
                ]
            }
        )
        
    if not canonical_info:
        raise HTTPException(
            status_code=404, 
            detail=f"Could not resolve a verified listed security for '{clean_input}'. Please verify company name or ticker symbol."
        )
        
    canonical_sym = canonical_info.get("symbol", "").upper().strip()
    company_name = canonical_info.get("company_name", canonical_sym)
    
    # Check if already existed in universe
    existing = database.get_company_by_symbol(canonical_sym)
    already_existed = bool(existing and existing.get("in_universe") and existing.get("is_active"))
    
    # Ingest financial statements using standardized Screener ingestion (durable in SQLite)
    stock_data = fetch_stock_from_screener(canonical_sym, force_refresh=True)
    if not stock_data:
        # If live scrape failed, attempt fallback resolution without force_refresh
        stock_data = fetch_stock_from_screener(canonical_sym, force_refresh=False)
        if not stock_data:
            raise HTTPException(
                status_code=400, 
                detail=f"Unable to ingest standardized financial statements for '{canonical_sym}'. Please verify ticker symbol."
            )
            
    # Persist canonical identity before taxonomy so the compatibility fields can
    # be updated atomically by the taxonomy service.
    raw_sector = stock_data.get("source_sector") or canonical_info.get("sector") or stock_data.get("sector")
    raw_industry = stock_data.get("source_industry") or canonical_info.get("industry") or stock_data.get("industry")
    real_name = stock_data.get("name") or company_name
    
    database.upsert_company_registry_item({
        "symbol": canonical_sym,
        "company_name": real_name,
        "nse_symbol": canonical_info.get("nse_symbol"),
        "bse_code": canonical_info.get("bse_code"),
        "isin": canonical_info.get("isin"),
        "exchange": canonical_info.get("exchange"),
        "sector": raw_sector or "Unclassified",
        "industry": raw_industry or "Unclassified",
        "aliases": canonical_info.get("aliases", [real_name, canonical_sym]),
        "source": canonical_info.get("source", "screener_ingestion"),
        "source_last_verified_at": canonical_info.get("source_last_verified_at"),
        "identity_source_name": canonical_info.get("identity_source_name"),
        "identity_source_url": canonical_info.get("identity_source_url"),
        "identity_verified_at": canonical_info.get("identity_verified_at"),
        "in_universe": True,
        "is_active": True
    })

    taxonomy = classify_and_persist_company(
        symbol=canonical_sym,
        sector=raw_sector,
        industry=raw_industry,
        sub_industry=stock_data.get("source_sub_industry") or canonical_info.get("sub_industry"),
        source=stock_data.get("taxonomy_source") or canonical_info.get("source") or "unknown",
        classification_method="add_company_ingestion",
        pl=stock_data.get("profit_loss"),
        bs=stock_data.get("balance_sheet"),
        quarters=stock_data.get("quarters"),
    )
    # If separately supplied registry metadata is stronger, it may reclassify
    # the same mapping without creating duplicate taxonomy entities.
    if canonical_info.get("sector") or canonical_info.get("industry"):
        taxonomy = classify_and_persist_company(
            symbol=canonical_sym,
            sector=canonical_info.get("sector"),
            industry=canonical_info.get("industry"),
            sub_industry=canonical_info.get("sub_industry"),
            source=canonical_info.get("source") or "authoritative_registry",
            classification_method="canonical_identity_metadata",
            pl=stock_data.get("profit_loss"),
            bs=stock_data.get("balance_sheet"),
            quarters=stock_data.get("quarters"),
        )
    stock_data["sector"] = taxonomy["sector"]
    stock_data["industry"] = taxonomy["industry"]
    stock_data["sub_industry"] = taxonomy.get("sub_industry")
    try:
        from scraper import serialize_stock_data
        database.save_stock_cache(
            canonical_sym, real_name, taxonomy["sector"], taxonomy["industry"], serialize_stock_data(stock_data)
        )
    except Exception as taxonomy_cache_error:
        print(f"Notice: Canonical taxonomy cache update note for {canonical_sym}: {taxonomy_cache_error}")
    
    detail = build_full_stock_detail(stock_data)
    research_status = get_research_lifecycle_status(canonical_sym)
    
    msg = (
        f"Successfully refreshed financial data for {real_name} ({canonical_sym})"
        if already_existed else
        f"Successfully added {real_name} ({canonical_sym}) to Stocker universe"
    )
    
    return AddCompanyResponse(
        success=True,
        message=msg,
        symbol=canonical_sym,
        company_name=real_name,
        already_existed=already_existed,
        stock=detail,
        research_status=research_status
    )

@app.post("/api/companies/{symbol}/add", response_model=AddCompanyResponse)
def add_company_to_universe_by_path(symbol: str):
    """
    Resolves canonical company identity, enrolls it in the persistent Stocker universe,
    and ingests 10-year financial statements on demand.
    """
    return execute_add_company_to_universe(symbol)

@app.post("/api/companies/add", response_model=AddCompanyResponse)
def add_company_to_universe_by_body(req: AddCompanyRequest):
    """
    Enrolls a company in the active Stocker universe by query or symbol in request body.
    """
    target = req.query or req.symbol
    if not target:
        raise HTTPException(status_code=400, detail="Either 'query' or 'symbol' must be provided in request body.")
    return execute_add_company_to_universe(target)

@app.get("/api/stocks/{symbol}/research-status", response_model=ResearchLifecycleStatus)
def get_stock_research_status(symbol: str):
    """
    Returns the canonical research lifecycle status for a company across all 8 dimensions
    defined in docs/STOCKER_ENGINEERING_CONTRACT.md.
    """
    clean_sym = symbol.upper().strip()
    return get_research_lifecycle_status(clean_sym)

@app.post("/api/stocks/{symbol}/discover-filings", response_model=DiscoverFilingsResponse)
def discover_stock_filings(symbol: str):
    """
    Executes explicit document discovery waterfall (BSE, NSE, Company IR, network validation),
    indexes metadata into source_documents table, and updates sync state without running AI.
    Requires registered or verified canonical company.
    """
    from datetime import datetime, timezone
    from company_resolver import resolve_canonical_company
    clean_sym = symbol.upper().strip()
    
    # 1. Resolve canonical security identity
    reg = database.get_company_by_symbol(clean_sym)
    if not reg:
        canonical_cand = resolve_canonical_company(clean_sym)
        if canonical_cand and canonical_cand.get("source") != "unresolved_input":
            clean_sym = canonical_cand.get("symbol", clean_sym).upper().strip()
            reg = database.get_company_by_symbol(clean_sym) or canonical_cand
            
    if not reg:
        raise HTTPException(
            status_code=404, 
            detail=f"Cannot discover filings: '{symbol}' is not a registered or verified listed company."
        )
        
    company_name = reg.get("company_name", clean_sym)
    bse_code = reg.get("bse_code")
    nse_symbol = reg.get("nse_symbol")
    
    # 2. Run explicit trusted document waterfall with canonical registry identifiers
    from document_sourcing import execute_document_sourcing_waterfall
    execute_document_sourcing_waterfall(
        symbol=clean_sym,
        company_name=company_name,
        screener_soup=None,
        bse_code=bse_code,
        nse_symbol=nse_symbol
    )
    
    db_docs = database.get_source_documents(clean_sym)
    filing_count = len(db_docs) if db_docs else 0
    now_iso = datetime.now(timezone.utc).isoformat()
    
    database.update_document_sync_state(clean_sym, category="all", checked_at=now_iso)
    lifecycle_status = get_research_lifecycle_status(clean_sym)
    
    return DiscoverFilingsResponse(
        symbol=clean_sym,
        company_name=company_name,
        filing_count=filing_count,
        documents_checked_at=now_iso,
        research_status=lifecycle_status
    )

@app.get("/api/companies", response_model=List[CompanyRegistryItem])
def get_registered_companies(active_only: bool = False):
    """
    Lists all companies in the persistent SQLite registry.
    """
    companies = database.get_universe_companies(active_only=active_only)
    enriched = []
    for company in companies:
        taxonomy = get_company_taxonomy(company["symbol"])
        if taxonomy:
            company = {**company, **{
                "sector": taxonomy["sector"],
                "industry": taxonomy["industry"],
                "sub_industry": taxonomy.get("sub_industry"),
                "taxonomy": taxonomy,
            }}
        enriched.append(CompanyRegistryItem(**company))
    return enriched

@app.get("/api/stocks/top-picks")
def get_top_picks():
    all_stocks = get_all_stocks()
    top_5 = [s for s in all_stocks if s.rank <= 5]
    return {
        "count": len(top_5),
        "picks": top_5,
        "methodology": "Ranked by 5 Fundamental Pillars: Growth Momentum (20%), Cash Flow Quality (25%), Capital Efficiency (20%), Balance Sheet Safety (15%), and Valuation Headroom (20%)."
    }

@app.get("/api/stocks/{symbol}", response_model=StockDetail)
def get_stock_detail(symbol: str):
    data = fetch_stock_from_screener(symbol, force_refresh=False)
    if not data:
        raise HTTPException(status_code=404, detail=f"Stock {symbol} not found in database or Screener.in")
    return build_full_stock_detail(data)

# =============================================================================
# AUTHORITATIVE FINANCIAL VERIFICATION APIS (PHASE B)
# =============================================================================

@app.get("/api/stocks/{symbol}/financial-verification", response_model=FinancialVerificationResponse)
def get_stock_financial_verification(symbol: str):
    """
    Returns authoritative financial verification records and summary for a stock.
    If no verification records exist yet, automatically executes initial verification
    against Screener statements and authoritative exchange sources.
    """
    clean_sym = symbol.strip().upper()
    summary_dict = database.get_financial_verification_summary(clean_sym)
    records_dict = database.get_financial_verification_records(clean_sym, limit=50)
    
    if not records_dict:
        stock_data = fetch_stock_from_screener(clean_sym, force_refresh=False)
        if stock_data:
            res = run_official_financial_verification(clean_sym, screener_stock_data=stock_data)
            return FinancialVerificationResponse(
                symbol=clean_sym,
                company_name=stock_data.get("name", clean_sym),
                summary=FinancialVerificationSummary(**res["summary"]),
                records=[FinancialVerificationItem(**r) for r in res["records"]]
            )
            
    company = database.get_company_by_symbol(clean_sym) or {}
    company_name = company.get("company_name", clean_sym)
    
    return FinancialVerificationResponse(
        symbol=clean_sym,
        company_name=company_name,
        summary=FinancialVerificationSummary(**summary_dict),
        records=[FinancialVerificationItem(**r) for r in records_dict]
    )

@app.post("/api/stocks/{symbol}/verify-financials", response_model=FinancialVerificationResponse)
def trigger_stock_financial_verification(symbol: str):
    """
    Triggers an on-demand authoritative identity resolution and official financial statement verification.
    """
    clean_sym = symbol.strip().upper()
    stock_data = fetch_stock_from_screener(clean_sym, force_refresh=False)
    if not stock_data:
        raise HTTPException(status_code=404, detail=f"Stock data not found for '{clean_sym}'")
        
    res = run_official_financial_verification(clean_sym, screener_stock_data=stock_data)
    return FinancialVerificationResponse(
        symbol=clean_sym,
        company_name=stock_data.get("name", clean_sym),
        summary=FinancialVerificationSummary(**res["summary"]),
        records=[FinancialVerificationItem(**r) for r in res["records"]]
    )

@app.get("/api/stocks/{symbol}/financial-truth", response_model=FinancialTruthContainer)
def get_stock_financial_truth(symbol: str):
    """
    Lightweight endpoint returning the persisted Canonical Financial Truth container
    (canonical facts, verification coverage, and provenance) without external network calls.
    Deterministically recomputes from local cached inputs if stale or missing.
    """
    clean_sym = symbol.strip().upper()
    from financial_truth_service import get_or_recompute_financial_truth
    container = get_or_recompute_financial_truth(clean_sym)
    if not container:
        raise HTTPException(status_code=404, detail=f"Financial data not found for '{clean_sym}'. Please add the stock first.")
    return container

from doc_intelligence_engine import get_company_doc_intelligence
from llm_service import is_llm_available, get_available_llm_provider
from doc_intelligence_pipeline import run_generic_document_pipeline, select_default_document_working_set, fetch_historical_evidence_document

def _get_minimal_financial_analytics(symbol: str) -> Optional[Dict[str, Any]]:
    """Retrieves or minimally computes only the essential analytics from local cache/persistence without network calls."""
    clean_sym = symbol.upper().strip()
    cached = database.get_stock_cache(clean_sym)
    if cached and "analytics" in cached and cached["analytics"]:
        return cached["analytics"]
    
    if cached:
        try:
            from financial_engine import compute_financial_analytics
            from models import FinancialStatement
            pl_raw = cached.get("profit_loss") or cached.get("profit_and_loss")
            bs_raw = cached.get("balance_sheet")
            cf_raw = cached.get("cash_flow")
            quarters_raw = cached.get("quarters")
            
            if pl_raw or bs_raw or cf_raw or quarters_raw:
                pl = FinancialStatement(**pl_raw) if pl_raw else None
                bs = FinancialStatement(**bs_raw) if bs_raw else None
                cf = FinancialStatement(**cf_raw) if cf_raw else None
                quarters = FinancialStatement(**quarters_raw) if quarters_raw else None
                
                return compute_financial_analytics(quarters, pl, bs, cf, symbol=clean_sym)
        except Exception as e:
            print(f"Notice: Minimal analytics computation note: {e}")
            
    # If no cache is found locally, return None (no external network fetch!)
    return None

@app.get("/api/stocks/{symbol}/business-analysis")
def get_stock_business_analysis(symbol: str):
    """
    Lightweight, high-performance endpoint returning the verified Business Analysis synthesis
    (Investment View, Business & Growth, Management & Execution) without full filing archives.
    """
    clean_sym = symbol.upper().strip()
    analytics = _get_minimal_financial_analytics(clean_sym)
    
    # Retrieve company name cleanly from registry or cache
    company_name = clean_sym
    reg = database.get_company_by_symbol(clean_sym)
    if reg:
        company_name = reg.get("company_name", clean_sym)
    else:
        cached = database.get_stock_cache(clean_sym)
        if cached:
            company_name = cached.get("company_name", clean_sym)
            
    doc_intel = get_company_doc_intelligence(clean_sym, financial_analytics=analytics, include_document_summaries=False)
    if not doc_intel:
        return {
            "symbol": clean_sym,
            "company_name": company_name,
            "status": "not_analyzed",
            "message": f"Deep AI fundamental analysis has not been executed for {company_name} ({clean_sym}) yet.",
            "ai_provider_used": "None",
            "model_version": None,
            "extraction_timestamp": "",
            "latest_document_period": "Not Analyzed",
            "older_document_period": None,
            "source_documents": [],
            "what_changed_recently": [],
            "growth_drivers": [],
            "promise_vs_delivery": [],
            "demand_momentum": {"summary": "", "company_specific_metrics": [], "segment_trends": [], "headwinds_and_risks": []},
            "risks_and_cash": {"working_capital_and_receivables": "", "debt_and_capex_burden": "", "execution_and_bottlenecks": [], "regulatory_or_legal_headwinds": []},
            "stocker_view": {"execution_verdict": "Evolving / Watchlist", "investor_summary": "", "positive_triggers": [], "main_risks": [], "what_to_watch_next": []},
            "business_quality": {"business_model_summary": "", "segment_mix": [], "geography_mix": [], "revenue_characteristics": {}},
            "competitive_position": {"moat_type": "Narrow / Evolving", "key_advantages": [], "competitive_threats": []},
            "capital_allocation": {},
            "governance_watch": {"regulatory_or_legal_risks": []},
            "document_summaries": [],
            "verified_facts": [],
            "operational_kpi_evolution": [],
            "guidance_vs_projections": [],
            "evidence_items": [],
            "management_guidance_items": [],
            "source_documents_hash": None,
            "analysis_version": "2.0",
            "staleness_status": "not_analyzed",
            "financial_business_model": "GENERAL_CORPORATE"
        }
        
    res_dict = doc_intel.model_dump()
    res_dict["source_documents"] = []
    res_dict["document_summaries"] = []
    return res_dict

@app.get("/api/stocks/{symbol}/doc-intelligence")
def get_stock_doc_intelligence(symbol: str):
    """Backward-compatible endpoint returning full document intelligence with working set & summaries."""
    clean_sym = symbol.upper().strip()
    data = fetch_stock_from_screener(clean_sym, force_refresh=False)
    analytics = None
    company_name = clean_sym
    queued_docs = []
    if data:
        detail = build_full_stock_detail(data)
        analytics = detail.analytics
        company_name = detail.name
        database.save_stock_cache(clean_sym, detail.name, detail.sector, detail.industry, data)
        queued_docs = select_default_document_working_set(detail.documents)
            
    doc_intel = get_company_doc_intelligence(clean_sym, financial_analytics=analytics, include_document_summaries=True)
    if not doc_intel:
        return {
            "symbol": clean_sym,
            "company_name": company_name,
            "status": "not_analyzed",
            "message": f"Deep AI fundamental analysis has not been executed for {company_name} ({clean_sym}) yet.",
            "ai_provider_used": "None",
            "model_version": None,
            "extraction_timestamp": "",
            "latest_document_period": "Not Analyzed",
            "older_document_period": None,
            "source_documents": [d.model_dump() for d in queued_docs],
            "what_changed_recently": [],
            "growth_drivers": [],
            "promise_vs_delivery": [],
            "demand_momentum": {"summary": "", "company_specific_metrics": [], "segment_trends": [], "headwinds_and_risks": []},
            "risks_and_cash": {"working_capital_and_receivables": "", "debt_and_capex_burden": "", "execution_and_bottlenecks": [], "regulatory_or_legal_headwinds": []},
            "stocker_view": {"execution_verdict": "Evolving / Watchlist", "investor_summary": "", "positive_triggers": [], "main_risks": [], "what_to_watch_next": []},
            "business_quality": {"business_model_summary": "", "segment_mix": [], "geography_mix": [], "revenue_characteristics": {}},
            "competitive_position": {"moat_type": "Narrow / Evolving", "key_advantages": [], "competitive_threats": []},
            "capital_allocation": {},
            "governance_watch": {"regulatory_or_legal_risks": []},
            "document_summaries": [],
            "verified_facts": [],
            "operational_kpi_evolution": [],
            "guidance_vs_projections": [],
            "evidence_items": [],
            "management_guidance_items": [],
            "source_documents_hash": None,
            "analysis_version": "2.0",
            "staleness_status": "not_analyzed",
            "financial_business_model": "GENERAL_CORPORATE"
        }
    return doc_intel

@app.get("/api/stocks/{symbol}/source-filings")
def get_stock_source_filings(symbol: str):
    """
    Returns structured filing archive and per-document AI summaries directly
    from the canonical persisted document layer without expensive full-detail recalculations.
    Documents are deduplicated at the physical file layer and ordered globally newest-first.
    """
    clean_sym = symbol.upper().strip()
    company_name = clean_sym
    
    # 1. Retrieve company name from registry or cache
    reg_entry = database.get_company_by_symbol(clean_sym)
    if reg_entry:
        company_name = reg_entry.get("company_name", clean_sym)
    else:
        cached = database.get_stock_cache(clean_sym)
        if cached:
            company_name = cached.get("company_name", clean_sym)

    # 2. Retrieve persisted source documents (Preferred Canonical Corpus)
    db_docs = database.get_source_documents(clean_sym)
    from models import DocumentLinks, DocumentItem
    doc_links = DocumentLinks()
    
    raw_doc_items = []
    if db_docs:
        raw_doc_items = db_docs
    else:
        # Fast fallback: fetch screener raw documents without full analytics/projections calculation
        cached = database.get_stock_cache(clean_sym)
        if cached and "documents" in cached:
            raw_d = cached["documents"]
            if isinstance(raw_d, dict):
                for k, lst in raw_d.items():
                    if isinstance(lst, list):
                        raw_doc_items.extend(lst)
        else:
            data = fetch_stock_from_screener(clean_sym, force_refresh=False)
            if data and "documents" in data:
                raw_d = data["documents"]
                if isinstance(raw_d, dict):
                    for k, lst in raw_d.items():
                        if isinstance(lst, list):
                            raw_doc_items.extend(lst)
                company_name = data.get("company_name", company_name)
    
    # 3. Deduplicate physical documents and normalize classifications
    canonical_docs = database.deduplicate_document_records(raw_doc_items, clean_sym)
    summaries = database.get_document_summaries(clean_sym)
    cached_ai = database.get_cached_ai_analysis(clean_sym)
    has_company_analysis = bool(cached_ai and (cached_ai.get("what_changed_recently") or cached_ai.get("growth_drivers") or cached_ai.get("promise_vs_delivery")))
    
    all_items: List[DocumentItem] = []
    for r in canonical_docs:
        c_url = database.canonicalize_document_url(r.get("url")) or r.get("url")
        norm_dt = database.normalize_document_type(r.get("doc_type"), r.get("title"))
        sort_ts = database.parse_document_sort_timestamp(r.get("period_or_date"), r.get("title"))
        doc_k = r.get("doc_key") or database.compute_canonical_document_key(
            clean_sym, norm_dt, r.get("period_or_date"), c_url, r.get("title")
        )
        
        # Summary resolution
        summary = summaries.get(doc_k) or summaries.get(c_url)
        if not summary and r.get("url"):
            summary = summaries.get(r.get("url"))
        if not summary and r.get("period_or_date"):
            sem_key = database.compute_canonical_semantic_key(clean_sym, norm_dt, r.get("period_or_date"))
            if sem_key:
                summary = summaries.get(sem_key)
                
        if summary:
            if summary.get("status") == "failed":
                ai_st = "PROCESSING_FAILED"
                fail_reason = summary.get("error", "AI document extraction failed.")
            else:
                ai_st = "AI_ANALYZED"
                fail_reason = None
        else:
            if has_company_analysis:
                ai_st = "NOT_SELECTED"
            else:
                ai_st = "NOT_ANALYZED_YET"
            fail_reason = None
            
        d_item = DocumentItem(
            ticker=clean_sym,
            company_name=company_name,
            title=r.get("title", ""),
            url=c_url,
            doc_type=norm_dt,
            doc_subtype=r.get("doc_subtype"),
            event_key=r.get("event_key"),
            is_substantive=r.get("is_substantive", True),
            is_wrapper=r.get("is_wrapper", False),
            wrapper_source_url=r.get("wrapper_source_url"),
            ai_eligible=r.get("ai_eligible", True),
            period_or_date=r.get("period_or_date"),
            discovery_source=r.get("discovery_source", "Database"),
            discovered_sources=r.get("discovered_sources") or [r.get("discovery_source", "Database")],
            source_aliases=r.get("source_aliases") or [],
            actual_source_host=r.get("actual_source_host", "bseindia.com"),
            doc_key=doc_k,
            ai_status=ai_st,
            ai_failure_reason=fail_reason,
            sort_timestamp=sort_ts
        )
        all_items.append(d_item)

    # 4. Global Chronological Sort: Newest First
    all_items.sort(key=lambda x: (x.sort_timestamp or "1970-01-01", x.title), reverse=True)
    doc_links.all_documents = all_items
    
    for doc in all_items:
        dt = doc.doc_type
        if dt == "annual_report":
            doc_links.annual_reports.append(doc)
        elif dt == "regulatory_annual_filing":
            doc_links.regulatory_annual_filings.append(doc)
        elif dt == "concall_transcript":
            doc_links.concalls.append(doc)
        elif dt == "presentation":
            doc_links.presentations.append(doc)
        elif dt == "announcement":
            doc_links.material_announcements.append(doc)
        elif dt == "brsr_esg":
            doc_links.brsr_reports.append(doc)
        else:
            doc_links.other_filings.append(doc)
            
    # Assign deterministic AI Working Set metadata
    doc_intelligence_pipeline.assign_working_set_metadata(doc_links)
    
    # Authoritative AI status synchronization
    for doc in doc_links.all_documents:
        sem_k = database.compute_canonical_semantic_key(doc.ticker, doc.doc_type, doc.period_or_date)
        summary = (
            summaries.get(doc.url) 
            or (summaries.get(doc.doc_key) if doc.doc_key else None)
            or (summaries.get(sem_k) if sem_k else None)
        )
        if summary:
            if summary.get("status") == "failed" or summary.get("error"):
                doc.ai_status = "PROCESSING_FAILED"
                doc.ai_failure_reason = summary.get("error", "AI document extraction failed.")
            else:
                doc.ai_status = "AI_ANALYZED"
                doc.ai_failure_reason = None
        elif has_company_analysis:
            if not doc.selected_for_ai:
                doc.ai_status = "NOT_SELECTED"
            else:
                doc.ai_status = "NOT_ANALYZED_YET"
        else:
            doc.ai_status = "NOT_ANALYZED_YET"
    
    return {
        "symbol": clean_sym,
        "company_name": company_name,
        "documents": doc_links.model_dump(),
        "summaries": summaries,
        "has_company_analysis": has_company_analysis
    }

@app.get("/api/stocks/{symbol}/document-summaries")
def get_stock_document_summaries(symbol: str):
    """Returns AI executive summaries for all individual documents of a stock."""
    clean_sym = symbol.upper().strip()
    return database.get_document_summaries(clean_sym)

@app.post("/api/stocks/{symbol}/fetch-historical-document")
def retrieve_historical_document(symbol: str, payload: Dict[str, str]):
    """Fetches an older filing on demand when checking long-term promises or capex history."""
    clean_sym = symbol.upper().strip()
    doc_type = payload.get("doc_type", "annual_report")
    period_or_year = payload.get("period_or_year", "")
    
    data = fetch_stock_from_screener(clean_sym, force_refresh=False)
    detail = build_full_stock_detail(data) if data else None
    all_docs = detail.documents if detail else None
    
    doc = fetch_historical_evidence_document(clean_sym, doc_type, period_or_year, all_available_documents=all_docs)
    if not doc:
        raise HTTPException(status_code=404, detail=f"No historical filing found for {clean_sym} ({doc_type}, {period_or_year})")
    return doc.model_dump()

@app.get("/api/ai/status")
def get_ai_status():
    """Returns real-time status and diagnostics of configured LLM providers (Gemini/OpenAI)."""
    from llm_service import test_ai_key_connectivity
    return test_ai_key_connectivity()

@app.post("/api/ai/configure")
def configure_ai_credentials(payload: Dict[str, str]):
    """Saves AI API credentials to .env file and tests connection immediately."""
    api_key = payload.get("api_key", "").strip()
    provider = payload.get("provider", "gemini").lower().strip()
    if not api_key:
        raise HTTPException(status_code=400, detail="API key string cannot be empty.")
        
    env_path = Path(__file__).parent.parent / ".env"
    lines = []
    if env_path.exists():
        lines = env_path.read_text().splitlines()
        
    var_name = "GEMINI_API_KEY" if provider == "gemini" else "OPENAI_API_KEY"
    new_lines = [l for l in lines if not l.startswith(f"{var_name}=")]
    new_lines.append(f"{var_name}={api_key}")
    env_path.write_text("\n".join(new_lines) + "\n")
    
    os.environ[var_name] = api_key
    from llm_service import test_ai_key_connectivity
    return test_ai_key_connectivity()

@app.post("/api/stocks/{symbol}/generate-doc-intelligence")
def generate_stock_doc_intelligence(symbol: str):
    clean_sym = symbol.upper().strip()
    from llm_service import is_llm_available, get_available_llm_provider, test_ai_key_connectivity
    if not is_llm_available():
        raise HTTPException(
            status_code=400,
            detail="AI document analysis unavailable: No GEMINI_API_KEY or OPENAI_API_KEY configured in .env file. Please add your key to run live extraction."
        )
    data = fetch_stock_from_screener(clean_sym, force_refresh=False)
    if not data:
        raise HTTPException(status_code=404, detail=f"Stock {clean_sym} not found on Screener.in")
    detail = build_full_stock_detail(data)
    
    # 1. Prefer canonical persisted source_documents from SQLite filing discovery
    db_docs = database.get_source_documents(clean_sym)
    from models import DocumentLinks, DocumentItem
    doc_links = DocumentLinks()
    
    raw_doc_items = []
    if db_docs:
        raw_doc_items = db_docs
    else:
        if detail.documents:
            for k, lst in detail.documents.model_dump().items():
                if isinstance(lst, list):
                    raw_doc_items.extend(lst)
                    
    canonical_docs = database.deduplicate_document_records(raw_doc_items, clean_sym)
    all_items = []
    for r in canonical_docs:
        c_url = database.canonicalize_document_url(r.get("url")) or r.get("url")
        norm_dt = database.normalize_document_type(r.get("doc_type"), r.get("title"))
        sort_ts = database.parse_document_sort_timestamp(r.get("period_or_date"), r.get("title"))
        doc_k = r.get("doc_key") or database.compute_canonical_document_key(
            clean_sym, norm_dt, r.get("period_or_date"), c_url, r.get("title")
        )
        d_item = DocumentItem(
            ticker=clean_sym,
            company_name=detail.name,
            title=r.get("title", ""),
            url=c_url,
            doc_type=norm_dt,
            doc_subtype=r.get("doc_subtype"),
            event_key=r.get("event_key"),
            is_substantive=r.get("is_substantive", True),
            is_wrapper=r.get("is_wrapper", False),
            wrapper_source_url=r.get("wrapper_source_url"),
            ai_eligible=r.get("ai_eligible", True),
            period_or_date=r.get("period_or_date"),
            discovery_source=r.get("discovery_source", "Database"),
            discovered_sources=r.get("discovered_sources") or [r.get("discovery_source", "Database")],
            source_aliases=r.get("source_aliases") or [],
            actual_source_host=r.get("actual_source_host", "bseindia.com"),
            doc_key=doc_k,
            sort_timestamp=sort_ts
        )
        all_items.append(d_item)
        
    all_items.sort(key=lambda x: (x.sort_timestamp or "1970-01-01", x.title), reverse=True)
    doc_links.all_documents = all_items
    for doc in all_items:
        dt = doc.doc_type
        if dt == "annual_report":
            doc_links.annual_reports.append(doc)
        elif dt == "regulatory_annual_filing":
            doc_links.regulatory_annual_filings.append(doc)
        elif dt == "concall_transcript":
            doc_links.concalls.append(doc)
        elif dt == "presentation":
            doc_links.presentations.append(doc)
        elif dt == "announcement":
            doc_links.material_announcements.append(doc)
        elif dt == "brsr_esg":
            doc_links.brsr_reports.append(doc)
        else:
            doc_links.other_filings.append(doc)
            
    doc_intelligence_pipeline.assign_working_set_metadata(doc_links)
    documents_to_analyze = doc_links
        
    try:
        from doc_intelligence_pipeline import run_multi_document_ai_pipeline
        res = run_multi_document_ai_pipeline(
            symbol=clean_sym,
            company_name=detail.name,
            documents=documents_to_analyze,
            save_output=True
        )
        return res
    except Exception as e:
        from llm_service import (
            AIProviderAuthError,
            AIProviderNetworkError,
            AIProviderQuotaError,
            format_ai_error_for_user,
            map_status_code_for_ai_error
        )
        if isinstance(e, (AIProviderAuthError, AIProviderNetworkError, AIProviderQuotaError)):
            status_code = map_status_code_for_ai_error(e)
            safe_detail = format_ai_error_for_user(e)
            raise HTTPException(status_code=status_code, detail=f"AI Document Intelligence generation failed: {safe_detail}")
        raise HTTPException(status_code=500, detail=f"AI Document Intelligence generation failed: {str(e)}")

@app.post("/api/stocks/{symbol}/project", response_model=ProjectionResult)
def project_stock_future(symbol: str, assumptions: ProjectionAssumption):
    data = fetch_stock_from_screener(symbol, force_refresh=False)
    if not data:
        raise HTTPException(status_code=404, detail=f"Stock {symbol} not found")
    ratios = data["ratios"]
    quarters = data["quarters"]
    pl = data["profit_loss"]
    bs = data["balance_sheet"]
    cf = data["cash_flow"]
    analytics = compute_financial_analytics(quarters, pl, bs, cf)
    doc_intel = get_company_doc_intelligence(symbol, financial_analytics=analytics)
    return run_projections(
        ratios=ratios,
        pl=pl,
        bs=bs,
        cf=cf,
        analytics=analytics,
        doc_intel=doc_intel,
        assumptions=assumptions
    )

from projection_engine import generate_scenario_suite

@app.get("/api/stocks/{symbol}/scenario-suite")
def get_stock_scenario_suite(symbol: str):
    data = fetch_stock_from_screener(symbol, force_refresh=False)
    if not data:
        raise HTTPException(status_code=404, detail=f"Stock {symbol} not found")
    ratios = data["ratios"]
    quarters = data["quarters"]
    pl = data["profit_loss"]
    bs = data["balance_sheet"]
    cf = data["cash_flow"]
    analytics = compute_financial_analytics(quarters, pl, bs, cf)
    doc_intel = get_company_doc_intelligence(symbol, financial_analytics=analytics)
    return generate_scenario_suite(
        ratios=ratios,
        pl=pl,
        bs=bs,
        cf=cf,
        analytics=analytics,
        doc_intel=doc_intel
    )

@app.post("/api/stocks/scrape/{symbol}")
def scrape_new_stock(symbol: str):
    clean_sym = symbol.upper().strip()
    # Force refresh directly from live Screener.in and overwrite cache
    data = fetch_stock_from_screener(clean_sym, force_refresh=True)
    if not data:
        raise HTTPException(status_code=400, detail=f"Unable to scrape data for symbol '{clean_sym}' from Screener.in. Please verify ticker.")
    detail = build_full_stock_detail(data)
    return {
        "success": True,
        "message": f"Successfully updated live Screener.in data for {detail.name} ({clean_sym})",
        "stock": detail
    }

class CompareRequest(BaseModel):
    symbols: List[str]

@app.post("/api/stocks/compare")
def compare_stocks(req: CompareRequest):
    comparison = []
    for sym in req.symbols:
        data = fetch_stock_from_screener(sym, force_refresh=False)
        if data:
            detail = build_full_stock_detail(data)
            r = detail.ratios
            comparison.append({
                "symbol": detail.symbol,
                "name": detail.name,
                "sector": detail.sector,
                "current_price": r.current_price,
                "market_cap_cr": r.market_cap_cr,
                "pe_ratio": r.stock_pe,
                "roce_pct": r.roce_pct,
                "roe_pct": r.roe_pct,
                "fcf_yield_pct": r.fcf_yield_pct,
                "debt_to_equity": r.debt_to_equity,
                "interest_coverage": r.interest_coverage,
                "sales_cagr_3yr": detail.analytics.get("growth_rates", {}).get("sales_cagr_3yr"),
                "cfo_to_pat_5yr": detail.analytics.get("cash_flow_quality", {}).get("cfo_to_pat_5yr_pct"),
                "cwip_to_fixed_assets": detail.analytics.get("balance_sheet_efficiency", {}).get("latest_cwip_to_net_block_pct"),
                "composite_score": detail.score.total_composite_score,
                "verdict": detail.score.verdict,
                "dcf_upside_pct": detail.projection.dcf_upside_pct,
                "projected_3yr_irr_pct": detail.projection.projected_3yr_irr_cagr_pct,
                "score_breakdown": {
                    "growth": detail.score.growth_momentum_score,
                    "cash_quality": detail.score.cash_quality_fcf_score,
                    "efficiency": detail.score.capital_efficiency_score,
                    "safety": detail.score.balance_sheet_safety_score,
                    "valuation": detail.score.valuation_margin_score
                }
            })
    return {"comparison": comparison}

# Mount built frontend SPA static files if frontend/dist exists
from starlette.staticfiles import StaticFiles
from fastapi.responses import FileResponse

frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if (frontend_dist / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="assets")

@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    if full_path.startswith("api"):
        raise HTTPException(status_code=404, detail="API endpoint not found")
    file_path = frontend_dist / full_path
    if file_path.exists() and file_path.is_file():
        return FileResponse(str(file_path))
    index_file = frontend_dist / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "Stocker API is running. Build frontend with 'npm run build' to serve UI."}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("BACKEND_PORT", os.environ.get("PORT", "8088")))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
