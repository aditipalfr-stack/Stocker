import os
import json
import re
import requests
from typing import List, Tuple, Dict, Any, Optional
from pathlib import Path

import database

try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
    else:
        load_dotenv()
except ImportError:
    pass

from doc_intelligence_models import (
    GenericDocumentIntelligenceResult, GenericPlanVsRealityItem,
    GenericGrowthPipelineItem, GenericDemandAndOrders, GenericCashAndProblems
)

from datetime import datetime, timezone

ANNUAL_REPORT_SUMMARY_PROMPT = """You are an institutional fundamental equity analyst extracting an executive summary from an Audited Annual Report.
Focus strictly on:
- Important business developments & strategic priorities
- Capital expenditure & capacity expansion plans
- Segment performance & operational highlights
- Cash flow, net debt & working capital management
- Major risks, compliance, and long-term management targets

Output MUST be a valid JSON object matching this schema:
{
  "key_takeaways": ["Takeaway 1", "Takeaway 2", "Takeaway 3", "Takeaway 4"],
  "management_tone": "Bullish / Confident" | "Prudent" | "Cautious" | "Neutral",
  "strategic_priorities": "Key long-term strategic roadmap",
  "capex_and_expansion": "Capex numbers and capacity additions",
  "cash_debt_working_capital": "Cash generation, leverage, and working capital commentary",
  "major_risks": ["Key operational/financial risk 1", "Key risk 2"],
  "long_term_targets": "Management's multi-year vision or numerical targets"
}
"""

CONCALL_SUMMARY_PROMPT = """You are an institutional fundamental equity analyst extracting an executive summary from an Earnings Conference Call Transcript.
Focus strictly on:
- Management quarterly guidance & commentary
- Demand environment, order book, deal pipeline
- Margin outlook, pricing power & cost trends
- Capex deployment & execution updates
- Key operational shifts vs previous quarter
- Management tone & analyst Q&A sentiment

Output MUST be a valid JSON object matching this schema:
{
  "key_takeaways": ["Takeaway 1", "Takeaway 2", "Takeaway 3"],
  "management_tone": "Bullish / Confident" | "Prudent" | "Cautious" | "Neutral",
  "management_guidance": "Explicit guidance numbers for sales/margins/capex",
  "demand_and_orders": "Demand commentary, order intake, backlog",
  "margin_outlook": "Margin trajectory and cost pressures",
  "capex_and_execution": "Capex timeline and project execution updates",
  "quarterly_shifts": "Key changes vs prior quarters"
}
"""

PRESENTATION_SUMMARY_PROMPT = """You are an institutional fundamental equity analyst extracting an executive summary from an Investor Presentation.
Focus strictly on:
- Core operational KPIs and market share
- Capacity additions and expansion roadmap
- Segment growth highlights
- Forward-looking financial and operational targets

Output MUST be a valid JSON object matching this schema:
{
  "key_takeaways": ["Takeaway 1", "Takeaway 2", "Takeaway 3"],
  "management_tone": "Bullish / Confident" | "Prudent" | "Cautious" | "Neutral",
  "major_kpis": ["Key KPI 1", "Key KPI 2"],
  "expansion_roadmap": "Capacity additions and project milestones",
  "segment_highlights": ["Segment 1 trajectory", "Segment 2 trajectory"],
  "forward_targets": "Target numbers and expected milestones"
}
"""

ANNOUNCEMENT_SUMMARY_PROMPT = """You are an institutional fundamental equity analyst extracting an executive summary from a Material Exchange Filing / Corporate Announcement.
Focus strictly on:
- What happened (core transaction, order, contract, regulatory development)
- Fundamental importance to the business
- Potential financial and operational impact
- Whether it modifies previous guidance or corporate strategy

Output MUST be a valid JSON object matching this schema:
{
  "key_takeaways": ["Takeaway 1", "Takeaway 2"],
  "event_summary": "Concise summary of the corporate action/announcement",
  "fundamental_importance": "Why this matters fundamentally for equity value",
  "business_and_financial_impact": "Quantifiable revenue, margin, or operational impact",
  "guidance_impact": "Whether this modifies previous guidance or strategy"
}
"""

