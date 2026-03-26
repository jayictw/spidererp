import argparse
import json
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.quote_agents.decision_writer import ensure_pricing_decisions_table


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Show a pricing decision detail view.")
    parser.add_argument("--db-path", default=r"F:/Jay_ic_tw/sol.db", help="SQLite database path.")
    parser.add_argument("--decision-id", type=int, default=0, help="Specific decision id.")
    parser.add_argument("--part-number", default="", help="Optional normalized part number lookup.")
    return parser.parse_args()


def _connect_db(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def build_pricing_decision_view(conn: sqlite3.Connection, decision_id: int = 0, part_number: str = "") -> dict:
    ensure_pricing_decisions_table(conn)
    if decision_id > 0:
        row = conn.execute("SELECT * FROM pricing_decisions WHERE decision_id=?", (decision_id,)).fetchone()
    elif str(part_number).strip():
        row = conn.execute(
            """
            SELECT * FROM pricing_decisions
            WHERE normalized_part_number=?
            ORDER BY decision_id DESC
            LIMIT 1
            """,
            (str(part_number).strip().upper(),),
        ).fetchone()
    else:
        return {"ok": False, "error": "decision_id_or_part_number_required"}

    if row is None:
        return {"ok": False, "error": "pricing_decision_not_found"}

    decision = dict(row)
    evidence = {}
    raw_evidence = decision.get("evidence_json")
    if raw_evidence:
        try:
            evidence = json.loads(raw_evidence)
        except json.JSONDecodeError:
            evidence = {"raw_evidence_invalid": True}

    return {
        "ok": True,
        "decision": decision,
        "summary": {
            "decision_id": decision.get("decision_id"),
            "normalized_part_number": decision.get("normalized_part_number"),
            "requested_qty": decision.get("requested_qty"),
            "proposed_quote": decision.get("proposed_quote"),
            "quote_strategy": decision.get("quote_strategy"),
            "auto_reply_allowed": bool(decision.get("auto_reply_allowed")),
            "handoff_reason": decision.get("handoff_reason"),
            "customer_id": decision.get("customer_id"),
        },
        "evidence_summary": {
            "supplier_item_id": (evidence.get("supplier_item") or {}).get("supplier_item_id") if isinstance(evidence, dict) else None,
            "market_quote_count": len((evidence.get("market_quotes") or [])) if isinstance(evidence, dict) else 0,
            "trader_quote_count": len((evidence.get("trader_quotes") or [])) if isinstance(evidence, dict) else 0,
            "erp_found": (evidence.get("erp_context") or {}).get("erp_found") if isinstance(evidence, dict) else None,
        },
    }


def main() -> int:
    args = parse_args()
    with closing(_connect_db(Path(args.db_path))) as conn:
        result = build_pricing_decision_view(conn, decision_id=args.decision_id, part_number=args.part_number)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
