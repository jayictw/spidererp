import sqlite3
import tempfile
from pathlib import Path

from scripts.quote_agents.decision_writer import ensure_pricing_decisions_table
from scripts.quote_agents.task_queue import ensure_quote_tasks_table


class QuoteTestEnv:
    def __init__(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "sol.db"
        self.soq_db_path = Path(self.tmpdir.name) / "soq.db"

    def cleanup(self) -> None:
        self.tmpdir.cleanup()


def create_quote_test_env() -> QuoteTestEnv:
    env = QuoteTestEnv()

    conn = sqlite3.connect(env.db_path)
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
    ensure_pricing_decisions_table(conn)
    ensure_quote_tasks_table(conn)

    conn.execute(
        """
        INSERT INTO supplier_items(
          batch_id, supplier_name, supplier_part_number, normalized_part_number,
          normalization_basis, supplier_stock_raw, supplier_stock_qty, parse_confidence,
          parse_status, created_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?)
        """,
        (
            "batch_accept_001",
            "VendorA",
            "STM32L412CBU6",
            "STM32L412CBU6",
            "exact_input",
            "库存数量=1000; DC23+; LQFP48",
            1000,
            0.92,
            "parsed",
            "2026-03-15T00:00:00",
        ),
    )
    supplier_item_id = conn.execute("SELECT supplier_item_id FROM supplier_items").fetchone()[0]
    conn.execute(
        """
        INSERT INTO market_quotes(
          batch_id, supplier_item_id, source_platform, searched_keyword, matched_part_number,
          match_confidence, price, currency, package, moq, stock, seller_name, region,
          url, capture_time, match_status, notes, raw_snapshot_path, created_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            "batch_accept_001",
            supplier_item_id,
            "so.szlcsc.com",
            "STM32L412CBU6",
            "STM32L412CBU6",
            0.98,
            1.23,
            "USD",
            "LQFP48",
            1,
            5000,
            "SZLCSC",
            "CN",
            "https://so.szlcsc.com/example",
            "2026-03-15T00:00:00",
            "matched_exact",
            "",
            "snapshot_001.txt",
            "2026-03-15T00:00:00",
        ),
    )
    conn.execute(
        """
        INSERT INTO trader_quotes(
          import_batch_id, normalized_part_number, trader_name, quoted_price, currency,
          quoted_qty, source, source_url, note, captured_at, created_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            "trader_accept_001",
            "STM32F103C8T6",
            "TraderB",
            1.35,
            "USD",
            500,
            "manual_csv",
            "",
            "",
            "2026-03-15T15:13:46",
            "2026-03-15T15:13:46",
        ),
    )
    conn.execute(
        """
        INSERT INTO trader_quotes(
          import_batch_id, normalized_part_number, trader_name, quoted_price, currency,
          quoted_qty, source, source_url, note, captured_at, created_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            "trader_accept_001",
            "STM32F103C8T6",
            "TraderA",
            1.40,
            "USD",
            1000,
            "manual_csv",
            "",
            "",
            "2026-03-15T15:13:46",
            "2026-03-15T15:13:46",
        ),
    )
    conn.commit()
    conn.close()

    soq = sqlite3.connect(env.soq_db_path)
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
        ("STM32L412CBU6", 1.52, 1.18, 1.25, "stock"),
    )
    soq.execute(
        "INSERT INTO products(model, normal_price, floor_price, min_auto_accept_price, default_supply_type, active) VALUES(?,?,?,?,?,1)",
        ("STM32F103C8T6", 1.45, 1.10, 1.20, "stock"),
    )
    soq.execute(
        "INSERT INTO customers(customer_id, qq_id, customer_name, level, is_old_customer, allow_floor_strategy, notes) VALUES(?,?,?,?,?,?,?)",
        ("cust_demo_001", "qq_demo_001", "Demo Customer", "A", 1, 0, "acceptance fixture"),
    )
    soq.execute(
        """
        INSERT INTO soq_logs(
          conversation_id, customer_id, raw_message, parsed_model, parsed_qty,
          action_taken, quoted_price, handoff_reason, confidence, agent_reply, created_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            "preview-conv-audit",
            "cust_demo_001",
            "old quote",
            "STM32F103C8T6",
            1200,
            "apply_then_handoff_preview",
            1.45,
            "supplier_context_missing",
            0.7,
            "{}",
            "2026-03-15T07:38:23",
        ),
    )
    soq.commit()
    soq.close()

    return env