SYSTEM_PROMPT = """You are an institutional fundamental equity research analyst extracting rigorous, verifiable qualitative claims, management targets, and execution evidence from official corporate filings (Annual Reports, Concalls, Presentations, Announcements).

CRITICAL RULES:
1. Work ONLY from the provided document summaries, tagged text chunks, and audited financial tables.
2. STRICT MULTI-DOCUMENT ATTRIBUTION MANDATE:
   - Every input text chunk begins with a tag header: `=== [DOC #N | Title: ... | Type: ... | URL: ... | Page X] ===`.
   - For EVERY extracted qualitative fact, you MUST specify:
     * `source_doc_title`: The exact Title from the chunk tag where the evidence appears.
     * `source_url`: The exact URL from the chunk tag where the evidence appears. NEVER default to the Annual Report URL if the quote came from a Concall, Presentation, or Announcement!
     * `source_page`: The exact page number from the [Page X] marker.
     * `source_quote`: The exact verbatim quote snippet (10 to 30 words) proving the claim.
     * `confidence`: Score between 0.8 and 1.0.
3. QUALITATIVE EXTRACTION & SEPARATION OF RESPONSIBILITIES:
   - Extract management guidance statements, capacity targets, and forward statements verbatim from earlier baseline documents.
   - Extract subsequently reported business outcomes and progress statements from later documents.
   - DO NOT attempt to compute mathematical CAGR, YoY growth %, margin basis point changes, CFO/PAT ratios, debt variances, or achievement percentages. Code calculates all financial formulas deterministically from structured audited statements.
   - Do NOT populate or compute 'financial_numbers_check'; leave it null or omit it. Deterministic statement checks are performed exclusively by Stocker code.
   - In 'stocker_analysis', summarize the qualitative execution takeaways and operational drivers.
   - For 'source_url_promise', use the baseline document URL. For 'source_url_actual', use the outcome document URL.

Output MUST be a valid JSON object matching this schema:
{
  "what_changed_recently": [
    {
      "headline": "Short headline of recent development",
      "category": "Capex / Expansion" | "Demand / Orders" | "Pricing / Tariff" | "Debt / Cash" | "Strategic / M&A",
      "detail": "Plain English summary of recent change",
      "source_doc_title": "Document title where stated",
      "source_url": "Exact document URL",
      "source_page": 5
    }
  ],
  "growth_drivers": [
    {
      "driver_title": "Expansion initiative, plant, product, or acquisition name",
      "driver_type": "Capacity / Plant" | "New Product / Market" | "M&A / Acquisition" | "Large Contract / Deal",
      "description": "What management is planning and expected business driver",
      "target_timeline": "Timeline or COD if stated",
      "stated_outlay_or_value": "Stated outlay in ₹ Cr or original currency if mentioned",
      "execution_status": "Current execution progress",
      "expected_impact": "Management stated business impact (do not fabricate)",
      "source_doc_title": "Document title where stated",
      "source_url": "Exact document URL",
      "source_page": 20,
      "source_quote": "Verbatim quote snippet",
      "confidence": 0.95
    }
  ],
  "promise_vs_delivery": [
    {
      "area": "Initiative or metric title",
      "management_promise": "What management promised/guided in earlier document",
      "promised_in_period": "Earlier document period",
      "promise_source_doc": "Earlier document title",
      "source_url_promise": "Earlier document URL",
      "promise_source_page": 12,
      "promise_quote": "Verbatim quote from earlier document",
      "actual_outcome": "What actually happened in later document",
      "actual_in_period": "Later document period",
      "actual_source_doc": "Later document title",
      "source_url_actual": "Later document URL",
      "actual_source_page": 44,
      "actual_quote": "Verbatim quote from later document",
      "status": "In Progress" | "Delivered" | "Missed" | "Delayed" | "Not Enough Evidence",
      "stocker_analysis": "Concise qualitative explanation of operational drivers",
      "financial_numbers_check": null,
      "confidence": 0.95
    }
  ],
  "demand_momentum": {
    "summary": "Plain English synthesis of current demand environment",
    "company_specific_metrics": [
      {"metric": "Metric Name e.g. 5G Users / Order Book / TCV", "value": "Metric Value e.g. 130M+ / ₹4.5L Cr"}
    ],
    "segment_trends": [
      {"segment": "Segment Name", "trend": "Segment demand trajectory e.g. +18% YoY growth"}
    ],
    "market_share_and_pricing": "Market share trends and pricing power signals if stated",
    "headwinds_and_risks": ["Stated demand headwinds or client caution"],
    "source_url": "Exact document URL",
    "source_page": 44,
    "source_quote": "Verbatim quote snippet",
    "confidence": 0.95
  },
  "risks_and_cash": {
    "working_capital_and_receivables": "Working capital cycle, inventory days, debtor days",
    "debt_and_capex_burden": "Net debt trajectory, interest costs, capex deployment",
    "margin_and_cost_pressures": "Input cost pressures, pricing headwinds, operating leverage",
    "execution_and_bottlenecks": ["Supply constraints, execution hurdles"],
    "regulatory_or_legal_headwinds": ["Compliance, litigation, regulatory scrutiny"],
    "source_url": "Exact document URL",
    "source_page": 45,
    "source_quote": "Verbatim quote snippet",
    "confidence": 0.95
  },
  "stocker_view": {
    "execution_verdict": "Strong Execution" | "Mixed Execution" | "Weak Execution" | "Evolving / Watchlist",
    "positive_triggers": ["Key upcoming positive triggers"],
    "main_risks": ["Critical fundamental risks to monitor"],
    "what_to_watch_next": ["Specific milestones to watch in next 2-4 quarters"],
    "investor_summary": "Concise, plain-English summary for fundamental investors."
  }
}
"""

