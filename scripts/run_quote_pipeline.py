import argparse
import json
import sys
from contextlib import closing
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.qq_reply_preview import connect_db
from scripts.quote_agents.qq_reply_agent import build_reply_preview
from scripts.quote_orchestrator import build_quote_context
from scripts.quote_agents.decision_writer import ensure_pricing_decisions_table, write_pricing_decision


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the full local quote pipeline.")
    parser.add_argument("--db-path", default=r"F:/Jay_ic_tw/sol.db", help="SQLite database path.")
    parser.add_argument("--soq-db-path", default=r"F:/Jay_ic_tw/qq/agent-harness/soq.db", help="QQ SOQ database path.")
    parser.add_argument("--part-number", required=True, help="Part number.")
    parser.add_argument("--requested-qty", type=int, default=0, help="Requested quantity.")
    parser.add_argument("--batch-id", default="", help="Optional batch id.")
    parser.add_argument("--customer-id", default="", help="Optional customer id.")
    parser.add_argument("--qq-conversation-id", default="", help="Optional QQ conversation id.")
    parser.add_argument("--write-decision", action="store_true", help="Persist pricing decision.")
    parser.add_argument("--output-json", default="", help="Optional explicit output json path.")
    return parser.parse_args()


def run_quote_pipeline(
    db_path: str,
    soq_db_path: str,
    part_number: str,
    requested_qty: int = 0,
    batch_id: str = "",
    customer_id: str = "",
    qq_conversation_id: str = "",
    write_decision: bool = False,
) -> dict[str, Any]:
    with closing(connect_db(Path(db_path))) as conn:
        payload = build_quote_context(
            conn,
            normalized_part_number=str(part_number).strip().upper(),
            batch_id=str(batch_id).strip() or None,
            requested_qty=requested_qty,
            customer_id=str(customer_id).strip() or None,
            soq_db_path=str(soq_db_path).strip(),
        )
        if not payload.get("ok"):
            return payload

        payload["evidence_json"] = json.dumps(payload, ensure_ascii=False, indent=2)
        if write_decision:
            ensure_pricing_decisions_table(conn)
            decision_id = write_pricing_decision(
                conn,
                payload,
                qq_conversation_id=str(qq_conversation_id).strip(),
                customer_id=str(customer_id).strip(),
            )
            payload["decision_id"] = decision_id

        reply_preview = build_reply_preview(
            normalized_part_number=payload.get("normalized_part_number", ""),
            requested_qty=payload.get("decision_stub", {}).get("requested_qty"),
            decision=payload.get("decision_stub", {}),
            evidence_partial=bool(payload.get("partial")),
        )

    result = {
        "ok": True,
        "pipeline": "quote_pipeline_v1",
        "part_number": payload.get("normalized_part_number"),
        "partial": bool(payload.get("partial")),
        "decision_id": payload.get("decision_id"),
        "decision_stub": payload.get("decision_stub"),
        "reply_preview": reply_preview,
        "evidence_summary": {
            "batch_id": payload.get("batch_id"),
            "supplier_item_id": (payload.get("supplier_item") or {}).get("supplier_item_id"),
            "market_quote_count": len(payload.get("market_quotes") or []),
            "trader_quote_count": len(payload.get("trader_quotes") or []),
            "erp_found": (payload.get("erp_context") or {}).get("erp_found"),
        },
        "evidence": payload,
    }
    return result


def main() -> int:
    args = parse_args()
    result = run_quote_pipeline(
        db_path=args.db_path,
        soq_db_path=args.soq_db_path,
        part_number=args.part_number,
        requested_qty=args.requested_qty,
        batch_id=args.batch_id,
        customer_id=args.customer_id,
        qq_conversation_id=args.qq_conversation_id,
        write_decision=args.write_decision,
    )
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output_json:
        Path(args.output_json).write_text(text, encoding="utf-8")
        print(f"[output] json={args.output_json}")
    else:
        print(text)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
