import argparse
import json
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.quote_agents.task_queue import (
    enqueue_quote_task,
    ensure_quote_tasks_table,
    fetch_next_task_by_stage,
    get_task_by_id,
    mark_task_completed,
    mark_task_failed,
    mark_task_running,
    mark_task_stage,
)
from scripts.quote_agents.decision_writer import ensure_pricing_decisions_table, write_pricing_decision
from scripts.quote_agents.qq_reply_agent import build_reply_preview
from scripts.quote_orchestrator import build_quote_context


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Queue and dispatch quote tasks.")
    parser.add_argument("--db-path", default=r"F:/Jay_ic_tw/sol.db", help="SQLite database path.")
    parser.add_argument("--soq-db-path", default=r"F:/Jay_ic_tw/qq/agent-harness/soq.db", help="QQ SOQ database path.")
    parser.add_argument("--enqueue", action="store_true", help="Enqueue a new quote task.")
    parser.add_argument("--run-next", action="store_true", help="Run the next queued quote task.")
    parser.add_argument("--run-stage", default="", help="Run the next task for a specific stage.")
    parser.add_argument("--source", default="manual", help="Task source label.")
    parser.add_argument("--part-number", default="", help="Part number for enqueue.")
    parser.add_argument("--requested-qty", type=int, default=0, help="Requested quantity.")
    parser.add_argument("--batch-id", default="", help="Optional batch id.")
    parser.add_argument("--customer-id", default="", help="Optional customer id.")
    parser.add_argument("--qq-conversation-id", default="", help="Optional QQ conversation id.")
    parser.add_argument("--task-id", type=int, default=0, help="Optional specific task id for stage execution.")
    parser.add_argument("--assigned-worker", default="", help="Worker label for stage execution.")
    return parser.parse_args()


