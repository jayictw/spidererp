import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.qq_reply_preview import connect_db
from scripts.quote_agents.qq_reply_agent import build_reply_preview, get_latest_pricing_decision
from scripts.quote_orchestrator import build_quote_context


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Guarded QQ first-round pricing agent.")
    parser.add_argument("--db-path", default=r"F:/Jay_ic_tw/sol.db", help="SQLite database path.")
    parser.add_argument("--soq-db-path", default=r"F:/Jay_ic_tw/qq/agent-harness/soq.db", help="QQ SOQ database path.")
    parser.add_argument("--part-number", required=True, help="Part number.")
    parser.add_argument("--requested-qty", type=int, default=0, help="Requested quantity.")
    parser.add_argument("--batch-id", default="", help="Optional batch id.")
    parser.add_argument("--customer-id", default="", help="Optional customer id.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    with connect_db(Path(args.db_path)) as conn:
        decision = get_latest_pricing_decision(conn, normalized_part_number=str(args.part_number).strip().upper())
        evidence_partial = False
        if decision is None:
            evidence = build_quote_context(
                conn,
                normalized_part_number=str(args.part_number).strip().upper(),
                batch_id=str(args.batch_id).strip() or None,
                requested_qty=args.requested_qty,
                customer_id=str(args.customer_id).strip() or None,
                soq_db_path=str(args.soq_db_path).strip(),
            )
            if not evidence.get("ok"):
                print(json.dumps(evidence, ensure_ascii=False, indent=2))
                return 1
            decision = evidence.get("decision_stub", {})
            evidence_partial = bool(evidence.get("partial"))
        payload = build_reply_preview(
            normalized_part_number=str(args.part_number).strip().upper(),
            requested_qty=args.requested_qty or decision.get("requested_qty"),
            decision=decision,
            evidence_partial=evidence_partial,
        )
        payload["worker"] = "qq_first_round_agent"
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
