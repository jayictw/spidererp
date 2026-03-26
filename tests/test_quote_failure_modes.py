import unittest
from contextlib import closing

from scripts.dispatch_quote_task import enqueue_mode, run_stage_mode
from scripts.quote_agents.qq_reply_agent import build_reply_preview
from scripts.quote_orchestrator import build_quote_context, connect_db
from tests.quote_test_support import create_quote_test_env


class TestQuoteFailureModes(unittest.TestCase):
    def setUp(self) -> None:
        self.env = create_quote_test_env()

    def tearDown(self) -> None:
        self.env.cleanup()

    def test_orchestrator_returns_error_without_supplier_or_erp(self) -> None:
        with closing(connect_db(self.env.db_path)) as conn:
            payload = build_quote_context(
                conn,
                normalized_part_number="UNKNOWN_PART_001",
                requested_qty=100,
                customer_id="cust_demo_001",
                soq_db_path=str(self.env.soq_db_path),
            )
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"], "supplier_item_not_found")

    def test_reply_preview_clarify_when_missing_qty(self) -> None:
        payload = build_reply_preview(
            normalized_part_number="STM32F103C8T6",
            requested_qty=0,
            decision={"proposed_quote": 1.45, "auto_reply_allowed": 1, "quote_strategy": "direct_quote"},
        )
        self.assertEqual(payload["action"], "clarify")
        self.assertEqual(payload["reason"], "missing_model_or_qty")

    def test_dispatcher_rejects_stage_mismatch(self) -> None:
        args = type(
            "Args",
            (),
            {
                "db_path": str(self.env.db_path),
                "soq_db_path": str(self.env.soq_db_path),
                "source": "failure_test",
                "part_number": "STM32F103C8T6",
                "requested_qty": 1200,
                "batch_id": "",
                "customer_id": "cust_demo_001",
                "qq_conversation_id": "",
                "task_id": 0,
                "assigned_worker": "",
            },
        )()
        enqueue_result = enqueue_mode(args)
        self.assertTrue(enqueue_result["ok"])
        args.task_id = enqueue_result["task_id"]
        result = run_stage_mode(args, "decision_ready")
        self.assertFalse(result["ok"])
        self.assertIn("task_stage_mismatch", result["error"])
