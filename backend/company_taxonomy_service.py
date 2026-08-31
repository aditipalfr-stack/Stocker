"""Deterministic, normalized company taxonomy for Stocker.

This module deliberately performs no network or AI work.  It converts trusted
labels already available during identity resolution/financial ingestion into a
durable sector -> industry -> sub-industry hierarchy.  Unknown evidence fails
closed to an explicit Unclassified assignment.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional, Tuple

import database
from financial_engine import classify_financial_business_model


UNCLASSIFIED = "Unclassified"
FAKE_LEGACY_LABELS = {
    "", "broad market", "indian equities", "diversified", "other", "unknown",
    "not available", "n/a", "na", "none", "unclassified",
}

# A small controlled vocabulary handles common market-label variants.  Labels
# outside it are still accepted when they are explicit source metadata, but are
# normalized and deduplicated before a new entity is created.
SECTOR_SYNONYMS = {
    "banking financial services": "Financial Services",
    "banking and financial services": "Financial Services",
    "financial services": "Financial Services",
    "financials": "Financial Services",
    "financial": "Financial Services",
    "banking": "Financial Services",
    "banks": "Financial Services",
    "consumer goods": "Consumer Staples",
    "consumer goods fmcg": "Consumer Staples",
    "fmcg": "Consumer Staples",
    "fast moving consumer goods": "Consumer Staples",
    "automobile": "Consumer Discretionary",
    "automobiles": "Consumer Discretionary",
    "automotive": "Consumer Discretionary",
    "technology": "Information Technology",
    "information technology": "Information Technology",
    "it": "Information Technology",
    "infrastructure engineering": "Industrials",
    "industrials": "Industrials",
    "capital goods": "Industrials",
    "metals": "Materials",
    "metals mining": "Materials",
    "materials": "Materials",
    "pharma": "Health Care",
    "pharmaceuticals": "Health Care",
    "healthcare": "Health Care",
    "health care": "Health Care",
    "energy conglomerate": "Energy",
    "oil gas": "Energy",
    "energy": "Energy",
    "telecom": "Communication Services",
    "telecommunications": "Communication Services",
    "real estate": "Real Estate",
    "utilities": "Utilities",
}

INDUSTRY_SYNONYMS = {
    "fmcg": ("Consumer Staples", "Fast Moving Consumer Goods"),
    "fast moving consumer goods": ("Consumer Staples", "Fast Moving Consumer Goods"),
    "consumer goods fmcg": ("Consumer Staples", "Fast Moving Consumer Goods"),
    "private sector bank": ("Financial Services", "Private Sector Banks"),
    "private sector banks": ("Financial Services", "Private Sector Banks"),
    "private banks": ("Financial Services", "Private Sector Banks"),
    "banks private": ("Financial Services", "Private Sector Banks"),
    "banking private": ("Financial Services", "Private Sector Banks"),
    "public sector bank": ("Financial Services", "Public Sector Banks"),
    "public sector banks": ("Financial Services", "Public Sector Banks"),
    "public banks": ("Financial Services", "Public Sector Banks"),
    "banks public": ("Financial Services", "Public Sector Banks"),
    "banking public": ("Financial Services", "Public Sector Banks"),
    "small finance bank": ("Financial Services", "Small Finance Banks"),
    "small finance banks": ("Financial Services", "Small Finance Banks"),
    "auto components": ("Consumer Discretionary", "Auto Components"),
    "automobile components": ("Consumer Discretionary", "Auto Components"),
    "auto ancillaries": ("Consumer Discretionary", "Auto Components"),
    "auto ancillary": ("Consumer Discretionary", "Auto Components"),
    "it services": ("Information Technology", "IT Services"),
    "it services consulting": ("Information Technology", "IT Services"),
    "it software": ("Information Technology", "Software & Services"),
    "software": ("Information Technology", "Software & Services"),
    "steel": ("Materials", "Steel"),
    "steel manufacturing value added products": ("Materials", "Steel"),
    "nbfc": ("Financial Services", "Non-Banking Financial Companies"),
    "non banking financial company": ("Financial Services", "Non-Banking Financial Companies"),
    "life insurance": ("Financial Services", "Insurance"),
    "general insurance": ("Financial Services", "Insurance"),
    "health insurance": ("Financial Services", "Insurance"),
    "insurance": ("Financial Services", "Insurance"),
}

SOURCE_PRIORITY = {
    "official_exchange": 100,
    "authoritative_registry": 95,
    "verified_registry": 90,
    "screener_metadata": 70,
    "seed_reference": 60,
    "registry_metadata": 55,
    "stocks_cache": 45,
    "statement_signature": 35,
    "unknown": 0,
}

CLASSIFICATION_STATE_RANK = {
    "UNCLASSIFIED": 0,
    "PARTIAL": 1,
    "COMPLETE": 2,
}


def normalize_taxonomy_key(value: Optional[str]) -> str:
    """Create a stable key insensitive to case, punctuation, '&' and spacing."""
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = text.encode("ascii", "ignore").decode("ascii").lower().replace("&", " and ")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text)).strip()


def _is_meaningful(value: Optional[str]) -> bool:
    key = normalize_taxonomy_key(value)
    return bool(key and key not in FAKE_LEGACY_LABELS and len(key) <= 100)


def _canonical_free_label(value: str) -> str:
    """Normalize safe explicit labels without pretending to understand them."""
    cleaned = re.sub(r"\s+", " ", re.sub(r"[|;/]+", " & ", value)).strip(" -&")
    if not cleaned:
        return UNCLASSIFIED
    small = {"and", "of", "for", "the", "to", "in"}
    acronyms = {"it", "nbfc", "fmcg", "epc", "ev", "bpo", "kpo", "reit"}
    words = []
    for index, word in enumerate(cleaned.split()):
        key = normalize_taxonomy_key(word)
        if key in acronyms:
            words.append(key.upper())
        elif index and key in small:
            words.append(key)
        else:
            words.append(word[:1].upper() + word[1:].lower())
    return " ".join(words)


def _source_kind(source: Optional[str]) -> str:
    key = normalize_taxonomy_key(source).replace(" ", "_")
    if key in {"nse", "bse", "nse_master", "bse_master", "official_exchange"}:
        return "official_exchange"
    if key in {"authoritative_registry", "authoritative_identity"}:
        return "authoritative_registry"
    if key in {"verified_registry", "company_ir"}:
        return "verified_registry"
    if key in {"screener", "screener_ingestion", "screener_metadata", "screener_in"}:
        return "screener_metadata"
    if key == "seed_reference":
        return "seed_reference"
    if key in {"stocks_cache", "cache"}:
        return "stocks_cache"
    if key in {"statement_signature", "financial_statement_signature"}:
        return "statement_signature"
    if key in {"registry_metadata", "local", "manual"}:
        return "registry_metadata"
    return "unknown"


def _classification_richness(classification: Dict[str, Any]) -> Tuple[int, int]:
    """Order assignments without inventing values: state first, explicit sub-industry second."""
    state_rank = CLASSIFICATION_STATE_RANK.get(str(classification.get("classification_state") or ""), 0)
    has_sub_industry = 1 if classification.get("sub_industry") else 0
    return state_rank, has_sub_industry


def _industry_match(value: Optional[str]) -> Optional[Tuple[str, str]]:
    key = normalize_taxonomy_key(value)
    if not key:
        return None
    if key in INDUSTRY_SYNONYMS:
        return INDUSTRY_SYNONYMS[key]
    # Exact components of composite labels may still identify a controlled term.
    for synonym, result in INDUSTRY_SYNONYMS.items():
        if len(synonym) >= 5 and re.search(rf"\b{re.escape(synonym)}\b", key):
            return result
    return None


def normalize_classification(
    sector: Optional[str],
    industry: Optional[str],
    sub_industry: Optional[str] = None,
) -> Tuple[str, str, Optional[str], str]:
    """Return canonical labels and COMPLETE/PARTIAL/UNCLASSIFIED state."""
    ind_match = _industry_match(industry)
    sector_key = normalize_taxonomy_key(sector)
    canonical_sector = SECTOR_SYNONYMS.get(sector_key) if _is_meaningful(sector) else None
    if canonical_sector is None and _is_meaningful(sector):
        canonical_sector = _canonical_free_label(str(sector))

    if ind_match:
        mapped_sector, canonical_industry = ind_match
        # A controlled industry mapping is more specific and also fixes a
        # contradictory broad source-sector label deterministically.
        canonical_sector = mapped_sector
    elif _is_meaningful(industry):
        canonical_industry = _canonical_free_label(str(industry))
    else:
        canonical_industry = None

    canonical_sub = _canonical_free_label(str(sub_industry)) if _is_meaningful(sub_industry) else None
    if not canonical_sector and not canonical_industry:
        return UNCLASSIFIED, UNCLASSIFIED, None, "UNCLASSIFIED"
    if not canonical_sector:
        canonical_sector = UNCLASSIFIED
    if not canonical_industry:
        canonical_industry = UNCLASSIFIED
    state = "COMPLETE" if canonical_sector != UNCLASSIFIED and canonical_industry != UNCLASSIFIED else "PARTIAL"
    return canonical_sector, canonical_industry, canonical_sub, state


def _ensure_sector(conn: Any, canonical_name: str, now_iso: str) -> int:
    key = normalize_taxonomy_key(canonical_name)
    conn.execute(
        "INSERT INTO taxonomy_sectors (canonical_name, normalized_key, created_at) VALUES (?, ?, ?) "
        "ON CONFLICT(normalized_key) DO NOTHING",
        (canonical_name, key, now_iso),
    )
    row = conn.execute("SELECT id FROM taxonomy_sectors WHERE normalized_key = ?", (key,)).fetchone()
    return int(row["id"])


def _ensure_industry(conn: Any, sector_id: int, canonical_name: str, now_iso: str) -> int:
    key = normalize_taxonomy_key(canonical_name)
    conn.execute(
        "INSERT INTO taxonomy_industries (sector_id, canonical_name, normalized_key, created_at) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(sector_id, normalized_key) DO NOTHING",
        (sector_id, canonical_name, key, now_iso),
    )
    row = conn.execute(
        "SELECT id FROM taxonomy_industries WHERE sector_id = ? AND normalized_key = ?", (sector_id, key)
    ).fetchone()
    return int(row["id"])


def _ensure_sub_industry(conn: Any, industry_id: int, canonical_name: Optional[str], now_iso: str) -> Optional[int]:
    if not canonical_name:
        return None
    key = normalize_taxonomy_key(canonical_name)
    conn.execute(
        "INSERT INTO taxonomy_sub_industries (industry_id, canonical_name, normalized_key, created_at) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(industry_id, normalized_key) DO NOTHING",
        (industry_id, canonical_name, key, now_iso),
    )
    row = conn.execute(
        "SELECT id FROM taxonomy_sub_industries WHERE industry_id = ? AND normalized_key = ?", (industry_id, key)
    ).fetchone()
    return int(row["id"])


def get_company_taxonomy(symbol: str) -> Optional[Dict[str, Any]]:
    clean_symbol = symbol.upper().strip()
    conn = database.get_db_connection()
    try:
        row = conn.execute(
            """
            SELECT ct.symbol, ts.canonical_name AS sector, ti.canonical_name AS industry,
                   tsi.canonical_name AS sub_industry, ct.source, ct.classification_method,
                   ct.confidence, ct.classification_state, ct.classified_at, ct.updated_at
            FROM company_taxonomy ct
            JOIN taxonomy_sectors ts ON ts.id = ct.sector_id
            JOIN taxonomy_industries ti ON ti.id = ct.industry_id
            LEFT JOIN taxonomy_sub_industries tsi ON tsi.id = ct.sub_industry_id
            WHERE ct.symbol = ? COLLATE NOCASE
            """,
            (clean_symbol,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def classify_and_persist_company(
    symbol: str,
    sector: Optional[str] = None,
    industry: Optional[str] = None,
    sub_industry: Optional[str] = None,
    source: Optional[str] = None,
    classification_method: str = "source_label_normalization",
    pl: Any = None,
    bs: Any = None,
    quarters: Any = None,
) -> Dict[str, Any]:
    """Persist only stronger-source or equally rich deterministic classification evidence."""
    clean_symbol = symbol.upper().strip()
    if not clean_symbol:
        raise ValueError("Taxonomy classification requires a canonical symbol")

    source_kind = _source_kind(source)
    canonical_sector, canonical_industry, canonical_sub, state = normalize_classification(
        sector, industry, sub_industry
    )

    if state == "UNCLASSIFIED":
        business_model = classify_financial_business_model(
            sector=None, industry=None, pl=pl, bs=bs, quarters=quarters
        )
        signature_mapping = {
            "BANK": ("Financial Services", "Banks"),
            "NBFC_LENDER": ("Financial Services", "Non-Banking Financial Companies"),
            "INSURANCE": ("Financial Services", "Insurance"),
            "OTHER_FINANCIAL": ("Financial Services", "Other Financial Services"),
        }
        if business_model in signature_mapping:
            canonical_sector, canonical_industry = signature_mapping[business_model]
            state = "COMPLETE"
            source_kind = "statement_signature"
            classification_method = "financial_statement_signature"

    confidence = {
        "official_exchange": "High", "authoritative_registry": "High", "verified_registry": "High",
        "screener_metadata": "Moderate", "seed_reference": "Moderate", "registry_metadata": "Moderate",
        "stocks_cache": "Low", "statement_signature": "Moderate", "unknown": "Unverified",
    }[source_kind]
    now_iso = datetime.now(timezone.utc).isoformat()
    existing = get_company_taxonomy(clean_symbol)
    incoming_priority = SOURCE_PRIORITY[source_kind]
    existing_priority = SOURCE_PRIORITY.get((existing or {}).get("source", "unknown"), 0)
    if existing and existing.get("classification_state") == "UNCLASSIFIED":
        existing_priority = -1
    elif existing and existing.get("classification_state") == "PARTIAL" and state == "COMPLETE":
        existing_priority = min(existing_priority, incoming_priority)
    if existing and incoming_priority < existing_priority:
        return existing
    if existing and incoming_priority == existing_priority:
        incoming = {
            "classification_state": state,
            "sub_industry": canonical_sub,
        }
        if _classification_richness(incoming) < _classification_richness(existing):
            return existing
        unchanged = (
            existing["sector"] == canonical_sector
            and existing["industry"] == canonical_industry
            and existing.get("sub_industry") == canonical_sub
        )
        if unchanged:
            return existing

    conn = database.get_db_connection()
    try:
        with conn:
            sector_id = _ensure_sector(conn, canonical_sector, now_iso)
            industry_id = _ensure_industry(conn, sector_id, canonical_industry, now_iso)
            sub_id = _ensure_sub_industry(conn, industry_id, canonical_sub, now_iso)
            conn.execute(
                """
                INSERT INTO company_taxonomy (
                    symbol, sector_id, industry_id, sub_industry_id, source,
                    classification_method, confidence, classification_state,
                    classified_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    sector_id = excluded.sector_id,
                    industry_id = excluded.industry_id,
                    sub_industry_id = excluded.sub_industry_id,
                    source = excluded.source,
                    classification_method = excluded.classification_method,
                    confidence = excluded.confidence,
                    classification_state = excluded.classification_state,
                    classified_at = excluded.classified_at,
                    updated_at = excluded.updated_at
                """,
                (
                    clean_symbol, sector_id, industry_id, sub_id, source_kind,
                    classification_method, confidence, state, now_iso, now_iso,
                ),
            )
            # Keep legacy compatibility fields canonical for old callers.
            conn.execute(
                "UPDATE company_registry SET sector = ?, industry = ?, updated_at = ? WHERE symbol = ? COLLATE NOCASE",
                (canonical_sector, canonical_industry, now_iso, clean_symbol),
            )
    finally:
        conn.close()
    return get_company_taxonomy(clean_symbol) or {}


def resolve_local_company_taxonomy(symbol: str, stock_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Reuse persisted taxonomy, or classify once from already-local evidence."""
    existing = get_company_taxonomy(symbol)
    data = stock_data or {}
    if existing:
        incoming_source = data.get("taxonomy_source")
        has_local_statement_evidence = any(data.get(key) is not None for key in ("profit_loss", "profit_and_loss", "balance_sheet", "quarters"))
        assignment_is_complete = existing.get("classification_state") == "COMPLETE"
        if assignment_is_complete and (
            not incoming_source or SOURCE_PRIORITY[_source_kind(incoming_source)] <= SOURCE_PRIORITY.get(existing["source"], 0)
        ):
            return existing
        if not has_local_statement_evidence and (
            not incoming_source or SOURCE_PRIORITY[_source_kind(incoming_source)] <= SOURCE_PRIORITY.get(existing["source"], 0)
        ):
            return existing

    registry = database.get_company_by_symbol(symbol) or {}
    sector = next((value for value in (
        data.get("source_sector"), data.get("sector"), registry.get("sector")
    ) if _is_meaningful(value)), None)
    industry = next((value for value in (
        data.get("source_industry"), data.get("industry"), registry.get("industry")
    ) if _is_meaningful(value)), None)
    incoming_source = data.get("taxonomy_source")
    source = incoming_source if _source_kind(incoming_source) != "unknown" else (registry.get("source") or ("stocks_cache" if sector or industry else "unknown"))
    return classify_and_persist_company(
        symbol=symbol,
        sector=sector,
        industry=industry,
        sub_industry=data.get("source_sub_industry") or data.get("sub_industry"),
        source=source,
        pl=data.get("profit_loss") or data.get("profit_and_loss"),
        bs=data.get("balance_sheet"),
        quarters=data.get("quarters"),
    )


def bootstrap_existing_taxonomy(records: Optional[Iterable[Dict[str, Any]]] = None) -> int:
    """Idempotently normalize seeded/registered companies into the taxonomy tables."""
    companies = list(records) if records is not None else database.get_universe_companies(active_only=False)
    count = 0
    for company in companies:
        if not company.get("symbol"):
            continue
        classify_and_persist_company(
            symbol=company["symbol"],
            sector=company.get("sector"),
            industry=company.get("industry"),
            sub_industry=company.get("sub_industry"),
            source=company.get("source") or "registry_metadata",
            classification_method="registry_bootstrap",
        )
        count += 1
    return count
