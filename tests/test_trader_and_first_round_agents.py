import csv
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.quote_agents.qq_reply_agent import build_reply_preview
from scripts.quote_agents.trader_quote_collector import get_trader_quotes, import_trader_quotes_csv, summarize_trader_quotes


class TestTraderAndFirstRoundAgents(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self.conn.close()
        self.tmpdir.cleanup()

    def test_import_and_summarize_trader_quotes(self) -> None:
        csv_path = Path(self.tmpdir.name) / "trader_quotes.csv"
        with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["normalized_part_number", "trader_name", "quoted_price", "currency", "quoted_qty", "source"],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "normalized_part_number": "STM32F103C8T6",
                    "trader_name": "TraderA",
                    "quoted_price": "1.40",
                    "currency": "USD",
                    "quoted_qty": "1000",
                    "source": "manual_csv",
                }
            )
            writer.writerow(
                {
                    "normalized_part_number": "STM32F103C8T6",
                    "trader_name": "TraderB",
                    "quoted_price": "1.35",
                    "currency": "USD",
                    "quoted_qty": "500",
                    "source": "manual_csv",
                }
            )
        result = import_trader_quotes_csv(self.conn, csv_path)
        self.assertTrue(result["ok"])
        rows = get_trader_quotes(self.conn, "STM32F103C8T6")
        summary = summarize_trader_quotes(rows)
        self.assertEqual(summary["quote_count"], 2)
        self.assertEqual(summary["trader_reference_price"], 1.35)

    def test_first_round_preview_from_decision(self) -> None:
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


if __name__ == "__main__":
    unittest.main()
