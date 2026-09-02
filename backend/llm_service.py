import os
import json
import re
import requests
from typing import List, Tuple, Dict, Any, Optional
from pathlib import Path

import database


GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"


class AIServiceError(RuntimeError):
    """Base exception for failures that callers can safely classify."""


class AIProviderNetworkError(AIServiceError):
    """The provider could not be reached because of DNS, connection, or timeout failures."""


class AIProviderAuthError(AIServiceError):
    """The provider rejected the configured credential."""


class AIProviderQuotaError(AIServiceError):
    """The provider rejected the request because its quota or rate limit was exhausted."""


def sanitize_ai_error(error: Any, api_key: Optional[str] = None) -> str:
    """Remove credentials from provider and requests-library error messages."""
    message = str(error)
    message = re.sub(r"([?&]key=)[^&\s'\"]+", r"\1[REDACTED]", message, flags=re.IGNORECASE)
    if api_key:
        message = message.replace(api_key, "[REDACTED]")
    return message


def format_ai_error_for_user(error: Any, provider: str = "gemini") -> str:
    """Convert an internal provider error into a safe, actionable UI message."""
    safe_message = sanitize_ai_error(error)
    lower_message = safe_message.lower()

    if isinstance(error, AIProviderNetworkError) or any(marker in lower_message for marker in (
        "nameresolutionerror",
        "failed to resolve",
        "name resolution",
        "connection error",
        "network/timeout",
    )):
        if provider.lower() == "gemini":
            return (
                "Could not reach Google Gemini because the backend has a DNS/network connection problem. "
                "This is not an API-key error. Check that the backend can resolve and access "
                "generativelanguage.googleapis.com, then retry."
            )
        return "Could not reach the AI provider because the backend has a DNS/network connection problem. Retry after connectivity is restored."

    if isinstance(error, AIProviderAuthError):
        return "Google Gemini rejected the configured API key. Verify or replace the key and try again."
    if isinstance(error, AIProviderQuotaError):
        return "Google Gemini quota or rate limit was exceeded. Check the API project's quota and retry later."

    # Keep useful model/schema context while ensuring a provider response cannot expose a key.
    return safe_message[:500]


def _gemini_headers(api_key: str) -> Dict[str, str]:
    # Sending the key in a header prevents requests from embedding it in exception URLs.
    return {"Content-Type": "application/json", "x-goog-api-key": api_key}

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
import hashlib

# Explicit Extraction & Synthesis Prompt/Schema Versioning
EXTRACTION_SCHEMA_VERSION = "4.4"
EXTRACTION_PROMPT_VERSION = "4.4.1"
COMPANY_SYNTHESIS_PROMPT_VERSION = "4.4.1"

ANNUAL_REPORT_SUMMARY_PROMPT = """You are an institutional fundamental equity analyst extracting an executive summary from a company Annual Report.
Focus strictly on:
- Important business developments & strategic priorities
- Capital expenditure & capacity expansion plans
- Segment performance & operational highlights
- Cash flow, net debt & working capital management
- Major risks, compliance, and long-term management targets
- Specific quantitative facts, operational KPIs (ARPU, capacity, order book, margins, volumes), and targets

Output MUST be a valid JSON object matching this schema:
{
  "key_takeaways": ["Takeaway 1", "Takeaway 2", "Takeaway 3", "Takeaway 4"],
  "management_tone": "Bullish / Confident" | "Prudent" | "Cautious" | "Neutral",
  "strategic_priorities": "Key long-term strategic roadmap",
  "capex_and_expansion": "Capex numbers and capacity additions",
  "cash_debt_working_capital": "Cash generation, leverage, and working capital commentary",
  "major_risks": ["Key operational/financial risk 1", "Key risk 2"],
  "long_term_targets": "Management's multi-year vision or numerical targets",
  "extracted_facts": [
    {
      "metric_name": "EBITDA Margin / ARPU / Capacity / Revenue / Order Book / Stores",
      "stated_value_raw": "52% / ₹245 / 1 GW / ₹14,500 Cr",
      "numeric_value": 52.0,
      "unit": "% / ₹ / MW / ₹ Cr / bps / units",
      "period_or_date": "FY26",
      "target_period": null,
      "category": "financial_metric" | "operational_kpi" | "management_guidance" | "strategic_initiative",
      "scope": "Consolidated" | "Standalone" | "Segment",
      "claim_type": "reported_fact" | "management_guidance" | "management_target",
      "source_quote": "Verbatim quote snippet",
      "source_page": 15
    }
  ]
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
- Specific stated KPIs, volume metrics, price movements, and forward guidance numbers

Output MUST be a valid JSON object matching this schema:
{
  "key_takeaways": ["Takeaway 1", "Takeaway 2", "Takeaway 3"],
  "management_tone": "Bullish / Confident" | "Prudent" | "Cautious" | "Neutral",
  "management_guidance": "Explicit guidance numbers for sales/margins/capex",
  "demand_and_orders": "Demand commentary, order intake, backlog",
  "margin_outlook": "Margin trajectory and cost pressures",
  "capex_and_execution": "Capex timeline and project execution updates",
  "quarterly_shifts": "Key changes vs prior quarters",
  "extracted_facts": [
    {
      "metric_name": "Metric Name e.g. Guidance Revenue Growth / Order Inflow / Utilization",
      "stated_value_raw": "14-16% / ₹8,200 Cr / 85%",
      "numeric_value": 15.0,
      "unit": "% / ₹ Cr / bps",
      "period_or_date": "Q3 FY26",
      "target_period": "FY27",
      "category": "management_guidance" | "operational_kpi" | "financial_metric",
      "scope": "Consolidated",
      "claim_type": "management_guidance" | "reported_fact",
      "source_quote": "Verbatim quote snippet",
      "source_page": 6
    }
  ]
}
"""