def connect_db(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def enqueue_mode(args: argparse.Namespace) -> dict:
    if not str(args.part_number).strip():
        return {"ok": False, "error": "part_number_required_for_enqueue"}
    with closing(connect_db(Path(args.db_path))) as conn:
        ensure_quote_tasks_table(conn)
        task_id = enqueue_quote_task(
            conn,
            source=str(args.source).strip() or "manual",
            part_number=str(args.part_number).strip().upper(),
            requested_qty=args.requested_qty,
            batch_id=str(args.batch_id).strip(),
            customer_id=str(args.customer_id).strip(),
            qq_conversation_id=str(args.qq_conversation_id).strip(),
        )
    return {"ok": True, "mode": "enqueue", "task_id": task_id}


def _default_worker_for_stage(stage: str) -> str:
    return {
        "queued": "supplier_market_worker",
        "evidence_ready": "pricing_worker",
        "decision_ready": "qq_preview_worker",
    }.get(stage, "quote_orchestrator")


def _run_stage(conn: sqlite3.Connection, task: dict, stage: str, soq_db_path: str) -> dict:
    task_id = int(task["task_id"])
    part_number = task["part_number"]
    requested_qty = int(task["requested_qty"] or 0)
    batch_id = str(task.get("batch_id") or "")
    customer_id = str(task.get("customer_id") or "")
    qq_conversation_id = str(task.get("qq_conversation_id") or "")

    if stage == "queued":
        payload = build_quote_context(
            conn,
            normalized_part_number=part_number,
            batch_id=batch_id or None,
            requested_qty=requested_qty,
            customer_id=customer_id or None,
            soq_db_path=soq_db_path,
        )
        if not payload.get("ok"):
            return {"ok": False, "error": payload.get("error") or "evidence_build_failed"}
        payload["evidence_json"] = json.dumps(payload, ensure_ascii=False, indent=2)
        mark_task_stage(conn, task_id, next_stage="evidence_ready", status="queued", evidence=payload)
        return {"ok": True, "task_id": task_id, "part_number": part_number, "stage": "evidence_ready"}

    if stage == "evidence_ready":
        raw_evidence = task.get("evidence_json")
        if not raw_evidence:
            return {"ok": False, "error": "missing_evidence_json"}
        payload = json.loads(raw_evidence)
        ensure_pricing_decisions_table(conn)
        decision_id = write_pricing_decision(
            conn,
            payload,
            qq_conversation_id=qq_conversation_id,
            customer_id=customer_id,
        )
        payload["decision_id"] = decision_id
        mark_task_stage(conn, task_id, next_stage="decision_ready", status="queued", evidence=payload, decision_id=decision_id)
        return {"ok": True, "task_id": task_id, "part_number": part_number, "stage": "decision_ready", "decision_id": decision_id}

    if stage == "decision_ready":
        raw_evidence = task.get("evidence_json")
        if not raw_evidence:
            return {"ok": False, "error": "missing_evidence_json"}
        payload = json.loads(raw_evidence)
        reply_preview = build_reply_preview(
            normalized_part_number=payload.get("normalized_part_number", ""),
            requested_qty=(payload.get("decision_stub") or {}).get("requested_qty"),
            decision=payload.get("decision_stub") or {},
            evidence_partial=bool(payload.get("partial")),
        )
        result = {
            "ok": True,
            "pipeline": "quote_pipeline_task_v2",
            "part_number": payload.get("normalized_part_number"),
            "partial": bool(payload.get("partial")),
            "decision_id": payload.get("decision_id") or task.get("decision_id"),
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
        mark_task_completed(conn, task_id, result)
        return {"ok": True, "task_id": task_id, "part_number": part_number, "stage": "completed", "decision_id": result.get("decision_id")}

    return {"ok": False, "error": f"unsupported_stage={stage}"}


def run_stage_mode(args: argparse.Namespace, stage: str) -> dict:
    with closing(connect_db(Path(args.db_path))) as conn:
        ensure_quote_tasks_table(conn)
        if args.task_id:
            task = get_task_by_id(conn, int(args.task_id))
            if task is not None and str(task.get("stage") or "") != stage:
                return {
                    "ok": False,
                    "mode": "run_stage",
                    "stage": stage,
                    "task_id": int(args.task_id),
                    "error": f"task_stage_mismatch:{task.get('stage')}",
                }
            if task is not None and str(task.get("status") or "") not in {"queued", "running"}:
                return {
                    "ok": False,
                    "mode": "run_stage",
                    "stage": stage,
                    "task_id": int(args.task_id),
                    "error": f"task_not_runnable:{task.get('status')}",
                }
        else:
            task = fetch_next_task_by_stage(conn, stage)
        if task is None:
            return {"ok": True, "mode": "run_stage", "stage": stage, "status": "no_task"}
        worker = str(args.assigned_worker).strip() or _default_worker_for_stage(stage)
        mark_task_running(conn, int(task["task_id"]), worker, stage=stage)
        result = _run_stage(conn, task, stage=stage, soq_db_path=args.soq_db_path)
        if result.get("ok"):
            return {
                "ok": True,
                "mode": "run_stage",
                "worker": worker,
                "task_id": int(task["task_id"]),
                "part_number": task["part_number"],
                "next_stage": result.get("stage"),
                "decision_id": result.get("decision_id"),
            }
        mark_task_failed(conn, int(task["task_id"]), str(result.get("error") or "task_stage_failed"), result=result)
        return {
            "ok": False,
            "mode": "run_stage",
            "worker": worker,
            "task_id": int(task["task_id"]),
            "stage": stage,
            "error": result.get("error") or "task_stage_failed",
        }


def run_next_mode(args: argparse.Namespace) -> dict:
    for stage in ("queued", "evidence_ready", "decision_ready"):
        result = run_stage_mode(args, stage)
        if result.get("status") != "no_task":
            result["mode"] = "run_next"
            return result
    return {"ok": True, "mode": "run_next", "status": "no_queued_task"}


def main() -> int:
    args = parse_args()
    mode_count = sum(bool(x) for x in (args.enqueue, args.run_next, bool(str(args.run_stage).strip())))
    if mode_count != 1:
        result = {"ok": False, "error": "choose_exactly_one_mode"}
    elif args.enqueue:
        result = enqueue_mode(args)
    elif str(args.run_stage).strip():
        result = run_stage_mode(args, str(args.run_stage).strip())
    else:
        result = run_next_mode(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
