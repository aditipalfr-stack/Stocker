"""Phase 3A deterministic taxonomy tests (isolated SQLite, no network/AI)."""

import os
import shutil
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ["STOCKER_TEST_MODE"] = "1"
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "libs"))

import database
from company_taxonomy_service import (
    classify_and_persist_company,
    get_company_taxonomy,
    normalize_taxonomy_key,
    resolve_local_company_taxonomy,
)
from financial_engine import classify_financial_business_model
from models import FinancialRow, FinancialStatement


class IsolatedTaxonomyDatabase:
    def __enter__(self):
        self.temp_dir = tempfile.mkdtemp(prefix="stocker_taxonomy_test_")
        self.db_path = Path(self.temp_dir) / "taxonomy.db"
        self.old_env = os.environ.get("STOCKER_DB_PATH")
        self.old_path = database.DB_PATH
        os.environ["STOCKER_DB_PATH"] = str(self.db_path)
        database.DB_PATH = self.db_path
        database.init_db()
        return self

    def __exit__(self, *_args):
        database.DB_PATH = self.old_path
        if self.old_env is None:
            os.environ.pop("STOCKER_DB_PATH", None)
        else:
            os.environ["STOCKER_DB_PATH"] = self.old_env
        shutil.rmtree(self.temp_dir, ignore_errors=True)


def _insert_company(symbol: str, sector=None, industry=None, source="manual"):
    database.upsert_company_registry_item({
        "symbol": symbol,
        "company_name": f"{symbol} Limited",
        "sector": sector,
        "industry": industry,
        "source": source,
        "in_universe": True,
        "is_active": True,
    })


def _count(table: str, where: str = "", params=()):
    conn = database.get_db_connection()
    try:
        return conn.execute(f"SELECT COUNT(*) AS count FROM {table} {where}", params).fetchone()["count"]
    finally:
        conn.close()


def test_a_new_unmapped_stock_fails_closed_without_fake_market_labels():
    with IsolatedTaxonomyDatabase():
        _insert_company("NEWCO")
        result = classify_and_persist_company("NEWCO", source="unknown")
        assert result["sector"] == "Unclassified"
        assert result["industry"] == "Unclassified"
        assert result["classification_state"] == "UNCLASSIFIED"
        assert result["sector"] != "Broad Market"
        assert result["industry"] != "Indian Equities"


def test_a2_explicit_screener_market_breadcrumb_is_classified_without_legacy_metadata():
    from bs4 import BeautifulSoup
    from scraper import parse_screener_taxonomy_metadata
    soup = BeautifulSoup("""
      <section id="peers">
        <a href="/market/IN08/">Information Technology</a>
        <a href="/market/IN08/IN0801/">Information Technology</a>
        <a href="/market/IN08/IN0801/IN080101/">IT - Software</a>
        <a href="/market/IN08/IN0801/IN080101/IN080101001/">Computers - Software &amp; Consulting</a>
        <a href="/company/NIFTY/">Nifty 50</a>
      </section>
    """, "html.parser")
    assert parse_screener_taxonomy_metadata(soup) == (
        "Information Technology", "IT - Software", "Computers - Software & Consulting"
    )


def test_b_synonyms_share_one_canonical_taxonomy_record():
    with IsolatedTaxonomyDatabase():
        _insert_company("FMCGONE")
        _insert_company("FMCGTWO")
        first = classify_and_persist_company("FMCGONE", "FMCG", "Fast Moving Consumer Goods", source="screener_metadata")
        second = classify_and_persist_company("FMCGTWO", "Consumer Goods - FMCG", "Consumer Goods - FMCG", source="screener_metadata")
        assert first["sector"] == second["sector"] == "Consumer Staples"
        assert first["industry"] == second["industry"] == "Fast Moving Consumer Goods"
        assert _count("taxonomy_sectors", "WHERE normalized_key = ?", (normalize_taxonomy_key("Consumer Staples"),)) == 1
        conn = database.get_db_connection()
        try:
            rows = conn.execute(
                "SELECT COUNT(*) AS count FROM taxonomy_industries WHERE normalized_key = ?",
                (normalize_taxonomy_key("Fast Moving Consumer Goods"),),
            ).fetchone()["count"]
            assert rows == 1
        finally:
            conn.close()


