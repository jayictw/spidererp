import tempfile
import unittest
from pathlib import Path

from scripts.generate_quote_handoff_guardrails import build_guardrail_rows, read_rows


class TestGenerateQuoteHandoffGuardrails(unittest.TestCase):
    def test_build_guardrail_rows_filters_auto_reply(self) -> None:
        rows = [
            {
                "normalized_part_number": "STM32L412CBU6",
                "requested_qty": "1560",
                "override_price": "11.5",
                "auto_reply_allowed": "True",
                "handoff_reason": "",
                "reply_action": "auto_quote_preview",
            },
            {
                "normalized_part_number": "STM32F302CBT6",
                "requested_qty": "254",
                "override_price": "11.978",
                "auto_reply_allowed": "False",
                "handoff_reason": "erp_requires_price_application",
                "reply_action": "apply_then_handoff_preview",
            },
        ]
        guardrails = build_guardrail_rows(rows)
        self.assertEqual(len(guardrails), 1)
        self.assertEqual(guardrails[0]["normalized_part_number"], "STM32F302CBT6")
        self.assertEqual(guardrails[0]["guardrail_action"], "manual_handoff_required")

    def test_read_rows_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "smoke.csv"
            path.write_text(
                "\n".join(
                    [
                        "normalized_part_number,requested_qty,override_price,auto_reply_allowed,handoff_reason,reply_action",
                        "STM32G0B1RBT6,6720,10.17,False,erp_requires_price_application,apply_then_handoff_preview",
                    ]
                ),
                encoding="utf-8-sig",
            )
            rows = read_rows(path)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["normalized_part_number"], "STM32G0B1RBT6")


if __name__ == "__main__":
    unittest.main()
