import csv
import sqlite3
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Any


def ensure_trader_quotes_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS trader_quotes (
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
        )
        """
    )
    conn.commit()


def import_trader_quotes_csv(conn: sqlite3.Connection, csv_path: Path) -> dict[str, Any]:
    ensure_trader_quotes_table(conn)
    batch_id = datetime.now().strftime("trader_import_%Y%m%d_%H%M%S")
    created_at = datetime.now().isoformat(timespec="seconds")
    inserted = 0
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            model = str(row.get("normalized_part_number") or row.get("model") or "").strip().upper()
            if not model:
                continue
            quoted_price = row.get("quoted_price") or row.get("price") or ""
            if quoted_price in ("", None):
                continue
            conn.execute(
                """
                INSERT INTO trader_quotes(
                  import_batch_id, normalized_part_number, trader_name, quoted_price, currency,
                  quoted_qty, source, source_url, note, captured_at, created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    batch_id,
                    model,
                    row.get("trader_name") or row.get("seller_name") or "",
                    float(quoted_price),
                    row.get("currency") or "",
                    float(row.get("quoted_qty")) if row.get("quoted_qty") not in ("", None) else None,
                    row.get("source") or "manual_csv",
                    row.get("source_url") or "",
                    row.get("note") or "",
                    row.get("captured_at") or created_at,
                    created_at,
                ),
            )
            inserted += 1
    conn.commit()
    return {"ok": True, "batch_id": batch_id, "inserted": inserted}


def get_trader_quotes(conn: sqlite3.Connection, normalized_part_number: str) -> list[dict[str, Any]]:
    if conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trader_quotes'").fetchone() is None:
        return []
    rows = conn.execute(
        """
        SELECT
          trader_quote_id,
          import_batch_id,
          normalized_part_number,
          trader_name,
          quoted_price,
          currency,
          quoted_qty,
          source,
          source_url,
          note,
          captured_at,
          created_at
        FROM trader_quotes
        WHERE normalized_part_number=?
        ORDER BY trader_quote_id DESC
        """,
        (normalized_part_number,),
    ).fetchall()
    return [dict(row) for row in rows]


def summarize_trader_quotes(rows: list[dict[str, Any]]) -> dict[str, Any]:
    prices = [float(row["quoted_price"]) for row in rows if row.get("quoted_price") not in (None, "")]
    return {
        "quote_count": len(rows),
        "trader_reference_price": min(prices) if prices else None,
        "trader_median_price": median(prices) if prices else None,
        "latest_trader_name": rows[0].get("trader_name") if rows else "",
    }
