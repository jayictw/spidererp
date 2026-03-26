import argparse
import csv
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.quote_agents.decision_writer import ensure_pricing_decisions_table, write_pricing_decision
from scripts.quote_agents.erp_reader import get_erp_context
from scripts.quote_agents.market_reader import get_market_quotes, summarize_market_quotes
from scripts.quote_agents.supplier_reader import get_latest_supplier_item
from scripts.quote_agents.trader_quote_collector import get_trader_quotes, summarize_trader_quotes

FIRST_ROUND_OVERRIDE_PATH = Path(__file__).resolve().parents[1] / "data" / "quote_first_round_overrides.csv"
HANDOFF_GUARDRAIL_PATH = Path(__file__).resolve().parents[1] / "data" / "quote_first_round_handoff_guardrails.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read supplier + market evidence and build a quote input view.")
    parser.add_argument("--db-path", default=r"F:/Jay_ic_tw/sol.db", help="SQLite database path.")
    parser.add_argument("--part-number", required=True, help="Normalized part number to orchestrate.")
    parser.add_argument("--batch-id", default="", help="Optional batch id filter.")
    parser.add_argument("--requested-qty", type=int, default=0, help="Optional customer requested quantity.")
    parser.add_argument("--qq-conversation-id", default="", help="Optional QQ conversation id for decision persistence.")
    parser.add_argument("--customer-id", default="", help="Optional customer id for decision persistence.")
    parser.add_argument("--soq-db-path", default=r"F:/Jay_ic_tw/qq/agent-harness/soq.db", help="QQ SOQ database path for ERP/history adapter.")
    parser.add_argument("--write-decision", action="store_true", help="Persist pricing decision into pricing_decisions table.")
    parser.add_argument("--output-json", default="", help="Optional explicit JSON output path.")
    return parser.parse_args()


