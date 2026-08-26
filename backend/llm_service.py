import os
import json
import re
import requests
from typing import List, Tuple, Dict, Any, Optional
from pathlib import Path

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

SYSTEM_PROMPT = """You are an institutional fundamental equity research analyst extracting rigorous, verifiable insights by triangulating official corporate filings (Annual Reports, Concall Transcripts, Investor Decks) with audited 10-year reported financial statements (P&L, Balance Sheet, Cash Flow, Quarterly trends).

CRITICAL RULES:
1. Work ONLY from the provided document text chunks with [Page X] markers and the audited financial tables.
2. Do NOT use outside training assumptions or generic boilerplate text.
3. If a metric or topic is NOT explicitly mentioned in the text, return null or an empty list. Never invent numbers or claims.
4. For EVERY extracted qualitative fact, you MUST specify:
   - Exact source page number based on the [Page X] marker where the statement appears.
   - Exact verbatim quote snippet (10 to 30 words) from that page proving the claim.
   - Confidence score between 0.8 and 1.0.
5. QUANTITATIVE TRIANGULATION MANDATE (Promise vs Delivery):
   - Compare management promises/guidance from the baseline document against actual delivered outcomes.
   - Cross-check EVERY guidance claim against the provided REPORTED AUDITED FINANCIAL STATEMENTS table (Sales growth %, OPM %, PAT, CFO/PAT conversion %, Gross Block, CWIP, Debt).
   - In 'financial_numbers_check', state the exact numerical outcome and variance percentage (e.g. 'Promised 20% revenue growth in FY25; audited FY26 P&L shows revenue of ₹58,500 Cr representing 12.3% YoY growth. OPM contracted by 140 bps').
   - Assign status: 'Delivered', 'In Progress', 'Delayed', 'Missed', or 'Not Enough Data'.
6. PER-DOCUMENT EXECUTIVE SUMMARIES:
   - For each distinct filing analyzed, generate a 3-bullet takeaway, management tone, and crucial capex/growth milestone.

Output MUST be a valid JSON object matching this schema:
{
  "what_changed_recently": [
    {
      "headline": "Short headline of recent development",
      "category": "Capex / Expansion" | "Demand / Orders" | "Pricing / Tariff" | "Debt / Cash" | "Strategic / M&A",
      "detail": "Plain English summary of recent change",
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
      "promise_source_page": 12,
      "promise_quote": "Verbatim quote from earlier document",
      "actual_outcome": "What actually happened in later document",
      "actual_in_period": "Later document period",
      "actual_source_page": 44,
      "actual_quote": "Verbatim quote from later document",
      "status": "Delivered" | "In Progress" | "Delayed" | "Missed" | "Not Enough Data",
      "stocker_analysis": "Concise variance explanation of why target was met/delayed/missed",
      "financial_numbers_check": "Exact audited financial statement check (Sales growth %, OPM %, CFO conversion, Debt changes)",
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
  },
  "document_summaries": [
    {
      "doc_title": "Title of filing analyzed",
      "doc_url": "URL of filing",
      "key_takeaways": ["Takeaway bullet 1", "Takeaway bullet 2", "Takeaway bullet 3"],
      "management_tone": "Prudent" | "Confident / Aggressive" | "Cautious" | "Neutral",
      "capex_or_guidance_highlight": "Key capex, growth, or guidance milestone from this filing"
    }
  ]
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
        test_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key={key}"
        payload = {"contents": [{"parts": [{"text": "Reply with OK"}]}]}
        try:
            r = requests.post(test_url, json=payload, headers={"Content-Type": "application/json"}, timeout=8)
            if r.status_code == 200:
                return {
                    "configured": True,
                    "provider": "Google Gemini (gemini-3.6-flash)",
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

def call_gemini_api(api_key: str, prompt: str) -> Dict[str, Any]:
    """Calls Gemini API with resilient multi-model fallback cascade."""
    import time
    models_to_try = [
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-flash-latest",
        "gemini-3.7-flash",
        "gemini-2.5-flash"
    ]
    last_err = None
    for model in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.1
            }
        }
        try:
            print(f"    • Invoking Gemini model: {model}...")
            resp = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=180)
            if resp.status_code == 200:
                data = resp.json()
                raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                return json.loads(raw_text)
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

def call_openai_api(api_key: str, prompt: str) -> Dict[str, Any]:
    url = "https://api.openai.com/v1/chat/completions"
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
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
    return json.loads(raw_text)

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
    candidate_documents_meta: Optional[List[Dict[str, str]]] = None
) -> Tuple[bool, Optional[GenericDocumentIntelligenceResult], str]:
    """
    LLM analysis pipeline feeding multi-document text pages + audited financial time-series.
    Returns (success, result, message).
    """
    provider_info = get_available_llm_provider()
    if not provider_info:
        return False, None, (
            "AI Provider Unavailable: Neither GEMINI_API_KEY (Google Gemini) nor OPENAI_API_KEY (OpenAI) "
            "is set in the environment. Please configure an API key to execute live LLM inference."
        )

    provider, api_key = provider_info
    
    latest_text = format_pages_for_prompt(latest_pages)
    older_text = format_pages_for_prompt(older_pages) if older_pages else "No older baseline document provided."
    
    fin_text = financial_statements_summary or "No reported financial time-series provided."
    
    prompt = f"""Perform comprehensive, institutional fundamental equity research for company '{company_name}' ({symbol}).

