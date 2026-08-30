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
                    generated_at TEXT NOT NULL
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_summaries_symbol ON ai_document_summaries(symbol);")

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
                    sector TEXT DEFAULT 'Broad Market',
                    industry TEXT DEFAULT 'Indian Equities',
                    aliases TEXT DEFAULT '[]',
                    is_active INTEGER DEFAULT 1,
                    in_universe INTEGER DEFAULT 1,
                    source TEXT DEFAULT 'seed',
                    source_last_verified_at TEXT,
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
    finally:
        conn.close()

    # Automatically seed initial registry if empty
    try:
        seed_company_registry()
    except Exception:
        pass

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

def get_document_summary(doc_url: str) -> Optional[Dict[str, Any]]:
    """Retrieves a single document's cached AI summary by doc_url."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT summary_json, generated_at FROM ai_document_summaries WHERE doc_url = ?", (doc_url,))
        row = cur.fetchone()
        if row:
            try:
                data = json.loads(row["summary_json"])
                if "analyzed_at" not in data or not data["analyzed_at"]:
                    data["analyzed_at"] = row["generated_at"]
                return data
            except Exception:
                pass
        return None
    finally:
        conn.close()

def get_document_summaries(symbol: str) -> Dict[str, Dict[str, Any]]:
    """Returns a dict mapping doc_url -> summary_json dict for a symbol."""
    clean_sym = symbol.upper().strip()
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT doc_url, summary_json, generated_at FROM ai_document_summaries WHERE symbol = ?", (clean_sym,))
        rows = cur.fetchall()
        res = {}
        for r in rows:
            try:
                data = json.loads(r["summary_json"])
                if "analyzed_at" not in data or not data["analyzed_at"]:
                    data["analyzed_at"] = r["generated_at"]
                res[r["doc_url"]] = data
            except Exception:
                pass
        return res
    finally:
        conn.close()

def save_document_summary(symbol: str, doc_url: str, doc_title: str, summary_data: Dict[str, Any]) -> None:
    """Saves per-document executive summary in SQLite."""
    clean_sym = symbol.upper().strip()
    now_iso = datetime.now(timezone.utc).isoformat()
    if "analyzed_at" not in summary_data or not summary_data["analyzed_at"]:
        summary_data["analyzed_at"] = now_iso
    conn = get_db_connection()
    try:
        with conn:
            conn.execute("""
                INSERT OR REPLACE INTO ai_document_summaries (doc_url, symbol, doc_title, summary_json, generated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (doc_url, clean_sym, doc_title, json.dumps(summary_data, default=_db_json_serializer), now_iso))
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

