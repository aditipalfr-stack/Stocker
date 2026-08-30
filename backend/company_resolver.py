"""
=============================================================================
Stocker Company Identity Resolver & Discovery Engine (Phase A)
=============================================================================
This module provides canonical company identity resolution, local registry search,
and external fallback discovery (e.g. Screener company search API).

Separation of concerns:
- SEARCH: Resolves names, symbols, partials, and aliases to canonical identity candidates.
- FETCH: Uses canonical ticker symbol to ingest standardized financial statements on demand.
=============================================================================
"""

import re
import json
import requests
from typing import Dict, Any, List, Optional, Tuple

import database

# Search Query Alias expansion mapping (Used strictly for search query matching / ranking, NEVER for security identity rewrite)
POPULAR_SEARCH_ALIASES: Dict[str, str] = {
    "RIL": "RELIANCE",
    "HUL": "HINDUNILVR",
    "TISCO": "TATASTEEL",
    "L&T": "LT",
    "AIRTEL": "BHARTIARTL",
    "JIO": "RELIANCE"
}

def normalize_symbol(symbol: str) -> str:
    """
    Normalizes a stock ticker symbol:
    - Uppercase & strip whitespace
    - Removes exchange suffixes (.NS, .BO, :NSE, :BSE, -EQ)
    - Strips invalid characters
    NOTE: Never silently rewrites ticker identity to avoid incorrectly merging securities.
    """
    if not symbol:
        return ""
    clean = symbol.strip().upper()
    # Remove exchange suffixes
    for suffix in [".NS", ".BO", ":NSE", ":BSE", "-EQ", ".BSE", ".NSE"]:
        if clean.endswith(suffix):
            clean = clean[:-len(suffix)]
            break
    clean = re.sub(r"[^A-Z0-9&_-]", "", clean)
    return clean

def clean_company_name(name: str) -> str:
    """Cleans company name string by normalizing whitespace and noise."""
    if not name:
        return ""
    cleaned = name.replace("\xa0", " ").strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned

def extract_symbol_from_url_slug(url_slug: str) -> Optional[str]:
    """
    Extracts stock ticker symbol from a Screener URL slug e.g.:
    '/company/BHARTIARTL/consolidated/' -> 'BHARTIARTL'
    '/company/500325/' -> '500325'
    '/company/RELIANCE/' -> 'RELIANCE'
    """
    if not url_slug:
        return None
    match = re.search(r"/company/([A-Za-z0-9&_-]+)", url_slug)
    if match:
        raw_sym = match.group(1).upper().strip()
        return normalize_symbol(raw_sym)
    return None

def calculate_match_score(query: str, candidate: Dict[str, Any]) -> int:
    """
    Calculates match quality score (0 - 100) based on ranking preference:
    1. Exact NSE symbol / symbol match (100)
    2. Exact company name match (90)
    3. Symbol prefix match (80)
    4. Exact alias match (75)
    5. Company name prefix match (70)
    6. Substring / partial match on name or aliases (50 - 65)
    """
    q = query.strip().lower()
    if not q:
        return 0
        
    sym = (candidate.get("symbol") or "").strip().lower()
    nse = (candidate.get("nse_symbol") or "").strip().lower()
    name = (candidate.get("company_name") or "").strip().lower()
    bse = (str(candidate.get("bse_code") or "")).strip().lower()
    
    aliases = candidate.get("aliases") or []
    if isinstance(aliases, str):
        try:
            aliases = json.loads(aliases)
        except Exception:
            aliases = [aliases]
    aliases_lower = [str(a).strip().lower() for a in aliases]

    # Check search query alias expansion
    expanded_target = POPULAR_SEARCH_ALIASES.get(query.strip().upper(), "").lower()

    # 1. Exact Symbol match
    if q == sym or q == nse or (bse and q == bse):
        return 100
        
    # 2. Exact Company Name match
    if q == name:
        return 90
        
    # 3. Exact Alias match or Popular Search Query Alias match (Direct user intention e.g. 'RIL' -> RELIANCE)
    if q in aliases_lower or (expanded_target and (sym == expanded_target or nse == expanded_target)):
        return 85

    # 4. Symbol Prefix match
    if sym.startswith(q) or (nse and nse.startswith(q)):
        return 80
        
    # 5. Company Name Prefix match
    if name.startswith(q):
        return 70
        
    # 6. Word-boundary / prefix in company name words (e.g. 'Airtel' in 'Bharti Airtel Limited')
    words = name.split()
    if any(w.startswith(q) for w in words):
        return 65
        
    # 7. Substring in Symbol
    if q in sym or (nse and q in nse):
        return 60
        
    # 8. Substring in Company Name
    if q in name:
        return 55
        
    # 9. Substring in any alias
    if any(q in a for a in aliases_lower):
        return 50
        
    return 10