======================================================================
1. REPORTED AUDITED FINANCIAL STATEMENTS & TIME-SERIES (Screener.in Data)
======================================================================
{fin_text}

======================================================================
2. HISTORICAL BASELINE DOCUMENT (MANAGEMENT GUIDANCE / TARGETS)
======================================================================
Document: '{older_doc_title or "None"}' (URL: {older_doc_url or "None"})
{older_text}

======================================================================
3. LATEST DOCUMENTS CORPUS (CURRENT ANNUAL REPORT & RECENT CONCALLS)
======================================================================
Document: '{latest_doc_title}' (URL: {latest_doc_url})
{latest_text}

======================================================================
ANALYSIS INSTRUCTIONS:
======================================================================
1. Cross-examine management promises from the baseline document against the LATEST document AND the REPORTED AUDITED FINANCIAL STATEMENTS table above.
2. In 'financial_numbers_check', state the exact numerical outcome and variance percentage (e.g. Sales growth %, OPM %, CFO conversion, Debt changes).
3. For each document in the corpus, provide a concise 3-bullet takeaway in 'document_summaries'.
4. Strictly follow the JSON schema.
"""

    try:
        if provider == "gemini":
            raw_json = call_gemini_api(api_key, prompt)
        else:
            raw_json = call_openai_api(api_key, prompt)
            
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
            
        data_to_parse["ai_provider_used"] = f"{provider.upper()}"
        data_to_parse["model_version"] = "gemini-3.6-flash" if provider == "gemini" else "gpt-4o-mini"
        
        result = GenericDocumentIntelligenceResult(**data_to_parse)
        
        # Ensure URLs are set
        for c in result.what_changed_recently:
            if not c.source_url:
                c.source_url = latest_doc_url
        for g in result.growth_drivers:
            if not g.source_url:
                g.source_url = latest_doc_url
        for p in result.promise_vs_delivery:
            if not p.source_url_actual:
                p.source_url_actual = latest_doc_url
            if not p.source_url_promise:
                p.source_url_promise = older_doc_url or latest_doc_url
                
        if not result.demand_momentum.source_url:
            result.demand_momentum.source_url = latest_doc_url
        if not result.risks_and_cash.source_url:
            result.risks_and_cash.source_url = latest_doc_url
            
        return True, result, "Extraction succeeded"
    except Exception as e:
        return False, None, f"Error running LLM extraction with {provider.upper()}: {e}"


