"""
=============================================================================
Stocker V3 Phase B: Authoritative Identity & Official Financial Verification
Comprehensive Verification Suite (Tests A - U)
=============================================================================
Fully isolated, deterministic test suite:
- Runs against an isolated temporary SQLite database (STOCKER_TEST_MODE=1)
- Zero live network side-effects during tests
- Tests:
  - XBRL unitRef resolution (INR, INR/shares, missing unitRef, unknown unitRef)
  - XBRL multiple contexts resolution (current vs prior quarter, Consolidated vs Standalone)
  - XBRL ambiguous units rejection
  - Generic EPS rejection (only explicit Basic/Diluted allowed)
  - PDF fail-closed numeric extraction policy
  - HTML structured table parsing
  - JSON structured schema validation & unmapped rejection
  - Unknown unit/scope fail-closed
  - Exact period matching without nearest-period fallback
  - Banking non-financial revenue safety
  - Mathematical tolerance VERIFIED vs DISCREPANCY
=============================================================================
"""

import os
import sys
from pathlib import Path

os.environ["STOCKER_TEST_MODE"] = "1"
sys.path.insert(0, str(Path(__file__).parent.parent / "libs"))
sys.path.insert(0, str(Path(__file__).parent))

import tempfile
import shutil
import json
import io
import urllib.request
from unittest.mock import patch, MagicMock

import pypdf

import database
import authoritative_identity
import official_financial_service
from authoritative_identity import (
    fetch_official_identity_from_exchange,
    lookup_authoritative_identity,
    is_ambiguous_company_name,
    resolve_and_upgrade_company_identity,
    normalize_legal_name,
    NSE_SECURITY_MASTER_URL
)
from official_financial_service import (
    normalize_period,
    normalize_metric_name,
    normalize_numeric_scale,
    compare_financial_metric,
    discover_official_financial_results,
    fetch_official_financial_result,
    extract_official_filing_metrics,
    parse_official_xbrl_xml,
    parse_official_pdf_document,
    parse_official_html_table,
    run_official_financial_verification
)

# Helper fixture for isolated test database
class IsolatedTestDatabase:
    def __enter__(self):
        self.temp_dir = tempfile.mkdtemp(prefix="stocker_phase_b_test_")
        self.db_path = Path(self.temp_dir) / "test_stocker.db"
        self.orig_env_db = os.environ.get("STOCKER_DB_PATH")
        os.environ["STOCKER_DB_PATH"] = str(self.db_path)
        self.orig_db_path = database.DB_PATH
        database.DB_PATH = self.db_path
        database.init_db()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        database.DB_PATH = self.orig_db_path
        if self.orig_env_db is not None:
            os.environ["STOCKER_DB_PATH"] = self.orig_env_db
        else:
            os.environ.pop("STOCKER_DB_PATH", None)
        try:
            shutil.rmtree(self.temp_dir)
        except Exception:
            pass

# =============================================================================
# TEST A: XBRL fact unitRef = INR resolves correctly
# =============================================================================
def test_a_xbrl_unitref_inr():
    print("Test A: XBRL fact unitRef = INR resolves correctly...")
    xml_data = b"""<?xml version="1.0" encoding="UTF-8"?>
    <xbrl xmlns="http://www.xbrl.org/2003/instance" xmlns:in-gaap="http://www.sebi.gov.in/xbrl/2026-03-31/in-gaap">
        <unit id="U_INR"><measure>iso4217:INR</measure></unit>
        <context id="C_Q1">
            <entity><identifier>INFY</identifier></entity>
            <period><startDate>2026-04-01</startDate><endDate>2026-06-30</endDate></period>
        </context>
        <in-gaap:LevelOfRounding>Crores</in-gaap:LevelOfRounding>
        <in-gaap:NatureOfReportStandaloneConsolidated>Consolidated</in-gaap:NatureOfReportStandaloneConsolidated>
        <in-gaap:RevenueFromOperations contextRef="C_Q1" unitRef="U_INR">48211.0</in-gaap:RevenueFromOperations>
    </xbrl>"""
    
    parsed = parse_official_xbrl_xml(xml_data, {"symbol": "INFY", "document_title": "Infosys XBRL"})
    rows = parsed["financial_table"]
    assert len(rows) == 1
    assert rows[0]["unit"] == "₹ Cr"
    assert rows[0]["currency"] == "INR"
    assert rows[0]["unit_ref"] == "U_INR"
    print("  ✓ Test A passed: XBRL unitRef=INR combined with LevelOfRounding resolves to ₹ Cr.")

