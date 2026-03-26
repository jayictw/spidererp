import tempfile
import unittest
from pathlib import Path

from scripts.run_quote_override_smoke_check import run_smoke_check
from tests.quote_test_support import create_quote_test_env


class TestQuoteOverrideSmokeCheck(unittest.TestCase):
    def test_run_smoke_check(self) -> None:
        env = create_quote_test_env()
        try:
            overrides_path = Path(env.tmpdir.name) / "overrides.csv"
            overrides_path.write_text(
                "\n".join(
                    [
                        "normalized_part_number,inquiry_type,qty_min,qty_max,first_quote_price,currency,note",
                        "STM32L412CBU6,general,1000,1000,1.52,CNY,fixture direct",
                        "STM32F103C8T6,general,1200,1200,1.45,CNY,fixture handoff",
                    ]
                ),
                encoding="utf-8-sig",
            )
            result = run_smoke_check(str(env.db_path), str(env.soq_db_path), str(overrides_path))
            self.assertTrue(result["ok"])
            self.assertEqual(result["override_row_count"], 2)
            self.assertEqual(result["direct_quote_count"], 2)
            self.assertEqual(len(result["results"]), 2)
        finally:
            env.cleanup()