def reload_env():
    try:
        from dotenv import load_dotenv
        env_path = Path(__file__).parent.parent / ".env"
        if env_path.exists():
            load_dotenv(dotenv_path=env_path, override=True)
    except Exception:
        pass

def get_available_llm_provider() -> Optional[Tuple[str, str]]:
    """
    Checks for available LLM API keys with dynamic .env reload.
    Returns (provider_name, api_key) or None.
    """
    reload_env()
    gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if gemini_key and gemini_key.strip():
        return "gemini", gemini_key.strip()
    openai_key = os.environ.get("OPENAI_API_KEY")
    if openai_key and openai_key.strip():
        return "openai", openai_key.strip()
    return None

def test_ai_key_connectivity() -> Dict[str, Any]:
    """
    Validates configured AI credentials with a fast connectivity test.
    Returns status: 'active', 'invalid_key', 'quota_exceeded', or 'missing_key'.
    """
    provider_info = get_available_llm_provider()
    if not provider_info:
        return {
            "configured": False,
            "provider": None,
            "status": "missing_key",
            "key_preview": None,
            "message": "No GEMINI_API_KEY or OPENAI_API_KEY found in .env file."
        }
        
    provider, key = provider_info
    masked_key = f"{key[:6]}...{key[-4:]}" if len(key) > 10 else "***"
    
    if provider == "gemini":
        test_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent?key={key}"
        payload = {"contents": [{"parts": [{"text": "Reply with OK"}]}]}
        try:
            r = requests.post(test_url, json=payload, headers={"Content-Type": "application/json"}, timeout=8)
            if r.status_code == 200:
                return {
                    "configured": True,
                    "provider": "Google Gemini (gemini-3.1-flash-lite)",
                    "status": "active",
                    "key_preview": masked_key,
                    "message": "Gemini API key is verified and fully operational."
                }
            elif r.status_code in (400, 403):
                return {
                    "configured": True,
                    "provider": "Google Gemini",
                    "status": "invalid_key",
                    "key_preview": masked_key,
                    "message": f"Gemini API rejected key ({r.status_code}). Please verify your key at https://aistudio.google.com/app/apikey"
                }
            elif r.status_code == 429:
                return {
                    "configured": True,
                    "provider": "Google Gemini",
                    "status": "quota_exceeded",
                    "key_preview": masked_key,
                    "message": "Gemini rate limit or quota exceeded. Please check your Google Cloud / AI Studio quota."
                }
            else:
                return {
                    "configured": True,
                    "provider": "Google Gemini",
                    "status": "error",
                    "key_preview": masked_key,
                    "message": f"Gemini API returned status {r.status_code}: {r.text[:150]}"
                }
        except Exception as e:
            return {
                "configured": True,
                "provider": "Google Gemini",
                "status": "network_error",
                "key_preview": masked_key,
                "message": f"Network connection to Google Gemini failed: {str(e)[:120]}"
            }
    else:
        test_url = "https://api.openai.com/v1/chat/completions"
        payload = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "Reply with OK"}],
            "max_tokens": 5
        }
        try:
            r = requests.post(test_url, json=payload, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, timeout=8)
            if r.status_code == 200:
                return {
                    "configured": True,
                    "provider": "OpenAI (gpt-4o-mini)",
                    "status": "active",
                    "key_preview": masked_key,
                    "message": "OpenAI API key is verified and fully operational."
                }
            else:
                return {
                    "configured": True,
                    "provider": "OpenAI",
                    "status": "invalid_key" if r.status_code in (401, 403) else "error",
                    "key_preview": masked_key,
                    "message": f"OpenAI API returned status {r.status_code}: {r.text[:150]}"
                }
        except Exception as e:
            return {
                "configured": True,
                "provider": "OpenAI",
                "status": "network_error",
                "key_preview": masked_key,
                "message": f"Network connection to OpenAI failed: {str(e)[:120]}"
            }