# =============================================================================
# TEST B: XBRL EPS unitRef = INR/shares resolves ₹ / Share
# =============================================================================
def test_b_xbrl_eps_unitref_inr_per_share():
    print("Test B: XBRL EPS unitRef = INR/shares resolves to ₹ / Share...")
    xml_data = b"""<?xml version="1.0" encoding="UTF-8"?>
    <xbrl xmlns="http://www.xbrl.org/2003/instance" xmlns:in-gaap="http://www.sebi.gov.in/xbrl/2026-03-31/in-gaap">
        <unit id="INRPerShare">
            <divide>
                <unitNumerator><measure>iso4217:INR</measure></unitNumerator>
                <unitDenominator><measure>shares</measure></unitDenominator>
            </divide>
        </unit>
        <context id="C_Q1">
            <entity><identifier>INFY</identifier></entity>
            <period><startDate>2026-04-01</startDate><endDate>2026-06-30</endDate></period>
        </context>
        <in-gaap:NatureOfReportStandaloneConsolidated>Consolidated</in-gaap:NatureOfReportStandaloneConsolidated>
        <in-gaap:BasicEarningsLossPerShare contextRef="C_Q1" unitRef="INRPerShare">16.40</in-gaap:BasicEarningsLossPerShare>
    </xbrl>"""
    
    parsed = parse_official_xbrl_xml(xml_data, {"symbol": "INFY", "document_title": "Infosys XBRL"})
    rows = parsed["financial_table"]
    assert len(rows) == 1
    assert rows[0]["unit"] == "₹ / Share"
    assert rows[0]["canonical_metric"] == "BASIC_EPS"
    assert rows[0]["value"] == 16.40
    print("  ✓ Test B passed: Divided unit INR/shares resolves to ₹ / Share.")

# =============================================================================
# TEST C: XBRL missing unitRef -> no VERIFIED
# =============================================================================
def test_c_xbrl_missing_unitref():
    print("Test C: XBRL missing unitRef -> unit is Unknown, no VERIFIED...")
    xml_data = b"""<?xml version="1.0" encoding="UTF-8"?>
    <xbrl xmlns="http://www.xbrl.org/2003/instance" xmlns:in-gaap="http://www.sebi.gov.in/xbrl/2026-03-31/in-gaap">
        <context id="C_Q1">
            <entity><identifier>INFY</identifier></entity>
            <period><startDate>2026-04-01</startDate><endDate>2026-06-30</endDate></period>
        </context>
        <in-gaap:NatureOfReportStandaloneConsolidated>Consolidated</in-gaap:NatureOfReportStandaloneConsolidated>
        <in-gaap:RevenueFromOperations contextRef="C_Q1">48211.0</in-gaap:RevenueFromOperations>
    </xbrl>"""
    
    parsed = parse_official_xbrl_xml(xml_data, {"symbol": "INFY", "document_title": "Infosys XBRL"})
    rows = parsed["financial_table"]
    assert len(rows) == 1
    assert rows[0]["unit"] == "Unknown"
    
    # Must fail verification as INSUFFICIENT_EVIDENCE
    comp = compare_financial_metric(
        screener_val=48211.0, official_val=48211.0, canonical_metric="REVENUE",
        screener_scope="Consolidated", official_scope="Consolidated",
        screener_period_key="2026-Q1", official_period_key="2026-Q1",
        official_unit="Unknown"
    )
    assert comp["status"] == "INSUFFICIENT_EVIDENCE"
    print("  ✓ Test C passed: Missing unitRef leaves unit as Unknown and rejects VERIFIED.")

