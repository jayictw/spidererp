import json
import sqlite3
import unittest

from scripts.dispatch_quote_task import enqueue_mode, run_stage_mode
from scripts.run_quote_pipeline import run_quote_pipeline
from scripts.show_pricing_decision import build_pricing_decision_view
from scripts.show_quote_task_timeline import build_task_timeline
from tests.quote_test_support import create_quote_test_env


class TestQuoteAcceptanceFlow(unittest.TestCase):
    def setUp(self) -> None:
        self.env = create_quote_test_env()

    def tearDown(self) -> None:
        self.env.cleanup()

    def test_end_to_end_acceptance(self) -> None:
        pipeline_result = run_quote_pipeline(
            db_path=str(self.env.db_path),
            soq_db_path=str(self.env.soq_db_path),
            part_number="STM32L412CBU6",
            requested_qty=1000,
            customer_id="cust_demo_001",
            qq_conversation_id="qq_accept_001",
            write_decision=True,
        )
        self.assertTrue(pipeline_result["ok"])
        self.assertEqual(pipeline_result["decision_stub"]["quote_strategy"], "direct_quote")
        self.assertEqual(pipeline_result["reply_preview"]["action"], "auto_quote_preview")
        self.assertIsNotNone(pipeline_result["decision_id"])

        args = type(
            "Args",
            (),
            {
                "db_path": str(self.env.db_path),
                "soq_db_path": str(self.env.soq_db_path),
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
        self.assertTrue(enqueue_result["ok"])
        task_id = enqueue_result["task_id"]

        args.task_id = task_id
        stage1 = run_stage_mode(args, "queued")
        stage2 = run_stage_mode(args, "evidence_ready")
        stage3 = run_stage_mode(args, "decision_ready")
        self.assertTrue(stage1["ok"])
        self.assertTrue(stage2["ok"])
        self.assertTrue(stage3["ok"])

        conn = sqlite3.connect(self.env.db_path)
        conn.row_factory = sqlite3.Row
        timeline = build_task_timeline(conn, task_id)
        decision = build_pricing_decision_view(conn, int(stage3["decision_id"]))
        conn.close()

        self.assertTrue(timeline["ok"])
        self.assertEqual(timeline["timeline_summary"]["event_count"], 7)
        self.assertEqual(timeline["timeline_summary"]["stage"], "completed")
        self.assertTrue(decision["ok"])
        self.assertEqual(decision["summary"]["normalized_part_number"], "STM32F103C8T6")
        self.assertEqual(decision["summary"]["quote_strategy"], "handoff")
        self.assertEqual(decision["summary"]["proposed_quote"], 1.45)
        self.assertEqual(decision["summary"]["handoff_reason"], "supplier_context_missing")

        proof = {
            "pipeline_action": pipeline_result["reply_preview"]["action"],
            "task_timeline_events": timeline["timeline_summary"]["event_count"],
            "task_decision_strategy": decision["summary"]["quote_strategy"],
        }
        self.assertEqual(
            json.dumps(proof, ensure_ascii=False),
            '{"pipeline_action": "auto_quote_preview", "task_timeline_events": 7, "task_decision_strategy": "handoff"}',
        )
