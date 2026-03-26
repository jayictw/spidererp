import sqlite3
from typing import Any


def get_latest_supplier_item(
    conn: sqlite3.Connection,
    normalized_part_number: str,
    batch_id: str | None = None,
) -> dict[str, Any] | None:
    sql = """
    SELECT
      supplier_item_id,
      batch_id,
      supplier_name,
      supplier_part_number,
      normalized_part_number,
      normalization_basis,
      supplier_stock_raw,
      supplier_stock_qty,
      supplier_stock_year,
      supplier_stock_lot,
      supplier_package,
      supplier_lead_time,
      supplier_stock_note,
      parse_confidence,
      parse_status,
      created_at
    FROM supplier_items
    WHERE normalized_part_number=?
    """
    params: list[Any] = [normalized_part_number]
    if batch_id:
        sql += " AND batch_id=?"
        params.append(batch_id)
    sql += " ORDER BY supplier_item_id DESC LIMIT 1"
    row = conn.execute(sql, tuple(params)).fetchone()
    return dict(row) if row else None