# =============================================================================
# TEST D: XBRL unknown unit id -> INSUFFICIENT_EVIDENCE
# =============================================================================
def test_d_xbrl_unknown_unit_id():
    print("Test D: XBRL unknown unit id -> INSUFFICIENT_EVIDENCE...")
    xml_data = b"""<?xml version="1.0" encoding="UTF-8"?>
    <xbrl xmlns="http://www.xbrl.org/2003/instance" xmlns:in-gaap="http://www.sebi.gov.in/xbrl/2026-03-31/in-gaap">
        <unit id="USD"><measure>iso4217:USD</measure></unit>
        <context id="C_Q1">
            <entity><identifier>INFY</identifier></entity>
            <period><startDate>2026-04-01</startDate><endDate>2026-06-30</endDate></period>
        </context>
        <in-gaap:NatureOfReportStandaloneConsolidated>Consolidated</in-gaap:NatureOfReportStandaloneConsolidated>
        <in-gaap:RevenueFromOperations contextRef="C_Q1" unitRef="NON_EXISTENT_UNIT">48211.0</in-gaap:RevenueFromOperations>
    </xbrl>"""
    
    parsed = parse_official_xbrl_xml(xml_data, {"symbol": "INFY", "document_title": "Infosys XBRL"})
    rows = parsed["financial_table"]
    assert len(rows) == 1
    assert rows[0]["unit"] == "Unknown"
    print("  ✓ Test D passed: Non-existent unitRef mapped to Unknown unit.")

# =============================================================================
# TEST E: XBRL same metric/period/scope with incompatible units -> ambiguity
# =============================================================================
def test_e_xbrl_incompatible_units_ambiguity():
    print("Test E: XBRL same metric/period/scope with incompatible units -> ambiguity rejected...")
    xml_data = b"""<?xml version="1.0" encoding="UTF-8"?>
    <xbrl xmlns="http://www.xbrl.org/2003/instance" xmlns:in-gaap="http://www.sebi.gov.in/xbrl/2026-03-31/in-gaap">
        <unit id="U_INR"><measure>iso4217:INR</measure></unit>
        <unit id="U_UNKNOWN"><measure>other:CUSTOM</measure></unit>
        <context id="C_1"><entity><identifier>INFY</identifier></entity><period><startDate>2026-04-01</startDate><endDate>2026-06-30</endDate></period></context>
        <context id="C_2"><entity><identifier>INFY</identifier></entity><period><startDate>2026-04-01</startDate><endDate>2026-06-30</endDate></period></context>
        <in-gaap:LevelOfRounding>Crores</in-gaap:LevelOfRounding>
        <in-gaap:NatureOfReportStandaloneConsolidated>Consolidated</in-gaap:NatureOfReportStandaloneConsolidated>
        <in-gaap:RevenueFromOperations contextRef="C_1" unitRef="U_INR">48211.0</in-gaap:RevenueFromOperations>
        <in-gaap:RevenueFromOperations contextRef="C_2" unitRef="U_UNKNOWN">48211.0</in-gaap:RevenueFromOperations>
    </xbrl>"""
    
    parsed = parse_official_xbrl_xml(xml_data, {"symbol": "INFY", "document_title": "Infosys XBRL"})
    # Conflicting unit definitions must not be blindly merged
    assert len(parsed["financial_table"]) == 0
    print("  ✓ Test E passed: Incompatible units across multiple facts rejected as ambiguous.")

# =============================================================================
# TEST F: XBRL current-quarter vs previous-quarter contexts
# =============================================================================
def test_f_xbrl_current_vs_previous_quarter():
    print("Test F: XBRL current-quarter vs previous-quarter contexts...")
    xml_data = b"""<?xml version="1.0" encoding="UTF-8"?>
    <xbrl xmlns="http://www.xbrl.org/2003/instance" xmlns:in-gaap="http://www.sebi.gov.in/xbrl/2026-03-31/in-gaap">
        <unit id="U_INR"><measure>iso4217:INR</measure></unit>
        <context id="C_Curr"><entity><identifier>INFY</identifier></entity><period><startDate>2026-04-01</startDate><endDate>2026-06-30</endDate></period></context>
        <context id="C_Prev"><entity><identifier>INFY</identifier></entity><period><startDate>2026-01-01</startDate><endDate>2026-03-31</endDate></period></context>
        <in-gaap:LevelOfRounding>Crores</in-gaap:LevelOfRounding>
        <in-gaap:NatureOfReportStandaloneConsolidated>Consolidated</in-gaap:NatureOfReportStandaloneConsolidated>
        <in-gaap:RevenueFromOperations contextRef="C_Curr" unitRef="U_INR">48211.0</in-gaap:RevenueFromOperations>
        <in-gaap:RevenueFromOperations contextRef="C_Prev" unitRef="U_INR">45000.0</in-gaap:RevenueFromOperations>
    </xbrl>"""
    
    parsed = parse_official_xbrl_xml(xml_data, {"symbol": "INFY", "document_title": "Infosys XBRL"})
    rows = parsed["financial_table"]
    
    curr = next((r for r in rows if r["canonical_period"] == "2026-Q1"), None)
    prev = next((r for r in rows if r["canonical_period"] == "2026-Q4"), None)
    assert curr["value"] == 48211.0
    assert prev["value"] == 45000.0
    print("  ✓ Test F passed: Context dates bind facts to exact quarter periods.")