def connect_db(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def compute_decision_stub(
    supplier_item: dict[str, Any],
    market_summary: dict[str, Any],
    trader_summary: dict[str, Any],
    erp_context: dict[str, Any],
    requested_qty: int,
) -> dict[str, Any]:
    reasons: list[str] = []
    auto_reply_allowed = True
    confidence = 0.88
    effective_qty = requested_qty or supplier_item.get("supplier_stock_qty")
    erp_floor_price = erp_context.get("erp_floor_price")
    erp_normal_price = erp_context.get("erp_normal_price")
    min_auto_accept_price = erp_context.get("min_auto_accept_price")
    allow_floor_strategy = False
    trader_reference_price = trader_summary.get("trader_reference_price")
    general_override = get_first_round_override(supplier_item.get("normalized_part_number", ""), effective_qty)
    handoff_guardrail = get_handoff_guardrail(supplier_item.get("normalized_part_number", ""), effective_qty)

    def add_reason(reason: str) -> None:
        if reason and reason not in reasons:
            reasons.append(reason)

    if handoff_guardrail is not None:
        add_reason("manual_handoff_required")
        add_reason(str(handoff_guardrail.get("handoff_reason") or "").strip())
        auto_reply_allowed = False
        confidence -= 0.2

    erp_fast_reply_allowed = (
        supplier_item.get("source_mode") == "erp_only"
        and general_override is None
        and handoff_guardrail is None
        and bool(erp_context.get("erp_found"))
        and bool(erp_context.get("erp_inventory_found"))
    )

    if supplier_item.get("source_mode") == "erp_only" and general_override is None and not erp_fast_reply_allowed:
        add_reason("supplier_context_missing")
        auto_reply_allowed = False
        confidence -= 0.18
    elif erp_fast_reply_allowed:
        confidence -= 0.08
    elif supplier_item.get("source_mode") == "erp_only":
        confidence -= 0.08
    elif supplier_item.get("parse_status") not in {"parsed", "raw_only"}:
        add_reason(f"parse_status={supplier_item.get('parse_status')}")
        auto_reply_allowed = False
        confidence -= 0.2
    if supplier_item.get("parse_confidence") not in (None, "") and float(supplier_item.get("parse_confidence") or 0) < 0.35:
        add_reason("supplier_parse_low_confidence")
        auto_reply_allowed = False
        confidence -= 0.1
    if market_summary.get("manual_review_needed") and general_override is None:
        add_reason("market_manual_review_needed")
        auto_reply_allowed = False
        confidence -= 0.25
    if not erp_context.get("erp_found") and general_override is None:
        add_reason("erp_missing")
        auto_reply_allowed = False
        confidence -= 0.25
    if erp_context.get("erp_inventory_supply_status") and "申请价格" in str(erp_context.get("erp_inventory_supply_status")):
        add_reason("erp_requires_price_application")
        auto_reply_allowed = False
        confidence -= 0.15
    if erp_context.get("erp_inventory_supply_status") and "价格倒挂" in str(erp_context.get("erp_inventory_supply_status")):
        add_reason("erp_price_inversion")
        auto_reply_allowed = False
        confidence -= 0.15

    quote_strategy = "handoff"
    proposed_quote = None
    if auto_reply_allowed:
        if general_override is not None:
            proposed_quote = general_override.get("first_quote_price")
        else:
            proposed_quote = erp_normal_price or erp_floor_price or trader_reference_price or market_summary.get("market_low_price")
        if proposed_quote is not None and min_auto_accept_price is not None:
            proposed_quote = max(float(proposed_quote), float(min_auto_accept_price))
        if proposed_quote is not None and erp_floor_price is not None and not allow_floor_strategy:
            proposed_quote = max(float(proposed_quote), float(erp_floor_price))
        if proposed_quote is not None:
            quote_strategy = "direct_quote"
            if allow_floor_strategy and erp_floor_price is not None and float(proposed_quote) <= float(erp_floor_price):
                quote_strategy = "floor_strategy"
        elif market_summary.get("market_low_price") is not None and erp_floor_price is None and erp_normal_price is None:
            proposed_quote = market_summary.get("market_low_price")
            quote_strategy = "market_reference_only"
        if proposed_quote is None:
            auto_reply_allowed = False
            add_reason("no_quote_basis")
    else:
        if general_override is not None:
            proposed_quote = general_override.get("first_quote_price")
        elif erp_normal_price is not None:
            proposed_quote = erp_normal_price
        elif erp_floor_price is not None:
            proposed_quote = erp_floor_price

    return {
        "requested_qty": effective_qty,
        "proposed_quote": round(float(proposed_quote), 4) if proposed_quote is not None else None,
        "quote_strategy": quote_strategy,
        "confidence": round(max(0.0, min(1.0, confidence)), 2),
        "auto_reply_allowed": auto_reply_allowed,
        "handoff_reason": " | ".join(reasons),
        "pricing_policy_source": "general_inquiry_override" if general_override is not None else "erp_market_default",
    }


def get_first_round_override(normalized_part_number: str, requested_qty: Any) -> dict[str, Any] | None:
    if not normalized_part_number or requested_qty in (None, "", 0):
        return None
    if not FIRST_ROUND_OVERRIDE_PATH.exists():
        return None
    try:
        qty_value = float(requested_qty)
    except (TypeError, ValueError):
        return None

    with FIRST_ROUND_OVERRIDE_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            part = str(row.get("normalized_part_number") or "").strip().upper()
            if part != str(normalized_part_number).strip().upper():
                continue
            qty_min_raw = str(row.get("qty_min") or "").strip()
            qty_max_raw = str(row.get("qty_max") or "").strip()
            qty_min = float(qty_min_raw) if qty_min_raw else None
            qty_max = float(qty_max_raw) if qty_max_raw else None
            if qty_min is not None and qty_value < qty_min:
                continue
            if qty_max is not None and qty_value > qty_max:
                continue
            price_raw = str(row.get("first_quote_price") or "").strip()
            if not price_raw:
                continue
            return {
                "normalized_part_number": part,
                "inquiry_type": str(row.get("inquiry_type") or "").strip() or "general",
                "first_quote_price": float(price_raw),
                "currency": str(row.get("currency") or "").strip() or "CNY",
                "note": str(row.get("note") or "").strip(),
            }
    return None


def get_handoff_guardrail(normalized_part_number: str, requested_qty: Any) -> dict[str, Any] | None:
    if not normalized_part_number or requested_qty in (None, "", 0):
        return None
    if not HANDOFF_GUARDRAIL_PATH.exists():
        return None
    try:
        qty_text = str(int(float(requested_qty)))
    except (TypeError, ValueError):
        return None

    with HANDOFF_GUARDRAIL_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            part = str(row.get("normalized_part_number") or "").strip().upper()
            if part != str(normalized_part_number).strip().upper():
                continue
            requested_qty_row = str(row.get("requested_qty") or "").strip()
            if requested_qty_row and requested_qty_row != qty_text:
                continue
            return {
                "normalized_part_number": part,
                "requested_qty": requested_qty_row,
                "handoff_reason": str(row.get("handoff_reason") or "").strip(),
                "reply_action": str(row.get("reply_action") or "").strip(),
                "guardrail_action": str(row.get("guardrail_action") or "").strip(),
            }
    return None


def build_quote_context(
    conn: sqlite3.Connection,
    normalized_part_number: str,
    batch_id: str | None = None,
    requested_qty: int = 0,
    customer_id: str | None = None,
    soq_db_path: str = r"F:/Jay_ic_tw/qq/agent-harness/soq.db",
) -> dict[str, Any]:
    supplier_item = get_latest_supplier_item(conn, normalized_part_number, batch_id=batch_id)
    erp_context = get_erp_context(conn, normalized_part_number, customer_id=customer_id, soq_db_path=soq_db_path)
    if supplier_item is None:
        if not erp_context.get("erp_found"):
            return {
                "ok": False,
                "normalized_part_number": normalized_part_number,
                "error": "supplier_item_not_found",
            }
        supplier_item = {
            "supplier_item_id": None,
            "batch_id": batch_id or "",
            "supplier_name": "",
            "supplier_part_number": normalized_part_number,
            "normalized_part_number": normalized_part_number,
            "normalization_basis": "erp_only",
            "supplier_stock_raw": "",
            "supplier_stock_qty": None,
            "supplier_stock_year": "",
            "supplier_stock_lot": "",
            "supplier_package": "",
            "supplier_lead_time": "",
            "supplier_stock_note": "",
            "parse_confidence": None,
            "parse_status": "not_provided",
            "created_at": "",
            "source_mode": "erp_only",
        }
        market_quotes: list[dict[str, Any]] = []
        market_summary = {
            "quote_count": 0,
            "priced_count": 0,
            "market_low_price": None,
            "market_median_price": None,
            "all_match_statuses": [],
            "manual_review_needed": False,
        }
        trader_quotes = get_trader_quotes(conn, normalized_part_number)
        trader_summary = summarize_trader_quotes(trader_quotes)
        decision = compute_decision_stub(supplier_item, market_summary, trader_summary, erp_context, requested_qty)
        return {
            "ok": True,
            "partial": True,
            "normalized_part_number": normalized_part_number,
            "batch_id": supplier_item.get("batch_id"),
            "supplier_item": supplier_item,
            "market_quotes": market_quotes,
            "market_summary": market_summary,
            "trader_quotes": trader_quotes,
            "trader_summary": trader_summary,
            "erp_context": erp_context,
            "decision_stub": decision,
        }

    market_quotes = get_market_quotes(conn, int(supplier_item["supplier_item_id"]))
    market_summary = summarize_market_quotes(market_quotes)
    trader_quotes = get_trader_quotes(conn, normalized_part_number)
    trader_summary = summarize_trader_quotes(trader_quotes)
    decision = compute_decision_stub(supplier_item, market_summary, trader_summary, erp_context, requested_qty)

    return {
        "ok": True,
        "partial": False,
        "normalized_part_number": normalized_part_number,
        "batch_id": supplier_item.get("batch_id"),
        "supplier_item": supplier_item,
        "market_quotes": market_quotes,
        "market_summary": market_summary,
        "trader_quotes": trader_quotes,
        "trader_summary": trader_summary,
        "erp_context": erp_context,
        "decision_stub": decision,
    }


def main() -> int:
    args = parse_args()
    db_path = Path(args.db_path)
    with connect_db(db_path) as conn:
        if args.write_decision:
            ensure_pricing_decisions_table(conn)
        payload = build_quote_context(
            conn,
            normalized_part_number=str(args.part_number).strip().upper(),
            batch_id=str(args.batch_id).strip() or None,
            requested_qty=args.requested_qty,
            customer_id=str(args.customer_id).strip() or None,
            soq_db_path=str(args.soq_db_path).strip(),
        )
        if payload.get("ok"):
            payload["evidence_json"] = json.dumps(payload, ensure_ascii=False, indent=2)
            if args.write_decision:
                decision_id = write_pricing_decision(
                    conn,
                    payload,
                    qq_conversation_id=str(args.qq_conversation_id).strip(),
                    customer_id=str(args.customer_id).strip(),
                )
                payload["decision_id"] = decision_id
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output_json:
        Path(args.output_json).write_text(text, encoding="utf-8")
        print(f"[output] json={args.output_json}")
    else:
        print(text)
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
