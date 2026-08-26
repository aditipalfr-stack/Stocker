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

SYSTEM_PROMPT = """You are an institutional fundamental equity analyst extracting rigorous, verifiable facts from company earnings call transcripts and annual reports.

CRITICAL RULES:
1. Work ONLY from the provided document text chunks with [Page X] markers.
2. Do NOT use outside training knowledge, assumptions, or general knowledge.
3. If a metric or topic is NOT explicitly mentioned in the text, return null or an empty list. Never invent or estimate numbers.
4. For EVERY extracted fact, you MUST specify:
   - Exact source page number (e.g. 4, 20) based on the [Page X] marker where the statement appears.
   - Exact verbatim quote snippet (10 to 30 words) from that page proving the claim.
   - Confidence score between 0.8 and 1.0.
5. For 'Plan vs Reality', compare previous management promises/targets in the OLDER document against actual delivered outcomes reported in the LATEST document. Assign status: 'Delivered', 'In Progress', 'Delayed', 'Missed', or 'Not Enough Data'.

Output MUST be a valid JSON object matching this schema:
{
  "plan_vs_reality": [
    {
      "area": "Target Metric or Project",
      "management_promise": "What was stated in earlier document",
      "promised_in_period": "Earlier period name",
      "promise_source_page": 5,
      "promise_quote": "Verbatim quote snippet from earlier doc",
      "actual_outcome": "What actually happened in later doc",
      "actual_in_period": "Later period name",
      "actual_source_page": 4,
      "actual_quote": "Verbatim quote snippet from later doc",
      "status": "Delivered" | "In Progress" | "Delayed" | "Missed" | "Not Enough Data",
      "variance_analysis": "Reason for outcome",
      "confidence": 0.95
    }
  ],
  "growth_pipeline": [
    {
      "initiative": "Project/Plant/M&A name",
      "type": "Capacity / Plant" | "Capex Program" | "M&A / Acquisition" | "New Product / Market",
      "outlay_cr": "Outlay amount or null",
      "target_commissioning": "Timeline or null",
      "current_status": "Execution progress",
      "expected_impact": "Stated business impact or null",
      "source_page": 20,
      "source_quote": "Verbatim quote snippet",
      "confidence": 0.95
    }
  ],
  "demand_and_orders": {
    "order_book_or_tcv": "Order book or TCV value or null",
    "book_to_bill_ratio": "Ratio or null",
    "customer_or_subscriber_growth": "Additions commentary or null",
    "volume_and_pricing_trends": "Volume and realization commentary or null",
    "segment_demand_trends": [{"segment": "...", "trend": "..."}],
    "market_share_signals": "Market share commentary or null",
    "headwinds_and_risks": ["Stated risk 1", "Stated risk 2"],
    "source_page": 8,
    "source_quote": "Verbatim quote snippet",
    "confidence": 0.95
  },
  "cash_and_problems": {
    "cfo_fcf_drivers": "Operating cash flow drivers or null",
    "inventory_and_receivables_audit": "Working capital / inventory / DSO commentary or null",
    "debt_and_leverage_status": "Debt, interest, capex deployment commentary or null",
    "operational_bottlenecks": ["Bottleneck 1", "Bottleneck 2"],
    "source_page": 5,
    "source_quote": "Verbatim quote snippet",
    "confidence": 0.95
  }
}
"""

def get_available_llm_provider() -> Optional[Tuple[str, str]]:
    """
    Checks for available LLM API keys.
    Returns (provider_name, api_key) or None.
    """
    gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if gemini_key:
        return "gemini", gemini_key
    openai_key = os.environ.get("OPENAI_API_KEY")
    if openai_key:
        return "openai", openai_key
    return None

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
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.1
        }
    }
    resp = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=60)
    if resp.status_code != 200:
        raise RuntimeError(f"Gemini API error ({resp.status_code}): {resp.text}")
    data = resp.json()
    raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(raw_text)

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
    older_pages: Optional[List[Tuple[int, str]]] = None
) -> Tuple[bool, Optional[GenericDocumentIntelligenceResult], str]:
    """
    Generic LLM analysis pipeline feeding extracted text pages to an LLM provider.
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
    older_text = format_pages_for_prompt(older_pages) if older_pages else "No older document provided."
    
    prompt = f"""Analyze the provided document text for company '{company_name}' ({symbol}).

LATEST DOCUMENT: '{latest_doc_title}' (URL: {latest_doc_url})
OLDER DOCUMENT (for Plan vs Reality historical comparison): '{older_doc_title or "None"}' (URL: {older_doc_url or "None"})

=== OLDER DOCUMENT TEXT (PREVIOUS PROMISES / TARGETS) ===
{older_text}

=== LATEST DOCUMENT TEXT (CURRENT QUARTER / ACTUAL OUTCOMES) ===
{latest_text}

Extract the 4 required sections (Plan vs Reality, Growth Pipeline, Demand & Orders, Cash & Problems) strictly following the JSON schema.
"""

    try:
        if provider == "gemini":
            raw_json = call_gemini_api(api_key, prompt)
        else:
            raw_json = call_openai_api(api_key, prompt)
            
        # Parse into typed generic Pydantic result
        result = GenericDocumentIntelligenceResult(
            symbol=symbol,
            company_name=company_name,
            latest_document_period=latest_doc_title,
            older_document_period=older_doc_title,
            source_documents=[
                {"title": latest_doc_title, "url": latest_doc_url, "type": "latest_concall"}
            ] + ([{"title": older_doc_title, "url": older_doc_url, "type": "older_baseline"}] if older_doc_title and older_doc_url else []),
            ai_provider_used=f"{provider.upper()}",
            extraction_timestamp="",
            plan_vs_reality=[GenericPlanVsRealityItem(**item) for item in raw_json.get("plan_vs_reality", [])],
            growth_pipeline=[GenericGrowthPipelineItem(**item) for item in raw_json.get("growth_pipeline", [])],
            demand_and_orders=GenericDemandAndOrders(**raw_json.get("demand_and_orders", {})),
            cash_and_problems=GenericCashAndProblems(**raw_json.get("cash_and_problems", {}))
        )
        return True, result, f"Successfully extracted intelligence using {provider.upper()}"
    except Exception as e:
        return False, None, f"Error running LLM extraction with {provider.upper()}: {e}"