PRESENTATION_SUMMARY_PROMPT = """You are an institutional fundamental equity analyst extracting an executive summary from an Investor Presentation.
Focus strictly on:
- Core operational KPIs and market share
- Capacity additions and expansion roadmap
- Segment growth highlights
- Forward-looking financial and operational targets
- Quantitative operational milestones (stores, megawatts, subscriber metrics, capacity utilization)

Output MUST be a valid JSON object matching this schema:
{
  "key_takeaways": ["Takeaway 1", "Takeaway 2", "Takeaway 3"],
  "management_tone": "Bullish / Confident" | "Prudent" | "Cautious" | "Neutral",
  "major_kpis": ["Key KPI 1", "Key KPI 2"],
  "expansion_roadmap": "Capacity additions and project milestones",
  "segment_highlights": ["Segment 1 trajectory", "Segment 2 trajectory"],
  "forward_targets": "Target numbers and expected milestones",
  "extracted_facts": [
    {
      "metric_name": "Solar Capacity / Subscriber Count / Store Count / ARPU",
      "stated_value_raw": "420 MW / 125M / 1,450 Stores / ₹230",
      "numeric_value": 420.0,
      "unit": "MW / Subscribers / Stores / ₹",
      "period_or_date": "Q2 FY26",
      "target_period": null,
      "category": "operational_kpi" | "management_guidance",
      "scope": "Consolidated",
      "claim_type": "reported_fact" | "management_target",
      "source_quote": "Verbatim quote snippet",
      "source_page": 10
    }
  ]
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
  "guidance_impact": "Whether this modifies previous guidance or strategy",
  "extracted_facts": [
    {
      "metric_name": "Order Win / Outlay / Acquisition Value / Capacity Addition",
      "stated_value_raw": "₹1,200 Cr / 100 MW",
      "numeric_value": 1200.0,
      "unit": "₹ Cr / MW",
      "period_or_date": "Announcement Date",
      "target_period": null,
      "category": "strategic_initiative" | "operational_kpi",
      "scope": "Consolidated",
      "claim_type": "reported_fact",
      "source_quote": "Verbatim quote snippet",
      "source_page": 1
    }
  ]
}
"""

