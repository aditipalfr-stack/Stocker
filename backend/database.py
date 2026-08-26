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

DB_PATH = Path(__file__).parent / "data" / "stocker.db"

def get_db_connection() -> sqlite3.Connection:
    """Returns a connection to the SQLite database with row factory enabled."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=15.0)
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
    finally:
        conn.close()

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

# Auto-initialize on module load
init_db()