def is_llm_available() -> bool:
    return get_available_llm_provider() is not None

def format_pages_for_prompt(pages: List[Tuple[int, str]]) -> str:
    """Formats page tuples into structured text chunks tagged with [Page X] markers."""
    formatted_chunks = []
    for page_num, text in pages:
        if text.strip():
            formatted_chunks.append(f"--- [Page {page_num}] ---\n{text.strip()}\n")
    return "\n".join(formatted_chunks)

def call_gemini_api(api_key: str, prompt: str, system_prompt: str = SYSTEM_PROMPT) -> Tuple[Dict[str, Any], str]:
    """Calls Gemini API with resilient multi-model fallback cascade and returns (result_dict, successful_model_name)."""
    import time
    models_to_try = [
        "gemini-3.1-flash-lite",
        "gemini-3.5-flash-lite",
        "gemini-flash-lite-latest",
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-3.7-flash"
    ]
    last_err = None
    for model in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.1
            }
        }
        try:
            print(f"    • Invoking Gemini model: {model}...")
            resp = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=40)
            if resp.status_code == 200:
                data = resp.json()
                raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                return json.loads(raw_text), model
            elif resp.status_code in (404, 503, 429, 500, 502, 504):
                last_err = f"Model {model} returned HTTP {resp.status_code}: {resp.text[:120]}"
                print(f"      ⚠️ {last_err}. Falling back to next available model...")
                time.sleep(1)
                continue
            else:
                raise RuntimeError(f"Gemini API error ({resp.status_code}): {resp.text[:250]}")
        except json.JSONDecodeError as je:
            last_err = f"Model {model} JSON parse error: {je}"
            print(f"      ⚠️ {last_err}. Retrying with next model...")
            continue
        except requests.exceptions.RequestException as re:
            last_err = f"Model {model} network/timeout error: {re}"
            print(f"      ⚠️ {last_err}. Retrying with next model...")
            time.sleep(1)
            continue
        except Exception as e:
            if any(code in str(e) for code in ["404", "503", "429", "timeout"]):
                last_err = str(e)
                continue
            raise e
            
    raise RuntimeError(f"All Gemini models failed. Last error: {last_err}")