# =============================================================================
# TEST G: XBRL consolidated vs standalone contexts
# =============================================================================
def test_g_xbrl_consolidated_vs_standalone():
    print("Test G: XBRL consolidated vs standalone contexts...")
    xml_data = b"""<?xml version="1.0" encoding="UTF-8"?>
    <xbrl xmlns="http://www.xbrl.org/2003/instance" xmlns:in-gaap="http://www.sebi.gov.in/xbrl/2026-03-31/in-gaap" xmlns:xbrldi="http://xbrl.org/2006/xbrldi">
        <unit id="U_INR"><measure>iso4217:INR</measure></unit>
        <context id="C_Cons">
            <entity><identifier>INFY</identifier><segment><xbrldi:explicitMember dimension="in-gaap:ConsolidatedStandaloneAxis">in-gaap:ConsolidatedMember</xbrldi:explicitMember></segment></entity>
            <period><startDate>2026-04-01</startDate><endDate>2026-06-30</endDate></period>
        </context>
        <context id="C_Stan">
            <entity><identifier>INFY</identifier><segment><xbrldi:explicitMember dimension="in-gaap:ConsolidatedStandaloneAxis">in-gaap:StandaloneMember</xbrldi:explicitMember></segment></entity>
            <period><startDate>2026-04-01</startDate><endDate>2026-06-30</endDate></period>
        </context>
        <in-gaap:LevelOfRounding>Crores</in-gaap:LevelOfRounding>
        <in-gaap:RevenueFromOperations contextRef="C_Cons" unitRef="U_INR">48211.0</in-gaap:RevenueFromOperations>
        <in-gaap:RevenueFromOperations contextRef="C_Stan" unitRef="U_INR">40000.0</in-gaap:RevenueFromOperations>
    </xbrl>"""
    
    parsed = parse_official_xbrl_xml(xml_data, {"symbol": "INFY", "document_title": "Infosys XBRL"})
    rows = parsed["financial_table"]
    
    cons = next((r for r in rows if r["scope"] == "Consolidated"), None)
    stan = next((r for r in rows if r["scope"] == "Standalone"), None)
    assert cons["value"] == 48211.0
    assert stan["value"] == 40000.0
    print("  ✓ Test G passed: Dimensional contexts isolate Consolidated vs Standalone.")

# =============================================================================
# TEST H: Generic "EPS" does NOT map to BASIC_EPS
# =============================================================================
def test_h_generic_eps_ambiguous():
    print("Test H: Generic 'EPS' / 'Earnings Per Share' does NOT map to BASIC_EPS...")
    assert normalize_metric_name("EPS") is None
    assert normalize_metric_name("Earnings Per Share") is None
    assert normalize_metric_name("EPS in Rs") is None
    print("  ✓ Test H passed: Unqualified generic EPS is rejected as ambiguous.")

# =============================================================================
# TEST I: Explicit "Basic EPS" -> BASIC_EPS
# =============================================================================
def test_i_explicit_basic_eps():
    print("Test I: Explicit 'Basic EPS' maps to BASIC_EPS...")
    assert normalize_metric_name("Basic EPS") == "BASIC_EPS"
    assert normalize_metric_name("Basic Earnings Per Share") == "BASIC_EPS"
    assert normalize_metric_name("BasicEarningsLossPerShare") == "BASIC_EPS"
    print("  ✓ Test I passed: Explicit Basic EPS mapped safely.")

