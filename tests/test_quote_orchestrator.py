import sqlite3
import tempfile
import unittest
from pathlib import Path

import scripts.quote_orchestrator as quote_orchestrator
from scripts.quote_agents.decision_writer import ensure_pricing_decisions_table, write_pricing_decision
from scripts.quote_orchestrator import build_quote_context


class TestQuoteOrchestrator(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.tmpdir = tempfile.TemporaryDirectory()
        self.soq_db_path = Path(self.tmpdir.name) / "soq.db"
        self.override_path = Path(self.tmpdir.name) / "quote_first_round_overrides.csv"
        self.guardrail_path = Path(self.tmpdir.name) / "quote_first_round_handoff_guardrails.csv"
        self.override_path.write_text(
            "\n".join(
                [
                    "normalized_part_number,inquiry_type,qty_min,qty_max,first_quote_price,currency,note",
                    "STM32L412CBU6,general,1560,1560,11.5,CNY,test override",
                    "LM2904YPT,general,120000,120000,0.28,CNY,test override",
                ]
            ),
            encoding="utf-8-sig",
        )
        self.guardrail_path.write_text(
            "normalized_part_number,requested_qty,override_price,handoff_reason,reply_action,guardrail_action\n",
            encoding="utf-8-sig",
        )
        self.original_override_path = quote_orchestrator.FIRST_ROUND_OVERRIDE_PATH
        self.original_guardrail_path = quote_orchestrator.HANDOFF_GUARDRAIL_PATH
        quote_orchestrator.FIRST_ROUND_OVERRIDE_PATH = self.override_path
        quote_orchestrator.HANDOFF_GUARDRAIL_PATH = self.guardrail_path
        self.conn.executescript(
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
            CREATE TABLE erp_inventory (
              erp_inventory_id INTEGER PRIMARY KEY AUTOINCREMENT,
              import_batch_id TEXT,
              model TEXT,
              stock_qty REAL,
              floor_sale_price REAL,
              standard_sale_price REAL,
              taxed_sale_price REAL,
              supply_status TEXT,
              package_type TEXT,
              inbound_date TEXT,
              warehouse TEXT
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
        ensure_pricing_decisions_table(self.conn)
        self.conn.execute(
            """
            INSERT INTO supplier_items(
              batch_id, supplier_part_number, normalized_part_number, normalization_basis,
              supplier_stock_raw, supplier_stock_qty, parse_confidence, parse_status, created_at
            ) VALUES(?,?,?,?,?,?,?,?,?)
            """,
            (
                "batch_a",
                "STM32L412CBU6",
                "STM32L412CBU6",
                "exact_input",
                "庫存数量=319800",
                319800,
                0.4,
                "parsed",
                "2026-03-15T14:16:21",
            ),
        )
        supplier_item_id = self.conn.execute("SELECT supplier_item_id FROM supplier_items").fetchone()[0]
        self.conn.executemany(
            """
            INSERT INTO market_quotes(
              batch_id, supplier_item_id, source_platform, searched_keyword, matched_part_number,
              match_confidence, price, currency, package, moq, stock, seller_name, region,
              url, capture_time, match_status, notes, raw_snapshot_path, created_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            [
                (
                    "batch_a",
                    supplier_item_id,
                    "bomman.com",
                    "STM32L412CBU6",
                    "",
                    0.0,
                    None,
                    "",
                    "",
                    None,
                    None,
                    "",
                    "",
                    "https://www.bomman.com/?s=STM32L412CBU6",
                    "2026-03-15T14:11:25",
                    "not_found",
                    "no part token hit in response text",
                    "snap1.txt",
                    "2026-03-15T14:11:25",
                ),
                (
                    "batch_a",
                    supplier_item_id,
                    "so.szlcsc.com",
                    "STM32L412CBU6",
                    "STM32L412CBU6",
                    0.95,
                    1.23,
                    "USD",
                    "LQFP48",
                    1,
                    100,
                    "",
                    "",
                    "https://so.szlcsc.com/global.html?k=STM32L412CBU6",
                    "2026-03-15T14:11:26",
                    "matched_exact",
                    "",
                    "snap2.txt",
                    "2026-03-15T14:11:26",
                ),
            ],
        )
        self.conn.execute(
            """
            INSERT INTO parts_pricing(model, st_official_price_usd, agent_price_usd)
            VALUES(?,?,?)
            """,
            ("STM32L412CBU6", 1.11, 1.35),
        )
        self.conn.execute(
            """
            INSERT INTO parts_pricing(model, st_official_price_usd, agent_price_usd, recent_orders, lc_price_usd_ex_tax)
            VALUES(?,?,?,?,?)
            """,
            ("LM2904YPT", 0.24, 0.26, 100, 0.04),
        )
        self.conn.execute(
            """
            INSERT INTO erp_inventory(import_batch_id, model, stock_qty, floor_sale_price, standard_sale_price, taxed_sale_price, supply_status, package_type, inbound_date, warehouse)
            VALUES(?,?,?,?,?,?,?,?,?,?)
            """,
            ("erp_batch_a", "STM32G431CBT6", 228, 10.6195, 11.5044, 12.0, "等待分货", "托盘Tray", "2025-11-28T00:00:00", "宝华仓"),
        )
        self.conn.execute(
            """
            INSERT INTO trader_quotes(import_batch_id, normalized_part_number, trader_name, quoted_price, currency, source, created_at)
            VALUES(?,?,?,?,?,?,?)
            """,
            ("trader_batch_a", "STM32L412CBU6", "TraderA", 1.33, "USD", "manual_csv", "2026-03-15T14:16:21"),
        )
        soq_conn = sqlite3.connect(self.soq_db_path)
        soq_conn.row_factory = sqlite3.Row
        soq_conn.executescript(
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
        soq_conn.execute(
            """
            INSERT INTO products(model,normal_price,floor_price,min_auto_accept_price,default_supply_type,active)
            VALUES(?,?,?,?,?,1)
            """,
            ("STM32L412CBU6", 1.52, 1.18, 1.25, "stock"),
        )
        soq_conn.execute(
            """
            INSERT INTO products(model,normal_price,floor_price,min_auto_accept_price,default_supply_type,active)
            VALUES(?,?,?,?,?,1)
            """,
            ("STM32F103C8T6", 1.45, 1.1, 1.2, "stock"),
        )
        soq_conn.execute(
            """
            INSERT INTO customers(customer_id,level,price_sensitivity_score,allow_floor_strategy,notes)
            VALUES(?,?,?,?,?)
            """,
            ("cust_1", "A", 0.85, 1, "VIP high-volume customer"),
        )
        soq_conn.execute(
            """
            INSERT INTO soq_logs(conversation_id,customer_id,parsed_model,action_taken,quoted_price,created_at)
            VALUES(?,?,?,?,?,?)
            """,
            ("conv_1", "cust_1", "STM32L412CBU6", "auto_quote", 1.41, "2026-03-14T10:00:00Z"),
        )
        soq_conn.execute(
            """
            INSERT INTO soq_logs(conversation_id,customer_id,parsed_model,action_taken,quoted_price,created_at)
            VALUES(?,?,?,?,?,?)
            """,
            ("compat-003", None, "STM32F103C8T6", "auto_quote", 1.45, "2026-03-14T03:14:58Z"),
        )
        soq_conn.commit()
        soq_conn.close()
        self.conn.commit()

    def tearDown(self) -> None:
        quote_orchestrator.FIRST_ROUND_OVERRIDE_PATH = self.original_override_path
        quote_orchestrator.HANDOFF_GUARDRAIL_PATH = self.original_guardrail_path
        self.conn.close()
        self.tmpdir.cleanup()

    def test_build_quote_context(self) -> None:
        payload = build_quote_context(
            self.conn,
            "STM32L412CBU6",
            batch_id="batch_a",
            requested_qty=500,
            customer_id="cust_1",
            soq_db_path=str(self.soq_db_path),
        )
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["supplier_item"]["normalized_part_number"], "STM32L412CBU6")
        self.assertEqual(payload["market_summary"]["market_low_price"], 1.23)
        self.assertEqual(payload["trader_summary"]["trader_reference_price"], 1.33)
        self.assertEqual(payload["erp_context"]["erp_normal_price"], 1.52)
        self.assertEqual(payload["erp_context"]["erp_floor_price"], 1.18)
        self.assertEqual(payload["erp_context"]["last_deal_price"], 1.41)
        self.assertEqual(payload["erp_context"]["customer_tier"], "A")
        self.assertTrue(payload["decision_stub"]["auto_reply_allowed"])
        self.assertEqual(payload["decision_stub"]["quote_strategy"], "direct_quote")
        self.assertEqual(payload["decision_stub"]["proposed_quote"], 1.52)

    def test_missing_supplier_item(self) -> None:
        payload = build_quote_context(self.conn, "UNKNOWN-PART")
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"], "supplier_item_not_found")

    def test_partial_context_when_only_erp_exists(self) -> None:
        payload = build_quote_context(
            self.conn,
            "STM32F103C8T6",
            requested_qty=1200,
            customer_id="cust_1",
            soq_db_path=str(self.soq_db_path),
        )
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["partial"])
        self.assertEqual(payload["supplier_item"]["source_mode"], "erp_only")
        self.assertEqual(payload["erp_context"]["erp_normal_price"], 1.45)
        self.assertEqual(payload["erp_context"]["erp_floor_price"], 1.1)
        self.assertEqual(payload["decision_stub"]["proposed_quote"], 1.45)
        self.assertFalse(payload["decision_stub"]["auto_reply_allowed"])
        self.assertIn("supplier_context_missing", payload["decision_stub"]["handoff_reason"])

    def test_write_pricing_decision(self) -> None:
        payload = build_quote_context(
            self.conn,
            "STM32L412CBU6",
            batch_id="batch_a",
            requested_qty=500,
            customer_id="cust_1",
            soq_db_path=str(self.soq_db_path),
        )
        payload["evidence_json"] = "{}"
        decision_id = write_pricing_decision(self.conn, payload, qq_conversation_id="qq_1", customer_id="cust_1")
        self.assertGreater(decision_id, 0)
        row = self.conn.execute(
            "SELECT normalized_part_number, quote_strategy, auto_reply_allowed, qq_conversation_id FROM pricing_decisions WHERE decision_id=?",
            (decision_id,),
        ).fetchone()
        self.assertEqual(row["normalized_part_number"], "STM32L412CBU6")
        self.assertEqual(row["quote_strategy"], "direct_quote")
        self.assertEqual(row["auto_reply_allowed"], 1)
        self.assertEqual(row["qq_conversation_id"], "qq_1")

    def test_handoff_still_keeps_erp_quote_basis(self) -> None:
        self.conn.execute("UPDATE market_quotes SET match_status='manual_review' WHERE supplier_item_id=1")
        self.conn.commit()
        payload = build_quote_context(
            self.conn,
            "STM32L412CBU6",
            batch_id="batch_a",
            requested_qty=500,
            customer_id="cust_1",
            soq_db_path=str(self.soq_db_path),
        )
        self.assertFalse(payload["decision_stub"]["auto_reply_allowed"])
        self.assertEqual(payload["decision_stub"]["quote_strategy"], "handoff")
        self.assertEqual(payload["decision_stub"]["proposed_quote"], 1.52)
        self.assertIn("market_manual_review_needed", payload["decision_stub"]["handoff_reason"])

    def test_general_inquiry_override_for_1560(self) -> None:
        self.conn.execute("UPDATE market_quotes SET match_status='manual_review' WHERE supplier_item_id=1")
        self.conn.commit()
        payload = build_quote_context(
            self.conn,
            "STM32L412CBU6",
            batch_id="batch_a",
            requested_qty=1560,
            soq_db_path=str(self.soq_db_path),
        )
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["decision_stub"]["auto_reply_allowed"])
        self.assertEqual(payload["decision_stub"]["quote_strategy"], "direct_quote")
        self.assertEqual(payload["decision_stub"]["proposed_quote"], 11.5)
        self.assertEqual(payload["decision_stub"]["pricing_policy_source"], "general_inquiry_override")

    def test_erp_only_override_can_direct_quote(self) -> None:
        payload = build_quote_context(
            self.conn,
            "LM2904YPT",
            requested_qty=120000,
            soq_db_path=str(self.soq_db_path),
        )
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["partial"])
        self.assertTrue(payload["decision_stub"]["auto_reply_allowed"])
        self.assertEqual(payload["decision_stub"]["quote_strategy"], "direct_quote")
        self.assertEqual(payload["decision_stub"]["proposed_quote"], 0.28)
        self.assertEqual(payload["decision_stub"]["pricing_policy_source"], "general_inquiry_override")

    def test_erp_only_without_override_can_direct_quote_from_erp(self) -> None:
        payload = build_quote_context(
            self.conn,
            "STM32G431CBT6",
            requested_qty=3120,
            soq_db_path=str(self.soq_db_path),
        )
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["partial"])
        self.assertEqual(payload["decision_stub"]["quote_strategy"], "direct_quote")
        self.assertEqual(payload["decision_stub"]["proposed_quote"], 11.5044)
        self.assertTrue(payload["decision_stub"]["auto_reply_allowed"])

    def test_handoff_guardrail_blocks_auto_quote(self) -> None:
        self.guardrail_path.write_text(
            "\n".join(
                [
                    "normalized_part_number,requested_qty,override_price,handoff_reason,reply_action,guardrail_action",
                    "LM2904YPT,120000,0.28,erp_requires_price_application,apply_then_handoff_preview,manual_handoff_required",
                ]
            ),
            encoding="utf-8-sig",
        )
        payload = build_quote_context(
            self.conn,
            "LM2904YPT",
            requested_qty=120000,
            soq_db_path=str(self.soq_db_path),
        )
        self.assertTrue(payload["ok"])
        self.assertFalse(payload["decision_stub"]["auto_reply_allowed"])
        self.assertEqual(payload["decision_stub"]["quote_strategy"], "handoff")
        self.assertEqual(payload["decision_stub"]["proposed_quote"], 0.28)
        self.assertIn("manual_handoff_required", payload["decision_stub"]["handoff_reason"])
        self.assertIn("erp_requires_price_application", payload["decision_stub"]["handoff_reason"])


if __name__ == "__main__":
    unittest.main()