def search_screener_company_discovery(query: str) -> List[Dict[str, Any]]:
    """
    Queries Screener.in company search API strictly as an external discovery fallback.
    Treats results strictly as unverified discovery candidates (source='screener_search').
    NOTE: Screener internal integer 'id' is NOT a BSE code and is NEVER mapped to bse_code.
    """
    clean_q = query.strip()
    if not clean_q:
        return []
        
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.5"
    }
    
    candidates: List[Dict[str, Any]] = []
    try:
        url = f"https://www.screener.in/api/company/search/?q={requests.utils.quote(clean_q)}"
        resp = requests.get(url, headers=headers, timeout=6)
        if resp.status_code == 200:
            results = resp.json()
            if isinstance(results, list):
                for item in results:
                    name = clean_company_name(item.get("name", ""))
                    rel_url = item.get("url", "")
                    sym = extract_symbol_from_url_slug(rel_url)
                    if not sym:
                        sym = normalize_symbol(name.split()[0] if name else "")
                    if not sym:
                        continue
                        
                    # Screener internal 'id' is NOT an exchange BSE code. Keep bse_code and isin None.
                    candidates.append({
                        "symbol": sym,
                        "company_name": name or sym,
                        "nse_symbol": sym,
                        "bse_code": None,
                        "isin": None,
                        "exchange": "NSE",
                        "sector": None,
                        "industry": None,
                        "aliases": [name, sym],
                        "source": "screener_search"
                    })
    except Exception as e:
        print(f"Notice: Screener discovery search failed for '{clean_q}': {e}")
        
    return candidates

def resolve_and_search_companies(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Master company search & identity resolution service:
    1. Searches local persistent registry.
    2. Also searches for popular alias targets if applicable.
    3. If needed or to discover new companies, queries external search fallback.
    4. Deduplicates candidates and checks current universe enrollment.
    5. Ranks by match score, universe status, and relevance.
    """
    clean_q = query.strip()
    if not clean_q:
        return []
        
    # 1. Local Registry Search
    local_matches = database.search_local_registry(clean_q, limit=limit * 2)
    
    # Check if query has an alias expansion
    alias_target = POPULAR_SEARCH_ALIASES.get(clean_q.upper())
    if alias_target:
        alias_matches = database.search_local_registry(alias_target, limit=limit)
        local_matches.extend(alias_matches)
        
    seen_symbols = set()
    combined_candidates: List[Dict[str, Any]] = []
    
    for item in local_matches:
        sym = item.get("symbol", "").upper().strip()
        if sym and sym not in seen_symbols:
            seen_symbols.add(sym)
            item["already_added"] = bool(item.get("in_universe") and item.get("is_active"))
            item["source"] = item.get("source") or "local"
            combined_candidates.append(item)
            
    # 2. External Fallback Discovery if local results are few or no exact match
    has_exact_local = any(
        c.get("symbol", "").upper() == clean_q.upper() or 
        c.get("company_name", "").lower() == clean_q.lower()
        for c in combined_candidates
    )
    
    if len(combined_candidates) < 5 or not has_exact_local:
        external_results = search_screener_company_discovery(clean_q)
        for ext in external_results:
            sym = ext.get("symbol", "").upper().strip()
            if sym and sym not in seen_symbols:
                seen_symbols.add(sym)
                # Check if it exists in local DB under another query form
                db_item = database.get_company_by_symbol(sym)
                if db_item:
                    db_item["already_added"] = bool(db_item.get("in_universe") and db_item.get("is_active"))
                    db_item["source"] = db_item.get("source") or "local"
                    combined_candidates.append(db_item)
                else:
                    ext["already_added"] = False
                    combined_candidates.append(ext)

    # 3. Calculate Scores & Rank
    scored_results = []
    for cand in combined_candidates:
        score = calculate_match_score(clean_q, cand)
        cand["match_score"] = score
        scored_results.append(cand)
        
    # Sort: Higher match score first, then already_added, then length of name
    scored_results.sort(
        key=lambda x: (
            x.get("match_score", 0),
            1 if x.get("already_added") else 0,
            -len(x.get("company_name", ""))
        ),
        reverse=True
    )
    
    return scored_results[:limit]

def resolve_canonical_company(symbol_or_name: str) -> Optional[Dict[str, Any]]:
    """
    Resolves a symbol or company name to its canonical identity candidate.
    Checks local registry first, then discovery if missing.
    If completely unresolved, returns an explicit unverified ticker candidate without fabricated metadata.
    """
    clean = symbol_or_name.strip()
    if not clean:
        return None
        
    norm_sym = normalize_symbol(clean)
    
    # 1. Exact local registry lookup
    local_item = database.get_company_by_symbol(norm_sym) or database.get_company_by_symbol(clean)
    if local_item:
        return local_item
        
    # 2. Search resolver
    candidates = resolve_and_search_companies(clean, limit=1)
    if candidates:
        top = candidates[0]
        if top.get("match_score", 0) >= 70:
            return top
            
    # 3. Explicit unverified candidate (no fabricated BSE code, ISIN, or sector)
    return {
        "symbol": norm_sym,
        "company_name": clean,
        "nse_symbol": norm_sym,
        "bse_code": None,
        "isin": None,
        "exchange": "NSE",
        "sector": None,
        "industry": None,
        "aliases": [clean],
        "source": "unresolved_input",
        "in_universe": True,
        "is_active": True
    }