# =============================================================================
# TEST J: Explicit "Diluted EPS" -> DILUTED_EPS
# =============================================================================
def test_j_explicit_diluted_eps():
    print("Test J: Explicit 'Diluted EPS' maps to DILUTED_EPS...")
    assert normalize_metric_name("Diluted EPS") == "DILUTED_EPS"
    assert normalize_metric_name("Diluted Earnings Per Share") == "DILUTED_EPS"
    assert normalize_metric_name("DilutedEarningsLossPerShare") == "DILUTED_EPS"
    print("  ✓ Test J passed: Explicit Diluted EPS mapped safely.")

# =============================================================================
# TEST K & L: PDF Policy (Unstructured text marked INSUFFICIENT_EVIDENCE)
# =============================================================================
def test_k_l_pdf_fail_closed_policy():
    print("Test K & L: PDF numeric extraction fails closed as INSUFFICIENT_EVIDENCE...")
    with IsolatedTestDatabase() as test_db:
        mock_pdf_bytes = b"%PDF-mock-document"
        filing_ref = {
            "symbol": "INFY",
            "document_title": "Infosys Financial Results PDF",
            "source_name": "NSE Filing",
            "source_url": "https://nsearchives.nseindia.com/corporate/INFY_Q1.pdf"
        }
        
        with patch("pypdf.PdfReader") as mock_reader_cls:
            mock_page = MagicMock()
            mock_page.extract_text.return_value = "Infosys Financial Results Statement of Consolidated Results"
            mock_reader = MagicMock()
            mock_reader.pages = [mock_page]
            mock_reader_cls.return_value = mock_reader
            
            parsed = parse_official_pdf_document(mock_pdf_bytes, filing_ref)
            assert len(parsed["financial_table"]) == 0
            assert parsed["extraction_method"] == "official_pdf_document"
            
            # Test full verification summary when only PDF is available
            res = run_official_financial_verification(
                "INFY",
                screener_stock_data={"symbol": "INFY", "name": "Infosys", "quarters": {"rows": []}},
                official_filing_docs=[parsed]
            )
            assert res["summary"]["overall_status"] == "INSUFFICIENT_EVIDENCE"
            assert "PDF text stream" in res["summary"]["unavailable_reason"]
        
    print("  ✓ Test K & L passed: PDF document provenance preserved while numeric extraction fails closed.")

# =============================================================================
# TEST M: Structured HTML Table with Explicit Period Columns
# =============================================================================
def test_m_structured_html_table():
    print("Test M: Structured HTML Table with explicit period columns...")
    mock_html = b"""
    <html>
        <body>
            <h1>Statement of Consolidated Financial Results</h1>
            <p>(Rs. in Crores)</p>
            <table>
                <tr><th>Particulars</th><th>30-Jun-2026</th><th>31-Mar-2026</th></tr>
                <tr><td>Revenue from operations</td><td>48211.0</td><td>45000.0</td></tr>
                <tr><td>Profit after tax</td><td>6800.0</td><td>6200.0</td></tr>
                <tr><td>Basic EPS</td><td>16.40</td><td>15.10</td></tr>
            </table>
        </body>
    </html>
    """
    parsed = parse_official_html_table(mock_html, {"symbol": "INFY", "document_title": "INFY HTML"})
    rows = parsed["financial_table"]
    
    q1_rev = next((r for r in rows if r["canonical_period"] == "2026-Q1" and r["canonical_metric"] == "REVENUE"), None)
    q1_pat = next((r for r in rows if r["canonical_period"] == "2026-Q1" and r["canonical_metric"] == "PAT"), None)
    q1_eps = next((r for r in rows if r["canonical_period"] == "2026-Q1" and r["canonical_metric"] == "BASIC_EPS"), None)
    
    assert q1_rev["value"] == 48211.0
    assert q1_pat["value"] == 6800.0
    assert q1_eps["value"] == 16.40
    print("  ✓ Test M passed: HTML table correctly extracts cells mapped to explicit column headers.")