def call_openai_api(api_key: str, prompt: str, system_prompt: str = SYSTEM_PROMPT) -> Tuple[Dict[str, Any], str]:
    """Calls OpenAI API and returns (result_dict, model_name)."""
    model = "gpt-4o-mini"
    url = "https://api.openai.com/v1/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.1
    }
    resp = requests.post(url, json=payload, headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, timeout=60)
    if resp.status_code != 200:
        raise RuntimeError(f"OpenAI API error ({resp.status_code}): {resp.text}")
    data = resp.json()
    raw_text = data["choices"][0]["message"]["content"]
    return json.loads(raw_text), model

def summarize_single_document_with_llm(
    symbol: str,
    company_name: str,
    doc_title: str,
    doc_url: str,
    doc_type: str,
    period_or_date: Optional[str],
    pages: List[Tuple[int, str]]
) -> Optional[Dict[str, Any]]:
    """
    Extracts a structured, document-type tailored executive summary for a single filing.
    Used for caching in SQLite (ai_document_summaries) to avoid repeated AI reads.
    """
    provider_info = get_available_llm_provider()
    if not provider_info:
        return None
    provider, api_key = provider_info
    
    pages_text = format_pages_for_prompt(pages)
    prompt = f"""Generate a structured, rigorous executive summary for the following filing of {company_name} ({symbol}):
DOCUMENT TITLE: {doc_title}
DOCUMENT TYPE: {doc_type}
PERIOD / DATE: {period_or_date or "Latest"}
OFFICIAL URL: {doc_url}

=== EXTRACTED FILING TEXT ===
{pages_text}
"""
    # Select document-type specialized system prompt
    norm_type = (doc_type or "").lower().strip()
    if norm_type == "annual_report":
        target_prompt = ANNUAL_REPORT_SUMMARY_PROMPT
    elif norm_type in ("concall_transcript", "concall"):
        target_prompt = CONCALL_SUMMARY_PROMPT
    elif norm_type in ("presentation", "investor_presentation"):
        target_prompt = PRESENTATION_SUMMARY_PROMPT
    else:
        target_prompt = ANNOUNCEMENT_SUMMARY_PROMPT

    try:
        if provider == "gemini":
            raw_json, used_model = call_gemini_api(api_key, prompt, system_prompt=target_prompt)
        else:
            raw_json, used_model = call_openai_api(api_key, prompt, system_prompt=target_prompt)
            
        summary = dict(raw_json)
        summary["doc_title"] = doc_title
        summary["doc_url"] = doc_url
        summary["doc_type"] = doc_type
        summary["period_or_date"] = period_or_date
        summary["model_version"] = used_model
        summary["ai_provider"] = f"{provider.upper()} ({used_model})"
        summary["analyzed_at"] = datetime.now(timezone.utc).isoformat()
        return summary
    except Exception as e:
        print(f"    ⚠️ Failed to generate single doc summary for {doc_title}: {e}")
        return None

