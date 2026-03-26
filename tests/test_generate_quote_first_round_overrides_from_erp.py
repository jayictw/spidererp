import csv
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.generate_quote_first_round_overrides_from_erp import (
    generate_rows,
    read_existing_overrides,
    refresh_guardrails,
    write_rows,
)
from tests.quote_test_support import create_quote_test_env


class TestGenerateQuoteFirstRoundOverridesFromErp(unittest.TestCase):
    def test_generate_rows_preserves_manual_and_adds_erp_rows(self) -> None:
        existing = [
            {
                "normalized_part_number": "STM32L412CBU6",
                "inquiry_type": "general",
                "qty_min": "1560",
                "qty_max": "1560",
                "first_quote_price": "11.5",
                "currency": "CNY",
                "note": "manual",
            }
        ]
        erp_rows = [
            {
                "model": "STM32L412CBU6",
                "taxed_sale_price": 11.0,
                "stock_qty": 1560,
                "supply_status": "随时有货",
            },
            {
                "model": "LM2904YPT",
                "taxed_sale_price": 0.28,
                "stock_qty": 120000,
                "supply_status": "打折特供",
            },
        ]
        rows = generate_rows(existing, erp_rows)
        self.assertEqual(rows[0]["first_quote_price"], "11.5")
        self.assertEqual(rows[0]["qty_min"], "1560")
        self.assertEqual(rows[1]["normalized_part_number"], "LM2904YPT")
        self.assertEqual(rows[1]["qty_min"], "120000")
        self.assertEqual(len(rows), 2)

    def test_write_and_read_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "overrides.csv"
            rows = [
                {
                    "normalized_part_number": "LM2904YPT",
                    "inquiry_type": "general",
                    "qty_min": "",
                    "qty_max": "",
                    "first_quote_price": "0.28",
                    "currency": "CNY",
                    "note": "generated",
                }
            ]
            write_rows(csv_path, rows)
            read_back = read_existing_overrides(csv_path)
            self.assertEqual(len(read_back), 1)
            self.assertEqual(read_back[0]["normalized_part_number"], "LM2904YPT")

    def test_refresh_guardrails_generates_outputs(self) -> None:
        env = create_quote_test_env()
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                override_path = Path(tmpdir) / "overrides.csv"
                smoke_json = Path(tmpdir) / "smoke.json"
                smoke_csv = Path(tmpdir) / "smoke.csv"
                guardrail_csv = Path(tmpdir) / "guardrails.csv"
                write_rows(
                    override_path,
                    [
                        {
                            "normalized_part_number": "STM32L412CBU6",
                            "inquiry_type": "general",
                            "qty_min": "1000",
                            "qty_max": "1000",
                            "first_quote_price": "1.52",
                            "currency": "CNY",
                            "note": "fixture direct",
                        },
                        {
                            "normalized_part_number": "STM32F103C8T6",
                            "inquiry_type": "general",
                            "qty_min": "1200",
                            "qty_max": "1200",
                            "first_quote_price": "1.45",
                            "currency": "CNY",
                            "note": "fixture handoff",
                        },
                    ],
                )
                result = refresh_guardrails(
                    db_path=env.db_path,
                    soq_db_path=str(env.soq_db_path),
                    override_output_path=override_path,
                    smoke_json_output=smoke_json,
                    smoke_csv_output=smoke_csv,
                    guardrail_output=guardrail_csv,
                )
                self.assertTrue(smoke_json.exists())
                self.assertTrue(smoke_csv.exists())
                self.assertTrue(guardrail_csv.exists())
                self.assertEqual(result["smoke_result"]["override_row_count"], 2)
                self.assertEqual(result["guardrail_result"]["guardrail_count"], 0)
        finally:
            env.cleanup()
