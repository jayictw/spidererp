import sqlite3
from datetime import datetime
from typing import Any


def ensure_pricing_decisions_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS pricing_decisions (
          decision_id INTEGER PRIMARY KEY AUTOINCREMENT,
          qq_conversation_id TEXT,
          customer_id TEXT,
          supplier_item_id INTEGER,
          batch_id TEXT,
          normalized_part_number TEXT NOT NULL,
          requested_qty REAL,
          erp_floor_price REAL,
          erp_normal_price REAL,
          last_deal_price REAL,
          market_low_price REAL,
          market_median_price REAL,
          trader_reference_price REAL,
          proposed_quote REAL,
          quote_strategy TEXT,
          confidence REAL,
          auto_reply_allowed INTEGER NOT NULL DEFAULT 0,
          handoff_reason TEXT,
          evidence_json TEXT,
          created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()


def write_pricing_decision(
    conn: sqlite3.Connection,
    payload: dict[str, Any],
    qq_conversation_id: str = "",
    customer_id: str = "",
) -> int:
    ensure_pricing_decisions_table(conn)
    supplier_item = payload.get("supplier_item") or {}
    market_summary = payload.get("market_summary") or {}
    erp_context = payload.get("erp_context") or {}
    decision_stub = payload.get("decision_stub") or {}
    created_at = datetime.now().isoformat(timespec="seconds")
    cur = conn.execute(
        """
        INSERT INTO pricing_decisions(
          qq_conversation_id, customer_id, supplier_item_id, batch_id, normalized_part_number,
          requested_qty, erp_floor_price, erp_normal_price, last_deal_price,
          market_low_price, market_median_price, trader_reference_price, proposed_quote,
          quote_strategy, confidence, auto_reply_allowed, handoff_reason, evidence_json, created_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            qq_conversation_id or None,
            customer_id or None,
            supplier_item.get("supplier_item_id"),
            payload.get("batch_id"),
            payload.get("normalized_part_number"),
            decision_stub.get("requested_qty"),
            erp_context.get("erp_floor_price"),
            erp_context.get("erp_normal_price"),
            erp_context.get("last_deal_price"),
            market_summary.get("market_low_price"),
            market_summary.get("market_median_price"),
            None,
            decision_stub.get("proposed_quote"),
            decision_stub.get("quote_strategy"),
            decision_stub.get("confidence"),
            1 if decision_stub.get("auto_reply_allowed") else 0,
            decision_stub.get("handoff_reason"),
            payload.get("evidence_json"),
            created_at,
        ),
    )
    conn.commit()
    return int(cur.lastrowid)