def test_c_genuinely_new_industry_is_created_once():
    with IsolatedTaxonomyDatabase():
        _insert_company("NEWIND1")
        _insert_company("NEWIND2")
        classify_and_persist_company("NEWIND1", "Specialty Services", "Orbital Logistics", source="screener_metadata")
        classify_and_persist_company("NEWIND2", "specialty-services", "ORBITAL LOGISTICS", source="screener_metadata")
        assert _count("taxonomy_industries", "WHERE normalized_key = ?", ("orbital logistics",)) == 1


def test_d_seeded_company_is_preserved_and_normalized():
    with IsolatedTaxonomyDatabase():
        tcs = get_company_taxonomy("TCS")
        hdfc = get_company_taxonomy("HDFCBANK")
        assert tcs and tcs["sector"] == "Information Technology"
        assert tcs["industry"] == "IT Services"
        assert hdfc and hdfc["sector"] == "Financial Services"
        assert hdfc["industry"] == "Private Sector Banks"


def test_e_stronger_evidence_reclassifies_one_company_mapping():
    with IsolatedTaxonomyDatabase():
        _insert_company("RECLASS")
        classify_and_persist_company("RECLASS", "Consumer Goods", "FMCG", source="seed_reference")
        updated = classify_and_persist_company(
            "RECLASS", "Health Care", "Diagnostic Services", source="official_exchange",
            classification_method="exchange_master",
        )
        assert updated["sector"] == "Health Care"
        assert updated["industry"] == "Diagnostic Services"
        assert updated["source"] == "official_exchange"
        assert _count("company_taxonomy", "WHERE symbol = ?", ("RECLASS",)) == 1
        weaker = classify_and_persist_company("RECLASS", "FMCG", "FMCG", source="seed_reference")
        assert weaker["sector"] == "Health Care"


def test_equal_priority_complete_is_not_replaced_by_partial():
    with IsolatedTaxonomyDatabase():
        _insert_company("RICHSTATE")
        original = classify_and_persist_company(
            "RICHSTATE", "Information Technology", "IT - Software",
            sub_industry="Cloud Platforms", source="screener_metadata",
        )
        refreshed = classify_and_persist_company(
            "RICHSTATE", "Information Technology", None, source="screener_metadata",
        )
        assert refreshed == original
        assert refreshed["classification_state"] == "COMPLETE"


def test_equal_priority_refresh_does_not_erase_sub_industry():
    with IsolatedTaxonomyDatabase():
        _insert_company("RICHSUB")
        original = classify_and_persist_company(
            "RICHSUB", "Information Technology", "IT - Software",
            sub_industry="Computers - Software & Consulting", source="screener_metadata",
        )
        refreshed = classify_and_persist_company(
            "RICHSUB", "Information Technology", "IT - Software",
            sub_industry=None, source="screener_metadata",
        )
        assert refreshed == original
        assert refreshed["sub_industry"] == "Computers - Software and Consulting"


def test_equal_priority_partial_upgrades_to_complete():
    with IsolatedTaxonomyDatabase():
        _insert_company("PARTIALUP")
        partial = classify_and_persist_company(
            "PARTIALUP", "Information Technology", None, source="screener_metadata",
        )
        assert partial["classification_state"] == "PARTIAL"
        complete = classify_and_persist_company(
            "PARTIALUP", "Information Technology", "IT - Software", source="screener_metadata",
        )
        assert complete["classification_state"] == "COMPLETE"
        assert complete["industry"] == "Software & Services"


def test_equal_priority_unclassified_upgrades_to_meaningful_classification():
    with IsolatedTaxonomyDatabase():
        _insert_company("UNKNOWNUP")
        unknown = classify_and_persist_company("UNKNOWNUP", source="screener_metadata")
        assert unknown["classification_state"] == "UNCLASSIFIED"
        complete = classify_and_persist_company(
            "UNKNOWNUP", "Consumer Goods", "FMCG", source="screener_metadata",
        )
        assert complete["classification_state"] == "COMPLETE"
        assert complete["sector"] == "Consumer Staples"