SYSTEM_PROMPT = """You are an institutional fundamental equity research analyst synthesizing rigorous, verifiable qualitative claims, management targets, and execution evidence from official corporate filings (Annual Reports, Concalls, Presentations, Announcements).

CRITICAL INSTITUTIONAL RULES:
1. WORK ONLY FROM SUPPLIED EVIDENCE: Work ONLY from the provided document summaries, tagged text chunks, and standardized financial statement tables. Do NOT invent guidance, do NOT invent causal mechanisms, and do NOT extrapolate beyond stated facts.
2. STRICT MULTI-DOCUMENT ATTRIBUTION MANDATE:
   - Every input text chunk begins with a tag header: `=== [DOC #N | Title: ... | Type: ... | URL: ... | Page X] ===`.
   - For EVERY extracted qualitative fact, you MUST specify:
     * `source_doc_title`: The exact Title from the chunk tag where the evidence appears.
     * `source_url`: The exact URL from the chunk tag where the evidence appears. NEVER default to the Annual Report URL if the quote came from a Concall, Presentation, or Announcement!
     * `source_page`: The exact page number from the [Page X] marker.
     * `source_quote`: The exact verbatim quote snippet (10 to 30 words) proving the claim.
     * `confidence`: Score between 0.8 and 1.0.
3. CONCISE, NON-REPETITIVE & INVESTOR-RELEVANT:
   - Prefer 3 to 5 strong, high-signal items per section. Avoid long verbose paragraphs.
   - Avoid vague buzzwords like "robust", "strong", "healthy", "significant" unless accompanied by concrete comparative metrics (e.g. "accelerated from X% to Y%").
   - Do NOT repeat the identical KPI finding across multiple views.
4. FOUR CANONICAL VIEWS:
   A. WHAT CHANGED:
      - Answer: "What is materially different now versus the previous comparable period?" (QoQ, YoY, or FY-on-FY).
      - Include: headline, category, direction (POSITIVE | NEGATIVE | NEUTRAL | MIXED), period_comparison (e.g. "Q1 FY27 vs Q4 FY26"), is_one_off (true if non-recurring event like tax-refund interest), detail (1-2 sentences explaining why it matters).
      - Do NOT merely state raw KPI movements without interpretation.
   B. GROWTH / BUSINESS DRIVERS:
      - Answer: "What is actually driving current growth, demand, profitability, or business momentum?"
      - Separate driver types: 'Structural Driver' | 'Cyclical Driver' | 'Management Action' | 'External Environment' | 'One-off Driver'.
      - If a metric improved due to a one-off: MUST label as 'One-off Driver' and set is_one_off = true.
      - Sector-Awareness: For Banks, focus on loan mix, deposit mobilization, CASA, NIM, credit costs, asset quality, fee income, capital. For Corporates, focus on volume, pricing, utilization, order backlog, capex, market share.
   C. PROMISE VS DELIVERY:
      - Compare: CURRENT YEAR / CURRENT PERIOD vs PREVIOUS YEAR / PRIOR MANAGEMENT PROMISE.
      - A Promise MUST be an explicit management guidance, numerical target/range, explicit timeline, or observable strategic commitment.
      - Do NOT infer promises from generic strategy platitudes (e.g. "we remain focused on profitable growth").
      - Status MUST be: 'Delivered' | 'On Track' | 'Partially Delivered' | 'Delayed' | 'Missed' | 'Not Yet Measurable' | 'Not Enough Evidence'.
      - If no measurable guidance was given in baseline filings: provide an item with management_promise = "No measurable prior management promise found.", status = "Not Enough Evidence", stocker_analysis = "Baseline filings contained general strategy discussion without measurable numerical guidance targets."
   D. RISKS & STOCKER VIEW:
      - NOT AN INVESTMENT RECOMMENDATION: Strictly FORBIDDEN from using "Buy", "Strong Buy", "Hold", "Sell".
      - Separate: Critical Risks (3-5 items with severity, current vs potential, metric to watch), Opportunities, Watch Items, and Stocker View (execution verdict, business momentum, financial quality, evidence confidence, investor summary).
5. TRUTH INTEGRITY & SEPARATION OF RESPONSIBILITIES:
   - DO NOT attempt mathematical calculations; code computes all financial ratios and achievement rates deterministically.
   - Leave 'financial_numbers_check' null.
   - Preserve 'STANDARDIZED HISTORICAL FINANCIAL STATEMENTS' wording; do NOT call them audited/officially verified unless explicitly verified.

Output MUST be a valid JSON object matching this schema:
{
  "what_changed_recently": [
    {
      "headline": "Short, factual headline of recent material shift",
      "category": "Margins / Funding Costs" | "Asset Quality / Provisions" | "Business Mix" | "Demand / Volumes" | "Capex / Expansion" | "Debt / Cash" | "Strategic / M&A" | "Regulatory / Policy",
      "direction": "POSITIVE" | "NEGATIVE" | "NEUTRAL" | "MIXED",
      "period_comparison": "e.g. Q1 FY27 vs Q4 FY26 / FY26 vs FY25",
      "is_one_off": false,
      "why_it_matters": "Why this development is fundamentally material",
      "detail": "Plain English summary of recent change and context (1-2 sentences)",
      "source_doc_title": "Document title where stated",
      "source_url": "Exact document URL",
      "source_page": 5,
      "source_quote": "Verbatim quote snippet proving claim"
    }
  ],
  "growth_drivers": [
    {
      "driver_title": "Expansion initiative, loan vertical, plant, product, or market expansion name",
      "driver_type": "Structural Driver" | "Cyclical Driver" | "Management Action" | "External Environment" | "One-off Driver",
      "is_one_off": false,
      "description": "What is driving growth/performance and why (1-2 sentences)",
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
      "area": "Initiative or metric title e.g. Margin Trajectory / Branch Expansion / Digital Loan Share / Capacity COD",
      "management_promise": "EXPLICIT PROMISE/GUIDANCE: What management guided or promised in earlier filing",
      "promised_in_period": "Earlier document period e.g. FY25 AR / Q3 FY26 Concall",
      "promise_source_doc": "Earlier document title",
      "source_url_promise": "Earlier document URL",
      "promise_source_page": 12,
      "promise_quote": "Verbatim quote from earlier document",
      "actual_outcome": "REPORTED OUTCOME: What actually happened in later document",
      "actual_in_period": "Later document period e.g. FY26 AR / Q1 FY27 Concall",
      "actual_source_doc": "Later document title",
      "source_url_actual": "Later document URL",
      "actual_source_page": 44,
      "actual_quote": "Verbatim quote from later document",
      "status": "Delivered" | "On Track" | "Partially Delivered" | "Delayed" | "Missed" | "Not Yet Measurable" | "Not Enough Evidence",
      "stocker_analysis": "STOCKER INTERPRETATION: Concise variance analysis explaining operational drivers",
      "financial_numbers_check": null,
      "confidence": 0.95
    }
  ],
  "demand_momentum": {
    "summary": "Plain English synthesis of current demand environment",
    "company_specific_metrics": [
      {"metric": "Metric Name e.g. Loan Growth / CASA / Order Book / TCV", "value": "Metric Value e.g. 19.6% / 43.6% / ₹4.5L Cr"}
    ],
    "segment_trends": [
      {"segment": "Segment Name", "trend": "Segment demand trajectory e.g. +35.4% YoY rural growth"}
    ],
    "market_share_and_pricing": "Market share trends and pricing power signals if stated",
    "headwinds_and_risks": ["Stated demand headwinds or client caution"],
    "source_url": "Exact document URL",
    "source_page": 44,
    "source_quote": "Verbatim quote snippet",
    "confidence": 0.95
  },
  "risks_and_cash": {
    "working_capital_and_receivables": "Working capital cycle, inventory days, debtor days (Corporate only; 'Not applicable to banking' for banks)",
    "debt_and_capex_burden": "Net debt trajectory, interest costs, capex commitments, capital adequacy (CET-1/CRAR for banks)",
    "margin_and_cost_pressures": "Input cost pressures, pricing headwinds, operating leverage, funding costs, credit costs",
    "execution_and_bottlenecks": ["Specific supply constraints, commissioning delays, execution hurdles"],
    "regulatory_or_legal_headwinds": ["Compliance, litigation, regulatory scrutiny, policy changes"],
    "risk_items": [
      {
        "risk_title": "Short title of critical risk",
        "risk_category": "Asset Quality" | "Margin Compression" | "Customer Concentration" | "Regulatory / Legal" | "Leverage" | "Execution" | "Cyclicality" | "Funding / Liquidity",
        "severity": "HIGH" | "MEDIUM" | "LOW",
        "is_current_or_potential": "CURRENT" | "POTENTIAL",
        "evidence_statement": "Evidence-backed description of the risk",
        "metric_to_watch": "What metric/document would confirm improvement or deterioration",
        "source_url": "Exact document URL",
        "source_page": 15
      }
    ],
    "source_url": "Exact document URL",
    "source_page": 45,
    "source_quote": "Verbatim quote snippet",
    "confidence": 0.95
  },
  "stocker_view": {
    "execution_verdict": "Strong Execution" | "Mixed Execution" | "Weak Execution" | "Evolving / Watchlist",
    "business_momentum": "Acceleration" | "Steady Growth" | "Moderating" | "Contracting",
    "financial_quality": "High Quality" | "Adequate" | "Under Pressure" | "Distressed",
    "evidence_confidence": "High" | "Moderate" | "Low / Incomplete",
    "positive_triggers": ["Key upcoming positive triggers / opportunities"],
    "main_risks": ["Critical fundamental risks to monitor"],
    "what_to_watch_next": ["Specific milestones to watch in next 2-4 quarters"],
    "investor_summary": "Concise, plain-English summary for fundamental investors. Strictly no buy/sell recommendations."
  },
  "evidence_items": [
    {
      "id": "evi_1",
      "evidence_type": "MANAGEMENT_GUIDANCE" | "DEMAND_DRIVER" | "SUPPLY_DRIVER" | "CAPEX_PLAN" | "CAPACITY_EXPANSION" | "MARGIN_DRIVER" | "COST_PRESSURE" | "ORDER_BOOK" | "CUSTOMER_CONCENTRATION" | "GEOGRAPHIC_EXPOSURE" | "NEW_PRODUCT" | "REGULATORY_RISK" | "COMPETITIVE_RISK" | "CAPITAL_ALLOCATION" | "WORKING_CAPITAL_COMMENTARY" | "MANAGEMENT_COMMITMENT" | "KPI" | "OTHER_MATERIAL_EVIDENCE",
      "title": "Short, clear title of this evidence item",
      "normalized_topic": "Topic e.g. Loan Growth / Capex / Revenue / Margins / Asset Quality",
      "statement": "Fact or claim directly extracted from filing",
      "source_document_type": "annual_report" | "concall_transcript" | "presentation" | "announcement",
      "source_document_title": "Document Title from chunk header",
      "source_url": "Exact document URL",
      "source_period": "FY26 / Q3 FY26",
      "source_page": 12,
      "evidence_quote": "Verbatim quote snippet proving claim",
      "confidence": "HIGH" | "MEDIUM" | "LOW"
    }
  ],
  "management_guidance_items": [
    {
      "metric_or_topic": "Revenue Growth / EBITDA Margin / Capex / Deposit Growth / Loan Growth / Net NPA",
      "guidance_text": "Exact guidance text stated by management",
      "quantified_value": 15.0,
      "quantified_range_min": null,
      "quantified_range_max": null,
      "unit": "% / ₹ Cr / bps / GW",
      "target_period": "FY26 / FY27 / Q4 FY26",
      "direction": "GROWTH" | "MARGIN_EXPANSION" | "CAPEX" | "MAINTAIN" | "REDUCTION",
      "source_document_title": "Document title where stated",
      "source_document_url": "Exact document URL",
      "source_date_or_period": "Q3 FY26 / FY25",
      "confidence": "HIGH"
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
        test_url = f"{GEMINI_API_BASE}/models/gemini-3.1-flash-lite:generateContent"
        payload = {"contents": [{"parts": [{"text": "Reply with OK"}]}]}
        try:
            r = requests.post(test_url, json=payload, headers=_gemini_headers(key), timeout=8)
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
        except requests.exceptions.RequestException:
            return {
                "configured": True,
                "provider": "Google Gemini",
                "status": "network_error",
                "key_preview": masked_key,
                "message": (
                    "Could not reach Google Gemini because the backend has a DNS/network connection problem. "
                    "The configured key was not rejected; check backend internet and DNS access."
                )
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
        url = f"{GEMINI_API_BASE}/models/{model}:generateContent"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.1
            }
        }
        print(f"    • Invoking Gemini model: {model}...")
        for network_attempt in range(3):
            try:
                resp = requests.post(url, json=payload, headers=_gemini_headers(api_key), timeout=40)
                if resp.status_code == 200:
                    data = resp.json()
                    raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                    return json.loads(raw_text), model
                if resp.status_code in (401, 403):
                    raise AIProviderAuthError("Gemini rejected the configured API key.")
                if resp.status_code == 429:
                    raise AIProviderQuotaError("Gemini quota or rate limit was exceeded.")
                if resp.status_code in (404, 500, 502, 503, 504):
                    last_err = f"Model {model} returned HTTP {resp.status_code}: {resp.text[:120]}"
                    print(f"      ⚠️ {last_err}. Falling back to next available model...")
                    time.sleep(1)
                    break
                raise AIServiceError(f"Gemini API error ({resp.status_code}): {resp.text[:250]}")
            except json.JSONDecodeError as json_error:
                last_err = f"Model {model} JSON parse error: {json_error}"
                print(f"      ⚠️ {last_err}. Retrying with next model...")
                break
            except requests.exceptions.ConnectionError as network_error:
                # Every model uses the same hostname, so switching models cannot fix DNS/connectivity.
                if network_attempt < 2:
                    time.sleep(0.5 * (2 ** network_attempt))
                    continue
                safe_error = sanitize_ai_error(network_error, api_key)
                raise AIProviderNetworkError(f"Gemini network connection failed after 3 attempts: {safe_error}") from network_error
            except requests.exceptions.Timeout as timeout_error:
                if network_attempt < 2:
                    time.sleep(0.5 * (2 ** network_attempt))
                    continue
                safe_error = sanitize_ai_error(timeout_error, api_key)
                raise AIProviderNetworkError(f"Gemini request timed out after 3 attempts: {safe_error}") from timeout_error
            except requests.exceptions.RequestException as request_error:
                safe_error = sanitize_ai_error(request_error, api_key)
                raise AIProviderNetworkError(f"Gemini network request failed: {safe_error}") from request_error
            
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

    raw_pages_text = "".join(text for _, text in pages) if pages else ""
    content_hash = hashlib.sha256(raw_pages_text.encode("utf-8")).hexdigest()

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
        summary["provider"] = provider.upper()
        summary["model"] = used_model
        summary["content_hash"] = content_hash
        summary["extraction_schema_version"] = EXTRACTION_SCHEMA_VERSION
        summary["extraction_prompt_version"] = EXTRACTION_PROMPT_VERSION
        summary["cache_status"] = "NEWLY_EXTRACTED"
        summary["analyzed_at"] = datetime.now(timezone.utc).isoformat()
        
        # Enrich and persist extracted knowledge facts
        facts_list = summary.get("extracted_facts", [])
        clean_facts = []
        if isinstance(facts_list, list):
            for f in facts_list:
                if isinstance(f, dict):
                    f_item = dict(f)
                    f_item["symbol"] = symbol.upper().strip()
                    f_item["doc_url"] = doc_url
                    f_item["doc_title"] = doc_title
                    f_item["doc_type"] = doc_type
                    if not f_item.get("period_or_date"):
                        f_item["period_or_date"] = period_or_date
                    # Ensure numeric_value is float if parsable
                    if f_item.get("numeric_value") is None and f_item.get("stated_value_raw"):
                        m_num = re.search(r'[-+]?\d*\.?\d+', str(f_item["stated_value_raw"]))
                        if m_num:
                            try:
                                f_item["numeric_value"] = float(m_num.group(0))
                            except Exception:
                                pass
                    clean_facts.append(f_item)
            summary["extracted_facts"] = clean_facts
            try:
                database.save_company_knowledge_facts(symbol, clean_facts, clear_doc_urls=[doc_url])
            except Exception as e_db:
                print(f"Notice: Could not persist knowledge facts for {doc_title}: {e_db}")
                
        # Persist single document summary in SQLite with provenance
        try:
            database.save_document_summary(
                symbol=symbol,
                doc_url=doc_url,
                doc_title=doc_title,
                summary_data=summary,
                doc_type=doc_type,
                period_or_date=period_or_date,
                content_hash=content_hash,
                extraction_schema_version=EXTRACTION_SCHEMA_VERSION,
                extraction_prompt_version=EXTRACTION_PROMPT_VERSION,
                provider=provider.upper(),
                model=used_model
            )
        except Exception as e_save:
            print(f"Notice: Could not cache document summary for {doc_title}: {e_save}")
            
        return summary
    except AIServiceError:
        # A provider outage should stop this run instead of being retried once per document.
        raise
    except Exception as e:
        print(f"    ⚠️ Failed to generate single doc summary for {doc_title}: {e}")
        return None

def sanitize_citation(
    url: Optional[str],
    doc_title: Optional[str],
    candidate_documents_meta: Optional[List[Dict[str, Any]]] = None,
    latest_doc_url: Optional[str] = None,
    latest_doc_title: Optional[str] = None,
    older_doc_url: Optional[str] = None,
    older_doc_title: Optional[str] = None
) -> Tuple[Optional[str], Optional[str]]:
    """
    Strict Citation Sanitization & Attribution Verification:
    Maps a cited URL or Title to a verified document in the candidate corpus.
    Fails closed and returns (None, None) for hallucinated/unmapped references.
    """
    if not url and not doc_title:
        return None, None
        
    valid_urls_map = {}
    if candidate_documents_meta:
        for d in candidate_documents_meta:
            u = d.get("url", "").strip()
            t = d.get("title", "").strip()
            if u:
                valid_urls_map[u] = t

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

def verify_citation_page(doc_url: Optional[str], quote: Optional[str], text_claim: Optional[str]) -> Optional[int]:
    """Verifies page occurrence in cached document pages."""
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

def sanitize_and_verify_intelligence_result(
    result: GenericDocumentIntelligenceResult,
    symbol: str,
    candidate_documents_meta: Optional[List[Dict[str, Any]]] = None,
    latest_doc_url: Optional[str] = None,
    latest_doc_title: Optional[str] = None,
    older_doc_url: Optional[str] = None,
    older_doc_title: Optional[str] = None,
    pl_stmt: Optional[Any] = None,
    quarters_stmt: Optional[Any] = None,
    bs_stmt: Optional[Any] = None,
    cf_stmt: Optional[Any] = None,
    precomputed_document_summaries: Optional[List[Dict[str, Any]]] = None,
    financial_business_model: str = "GENERAL_CORPORATE"
) -> GenericDocumentIntelligenceResult:
    """
    Sanitizes all citations in extracted intelligence, rejects unmapped sources,
    verifies page numbers, enforces sector-safety and truth categories, and evaluates management guidance deterministically.
    """
    is_bank = (financial_business_model == "BANK")

    # 1. RecentChange: headline, category, detail, direction, period_comparison, is_one_off, source_doc, source_page, source_url
    clean_changes = []
    for c in result.what_changed_recently:
        c.source_url, matched_doc = sanitize_citation(
            c.source_url, c.source_doc, candidate_documents_meta,
            latest_doc_url, latest_doc_title, older_doc_url, older_doc_title
        )
        if matched_doc:
            c.source_doc = matched_doc
        elif not c.source_url:
            c.source_doc = None
        page_match = verify_citation_page(c.source_url, getattr(c, "source_quote", None), f"{c.headline} {c.detail}")
        if page_match:
            c.source_page = page_match
        elif not c.source_url:
            c.source_page = None

        # Check for one-off / non-recurring indicators (e.g. tax refund interest)
        detail_low = f"{c.headline} {c.detail}".lower()
        if any(w in detail_low for w in ["tax refund", "one-off", "one off", "exceptional item", "non-recurring", "prior period item", "write-back"]):
            c.is_one_off = True

        # Normalize direction
        if c.direction not in ("POSITIVE", "NEGATIVE", "NEUTRAL", "MIXED"):
            c.direction = "NEUTRAL"

        clean_changes.append(c)
    result.what_changed_recently = clean_changes
            
    # 2. GrowthDriver: driver_title, driver_type, description, is_one_off, target_timeline, stated_outlay_or_value, execution_status, expected_impact, source_page, source_quote, source_url, confidence
    clean_drivers = []
    for g in result.growth_drivers:
        g.source_url, matched_doc = sanitize_citation(
            g.source_url, getattr(g, "source_doc_title", None), candidate_documents_meta,
            latest_doc_url, latest_doc_title, older_doc_url, older_doc_title
        )
        if matched_doc:
            g.source_doc_title = matched_doc
        page_match = verify_citation_page(g.source_url, g.source_quote, f"{g.driver_title} {g.description}")
        if page_match:
            g.source_page = page_match
        elif not g.source_url:
            g.source_page = None
            g.source_quote = None

        desc_low = f"{g.driver_title} {g.description}".lower()
        if g.is_one_off or g.driver_type == "One-off Driver" or any(w in desc_low for w in ["tax refund", "one-off", "one off", "exceptional gain", "non-recurring"]):
            g.is_one_off = True
            g.driver_type = "One-off Driver"

        # Bank Safety: Reject industrial FCF/CWIP drivers for banks
        if is_bank and any(w in desc_low for w in ["working capital cycle", "debtor days", "inventory days", "industrial fcf", "cwip conversion"]):
            continue

        clean_drivers.append(g)
    result.growth_drivers = clean_drivers
            
    # 3. PromiseVsDeliveryItem
    clean_promises = []
    for p in result.promise_vs_delivery:
        p.source_url_actual, matched_act_doc = sanitize_citation(
            p.source_url_actual, p.actual_in_period, candidate_documents_meta,
            latest_doc_url, latest_doc_title, older_doc_url, older_doc_title
        )
        if matched_act_doc and not p.actual_source_doc:
            p.actual_source_doc = matched_act_doc

        p.source_url_promise, matched_prom_doc = sanitize_citation(
            p.source_url_promise, p.promised_in_period, candidate_documents_meta,
            latest_doc_url, latest_doc_title, older_doc_url, older_doc_title
        )
        if matched_prom_doc and not p.promise_source_doc:
            p.promise_source_doc = matched_prom_doc
        
        if p.source_url_actual:
            act_page = verify_citation_page(p.source_url_actual, p.actual_quote, p.actual_outcome)
            if act_page:
                p.actual_source_page = act_page
        else:
            p.actual_source_page = None
            p.actual_quote = None
            
        if p.source_url_promise:
            prom_page = verify_citation_page(p.source_url_promise, p.promise_quote, p.management_promise)
            if prom_page:
                p.promise_source_page = prom_page
        else:
            p.promise_source_page = None
            p.promise_quote = None
            
        if not p.source_url_promise or not p.source_url_actual:
            p.status = "Not Enough Evidence"
            if "no measurable" in str(p.management_promise).lower():
                p.stocker_analysis = "No measurable prior management promise found in baseline filings."
                p.financial_numbers_check = "Baseline filings contained general strategy discussion without measurable numerical guidance targets."
        else:
            try:
                from financial_engine import verify_promise_vs_delivery_item
                verified_dict = verify_promise_vs_delivery_item(
                    item=p.model_dump(),
                    pl_stmt=pl_stmt,
                    quarters_stmt=quarters_stmt,
                    current_year=None
                )
                p.status = verified_dict.get("status", "Not Enough Evidence")
                p.financial_numbers_check = verified_dict.get("financial_numbers_check")
                if verified_dict.get("stocker_analysis"):
                    p.stocker_analysis = verified_dict["stocker_analysis"]
            except Exception as e:
                print(f"Notice: Verification engine error on promise item: {e}")

        clean_promises.append(p)

    if not clean_promises:
        from doc_intelligence_models import PromiseVsDeliveryItem
        clean_promises.append(PromiseVsDeliveryItem(
            area="Corporate Guidance & Execution",
            management_promise="No measurable prior management promise found in baseline filings.",
            promised_in_period="Baseline Filing",
            actual_outcome="No quantifiable guidance target was disclosed in baseline filings.",
            actual_in_period="Latest Results",
            status="Not Enough Evidence",
            stocker_analysis="Baseline filings contained general business strategy without measurable numerical guidance targets or verifiable completion deadlines.",
            financial_numbers_check="No structured forward-guidance numbers found in earlier annual reports.",
            confidence=1.0
        ))
    result.promise_vs_delivery = clean_promises

    # 4. DemandMomentum
    if result.demand_momentum:
        result.demand_momentum.source_url, _ = sanitize_citation(
            result.demand_momentum.source_url, None, candidate_documents_meta,
            latest_doc_url, latest_doc_title, older_doc_url, older_doc_title
        )
        if result.demand_momentum.source_url:
            d_page = verify_citation_page(result.demand_momentum.source_url, result.demand_momentum.source_quote, result.demand_momentum.summary)
            if d_page:
                result.demand_momentum.source_page = d_page
        else:
            result.demand_momentum.source_page = None
            result.demand_momentum.source_quote = None

    # 5. RisksAndCashIssues
    if result.risks_and_cash:
        if is_bank:
            result.risks_and_cash.working_capital_and_receivables = "Not applicable to banking operations."
        result.risks_and_cash.source_url, _ = sanitize_citation(
            result.risks_and_cash.source_url, None, candidate_documents_meta,
            latest_doc_url, latest_doc_title, older_doc_url, older_doc_title
        )
        if result.risks_and_cash.source_url:
            r_page = verify_citation_page(result.risks_and_cash.source_url, result.risks_and_cash.source_quote, None)
            if r_page:
                result.risks_and_cash.source_page = r_page
        else:
            result.risks_and_cash.source_page = None
            result.risks_and_cash.source_quote = None

        if hasattr(result.risks_and_cash, "risk_items") and isinstance(result.risks_and_cash.risk_items, list):
            sanitized_risks = []
            for r_item in result.risks_and_cash.risk_items:
                if isinstance(r_item, dict):
                    r_url, _ = sanitize_citation(
                        r_item.get("source_url"), None, candidate_documents_meta,
                        latest_doc_url, latest_doc_title, older_doc_url, older_doc_title
                    )
                    r_item["source_url"] = r_url or ""
                    sanitized_risks.append(r_item)
            result.risks_and_cash.risk_items = sanitized_risks

    # 6. StockerView: Prohibit AI Investment Recommendations & Enforce Risk Register Authority
    if result.stocker_view:
        s_summary = result.stocker_view.investor_summary or ""
        for prohibited in ["Buy", "Strong Buy", "Sell", "Strong Sell", "Hold"]:
            s_summary = re.sub(rf'\b{prohibited}\b', 'Watchlist / Neutral Stance', s_summary, flags=re.IGNORECASE)
        result.stocker_view.investor_summary = s_summary.strip()
        if not result.stocker_view.evidence_confidence:
            result.stocker_view.evidence_confidence = "High"

        # Hero Critical Risks strictly derived from validated risk register
        if result.risks_and_cash and getattr(result.risks_and_cash, "risk_items", None):
            hero_risks = []
            for r in result.risks_and_cash.risk_items:
                r_dict = r if isinstance(r, dict) else (r.model_dump() if hasattr(r, "model_dump") else {})
                t = r_dict.get("risk_title")
                d = r_dict.get("description") or ""
                if t:
                    hero_risks.append(f"{t}: {d}".strip(" :"))
            result.stocker_view.main_risks = hero_risks
        else:
            result.stocker_view.main_risks = []

        # Deterministic Fail-Closed Execution Verdict
        if result.promise_vs_delivery:
            from financial_engine import compute_fail_closed_execution_verdict
            result.stocker_view.execution_verdict = compute_fail_closed_execution_verdict(result.promise_vs_delivery)
        else:
            result.stocker_view.execution_verdict = "Insufficient History"

    # 6. Integrated Persistent Company Knowledge & Triangulation Layer
    all_facts: List[Dict[str, Any]] = []
    try:
        from financial_engine import process_and_verify_company_knowledge
        if precomputed_document_summaries:
            for s in precomputed_document_summaries:
                for f in s.get("extracted_facts", []):
                    if isinstance(f, dict):
                        all_facts.append(f)
        db_facts = database.get_company_knowledge_facts(symbol)
        seen_fact_keys = set()
        merged_facts = []
        for f in (all_facts + db_facts):
            key = (f.get("metric_name", ""), f.get("period_or_date", ""), f.get("doc_url", ""))
            if key not in seen_fact_keys:
                seen_fact_keys.add(key)
                merged_facts.append(f)
                
        stock_data_pkg = {
            "profit_loss": pl_stmt,
            "quarters": quarters_stmt,
            "balance_sheet": bs_stmt,
            "cash_flow": cf_stmt
        }
        
        projection_pkg = None
        try:
            from projection_engine import generate_scenario_suite
            from models import KeyRatios, FinancialStatement
            from financial_engine import get_row_values
            cached_stock = database.get_stock_cache(symbol) or {}
            r_dict = cached_stock.get("ratios")
            if r_dict:
                ratios_obj = KeyRatios(**r_dict) if isinstance(r_dict, dict) else r_dict
                analytics = cached_stock.get("analytics") or {}
                pl_obj = FinancialStatement(**pl_stmt) if isinstance(pl_stmt, dict) else pl_stmt
                bs_obj = FinancialStatement(**bs_stmt) if isinstance(bs_stmt, dict) else bs_stmt
                cf_obj = FinancialStatement(**cf_stmt) if isinstance(cf_stmt, dict) else cf_stmt
                
                scenario_suite = generate_scenario_suite(
                    ratios=ratios_obj,
                    pl=pl_obj,
                    bs=bs_obj,
                    cf=cf_obj,
                    analytics=analytics,
                    doc_intel=None
                )
                base_case = scenario_suite.get("base_case")
                bull_case = scenario_suite.get("bull_case")
                bear_case = scenario_suite.get("bear_case")
                
                base_sales = base_case.assumptions.revenue_growth_rate_pct if base_case else None
                bull_sales = bull_case.assumptions.revenue_growth_rate_pct if bull_case else None
                bear_sales = bear_case.assumptions.revenue_growth_rate_pct if bear_case else None
                target_opm = base_case.assumptions.target_opm_pct if base_case else None
                capex_sales = base_case.assumptions.capex_pct_of_sales if base_case else None
                
                base_pat_cagr = None
                bull_pat_cagr = None
                bear_pat_cagr = None
                if base_case and len(base_case.projections) >= 3:
                    y_pat = get_row_values(pl_obj, "Net Profit") or get_row_values(pl_obj, "PAT") if pl_obj else {}
                    y_periods = pl_obj.periods if pl_obj else []
                    latest_pat = y_pat.get(y_periods[-1], 0.0) if y_periods else 0.0
                    if latest_pat > 0:
                        yr3_pat_base = base_case.projections[2].pat_cr
                        if yr3_pat_base > 0:
                            base_pat_cagr = round(((yr3_pat_base / latest_pat) ** (1.0 / 3.0) - 1.0) * 100.0, 1)
                        if bull_case and len(bull_case.projections) >= 3:
                            yr3_pat_bull = bull_case.projections[2].pat_cr
                            if yr3_pat_bull > 0:
                                bull_pat_cagr = round(((yr3_pat_bull / latest_pat) ** (1.0 / 3.0) - 1.0) * 100.0, 1)
                        if bear_case and len(bear_case.projections) >= 3:
                            yr3_pat_bear = bear_case.projections[2].pat_cr
                            if yr3_pat_bear > 0:
                                bear_pat_cagr = round(((yr3_pat_bear / latest_pat) ** (1.0 / 3.0) - 1.0) * 100.0, 1)

                projection_pkg = {
                    "revenue_growth_rate_pct": base_sales,
                    "base_sales_cagr": base_sales,
                    "bull_sales_cagr": bull_sales,
                    "bear_sales_cagr": bear_sales,
                    "target_opm_pct": target_opm,
                    "capex_pct_of_sales": capex_sales,
                    "base_pat_cagr": base_pat_cagr,
                    "bull_pat_cagr": bull_pat_cagr,
                    "bear_pat_cagr": bear_pat_cagr,
                    "projection_source": "Stocker DCF Projection Engine"
                }
        except Exception as e_proj:
            print(f"Notice: Projection derivation skipped during knowledge verification: {e_proj}")
            projection_pkg = None

        knowledge_res = process_and_verify_company_knowledge(
            symbol=symbol,
            facts_list=merged_facts,
            stock_data=stock_data_pkg,
            projection_assumptions=projection_pkg
        )
        
        from doc_intelligence_models import VerifiedFactComparison, InterDocumentKPITrend, GuidanceVsProjection
        result.verified_facts = [VerifiedFactComparison(**vf) for vf in knowledge_res.get("verified_facts", [])]
        result.operational_kpi_evolution = [InterDocumentKPITrend(**it) for it in knowledge_res.get("operational_kpi_evolution", [])]
        result.guidance_vs_projections = [GuidanceVsProjection(**gp) for gp in knowledge_res.get("guidance_vs_projections", [])]
    except Exception as e_k:
        print(f"Notice: Knowledge verification engine error: {e_k}")

    # 7. Document Evidence Items: Validate source URLs, titles, and verify pages
    from doc_intelligence_models import DocumentEvidenceItem
    sanitized_evidence: List[DocumentEvidenceItem] = []
    for idx, ev in enumerate(result.evidence_items):
        ev.symbol = symbol
        s_url, matched_doc = sanitize_citation(
            ev.source_url, ev.source_document_title, candidate_documents_meta,
            latest_doc_url, latest_doc_title, older_doc_url, older_doc_title
        )
        if s_url:
            ev.source_url = s_url
            if matched_doc:
                ev.source_document_title = matched_doc
            page_match = verify_citation_page(ev.source_url, ev.evidence_quote, f"{ev.title} {ev.statement}")
            if page_match:
                ev.page = page_match
            ev.status = "SUPPORTED"
        else:
            ev.source_url = ""
            ev.status = "UNSUPPORTED"
            ev.confidence = "LOW"
        if not ev.id:
            from database import generate_deterministic_evidence_id
            ev.id = generate_deterministic_evidence_id(symbol, {
                "source_url": ev.source_url,
                "evidence_type": ev.evidence_type,
                "normalized_topic": ev.normalized_topic,
                "title": ev.title,
                "statement": ev.statement
            })
        sanitized_evidence.append(ev)
    result.evidence_items = sanitized_evidence

    # 8. Management Guidance Items: Fail closed on unverified sources, evaluate deterministically
    sanitized_guidance = []
    for g in result.management_guidance_items:
        g_url, g_doc = sanitize_citation(
            g.source_document_url, g.source_document_title, candidate_documents_meta,
            latest_doc_url, latest_doc_title, older_doc_url, older_doc_title
        )
        if g_url:
            g.source_document_url = g_url
            if g_doc:
                g.source_document_title = g_doc
            g.source_support_status = "SUPPORTED"
        else:
            g.source_document_url = ""
            g.source_support_status = "UNSUPPORTED"
            g.confidence = "LOW"
            g.status = "INSUFFICIENT_EVIDENCE"
            g.comparison_detail = "Unverified source filing; guidance cannot be verified against actuals."
        if not g.id:
            from database import generate_deterministic_guidance_id
            g.id = generate_deterministic_guidance_id(symbol, {
                "metric_or_topic": g.metric_or_topic,
                "target_period": g.target_period,
                "guidance_text": g.guidance_text,
                "source_document_title": g.source_document_title,
                "source_document_url": g.source_document_url
            })
        sanitized_guidance.append(g)
    result.management_guidance_items = sanitized_guidance

    try:
        from doc_intelligence_engine import evaluate_management_guidance_vs_actual
        eval_guidance = evaluate_management_guidance_vs_actual(
            guidance_items=result.management_guidance_items,
            financial_statements={"profit_loss": pl_stmt, "quarters": quarters_stmt, "balance_sheet": bs_stmt, "cash_flow": cf_stmt},
            knowledge_facts=all_facts,
            business_model=financial_business_model
        )
        result.management_guidance_items = eval_guidance
    except Exception as e_g:
        print(f"Notice: Guidance evaluation engine error: {e_g}")

    result.financial_business_model = financial_business_model
    return result

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
    cf_stmt: Optional[Any] = None,
    financial_business_model: str = "GENERAL_CORPORATE"
) -> Tuple[bool, Optional[GenericDocumentIntelligenceResult], str]:
    """
    Synthesizes company-level fundamental research using:
    - Pre-computed per-document AI summaries
    - Tagged raw excerpt chunks [Doc ID | Title | Type | URL | Page]
    - 10-year standardized historical financial statements table
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
        
    if financial_business_model == "BANK":
        sector_instructions = """
======================================================================
BANK SECTOR-SPECIFIC INSTRUCTIONS:
======================================================================
This company is classified as a BANK / LENDING INSTITUTION.
- Focus evidence extraction strictly on: Loan/Advances Growth, Deposit Growth, CASA Ratio, Asset Quality (Gross NPA, Net NPA, Slippages, PCR), Credit Cost / Provisions, Net Interest Margin (NIM), Cost-to-Income Ratio, Capital Adequacy (CRAR / Tier-1 Ratio), ROA, ROE, Branch network & Digital expansion.
- DO NOT extract or interpret Industrial Free Cash Flow (FCF), Working Capital (Debtor Days / Inventory Days), or Capital Work in Progress (CWIP) for Banks.
"""
    else:
        sector_instructions = """
======================================================================
CORPORATE SECTOR INSTRUCTIONS:
======================================================================
- Focus evidence extraction on: Revenue Drivers, Volume Growth, Pricing / Realization, Operating Margins (OPM / EBITDA), Capex & Capacity Additions, CWIP Commissioning, Working Capital & Debtor Days, Order Book / Pipeline, Customer Concentration, Geographic Mix, Capital Allocation.
"""

    prompt = f"""Synthesize comprehensive, institutional fundamental equity research for company '{company_name}' ({symbol}).

======================================================================
1. STANDARDIZED HISTORICAL FINANCIAL STATEMENTS (Standardized Statement Inputs)
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
{sector_instructions}
======================================================================
SYNTHESIS INSTRUCTIONS:
======================================================================
1. Cross-examine management promises from the baseline document against subsequent outcomes and verified operational milestones.
2. QUALITATIVE EXTRACTION ONLY: Extract management guidance statements, operational milestones, and reported business events verbatim. Do not attempt mathematical calculations; code computes all financial ratios and achievement rates deterministically.
3. PROVENANCE & TRUTH INTEGRITY:
   - The financial table provides standardized financial-statement inputs; do NOT call them officially verified or audited merely because they are present.
   - Official verification status is supplied separately by Stocker when available. Do not upgrade provenance through wording.
4. ATTRIBUTION MANDATE: For EVERY finding, extract the exact source document Title and URL from the corresponding chunk tag where the evidence appears. NEVER default to an Annual Report URL if the quote is from a Concall or Announcement!
5. Output MUST be valid JSON strictly matching the schema.
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
            
        if "evidence_items" in data_to_parse and isinstance(data_to_parse["evidence_items"], list):
            for ev in data_to_parse["evidence_items"]:
                if isinstance(ev, dict) and not ev.get("symbol"):
                    ev["symbol"] = symbol
                    
        result = GenericDocumentIntelligenceResult(**data_to_parse)
        
        result = sanitize_and_verify_intelligence_result(
            result=result,
            symbol=symbol,
            candidate_documents_meta=candidate_documents_meta,
            latest_doc_url=latest_doc_url,
            latest_doc_title=latest_doc_title,
            older_doc_url=older_doc_url,
            older_doc_title=older_doc_title,
            pl_stmt=pl_stmt,
            quarters_stmt=quarters_stmt,
            bs_stmt=bs_stmt,
            cf_stmt=cf_stmt,
            precomputed_document_summaries=precomputed_document_summaries,
            financial_business_model=financial_business_model
        )

        return True, result, "Extraction succeeded"
    except AIServiceError:
        raise
    except Exception as e:
        return False, None, f"Error running LLM extraction with {provider.upper()}: {format_ai_error_for_user(e, provider)}"

