import json
import subprocess
import unittest

from scripts.quote_orchestrator import get_first_round_override


class TestQuoteFirstRoundOverride(unittest.TestCase):
    def test_get_first_round_override_exact_qty(self) -> None:
        row = get_first_round_override("STM32L412CBU6", 1560)
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["first_quote_price"], 11.5)
        self.assertEqual(row["currency"], "CNY")

    def test_get_first_round_override_miss_other_qty(self) -> None:
        row = get_first_round_override("STM32L412CBU6", 1500)
        self.assertIsNone(row)

    def test_show_override_script(self) -> None:
        proc = subprocess.run(
            [
                "py",
                "-3",
                "scripts/show_quote_first_round_override.py",
                "--part-number",
                "STM32L412CBU6",
                "--requested-qty",
                "1560",
            ],
            cwd=r"F:\Jay_ic_tw",
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["row_count"], 1)
        self.assertEqual(payload["matched_override"]["first_quote_price"], 11.5)