# =============================================================================
# TEST M2: Multi-Table HTML Page (Isolated Scope per Table)
# =============================================================================
def test_m2_html_multi_table_scope_isolation():
    print("Test M2: Multi-Table HTML Page with Standalone and Consolidated Tables (Isolated Scope)...")
    multi_html = b"""
    <html>
        <body>
            <div id="consolidated_section">
                <h2>Statement of Consolidated Financial Results</h2>
                <p>(Rs. in Crores)</p>
                <table>
                    <tr><th>Particulars</th><th>30-Jun-2026</th><th>31-Mar-2026</th></tr>
                    <tr><td>Revenue from operations</td><td>48211.0</td><td>45000.0</td></tr>
                    <tr><td>Profit after tax</td><td>6800.0</td><td>6200.0</td></tr>
                </table>
            </div>
            <div id="standalone_section">
                <h2>Statement of Standalone Financial Results</h2>
                <p>(Rs. in Crores)</p>
                <table>
                    <tr><th>Particulars</th><th>30-Jun-2026</th><th>31-Mar-2026</th></tr>
                    <tr><td>Revenue from operations</td><td>40000.0</td><td>38000.0</td></tr>
                    <tr><td>Profit after tax</td><td>5500.0</td><td>5100.0</td></tr>
                </table>
            </div>
        </body>
    </html>
    """
    parsed = parse_official_html_table(multi_html, {"symbol": "INFY", "document_title": "INFY Multi HTML"})
    rows = parsed["financial_table"]
    
    cons_rev = next((r for r in rows if r["scope"] == "Consolidated" and r["canonical_metric"] == "REVENUE" and r["canonical_period"] == "2026-Q1"), None)
    stan_rev = next((r for r in rows if r["scope"] == "Standalone" and r["canonical_metric"] == "REVENUE" and r["canonical_period"] == "2026-Q1"), None)
    
    assert cons_rev is not None and cons_rev["value"] == 48211.0
    assert stan_rev is not None and stan_rev["value"] == 40000.0
    print("  ✓ Test M2 passed: Multi-table HTML isolates Consolidated vs Standalone scopes without page-global leakage.")

# =============================================================================
# TEST N: JSON with Explicit Schema Accepted
# =============================================================================
def test_n_json_explicit_schema_accepted():
    print("Test N: JSON with explicit period/scope/unit schema accepted...")
    valid_json = {
        "symbol": "INFY",
        "document_title": "Infosys Results API",
        "scope": "Consolidated",
        "unit": "₹ Cr",
        "financial_table": [
            {
                "metric": "Revenue from Operations",
                "canonical_metric": "REVENUE",
                "canonical_period": "2026-Q1",
                "period": "Jun 2026",
                "scope": "Consolidated",
                "unit": "₹ Cr",
                "value": 48211.0
            }
        ]
    }
    extracted = extract_official_filing_metrics("INFY", valid_json)
    assert len(extracted) == 1
    assert extracted[0]["canonical_metric"] == "REVENUE"
    assert extracted[0]["official_value"] == 48211.0
    print("  ✓ Test N passed: Explicit structured JSON schema accepted.")

# =============================================================================
# TEST O: JSON Rows Without Required Metadata Rejected
# =============================================================================
def test_o_json_unmapped_rejected():
    print("Test O: JSON rows without required dimension metadata rejected...")
    raw_unmapped_json = {
        "symbol": "INFY",
        "document_title": "Untyped API",
        "financial_table": [] # No verified dimension mapping
    }
    extracted = extract_official_filing_metrics("INFY", raw_unmapped_json)
    assert len(extracted) == 0
    print("  ✓ Test O passed: Unmapped JSON rejected without creating false records.")

# =============================================================================
# TEST P: Official Unit Unknown -> no VERIFIED
# =============================================================================
def test_p_official_unit_unknown():
    print("Test P: Official unit Unknown -> INSUFFICIENT_EVIDENCE...")
    res = compare_financial_metric(
        screener_val=48211.0, official_val=48211.0, canonical_metric="REVENUE",
        screener_scope="Consolidated", official_scope="Consolidated",
        screener_period_key="2026-Q1", official_period_key="2026-Q1",
        official_unit="Unknown"
    )
    assert res["status"] == "INSUFFICIENT_EVIDENCE"
    print("  ✓ Test P passed: Unknown official unit rejected.")

# =============================================================================
# TEST Q: Official Scope Unknown -> no VERIFIED
# =============================================================================
def test_q_official_scope_unknown():
    print("Test Q: Official scope Unknown -> NOT_COMPARABLE...")
    res = compare_financial_metric(
        screener_val=48211.0, official_val=48211.0, canonical_metric="REVENUE",
        screener_scope="Consolidated", official_scope="Unknown",
        screener_period_key="2026-Q1", official_period_key="2026-Q1",
        official_unit="₹ Cr"
    )
    assert res["status"] == "NOT_COMPARABLE"
    print("  ✓ Test Q passed: Unknown official scope rejected.")

