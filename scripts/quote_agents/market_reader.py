import sqlite3
from statistics import median
from typing import Any


def get_market_quotes(conn: sqlite3.Connection, supplier_item_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
          market_quote_id,
          batch_id,
          supplier_item_id,
          source_platform,
          searched_keyword,
          matched_part_number,
          match_confidence,
          price,
          currency,
          package,
          moq,
          stock,
          seller_name,
          region,
          url,
          capture_time,
          match_status,
          notes,
          raw_snapshot_path,
          created_at
        FROM market_quotes
        WHERE supplier_item_id=?
        ORDER BY market_quote_id ASC
        """,
        (supplier_item_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def summarize_market_quotes(rows: list[dict[str, Any]]) -> dict[str, Any]:
    priced = [float(row["price"]) for row in rows if row.get("price") not in (None, "")]
    statuses = {str(row.get("match_status") or "") for row in rows}
    return {
        "quote_count": len(rows),
        "priced_count": len(priced),
        "market_low_price": min(priced) if priced else None,
        "market_median_price": median(priced) if priced else None,
        "all_match_statuses": sorted(s for s in statuses if s),
        "manual_review_needed": any(status in {"manual_review", "multiple_candidates", "blocked", "fetch_error"} for status in statuses),
    }
