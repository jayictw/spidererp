import sqlite3
from typing import Any


CLARIFY_REPLY = "请提供完整型号和数量，我这边先帮您确认。"
APPLY_REPLY = "这个价格需要向公司申请，请稍候，我们尽快回复您。"


def get_latest_pricing_decision(conn: sqlite3.Connection, decision_id: int | None = None, normalized_part_number: str = "") -> dict[str, Any] | None:
    if decision_id is not None:
        row = conn.execute(
            "SELECT * FROM pricing_decisions WHERE decision_id=?",
            (decision_id,),
        ).fetchone()
        return dict(row) if row else None
    if normalized_part_number:
        row = conn.execute(
            """
            SELECT * FROM pricing_decisions
            WHERE normalized_part_number=?
            ORDER BY decision_id DESC
            LIMIT 1
            """,
            (normalized_part_number,),
        ).fetchone()
        return dict(row) if row else None
    return None


def build_reply_preview(
    normalized_part_number: str,
    requested_qty: Any,
    decision: dict[str, Any],
    evidence_partial: bool = False,
) -> dict[str, Any]:
    proposed_quote = decision.get("proposed_quote")
    auto_reply_allowed = bool(decision.get("auto_reply_allowed"))
    handoff_reason = str(decision.get("handoff_reason") or "").strip()
    quote_strategy = str(decision.get("quote_strategy") or "handoff")

    if not normalized_part_number or not requested_qty:
        return {
            "ok": True,
            "action": "clarify",
            "reply": CLARIFY_REPLY,
            "reason": "missing_model_or_qty",
        }

    if auto_reply_allowed and proposed_quote is not None:
        reply = f"{normalized_part_number} 数量 {requested_qty}，当前可给单价 {float(proposed_quote):.4f}。如有目标价可告知，我帮您确认。"
        return {
            "ok": True,
            "action": "auto_quote_preview",
            "reply": reply,
            "quoted_price": float(proposed_quote),
            "quote_strategy": quote_strategy,
        }

    if proposed_quote is not None:
        return {
            "ok": True,
            "action": "apply_then_handoff_preview",
            "reply": APPLY_REPLY,
            "quoted_price": float(proposed_quote),
            "quote_strategy": quote_strategy,
            "reason": handoff_reason or ("partial_evidence" if evidence_partial else "manual_review_required"),
        }

    return {
        "ok": True,
        "action": "handoff_no_reply",
        "reply": "",
        "quote_strategy": quote_strategy,
        "reason": handoff_reason or ("partial_evidence" if evidence_partial else "no_quote_basis"),
    }
