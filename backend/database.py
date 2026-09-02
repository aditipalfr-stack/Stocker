"""
Stocker Free Embedded Knowledge Store (SQLite3)
Zero-cost, persistent, embedded SQL database caching:
1. Raw Screener financials & quarterly time-series (stocks_cache)
2. Verified multi-source documents & discovery provenance (source_documents)
3. Extracted PDF page chunks (document_pages_cache)
4. Per-document AI executive summaries (ai_document_summaries)
5. Multi-document institutional intelligence & analysis timestamps (ai_analysis_cache)
"""

import sqlite3
import json
import os
import re
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

DB_PATH = Path(os.environ.get("STOCKER_DB_PATH", str(Path(__file__).parent / "data" / "stocker.db")))

def get_db_connection() -> sqlite3.Connection:
    """Returns a connection to the SQLite database with row factory enabled."""
    current_db_path = Path(os.environ.get("STOCKER_DB_PATH", str(DB_PATH)))
    current_db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(current_db_path), timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

def init_db() -> None:
    """Initializes the database schema and indices."""
    conn = get_db_connection()
    try:
        with conn:
            # 1. Raw Financials & Scraped Statements Cache
            conn.execute("""
                CREATE TABLE IF NOT EXISTS stocks_cache (
                    symbol TEXT PRIMARY KEY,
                    name TEXT,
                    sector TEXT,
                    industry TEXT,
                    data_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)

            # 2. Sourced & Verified Documents Repository
            conn.execute("""
                CREATE TABLE IF NOT EXISTS source_documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL UNIQUE,
                    doc_type TEXT NOT NULL,
                    period_or_date TEXT,
                    discovery_source TEXT,
                    actual_source_host TEXT,
                    is_valid INTEGER DEFAULT 1,
                    added_at TEXT NOT NULL
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_docs_symbol ON source_documents(symbol);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_docs_type ON source_documents(doc_type);")

            # 3. PDF Extracted Page Chunks Cache (Avoids re-downloading PDFs)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS document_pages_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    doc_url TEXT NOT NULL,
                    page_num INTEGER NOT NULL,
                    text_content TEXT NOT NULL,
                    extracted_at TEXT NOT NULL,
                    UNIQUE(doc_url, page_num)
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_pages_url ON document_pages_cache(doc_url);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_pages_symbol ON document_pages_cache(symbol);")

            # 4. Per-Document AI Executive Summaries
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ai_document_summaries (
                    doc_url TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    doc_title TEXT NOT NULL,
                    summary_json TEXT NOT NULL,
                    generated_at TEXT NOT NULL,
                    doc_key TEXT,
                    content_hash TEXT,
                    extraction_schema_version TEXT,
                    extraction_prompt_version TEXT,
                    provider TEXT,
                    model TEXT
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_summaries_symbol ON ai_document_summaries(symbol);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_summaries_key ON ai_document_summaries(doc_key);")

            # 5. Full Institutional AI Synthesis & Analysis Provenance
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ai_analysis_cache (
                    symbol TEXT PRIMARY KEY,
                    company_name TEXT,
                    intelligence_json TEXT NOT NULL,
                    ai_provider TEXT NOT NULL,
                    model_version TEXT NOT NULL,
                    prompt_tokens INTEGER DEFAULT 0,
                    source_documents_count INTEGER DEFAULT 0,
                    generated_at TEXT NOT NULL
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_analysis_symbol ON ai_analysis_cache(symbol);")

            # 6. Document Sources Sync State (Incremental Date-Window Tracking)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS document_sync_state (
                    symbol TEXT NOT NULL,
                    category TEXT NOT NULL,
                    last_checked_at TEXT NOT NULL,
                    last_filing_date TEXT,
                    PRIMARY KEY(symbol, category)
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sync_symbol ON document_sync_state(symbol);")

            # 7. Persistent Company Knowledge Facts Repository
            conn.execute("""
                CREATE TABLE IF NOT EXISTS company_knowledge_facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    doc_url TEXT NOT NULL,
                    doc_title TEXT NOT NULL,
                    doc_type TEXT NOT NULL,
                    period_or_date TEXT,
                    category TEXT NOT NULL,
                    metric_name TEXT NOT NULL,
                    stated_value_raw TEXT NOT NULL,
                    numeric_value REAL,
                    unit TEXT,
                    target_period TEXT,
                    scope TEXT DEFAULT 'Consolidated',
                    claim_type TEXT DEFAULT 'reported_fact',
                    source_quote TEXT,
                    source_page INTEGER,
                    extracted_at TEXT NOT NULL,
                    fact_json TEXT NOT NULL
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_facts_sym_metric ON company_knowledge_facts(symbol, metric_name);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_facts_sym_cat ON company_knowledge_facts(symbol, category);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_facts_doc_url ON company_knowledge_facts(doc_url);")

            # 8. Persistent Company Registry & Universe Directory
            conn.execute("""
                CREATE TABLE IF NOT EXISTS company_registry (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    company_name TEXT NOT NULL,
                    nse_symbol TEXT COLLATE NOCASE,
                    bse_code TEXT,
                    isin TEXT,
                    exchange TEXT,
                    sector TEXT DEFAULT 'Unclassified',
                    industry TEXT DEFAULT 'Unclassified',
                    aliases TEXT DEFAULT '[]',
                    is_active INTEGER DEFAULT 1,
                    in_universe INTEGER DEFAULT 1,
                    source TEXT DEFAULT 'seed_reference',
                    source_last_verified_at TEXT,
                    identity_source_name TEXT,
                    identity_source_url TEXT,
                    identity_verified_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_reg_sym ON company_registry(symbol);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_reg_name ON company_registry(company_name);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_reg_nse ON company_registry(nse_symbol);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_reg_bse ON company_registry(bse_code);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_reg_isin ON company_registry(isin);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_reg_universe ON company_registry(in_universe, is_active);")

            # 9. Normalized Company Taxonomy (Phase 3A)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS taxonomy_sectors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    canonical_name TEXT NOT NULL,
                    normalized_key TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS taxonomy_industries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sector_id INTEGER NOT NULL,
                    canonical_name TEXT NOT NULL,
                    normalized_key TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(sector_id) REFERENCES taxonomy_sectors(id),
                    UNIQUE(sector_id, normalized_key)
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_taxonomy_industry_sector ON taxonomy_industries(sector_id);")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS taxonomy_sub_industries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    industry_id INTEGER NOT NULL,
                    canonical_name TEXT NOT NULL,
                    normalized_key TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(industry_id) REFERENCES taxonomy_industries(id),
                    UNIQUE(industry_id, normalized_key)
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_taxonomy_sub_industry_parent ON taxonomy_sub_industries(industry_id);")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS company_taxonomy (
                    symbol TEXT PRIMARY KEY COLLATE NOCASE,
                    sector_id INTEGER NOT NULL,
                    industry_id INTEGER NOT NULL,
                    sub_industry_id INTEGER,
                    source TEXT NOT NULL,
                    classification_method TEXT NOT NULL,
                    confidence TEXT NOT NULL,
                    classification_state TEXT NOT NULL,
                    classified_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(sector_id) REFERENCES taxonomy_sectors(id),
                    FOREIGN KEY(industry_id) REFERENCES taxonomy_industries(id),
                    FOREIGN KEY(sub_industry_id) REFERENCES taxonomy_sub_industries(id)
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_company_taxonomy_sector ON company_taxonomy(sector_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_company_taxonomy_industry ON company_taxonomy(industry_id);")

            # 10. Persistent Authoritative Financial Verification Records (Phase B)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS financial_verification_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL COLLATE NOCASE,
                    metric_name TEXT NOT NULL,
                    canonical_metric TEXT NOT NULL,
                    period TEXT NOT NULL,
                    canonical_period TEXT NOT NULL,
                    scope TEXT NOT NULL DEFAULT 'Consolidated',
                    screener_value REAL,
                    official_value REAL,
                    variance_abs REAL,
                    variance_pct REAL,
                    unit TEXT DEFAULT '₹ Cr',
                    currency TEXT DEFAULT 'INR',
                    status TEXT NOT NULL,
                    tolerance_used REAL,
                    screener_source_url TEXT,
                    official_source_url TEXT,
                    official_source_name TEXT,
                    official_document_id TEXT,
                    notes TEXT,
                    verified_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_verif_sym_period ON financial_verification_records(symbol, canonical_period, canonical_metric);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_verif_status ON financial_verification_records(status);")

            # 11. Projection & Score Computation State (tracks evidence enrichment vs AI updates)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS projection_computation_state (
                    symbol TEXT PRIMARY KEY,
                    fin_data_version TEXT,
                    doc_intel_version TEXT,
                    computed_at TEXT NOT NULL
                );
            """)

            # 12. Canonical Financial Facts (Phase 2A Financial Truth Layer)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS canonical_financial_facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    canonical_metric TEXT NOT NULL,
                    display_metric TEXT NOT NULL,
                    period TEXT NOT NULL,
                    canonical_period TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    canonical_value REAL,
                    unit TEXT NOT NULL,
                    currency TEXT NOT NULL DEFAULT 'INR',
                    selected_source_type TEXT NOT NULL,
                    selected_source_name TEXT,
                    selected_source_url TEXT,
                    screener_value REAL,
                    official_value REAL,
                    verification_status TEXT NOT NULL,
                    difference_absolute REAL,
                    difference_pct REAL,
                    confidence TEXT NOT NULL,
                    provenance_note TEXT,
                    verified_at TEXT,
                    computed_at TEXT NOT NULL,
                    input_financial_version TEXT,
                    verification_version TEXT,
                    UNIQUE(symbol, canonical_metric, period, scope)
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cff_lookup ON canonical_financial_facts(symbol, canonical_metric, period, scope);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cff_canon_p ON canonical_financial_facts(symbol, canonical_period, canonical_metric);")

            # 13. Canonical Financial Truth Header State
            conn.execute("""
                CREATE TABLE IF NOT EXISTS canonical_financial_truth_state (
                    symbol TEXT PRIMARY KEY,
                    input_financial_version TEXT,
                    verification_version TEXT,
                    target_facts_count INTEGER NOT NULL DEFAULT 0,
                    verified_count INTEGER NOT NULL DEFAULT 0,
                    discrepancies_count INTEGER NOT NULL DEFAULT 0,
                    not_comparable_count INTEGER NOT NULL DEFAULT 0,
                    insufficient_evidence_count INTEGER NOT NULL DEFAULT 0,
                    official_source_missing_count INTEGER NOT NULL DEFAULT 0,
                    screener_value_missing_count INTEGER NOT NULL DEFAULT 0,
                    unverified_count INTEGER NOT NULL DEFAULT 0,
                    coverage_pct REAL NOT NULL DEFAULT 0.0,
                    overall_truth_state TEXT NOT NULL DEFAULT 'UNVERIFIED',
                    computed_at TEXT NOT NULL
                );
            """)

            # 14. Document Evidence Items (V4.4 Document Intelligence 2.0)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS document_evidence_items (
                    id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    evidence_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    normalized_topic TEXT NOT NULL,
                    statement TEXT NOT NULL,
                    source_document_type TEXT NOT NULL,
                    source_document_title TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    source_period TEXT,
                    source_date TEXT,
                    page INTEGER,
                    section TEXT,
                    evidence_quote TEXT,
                    extraction_method TEXT NOT NULL DEFAULT 'llm_structured_extraction',
                    confidence TEXT NOT NULL DEFAULT 'HIGH',
                    status TEXT NOT NULL DEFAULT 'SUPPORTED',
                    created_at TEXT NOT NULL,
                    evidence_json TEXT DEFAULT '{}'
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_evi_sym ON document_evidence_items(symbol, evidence_type);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_evi_topic ON document_evidence_items(symbol, normalized_topic);")

            # 15. Management Guidance Items (V4.4 Guidance Tracking Layer)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS management_guidance_items (
                    id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    metric_or_topic TEXT NOT NULL,
                    guidance_text TEXT NOT NULL,
                    quantified_value REAL,
                    quantified_range_min REAL,
                    quantified_range_max REAL,
                    unit TEXT,
                    target_period TEXT NOT NULL,
                    direction TEXT,
                    source_document_title TEXT NOT NULL,
                    source_document_url TEXT,
                    source_date_or_period TEXT,
                    confidence TEXT NOT NULL DEFAULT 'HIGH',
                    status TEXT NOT NULL DEFAULT 'INSUFFICIENT_EVIDENCE',
                    source_support_status TEXT NOT NULL DEFAULT 'SUPPORTED',
                    actual_reported_value REAL,
                    actual_reported_period TEXT,
                    actual_reported_source TEXT,
                    comparison_detail TEXT,
                    created_at TEXT NOT NULL,
                    guidance_json TEXT DEFAULT '{}'
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_mgi_sym ON management_guidance_items(symbol, metric_or_topic);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_mgi_status ON management_guidance_items(symbol, status);")

            # Safe schema migrations for preexisting tables
            try:
                cur = conn.cursor()
                evi_cols = {r[1] for r in cur.execute("PRAGMA table_info(document_evidence_items);").fetchall()}
                if evi_cols and "evidence_json" not in evi_cols:
                    conn.execute("ALTER TABLE document_evidence_items ADD COLUMN evidence_json TEXT DEFAULT '{}';")
            except Exception:
                pass

            try:
                cur = conn.cursor()
                mgi_cols = {r[1] for r in cur.execute("PRAGMA table_info(management_guidance_items);").fetchall()}
                if mgi_cols and "guidance_json" not in mgi_cols:
                    conn.execute("ALTER TABLE management_guidance_items ADD COLUMN guidance_json TEXT DEFAULT '{}';")
                if mgi_cols and "source_support_status" not in mgi_cols:
                    conn.execute("ALTER TABLE management_guidance_items ADD COLUMN source_support_status TEXT NOT NULL DEFAULT 'SUPPORTED';")
                if mgi_cols and "created_at" not in mgi_cols:
                    conn.execute("ALTER TABLE management_guidance_items ADD COLUMN created_at TEXT DEFAULT '';")
            except Exception:
                pass

            # Safe schema migration for source_documents.doc_key, discovered_sources, and source_aliases
            try:
                cur = conn.cursor()
                sdocs_cols = {r[1] for r in cur.execute("PRAGMA table_info(source_documents);").fetchall()}
                if sdocs_cols and "doc_key" not in sdocs_cols:
                    conn.execute("ALTER TABLE source_documents ADD COLUMN doc_key TEXT;")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_docs_key ON source_documents(doc_key);")
                if sdocs_cols and "discovered_sources" not in sdocs_cols:
                    conn.execute("ALTER TABLE source_documents ADD COLUMN discovered_sources TEXT DEFAULT '[]';")
                if sdocs_cols and "source_aliases" not in sdocs_cols:
                    conn.execute("ALTER TABLE source_documents ADD COLUMN source_aliases TEXT DEFAULT '[]';")
            except Exception:
                pass

            # Safe schema migration for ai_document_summaries provenance columns
            try:
                cur = conn.cursor()
                sums_cols = {r[1] for r in cur.execute("PRAGMA table_info(ai_document_summaries);").fetchall()}
                if sums_cols:
                    if "doc_key" not in sums_cols:
                        conn.execute("ALTER TABLE ai_document_summaries ADD COLUMN doc_key TEXT;")
                        conn.execute("CREATE INDEX IF NOT EXISTS idx_summaries_key ON ai_document_summaries(doc_key);")
                    if "content_hash" not in sums_cols:
                        conn.execute("ALTER TABLE ai_document_summaries ADD COLUMN content_hash TEXT;")
                    if "extraction_schema_version" not in sums_cols:
                        conn.execute("ALTER TABLE ai_document_summaries ADD COLUMN extraction_schema_version TEXT;")
                    if "extraction_prompt_version" not in sums_cols:
                        conn.execute("ALTER TABLE ai_document_summaries ADD COLUMN extraction_prompt_version TEXT;")
                    if "provider" not in sums_cols:
                        conn.execute("ALTER TABLE ai_document_summaries ADD COLUMN provider TEXT;")
                    if "model" not in sums_cols:
                        conn.execute("ALTER TABLE ai_document_summaries ADD COLUMN model TEXT;")
            except Exception:
                pass
    finally:
        conn.close()

    # Automatically seed initial registry if empty
    try:
        seed_company_registry()
    except Exception as e:
        print(f"Notice: Company registry auto-seed skipped or failed: {e}")

# ---------------------------------------------------------
# DOCUMENT EVIDENCE & GUIDANCE PERSISTENCE HELPERS
# ---------------------------------------------------------

def generate_deterministic_evidence_id(symbol: str, item: Dict[str, Any]) -> str:
    """Generates a stable, reproducible SHA-256 fallback ID for document evidence items."""
    clean_sym = symbol.upper().strip()
    s_url = item.get("source_url") or ""
    ev_type = item.get("evidence_type") or "OTHER_MATERIAL_EVIDENCE"
    norm_top = item.get("normalized_topic") or ""
    title = item.get("title") or ""
    stmt = item.get("statement") or ""
    raw = f"{clean_sym}|{s_url}|{ev_type}|{norm_top}|{title}|{stmt}"
    h = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    return f"evi_{clean_sym}_{h}"

def generate_deterministic_guidance_id(symbol: str, item: Dict[str, Any]) -> str:
    """Generates a stable, reproducible SHA-256 fallback ID for management guidance items."""
    clean_sym = symbol.upper().strip()
    mot = item.get("metric_or_topic") or ""
    tp = item.get("target_period") or ""
    gt = item.get("guidance_text") or ""
    sdt = item.get("source_document_title") or ""
    sdu = item.get("source_document_url") or ""
    raw = f"{clean_sym}|{mot}|{tp}|{gt}|{sdt}|{sdu}"
    h = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    return f"mgi_{clean_sym}_{h}"

def save_document_evidence_items(symbol: str, items: List[Dict[str, Any]]) -> int:
    clean_sym = symbol.upper().strip()
    if not items:
        return 0
    now_str = datetime.now(timezone.utc).isoformat()
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        table_cols = {r[1] for r in cur.execute("PRAGMA table_info(document_evidence_items);").fetchall()}
        saved = 0
        for it in items:
            item_id = it.get("id") or generate_deterministic_evidence_id(clean_sym, it)
            row_dict = {
                "id": item_id,
                "symbol": clean_sym,
                "evidence_type": it.get("evidence_type", "OTHER_MATERIAL_EVIDENCE"),
                "title": it.get("title", ""),
                "normalized_topic": it.get("normalized_topic", "General"),
                "statement": it.get("statement", ""),
                "source_document_type": it.get("source_document_type", "annual_report"),
                "source_document_title": it.get("source_document_title", ""),
                "source_url": it.get("source_url", ""),
                "source_period": it.get("source_period"),
                "source_date": it.get("source_date"),
                "page": it.get("page"),
                "section": it.get("section"),
                "evidence_quote": it.get("evidence_quote"),
                "extraction_method": it.get("extraction_method", "llm_structured_extraction"),
                "confidence": it.get("confidence", "HIGH"),
                "status": it.get("status", "SUPPORTED"),
                "created_at": it.get("created_at") or now_str,
                "evidence_json": json.dumps(it)
            }
            cols_to_insert = [k for k in row_dict.keys() if k in table_cols]
            placeholders = ", ".join(["?"] * len(cols_to_insert))
            col_names = ", ".join(cols_to_insert)
            update_clause = ", ".join([f"{c} = excluded.{c}" for c in cols_to_insert if c != "id"])

            sql = f"""
                INSERT INTO document_evidence_items ({col_names})
                VALUES ({placeholders})
                ON CONFLICT(id) DO UPDATE SET {update_clause};
            """
            cur.execute(sql, tuple(row_dict[c] for c in cols_to_insert))
            saved += 1
        conn.commit()
        return saved
    finally:
        conn.close()

def get_document_evidence_items(symbol: str, evidence_type: Optional[str] = None) -> List[Dict[str, Any]]:
    clean_sym = symbol.upper().strip()
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        if evidence_type:
            cur.execute("""
                SELECT * FROM document_evidence_items
                WHERE symbol = ? AND evidence_type = ?
                ORDER BY created_at DESC;
            """, (clean_sym, evidence_type))
        else:
            cur.execute("""
                SELECT * FROM document_evidence_items
                WHERE symbol = ?
                ORDER BY created_at DESC;
            """, (clean_sym,))
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def save_management_guidance_items(symbol: str, items: List[Dict[str, Any]]) -> int:
    clean_sym = symbol.upper().strip()
    if not items:
        return 0
    now_str = datetime.now(timezone.utc).isoformat()
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        table_cols = {r[1] for r in cur.execute("PRAGMA table_info(management_guidance_items);").fetchall()}
        saved = 0
        for it in items:
            item_id = it.get("id") or generate_deterministic_guidance_id(clean_sym, it)
            row_dict = {
                "id": item_id,
                "symbol": clean_sym,
                "metric_or_topic": it.get("metric_or_topic", ""),
                "guidance_text": it.get("guidance_text", ""),
                "quantified_value": it.get("quantified_value"),
                "quantified_range_min": it.get("quantified_range_min"),
                "quantified_range_max": it.get("quantified_range_max"),
                "unit": it.get("unit"),
                "target_period": it.get("target_period", ""),
                "direction": it.get("direction"),
                "source_document_title": it.get("source_document_title", ""),
                "source_document_url": it.get("source_document_url"),
                "source_date_or_period": it.get("source_date_or_period"),
                "confidence": it.get("confidence", "HIGH"),
                "status": it.get("status", "INSUFFICIENT_EVIDENCE"),
                "source_support_status": it.get("source_support_status", "SUPPORTED"),
                "actual_reported_value": it.get("actual_reported_value"),
                "actual_reported_period": it.get("actual_reported_period"),
                "actual_reported_source": it.get("actual_reported_source"),
                "comparison_detail": it.get("comparison_detail"),
                "created_at": it.get("created_at") or now_str,
                "updated_at": it.get("updated_at") or now_str,
                "guidance_json": json.dumps(it)
            }
            cols_to_insert = [k for k in row_dict.keys() if k in table_cols]
            placeholders = ", ".join(["?"] * len(cols_to_insert))
            col_names = ", ".join(cols_to_insert)
            update_clause = ", ".join([f"{c} = excluded.{c}" for c in cols_to_insert if c != "id"])

            sql = f"""
                INSERT INTO management_guidance_items ({col_names})
                VALUES ({placeholders})
                ON CONFLICT(id) DO UPDATE SET {update_clause};
            """
            cur.execute(sql, tuple(row_dict[c] for c in cols_to_insert))
            saved += 1
        conn.commit()
        return saved
    finally:
        conn.close()

def get_management_guidance_items(symbol: str) -> List[Dict[str, Any]]:
    clean_sym = symbol.upper().strip()
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM management_guidance_items
            WHERE symbol = ?
            ORDER BY created_at DESC;
        """, (clean_sym,))
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def canonicalize_document_url(url: Optional[str]) -> str:
    """
    Cleans and canonicalizes a document URL safely.
    - Strips leading/trailing whitespace and harmless URL fragments (#page=1, #...).
    - Normalizes BSE AnnPdfOpen.aspx?Pname=FILENAME to direct AttachHis/FILENAME URL.
    - Normalizes protocol to https:// and hostnames (bseindia.com -> www.bseindia.com).
    - Normalizes query parameters safely without breaking endpoint semantics.
    """
    if not url:
        return ""
    clean = str(url).strip()
    if not clean:
        return ""
    # Strip URL fragments
    if "#" in clean:
        clean = clean.split("#", 1)[0].strip()

    # BSE AnnPdfOpen normalization
    if "bseindia.com" in clean.lower() and "annpdfopen.aspx" in clean.lower():
        try:
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(clean)
            qs = parse_qs(parsed.query)
            pname = qs.get("Pname") or qs.get("pname")
            if pname and pname[0]:
                filename = pname[0].strip()
                clean = f"https://www.bseindia.com/xml-data/corpfiling/AttachHis/{filename}"
        except Exception:
            pass

    # Normalize bseindia.com protocol and subdomain
    if "bseindia.com" in clean.lower():
        clean = re.sub(r"^http://", "https://", clean)
        clean = re.sub(r"^https://bseindia\.com", "https://www.bseindia.com", clean)

    try:
        from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
        parsed = urlparse(clean)
        if parsed.scheme and parsed.netloc:
            scheme = parsed.scheme.lower()
            netloc = parsed.netloc.lower()
            query_tuples = parse_qsl(parsed.query, keep_blank_values=True)
            if query_tuples:
                sorted_query = urlencode(sorted(query_tuples))
            else:
                sorted_query = parsed.query
            return urlunparse((scheme, netloc, parsed.path, parsed.params, sorted_query, ""))
    except Exception:
        pass
    return clean

def normalize_document_type(raw_type: Optional[str], title: str = "") -> str:
    """
    Normalizes document classification into standard taxonomy:
    - annual_report
    - regulatory_annual_filing (20-F)
    - concall_transcript
    - presentation
    - announcement
    - brsr_esg
    - general (other)
    """
    t_clean = (title or "").lower().strip()
    rt_clean = str(raw_type or "").lower().strip()

    # 1. 20-F / Regulatory Annual Filing
    if any(k in t_clean for k in ["20-f", "form 20-f", "form 20 f", "10-k", "form 10-k"]) or rt_clean in ("regulatory_annual_filing", "20-f", "form_20_f"):
        return "regulatory_annual_filing"

    # 2. BRSR / ESG Reports
    if any(k in t_clean for k in [
        "brsr", "business responsibility and sustainability", "sustainability report",
        "esg report", "esg factsheet", "sustainability disclosure"
    ]) or rt_clean in ("brsr_esg", "brsr", "esg"):
        return "brsr_esg"

    # 3. Concall Transcripts
    if "concall" in rt_clean or "transcript" in rt_clean or any(k in t_clean for k in [
        "earnings call", "conference call", "concall transcript", "earnings conference", "call transcript"
    ]) or ("transcript" in t_clean and not any(w in t_clean for w in ["share", "transfer", "notice", "court", "tribunal"])):
        return "concall_transcript"

    # 4. Investor Presentations
    if "presentation" in rt_clean or "ppt" in rt_clean or any(k in t_clean for k in [
        "investor presentation", "earnings presentation", "investor deck", "analyst presentation",
        "quarterly presentation", "investor update", "presentation", "ppt"
    ]):
        return "presentation"

    # 5. Annual Reports (Excluding BRSR and 20-F)
    if "annual" in rt_clean or any(k in t_clean for k in [
        "annual report", "integrated report", "integrated annual report", "annual accounts", "annual general meeting and annual report"
    ]):
        return "annual_report"

    # 6. Material Announcements
    if "announcement" in rt_clean or any(k in t_clean for k in [
        "announcement", "outcome", "board meeting", "filing", "regulation 30", "press release",
        "media release", "disclosure", "intimation", "allotment", "credit rating"
    ]):
        return "announcement"

    return "general"

def derive_document_subtype(doc_type: str, title: str = "", period_or_date: Optional[str] = None) -> str:
    """Derives specific structural subtype of the document for metadata and filtering."""
    t_clean = (title or "").lower().strip()
    norm_dt = normalize_document_type(doc_type, title)

    if norm_dt == "regulatory_annual_filing":
        return "20-f" if "20-f" in t_clean else "regulatory_annual"
    if norm_dt == "brsr_esg":
        return "brsr" if "brsr" in t_clean else "esg_report"
    if norm_dt == "annual_report":
        return "annual_report"
    if norm_dt == "concall_transcript":
        if ("media" in t_clean or "press" in t_clean) and not any(k in t_clean for k in ["analyst", "investor", "earnings call", "quarterly earnings"]):
            return "media_call_transcript"
        if "analyst" in t_clean or "investor" in t_clean or "earnings" in t_clean or "concall" in t_clean:
            return "analyst_investor_transcript"
        return "earnings_transcript"
    if norm_dt == "presentation":
        if any(k in t_clean for k in ["agm", "annual general meeting", "general meeting"]):
            return "agm_presentation"
        if any(k in t_clean for k in ["investor day", "analyst meet", "analyst day", "strategy presentation", "strategy update", "thematic", "corporate presentation"]):
            return "investor_day_presentation"
        # Deterministically check for explicit quarterly/earnings indicators in title or period
        p_clean = (period_or_date or "").lower().strip()
        combined_text = f"{t_clean} {p_clean}"
        has_earnings_indicator = bool(re.search(
            r'\b(q[1-4]|quarter|financial results|earnings|performance review|quarter ended|half year|h[12]|annual results|fy\s*\d{2,4}|20\d\d[-/]\d{2})\b',
            combined_text
        ))
        if has_earnings_indicator:
            return "earnings_presentation"
        return "other_presentation"
    if norm_dt == "announcement":
        if "board meeting" in t_clean or "outcome" in t_clean:
            return "board_outcome"
        if "credit rating" in t_clean or "rating" in t_clean:
            return "credit_rating"
        if "esop" in t_clean or "allotment" in t_clean:
            return "esop_allotment"
        if "press release" in t_clean or "media" in t_clean:
            return "press_release"
        return "material_disclosure"
    return "general_filing"

def derive_announcement_event_key(symbol: str, title: str, period_or_date: Optional[str] = None) -> str:
    """
    Computes a deterministic canonical event key for announcements to suppress
    near-duplicate disclosure wrappers for the same underlying material event.
    """
    clean_sym = symbol.upper().strip()
    t_clean = (title or "").lower().strip()
    p_clean = (period_or_date or "").strip()

    # 1. Credit Rating Action (e.g. CRISIL, ICRA, CARE, India Ratings)
    if "rating" in t_clean or "credit rating" in t_clean:
        agency = "rating"
        for ag in ["crisil", "icra", "care", "india ratings", "fitch", "moody", "s&p", "brickwork"]:
            if ag in t_clean:
                agency = ag.replace(" ", "_")
                break
        m_date = re.search(r'\b(20\d\d[-/]\d{2}(?:[-/]\d{2})?)\b', p_clean or t_clean)
        d_part = m_date.group(1) if m_date else p_clean[:7]
        return f"ANN_EVENT_{clean_sym}_RATING_{agency}_{d_part}"

    # 2. Debt / Bond / NCD Issuance
    if any(k in t_clean for k in ["bond", "ncd", "debenture", "senior notes", "commercial paper", "issuance"]):
        m_date = re.search(r'\b(20\d\d[-/]\d{2}(?:[-/]\d{2})?)\b', p_clean or t_clean)
        d_part = m_date.group(1) if m_date else p_clean[:7]
        return f"ANN_EVENT_{clean_sym}_DEBT_ISSUE_{d_part}"

    # 3. Dividend / AGM Outcome
    if "dividend" in t_clean or "agm" in t_clean:
        return f"ANN_EVENT_{clean_sym}_DIVIDEND_AGM_{p_clean[:7]}"

    # 4. Board Meeting Outcome / Results
    if "board meeting" in t_clean or "outcome of" in t_clean:
        m_date = re.search(r'\b(\d{1,2}\s+[A-Za-z]{3}\s+20\d\d)\b', p_clean or t_clean)
        d_part = m_date.group(1) if m_date else p_clean[:10]
        return f"ANN_EVENT_{clean_sym}_BOARD_MEETING_{d_part.replace(' ', '_')}"

    # Default: each distinct title/date combination remains distinct
    return f"ANN_EVENT_{clean_sym}_{hashlib.md5(f'{t_clean}_{p_clean}'.encode()).hexdigest()[:10]}"

def extract_normalized_fiscal_year(period_or_date: Optional[str], title: str = "") -> str:
    """Extracts a normalized fiscal year key (e.g. FY2026, FY2025) from filing date or title."""
    combined = f"{period_or_date or ''} {title or ''}".strip()

    # 1. Match FY2026, FY26, FY 2026, FY 26
    m_fy = re.search(r'\bFY\s*(\d{2,4})\b', combined, re.IGNORECASE)
    if m_fy:
        raw_yr = int(m_fy.group(1))
        return f"FY{raw_yr if raw_yr > 1000 else 2000 + raw_yr}"

    # 2. Match 2025-26, 2025-2026, 2025–26
    m_range = re.search(r'\b(\d{4})\s*[-–]\s*(\d{2,4})\b', combined)
    if m_range:
        yr1 = int(m_range.group(1))
        yr2 = int(m_range.group(2))
        fy_yr = yr2 if yr2 > 1000 else int(str(yr1)[:2] + str(yr2).zfill(2))
        return f"FY{fy_yr}"

    # 3. Match March 31, 2026 or March 2026
    m_mar = re.search(r'March[a-z]*\s*(?:\d{1,2}\s*,?\s*)?(\d{4})', combined, re.IGNORECASE)
    if m_mar:
        return f"FY{m_mar.group(1)}"

    # 4. Match year only in title: 'Annual Report 2026'
    m_yr = re.search(r'\b(20\d{2})\b', combined)
    if m_yr:
        return f"FY{m_yr.group(1)}"

    return "UNKNOWN_FY"

def derive_earnings_event_key(symbol: str, period_or_date: Optional[str], title: str = "") -> str:
    """
    Computes a deterministic event key for earnings-event filings (e.g. event_ICICIBANK_Q1FY27).
    Allows linking transcripts and presentations from the same reporting event while preserving them as distinct documents.
    """
    clean_sym = symbol.upper().strip()
    combined = f"{period_or_date or ''} {title or ''}".strip()

    # 1. Match explicit Quarter + FY: 'Q1 FY27', 'Q4 FY26', 'Q1-2027', 'Q1 FY2027'
    m_q = re.search(r'Q([1-4])\s*(?:FY|[-–])?\s*(\d{2,4})', combined, re.IGNORECASE)
    if m_q:
        q_num = int(m_q.group(1))
        raw_yr = int(m_q.group(2))
        fy_yr = raw_yr if raw_yr > 1000 else 2000 + raw_yr
        return f"event_{clean_sym}_Q{q_num}FY{str(fy_yr)[-2:]}"

    # 2. Match Month + Year for Indian reporting cycle:
    # Jun/Jul/Aug earnings calls -> Q1 of following FY (e.g. Jul 2026 -> Q1 FY27)
    # Sep/Oct/Nov earnings calls -> Q2 of following FY (e.g. Oct 2025 -> Q2 FY26)
    # Dec/Jan/Feb earnings calls -> Q3 of FY (e.g. Jan 2026 -> Q3 FY26)
    # Mar/Apr/May earnings calls -> Q4 of FY (e.g. Apr 2026 -> Q4 FY26)
    m_my = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[-/ ,]+(\d{4})', combined, re.IGNORECASE)
    if m_my:
        mon = m_my.group(1)[:3].lower()
        yr = int(m_my.group(2))
        if mon in ["jun", "jul", "aug"]:
            return f"event_{clean_sym}_Q1FY{str(yr + 1)[-2:]}"
        elif mon in ["sep", "oct", "nov"]:
            return f"event_{clean_sym}_Q2FY{str(yr + 1)[-2:]}"
        elif mon in ["dec", "jan", "feb"]:
            return f"event_{clean_sym}_Q3FY{str(yr if mon != 'dec' else yr + 1)[-2:]}"
        elif mon in ["mar", "apr", "may"]:
            return f"event_{clean_sym}_Q4FY{str(yr)[-2:]}"

    # 3. Match exact text date: '18 Jul 2026', '23 Jul 2026'
    m_dmy = re.search(r'\d{1,2}[-/ ]+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[-/ ,]+(\d{4})', combined, re.IGNORECASE)
    if m_dmy:
        mon = m_dmy.group(1)[:3].lower()
        yr = int(m_dmy.group(2))
        if mon in ["jun", "jul", "aug"]:
            return f"event_{clean_sym}_Q1FY{str(yr + 1)[-2:]}"
        elif mon in ["sep", "oct", "nov"]:
            return f"event_{clean_sym}_Q2FY{str(yr + 1)[-2:]}"
        elif mon in ["dec", "jan", "feb"]:
            return f"event_{clean_sym}_Q3FY{str(yr if mon != 'dec' else yr + 1)[-2:]}"
        elif mon in ["mar", "apr", "may"]:
            return f"event_{clean_sym}_Q4FY{str(yr)[-2:]}"

    return f"event_{clean_sym}_GENERIC"

def is_document_wrapper(title: str, url: str = "", text_content: Optional[str] = None, page_count: Optional[int] = None) -> bool:
    """
    Detects whether a filing is a 1-page notification / cover-letter wrapper rather than the substantive document.
    Inspects title, cached first-page text, and notification phrases.
    """
    t_lower = (title or "").lower().strip()
    if any(k in t_lower for k in [
        "audio recording of earnings", "link for audio recording", "audio recording",
        "intimation of schedule of analyst", "schedule of analyst meet", "intimation of analyst meet",
        "newspaper publication", "loss of share certificate", "duplicate share",
        "call with media on financial results for the quarter"
    ]):
        return True

    fp_text = text_content
    p_cnt = page_count

    if fp_text is None and url:
        try:
            cached_pages = get_cached_document_pages(url)
            if cached_pages:
                p_cnt = len(cached_pages)
                fp_text = cached_pages[0][1]
        except Exception:
            pass

    if p_cnt is not None and p_cnt <= 2 and fp_text:
        fp_lower = fp_text.lower()
        if any(w in fp_lower for w in [
            "transcripts of the call", "transcripts are available", "available on website",
            "please find link", "web-link", "web link", "link for audio", "available at https",
            "please find attached", "we wish to inform that", "we inform that", "enclosed herewith"
        ]):
            return True

    return False

def parse_document_sort_timestamp(period_or_date: Optional[str], title: str = "") -> str:
    """
    Extracts a deterministic ISO sort timestamp (YYYY-MM-DD) for global chronological ordering.
    Does NOT invent or change visible text; used strictly for ordering.
    Priority:
    1. Exact filing / publication date
    2. Exact quarter / month if no full date
    3. FY-only documents (mapped to fiscal year end YYYY-03-31)
    4. Unknown-date documents last (1970-01-01)
    """
    combined = f"{period_or_date or ''} {title or ''}".strip()
    if not combined:
        return "1970-01-01"

    # 1. Exact ISO: YYYY-MM-DD
    m_iso = re.search(r'(\d{4})-(\d{2})-(\d{2})', combined)
    if m_iso:
        try:
            dt = datetime(int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3)))
            return dt.strftime('%Y-%m-%d')
        except Exception:
            pass

    # 2. Exact text date: '28 Aug 2026', '28-Aug-2026', 'August 21, 2026', '21 August 2026'
    m_dmy = re.search(r'(\d{1,2})[-/ ]+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[-/ ,]+(\d{4})', combined, re.IGNORECASE)
    if m_dmy:
        try:
            day = int(m_dmy.group(1))
            mon_str = m_dmy.group(2)[:3].capitalize()
            yr = int(m_dmy.group(3))
            dt = datetime.strptime(f"{day} {mon_str} {yr}", "%d %b %Y")
            return dt.strftime('%Y-%m-%d')
        except Exception:
            pass

    m_mdy = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[-/ ]+(\d{1,2})[-/ ,]+(\d{4})', combined, re.IGNORECASE)
    if m_mdy:
        try:
            mon_str = m_mdy.group(1)[:3].capitalize()
            day = int(m_mdy.group(2))
            yr = int(m_mdy.group(3))
            dt = datetime.strptime(f"{day} {mon_str} {yr}", "%d %b %Y")
            return dt.strftime('%Y-%m-%d')
        except Exception:
            pass

    # 3. Month & Year only: 'Jul 2026', 'July 2026'
    m_my = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[-/ ]+(\d{4})', combined, re.IGNORECASE)
    if m_my:
        try:
            mon_str = m_my.group(1)[:3].capitalize()
            yr = int(m_my.group(2))
            dt = datetime.strptime(f"01 {mon_str} {yr}", "%d %b %Y")
            return dt.strftime('%Y-%m-%d')
        except Exception:
            pass

    # 4. Quarter & Fiscal Year: 'Q1 FY27', 'Q4 FY26', 'Q1 FY2026'
    m_q = re.search(r'Q([1-4])\s*(?:FY)?\s*(\d{2,4})', combined, re.IGNORECASE)
    if m_q:
        q_num = int(m_q.group(1))
        raw_yr = int(m_q.group(2))
        fy_yr = raw_yr if raw_yr > 1000 else 2000 + raw_yr
        if q_num == 1:
            return f"{fy_yr - 1}-06-30"
        elif q_num == 2:
            return f"{fy_yr - 1}-09-30"
        elif q_num == 3:
            return f"{fy_yr - 1}-12-31"
        elif q_num == 4:
            return f"{fy_yr}-03-31"

    # 5. Fiscal Year only: 'FY2026', 'FY26', '2025-26', '2025-2026'
    m_fy = re.search(r'FY\s*(\d{2,4})', combined, re.IGNORECASE)
    if m_fy:
        raw_yr = int(m_fy.group(1))
        fy_yr = raw_yr if raw_yr > 1000 else 2000 + raw_yr
        return f"{fy_yr}-03-31"

    m_fy_range = re.search(r'(\d{4})\s*[-–]\s*(\d{2,4})', combined)
    if m_fy_range:
        yr1 = int(m_fy_range.group(1))
        yr2 = int(m_fy_range.group(2))
        fy_yr = yr2 if yr2 > 1000 else int(str(yr1)[:2] + str(yr2).zfill(2))
        return f"{fy_yr}-03-31"

    # 6. Year only in title: 'Annual Report 2024'
    m_yr = re.search(r'\b(20\d{2})\b', combined)
    if m_yr:
        return f"{m_yr.group(1)}-03-31"

    return "1970-01-01"

def deduplicate_document_records(documents: List[Any], symbol: str) -> List[Dict[str, Any]]:
    """
    Implements deterministic canonical source strategy across filing categories:
    1. Annual Reports: normally ONE canonical Annual Report per known FY; merges Screener & BSE representations,
       inheriting exact exchange filing date and preferred direct official PDF representation.
       Fail-closed: Unknown FY annual reports are NOT semantically merged and retain strict physical identity.
    2. Regulatory Annual Filings (20-F): kept distinct from domestic Annual Reports.
    3. Concalls: Screener-first for normal transcript/deck pairs; exchange acts as gap detector.
       Subtype isolation: Media call transcript vs Analyst/investor transcript are distinct.
       Fail-closed: Unknown event concalls retain physical identity.
    4. Investor Presentations: one canonical deck per event/URL; complementary to transcript.
    5. BRSR / ESG: kept distinct and discoverable with low default AI working-set priority.
    6. Material Announcements: distinct announcements on same date preserved; only true duplicate files merged.
    """
    if not documents:
        return []

    clean_sym = symbol.upper().strip()
    canonical_map: Dict[str, Dict[str, Any]] = {}

    for doc in documents:
        if isinstance(doc, dict):
            raw_title = str(doc.get("title") or doc.get("name") or "").strip()
            raw_url = str(doc.get("url") or "").strip()
            raw_dt = str(doc.get("doc_type") or "general").strip()
            p_date = doc.get("period_or_date")
            discovery = doc.get("discovery_source") or "Unknown"
            host = doc.get("actual_source_host") or ""
            status = doc.get("validation_status", "Valid")
            is_valid = doc.get("is_valid", 1)
            f_date = doc.get("fetched_date")
            doc_k = doc.get("doc_key")
            ev_k = doc.get("event_key")
            sources = list(doc.get("discovered_sources") or [])
            aliases = list(doc.get("source_aliases") or [])
            is_subst = doc.get("is_substantive", True)
            is_wrap = doc.get("is_wrapper", False)
            ai_elig = doc.get("ai_eligible", True)
        else:
            raw_title = str(getattr(doc, "title", None) or getattr(doc, "name", None) or "").strip()
            raw_url = str(getattr(doc, "url", None) or "").strip()
            raw_dt = str(getattr(doc, "doc_type", None) or "general").strip()
            p_date = getattr(doc, "period_or_date", None)
            discovery = getattr(doc, "discovery_source", None) or "Unknown"
            host = getattr(doc, "actual_source_host", None) or ""
            status = getattr(doc, "validation_status", "Valid")
            is_valid = getattr(doc, "is_valid", 1)
            f_date = getattr(doc, "fetched_date", None)
            doc_k = getattr(doc, "doc_key", None)
            ev_k = getattr(doc, "event_key", None)
            sources = list(getattr(doc, "discovered_sources", None) or [])
            aliases = list(getattr(doc, "source_aliases", None) or [])
            is_subst = getattr(doc, "is_substantive", True)
            is_wrap = getattr(doc, "is_wrapper", False)
            ai_elig = getattr(doc, "ai_eligible", True)

        if not raw_url:
            continue

        c_url = canonicalize_document_url(raw_url) or raw_url
        norm_dt = normalize_document_type(raw_dt, raw_title)
        subtype = derive_document_subtype(norm_dt, raw_title, p_date)
        wrapper = is_wrap or is_document_wrapper(raw_title, c_url)

        if discovery and discovery not in sources:
            sources.append(discovery)

        # Determine canonical group identity per category (Fail-Closed on Unknown / Generic):
        if norm_dt == "annual_report":
            fy = extract_normalized_fiscal_year(p_date, raw_title)
            if fy and fy != "UNKNOWN_FY":
                group_key = f"AR_{clean_sym}_{fy}"
            else:
                # Never semantically merge unknown-period annual reports
                group_key = f"AR_{clean_sym}_PHYSICAL_{c_url}"
        elif norm_dt == "regulatory_annual_filing":
            group_key = f"REG20F_{clean_sym}_{c_url}"
        elif norm_dt == "brsr_esg":
            fy = extract_normalized_fiscal_year(p_date, raw_title)
            if fy and fy != "UNKNOWN_FY":
                group_key = f"BRSR_{clean_sym}_{fy}"
            else:
                group_key = f"BRSR_{clean_sym}_PHYSICAL_{c_url}"
        elif norm_dt == "concall_transcript":
            ev = ev_k or derive_earnings_event_key(clean_sym, p_date, raw_title)
            if ev and ev != f"event_{clean_sym}_GENERIC":
                # Isolate subtypes: Media call transcript vs Analyst/investor transcript
                group_key = f"CC_{clean_sym}_{ev}_{subtype}"
            else:
                # Fail closed: unknown event concalls are not merged across different URLs
                group_key = f"CC_{clean_sym}_PHYSICAL_{c_url}"
        elif norm_dt == "presentation":
            ev = ev_k or derive_earnings_event_key(clean_sym, p_date, raw_title)
            if ev and ev != f"event_{clean_sym}_GENERIC":
                # Key presentations by event + URL to preserve distinct decks
                group_key = f"PPT_{clean_sym}_{ev}_{c_url}"
            else:
                group_key = f"PPT_{clean_sym}_PHYSICAL_{c_url}"
        else:
            group_key = f"ANN_{clean_sym}_{c_url}"

        event_key_val = ev_k or (derive_earnings_event_key(clean_sym, p_date, raw_title) if norm_dt in ("concall_transcript", "presentation") else None)
        if event_key_val == f"event_{clean_sym}_GENERIC":
            event_key_val = None

        if group_key in canonical_map:
            existing = canonical_map[group_key]
            # Merge discovery sources
            for s in sources:
                if s and s not in existing["discovered_sources"]:
                    existing["discovered_sources"].append(s)

            # Record alias if title or URL is different
            if raw_title and raw_title != existing["title"] and raw_title not in existing["source_aliases"]:
                existing["source_aliases"].append(raw_title)
            if raw_url and raw_url != existing["url"] and raw_url not in existing["source_aliases"]:
                existing["source_aliases"].append(raw_url)

            # Date enrichment: Inherit exact/stronger date from alias
            curr_ts = existing.get("sort_timestamp") or parse_document_sort_timestamp(existing.get("period_or_date"), existing["title"])
            new_ts = parse_document_sort_timestamp(p_date, raw_title)
            if new_ts != "1970-01-01" and (curr_ts == "1970-01-01" or (curr_ts.endswith("-03-31") and not new_ts.endswith("-03-31")) or (p_date and len(str(p_date)) > len(str(existing.get("period_or_date") or "")))):
                existing["period_or_date"] = p_date
                existing["sort_timestamp"] = new_ts

            # Category-specific representation preferences:
            if norm_dt == "annual_report":
                # Prefer official exchange title and direct host
                if ("bse" in discovery.lower() or "exchange" in discovery.lower() or "notice" in raw_title.lower()) and not ("bse" in existing["discovery_source"].lower()):
                    existing["title"] = raw_title
                    existing["url"] = c_url
                    existing["discovery_source"] = discovery
            elif norm_dt == "concall_transcript":
                # Prefer substantive transcript over 1-page wrapper notification
                if not wrapper and existing.get("is_wrapper"):
                    existing["title"] = raw_title
                    existing["url"] = c_url
                    existing["discovery_source"] = discovery
                    existing["is_wrapper"] = False
                    existing["is_substantive"] = True
                    existing["ai_eligible"] = True
                elif "screener" in discovery.lower() and not wrapper:
                    existing["title"] = raw_title
                    existing["url"] = c_url
                    existing["discovery_source"] = discovery
            elif norm_dt == "presentation":
                if ("bse" in discovery.lower() or "company" in discovery.lower()) and "screener" in existing["discovery_source"].lower():
                    existing["title"] = raw_title
                    existing["url"] = c_url
                    existing["discovery_source"] = discovery

            # Recompute canonical doc_key
            existing["doc_key"] = compute_canonical_document_key(
                clean_sym, existing["doc_type"], existing.get("period_or_date"), existing["url"], existing["title"]
            )
        else:
            final_key = doc_k or compute_canonical_document_key(
                clean_sym, norm_dt, p_date, c_url, raw_title
            )
            sort_ts = parse_document_sort_timestamp(p_date, raw_title)
            canonical_map[group_key] = {
                "symbol": clean_sym,
                "ticker": clean_sym,
                "title": raw_title,
                "url": c_url,
                "doc_type": norm_dt,
                "doc_subtype": subtype,
                "period_or_date": p_date,
                "discovery_source": discovery,
                "discovered_sources": sources,
                "source_aliases": aliases,
                "actual_source_host": host or ("bseindia.com" if "bseindia.com" in c_url else "screener.in"),
                "actual_source_url": c_url,
                "is_direct_pdf": True if c_url.lower().endswith(".pdf") or ".pdf" in c_url.lower() else False,
                "validation_status": status,
                "is_valid": 1 if is_valid in (1, True, "1", "Valid") else 0,
                "fetched_date": f_date,
                "doc_key": final_key,
                "event_key": event_key_val,
                "is_substantive": not wrapper and is_subst,
                "is_wrapper": wrapper,
                "wrapper_source_url": raw_url if wrapper else None,
                "ai_eligible": not wrapper and ai_elig and is_valid in (1, True, "1", "Valid"),
                "sort_timestamp": sort_ts
            }

    res = list(canonical_map.values())
    res.sort(key=lambda x: (x.get("sort_timestamp") or "1970-01-01", x.get("title", "")), reverse=True)
    return res

def compute_canonical_document_key(
    symbol: str,
    doc_type: str,
    period_or_date: Optional[str] = None,
    url: Optional[str] = None,
    title: Optional[str] = None
) -> str:
    """
    Computes a stable, deterministic canonical document key across processes and sources.
    Uses normalized symbol, doc_type, and canonical URL (or normalized period/title fallback).
    """
    clean_sym = symbol.upper().strip()
    dt = normalize_document_type(doc_type, title or "")

    c_url = canonicalize_document_url(url)
    p_date = (period_or_date or "").strip().upper()
    norm_title = re.sub(r'\s+', ' ', (title or "").strip().lower())

    if c_url:
        raw = f"{clean_sym}|{dt}|{c_url}"
        h = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
        return f"doc_{clean_sym}_{dt}_{h}"
    else:
        raw = f"{clean_sym}|{dt}|{p_date}|{norm_title}"
        h = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
        return f"doc_{clean_sym}_{dt}_{h}"

def compute_canonical_semantic_key(
    symbol: str,
    doc_type: str,
    period_or_date: Optional[str] = None
) -> Optional[str]:
    """
    Computes an unambiguous secondary semantic key (e.g. sem_INFY_annual_report_FY26)
    for cross-referencing equivalent filings across Screener and exchange discovery.
    """
    clean_sym = symbol.upper().strip()
    dt = normalize_document_type(doc_type)
    if dt == "general":
        return None

    p = (period_or_date or "").strip().upper()
    # Match standard periods like FY26, FY2026, Q3 FY26, Q1 FY25, etc.
    if re.match(r'^(FY\d{2,4}|Q[1-4]\s*FY\d{2,4}|\d{4}-\d{2}-\d{2})$', p, re.IGNORECASE):
        norm_p = re.sub(r'\s+', '', p)
        return f"sem_{clean_sym}_{dt}_{norm_p}"
    return None

def compute_source_documents_hash(docs: Optional[List[Any]]) -> str:
    """Computes a stable deterministic SHA256 hash over candidate source documents."""
    if not docs:
        return "empty_corpus"
    elements = []
    for d in docs:
        if isinstance(d, dict):
            u = str(d.get("url", "")).strip()
            t = str(d.get("title", "")).strip()
            p = str(d.get("period") or d.get("period_or_date", "")).strip()
        else:
            u = str(getattr(d, "url", "")).strip()
            t = str(getattr(d, "title", "")).strip()
            p = str(getattr(d, "period_or_date", "")).strip()
        elements.append(f"{u}|{t}|{p}")
    elements.sort()
    combined = "\n".join(elements)
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()[:16]

def check_business_analysis_staleness(symbol: str, current_docs: Optional[List[Any]] = None) -> Tuple[bool, str]:
    """
    Evaluates whether the stored business analysis intelligence for a company is stale.
    Returns (is_stale, reason_or_status).

    If current_docs is None:
    - do not compare hashes
    - return (False, "not_checked") if analysis exists, or (True, "not_analyzed") if no analysis exists
    """
    clean_sym = symbol.upper().strip()
    ai_record = get_cached_ai_analysis(clean_sym)
    if not ai_record:
        return True, "not_analyzed"

    stored_hash = ai_record.get("source_documents_hash")
    if not stored_hash:
        return True, "missing_documents_hash"

    if current_docs is None:
        return False, "not_checked"

    curr_hash = compute_source_documents_hash(current_docs)
    if stored_hash != curr_hash:
        return True, f"source_documents_changed (stored: {stored_hash}, current: {curr_hash})"

    return False, "fresh"

# ---------------------------------------------------------
# STOCKS FINANCIALS CACHE HELPERS
# ---------------------------------------------------------

def get_stock_cache(symbol: str) -> Optional[Dict[str, Any]]:
    """Retrieves raw scraped stock data from cache."""
    clean_sym = symbol.upper().strip()
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT data_json FROM stocks_cache WHERE symbol = ?", (clean_sym,))
        row = cur.fetchone()
        if row:
            return json.loads(row["data_json"])
        return None
    finally:
        conn.close()

def get_all_cached_symbols() -> List[str]:
    """Retrieves all cached stock symbols."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT symbol FROM stocks_cache ORDER BY symbol ASC")
        return [r["symbol"] for r in cur.fetchall()]
    finally:
        conn.close()

def _db_json_serializer(obj: Any) -> Any:
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    return str(obj)

def save_stock_cache(symbol: str, name: str, sector: str, industry: str, data: Dict[str, Any]) -> None:
    """Saves or updates raw scraped stock data in SQLite."""
    clean_sym = symbol.upper().strip()
    now_iso = datetime.now(timezone.utc).isoformat()
    conn = get_db_connection()
    try:
        with conn:
            conn.execute("""
                INSERT INTO stocks_cache (symbol, name, sector, industry, data_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    name = excluded.name,
                    sector = excluded.sector,
                    industry = excluded.industry,
                    data_json = excluded.data_json,
                    updated_at = excluded.updated_at
            """, (clean_sym, name, sector, industry, json.dumps(data, default=_db_json_serializer), now_iso))
    finally:
        conn.close()

def record_projection_computation_state(
    symbol: str,
    fin_data_version: Optional[str] = None,
    doc_intel_version: Optional[str] = None
) -> None:
    """Records the exact financial data and business analysis versions used in the latest projection computation."""
    clean_sym = symbol.upper().strip()
    now_iso = datetime.now(timezone.utc).isoformat()
    conn = get_db_connection()
    try:
        with conn:
            conn.execute("""
                INSERT INTO projection_computation_state (symbol, fin_data_version, doc_intel_version, computed_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    fin_data_version = excluded.fin_data_version,
                    doc_intel_version = excluded.doc_intel_version,
                    computed_at = excluded.computed_at
            """, (clean_sym, fin_data_version, doc_intel_version, now_iso))
    finally:
        conn.close()

def get_projection_computation_state(symbol: str) -> Optional[Dict[str, Any]]:
    """Retrieves the latest recorded projection computation state."""
    clean_sym = symbol.upper().strip()
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM projection_computation_state WHERE symbol = ?", (clean_sym,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

# ---------------------------------------------------------
# PDF PAGE EXTRACTIONS CACHE HELPERS
# ---------------------------------------------------------

def get_cached_document_pages(doc_url: str) -> List[Tuple[int, str]]:
    """Retrieves pre-extracted text pages for a document URL."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT page_num, text_content FROM document_pages_cache WHERE doc_url = ? ORDER BY page_num ASC", (doc_url,))
        rows = cur.fetchall()
        return [(r["page_num"], r["text_content"]) for r in rows]
    finally:
        conn.close()

def save_cached_document_pages(symbol: str, doc_url: str, pages: List[Tuple[int, str]]) -> None:
    """Stores extracted PDF pages in SQLite to prevent repeated network downloads."""
    clean_sym = symbol.upper().strip()
    now_iso = datetime.now(timezone.utc).isoformat()
    conn = get_db_connection()
    try:
        with conn:
            for page_num, text in pages:
                conn.execute("""
                    INSERT OR REPLACE INTO document_pages_cache (symbol, doc_url, page_num, text_content, extracted_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (clean_sym, doc_url, page_num, text, now_iso))
    finally:
        conn.close()

# ---------------------------------------------------------
# PER-DOCUMENT AI SUMMARIES HELPERS
# ---------------------------------------------------------

def find_substantive_alternate_source(
    symbol: str,
    doc_type: str,
    doc_subtype: Optional[str] = None,
    event_key: Optional[str] = None,
    period_or_date: Optional[str] = None,
    failed_url: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Searches the stored/discovered document corpus for an alternative substantive document
    for the exact same canonical event & subtype when a convenience URL fails (e.g. HTTP 403).
    Source priority:
    1. Company IR direct substantive document
    2. BSE/NSE substantive document
    3. Screener convenience transcript
    4. Other verified source
    """
    clean_sym = symbol.upper().strip()
    failed_clean = (failed_url or "").strip().rstrip("/")
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cols = {r[1] for r in cur.execute("PRAGMA table_info(source_documents);").fetchall()}
        has_aliases = "source_aliases" in cols
        select_cols = "title, url, doc_type, period_or_date, discovery_source, actual_source_host"
        if has_aliases:
            select_cols += ", source_aliases"

        cur.execute(f"""
            SELECT {select_cols}
            FROM source_documents
            WHERE symbol = ?
        """, (clean_sym,))
        rows = cur.fetchall()

        candidates = []
        for r in rows:
            all_urls = []
            primary_u = (r["url"] or "").strip().rstrip("/")
            if primary_u and primary_u != failed_clean:
                all_urls.append((primary_u, r["discovery_source"]))

            raw_aliases = r["source_aliases"] if has_aliases and r["source_aliases"] else None
            if raw_aliases:
                try:
                    alias_list = json.loads(raw_aliases) if isinstance(raw_aliases, str) else list(raw_aliases)
                    for a in alias_list:
                        if isinstance(a, str) and (a.startswith("http://") or a.startswith("https://")):
                            clean_a = a.strip().rstrip("/")
                            if clean_a != failed_clean:
                                disc_name = "bse" if "bse" in clean_a else ("ir" if "ir" in clean_a or "company" in clean_a else "alternate")
                                all_urls.append((clean_a, disc_name))
                except Exception:
                    pass

            for cand_url, cand_disc in all_urls:
                if is_document_wrapper(r["title"], cand_url):
                    continue
                norm_dt = normalize_document_type(r["doc_type"], r["title"])
                if norm_dt != doc_type:
                    continue
                r_subtype = derive_document_subtype(norm_dt, r["title"])
                if doc_subtype and r_subtype != doc_subtype:
                    continue
                r_ev = derive_announcement_event_key(clean_sym, r["title"], r["period_or_date"]) if norm_dt == "material_announcements" else derive_earnings_event_key(clean_sym, r["period_or_date"], r["title"])
                if event_key and r_ev and r_ev != event_key:
                    continue
                if not event_key and period_or_date and r["period_or_date"] != period_or_date:
                    continue

                disc = (cand_disc or "").lower()
                host = (r["actual_source_host"] or "").lower()

                # Score by source preference:
                # 1. Company IR (score 3)
                # 2. BSE/NSE (score 2)
                # 3. Screener (score 1)
                # 4. Other (score 0)
                if "company" in disc or "company" in host or "ir" in host:
                    pref_score = 3
                elif "bse" in disc or "nse" in disc or "bseindia" in host or "nseindia" in host or "bseindia" in cand_url or "bse.com" in cand_url:
                    pref_score = 2
                elif "screener" in disc or "screener" in host:
                    pref_score = 1
                else:
                    pref_score = 0

                cand_dict = dict(r)
                cand_dict["url"] = cand_url
                candidates.append((pref_score, cand_dict))

        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            return candidates[0][1]
        return None
    finally:
        conn.close()

def compute_document_content_hash(pages_or_text: Any) -> str:
    """
    Computes a deterministic SHA-256 fingerprint from extracted document pages, text, or raw bytes.
    Normalizes whitespace across lines and pages to ensure consistency.
    """
    if not pages_or_text:
        return ""
    if isinstance(pages_or_text, str):
        normalized = " ".join(pages_or_text.split())
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    if isinstance(pages_or_text, (bytes, bytearray)):
        return hashlib.sha256(pages_or_text).hexdigest()
    if isinstance(pages_or_text, list):
        normalized_parts = []
        for item in pages_or_text:
            if isinstance(item, (tuple, list)) and len(item) >= 2:
                p_num, p_text = item[0], item[1]
                clean = " ".join(str(p_text or "").split())
                normalized_parts.append(f"P{p_num}:{clean}")
            elif isinstance(item, dict):
                p_num = item.get("page") or item.get("page_num") or 0
                clean = " ".join(str(item.get("text") or item.get("text_content") or "").split())
                normalized_parts.append(f"P{p_num}:{clean}")
            elif isinstance(item, str):
                normalized_parts.append(" ".join(item.split()))
        content_str = "\n".join(normalized_parts)
        return hashlib.sha256(content_str.encode("utf-8")).hexdigest()
    return ""

def get_document_summary(
    doc_url: str,
    doc_key: Optional[str] = None,
    symbol: Optional[str] = None,
    doc_type: Optional[str] = None,
    period_or_date: Optional[str] = None,
    expected_content_hash: Optional[str] = None,
    expected_schema_version: Optional[str] = None,
    expected_prompt_version: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Retrieves a single document's cached AI summary by doc_url, canonical doc_key, or unambiguous semantic identity.
    Validates content hash, extraction schema version, and prompt version to ensure freshness.
    """
    c_url = canonicalize_document_url(doc_url) or doc_url
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cols = {r[1] for r in cur.execute("PRAGMA table_info(ai_document_summaries);").fetchall()}

        def _check_and_enrich_row(row_dict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            try:
                data = json.loads(row_dict["summary_json"])
                if "analyzed_at" not in data or not data["analyzed_at"]:
                    data["analyzed_at"] = row_dict.get("generated_at")

                c_hash = row_dict.get("content_hash") or data.get("content_hash")
                s_ver = row_dict.get("extraction_schema_version") or data.get("extraction_schema_version")
                p_ver = row_dict.get("extraction_prompt_version") or data.get("extraction_prompt_version")

                # Check version and hash freshness constraints
                if expected_schema_version and (not s_ver or s_ver != expected_schema_version):
                    return None
                if expected_prompt_version and (not p_ver or p_ver != expected_prompt_version):
                    return None
                if expected_content_hash and (not c_hash or c_hash != expected_content_hash):
                    return None

                data["content_hash"] = c_hash
                data["extraction_schema_version"] = s_ver
                data["extraction_prompt_version"] = p_ver
                data["provider"] = row_dict.get("provider") or data.get("provider")
                data["model"] = row_dict.get("model") or data.get("model")

                if c_hash and s_ver and p_ver:
                    data["cache_status"] = data.get("cache_status") or "CURRENT_VERSION_CONTENT_UNCHECKED"
                else:
                    data["cache_status"] = "LEGACY_STALE"

                return data
            except Exception:
                return None

        # 1. Look up by exact/canonical URL
        select_cols = "summary_json, generated_at"
        if "content_hash" in cols:
            select_cols += ", content_hash, extraction_schema_version, extraction_prompt_version, provider, model"
        if "doc_key" in cols:
            select_cols += ", doc_key"

        cur.execute(f"SELECT {select_cols} FROM ai_document_summaries WHERE doc_url = ? OR doc_url = ?", (doc_url, c_url))
        row = cur.fetchone()
        if row:
            res = _check_and_enrich_row(dict(row))
            if res is not None:
                return res

        # 2. Look up by canonical doc_key if column exists
        target_key = doc_key
        if not target_key and symbol:
            target_key = compute_canonical_document_key(symbol, doc_type or "general", period_or_date, doc_url)
        if target_key and "doc_key" in cols:
            cur.execute(f"SELECT {select_cols} FROM ai_document_summaries WHERE doc_key = ?", (target_key,))
            row = cur.fetchone()
            if row:
                res = _check_and_enrich_row(dict(row))
                if res is not None:
                    return res

        # 3. Look up by unambiguous semantic identity (symbol + doc_type + period_or_date)
        if symbol and doc_type and period_or_date:
            sem_key = compute_canonical_semantic_key(symbol, doc_type, period_or_date)
            if sem_key:
                cur.execute(f"SELECT {select_cols} FROM ai_document_summaries WHERE symbol = ?", (symbol.upper().strip(),))
                rows = cur.fetchall()
                for r in rows:
                    res = _check_and_enrich_row(dict(r))
                    if res:
                        d_sem = compute_canonical_semantic_key(symbol, res.get("doc_type", ""), res.get("period_or_date", ""))
                        if d_sem and d_sem == sem_key:
                            return res
        return None
    finally:
        conn.close()

def get_document_summaries(symbol: str) -> Dict[str, Dict[str, Any]]:
    """
    Returns a dict mapping canonical identities (doc_url, canonicalized url, doc_key, semantic_key)
    to summary_json dicts for a symbol.
    """
    clean_sym = symbol.upper().strip()
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cols = {r[1] for r in cur.execute("PRAGMA table_info(ai_document_summaries);").fetchall()}
        has_doc_key = "doc_key" in cols

        select_cols = "doc_url, summary_json, generated_at"
        if has_doc_key:
            select_cols += ", doc_key"
        if "content_hash" in cols:
            select_cols += ", content_hash, extraction_schema_version, extraction_prompt_version, provider, model"

        cur.execute(f"SELECT {select_cols} FROM ai_document_summaries WHERE symbol = ?", (clean_sym,))
        rows = cur.fetchall()
        res = {}
        for r in rows:
            try:
                data = json.loads(r["summary_json"])
                if "analyzed_at" not in data or not data["analyzed_at"]:
                    data["analyzed_at"] = r["generated_at"]

                raw_url = r["doc_url"]
                c_url = canonicalize_document_url(raw_url)
                doc_k = r["doc_key"] if has_doc_key and r["doc_key"] else compute_canonical_document_key(
                    clean_sym, data.get("doc_type", "general"), data.get("period_or_date"), raw_url, data.get("doc_title")
                )
                data["doc_key"] = doc_k
                data["doc_url"] = raw_url

                if "content_hash" in cols:
                    data["content_hash"] = r["content_hash"] or data.get("content_hash")
                    data["extraction_schema_version"] = r["extraction_schema_version"] or data.get("extraction_schema_version")
                    data["extraction_prompt_version"] = r["extraction_prompt_version"] or data.get("extraction_prompt_version")
                    data["provider"] = r["provider"] or data.get("provider")
                    data["model"] = r["model"] or data.get("model")

                # Assign status badge for UI
                if data.get("cache_status"):
                    pass
                elif data.get("extraction_schema_version") and data.get("extraction_prompt_version") and data.get("content_hash"):
                    data["cache_status"] = "CURRENT_VERSION_CONTENT_UNCHECKED"
                else:
                    data["cache_status"] = "LEGACY_STALE"

                # Map by raw URL
                res[raw_url] = data
                # Map by canonicalized URL
                if c_url:
                    res[c_url] = data
                # Map by canonical doc_key
                if doc_k:
                    res[doc_k] = data
                # Map by semantic key if unambiguous
                sem_key = compute_canonical_semantic_key(clean_sym, data.get("doc_type", ""), data.get("period_or_date", ""))
                if sem_key:
                    res[sem_key] = data
            except Exception:
                pass
        return res
    finally:
        conn.close()

def save_document_summary(
    symbol: str,
    doc_url: str,
    doc_title: str,
    summary_data: Dict[str, Any],
    doc_key: Optional[str] = None,
    doc_type: Optional[str] = None,
    period_or_date: Optional[str] = None,
    content_hash: Optional[str] = None,
    extraction_schema_version: Optional[str] = None,
    extraction_prompt_version: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None
) -> None:
    """Saves per-document executive summary in SQLite with canonical document key and full provenance lineage."""
    clean_sym = symbol.upper().strip()
    now_iso = datetime.now(timezone.utc).isoformat()
    if "analyzed_at" not in summary_data or not summary_data["analyzed_at"]:
        summary_data["analyzed_at"] = now_iso
    c_url = canonicalize_document_url(doc_url) or doc_url

    dt = doc_type or summary_data.get("doc_type") or "general"
    p_date = period_or_date or summary_data.get("period_or_date")

    k = doc_key or summary_data.get("doc_key") or compute_canonical_document_key(clean_sym, dt, p_date, c_url, doc_title)
    c_hash = content_hash or summary_data.get("content_hash")
    s_ver = extraction_schema_version or summary_data.get("extraction_schema_version") or "4.4"
    p_ver = extraction_prompt_version or summary_data.get("extraction_prompt_version") or "4.4.1"
    prov = provider or summary_data.get("provider")
    mod = model or summary_data.get("model") or summary_data.get("model_version")

    summary_data["doc_key"] = k
    summary_data["doc_url"] = c_url
    summary_data["doc_title"] = doc_title
    summary_data["content_hash"] = c_hash
    summary_data["extraction_schema_version"] = s_ver
    summary_data["extraction_prompt_version"] = p_ver
    summary_data["provider"] = prov
    summary_data["model"] = mod
    if "cache_status" not in summary_data:
        summary_data["cache_status"] = "CURRENT_VERSION_CONTENT_UNCHECKED"
    if "doc_type" not in summary_data:
        summary_data["doc_type"] = dt
    if "period_or_date" not in summary_data and p_date:
        summary_data["period_or_date"] = p_date

    conn = get_db_connection()
    try:
        with conn:
            cur = conn.cursor()
            cols = {r[1] for r in cur.execute("PRAGMA table_info(ai_document_summaries);").fetchall()}
            if "content_hash" in cols and "doc_key" in cols:
                conn.execute("""
                    INSERT OR REPLACE INTO ai_document_summaries (
                        doc_url, symbol, doc_title, summary_json, generated_at, doc_key,
                        content_hash, extraction_schema_version, extraction_prompt_version, provider, model
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    c_url, clean_sym, doc_title, json.dumps(summary_data, default=_db_json_serializer),
                    now_iso, k, c_hash, s_ver, p_ver, prov, mod
                ))
            elif "doc_key" in cols:
                conn.execute("""
                    INSERT OR REPLACE INTO ai_document_summaries (doc_url, symbol, doc_title, summary_json, generated_at, doc_key)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (c_url, clean_sym, doc_title, json.dumps(summary_data, default=_db_json_serializer), now_iso, k))
            else:
                conn.execute("""
                    INSERT OR REPLACE INTO ai_document_summaries (doc_url, symbol, doc_title, summary_json, generated_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (c_url, clean_sym, doc_title, json.dumps(summary_data, default=_db_json_serializer), now_iso))
    finally:
        conn.close()

# ---------------------------------------------------------
# INSTITUTIONAL AI ANALYSIS CACHE HELPERS
# ---------------------------------------------------------

def get_cached_ai_analysis(symbol: str) -> Optional[Dict[str, Any]]:
    """Retrieves full institutional AI analysis from SQLite."""
    clean_sym = symbol.upper().strip()
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT intelligence_json, ai_provider, model_version, prompt_tokens, source_documents_count, generated_at
            FROM ai_analysis_cache
            WHERE symbol = ?
        """, (clean_sym,))
        row = cur.fetchone()
        if row:
            data = json.loads(row["intelligence_json"])
            data["ai_provider_used"] = row["ai_provider"]
            data["model_version"] = row["model_version"]
            data["extraction_timestamp"] = row["generated_at"]
            return data
        return None
    finally:
        conn.close()

get_ai_analysis = get_cached_ai_analysis

def save_source_documents(symbol: str, documents: List[Any]) -> None:
    """Persists discovered and verified source documents into SQLite with canonical doc_keys and deduplication."""
    if not documents:
        return
    clean_sym = symbol.upper().strip()
    now_iso = datetime.now(timezone.utc).isoformat()
    deduped = deduplicate_document_records(documents, clean_sym)

    conn = get_db_connection()
    try:
        with conn:
            cur = conn.cursor()
            cols = {r[1] for r in cur.execute("PRAGMA table_info(source_documents);").fetchall()}
            has_doc_key = "doc_key" in cols
            has_sources = "discovered_sources" in cols
            has_aliases = "source_aliases" in cols

            for doc in deduped:
                title = doc.get("title", "")
                url = doc.get("url", "")
                doc_type = doc.get("doc_type", "general")
                period = doc.get("period_or_date")
                discovery = doc.get("discovery_source", "Unknown")
                sources_json = json.dumps(doc.get("discovered_sources") or [discovery])
                aliases_json = json.dumps(doc.get("source_aliases") or [])
                host = doc.get("actual_source_host", "")
                is_valid = doc.get("is_valid", 1)
                doc_key = doc.get("doc_key") or compute_canonical_document_key(
                    clean_sym, doc_type, period, url, title
                )

                if not url:
                    continue

                if has_doc_key and has_sources and has_aliases:
                    conn.execute("""
                        INSERT INTO source_documents (
                            symbol, title, url, doc_type, period_or_date, discovery_source, actual_source_host, is_valid, added_at, doc_key, discovered_sources, source_aliases
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(url) DO UPDATE SET
                            symbol = excluded.symbol,
                            title = excluded.title,
                            doc_type = excluded.doc_type,
                            period_or_date = excluded.period_or_date,
                            discovery_source = excluded.discovery_source,
                            actual_source_host = excluded.actual_source_host,
                            is_valid = excluded.is_valid,
                            doc_key = excluded.doc_key,
                            discovered_sources = excluded.discovered_sources,
                            source_aliases = excluded.source_aliases
                    """, (clean_sym, title, url, doc_type, period, discovery, host, is_valid, now_iso, doc_key, sources_json, aliases_json))
                elif has_doc_key:
                    conn.execute("""
                        INSERT INTO source_documents (
                            symbol, title, url, doc_type, period_or_date, discovery_source, actual_source_host, is_valid, added_at, doc_key
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(url) DO UPDATE SET
                            symbol = excluded.symbol,
                            title = excluded.title,
                            doc_type = excluded.doc_type,
                            period_or_date = excluded.period_or_date,
                            discovery_source = excluded.discovery_source,
                            actual_source_host = excluded.actual_source_host,
                            is_valid = excluded.is_valid,
                            doc_key = excluded.doc_key
                    """, (clean_sym, title, url, doc_type, period, discovery, host, is_valid, now_iso, doc_key))
                else:
                    conn.execute("""
                        INSERT INTO source_documents (
                            symbol, title, url, doc_type, period_or_date, discovery_source, actual_source_host, is_valid, added_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(url) DO UPDATE SET
                            symbol = excluded.symbol,
                            title = excluded.title,
                            doc_type = excluded.doc_type,
                            period_or_date = excluded.period_or_date,
                            discovery_source = excluded.discovery_source,
                            actual_source_host = excluded.actual_source_host,
                            is_valid = excluded.is_valid
                    """, (clean_sym, title, url, doc_type, period, discovery, host, is_valid, now_iso))
    finally:
        conn.close()

def get_source_documents(symbol: str, doc_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves verified and deduplicated canonical source documents from SQLite."""
    clean_sym = symbol.upper().strip()
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cols = {r[1] for r in cur.execute("PRAGMA table_info(source_documents);").fetchall()}
        has_doc_key = "doc_key" in cols
        has_sources = "discovered_sources" in cols
        has_aliases = "source_aliases" in cols

        select_cols = "symbol, title, url, doc_type, period_or_date, discovery_source, actual_source_host, is_valid, added_at"
        if has_doc_key:
            select_cols += ", doc_key"
        if has_sources:
            select_cols += ", discovered_sources"
        if has_aliases:
            select_cols += ", source_aliases"

        cur.execute(f"""
            SELECT {select_cols}
            FROM source_documents
            WHERE symbol = ? AND is_valid = 1
            ORDER BY id DESC
        """, (clean_sym,))
        rows = cur.fetchall()
        raw_list = []
        for r in rows:
            d = dict(r)
            if has_sources and d.get("discovered_sources"):
                try:
                    d["discovered_sources"] = json.loads(d["discovered_sources"])
                except Exception:
                    d["discovered_sources"] = [d["discovery_source"]] if d.get("discovery_source") else []
            if has_aliases and d.get("source_aliases"):
                try:
                    d["source_aliases"] = json.loads(d["source_aliases"])
                except Exception:
                    d["source_aliases"] = []
            raw_list.append(d)

        deduped = deduplicate_document_records(raw_list, clean_sym)

        if doc_type:
            target_norm = normalize_document_type(doc_type)
            return [d for d in deduped if d.get("doc_type") == target_norm]
        return deduped
    finally:
        conn.close()

def save_ai_analysis(
    symbol: str,
    company_name: str,
    intelligence_data: Dict[str, Any],
    ai_provider: str,
    model_version: str = "gemini-3.6-flash",
    prompt_tokens: int = 0,
    source_docs_count: int = 0
) -> str:
    """
    Saves full institutional AI analysis into SQLite.
    Application code strictly owns the authoritative UTC system timestamp:
    - Overwrites intelligence_data["extraction_timestamp"] with canonical system UTC timestamp
    - Persists generated_at in SQLite with the exact same system timestamp
    - Returns the authoritative system timestamp string
    """
    clean_sym = symbol.upper().strip()
    now_iso = datetime.now(timezone.utc).isoformat()
    intelligence_data["extraction_timestamp"] = now_iso
    intelligence_data["ai_provider_used"] = ai_provider
    intelligence_data["model_version"] = model_version

    conn = get_db_connection()
    try:
        with conn:
            conn.execute("""
                INSERT INTO ai_analysis_cache (
                    symbol, company_name, intelligence_json, ai_provider, model_version, prompt_tokens, source_documents_count, generated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    company_name = excluded.company_name,
                    intelligence_json = excluded.intelligence_json,
                    ai_provider = excluded.ai_provider,
                    model_version = excluded.model_version,
                    prompt_tokens = excluded.prompt_tokens,
                    source_documents_count = excluded.source_documents_count,
                    generated_at = excluded.generated_at
            """, (
                clean_sym,
                company_name,
                json.dumps(intelligence_data, default=_db_json_serializer),
                ai_provider,
                model_version,
                prompt_tokens,
                source_docs_count,
                now_iso
            ))
    finally:
        conn.close()

    return now_iso

# ---------------------------------------------------------
# DOCUMENT SOURCES SYNC STATE HELPERS
# ---------------------------------------------------------

def get_document_sources_checked_at(symbol: str) -> Optional[str]:
    """Retrieves the timestamp when document sources were last checked from trusted external sources."""
    clean_sym = symbol.upper().strip()
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT last_checked_at FROM document_sync_state
            WHERE symbol = ?
            ORDER BY last_checked_at DESC
            LIMIT 1
        """, (clean_sym,))
        row = cur.fetchone()
        if row:
            return row["last_checked_at"]
        return None
    finally:
        conn.close()

def get_document_sync_state(symbol: str, category: str = "all") -> Optional[Dict[str, Any]]:
    """Retrieves document sync state for a symbol and category."""
    clean_sym = symbol.upper().strip()
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT symbol, category, last_checked_at, last_filing_date
            FROM document_sync_state
            WHERE symbol = ? AND category = ?
        """, (clean_sym, category))
        row = cur.fetchone()
        if row:
            return dict(row)
        return None
    finally:
        conn.close()

def update_document_sync_state(
    symbol: str,
    category: str = "all",
    checked_at: Optional[str] = None,
    last_filing_date: Optional[str] = None
) -> None:
    """Updates the last_checked_at timestamp when trusted external sources are checked."""
    clean_sym = symbol.upper().strip()
    now_iso = checked_at or datetime.now(timezone.utc).isoformat()
    conn = get_db_connection()
    try:
        with conn:
            conn.execute("""
                INSERT INTO document_sync_state (symbol, category, last_checked_at, last_filing_date)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(symbol, category) DO UPDATE SET
                    last_checked_at = excluded.last_checked_at,
                    last_filing_date = COALESCE(excluded.last_filing_date, document_sync_state.last_filing_date)
            """, (clean_sym, category, now_iso, last_filing_date))
    finally:
        conn.close()

# ---------------------------------------------------------
# PERSISTENT COMPANY KNOWLEDGE FACTS HELPERS
# ---------------------------------------------------------

def save_company_knowledge_facts(symbol: str, facts: List[Dict[str, Any]], clear_doc_urls: Optional[List[str]] = None) -> int:
    """
    Saves extracted company knowledge facts to the persistent SQLite table.
    Optionally clears existing facts for the specific document URLs before inserting to avoid duplicates.
    """
    clean_sym = symbol.upper().strip()
    if not facts:
        return 0

    now_iso = datetime.now(timezone.utc).isoformat()
    conn = get_db_connection()
    inserted_count = 0
    try:
        with conn:
            if clear_doc_urls:
                for u in clear_doc_urls:
                    conn.execute("DELETE FROM company_knowledge_facts WHERE symbol = ? AND doc_url = ?", (clean_sym, u))

            for f in facts:
                doc_url = f.get("doc_url", "")
                doc_title = f.get("doc_title", "Official Filing")
                doc_type = f.get("doc_type", "filing")
                period = f.get("period_or_date") or f.get("period", "")
                category = f.get("category", "operational_kpi")
                metric_name = f.get("metric_name") or f.get("metric", "General KPI")
                stated_value_raw = str(f.get("stated_value_raw") or f.get("value", ""))
                numeric_value = f.get("numeric_value")
                unit = f.get("unit")
                target_period = f.get("target_period")
                scope = f.get("scope", "Consolidated")
                claim_type = f.get("claim_type", "reported_fact")
                quote = f.get("source_quote") or f.get("quote")
                page = f.get("source_page") or f.get("page")
                extracted_at = f.get("extracted_at") or now_iso
                fact_json = json.dumps(f)

                conn.execute("""
                    INSERT INTO company_knowledge_facts (
                        symbol, doc_url, doc_title, doc_type, period_or_date,
                        category, metric_name, stated_value_raw, numeric_value,
                        unit, target_period, scope, claim_type, source_quote,
                        source_page, extracted_at, fact_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    clean_sym, doc_url, doc_title, doc_type, period,
                    category, metric_name, stated_value_raw, numeric_value,
                    unit, target_period, scope, claim_type, quote,
                    page, extracted_at, fact_json
                ))
                inserted_count += 1
        return inserted_count
    finally:
        conn.close()

def get_company_knowledge_facts(symbol: str, category: Optional[str] = None, metric_name: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves persistent company knowledge facts for a symbol with optional filtering."""
    clean_sym = symbol.upper().strip()
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        query = "SELECT * FROM company_knowledge_facts WHERE symbol = ?"
        params = [clean_sym]

        if category:
            query += " AND category = ?"
            params.append(category)
        if metric_name:
            query += " AND metric_name LIKE ?"
            params.append(f"%{metric_name}%")

        query += " ORDER BY id ASC"
        cur.execute(query, tuple(params))
        rows = cur.fetchall()

        results = []
        for r in rows:
            try:
                item = json.loads(r["fact_json"])
            except Exception:
                item = dict(r)
            item["id"] = r["id"]
            item["symbol"] = r["symbol"]
            item["doc_url"] = r["doc_url"]
            item["doc_title"] = r["doc_title"]
            item["doc_type"] = r["doc_type"]
            item["period_or_date"] = r["period_or_date"]
            item["category"] = r["category"]
            item["metric_name"] = r["metric_name"]
            item["stated_value_raw"] = r["stated_value_raw"]
            item["numeric_value"] = r["numeric_value"]
            item["unit"] = r["unit"]
            item["target_period"] = r["target_period"]
            item["scope"] = r["scope"]
            item["claim_type"] = r["claim_type"]
            item["source_quote"] = r["source_quote"]
            item["source_page"] = r["source_page"]
            item["extracted_at"] = r["extracted_at"]
            results.append(item)

        return results
    finally:
        conn.close()

def clear_company_knowledge_facts(symbol: str) -> None:
    """Clears all persistent facts for a given symbol."""
    clean_sym = symbol.upper().strip()
    conn = get_db_connection()
    try:
        with conn:
            conn.execute("DELETE FROM company_knowledge_facts WHERE symbol = ?", (clean_sym,))
    finally:
        conn.close()

# ---------------------------------------------------------
# COMPANY REGISTRY & UNIVERSE HELPERS
# ---------------------------------------------------------

def find_existing_company_row(
    conn: sqlite3.Connection,
    isin: Optional[str] = None,
    nse_symbol: Optional[str] = None,
    bse_code: Optional[str] = None,
    symbol: str = "",
    company_name: Optional[str] = None
) -> Optional[sqlite3.Row]:
    """
    Searches for an existing company record following canonical identity precedence:
    1. ISIN (International Securities Identification Number)
    2. Verified NSE Symbol
    3. Verified BSE Code
    4. Canonical Symbol
    5. Exact Company Name
    """
    cur = conn.cursor()

    # 1. ISIN Precedence
    clean_isin = (isin or "").strip().upper()
    if clean_isin:
        cur.execute("SELECT * FROM company_registry WHERE isin IS NOT NULL AND isin != '' AND isin = ? COLLATE NOCASE LIMIT 1", (clean_isin,))
        row = cur.fetchone()
        if row:
            return row

    # 2. NSE Symbol Precedence
    clean_nse = (nse_symbol or "").strip().upper()
    if clean_nse:
        cur.execute("""
            SELECT * FROM company_registry
            WHERE (nse_symbol IS NOT NULL AND nse_symbol != '' AND nse_symbol = ? COLLATE NOCASE)
               OR symbol = ? COLLATE NOCASE
            LIMIT 1
        """, (clean_nse, clean_nse))
        row = cur.fetchone()
        if row:
            return row

    # 3. BSE Code Precedence
    clean_bse = str(bse_code or "").strip()
    if clean_bse:
        cur.execute("SELECT * FROM company_registry WHERE bse_code IS NOT NULL AND bse_code != '' AND bse_code = ? LIMIT 1", (clean_bse,))
        row = cur.fetchone()
        if row:
            return row

    # 4. Canonical Symbol
    clean_sym = symbol.strip().upper()
    if clean_sym:
        cur.execute("""
            SELECT * FROM company_registry
            WHERE symbol = ? COLLATE NOCASE
               OR (nse_symbol IS NOT NULL AND nse_symbol != '' AND nse_symbol = ? COLLATE NOCASE)
            LIMIT 1
        """, (clean_sym, clean_sym))
        row = cur.fetchone()
        if row:
            return row

    # 5. Exact Company Name
    clean_name = (company_name or "").strip()
    if clean_name and len(clean_name) >= 3:
        cur.execute("SELECT * FROM company_registry WHERE company_name = ? COLLATE NOCASE LIMIT 1", (clean_name,))
        row = cur.fetchone()
        if row:
            return row

    return None

def _merge_aliases(existing_aliases_json: Optional[str], incoming_aliases: Any) -> str:
    """Merges existing and incoming aliases into a deduplicated JSON list."""
    existing_list = []
    if existing_aliases_json:
        try:
            parsed = json.loads(existing_aliases_json)
            if isinstance(parsed, list):
                existing_list = parsed
        except Exception:
            pass

    incoming_list = []
    if isinstance(incoming_aliases, list):
        incoming_list = incoming_aliases
    elif isinstance(incoming_aliases, str):
        try:
            parsed = json.loads(incoming_aliases)
            incoming_list = parsed if isinstance(parsed, list) else [parsed]
        except Exception:
            incoming_list = [incoming_aliases]

    combined = []
    seen = set()
    for a in existing_list + incoming_list:
        a_str = str(a).strip()
        if a_str and a_str.lower() not in seen:
            seen.add(a_str.lower())
            combined.append(a_str)
    return json.dumps(combined)

def upsert_company_registry_item(item: Dict[str, Any]) -> int:
    """
    Inserts or updates a company identity in the company_registry table.
    Uses canonical identity precedence (ISIN > NSE > BSE > Symbol > Name) to safely
    deduplicate and prevent multiple rows for the same security under different identifiers.
    """
    clean_sym = item.get("symbol", "").upper().strip()
    if not clean_sym:
        raise ValueError("Cannot upsert company registry item without a symbol")

    company_name = (item.get("company_name") or clean_sym).strip()
    raw_nse = item.get("nse_symbol")
    nse_symbol = raw_nse.upper().strip() if raw_nse else None
    bse_code = str(item.get("bse_code") or "").strip() or None
    isin = (item.get("isin") or "").upper().strip() or None
    exchange = (item.get("exchange") or "").strip() or None
    sector = item.get("sector")
    industry = item.get("industry")
    incoming_aliases = item.get("aliases", [])

    in_universe_val = item.get("in_universe")
    is_active_val = item.get("is_active")
    source = item.get("source", "manual")
    now_iso = datetime.now(timezone.utc).isoformat()
    source_last_verified_at = item.get("source_last_verified_at")
    identity_source_name = item.get("identity_source_name")
    identity_source_url = item.get("identity_source_url")
    identity_verified_at = item.get("identity_verified_at")

    conn = get_db_connection()
    try:
        with conn:
            existing = find_existing_company_row(
                conn,
                isin=isin,
                nse_symbol=nse_symbol,
                bse_code=bse_code,
                symbol=clean_sym,
                company_name=company_name
            )

            if existing:
                existing_dict = dict(existing)
                row_id = existing_dict["id"]
                merged_aliases_json = _merge_aliases(existing_dict.get("aliases"), incoming_aliases)

                # Determine updated field values
                up_name = company_name if company_name and company_name != clean_sym else (existing_dict.get("company_name") or company_name)
                up_nse = nse_symbol or existing_dict.get("nse_symbol")
                up_bse = bse_code or existing_dict.get("bse_code")
                up_isin = isin or existing_dict.get("isin")
                up_exchange = exchange or existing_dict.get("exchange")
                up_sector = sector if sector and sector not in ("Broad Market", "Unclassified") else (existing_dict.get("sector") or sector or "Unclassified")
                up_industry = industry if industry and industry not in ("Indian Equities", "Unclassified") else (existing_dict.get("industry") or industry or "Unclassified")

                up_in_uni = (1 if in_universe_val else 0) if in_universe_val is not None else existing_dict.get("in_universe")
                up_is_act = (1 if is_active_val else 0) if is_active_val is not None else existing_dict.get("is_active")
                up_source = source if source in ("NSE", "BSE", "nse_master", "bse_master") else (existing_dict.get("source") or source)
                up_verif_at = source_last_verified_at or existing_dict.get("source_last_verified_at")
                up_id_name = identity_source_name or existing_dict.get("identity_source_name")
                up_id_url = identity_source_url or existing_dict.get("identity_source_url")
                up_id_verif = identity_verified_at or existing_dict.get("identity_verified_at")

                conn.execute("""
                    UPDATE company_registry
                    SET company_name = ?,
                        nse_symbol = ?,
                        bse_code = ?,
                        isin = ?,
                        exchange = ?,
                        sector = ?,
                        industry = ?,
                        aliases = ?,
                        in_universe = ?,
                        is_active = ?,
                        source = ?,
                        source_last_verified_at = ?,
                        identity_source_name = ?,
                        identity_source_url = ?,
                        identity_verified_at = ?,
                        updated_at = ?
                    WHERE id = ?
                """, (
                    up_name, up_nse, up_bse, up_isin, up_exchange,
                    up_sector, up_industry, merged_aliases_json,
                    up_in_uni, up_is_act, up_source, up_verif_at,
                    up_id_name, up_id_url, up_id_verif, now_iso,
                    row_id
                ))
                return row_id
            else:
                aliases_json = _merge_aliases(None, incoming_aliases)
                in_uni = 1 if in_universe_val is not False else 0
                is_act = 1 if is_active_val is not False else 0
                sec_val = sector or "Unclassified"
                ind_val = industry or "Unclassified"

                cur = conn.execute("""
                    INSERT INTO company_registry (
                        symbol, company_name, nse_symbol, bse_code, isin,
                        exchange, sector, industry, aliases, is_active,
                        in_universe, source, source_last_verified_at,
                        identity_source_name, identity_source_url, identity_verified_at,
                        created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    clean_sym, company_name, nse_symbol, bse_code, isin,
                    exchange, sec_val, ind_val, aliases_json, is_act,
                    in_uni, source, source_last_verified_at,
                    identity_source_name, identity_source_url, identity_verified_at,
                    now_iso, now_iso
                ))
                return cur.lastrowid or 0
    finally:
        conn.close()

def get_company_by_symbol(symbol: str) -> Optional[Dict[str, Any]]:
    """Retrieves a single company identity by symbol (case-insensitive) or NSE symbol / BSE code."""
    clean_sym = symbol.upper().strip()
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM company_registry
            WHERE symbol = ? COLLATE NOCASE OR nse_symbol = ? COLLATE NOCASE OR bse_code = ?
            LIMIT 1
        """, (clean_sym, clean_sym, clean_sym))
        row = cur.fetchone()
        if row:
            res = dict(row)
            try:
                res["aliases"] = json.loads(res.get("aliases") or "[]")
            except Exception:
                res["aliases"] = []
            res["is_active"] = bool(res.get("is_active"))
            res["in_universe"] = bool(res.get("in_universe"))
            return res
        return None
    finally:
        conn.close()

def get_company_by_name(company_name: str) -> Optional[Dict[str, Any]]:
    """Retrieves a single company identity by exact company name (case-insensitive)."""
    clean_name = company_name.strip()
    if not clean_name:
        return None
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM company_registry
            WHERE company_name = ? COLLATE NOCASE
            LIMIT 1
        """, (clean_name,))
        row = cur.fetchone()
        if row:
            res = dict(row)
            try:
                res["aliases"] = json.loads(res.get("aliases") or "[]")
            except Exception:
                res["aliases"] = []
            res["is_active"] = bool(res.get("is_active"))
            res["in_universe"] = bool(res.get("in_universe"))
            return res
        return None
    finally:
        conn.close()

def get_company_by_bse_code(bse_code: str) -> Optional[Dict[str, Any]]:
    """Retrieves a single company identity by BSE security code."""
    clean_bse = str(bse_code or "").strip()
    if not clean_bse:
        return None
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM company_registry
            WHERE bse_code = ?
            LIMIT 1
        """, (clean_bse,))
        row = cur.fetchone()
        if row:
            res = dict(row)
            try:
                res["aliases"] = json.loads(res.get("aliases") or "[]")
            except Exception:
                res["aliases"] = []
            res["is_active"] = bool(res.get("is_active"))
            res["in_universe"] = bool(res.get("in_universe"))
            return res
        return None
    finally:
        conn.close()

def get_company_registry_total_count() -> int:
    """Returns the total count of all registered companies regardless of active/universe state."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM company_registry")
        row = cur.fetchone()
        return row[0] if row else 0
    finally:
        conn.close()

def get_universe_companies(active_only: bool = True) -> List[Dict[str, Any]]:
    """Retrieves all companies currently enrolled in the Stocker universe."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        if active_only:
            cur.execute("""
                SELECT * FROM company_registry
                WHERE in_universe = 1 AND is_active = 1
                ORDER BY symbol ASC
            """)
        else:
            cur.execute("""
                SELECT * FROM company_registry
                ORDER BY symbol ASC
            """)
        rows = cur.fetchall()
        results = []
        for r in rows:
            res = dict(r)
            try:
                res["aliases"] = json.loads(res.get("aliases") or "[]")
            except Exception:
                res["aliases"] = []
            res["is_active"] = bool(res.get("is_active"))
            res["in_universe"] = bool(res.get("in_universe"))
            results.append(res)
        return results
    finally:
        conn.close()

def get_universe_symbols(active_only: bool = True) -> List[str]:
    """Retrieves canonical symbols for all active universe companies."""
    companies = get_universe_companies(active_only=active_only)
    return [c["symbol"] for c in companies]

def set_company_universe_status(symbol: str, in_universe: bool = True, is_active: bool = True) -> bool:
    """Updates active/in_universe status for a registered company."""
    clean_sym = symbol.upper().strip()
    now_iso = datetime.now(timezone.utc).isoformat()
    conn = get_db_connection()
    try:
        with conn:
            cur = conn.execute("""
                UPDATE company_registry
                SET in_universe = ?, is_active = ?, updated_at = ?
                WHERE symbol = ? COLLATE NOCASE OR nse_symbol = ? COLLATE NOCASE
            """, (1 if in_universe else 0, 1 if is_active else 0, now_iso, clean_sym, clean_sym))
            return cur.rowcount > 0
    finally:
        conn.close()

def search_local_registry(query: str, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Searches the local SQLite company registry across symbol, company_name, and aliases.
    Supports exact, prefix, substring, and multi-word token queries.
    """
    clean_q = query.strip()
    if not clean_q:
        return []

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        pattern = f"%{clean_q}%"

        # Extract alphanumeric search tokens (omitting common noise words)
        tokens = [
            t for t in re.split(r"[\s\(\),.-]+", clean_q)
            if len(t) >= 3 and t.lower() not in {"ltd", "limited", "pvt", "private", "corp", "corporation", "inc", "co", "the", "and", "india"}
        ]

        token_clauses = []
        token_params = [pattern, pattern, pattern, pattern, pattern]
        for t in tokens:
            token_clauses.append("(company_name LIKE ? OR aliases LIKE ? OR symbol LIKE ?)")
            token_params.extend([f"%{t}%", f"%{t}%", f"%{t}%"])

        where_sql = "symbol LIKE ? OR company_name LIKE ? OR nse_symbol LIKE ? OR aliases LIKE ? OR bse_code LIKE ?"
        if token_clauses:
            where_sql += " OR " + " OR ".join(token_clauses)

        order_params = [clean_q, clean_q, clean_q, f"{clean_q}%", f"{clean_q}%", limit]

        cur.execute(f"""
            SELECT * FROM company_registry
            WHERE {where_sql}
            ORDER BY
                CASE
                    WHEN symbol = ? COLLATE NOCASE THEN 1
                    WHEN nse_symbol = ? COLLATE NOCASE THEN 2
                    WHEN company_name = ? COLLATE NOCASE THEN 3
                    WHEN symbol LIKE ? THEN 4
                    WHEN company_name LIKE ? THEN 5
                    ELSE 6
                END,
                symbol ASC
            LIMIT ?
        """, tuple(token_params + order_params))
        rows = cur.fetchall()
        results = []
        for r in rows:
            res = dict(r)
            try:
                res["aliases"] = json.loads(res.get("aliases") or "[]")
            except Exception:
                res["aliases"] = []
            res["is_active"] = bool(res.get("is_active"))
            res["in_universe"] = bool(res.get("in_universe"))
            results.append(res)
        return results
    finally:
        conn.close()

def seed_company_registry(seed_records: Optional[List[Dict[str, Any]]] = None) -> int:
    """
    Seeds the company_registry table with anchor companies and any already-cached stocks.
    Safe and idempotent:
    - Never overwrites or resets user removal (in_universe=0 or is_active=0)
    - Updates metadata without creating duplicates
    """
    try:
        from data_seed import SEED_REGISTRY_COMPANIES, COMPANY_METADATA
    except ImportError:
        import sys
        sys.path.insert(0, str(Path(__file__).parent))
        from data_seed import SEED_REGISTRY_COMPANIES, COMPANY_METADATA

    records_to_seed = list(seed_records or SEED_REGISTRY_COMPANIES)

    # Check cached stocks in stocks_cache.json as one-time legacy bootstrap migration
    # Note: cache-derived legacy identities have UNVERIFIED exchange fields (nse_symbol=None, exchange=None)
    cache_file = DB_PATH.parent / "stocks_cache.json"
    if cache_file.exists():
        try:
            with open(cache_file, "r") as f:
                cached_json = json.load(f)
                for sym, stock_dict in cached_json.items():
                    clean_s = sym.upper().strip()
                    if not any(r.get("symbol", "").upper() == clean_s for r in records_to_seed):
                        meta = COMPANY_METADATA.get(clean_s, {})
                        records_to_seed.append({
                            "symbol": clean_s,
                            "company_name": stock_dict.get("name") or clean_s,
                            "nse_symbol": None,
                            "bse_code": None,
                            "isin": None,
                            "exchange": None,
                            "sector": stock_dict.get("sector") or meta.get("sector") or "Unclassified",
                            "industry": stock_dict.get("industry") or meta.get("industry") or "Unclassified",
                            "aliases": [clean_s, stock_dict.get("name") or clean_s],
                            "in_universe": True,
                            "is_active": True,
                            "source": "stocks_cache",
                            "identity_source_name": "stocks_cache",
                            "identity_source_url": None,
                            "identity_verified_at": None
                        })
        except Exception:
            pass

    inserted_count = 0
    now_iso = datetime.now(timezone.utc).isoformat()
    conn = get_db_connection()
    try:
        with conn:
            for rec in records_to_seed:
                sym = rec.get("symbol", "").upper().strip()
                name = rec.get("company_name", sym).strip()
                nse = (rec.get("nse_symbol") or "").upper().strip() or None
                bse = str(rec.get("bse_code") or "").strip() or None
                isin = (rec.get("isin") or "").upper().strip() or None
                exchange = (rec.get("exchange") or "").strip() or None
                sector = rec.get("sector", "Unclassified")
                industry = rec.get("industry", "Unclassified")
                aliases = rec.get("aliases", [])
                source = rec.get("source", "seed_reference")
                id_src_name = rec.get("identity_source_name") or (source if source == "seed_reference" else None)
                id_src_url = rec.get("identity_source_url")
                id_ver_at = rec.get("identity_verified_at")

                existing = find_existing_company_row(
                    conn,
                    isin=isin,
                    nse_symbol=nse,
                    bse_code=bse,
                    symbol=sym,
                    company_name=name
                )

                if existing:
                    # Do NOT overwrite in_universe or is_active if user modified them!
                    # Only update canonical identity metadata and merge aliases
                    merged_aliases = _merge_aliases(existing["aliases"], aliases)
                    conn.execute("""
                        UPDATE company_registry
                        SET company_name = COALESCE(?, company_name),
                            nse_symbol = COALESCE(?, nse_symbol),
                            bse_code = COALESCE(?, bse_code),
                            isin = COALESCE(?, isin),
                            exchange = COALESCE(?, exchange),
                            sector = CASE WHEN ? NOT IN ('Broad Market', 'Unclassified') THEN ? ELSE sector END,
                            industry = CASE WHEN ? NOT IN ('Indian Equities', 'Unclassified') THEN ? ELSE industry END,
                            aliases = ?,
                            updated_at = ?
                        WHERE id = ?
                    """, (
                        name, nse, bse, isin, exchange,
                        sector, sector, industry, industry,
                        merged_aliases, now_iso,
                        existing["id"]
                    ))
                else:
                    aliases_json = _merge_aliases(None, aliases)
                    in_uni = 1 if rec.get("in_universe", True) else 0
                    is_act = 1 if rec.get("is_active", True) else 0

                    conn.execute("""
                        INSERT INTO company_registry (
                            symbol, company_name, nse_symbol, bse_code, isin,
                            exchange, sector, industry, aliases, is_active,
                            in_universe, source, source_last_verified_at,
                            identity_source_name, identity_source_url, identity_verified_at,
                            created_at, updated_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        sym, name, nse, bse, isin,
                        exchange, sector, industry, aliases_json, is_act,
                        in_uni, source, id_ver_at,
                        id_src_name, id_src_url, id_ver_at,
                        now_iso, now_iso
                    ))
                    inserted_count += 1
        return inserted_count
    finally:
        conn.close()

# Source precedence tier ranking (Higher integer = Higher authority)
SOURCE_PRECEDENCE_TIER: Dict[str, int] = {
    "verified_official": 100,
    "NSE": 100,
    "BSE": 100,
    "nse_master": 100,
    "bse_master": 100,
    "Company IR": 80,
    "company_ir": 80,
    "seed_reference": 50,
    "seed": 50,
    "screener_ingestion": 30,
    "stocks_cache": 20,
    "screener_search": 10,
    "unresolved_input": 5,
    "manual": 5,
    "local": 5
}

def upgrade_company_authoritative_identity(symbol: str, official_data: Dict[str, Any]) -> bool:
    """
    Upgrades an existing company registry record with verified authoritative exchange/IR metadata
    following strict source precedence.
    - Never creates a duplicate company row.
    - Preserves in_universe, is_active, aliases, and user status.
    - Upgrades source only if incoming source tier is >= existing source tier.
    - Weaker discovery sources can NEVER overwrite verified official metadata.
    """
    clean_sym = symbol.strip().upper()
    if not clean_sym:
        return False

    conn = get_db_connection()
    try:
        with conn:
            existing = find_existing_company_row(
                conn,
                isin=official_data.get("isin"),
                nse_symbol=official_data.get("nse_symbol"),
                bse_code=official_data.get("bse_code"),
                symbol=clean_sym,
                company_name=official_data.get("company_name")
            )

            now_iso = datetime.now(timezone.utc).isoformat()
            incoming_source = official_data.get("source", "verified_official")
            incoming_tier = SOURCE_PRECEDENCE_TIER.get(incoming_source, 50)

            if existing:
                row_id = existing["id"]
                existing_source = existing["source"] or "local"
                existing_tier = SOURCE_PRECEDENCE_TIER.get(existing_source, 10)

                # Check if incoming tier is high enough to upgrade
                if incoming_tier >= existing_tier:
                    final_source = incoming_source
                    final_name = official_data.get("company_name") or existing["company_name"]
                    final_nse = official_data.get("nse_symbol") or existing["nse_symbol"]
                    final_bse = str(official_data.get("bse_code") or "").strip() or existing["bse_code"]
                    final_isin = (official_data.get("isin") or "").upper().strip() or existing["isin"]
                    final_exch = official_data.get("exchange") or existing["exchange"]
                    id_src_name = official_data.get("identity_source_name") or incoming_source
                    id_src_url = official_data.get("identity_source_url") or existing["identity_source_url"]
                    id_ver_at = official_data.get("identity_verified_at") or now_iso
                else:
                    # Keep existing higher-tier metadata; do NOT overwrite verified fields with weaker source
                    final_source = existing_source
                    final_name = existing["company_name"]
                    final_nse = existing["nse_symbol"]
                    final_bse = existing["bse_code"]
                    final_isin = existing["isin"]
                    final_exch = existing["exchange"]
                    id_src_name = existing["identity_source_name"]
                    id_src_url = existing["identity_source_url"]
                    id_ver_at = existing["identity_verified_at"]

                # Merge aliases without losing existing ones
                incoming_aliases = official_data.get("aliases", [])
                merged_aliases_json = _merge_aliases(existing["aliases"], incoming_aliases)

                conn.execute("""
                    UPDATE company_registry
                    SET company_name = ?,
                        nse_symbol = ?,
                        bse_code = ?,
                        isin = ?,
                        exchange = ?,
                        aliases = ?,
                        source = ?,
                        source_last_verified_at = ?,
                        identity_source_name = ?,
                        identity_source_url = ?,
                        identity_verified_at = ?,
                        updated_at = ?
                    WHERE id = ?
                """, (
                    final_name, final_nse, final_bse, final_isin, final_exch,
                    merged_aliases_json, final_source, id_ver_at,
                    id_src_name, id_src_url, id_ver_at, now_iso,
                    row_id
                ))
                return True
            else:
                # If record doesn't exist yet, insert with authoritative metadata
                upsert_company_registry_item(official_data)
                return True
    finally:
        conn.close()

def save_financial_verification_records(records: List[Dict[str, Any]]) -> int:
    """
    Persists financial verification items into the financial_verification_records table.
    Updates existing records for the same (symbol, canonical_period, canonical_metric, scope).
    """
    if not records:
        return 0

    conn = get_db_connection()
    now_iso = datetime.now(timezone.utc).isoformat()
    saved_count = 0

    try:
        with conn:
            for rec in records:
                sym = rec.get("symbol", "").upper().strip()
                metric_name = rec.get("metric_name", "")
                canon_metric = rec.get("canonical_metric", metric_name).upper().strip()
                period = rec.get("period", "")
                canon_period = rec.get("canonical_period", period).strip()
                scope = rec.get("scope", "Consolidated").capitalize().strip()

                scr_val = rec.get("screener_value")
                off_val = rec.get("official_value")
                var_abs = rec.get("variance_abs")
                var_pct = rec.get("variance_pct")
                unit = rec.get("unit", "₹ Cr")
                curr = rec.get("currency", "INR")
                status = rec.get("status", "INSUFFICIENT_EVIDENCE")
                tol_used = rec.get("tolerance_used")
                scr_url = rec.get("screener_source_url")
                off_url = rec.get("official_source_url")
                off_name = rec.get("official_source_name", "NSE Filing")
                off_doc_id = rec.get("official_document_id")
                notes = rec.get("notes")
                ver_at = rec.get("verified_at") or now_iso

                # Check for existing record
                cur = conn.execute("""
                    SELECT id FROM financial_verification_records
                    WHERE symbol = ? AND canonical_period = ? AND canonical_metric = ? AND scope = ?
                """, (sym, canon_period, canon_metric, scope))
                row = cur.fetchone()

                if row:
                    conn.execute("""
                        UPDATE financial_verification_records
                        SET metric_name = ?,
                            period = ?,
                            screener_value = ?,
                            official_value = ?,
                            variance_abs = ?,
                            variance_pct = ?,
                            unit = ?,
                            currency = ?,
                            status = ?,
                            tolerance_used = ?,
                            screener_source_url = ?,
                            official_source_url = ?,
                            official_source_name = ?,
                            official_document_id = ?,
                            notes = ?,
                            verified_at = ?,
                            updated_at = ?
                        WHERE id = ?
                    """, (
                        metric_name, period, scr_val, off_val, var_abs, var_pct,
                        unit, curr, status, tol_used, scr_url, off_url,
                        off_name, off_doc_id, notes, ver_at, now_iso,
                        row["id"]
                    ))
                else:
                    conn.execute("""
                        INSERT INTO financial_verification_records (
                            symbol, metric_name, canonical_metric, period, canonical_period,
                            scope, screener_value, official_value, variance_abs, variance_pct,
                            unit, currency, status, tolerance_used, screener_source_url,
                            official_source_url, official_source_name, official_document_id,
                            notes, verified_at, created_at, updated_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        sym, metric_name, canon_metric, period, canon_period,
                        scope, scr_val, off_val, var_abs, var_pct,
                        unit, curr, status, tol_used, scr_url,
                        off_url, off_name, off_doc_id, notes, ver_at,
                        now_iso, now_iso
                    ))
                saved_count += 1
        return saved_count
    finally:
        conn.close()

def get_financial_verification_records(symbol: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Retrieves chronological financial verification records for a company."""
    clean_sym = symbol.strip().upper()
    conn = get_db_connection()
    try:
        cur = conn.execute("""
            SELECT * FROM financial_verification_records
            WHERE symbol = ?
            ORDER BY canonical_period DESC, canonical_metric ASC
            LIMIT ?
        """, (clean_sym, limit))
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def get_financial_verification_summary(symbol: str) -> Dict[str, Any]:
    """
    Computes an aggregated financial verification summary including authoritative identity metadata,
    counts by verification status, and calculated confidence level.
    """
    clean_sym = symbol.strip().upper()
    company = get_company_by_symbol(clean_sym) or {}
    records = get_financial_verification_records(clean_sym, limit=100)

    total = len(records)
    verified = sum(1 for r in records if r.get("status") == "VERIFIED")
    discrepancy = sum(1 for r in records if r.get("status") == "DISCREPANCY")
    not_comparable = sum(1 for r in records if r.get("status") == "NOT_COMPARABLE")
    missing_source = sum(1 for r in records if r.get("status") in ("OFFICIAL_SOURCE_MISSING", "SCREENER_VALUE_MISSING", "INSUFFICIENT_EVIDENCE"))

    if discrepancy > 0:
        overall_status = "DISCREPANCY"
    elif verified > 0 and discrepancy == 0:
        overall_status = "VERIFIED"
    elif not_comparable > 0:
        overall_status = "NOT_COMPARABLE"
    elif missing_source > 0:
        overall_status = "OFFICIAL_SOURCE_MISSING"
    else:
        overall_status = "UNVERIFIED"

    confidence = round(verified / total, 2) if total > 0 else 0.0
    if discrepancy > 0:
        confidence = max(0.0, round(1.0 - (discrepancy / max(total, 1)), 2))

    last_verified = None
    if records:
        last_verified = max((r.get("verified_at") or "") for r in records)

    return {
        "symbol": clean_sym,
        "overall_status": overall_status,
        "total_metrics_checked": total,
        "verified_count": verified,
        "discrepancy_count": discrepancy,
        "not_comparable_count": not_comparable,
        "missing_source_count": missing_source,
        "authoritative_source_name": company.get("identity_source_name") or company.get("source") or "Screener Standardized",
        "identity_source_name": company.get("identity_source_name"),
        "identity_source_url": company.get("identity_source_url"),
        "identity_verified_at": company.get("identity_verified_at") or company.get("source_last_verified_at"),
        "isin": company.get("isin"),
        "nse_symbol": company.get("nse_symbol"),
        "bse_code": company.get("bse_code"),
        "exchange": company.get("exchange"),
        "last_verified_at": last_verified or company.get("identity_verified_at") or company.get("source_last_verified_at"),
        "confidence_score": confidence if total > 0 else (1.0 if company.get("source") in ("NSE", "BSE", "verified_official") else 0.0)
    }

# ---------------------------------------------------------
# CANONICAL FINANCIAL TRUTH HELPERS (PHASE 2A)
# ---------------------------------------------------------

def save_canonical_financial_facts(
    symbol: str,
    facts: List[Dict[str, Any]],
    coverage_summary: Dict[str, Any],
    input_financial_version: Optional[str] = None,
    verification_version: Optional[str] = None,
    computed_at: Optional[str] = None
) -> None:
    """
    Persists canonical financial facts and truth container state for a company.
    Replaces existing facts for the symbol atomically within a transaction.
    """
    clean_sym = symbol.upper().strip()
    now_iso = computed_at or datetime.now(timezone.utc).isoformat()
    conn = get_db_connection()
    try:
        with conn:
            # 1. Clear prior facts for this symbol
            conn.execute("DELETE FROM canonical_financial_facts WHERE symbol = ?", (clean_sym,))

            # 2. Insert new canonical facts
            for f in facts:
                conn.execute("""
                    INSERT INTO canonical_financial_facts (
                        symbol, canonical_metric, display_metric, period, canonical_period, scope,
                        canonical_value, unit, currency, selected_source_type, selected_source_name,
                        selected_source_url, screener_value, official_value, verification_status,
                        difference_absolute, difference_pct, confidence, provenance_note,
                        verified_at, computed_at, input_financial_version, verification_version
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    clean_sym,
                    f.get("canonical_metric", ""),
                    f.get("display_metric", ""),
                    f.get("period", ""),
                    f.get("canonical_period", ""),
                    f.get("scope", "Consolidated"),
                    f.get("value"),
                    f.get("unit", "₹ Cr"),
                    f.get("currency", "INR"),
                    f.get("selected_source_type", "unverified"),
                    f.get("selected_source_name"),
                    f.get("selected_source_url"),
                    f.get("screener_value"),
                    f.get("official_value"),
                    f.get("verification_status", "UNVERIFIED"),
                    f.get("difference_absolute"),
                    f.get("difference_pct"),
                    f.get("confidence", "Unverified"),
                    f.get("provenance_note", ""),
                    f.get("verified_at"),
                    f.get("computed_at") or now_iso,
                    input_financial_version,
                    verification_version
                ))

            # 3. Upsert truth header state
            conn.execute("""
                INSERT INTO canonical_financial_truth_state (
                    symbol, input_financial_version, verification_version, target_facts_count,
                    verified_count, discrepancies_count, not_comparable_count, insufficient_evidence_count,
                    official_source_missing_count, screener_value_missing_count, unverified_count,
                    coverage_pct, overall_truth_state, computed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    input_financial_version = excluded.input_financial_version,
                    verification_version = excluded.verification_version,
                    target_facts_count = excluded.target_facts_count,
                    verified_count = excluded.verified_count,
                    discrepancies_count = excluded.discrepancies_count,
                    not_comparable_count = excluded.not_comparable_count,
                    insufficient_evidence_count = excluded.insufficient_evidence_count,
                    official_source_missing_count = excluded.official_source_missing_count,
                    screener_value_missing_count = excluded.screener_value_missing_count,
                    unverified_count = excluded.unverified_count,
                    coverage_pct = excluded.coverage_pct,
                    overall_truth_state = excluded.overall_truth_state,
                    computed_at = excluded.computed_at
            """, (
                clean_sym,
                input_financial_version,
                verification_version,
                coverage_summary.get("target_facts_count", len(facts)),
                coverage_summary.get("officially_verified_count", 0),
                coverage_summary.get("discrepancy_count", 0),
                coverage_summary.get("not_comparable_count", 0),
                coverage_summary.get("insufficient_evidence_count", 0),
                coverage_summary.get("official_source_missing_count", 0),
                coverage_summary.get("screener_value_missing_count", 0),
                coverage_summary.get("unverified_count", 0),
                coverage_summary.get("coverage_pct", 0.0),
                coverage_summary.get("overall_truth_state", "UNVERIFIED"),
                now_iso
            ))
    finally:
        conn.close()

def get_canonical_financial_facts(symbol: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves the complete persisted Canonical Financial Truth container for a symbol.
    Returns None if no truth records have been computed/persisted.
    """
    clean_sym = symbol.upper().strip()
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM canonical_financial_truth_state WHERE symbol = ?", (clean_sym,))
        st_row = cur.fetchone()
        if not st_row:
            return None

        cur.execute("SELECT * FROM canonical_financial_facts WHERE symbol = ? ORDER BY id ASC", (clean_sym,))
        fact_rows = cur.fetchall()

        facts = []
        for r in fact_rows:
            facts.append({
                "symbol": r["symbol"],
                "canonical_metric": r["canonical_metric"],
                "display_metric": r["display_metric"],
                "period": r["period"],
                "canonical_period": r["canonical_period"],
                "scope": r["scope"],
                "value": r["canonical_value"],
                "unit": r["unit"],
                "currency": r["currency"],
                "selected_source_type": r["selected_source_type"],
                "selected_source_name": r["selected_source_name"],
                "selected_source_url": r["selected_source_url"],
                "screener_value": r["screener_value"],
                "official_value": r["official_value"],
                "verification_status": r["verification_status"],
                "difference_absolute": r["difference_absolute"],
                "difference_pct": r["difference_pct"],
                "confidence": r["confidence"],
                "provenance_note": r["provenance_note"],
                "verified_at": r["verified_at"],
                "computed_at": r["computed_at"]
            })

        coverage = {
            "symbol": clean_sym,
            "target_facts_count": st_row["target_facts_count"],
            "officially_verified_count": st_row["verified_count"],
            "discrepancy_count": st_row["discrepancies_count"],
            "not_comparable_count": st_row["not_comparable_count"],
            "insufficient_evidence_count": st_row["insufficient_evidence_count"],
            "official_source_missing_count": st_row["official_source_missing_count"],
            "screener_value_missing_count": st_row["screener_value_missing_count"],
            "unverified_count": st_row["unverified_count"],
            "coverage_pct": st_row["coverage_pct"],
            "overall_truth_state": st_row["overall_truth_state"]
        }

        return {
            "symbol": clean_sym,
            "facts": facts,
            "coverage": coverage,
            "discrepancies_count": st_row["discrepancies_count"],
            "verified_count": st_row["verified_count"],
            "unverified_count": st_row["unverified_count"],
            "last_computed_at": st_row["computed_at"],
            "input_financial_version": st_row["input_financial_version"],
            "verification_version": st_row["verification_version"]
        }
    finally:
        conn.close()

def get_canonical_fact_by_key(symbol: str, canonical_metric: str, period: str, scope: str = "Consolidated") -> Optional[Dict[str, Any]]:
    """Retrieves a single canonical financial fact by symbol, canonical_metric, period, and scope."""
    clean_sym = symbol.upper().strip()
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM canonical_financial_facts
            WHERE symbol = ? AND canonical_metric = ? AND (period = ? OR canonical_period = ?) AND scope = ?
            LIMIT 1
        """, (clean_sym, canonical_metric.upper().strip(), period, period, scope.capitalize()))
        r = cur.fetchone()
        if not r:
            return None
        return {
            "symbol": r["symbol"],
            "canonical_metric": r["canonical_metric"],
            "display_metric": r["display_metric"],
            "period": r["period"],
            "canonical_period": r["canonical_period"],
            "scope": r["scope"],
            "value": r["canonical_value"],
            "unit": r["unit"],
            "currency": r["currency"],
            "selected_source_type": r["selected_source_type"],
            "selected_source_name": r["selected_source_name"],
            "selected_source_url": r["selected_source_url"],
            "screener_value": r["screener_value"],
            "official_value": r["official_value"],
            "verification_status": r["verification_status"],
            "difference_absolute": r["difference_absolute"],
            "difference_pct": r["difference_pct"],
            "confidence": r["confidence"],
            "provenance_note": r["provenance_note"],
            "verified_at": r["verified_at"],
            "computed_at": r["computed_at"]
        }
    finally:
        conn.close()

def get_canonical_facts_series(symbol: str, canonical_metric: str, scope: str = "Consolidated") -> List[Dict[str, Any]]:
    """Retrieves a time series of canonical financial facts for a given metric and scope."""
    clean_sym = symbol.upper().strip()
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM canonical_financial_facts
            WHERE symbol = ? AND canonical_metric = ? AND scope = ?
            ORDER BY id ASC
        """, (clean_sym, canonical_metric.upper().strip(), scope.capitalize()))
        rows = cur.fetchall()
        series = []
        for r in rows:
            series.append({
                "symbol": r["symbol"],
                "canonical_metric": r["canonical_metric"],
                "display_metric": r["display_metric"],
                "period": r["period"],
                "canonical_period": r["canonical_period"],
                "scope": r["scope"],
                "value": r["canonical_value"],
                "unit": r["unit"],
                "currency": r["currency"],
                "selected_source_type": r["selected_source_type"],
                "selected_source_name": r["selected_source_name"],
                "selected_source_url": r["selected_source_url"],
                "screener_value": r["screener_value"],
                "official_value": r["official_value"],
                "verification_status": r["verification_status"],
                "difference_absolute": r["difference_absolute"],
                "difference_pct": r["difference_pct"],
                "confidence": r["confidence"],
                "provenance_note": r["provenance_note"],
                "verified_at": r["verified_at"],
                "computed_at": r["computed_at"]
            })
        return series
    finally:
        conn.close()

# Auto-initialize on module load unless test mode is active
if not (os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("STOCKER_TEST_MODE") or os.environ.get("STOCKER_DB_PATH")):
    try:
        init_db()
    except Exception:
        pass


