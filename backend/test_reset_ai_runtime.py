import hashlib
import io
import json
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stdout
from dataclasses import replace
from pathlib import Path

from tools import reset_ai_runtime


AI_TABLES = reset_ai_runtime.AI_RUNTIME_TABLES
PROTECTED_TABLES = reset_ai_runtime.PROTECTED_SYMBOL_TABLES


class ResetAiRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="stocker_reset_test_")
        self.root = Path(self.temp_dir.name)
        self.db_path = self.root / "stocker.db"
        self.cache_dir = self.root / "pdf_cache"
        self.generated_dir = self.root / "doc_intelligence_generated"
        self.cache_dir.mkdir()
        self.generated_dir.mkdir()
        self.icici_urls = (
            "https://example.test/icici-q1.pdf",
            "https://example.test/icici-annual.pdf",
        )
        self.reliance_url = "https://example.test/reliance.pdf"
        self._create_schema_and_data()
        for url in (*self.icici_urls, self.reliance_url):
            key = hashlib.md5(url.encode("utf-8")).hexdigest()
            (self.cache_dir / f"{key}.json").write_text("[]", encoding="utf-8")
        self.orphan_cache = self.cache_dir / ("f" * 32 + ".json")
        self.orphan_cache.write_text("[]", encoding="utf-8")
        (self.generated_dir / "ICICIBANK.json").write_text("{}", encoding="utf-8")
        (self.generated_dir / "RELIANCE.json").write_text("{}", encoding="utf-8")

    def tearDown(self):
        self.temp_dir.cleanup()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _create_schema_and_data(self):
        conn = self._connect()
        try:
            for table in AI_TABLES:
                conn.execute(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY, symbol TEXT NOT NULL)")
            conn.execute(
                "CREATE TABLE document_pages_cache "
                "(id INTEGER PRIMARY KEY, symbol TEXT NOT NULL, doc_url TEXT NOT NULL)"
            )
            conn.execute(
                "CREATE TABLE source_documents "
                "(id INTEGER PRIMARY KEY, symbol TEXT NOT NULL, url TEXT NOT NULL)"
            )
            conn.execute(
                "CREATE TABLE stocks_cache "
                "(symbol TEXT PRIMARY KEY, data_json TEXT NOT NULL)"
            )
            for table in PROTECTED_TABLES:
                if table in {"source_documents", "stocks_cache"}:
                    continue
                conn.execute(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY, symbol TEXT NOT NULL)")
            for table in reset_ai_runtime.PROTECTED_GLOBAL_TABLES:
                conn.execute(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY)")

            next_id = 1
            for table in AI_TABLES:
                conn.execute(f"INSERT INTO {table} (id, symbol) VALUES (?, ?)", (next_id, "ICICIBANK"))
                conn.execute(f"INSERT INTO {table} (id, symbol) VALUES (?, ?)", (next_id + 1, "RELIANCE"))
                next_id += 2
            conn.executemany(
                "INSERT INTO document_pages_cache (id, symbol, doc_url) VALUES (?, ?, ?)",
                (
                    (1, "ICICIBANK", self.icici_urls[0]),
                    (2, "ICICIBANK", self.icici_urls[0]),
                    (3, "ICICIBANK", self.icici_urls[1]),
                    (4, "RELIANCE", self.reliance_url),
                ),
            )
            conn.executemany(
                "INSERT INTO source_documents (id, symbol, url) VALUES (?, ?, ?)",
                (
                    (1, "ICICIBANK", self.icici_urls[0]),
                    (2, "ICICIBANK", self.icici_urls[1]),
                    (3, "RELIANCE", self.reliance_url),
                ),
            )
            statements = {
                "profit_loss": {},
                "balance_sheet": {},
                "cash_flow": {},
                "quarters": {},
                "documents": ["preserved"],
            }
            conn.execute(
                "INSERT INTO stocks_cache (symbol, data_json) VALUES (?, ?)",
                ("ICICIBANK", json.dumps(statements)),
            )
            conn.execute(
                "INSERT INTO stocks_cache (symbol, data_json) VALUES (?, ?)",
                ("RELIANCE", json.dumps(statements)),
            )
            for table in PROTECTED_TABLES:
                if table in {"source_documents", "stocks_cache"}:
                    continue
                conn.execute(f"INSERT INTO {table} (id, symbol) VALUES (?, ?)", (1, "ICICIBANK"))
                conn.execute(f"INSERT INTO {table} (id, symbol) VALUES (?, ?)", (2, "RELIANCE"))
            for table in reset_ai_runtime.PROTECTED_GLOBAL_TABLES:
                conn.execute(f"INSERT INTO {table} (id) VALUES (1)")
            conn.commit()
        finally:
            conn.close()

    def _build_plan(self, purge=True):
        return reset_ai_runtime.build_reset_plan(
            "ICICIBANK",
            purge_document_pages=purge,
            db_path=self.db_path,
            cache_dir=self.cache_dir,
            generated_dir=self.generated_dir,
        )

    def _symbol_count(self, table, symbol):
        conn = self._connect()
        try:
            return conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE symbol = ?", (symbol,)
            ).fetchone()[0]
        finally:
            conn.close()

    def _reliance_snapshot(self):
        tables = (*AI_TABLES, reset_ai_runtime.DOCUMENT_PAGE_TABLE, *PROTECTED_TABLES)
        return {table: self._symbol_count(table, "RELIANCE") for table in tables}

    def test_dry_run_counts_and_does_not_mutate(self):
        reliance_before = self._reliance_snapshot()
        plan = self._build_plan(purge=True)
        changes = {item.resource: item for item in plan.resources}

        for table in AI_TABLES:
            self.assertEqual(changes[table].to_delete, 1)
        self.assertEqual(changes[reset_ai_runtime.DOCUMENT_PAGE_TABLE].to_delete, 3)
        self.assertEqual(changes["document_page_cache_files"].to_delete, 2)
        self.assertEqual(changes["generated_document_intelligence_json"].to_delete, 1)
        self.assertEqual(plan.protected_symbol_counts["source_documents"], 2)
        self.assertEqual(plan.protected_symbol_counts["stocks_cache"], 1)
        self.assertEqual(plan.protected_symbol_counts["standardized_statement_collections"], 4)
        self.assertEqual(plan.protected_symbol_counts["company_registry"], 1)
        for resource in reset_ai_runtime.SAFETY_CRITICAL_RESOURCES:
            self.assertEqual(changes[resource].to_delete, 0)

        for table in AI_TABLES:
            self.assertEqual(self._symbol_count(table, "ICICIBANK"), 1)
        self.assertEqual(self._reliance_snapshot(), reliance_before)
        self.assertTrue((self.generated_dir / "ICICIBANK.json").exists())
        self.assertEqual(len(list(self.cache_dir.iterdir())), 4)

    def test_reset_clears_only_allowlisted_icici_runtime_state(self):
        plan = self._build_plan(purge=True)
        reliance_before = self._reliance_snapshot()
        protected_before = {
            table: self._symbol_count(table, "ICICIBANK") for table in PROTECTED_TABLES
        }

        result = reset_ai_runtime.apply_reset(plan)

        for table in AI_TABLES:
            self.assertEqual(result.deleted[table], 1)
            self.assertEqual(self._symbol_count(table, "ICICIBANK"), 0)
        self.assertEqual(result.deleted[reset_ai_runtime.DOCUMENT_PAGE_TABLE], 3)
        self.assertEqual(self._symbol_count(reset_ai_runtime.DOCUMENT_PAGE_TABLE, "ICICIBANK"), 0)
        self.assertEqual(result.deleted["document_page_cache_files"], 2)
        self.assertEqual(result.deleted["generated_document_intelligence_json"], 1)

        protected_after = {
            table: self._symbol_count(table, "ICICIBANK") for table in PROTECTED_TABLES
        }
        self.assertEqual(protected_after, protected_before)
        self.assertEqual(self._reliance_snapshot(), reliance_before)
        self.assertFalse((self.generated_dir / "ICICIBANK.json").exists())
        self.assertTrue((self.generated_dir / "RELIANCE.json").exists())
        self.assertTrue(self.orphan_cache.exists())
        reliance_cache = hashlib.md5(self.reliance_url.encode("utf-8")).hexdigest()
        self.assertTrue((self.cache_dir / f"{reliance_cache}.json").exists())
        for url in self.icici_urls:
            cache_key = hashlib.md5(url.encode("utf-8")).hexdigest()
            self.assertFalse((self.cache_dir / f"{cache_key}.json").exists())

    def test_document_pages_require_explicit_purge_flag(self):
        plan = self._build_plan(purge=False)
        changes = {item.resource: item for item in plan.resources}
        self.assertEqual(changes[reset_ai_runtime.DOCUMENT_PAGE_TABLE].to_delete, 0)
        self.assertEqual(changes["document_page_cache_files"].to_delete, 0)
        reset_ai_runtime.apply_reset(plan)
        self.assertEqual(self._symbol_count(reset_ai_runtime.DOCUMENT_PAGE_TABLE, "ICICIBANK"), 3)
        for url in self.icici_urls:
            cache_key = hashlib.md5(url.encode("utf-8")).hexdigest()
            self.assertTrue((self.cache_dir / f"{cache_key}.json").exists())

    def test_rejects_empty_wildcard_and_multi_symbol_inputs(self):
        invalid = ("", "   ", "ALL", "%", "_", "ICICI%", "ICICI_", "ICICI*", "ICICI?", "ICICI,RELIANCE", "ICICI RELIANCE")
        for symbol in invalid:
            with self.subTest(symbol=symbol):
                with self.assertRaises(reset_ai_runtime.ResetSafetyError):
                    reset_ai_runtime.normalize_symbol(symbol)

    def test_safety_gate_refuses_any_protected_deletion(self):
        plan = self._build_plan(purge=True)
        resources = tuple(
            replace(item, to_delete=1) if item.resource == "source_documents" else item
            for item in plan.resources
        )
        unsafe_plan = replace(plan, resources=resources)
        with self.assertRaises(reset_ai_runtime.ResetSafetyError):
            reset_ai_runtime.assert_plan_safe(unsafe_plan)

    def test_cli_dry_run_prints_required_preservation_counts(self):
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = reset_ai_runtime.main(
                [
                    "ICICIBANK",
                    "--purge-document-pages",
                    "--dry-run",
                    "--db-path",
                    str(self.db_path),
                    "--cache-dir",
                    str(self.cache_dir),
                    "--generated-dir",
                    str(self.generated_dir),
                ]
            )
        rendered = output.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("RESOURCE", rendered)
        self.assertIn("source_documents: 2", rendered)
        self.assertIn("stocks_cache: 1", rendered)
        self.assertIn("standardized_statement_collections: 4", rendered)
        self.assertIn("company_registry: 1", rendered)
        self.assertIn("No data or files changed", rendered)


if __name__ == "__main__":
    unittest.main()
