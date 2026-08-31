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

def normalize_company_title(name: str) -> str:
    """Normalizes company title by stripping corporate legal entity noise and punctuation."""
    if not name:
        return ""
    clean = name.lower()
    # remove legal suffixes & geographical qualifiers
    clean = re.sub(r"\b(limited|ltd|pvt|private|corporation|corp|inc|incorporated|holdings|holding|india|co)\b", "", clean)
    clean = re.sub(r"[^a-z0-9\s]", " ", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean

def calculate_match_score(query: str, candidate: Dict[str, Any]) -> int:
    """
    Calculates match quality score (0 - 100) based on ranking preference:
    1. Exact NSE symbol / symbol match (100)
    2. Exact company name match (90)
    3. Normalized company title match (95)
    4. Exact alias match or Popular Search Query Alias match (85)
    5. Symbol Prefix match (80)
    6. Company Name Prefix match (70)
    7. Word-boundary / token overlap match (65 - 88)
    8. Substring in Symbol or Name (50 - 60)
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
        
    # 3. Normalized Title Match (e.g. "Colgate-Palmolive (India) Ltd" vs "Colgate-Palmolive (India) Limited")
    norm_q = normalize_company_title(query)
    norm_name = normalize_company_title(name)
    if norm_q and norm_name:
        if norm_q == norm_name:
            return 95
        q_tokens = set(norm_q.split())
        name_tokens = set(norm_name.split())
        if q_tokens and name_tokens:
            overlap = q_tokens.intersection(name_tokens)
            if len(overlap) == len(q_tokens) or len(overlap) == len(name_tokens):
                return 88
            elif len(overlap) >= 1 and (len(overlap) / max(len(q_tokens), len(name_tokens))) >= 0.5:
                return 75

    # 4. Exact Alias match or Popular Search Query Alias match (Direct user intention e.g. 'RIL' -> RELIANCE)
    if q in aliases_lower or (expanded_target and (sym == expanded_target or nse == expanded_target)):
        return 85

    # 5. Symbol Prefix match
    if sym.startswith(q) or (nse and nse.startswith(q)):
        return 80
        
    # 6. Company Name Prefix match
    if name.startswith(q):
        return 70
        
    # 7. Word-boundary / prefix in company name words (e.g. 'Airtel' in 'Bharti Airtel Limited')
    words = name.split()
    if any(w.startswith(q) for w in words):
        return 65
        
    # 8. Substring in Symbol
    if q in sym or (nse and q in nse):
        return 60
        
    # 9. Substring in Company Name
    if q in name:
        return 55
        
    # 10. Substring in any alias
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
                        
                    candidates.append({
                        "symbol": sym,
                        "company_name": name or sym,
                        "nse_symbol": None,
                        "bse_code": None,
                        "isin": None,
                        "exchange": None,
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
            name = ext.get("company_name", "")
            if sym and sym not in seen_symbols:
                seen_symbols.add(sym)
                # Check if it exists in local DB under canonical symbol, BSE code, or name
                db_item = (
                    database.get_company_by_symbol(sym) or 
                    (database.get_company_by_bse_code(sym) if sym.isdigit() else None) or
                    database.get_company_by_name(name)
                )
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

def resolve_proven_security_for_add(symbol_or_query: str) -> Tuple[Optional[Dict[str, Any]], bool, List[Dict[str, Any]]]:
    """
    Strict security resolver for the ADD COMPANY flow.
    Fails closed:
    - Never returns unverified / fabricated placeholder securities.
    - If multiple plausible securities match: returns (None, True, candidates).
    - If proven unique security is established: returns (canonical_security, False, [canonical_security]).
    - If unresolved: returns (None, False, candidates).
    """
    clean_q = symbol_or_query.strip()
    if not clean_q:
        return (None, False, [])
        
    norm_sym = normalize_symbol(clean_q)
    
    # 1. Check local persistent registry first
    local_item = (
        database.get_company_by_symbol(norm_sym) or
        database.get_company_by_symbol(clean_q) or
        database.get_company_by_name(clean_q) or
        (database.get_company_by_bse_code(clean_q) if clean_q.isdigit() else None)
    )
    if local_item:
        return (local_item, False, [local_item])
        
    # 2. Check Authoritative Official Exchange Identity (Phase B adapter)
    from authoritative_identity import lookup_authoritative_identity
    auth_identity, is_ambig = lookup_authoritative_identity(clean_q, allow_seed_reference=True, use_live_exchange=True)
    if is_ambig:
        cands = resolve_and_search_companies(clean_q, limit=10)
        return (None, True, cands)
    if auth_identity:
        return (auth_identity, False, [auth_identity])
        
    # 3. External Discovery & Disambiguation
    candidates = resolve_and_search_companies(clean_q, limit=10)
    if not candidates:
        return (None, False, [])
        
    # Filter candidates with meaningful match score >= 50
    plausible = [c for c in candidates if c.get("match_score", 0) >= 50]
    if not plausible:
        return (None, False, candidates)
        
    top_score = plausible[0].get("match_score", 0)
    # Check if multiple candidates compete closely (within 15 pts of top score and score >= 60)
    competing = [c for c in plausible if top_score - c.get("match_score", 0) <= 15 and c.get("match_score", 0) >= 60]
    
    # Check if top candidate is an exact match on symbol, nse_symbol, or normalized title
    top_cand = plausible[0]
    norm_q = normalize_company_title(clean_q)
    norm_top_name = normalize_company_title(top_cand.get("company_name", ""))
    is_exact_top = (
        clean_q.upper() == top_cand.get("symbol", "").upper() or
        clean_q.upper() == (top_cand.get("nse_symbol") or "").upper() or
        (norm_q and norm_top_name and norm_q == norm_top_name)
    )
    
    if len(competing) > 1 and not is_exact_top:
        # Multiple plausible competing entities with no exact match -> Ambiguous!
        return (None, True, competing)
        
    # Single clear top candidate. Reconcile with authoritative identity or local data
    cand_sym = top_cand.get("symbol", "").upper().strip()
    cand_name = top_cand.get("company_name", "")
    
    auth_cand, _ = lookup_authoritative_identity(cand_sym, allow_seed_reference=True, use_live_exchange=True)
    if not auth_cand and cand_name:
        auth_cand, _ = lookup_authoritative_identity(cand_name, allow_seed_reference=True, use_live_exchange=True)
        
    if auth_cand:
        return (auth_cand, False, [auth_cand])
        
    # If not in official master but candidate has a high match score >= 70 and non-numeric ticker
    if top_cand.get("match_score", 0) >= 70 and not cand_sym.isdigit():
        return (top_cand, False, [top_cand])
        
    return (None, False, candidates)

def resolve_canonical_company(symbol_or_name: str) -> Optional[Dict[str, Any]]:
    """
    Resolves a symbol or company name to its canonical identity candidate.
    Checks local registry first, then authoritative lookup, then search resolver.
    """
    clean = symbol_or_name.strip()
    if not clean:
        return None
        
    norm_sym = normalize_symbol(clean)
    
    # 1. Exact local registry lookup
    local_item = (
        database.get_company_by_symbol(norm_sym) or
        database.get_company_by_symbol(clean) or
        database.get_company_by_name(clean) or
        (database.get_company_by_bse_code(clean) if clean.isdigit() else None)
    )
    if local_item:
        return local_item
        
    # 2. Authoritative lookup
    from authoritative_identity import lookup_authoritative_identity
    auth_res, _ = lookup_authoritative_identity(clean, allow_seed_reference=True, use_live_exchange=True)
    if auth_res:
        return auth_res
        
    # 3. Search resolver
    candidates = resolve_and_search_companies(clean, limit=5)
    if candidates:
        top = candidates[0]
        if top.get("match_score", 0) >= 70:
            auth_top, _ = lookup_authoritative_identity(top["symbol"], allow_seed_reference=True, use_live_exchange=True)
            if auth_top:
                return auth_top
            return top
            
    # 4. Explicit unverified candidate (no fabricated exchange/security metadata)
    return {
        "symbol": norm_sym,
        "company_name": clean,
        "nse_symbol": None,
        "bse_code": None,
        "isin": None,
        "exchange": None,
        "sector": None,
        "industry": None,
        "aliases": [clean],
        "source": "unresolved_input",
        "in_universe": True,
        "is_active": True
    }