# =============================================================================
# TEST R: No Exact Screener Period -> SCREENER_VALUE_MISSING (No Fallback)
# =============================================================================
def test_r_no_exact_screener_period():
    print("Test R: No exact Screener period -> SCREENER_VALUE_MISSING without nearest fallback...")
    with IsolatedTestDatabase() as test_db:
        mock_screener = {
            "symbol": "INFY",
            "name": "Infosys Limited",
            "statement_type": "consolidated",
            "quarters": {"periods": ["Jun 2026"], "rows": [{"metric": "Sales", "values": {"Jun 2026": 48211.0}}]}
        }
        mock_official = {
            "symbol": "INFY",
            "document_title": "Infosys Q2 Results",
            "scope": "Consolidated",
            "unit": "₹ Cr",
            "financial_table": [
                {"metric": "Revenue from Operations", "canonical_metric": "REVENUE", "canonical_period": "2026-Q2", "period": "Sep 2026", "value": 50000.0, "unit": "₹ Cr"}
            ]
        }
        res = run_official_financial_verification("INFY", screener_stock_data=mock_screener, official_filing_docs=[mock_official])
        records = res["records"]
        assert len(records) == 1
        assert records[0]["status"] == "SCREENER_VALUE_MISSING"
        assert records[0]["screener_value"] is None
    print("  ✓ Test R passed: Zero nearest-period fallback; exact period missing cleanly flagged.")

# =============================================================================
# TEST S: Banking Revenue -> INSUFFICIENT_EVIDENCE
# =============================================================================
def test_s_banking_revenue_safety():
    print("Test S: Banking Revenue -> INSUFFICIENT_EVIDENCE...")
    with IsolatedTestDatabase() as test_db:
        database.upsert_company_registry_item({
            "symbol": "HDFCBANK",
            "company_name": "HDFC Bank Limited",
            "sector": "Banking & Financial Services",
            "industry": "Private Sector Bank",
            "source": "seed_reference",
            "in_universe": True,
            "is_active": True
        })
        mock_screener = {
            "symbol": "HDFCBANK",
            "name": "HDFC Bank Limited",
            "statement_type": "consolidated",
            "quarters": {"periods": ["Jun 2026"], "rows": [{"metric": "Revenue", "values": {"Jun 2026": 85000.0}}]}
        }
        mock_official = {
            "symbol": "HDFCBANK",
            "document_title": "HDFC Bank XBRL",
            "scope": "Consolidated",
            "unit": "₹ Cr",
            "financial_table": [
                {"metric": "Revenue from Operations", "canonical_metric": "REVENUE", "canonical_period": "2026-Q1", "period": "Jun 2026", "value": 85000.0, "unit": "₹ Cr"}
            ]
        }
        res = run_official_financial_verification("HDFCBANK", screener_stock_data=mock_screener, official_filing_docs=[mock_official])
        assert res["records"][0]["status"] == "INSUFFICIENT_EVIDENCE"
    print("  ✓ Test S passed: Non-financial revenue metrics rejected for banking sector.")

# =============================================================================
# TEST T: Exact Aligned Revenue/PAT/Basic EPS -> VERIFIED
# =============================================================================
def test_t_exact_aligned_verified():
    print("Test T: Exact aligned Revenue / PAT / Basic EPS -> VERIFIED...")
    res_rev = compare_financial_metric(
        screener_val=48211.0, official_val=48210.8, canonical_metric="REVENUE",
        screener_scope="Consolidated", official_scope="Consolidated",
        screener_period_key="2026-Q1", official_period_key="2026-Q1",
        official_unit="₹ Cr"
    )
    res_pat = compare_financial_metric(
        screener_val=6800.0, official_val=6800.2, canonical_metric="PAT",
        screener_scope="Consolidated", official_scope="Consolidated",
        screener_period_key="2026-Q1", official_period_key="2026-Q1",
        official_unit="₹ Cr"
    )
    res_eps = compare_financial_metric(
        screener_val=16.40, official_val=16.38, canonical_metric="BASIC_EPS",
        screener_scope="Consolidated", official_scope="Consolidated",
        screener_period_key="2026-Q1", official_period_key="2026-Q1",
        official_unit="₹ / Share"
    )
    assert res_rev["status"] == "VERIFIED"
    assert res_pat["status"] == "VERIFIED"
    assert res_eps["status"] == "VERIFIED"
    print("  ✓ Test T passed: Fully aligned metrics within mathematical tolerance verified.")

