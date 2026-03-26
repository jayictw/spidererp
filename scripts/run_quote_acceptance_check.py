import json
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.dispatch_quote_task import enqueue_mode, run_stage_mode
from scripts.run_quote_pipeline import run_quote_pipeline
from scripts.show_pricing_decision import build_pricing_decision_view
from scripts.show_quote_task_timeline import build_task_timeline
from tests.quote_test_support import create_quote_test_env


def main() -> int:
    env = create_quote_test_env()
    try:
        pipeline_result = run_quote_pipeline(
            db_path=str(env.db_path),
            soq_db_path=str(env.soq_db_path),
            part_number="STM32L412CBU6",
            requested_qty=1000,
            customer_id="cust_demo_001",
            qq_conversation_id="qq_accept_001",
            write_decision=True,
        )

        args = type(
            "Args",
            (),
            {
                "db_path": str(env.db_path),
                "soq_db_path": str(env.soq_db_path),
                "source": "acceptance",
                "part_number": "STM32F103C8T6",
                "requested_qty": 1200,
                "batch_id": "",
                "customer_id": "cust_demo_001",
                "qq_conversation_id": "qq_accept_002",
                "task_id": 0,
                "assigned_worker": "",
            },
        )()
        enqueue_result = enqueue_mode(args)
        task_id = int(enqueue_result["task_id"])
        args.task_id = task_id
        stage_results = [
            run_stage_mode(args, "queued"),
            run_stage_mode(args, "evidence_ready"),
            run_stage_mode(args, "decision_ready"),
        ]

        with closing(sqlite3.connect(env.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            timeline_result = build_task_timeline(conn, task_id)
            decision_result = build_pricing_decision_view(conn, decision_id=int(stage_results[-1]["decision_id"]))

        acceptance = {
            "ok": all(
                [
                    pipeline_result.get("ok"),
                    enqueue_result.get("ok"),
                    all(item.get("ok") for item in stage_results),
                    timeline_result.get("ok"),
                    decision_result.get("ok"),
                ]
            ),
            "acceptance_suite": "quote_acceptance_v1",
            "checks": {
                "pipeline_auto_quote_action": pipeline_result.get("reply_preview", {}).get("action"),
                "pipeline_decision_id": pipeline_result.get("decision_id"),
                "task_id": task_id,
                "task_stage": timeline_result.get("timeline_summary", {}).get("stage"),
                "task_event_count": timeline_result.get("timeline_summary", {}).get("event_count"),
                "task_decision_id": decision_result.get("summary", {}).get("decision_id"),
                "task_quote_strategy": decision_result.get("summary", {}).get("quote_strategy"),
                "task_handoff_reason": decision_result.get("summary", {}).get("handoff_reason"),
            },
        }
        print(json.dumps(acceptance, ensure_ascii=False, indent=2))
        return 0 if acceptance["ok"] else 1
    finally:
        env.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
