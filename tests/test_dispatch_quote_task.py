import sqlite3
import tempfile
import unittest
from pathlib import Path
import gc
import io
from contextlib import redirect_stdout

from scripts.dispatch_quote_task import main as dispatch_main
from scripts.quote_agents.task_queue import ensure_quote_tasks_table, enqueue_quote_task
from scripts.show_quote_task_timeline import main as show_task_timeline_main


class TestDispatchQuoteTask(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "sol.db"
        self.soq_db_path = Path(self.tmpdir.name) / "soq.db"

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
            CREATE TABLE supplier_items (
              supplier_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
              batch_id TEXT NOT NULL,
              supplier_name TEXT,
              supplier_part_number TEXT NOT NULL,
              normalized_part_number TEXT,
              normalization_basis TEXT,
              supplier_stock_raw TEXT,
              supplier_stock_qty REAL,
              supplier_stock_year TEXT,
              supplier_stock_lot TEXT,
              supplier_package TEXT,
              supplier_lead_time TEXT,
              supplier_stock_note TEXT,
              parse_confidence REAL,
              parse_status TEXT,
              created_at TEXT NOT NULL
            );
            CREATE TABLE market_quotes (
              market_quote_id INTEGER PRIMARY KEY AUTOINCREMENT,
              batch_id TEXT NOT NULL,
              supplier_item_id INTEGER NOT NULL,
              source_platform TEXT NOT NULL,
              searched_keyword TEXT,
              matched_part_number TEXT,
              match_confidence REAL,
              price REAL,
              currency TEXT,
              package TEXT,
              moq REAL,
              stock REAL,
              seller_name TEXT,
              region TEXT,
              url TEXT,
              capture_time TEXT,
              match_status TEXT,
              notes TEXT,
              raw_snapshot_path TEXT,
              created_at TEXT NOT NULL
            );
            CREATE TABLE parts_pricing (
              model TEXT,
              st_official_price_usd REAL,
              lc_price_cny_tax REAL,
              agent_price_usd REAL,
              recent_orders REAL,
              lc_to_st_ratio REAL,
              agent_to_st_ratio REAL,
              usd_fx_rate INTEGER,
              tax_factor REAL,
              lc_price_cny_tax_extracted REAL,
              lc_recent_orders_extracted REAL,
              lc_price_usd_ex_tax REAL
            );
            CREATE TABLE trader_quotes (
              trader_quote_id INTEGER PRIMARY KEY AUTOINCREMENT,
              import_batch_id TEXT NOT NULL,
              normalized_part_number TEXT NOT NULL,
              trader_name TEXT,
              quoted_price REAL,
              currency TEXT,
              quoted_qty REAL,
              source TEXT,
              source_url TEXT,
              note TEXT,
              captured_at TEXT,
              created_at TEXT NOT NULL
            );
            """
        )
        ensure_quote_tasks_table(conn)
        conn.execute(
            """
            INSERT INTO supplier_items(batch_id, supplier_part_number, normalized_part_number, normalization_basis, supplier_stock_raw, supplier_stock_qty, parse_confidence, parse_status, created_at)
            VALUES(?,?,?,?,?,?,?,?,?)
            """,
            ("batch_q", "STM32L412CBU6", "STM32L412CBU6", "exact_input", "qty=1000", 1000, 0.9, "parsed", "2026-03-15T00:00:00"),
        )
        supplier_item_id = conn.execute("SELECT supplier_item_id FROM supplier_items").fetchone()[0]
        conn.execute(
            """
            INSERT INTO market_quotes(batch_id, supplier_item_id, source_platform, searched_keyword, matched_part_number, match_confidence, price, currency, match_status, created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?)
            """,
            ("batch_q", supplier_item_id, "so.szlcsc.com", "STM32L412CBU6", "STM32L412CBU6", 0.98, 1.2, "USD", "matched_exact", "2026-03-15T00:00:00"),
        )
        conn.commit()
        conn.close()

        soq = sqlite3.connect(self.soq_db_path)
        soq.executescript(
            """
            CREATE TABLE products (
              model TEXT PRIMARY KEY,
              normal_price REAL NOT NULL,
              tier_price_json TEXT,
              floor_price REAL NOT NULL,
              min_auto_accept_price REAL NOT NULL,
              default_supply_type TEXT,
              active INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE customers (
              customer_id TEXT PRIMARY KEY,
              qq_id TEXT,
              customer_name TEXT,
              level TEXT,
              is_old_customer INTEGER DEFAULT 0,
              price_sensitivity_score REAL DEFAULT 0,
              allow_floor_strategy INTEGER DEFAULT 0,
              notes TEXT
            );
            CREATE TABLE soq_logs (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              conversation_id TEXT NOT NULL,
              customer_id TEXT,
              raw_message TEXT,
              parsed_model TEXT,
              parsed_qty INTEGER,
              action_taken TEXT NOT NULL,
              quoted_price REAL,
              handoff_reason TEXT,
              confidence REAL,
              agent_reply TEXT,
              created_at TEXT NOT NULL
            );
            """
        )
        soq.execute(
            "INSERT INTO products(model, normal_price, floor_price, min_auto_accept_price, default_supply_type, active) VALUES(?,?,?,?,?,1)",
            ("STM32L412CBU6", 1.5, 1.2, 1.25, "stock"),
        )
        soq.commit()
        soq.close()

    def tearDown(self) -> None:
        gc.collect()
        self.tmpdir.cleanup()

    def test_enqueue_and_run_stages(self) -> None:
        import sys

        old_argv = sys.argv
        try:
            sys.argv = [
                "dispatch_quote_task.py",
                "--db-path",
                str(self.db_path),
                "--soq-db-path",
                str(self.soq_db_path),
                "--enqueue",
                "--part-number",
                "STM32L412CBU6",
                "--requested-qty",
                "1000",
                "--customer-id",
                "cust_test_001",
            ]
            rc = dispatch_main()
            self.assertEqual(rc, 0)

            sys.argv = [
                "dispatch_quote_task.py",
                "--db-path",
                str(self.db_path),
                "--soq-db-path",
                str(self.soq_db_path),
                "--run-stage",
                "queued",
            ]
            rc = dispatch_main()
            self.assertEqual(rc, 0)

            sys.argv = [
                "dispatch_quote_task.py",
                "--db-path",
                str(self.db_path),
                "--soq-db-path",
                str(self.soq_db_path),
                "--run-stage",
                "evidence_ready",
            ]
            rc = dispatch_main()
            self.assertEqual(rc, 0)

            sys.argv = [
                "dispatch_quote_task.py",
                "--db-path",
                str(self.db_path),
                "--soq-db-path",
                str(self.soq_db_path),
                "--run-stage",
                "decision_ready",
            ]
            rc = dispatch_main()
            self.assertEqual(rc, 0)
        finally:
            sys.argv = old_argv

        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            "SELECT status, stage, assigned_worker, decision_id, evidence_json, result_json FROM quote_tasks ORDER BY task_id DESC LIMIT 1"
        ).fetchone()
        self.assertEqual(row[0], "completed")
        self.assertEqual(row[1], "completed")
        self.assertEqual(row[2], "qq_preview_worker")
        self.assertIsNotNone(row[3])
        self.assertIsNotNone(row[4])
        self.assertIn("quote_pipeline_task_v2", row[5])
        events = conn.execute(
            "SELECT event_type, from_stage, to_stage, worker, status FROM quote_task_events ORDER BY event_id ASC"
        ).fetchall()
        self.assertEqual(events[0][0], "enqueue")
        self.assertEqual(events[1][0], "claim")
        self.assertEqual(events[2][0], "stage_advance")
        self.assertEqual(events[-1][0], "completed")
        conn.close()

    def test_run_stage_uses_specific_task_id(self) -> None:
        import sys

        conn = sqlite3.connect(self.db_path)
        first_task_id = enqueue_quote_task(
            conn,
            source="manual",
            part_number="STM32L412CBU6",
            requested_qty=1000,
            customer_id="cust_test_001",
        )
        second_task_id = enqueue_quote_task(
            conn,
            source="manual",
            part_number="STM32L412CBU6",
            requested_qty=2000,
            customer_id="cust_test_002",
        )
        conn.close()

        old_argv = sys.argv
        try:
            sys.argv = [
                "dispatch_quote_task.py",
                "--db-path",
                str(self.db_path),
                "--soq-db-path",
                str(self.soq_db_path),
                "--run-stage",
                "queued",
                "--task-id",
                str(second_task_id),
            ]
            rc = dispatch_main()
            self.assertEqual(rc, 0)
        finally:
            sys.argv = old_argv

        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            "SELECT task_id, stage, status FROM quote_tasks ORDER BY task_id ASC"
        ).fetchall()
        self.assertEqual(rows[0][0], first_task_id)
        self.assertEqual(rows[0][1], "queued")
        self.assertEqual(rows[1][0], second_task_id)
        self.assertEqual(rows[1][1], "evidence_ready")
        conn.close()

    def test_show_quote_task_timeline(self) -> None:
        import sys

        conn = sqlite3.connect(self.db_path)
        task_id = enqueue_quote_task(
            conn,
            source="manual",
            part_number="STM32L412CBU6",
            requested_qty=1000,
            customer_id="cust_test_001",
        )
        conn.close()

        old_argv = sys.argv
        buf = io.StringIO()
        try:
            for stage in ("queued", "evidence_ready", "decision_ready"):
                sys.argv = [
                    "dispatch_quote_task.py",
                    "--db-path",
                    str(self.db_path),
                    "--soq-db-path",
                    str(self.soq_db_path),
                    "--run-stage",
                    stage,
                    "--task-id",
                    str(task_id),
                ]
                rc = dispatch_main()
                self.assertEqual(rc, 0)

            sys.argv = [
                "show_quote_task_timeline.py",
                "--db-path",
                str(self.db_path),
                "--task-id",
                str(task_id),
            ]
            with redirect_stdout(buf):
                rc = show_task_timeline_main()
            self.assertEqual(rc, 0)
        finally:
            sys.argv = old_argv

        payload = buf.getvalue()
        self.assertIn(f'"task_id": {task_id}', payload)
        self.assertIn('"event_type": "enqueue"', payload)
        self.assertIn('"event_type": "completed"', payload)
        self.assertIn('"event_count": 7', payload)


if __name__ == "__main__":
    unittest.main()
