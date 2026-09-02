#!/usr/bin/env python3
"""Reset regenerable AI/runtime state for exactly one Stocker symbol.

The utility deliberately uses a small deletion allowlist. Research-source,
identity, financial, verification, taxonomy, sync, projection, and other
deterministic state is audited and preserved.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Mapping, Sequence, Tuple


DEFAULT_DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DEFAULT_DB_PATH = DEFAULT_DATA_DIR / "stocker.db"

AI_RUNTIME_TABLES: Tuple[str, ...] = (
    "ai_document_summaries",
    "ai_analysis_cache",
    "company_knowledge_facts",
    "document_evidence_items",
    "management_guidance_items",
)
DOCUMENT_PAGE_TABLE = "document_pages_cache"

PROTECTED_SYMBOL_TABLES: Tuple[str, ...] = (
    "source_documents",
    "stocks_cache",
    "company_registry",
    "company_taxonomy",
    "document_sync_state",
    "financial_verification_records",
    "canonical_financial_facts",
    "canonical_financial_truth_state",
    "projection_computation_state",
)
PROTECTED_GLOBAL_TABLES: Tuple[str, ...] = (
    "taxonomy_sectors",
    "taxonomy_industries",
    "taxonomy_sub_industries",
)
SAFETY_CRITICAL_RESOURCES = frozenset(
    {
        "source_documents",
        "stocks_cache",
        "standardized_statement_collections",
        "company_registry",
        "financial_verification_records",
        "canonical_financial_facts",
        "canonical_financial_truth_state",
    }
)
STANDARDIZED_STATEMENT_KEYS: Tuple[str, ...] = (
    "profit_loss",
    "balance_sheet",
    "cash_flow",
    "quarters",
)
SYMBOL_PATTERN = re.compile(r"[A-Z0-9][A-Z0-9.-]{0,31}\Z")


class ResetSafetyError(RuntimeError):
    """Raised before mutation when a reset request is not provably symbol-safe."""


@dataclass(frozen=True)
class ResourceChange:
    resource: str
    to_delete: int
    preserved: int
    protected: bool = False


@dataclass(frozen=True)
class ResetPlan:
    symbol: str
    db_path: Path
    cache_dir: Path
    generated_dir: Path
    purge_document_pages: bool
    source_urls: Tuple[str, ...]
    resources: Tuple[ResourceChange, ...]
    page_cache_files: Tuple[Path, ...]
    generated_files: Tuple[Path, ...]
    protected_symbol_counts: Mapping[str, int]


@dataclass(frozen=True)
class ResetResult:
    symbol: str
    deleted: Mapping[str, int]
    preserved_symbol_counts: Mapping[str, int]


def normalize_symbol(raw_symbol: str) -> str:
    raw = "" if raw_symbol is None else str(raw_symbol)
    clean = raw.strip().upper()
    if not clean:
        raise ResetSafetyError("A single non-empty symbol is required.")
    if clean == "ALL":
        raise ResetSafetyError("ALL is forbidden; this tool resets exactly one symbol.")
    if not SYMBOL_PATTERN.fullmatch(clean):
        raise ResetSafetyError(
            "Invalid symbol. Wildcards, underscores, whitespace, and multi-symbol expressions are forbidden."
        )
    return clean


def _connect_read_only(db_path: Path) -> sqlite3.Connection:
    if not db_path.is_file():
        raise ResetSafetyError(f"Database does not exist: {db_path}")
    uri = db_path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=15.0)
    conn.row_factory = sqlite3.Row
    return conn


def _table_names(conn: sqlite3.Connection) -> set[str]:
    return {
        str(row[0])
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    }


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _symbol_count(conn: sqlite3.Connection, table: str, symbol: str) -> int:
    row = conn.execute(
        f"SELECT COUNT(*) FROM {table} WHERE symbol = ? COLLATE NOCASE", (symbol,)
    ).fetchone()
    return int(row[0])


def _total_count(conn: sqlite3.Connection, table: str) -> int:
    return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def _standardized_statement_count(conn: sqlite3.Connection, symbol: str) -> int:
    rows = conn.execute(
        "SELECT data_json FROM stocks_cache WHERE symbol = ? COLLATE NOCASE", (symbol,)
    ).fetchall()
    count = 0
    for row in rows:
        try:
            payload = json.loads(row[0])
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            count += sum(1 for key in STANDARDIZED_STATEMENT_KEYS if payload.get(key) is not None)
    return count


def _safe_direct_child(path: Path, parent: Path) -> Path:
    resolved_parent = parent.resolve()
    resolved_path = path.resolve(strict=False)
    if resolved_path.parent != resolved_parent:
        raise ResetSafetyError(f"Refusing non-local cache path: {path}")
    return path


def _existing_url_cache_files(cache_dir: Path, source_urls: Iterable[str]) -> Tuple[Path, ...]:
    files = []
    for url in sorted(set(source_urls)):
        cache_key = hashlib.md5(url.encode("utf-8")).hexdigest()
        candidate = _safe_direct_child(cache_dir / f"{cache_key}.json", cache_dir)
        if candidate.is_file():
            files.append(candidate)
    return tuple(files)


def _count_regular_files(directory: Path) -> int:
    if not directory.is_dir():
        return 0
    return sum(1 for path in directory.iterdir() if path.is_file())


def build_reset_plan(
    raw_symbol: str,
    *,
    purge_document_pages: bool = False,
    db_path: Path | str | None = None,
    cache_dir: Path | str | None = None,
    generated_dir: Path | str | None = None,
) -> ResetPlan:
    symbol = normalize_symbol(raw_symbol)
    resolved_db = Path(db_path or os.environ.get("STOCKER_DB_PATH") or DEFAULT_DB_PATH)
    resolved_cache = Path(
        cache_dir or os.environ.get("STOCKER_PDF_CACHE_DIR") or resolved_db.parent / "pdf_cache"
    )
    resolved_generated = Path(
        generated_dir
        or os.environ.get("STOCKER_DOC_INTEL_GENERATED_DIR")
        or resolved_db.parent / "doc_intelligence_generated"
    )

    conn = _connect_read_only(resolved_db)
    try:
        tables = _table_names(conn)
        required = set(AI_RUNTIME_TABLES) | {DOCUMENT_PAGE_TABLE} | set(PROTECTED_SYMBOL_TABLES) | set(PROTECTED_GLOBAL_TABLES)
        missing = sorted(required - tables)
        if missing:
            raise ResetSafetyError(f"Schema audit failed; required tables are missing: {', '.join(missing)}")

        for table in set(AI_RUNTIME_TABLES) | {DOCUMENT_PAGE_TABLE} | set(PROTECTED_SYMBOL_TABLES):
            if "symbol" not in _table_columns(conn, table):
                raise ResetSafetyError(f"Schema audit failed; {table} is not symbol-scoped.")

        source_urls = tuple(
            sorted(
                {
                    str(row[0]).strip()
                    for row in conn.execute(
                        "SELECT url FROM source_documents WHERE symbol = ? COLLATE NOCASE", (symbol,)
                    ).fetchall()
                    if row[0] and str(row[0]).strip()
                }
            )
        )

        resources = []
        for table in AI_RUNTIME_TABLES:
            target_count = _symbol_count(conn, table, symbol)
            resources.append(
                ResourceChange(table, target_count, _total_count(conn, table) - target_count)
            )

        page_rows = _symbol_count(conn, DOCUMENT_PAGE_TABLE, symbol) if purge_document_pages else 0
        resources.append(
            ResourceChange(
                DOCUMENT_PAGE_TABLE,
                page_rows,
                _total_count(conn, DOCUMENT_PAGE_TABLE) - page_rows,
            )
        )

        protected_counts: Dict[str, int] = {}
        for table in PROTECTED_SYMBOL_TABLES:
            count = _symbol_count(conn, table, symbol)
            protected_counts[table] = count
            resources.append(ResourceChange(table, 0, _total_count(conn, table), protected=True))

        standardized_count = _standardized_statement_count(conn, symbol)
        protected_counts["standardized_statement_collections"] = standardized_count
        resources.append(
            ResourceChange(
                "standardized_statement_collections",
                0,
                standardized_count,
                protected=True,
            )
        )
        for table in PROTECTED_GLOBAL_TABLES:
            resources.append(ResourceChange(table, 0, _total_count(conn, table), protected=True))
    finally:
        conn.close()

    page_files = _existing_url_cache_files(resolved_cache, source_urls) if purge_document_pages else ()
    generated_candidate = _safe_direct_child(resolved_generated / f"{symbol}.json", resolved_generated)
    generated_files = (generated_candidate,) if generated_candidate.is_file() else ()
    resources.append(
        ResourceChange(
            "document_page_cache_files",
            len(page_files),
            _count_regular_files(resolved_cache) - len(page_files),
        )
    )
    resources.append(
        ResourceChange(
            "generated_document_intelligence_json",
            len(generated_files),
            _count_regular_files(resolved_generated) - len(generated_files),
        )
    )

    plan = ResetPlan(
        symbol=symbol,
        db_path=resolved_db,
        cache_dir=resolved_cache,
        generated_dir=resolved_generated,
        purge_document_pages=purge_document_pages,
        source_urls=source_urls,
        resources=tuple(resources),
        page_cache_files=page_files,
        generated_files=generated_files,
        protected_symbol_counts=protected_counts,
    )
    assert_plan_safe(plan)
    return plan


def assert_plan_safe(plan: ResetPlan) -> None:
    normalize_symbol(plan.symbol)
    changes = {item.resource: item for item in plan.resources}
    for resource in SAFETY_CRITICAL_RESOURCES:
        change = changes.get(resource)
        if change is None:
            raise ResetSafetyError(f"Safety audit is missing protected resource: {resource}")
        if change.to_delete != 0:
            raise ResetSafetyError(
                f"Refusing reset: protected resource {resource} would delete {change.to_delete} row(s)."
            )
    allowed = set(AI_RUNTIME_TABLES) | {
        DOCUMENT_PAGE_TABLE,
        "document_page_cache_files",
        "generated_document_intelligence_json",
    }
    for change in plan.resources:
        if change.to_delete and change.resource not in allowed:
            raise ResetSafetyError(f"Refusing deletion from non-allowlisted resource: {change.resource}")
    if not plan.purge_document_pages:
        for name in (DOCUMENT_PAGE_TABLE, "document_page_cache_files"):
            if changes[name].to_delete:
                raise ResetSafetyError("Document-page deletion requires --purge-document-pages.")


def apply_reset(plan: ResetPlan) -> ResetResult:
    assert_plan_safe(plan)
    conn = sqlite3.connect(str(plan.db_path), timeout=15.0)
    conn.row_factory = sqlite3.Row
    deleted: Dict[str, int] = {}
    try:
        conn.execute("BEGIN IMMEDIATE")
        before = {
            table: _symbol_count(conn, table, plan.symbol) for table in PROTECTED_SYMBOL_TABLES
        }
        before["standardized_statement_collections"] = _standardized_statement_count(
            conn, plan.symbol
        )

        for table in AI_RUNTIME_TABLES:
            cursor = conn.execute(
                f"DELETE FROM {table} WHERE symbol = ? COLLATE NOCASE", (plan.symbol,)
            )
            deleted[table] = max(cursor.rowcount, 0)
        if plan.purge_document_pages:
            cursor = conn.execute(
                f"DELETE FROM {DOCUMENT_PAGE_TABLE} WHERE symbol = ? COLLATE NOCASE",
                (plan.symbol,),
            )
            deleted[DOCUMENT_PAGE_TABLE] = max(cursor.rowcount, 0)
        else:
            deleted[DOCUMENT_PAGE_TABLE] = 0

        after = {
            table: _symbol_count(conn, table, plan.symbol) for table in PROTECTED_SYMBOL_TABLES
        }
        after["standardized_statement_collections"] = _standardized_statement_count(
            conn, plan.symbol
        )
        if before != after:
            raise ResetSafetyError("Protected resource counts changed; rolling back reset.")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    deleted_page_files = 0
    for path in plan.page_cache_files:
        _safe_direct_child(path, plan.cache_dir).unlink(missing_ok=True)
        deleted_page_files += 1
    deleted_generated_files = 0
    for path in plan.generated_files:
        _safe_direct_child(path, plan.generated_dir).unlink(missing_ok=True)
        deleted_generated_files += 1
    deleted["document_page_cache_files"] = deleted_page_files
    deleted["generated_document_intelligence_json"] = deleted_generated_files

    return ResetResult(plan.symbol, deleted, before)


def _print_table(resources: Sequence[ResourceChange], *, actual: Mapping[str, int] | None = None) -> None:
    rows = []
    for item in resources:
        delete_count = actual.get(item.resource, item.to_delete) if actual is not None else item.to_delete
        rows.append((item.resource, str(delete_count), str(item.preserved)))
    widths = [
        max(len(header), *(len(row[index]) for row in rows))
        for index, header in enumerate(("RESOURCE", "ROWS/FILES TO DELETE", "ROWS/FILES PRESERVED"))
    ]
    headers = ("RESOURCE", "ROWS/FILES TO DELETE", "ROWS/FILES PRESERVED")
    print("  ".join(headers[index].ljust(widths[index]) for index in range(3)))
    print("  ".join("-" * widths[index] for index in range(3)))
    for row in rows:
        print("  ".join(row[index].ljust(widths[index]) for index in range(3)))


def print_plan(plan: ResetPlan, *, dry_run: bool) -> None:
    mode = "DRY RUN" if dry_run else "RESET PLAN"
    print(f"{mode}: {plan.symbol}")
    print(f"Database: {plan.db_path}")
    _print_table(plan.resources)
    print("\nRequested-symbol preservation counts:")
    for resource in (
        "source_documents",
        "stocks_cache",
        "standardized_statement_collections",
        "company_registry",
        "financial_verification_records",
        "canonical_financial_facts",
        "canonical_financial_truth_state",
    ):
        print(f"  {resource}: {plan.protected_symbol_counts[resource]}")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reset regenerable Stocker AI/runtime state for exactly one symbol."
    )
    parser.add_argument("symbol")
    parser.add_argument("--purge-document-pages", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--db-path", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--cache-dir", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--generated-dir", type=Path, help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        plan = build_reset_plan(
            args.symbol,
            purge_document_pages=args.purge_document_pages,
            db_path=args.db_path,
            cache_dir=args.cache_dir,
            generated_dir=args.generated_dir,
        )
        print_plan(plan, dry_run=args.dry_run)
        if args.dry_run:
            print("\nSafety gate: PASS. No data or files changed.")
            return 0
        result = apply_reset(plan)
        print("\nActual deletions:")
        _print_table(plan.resources, actual=result.deleted)
        print("\nSafety gate: PASS. Protected requested-symbol counts are unchanged.")
        return 0
    except (ResetSafetyError, sqlite3.Error, OSError) as exc:
        print(f"RESET REFUSED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
