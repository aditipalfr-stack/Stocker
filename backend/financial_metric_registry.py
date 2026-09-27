"""Controlled analytical metric taxonomy for reported financial rows.

This taxonomy describes what a row represents. It does not establish authority.
Official verification remains responsible for deciding whether a fact is verified.
"""
import re
from typing import Optional

_ALIASES = {
    "revenue": "REVENUE", "sales": "REVENUE",
    "revenue from operations": "REVENUE", "net sales": "REVENUE",
    "total income from operations": "REVENUE", "income from operations": "REVENUE",
    "operating profit": "OPERATING_PROFIT", "ebitda": "OPERATING_PROFIT",
    "opm": "OPM", "opm %": "OPM",
    "net profit": "PAT", "profit after tax": "PAT", "pat": "PAT",
    "profit for the period": "PAT", "net profit for the period": "PAT",
    "profit before tax": "PBT", "pbt": "PBT",
    "depreciation": "DEPRECIATION", "interest": "INTEREST",
    "tax": "TAX", "tax %": "TAX",
    "cash from operating activity": "CFO", "cash from operations": "CFO",
    "net cash flow from operating activities": "CFO",
    "cash flow from operating activities": "CFO",
    "fixed assets purchased": "CAPEX", "purchase of fixed assets": "CAPEX",
    "purchase of property, plant and equipment": "CAPEX",
    "capital expenditure": "CAPEX", "capex": "CAPEX",
    "fixed assets": "FIXED_ASSETS", "cwip": "CWIP",
    "capital work in progress": "CWIP", "borrowings": "BORROWINGS",
    "equity capital": "EQUITY_CAPITAL", "reserves": "RESERVES",
    "total assets": "TOTAL_ASSETS", "other assets": "OTHER_ASSETS",
}

def _clean(value: str) -> str:
    value = str(value or "").replace("\xa0", " ").strip().lower()
    value = re.sub(r"[\(\)\[\],.:]", " ", value)
    return re.sub(r"\s+", " ", value).strip()

def normalize_analysis_metric(raw_metric: str) -> Optional[str]:
    """Map only explicit known aliases; unknown/ambiguous labels return None."""
    return _ALIASES.get(_clean(raw_metric))
