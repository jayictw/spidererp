import sqlite3
import unittest

from scripts.quote_agents.qq_reply_agent import build_reply_preview


class TestQqReplyPreview(unittest.TestCase):
    def test_auto_quote_preview(self) -> None:
        payload = build_reply_preview(
            normalized_part_number="STM32F103C8T6",
            requested_qty=1200,
            decision={
                "proposed_quote": 1.45,
                "auto_reply_allowed": 1,
                "quote_strategy": "direct_quote",
                "handoff_reason": "",
            },
        )
        self.assertEqual(payload["action"], "auto_quote_preview")
        self.assertIn("1.4500", payload["reply"])

    def test_apply_then_handoff_preview(self) -> None:
        payload = build_reply_preview(
            normalized_part_number="STM32L412CBU6",
            requested_qty=500,
            decision={
                "proposed_quote": 10.6195,
                "auto_reply_allowed": 0,
                "quote_strategy": "handoff",
                "handoff_reason": "market_manual_review_needed",
            },
        )
        self.assertEqual(payload["action"], "apply_then_handoff_preview")
        self.assertIn("需要向公司申请", payload["reply"])

    def test_handoff_no_reply_when_no_quote(self) -> None:
        payload = build_reply_preview(
            normalized_part_number="STM32L412CBU6",
            requested_qty=500,
            decision={
                "proposed_quote": None,
                "auto_reply_allowed": 0,
                "quote_strategy": "handoff",
                "handoff_reason": "market_manual_review_needed",
            },
            evidence_partial=True,
        )
        self.assertEqual(payload["action"], "handoff_no_reply")
        self.assertEqual(payload["reason"], "market_manual_review_needed")


if __name__ == "__main__":
    unittest.main()