def extract_document_intelligence_with_llm(
    symbol: str,
    company_name: str,
    latest_doc_title: str,
    latest_doc_url: str,
    latest_pages: List[Tuple[int, str]],
    older_doc_title: Optional[str] = None,
    older_doc_url: Optional[str] = None,
    older_pages: Optional[List[Tuple[int, str]]] = None,
    financial_statements_summary: Optional[str] = None,
    candidate_documents_meta: Optional[List[Dict[str, str]]] = None,
    precomputed_document_summaries: Optional[List[Dict[str, Any]]] = None,
    tagged_all_documents_text: Optional[str] = None,
    pl_stmt: Optional[Any] = None,
    quarters_stmt: Optional[Any] = None,
    bs_stmt: Optional[Any] = None,
    cf_stmt: Optional[Any] = None
) -> Tuple[bool, Optional[GenericDocumentIntelligenceResult], str]:
    """
    Synthesizes company-level fundamental research using:
    - Pre-computed per-document AI summaries
    - Tagged raw excerpt chunks [Doc ID | Title | Type | URL | Page]
    - 10-year audited financial statements table
    Returns (success, result, message).
    """
    provider_info = get_available_llm_provider()
    if not provider_info:
        return False, None, (
            "AI Provider Unavailable: Neither GEMINI_API_KEY (Google Gemini) nor OPENAI_API_KEY (OpenAI) "
            "is set in the environment. Please configure an API key to execute live LLM inference."
        )

    provider, api_key = provider_info
    
    fin_text = financial_statements_summary or "No reported financial time-series provided."
    
    # Format precomputed summaries section
    summaries_text_lines = []
    if precomputed_document_summaries:
        for idx, s in enumerate(precomputed_document_summaries):
            title = s.get("doc_title", "Filing")
            url = s.get("doc_url", "")
            dtype = s.get("doc_type", "Filing")
            period = s.get("period_or_date", "")
            tone = s.get("management_tone", "Neutral")
            takeaways = s.get("key_takeaways", [])
            guidance = s.get("guidance_and_capex") or s.get("capex_or_guidance_highlight")
            risks = s.get("risks_and_headwinds", [])
            
            summary_block = [
                f"--- [SUMMARY OF DOC #{idx+1}: {title} | Type: {dtype} | Period: {period} | URL: {url}] ---",
                f"Management Tone: {tone}",
                f"Key Takeaways: {'; '.join(takeaways) if takeaways else 'N/A'}",
                f"Guidance & Capex: {guidance or 'None stated'}",
                f"Key Risks: {'; '.join(risks) if risks else 'None stated'}"
            ]
            if s.get("concall_specific"):
                cs = s["concall_specific"]
                if cs.get("demand_commentary"): summary_block.append(f"Demand: {cs['demand_commentary']}")
                if cs.get("order_book_or_pipeline"): summary_block.append(f"Orders/Pipeline: {cs['order_book_or_pipeline']}")
                if cs.get("margin_outlook"): summary_block.append(f"Margin Outlook: {cs['margin_outlook']}")
            if s.get("presentation_specific"):
                ps = s["presentation_specific"]
                if ps.get("expansion_roadmap"): summary_block.append(f"Expansion Roadmap: {ps['expansion_roadmap']}")
                if ps.get("forward_targets"): summary_block.append(f"Forward Targets: {ps['forward_targets']}")
            if s.get("announcement_specific"):
                aspec = s["announcement_specific"]
                if aspec.get("fundamental_importance"): summary_block.append(f"Importance: {aspec['fundamental_importance']}")
                if aspec.get("business_impact"): summary_block.append(f"Impact: {aspec['business_impact']}")
                
            summaries_text_lines.append("\n".join(summary_block))
    
    summaries_section = "\n\n".join(summaries_text_lines) if summaries_text_lines else "No precomputed summaries provided."
    
    # Excerpt chunks text
    if tagged_all_documents_text:
        excerpts_text = tagged_all_documents_text
    else:
        latest_text = format_pages_for_prompt(latest_pages)
        older_text = format_pages_for_prompt(older_pages) if older_pages else "No older baseline document provided."
        excerpts_text = f"=== HISTORICAL BASELINE: {older_doc_title} (URL: {older_doc_url}) ===\n{older_text}\n\n=== LATEST CORPUS: {latest_doc_title} (URL: {latest_doc_url}) ===\n{latest_text}"
        
    prompt = f"""Synthesize comprehensive, institutional fundamental equity research for company '{company_name}' ({symbol}).

======================================================================
1. REPORTED AUDITED 10-YEAR FINANCIAL STATEMENTS (Screener.in Audited Data)
======================================================================
{fin_text}

======================================================================
2. AI-EXTRACTED PER-DOCUMENT EXECUTIVE SUMMARIES (Pre-Computed)
======================================================================
{summaries_section}

======================================================================
3. VERIFIABLE PRIMARY TEXT EXCERPTS & QUOTES (From Official Filings)
======================================================================
{excerpts_text}

======================================================================
SYNTHESIS INSTRUCTIONS:
======================================================================
1. Cross-examine management promises from the baseline document against subsequent outcomes and verified operational milestones.
2. QUALITATIVE EXTRACTION ONLY: Extract management guidance statements, operational milestones, and reported business events verbatim. Do not attempt mathematical calculations; code computes all financial ratios and achievement rates deterministically.
3. ATTRIBUTION MANDATE: For EVERY finding, extract the exact source document Title and URL from the corresponding chunk tag where the evidence appears. NEVER default to an Annual Report URL if the quote is from a Concall or Announcement!
4. Output MUST be valid JSON strictly matching the schema.
"""

    try:
        if provider == "gemini":
            raw_json, used_model = call_gemini_api(api_key, prompt, system_prompt=SYSTEM_PROMPT)
            used_provider = f"GEMINI ({used_model})"
        else:
            raw_json, used_model = call_openai_api(api_key, prompt, system_prompt=SYSTEM_PROMPT)
            used_provider = f"OPENAI ({used_model})"
            
        # Parse into typed generic Pydantic result
        data_to_parse = dict(raw_json)
        data_to_parse["symbol"] = symbol
        data_to_parse["company_name"] = company_name
        data_to_parse["latest_document_period"] = latest_doc_title
        data_to_parse["older_document_period"] = older_doc_title
        
        if candidate_documents_meta:
            data_to_parse["source_documents"] = candidate_documents_meta
        else:
            data_to_parse["source_documents"] = [
                {"title": latest_doc_title, "url": latest_doc_url, "type": "Latest Filing"}
            ] + ([{"title": older_doc_title, "url": older_doc_url, "type": "Baseline Comparison"}] if older_doc_title and older_doc_url else [])
            
        data_to_parse["ai_provider_used"] = used_provider
        data_to_parse["model_version"] = used_model
        if precomputed_document_summaries:
            data_to_parse["document_summaries"] = precomputed_document_summaries
            
        result = GenericDocumentIntelligenceResult(**data_to_parse)
        
        # Strict Citation Sanitization & Attribution Verification
        valid_urls_map = {}
        if candidate_documents_meta:
            for d in candidate_documents_meta:
                u = d.get("url", "").strip()
                t = d.get("title", "").strip()
                if u:
                    valid_urls_map[u] = t
                    
        def _sanitize_citation(url: Optional[str], doc_title: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
            if not url and not doc_title:
                return None, None
            # 1. Exact URL match in verified corpus
            if url and url in valid_urls_map:
                return url, valid_urls_map[url]
            # 2. Confident title match in verified corpus
            if doc_title:
                clean_title = doc_title.lower().strip()
                for v_url, v_title in valid_urls_map.items():
                    clean_v = v_title.lower().strip()
                    if clean_title == clean_v or (len(clean_title) > 8 and clean_title in clean_v) or (len(clean_v) > 8 and clean_v in clean_title):
                        return v_url, v_title
            # 3. Exact URL match to primary baseline documents
            if url and url == latest_doc_url:
                return latest_doc_url, latest_doc_title
            if url and url == older_doc_url:
                return older_doc_url, older_doc_title
            # 4. Strictly reject unmapped / hallucinated URLs or titles
            return None, None

        def _verify_page(doc_url: Optional[str], quote: Optional[str], text_claim: Optional[str]) -> Optional[int]:
            if not doc_url:
                return None
            try:
                cached_pages = database.get_cached_document_pages(doc_url)
                if not cached_pages:
                    return None
                if quote and len(quote.strip()) >= 10:
                    q_clean = quote.lower().strip()
                    q_snippet = q_clean[:25]
                    for p_num, p_text in cached_pages:
                        if q_clean in p_text.lower() or q_snippet in p_text.lower():
                            return p_num
                if text_claim and len(text_claim.strip()) >= 15:
                    words = [w.strip() for w in text_claim.lower().split() if len(w) > 4]
                    if len(words) >= 3:
                        for p_num, p_text in cached_pages:
                            t_low = p_text.lower()
                            matches = sum(1 for w in words if w in t_low)
                            if matches >= min(3, len(words)):
                                return p_num
            except Exception:
                pass
            return None

        # 1. RecentChange: headline, category, detail, source_doc, source_page, source_url
        for c in result.what_changed_recently:
            c.source_url, matched_doc = _sanitize_citation(c.source_url, c.source_doc)
            if matched_doc:
                c.source_doc = matched_doc
            elif not c.source_url:
                c.source_doc = None
            page_match = _verify_page(c.source_url, None, f"{c.headline} {c.detail}")
            if page_match:
                c.source_page = page_match
            elif not c.source_url:
                c.source_page = None
                
        # 2. GrowthDriver: driver_title, driver_type, description, target_timeline, stated_outlay_or_value, execution_status, expected_impact, source_page, source_quote, source_url, confidence
        for g in result.growth_drivers:
            g.source_url, _ = _sanitize_citation(g.source_url, None)
            page_match = _verify_page(g.source_url, g.source_quote, f"{g.driver_title} {g.description}")
            if page_match:
                g.source_page = page_match
            elif not g.source_url:
                g.source_page = None
                g.source_quote = None
                
        # 3. PromiseVsDeliveryItem: area, management_promise, promised_in_period, promise_source_page, promise_quote, actual_outcome, actual_in_period, actual_source_page, actual_quote, status, stocker_analysis, financial_numbers_check, source_url_promise, source_url_actual, confidence
        for p in result.promise_vs_delivery:
            p.source_url_actual, _ = _sanitize_citation(p.source_url_actual, p.actual_in_period)
            p.source_url_promise, _ = _sanitize_citation(p.source_url_promise, p.promised_in_period)
            
            if p.source_url_actual:
                act_page = _verify_page(p.source_url_actual, p.actual_quote, p.actual_outcome)
                if act_page:
                    p.actual_source_page = act_page
            else:
                p.actual_source_page = None
                p.actual_quote = None
                
            if p.source_url_promise:
                prom_page = _verify_page(p.source_url_promise, p.promise_quote, p.management_promise)
                if prom_page:
                    p.promise_source_page = prom_page
            else:
                p.promise_source_page = None
                p.promise_quote = None
                
            if not p.source_url_promise or not p.source_url_actual:
                p.status = "Not Enough Evidence"
            else:
                # Deterministic Chronological & Mathematical Verification in Code
                try:
                    from financial_engine import verify_promise_vs_delivery_item
                    verified_dict = verify_promise_vs_delivery_item(
                        item=p.model_dump(),
                        pl_stmt=pl_stmt,
                        quarters_stmt=quarters_stmt,
                        current_year=None  # Computes runtime UTC datetime
                    )
                    p.status = verified_dict.get("status", "Not Enough Evidence")
                    p.financial_numbers_check = verified_dict.get("financial_numbers_check")
                    if verified_dict.get("stocker_analysis"):
                        p.stocker_analysis = verified_dict["stocker_analysis"]
                except Exception as e:
                    print(f"Notice: Verification engine error on promise item: {e}")
        # 4. DemandMomentum: summary, company_specific_metrics, segment_trends, market_share_and_pricing, headwinds_and_risks, source_page, source_quote, source_url, confidence
        if result.demand_momentum:
            result.demand_momentum.source_url, _ = _sanitize_citation(result.demand_momentum.source_url, None)
            if result.demand_momentum.source_url:
                d_page = _verify_page(result.demand_momentum.source_url, result.demand_momentum.source_quote, result.demand_momentum.summary)
                if d_page:
                    result.demand_momentum.source_page = d_page
            else:
                result.demand_momentum.source_page = None
                result.demand_momentum.source_quote = None

        # 5. RisksAndCashIssues: working_capital_and_receivables, debt_and_capex_burden, margin_and_cost_pressures, execution_and_bottlenecks, regulatory_or_legal_headwinds, reported_numbers_comparison, source_page, source_quote, source_url, confidence
        if result.risks_and_cash:
            result.risks_and_cash.source_url, _ = _sanitize_citation(result.risks_and_cash.source_url, None)
            if result.risks_and_cash.source_url:
                r_page = _verify_page(result.risks_and_cash.source_url, result.risks_and_cash.source_quote, None)
                if r_page:
                    result.risks_and_cash.source_page = r_page
            else:
                result.risks_and_cash.source_page = None
                result.risks_and_cash.source_quote = None
            
        return True, result, "Extraction succeeded"
    except Exception as e:
        return False, None, f"Error running LLM extraction with {provider.upper()}: {e}"