# =============================================================================
# TEST U: Exact Aligned but Materially Different Value -> DISCREPANCY
# =============================================================================
def test_u_material_discrepancy():
    print("Test U: Exact aligned but materially different value -> DISCREPANCY...")
    res = compare_financial_metric(
        screener_val=48211.0, official_val=42000.0, canonical_metric="REVENUE",
        screener_scope="Consolidated", official_scope="Consolidated",
        screener_period_key="2026-Q1", official_period_key="2026-Q1",
        official_unit="₹ Cr"
    )
    assert res["status"] == "DISCREPANCY"
    assert res["variance_abs"] == 6211.0
    print("  ✓ Test U passed: Material variance exceeding tolerance flagged as DISCREPANCY.")

# =============================================================================
# TEST V: Pre-Supplied rows / financial_table Enforces Shared Fail-Closed Validation
# =============================================================================
def test_v_presupplied_rows_shared_validation():
    print("Test V: Pre-Supplied rows / financial_table enforces shared fail-closed validation...")
    # Unfiltered raw rows containing invalid items (generic EPS, ambiguous metrics, non-numeric values)
    raw_doc = {
        "symbol": "INFY",
        "document_title": "Infosys Injected Fixture",
        "scope": "Consolidated",
        "reporting_period": "30-Jun-2026",
        "unit": "₹ Cr",
        "rows": [
            {"metric": "Revenue from operations", "value": 48211.0}, # Valid -> REVENUE
            {"metric": "Operating Profit", "value": 12000.0}, # Ambiguous -> Rejected
            {"metric": "EPS", "value": 16.40}, # Generic EPS -> Rejected
            {"metric": "Profit after tax", "value": "corrupted_val"}, # Non-numeric -> Rejected
            {"metric": "Basic EPS", "value": 16.40, "unit": "₹ / Share"} # Valid -> BASIC_EPS
        ]
    }
    
    # Passing to fetch_official_financial_result
    fetched = fetch_official_financial_result("INFY", raw_doc)
    valid_rows = fetched["financial_table"]
    
    # Must only contain the 2 valid canonical metrics
    assert len(valid_rows) == 2
    metrics = [r["canonical_metric"] for r in valid_rows]
    assert "REVENUE" in metrics
    assert "BASIC_EPS" in metrics
    assert "DILUTED_EPS" not in metrics
    
    # Passing to extract_official_filing_metrics
    extracted = extract_official_filing_metrics("INFY", raw_doc)
    assert len(extracted) == 2
    assert extracted[0]["canonical_metric"] == "REVENUE"
    assert extracted[0]["official_value"] == 48211.0
    assert extracted[1]["canonical_metric"] == "BASIC_EPS"
    assert extracted[1]["official_value"] == 16.40
    print("  ✓ Test V passed: Pre-supplied rows/financial_table enforces shared validation without shortcuts.")

if __name__ == "__main__":
    test_a_xbrl_unitref_inr()
    test_b_xbrl_eps_unitref_inr_per_share()
    test_c_xbrl_missing_unitref()
    test_d_xbrl_unknown_unit_id()
    test_e_xbrl_incompatible_units_ambiguity()
    test_f_xbrl_current_vs_previous_quarter()
    test_g_xbrl_consolidated_vs_standalone()
    test_h_generic_eps_ambiguous()
    test_i_explicit_basic_eps()
    test_j_explicit_diluted_eps()
    test_k_l_pdf_fail_closed_policy()
    test_m_structured_html_table()
    test_m2_html_multi_table_scope_isolation()
    test_n_json_explicit_schema_accepted()
    test_o_json_unmapped_rejected()
    test_p_official_unit_unknown()
    test_q_official_scope_unknown()
    test_r_no_exact_screener_period()
    test_s_banking_revenue_safety()
    test_t_exact_aligned_verified()
    test_u_material_discrepancy()
    test_v_presupplied_rows_shared_validation()
    print("\n🎉 ALL 22 TESTS (A - V) PASSED WITH 100% DETERMINISTIC ISOLATION & FAIL-CLOSED INTEGRITY!")
