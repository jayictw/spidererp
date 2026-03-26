import importlib
import json
import os
import sqlite3
import sys
import time
import unittest
from pathlib import Path

from tests.quote_test_support import create_quote_test_env


class TestBridgeQuoteRoutes(unittest.TestCase):
    def setUp(self) -> None:
        self.env = create_quote_test_env()
        os.environ["QUOTE_SOL_DB_PATH"] = str(self.env.db_path)
        os.environ["QUOTE_SOQ_DB_PATH"] = str(self.env.soq_db_path)
        os.environ["BRIDGE_SUPER_ACTOR_ID"] = "owner_qq_10001"
        bridge_root = str(Path(r"F:/Jay_ic_tw/qq/agent-harness"))
        if bridge_root not in sys.path:
            sys.path.insert(0, bridge_root)
        if "bridge_server" in sys.modules:
            del sys.modules["bridge_server"]
        self.bridge_server = importlib.import_module("bridge_server")

    def tearDown(self) -> None:
        self.bridge_server = None
        if "bridge_server" in sys.modules:
            del sys.modules["bridge_server"]
        os.environ.pop("QUOTE_SOL_DB_PATH", None)
        os.environ.pop("QUOTE_SOQ_DB_PATH", None)
        os.environ.pop("BRIDGE_SUPER_ACTOR_ID", None)
        last_error = None
        for _ in range(5):
            try:
                self.env.cleanup()
                last_error = None
                break
            except PermissionError as exc:
                last_error = exc
                time.sleep(0.1)
        if last_error is not None:
            raise last_error

    def test_quote_preview_route_smoke(self) -> None:
        result = self.bridge_server._run_quote_preview("/quote-preview STM32F103C8T6 1200pcs", customer_id="cust_demo_001")
        self.assertTrue(result["ok"])
        self.assertEqual(result["result"]["reply_preview"]["action"], "apply_then_handoff_preview")
        self.assertTrue(int(result["task_id"]) > 0)

    def test_quote_task_route_smoke(self) -> None:
        preview = self.bridge_server._run_quote_preview("/quote-preview STM32F103C8T6 1200pcs", customer_id="cust_demo_001")
        task_id = int(preview["task_id"])
        result = self.bridge_server._run_quote_task_timeline(f"/quote-task {task_id}")
        summary_text = self.bridge_server._build_task_timeline_summary_text(result)
        self.assertTrue(result["ok"])
        self.assertEqual(result["timeline_summary"]["event_count"], 7)
        self.assertIn("任务", summary_text)
        self.assertIn("事件数 7", summary_text)

    def test_quote_task_route_rejects_missing_id(self) -> None:
        result = self.bridge_server._run_quote_task_timeline("/quote-task")
        self.assertFalse(result["ok"])
        self.assertIn("requires a task id", result["error"])

    def test_refresh_quote_inputs_route_smoke(self) -> None:
        conn = sqlite3.connect(self.env.db_path)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS erp_inventory (
              erp_inventory_id INTEGER PRIMARY KEY AUTOINCREMENT,
              import_batch_id TEXT NOT NULL,
              row_no INTEGER,
              action_type TEXT,
              model TEXT NOT NULL,
              warehouse TEXT,
              brand TEXT,
              batch_no TEXT,
              stock_qty REAL,
              aging_days REAL,
              currency TEXT,
              usd_purchase_price REAL,
              taxed_purchase_price REAL,
              origin TEXT,
              inventory_value_cny_ex_tax REAL,
              inventory_value_cny_tax REAL,
              tax_rate REAL,
              floor_sale_price REAL,
              taxed_sale_price REAL,
              standard_sale_price REAL,
              standard_pack_qty REAL,
              min_pack_qty REAL,
              inbound_date TEXT,
              package_type TEXT,
              lifecycle TEXT,
              product_category TEXT,
              supply_status TEXT,
              source_file TEXT,
              imported_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO erp_inventory(
              import_batch_id, model, stock_qty, floor_sale_price, taxed_sale_price,
              standard_sale_price, package_type, supply_status, source_file, imported_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?)
            """,
            (
                "erp_test_batch",
                "STM32F103C8T6",
                1200,
                1.10,
                1.45,
                1.45,
                "Tray",
                "随时有货",
                "fixture.xlsx",
                "2026-03-15T00:00:00",
            ),
        )
        conn.commit()
        conn.close()

        real_soq_db = str(Path(r"F:/Jay_ic_tw/qq/agent-harness/soq.db"))
        os.environ["QUOTE_SOQ_DB_PATH"] = real_soq_db
        self.bridge_server.QUOTE_SOQ_DB_PATH = real_soq_db

        result = self.bridge_server._run_refresh_quote_inputs()
        self.assertTrue(result["ok"])
        payload = result["result"]
        self.assertTrue(payload["ok"])
        self.assertIn("guardrail_refresh", payload)
        self.assertEqual(payload["guardrail_refresh"]["smoke_result"]["override_row_count"], 2)

        summary = self.bridge_server._build_refresh_summary_text(result)
        self.assertIn("已刷新报价输入", summary)
        self.assertIn("首报规则 2", summary)

        log_result = self.bridge_server._log_refresh_quote_inputs(
            conversation="refresh-conv-001",
            raw_message="/refresh-quote-inputs",
            customer_id="owner_qq_10001",
            refresh_result=result,
        )
        self.assertTrue(log_result["ok"])

        soq_conn = sqlite3.connect(real_soq_db)
        try:
            row = soq_conn.execute(
                "SELECT action_taken, handoff_reason, agent_reply FROM soq_logs ORDER BY id DESC LIMIT 1"
            ).fetchone()
        finally:
            soq_conn.close()

        self.assertEqual(row[0], "refresh_quote_inputs")
        self.assertIn("guardrail_count=", row[1])
        agent_reply = json.loads(row[2])
        self.assertIn("refresh_summary_text", agent_reply)

    def test_super_actor_match_helper(self) -> None:
        self.assertTrue(self.bridge_server._is_bridge_super_actor("owner_qq_10001"))
        self.assertFalse(self.bridge_server._is_bridge_super_actor("cust_demo_001"))


if __name__ == "__main__":
    unittest.main()