def test_stronger_source_can_reclassify_complete_taxonomy():
    with IsolatedTaxonomyDatabase():
        _insert_company("STRONGER")
        classify_and_persist_company(
            "STRONGER", "Information Technology", "IT - Software",
            sub_industry="Cloud Platforms", source="screener_metadata",
        )
        authoritative = classify_and_persist_company(
            "STRONGER", "Health Care", "Diagnostic Services",
            source="official_exchange", classification_method="exchange_master",
        )
        assert authoritative["sector"] == "Health Care"
        assert authoritative["industry"] == "Diagnostic Services"
        assert authoritative["sub_industry"] is None
        assert authoritative["source"] == "official_exchange"


def test_f_stock_summary_pipeline_uses_canonical_sector():
    with IsolatedTaxonomyDatabase():
        _insert_company("SUMMARYCO", "Automobile", "Auto Ancillaries", "screener_metadata")
        taxonomy = classify_and_persist_company("SUMMARYCO", "Automobile", "Auto Ancillaries", source="screener_metadata")
        import main
        ratios = SimpleNamespace(
            current_price=100.0, market_cap_cr=1000.0, stock_pe=15.0, roce_pct=12.0,
            roe_pct=10.0, fcf_yield_pct=3.0, sales_growth_3yr_cagr=8.0, debt_to_equity=0.2,
        )
        detail = SimpleNamespace(
            symbol="SUMMARYCO", name="Summary Co", sector=taxonomy["sector"], industry=taxonomy["industry"],
            sub_industry=None, taxonomy=taxonomy, ratios=ratios,
            analytics={"growth_rates": {}, "cash_flow_quality": {}},
            score=SimpleNamespace(total_composite_score=60.0, verdict="Watchlist", data_confidence="Moderate", investment_thesis="Test"),
            source_name="Screener.in", source_url="", statement_type="consolidated",
            financial_business_model="GENERAL_CORPORATE", fetched_at="",
        )
        with patch.object(main.database, "get_universe_symbols", return_value=["SUMMARYCO"]), \
             patch.object(main, "fetch_stock_from_screener", return_value={"symbol": "SUMMARYCO"}), \
             patch.object(main, "build_full_stock_detail", return_value=detail):
            result = main.get_all_stocks()
        assert result[0].sector == "Consumer Discretionary"
        assert result[0].industry == "Auto Components"
        assert result[0].taxonomy.sector == "Consumer Discretionary"


def test_g_business_model_classifier_consumes_canonical_taxonomy():
    assert classify_financial_business_model("Financial Services", "Private Sector Banks") == "BANK"
    assert classify_financial_business_model("Consumer Staples", "Fast Moving Consumer Goods") == "GENERAL_CORPORATE"


def test_h_local_reuse_and_statement_classification_make_no_network_or_ai_calls():
    bank_bs = FinancialStatement(periods=["Mar 2026"], rows=[
        FinancialRow(metric="Deposits", values={"Mar 2026": 1000.0}),
        FinancialRow(metric="Advances", values={"Mar 2026": 800.0}),
        FinancialRow(metric="Gross NPA %", values={"Mar 2026": 2.0}),
    ])
    with IsolatedTaxonomyDatabase():
        _insert_company("LOCALBANK")
        initial = classify_and_persist_company("LOCALBANK", source="seed_reference")
        assert initial["classification_state"] == "UNCLASSIFIED"
        with patch("requests.get", side_effect=AssertionError("network must not run")) as network:
            first = resolve_local_company_taxonomy("LOCALBANK", {"balance_sheet": bank_bs})
            second = resolve_local_company_taxonomy("LOCALBANK", {})
        assert first["sector"] == second["sector"] == "Financial Services"
        assert first["industry"] == "Banks"
        network.assert_not_called()
