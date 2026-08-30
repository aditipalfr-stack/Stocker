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
    ProjectionResult, ScoreBreakdown
)
from data_seed import DEFAULT_UNIVERSE_SYMBOLS
from scraper import fetch_stock_from_screener
from financial_engine import compute_financial_analytics
from projection_engine import run_projections
from ranking_engine import compute_stock_score

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
    symbol = stock_data["symbol"]
    name = stock_data["name"]
    sector = stock_data.get("sector", "Diversified")
    industry = stock_data.get("industry", "Indian Equities")
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
    
    # 1. Financial Analytics
    analytics = compute_financial_analytics(quarters, pl, bs, cf)
    
    # 2. Document Intelligence (if available)
    doc_intel = get_company_doc_intelligence(symbol, financial_analytics=analytics)
    
    # 3. Projections & DCF Valuation (grounded in historical parameters + AI forward signals)
    projection = run_projections(
        ratios=ratios,
        pl=pl,
        bs=bs,
        cf=cf,
        analytics=analytics,
        doc_intel=doc_intel,
        assumptions=custom_assumptions
    )
    
    # 4. Multi-Factor Scoring & Thesis (with execution track record and confidence tracking)
    score = compute_stock_score(symbol, name, ratios, analytics, projection, sector=sector, doc_intel=doc_intel)
    
    return StockDetail(
        symbol=symbol,
        name=name,
        sector=sector,
        industry=industry,
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
        fetched_at=fetched_at,
        documents_checked_at=database.get_document_sources_checked_at(symbol) or stock_data.get("documents_checked_at")
    )

@app.get("/api/health")
def health_check():
    return {"status": "healthy", "service": "stocker-backend"}

@app.get("/api/stocks", response_model=List[StockSummary])
def get_all_stocks(sector: Optional[str] = None, min_score: Optional[float] = None):
    results: List[StockSummary] = []
    
    # Universe starts with default symbols
    symbols = list(DEFAULT_UNIVERSE_SYMBOLS)
    
    # Check cache for additional scraped stocks
    cache_file = os.path.join(os.path.dirname(__file__), "data", "stocks_cache.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r") as f:
                cached = json.load(f)
                for sym in cached.keys():
                    if sym not in symbols:
                        symbols.append(sym)
        except Exception:
            pass
            
    details = []
    for sym in symbols:
        data = fetch_stock_from_screener(sym, force_refresh=False)
        if data:
            detail = build_full_stock_detail(data)
            details.append(detail)
            
    # Sort by total composite score descending
    details.sort(key=lambda x: x.score.total_composite_score, reverse=True)
    
    for idx, d in enumerate(details):
        r = d.ratios
        sales_cagr = d.analytics.get("growth_rates", {}).get("sales_cagr_3yr") or r.sales_growth_3yr_cagr or 0.0
        cfo_to_pat = d.analytics.get("cash_flow_quality", {}).get("cfo_to_pat_5yr_pct") or 0.0
        
        summary = StockSummary(
            symbol=d.symbol,
            name=d.name,
            sector=d.sector,
            industry=d.industry,
            current_price=r.current_price,
            market_cap_cr=r.market_cap_cr,
            pe_ratio=r.stock_pe,
            roce_pct=r.roce_pct,
            roe_pct=r.roe_pct,
            fcf_yield_pct=r.fcf_yield_pct or 0.0,
            sales_growth_3yr_pct=sales_cagr,
            cfo_to_pat_5yr_pct=cfo_to_pat,
            net_debt_to_equity=r.debt_to_equity or 0.0,
            composite_score=d.score.total_composite_score,
            verdict=d.score.verdict,
            data_confidence=d.score.data_confidence,
            rank=idx + 1,
            is_top_conviction=(idx < 5 and d.score.total_composite_score >= 70.0),
            investment_thesis_short=d.score.investment_thesis,
            source_name=d.source_name,
            source_url=d.source_url,
            statement_type=d.statement_type,
            fetched_at=d.fetched_at
        )
        
        if sector and sector.lower() not in summary.sector.lower():
            continue
        if min_score and summary.composite_score < min_score:
            continue
            
        results.append(summary)
        
    return results

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

import database
from doc_intelligence_engine import get_company_doc_intelligence
from llm_service import is_llm_available, get_available_llm_provider
from doc_intelligence_pipeline import run_generic_document_pipeline, select_default_document_working_set, fetch_historical_evidence_document

@app.get("/api/stocks/{symbol}/doc-intelligence")
def get_stock_doc_intelligence(symbol: str):
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
        
        # Collect default visible working set
        queued_docs = select_default_document_working_set(detail.documents)
            
    doc_intel = get_company_doc_intelligence(clean_sym, financial_analytics=analytics)
    if not doc_intel:
        return {
            "symbol": clean_sym,
            "company_name": company_name,
            "status": "not_analyzed",
            "message": (
                f"Deep AI fundamental analysis has not been executed for {company_name} ({clean_sym}) yet."
            ),
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
            "document_summaries": []
        }
    return doc_intel

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
    
    # Identify concalls and annual reports
    concalls = detail.documents.concalls or []
    annual_reports = detail.documents.annual_reports or []
    
    latest_url = None
    latest_title = f"{detail.name} Latest Filing"
    older_url = None
    older_title = f"{detail.name} Previous Baseline Filing"
    is_ar = False
    
    if concalls:
        latest_url = concalls[0].url
        latest_title = concalls[0].title or f"{detail.name} Latest Concall"
        if len(concalls) > 1:
            older_url = concalls[1].url
            older_title = concalls[1].title or f"{detail.name} Previous Concall"
    elif annual_reports:
        latest_url = annual_reports[0].url
        latest_title = annual_reports[0].title or f"{detail.name} Latest Annual Report"
        is_ar = True
        if len(annual_reports) > 1:
            older_url = annual_reports[1].url
            older_title = annual_reports[1].title or f"{detail.name} Previous Annual Report"
            
    if not latest_url:
        raise HTTPException(status_code=404, detail=f"No PDF filings found under #documents for {clean_sym}")
        
    try:
        from doc_intelligence_pipeline import run_multi_document_ai_pipeline
        res = run_multi_document_ai_pipeline(
            symbol=clean_sym,
            company_name=detail.name,
            documents=detail.documents,
            save_output=True
        )
        return res
    except Exception as e:
        from llm_service import (
            AIProviderAuthError,
            AIProviderNetworkError,
            AIProviderQuotaError,
            format_ai_error_for_user,
        )
        if isinstance(e, AIProviderAuthError):
            status_code = 401
        elif isinstance(e, AIProviderQuotaError):
            status_code = 429
        elif isinstance(e, AIProviderNetworkError):
            status_code = 503
        else:
            status_code = 500
        safe_detail = format_ai_error_for_user(e, "gemini")
        raise HTTPException(status_code=status_code, detail=f"AI Document Intelligence generation failed: {safe_detail}")

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
                "sales_cagr_3yr": detail.analytics.get("growth_rates", {}).get("sales_cagr_3yr", 0),
                "cfo_to_pat_5yr": detail.analytics.get("cash_flow_quality", {}).get("cfo_to_pat_5yr_pct", 0),
                "cwip_to_fixed_assets": detail.analytics.get("balance_sheet_efficiency", {}).get("latest_cwip_to_net_block_pct", 0),
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
