import argparse
import sqlite3
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.quote_agents.trader_quote_collector import import_trader_quotes_csv


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Import manual trader quotes CSV into sol.db.")
    p.add_argument("--input", required=True, help="Trader quote CSV path.")
    p.add_argument("--db-path", default=r"F:/Jay_ic_tw/sol.db", help="SQLite database path.")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    with sqlite3.connect(Path(args.db_path)) as conn:
        result = import_trader_quotes_csv(conn, Path(args.input))
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