def save_source_documents(symbol: str, documents: List[Any]) -> None:
    """Persists discovered and verified source documents into SQLite."""
    if not documents:
        return
    clean_sym = symbol.upper().strip()
    now_iso = datetime.now(timezone.utc).isoformat()
    conn = get_db_connection()
    try:
        with conn:
            for doc in documents:
                title = getattr(doc, "title", None) or (doc.get("title") if isinstance(doc, dict) else "")
                url = getattr(doc, "url", None) or (doc.get("url") if isinstance(doc, dict) else "")
                doc_type = getattr(doc, "doc_type", None) or (doc.get("doc_type") if isinstance(doc, dict) else "general")
                period = getattr(doc, "period_or_date", None) or (doc.get("period_or_date") if isinstance(doc, dict) else None)
                discovery = getattr(doc, "discovery_source", None) or (doc.get("discovery_source") if isinstance(doc, dict) else "Unknown")
                host = getattr(doc, "actual_source_host", None) or (doc.get("actual_source_host") if isinstance(doc, dict) else "")
                status = getattr(doc, "validation_status", "Valid") or (doc.get("validation_status", "Valid") if isinstance(doc, dict) else "Valid")
                is_valid = 1 if status == "Valid" else 0
                
                if not url:
                    continue
                    
                conn.execute("""
                    INSERT INTO source_documents (
                        symbol, title, url, doc_type, period_or_date, discovery_source, actual_source_host, is_valid, added_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(url) DO UPDATE SET
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
    """Retrieves verified source documents from SQLite."""
    clean_sym = symbol.upper().strip()
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        if doc_type:
            cur.execute("""
                SELECT symbol, title, url, doc_type, period_or_date, discovery_source, actual_source_host, is_valid, added_at
                FROM source_documents
                WHERE symbol = ? AND doc_type = ? AND is_valid = 1
                ORDER BY id DESC
            """, (clean_sym, doc_type))
        else:
            cur.execute("""
                SELECT symbol, title, url, doc_type, period_or_date, discovery_source, actual_source_host, is_valid, added_at
                FROM source_documents
                WHERE symbol = ? AND is_valid = 1
                ORDER BY id DESC
            """, (clean_sym,))
        rows = cur.fetchall()
        return [dict(r) for r in rows]
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
) -> None:
    """Saves full institutional AI analysis into SQLite."""
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
    source_last_verified_at = item.get("source_last_verified_at") or now_iso
    
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
                row_id = existing["id"]
                merged_aliases_json = _merge_aliases(existing["aliases"], incoming_aliases)
                
                # Determine updated field values
                up_name = company_name if company_name and company_name != clean_sym else (existing["company_name"] or company_name)
                up_nse = nse_symbol or existing["nse_symbol"]
                up_bse = bse_code or existing["bse_code"]
                up_isin = isin or existing["isin"]
                up_exchange = exchange or existing["exchange"]
                up_sector = sector if sector and sector != "Broad Market" else (existing["sector"] or sector or "Broad Market")
                up_industry = industry if industry and industry != "Indian Equities" else (existing["industry"] or industry or "Indian Equities")
                
                up_in_uni = (1 if in_universe_val else 0) if in_universe_val is not None else existing["in_universe"]
                up_is_act = (1 if is_active_val else 0) if is_active_val is not None else existing["is_active"]
                up_source = existing["source"] if existing["source"] == "seed" else source
                
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
                        updated_at = ?
                    WHERE id = ?
                """, (
                    up_name, up_nse, up_bse, up_isin, up_exchange,
                    up_sector, up_industry, merged_aliases_json,
                    up_in_uni, up_is_act, up_source, source_last_verified_at, now_iso,
                    row_id
                ))
                return row_id
            else:
                aliases_json = _merge_aliases(None, incoming_aliases)
                in_uni = 1 if in_universe_val is not False else 0
                is_act = 1 if is_active_val is not False else 0
                sec_val = sector or "Broad Market"
                ind_val = industry or "Indian Equities"
                
                cur = conn.execute("""
                    INSERT INTO company_registry (
                        symbol, company_name, nse_symbol, bse_code, isin,
                        exchange, sector, industry, aliases, is_active,
                        in_universe, source, source_last_verified_at, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    clean_sym, company_name, nse_symbol, bse_code, isin,
                    exchange, sec_val, ind_val, aliases_json, is_act,
                    in_uni, source, source_last_verified_at, now_iso, now_iso
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
    """
    clean_q = query.strip()
    if not clean_q:
        return []
        
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        pattern = f"%{clean_q}%"
        cur.execute("""
            SELECT * FROM company_registry
            WHERE symbol LIKE ? OR company_name LIKE ? OR nse_symbol LIKE ? OR aliases LIKE ? OR bse_code LIKE ?
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
        """, (
            pattern, pattern, pattern, pattern, pattern,
            clean_q, clean_q, clean_q,
            f"{clean_q}%", f"{clean_q}%",
            limit
        ))
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
                            "nse_symbol": clean_s,
                            "bse_code": None,
                            "isin": None,
                            "exchange": "NSE",
                            "sector": stock_dict.get("sector") or meta.get("sector") or "Broad Market",
                            "industry": stock_dict.get("industry") or meta.get("industry") or "Indian Equities",
                            "aliases": [clean_s, stock_dict.get("name") or clean_s],
                            "in_universe": True,
                            "is_active": True,
                            "source": "stocks_cache"
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
                nse = (rec.get("nse_symbol") or sym).upper().strip()
                bse = str(rec.get("bse_code") or "").strip() or None
                isin = (rec.get("isin") or "").upper().strip() or None
                exchange = rec.get("exchange", "NSE")
                sector = rec.get("sector", "Broad Market")
                industry = rec.get("industry", "Indian Equities")
                aliases = rec.get("aliases", [])
                source = rec.get("source", "seed")
                
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
                            sector = CASE WHEN ? != 'Broad Market' THEN ? ELSE sector END,
                            industry = CASE WHEN ? != 'Indian Equities' THEN ? ELSE industry END,
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
                            in_universe, source, source_last_verified_at, created_at, updated_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        sym, name, nse, bse, isin,
                        exchange, sector, industry, aliases_json, is_act,
                        in_uni, source, now_iso, now_iso, now_iso
                    ))
                    inserted_count += 1
        return inserted_count
    finally:
        conn.close()

# Auto-initialize on module load unless test mode is active
if not (os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("STOCKER_TEST_MODE") or os.environ.get("STOCKER_DB_PATH")):
    try:
        init_db()
    except Exception:
        pass


