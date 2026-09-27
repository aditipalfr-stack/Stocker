"""
Read-only end-to-end lineage audit for four core metrics.

This test intentionally inspects the persisted SQLite database rather than
constructing a synthetic company fixture. It is designed to answer:

  Revenue -> reported fact / verification record
  PAT     -> reported fact / verification record
  CFO     -> reported-but-unverified fact (unless separately verified later)
  FCF     -> deterministic Stocker-derived metric from CFO + Capex

It does not mutate the database and does not require network access.
"""

import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent))

from financial_metric_registry import normalize_analysis_metric
from financial_engine import compute_financial_analytics
from models import FinancialStatement


PREFERRED_SYMBOLS = [
    "INFY", "TCS", "RELIANCE", "LT", "HINDUNILVR", "ITC",
    "TATASTEEL", "TATAMOTORS",
]


def _db_path() -> Path:
    configured = os.environ.get("STOCKER_DB_PATH")
    if configured:
        return Path(configured)
    return Path(__file__).parent / "data" / "stocker.db"


def _connect_read_only() -> sqlite3.Connection:
    path = _db_path().resolve()
    if not path.exists():
        raise AssertionError(
            f"Persisted Stocker database not found at {path}. "
            "Run the application/ingestion first, then rerun this audit."
        )
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _load_stock(conn: sqlite3.Connection, symbol: str) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        "SELECT symbol, name, data_json FROM stocks_cache WHERE symbol = ?",
        (symbol,),
    ).fetchone()
    if not row:
        return None
    return {
        "symbol": row["symbol"],
        "name": row["name"],
        "data": json.loads(row["data_json"]),
    }


def _candidate_symbols(conn: sqlite3.Connection) -> List[str]:
    available = {
        str(r["symbol"]).upper()
        for r in conn.execute("SELECT symbol FROM stocks_cache").fetchall()
    }
    ordered = [s for s in PREFERRED_SYMBOLS if s in available]
    ordered.extend(sorted(available - set(ordered)))
    return ordered


def _statement(data: Dict[str, Any], key: str) -> FinancialStatement:
    return FinancialStatement(**data[key])


def _find_row(stmt: FinancialStatement, canonical_metric: str):
    for row in stmt.rows:
        if row.canonical_metric == canonical_metric:
            return row
    for row in stmt.rows:
        if normalize_analysis_metric(row.metric) == canonical_metric:
            return row
    return None


def _find_verification_records(
    conn: sqlite3.Connection,
    symbol: str,
    canonical_metric: str,
) -> List[Dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT symbol, metric_name, canonical_metric, period, canonical_period,
               scope, screener_value, official_value, variance_abs, variance_pct,
               unit, currency, status, screener_source_url, official_source_url,
               official_source_name, official_document_id, verified_at
        FROM financial_verification_records
        WHERE symbol = ? AND canonical_metric = ?
        ORDER BY canonical_period DESC
        """,
        (symbol, canonical_metric),
    ).fetchall()
    return [dict(r) for r in rows]


def _trace_metric(stmt: FinancialStatement, canonical_metric: str) -> Dict[str, Any]:
    row = _find_row(stmt, canonical_metric)
    if row is None:
        return {
            "canonical_metric": canonical_metric,
            "status": "MISSING",
            "periods": [],
            "source_labels": [],
            "source_providers": [],
            "evidence_statuses": [],
        }

    return {
        "canonical_metric": canonical_metric,
        "status": "OK" if row.canonical_metric == canonical_metric else "LEGACY_METADATA_GAP",
        "periods": list(row.values.keys()),
        "source_labels": [row.source_label or row.metric],
        "source_providers": [row.source_provider],
        "evidence_statuses": [row.evidence_status],
        "unit": row.unit,
        "currency": row.currency,
        "values": row.values,
    }


def audit_four_metric_lineage() -> Dict[str, Any]:
    conn = _connect_read_only()
    try:
        symbol = next(
            (
                s for s in _candidate_symbols(conn)
                if _load_stock(conn, s)
                and "profit_loss" in _load_stock(conn, s)["data"]
                and "cash_flow" in _load_stock(conn, s)["data"]
            ),
            None,
        )
        if not symbol:
            raise AssertionError(
                "No persisted company has both Profit & Loss and Cash Flow data."
            )

        stock = _load_stock(conn, symbol)
        assert stock is not None
        data = stock["data"]

        pl = _statement(data, "profit_loss")
        cf = _statement(data, "cash_flow")
        bs = _statement(data, "balance_sheet")

        metric_traces = {
            "Revenue": _trace_metric(pl, "REVENUE"),
            "PAT": _trace_metric(pl, "PAT"),
            "CFO": _trace_metric(cf, "CFO"),
        }

        analytics = compute_financial_analytics(
            quarters=None, pl=pl, bs=bs, cf=cf
        )
        fcf_trends = analytics.get("cash_flow_quality", {}).get("fcf_trends", [])
        latest_fcf = fcf_trends[-1] if fcf_trends else {}

        metric_traces["FCF"] = {
            "canonical_metric": "DERIVED_FCF",
            "status": "OK" if latest_fcf else "MISSING",
            "period": latest_fcf.get("period"),
            "value": latest_fcf.get("stocker_derived_fcf_cr"),
            "formula": "FCF = CFO - Capex",
            "cfo_input": latest_fcf.get("reported_cfo_cr"),
            "capex_input": latest_fcf.get("capex_cr"),
            "capex_methodology": latest_fcf.get("capex_methodology"),
            "confidence": latest_fcf.get("fcf_confidence"),
        }

        verification = {
            metric: _find_verification_records(conn, symbol, canonical)
            for metric, canonical in (
                ("Revenue", "REVENUE"),
                ("PAT", "PAT"),
                ("CFO", "CFO"),
                ("FCF", "FCF"),
            )
        }

        assert not verification["FCF"], (
            "FCF has a financial_verification_records entry. "
            "FCF is a Stocker-derived metric and must not be represented as an "
            "official reported fact."
        )

        if latest_fcf.get("stocker_derived_fcf_cr") is not None:
            assert latest_fcf.get("reported_cfo_cr") is not None
            assert latest_fcf.get("capex_cr") is not None

        report = {
            "symbol": symbol,
            "company_name": stock["name"],
            "statement_type": data.get("statement_type", "unknown"),
            "fetched_at": data.get("fetched_at"),
            "metrics": metric_traces,
            "verification_records": verification,
            "assessment": {
                "revenue": metric_traces["Revenue"]["status"],
                "pat": metric_traces["PAT"]["status"],
                "cfo": metric_traces["CFO"]["status"],
                "fcf": metric_traces["FCF"]["status"],
                "revenue_verification_count": len(verification["Revenue"]),
                "pat_verification_count": len(verification["PAT"]),
                "cfo_verification_count": len(verification["CFO"]),
                "fcf_verification_count": len(verification["FCF"]),
            },
        }

        print(json.dumps(report, indent=2, default=str))
        return report
    finally:
        conn.close()


def test_four_metric_lineage_against_persisted_data():
    report = audit_four_metric_lineage()

    assert report["metrics"]["Revenue"]["status"] in {"OK", "LEGACY_METADATA_GAP"}
    assert report["metrics"]["PAT"]["status"] in {"OK", "LEGACY_METADATA_GAP"}
    assert report["metrics"]["CFO"]["status"] in {"OK", "LEGACY_METADATA_GAP"}
    assert report["metrics"]["FCF"]["status"] in {"OK", "MISSING"}
