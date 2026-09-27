import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from financial_metric_registry import normalize_analysis_metric
from models import FinancialRow, FinancialStatement
from financial_engine import get_row_values

def test_metric_registry_explicit_aliases():
    assert normalize_analysis_metric("Sales") == "REVENUE"
    assert normalize_analysis_metric("Revenue from Operations") == "REVENUE"
    assert normalize_analysis_metric("Net Profit") == "PAT"
    assert normalize_analysis_metric("Cash from Operating Activity") == "CFO"
    assert normalize_analysis_metric("Fixed assets purchased") == "CAPEX"

def test_metric_registry_rejects_ambiguous_labels():
    assert normalize_analysis_metric("Other Income") is None
    assert normalize_analysis_metric("Operating Profit / EBITDA") is None
    assert normalize_analysis_metric("Free Cash Flow") is None

def test_financial_engine_prefers_canonical_metadata():
    stmt = FinancialStatement(
        periods=["Mar 2026"],
        rows=[
            FinancialRow(metric="Sales", source_label="Sales", values={"Mar 2026": 100.0}, canonical_metric="REVENUE"),
            FinancialRow(metric="Revenue from Operations", source_label="Revenue from Operations", values={"Mar 2026": 110.0}, canonical_metric="REVENUE"),
        ],
    )
    assert get_row_values(stmt, "Revenue") == {"Mar 2026": 100.0}

def test_financial_row_defaults_preserve_backward_compatibility():
    row = FinancialRow(metric="Sales", values={"Mar 2026": 100.0})
    assert row.canonical_metric is None
    assert row.evidence_status == "reported_unverified"
