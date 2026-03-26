import argparse
import csv
import json
import sqlite3
import sys
from contextlib import contextmanager
from contextlib import closing
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.qq_reply_preview import connect_db
from scripts.quote_agents.qq_reply_agent import build_reply_preview
import scripts.quote_orchestrator as quote_orchestrator
from scripts.quote_orchestrator import build_quote_context


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a smoke check across first-round quote overrides.")
    parser.add_argument("--db-path", default=r"F:/Jay_ic_tw/sol.db", help="SQLite database path.")
    parser.add_argument("--soq-db-path", default=r"F:/Jay_ic_tw/qq/agent-harness/soq.db", help="QQ SOQ database path.")
    parser.add_argument("--overrides-path", default=r"F:/Jay_ic_tw/data/quote_first_round_overrides.csv", help="Override csv path.")
    parser.add_argument("--output-json", default=r"F:/Jay_ic_tw/data/quote_override_smoke_check_latest.json", help="JSON output path.")
    parser.add_argument("--output-csv", default=r"F:/Jay_ic_tw/data/quote_override_smoke_check_latest.csv", help="CSV output path.")
    return parser.parse_args()


def read_override_rows(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


@contextmanager
def use_override_path(csv_path: Path):
    original_path = quote_orchestrator.FIRST_ROUND_OVERRIDE_PATH
    quote_orchestrator.FIRST_ROUND_OVERRIDE_PATH = csv_path
    try:
        yield
    finally:
        quote_orchestrator.FIRST_ROUND_OVERRIDE_PATH = original_path


@contextmanager
def disable_handoff_guardrails():
    original_path = quote_orchestrator.HANDOFF_GUARDRAIL_PATH
    quote_orchestrator.HANDOFF_GUARDRAIL_PATH = Path("__smoke_guardrail_disabled__.csv")
    try:
        yield
    finally:
        quote_orchestrator.HANDOFF_GUARDRAIL_PATH = original_path


def run_smoke_check(db_path: str, soq_db_path: str, overrides_path: str) -> dict:
    override_path = Path(overrides_path)
    rows = read_override_rows(override_path)
    results: list[dict[str, object]] = []
    with use_override_path(override_path), disable_handoff_guardrails():
        with closing(connect_db(Path(db_path))) as conn:
            for row in rows:
                part_number = str(row.get("normalized_part_number") or "").strip().upper()
                qty_raw = str(row.get("qty_max") or row.get("qty_min") or "").strip()
                qty = int(float(qty_raw)) if qty_raw else 0
                payload = build_quote_context(
                    conn,
                    normalized_part_number=part_number,
                    requested_qty=qty,
                    soq_db_path=soq_db_path,
                )
                if payload.get("ok"):
                    reply_preview = build_reply_preview(
                        normalized_part_number=part_number,
                        requested_qty=payload.get("decision_stub", {}).get("requested_qty"),
                        decision=payload.get("decision_stub", {}),
                        evidence_partial=bool(payload.get("partial")),
                    )
                    results.append(
                        {
                            "normalized_part_number": part_number,
                            "requested_qty": qty,
                            "override_price": row.get("first_quote_price"),
                            "pricing_policy_source": payload.get("decision_stub", {}).get("pricing_policy_source"),
                            "quote_strategy": payload.get("decision_stub", {}).get("quote_strategy"),
                            "auto_reply_allowed": payload.get("decision_stub", {}).get("auto_reply_allowed"),
                            "handoff_reason": payload.get("decision_stub", {}).get("handoff_reason"),
                            "reply_action": reply_preview.get("action"),
                            "quoted_price": reply_preview.get("quoted_price"),
                        }
                    )
                else:
                    results.append(
                        {
                            "normalized_part_number": part_number,
                            "requested_qty": qty,
                            "override_price": row.get("first_quote_price"),
                            "pricing_policy_source": "",
                            "quote_strategy": "error",
                            "auto_reply_allowed": False,
                            "handoff_reason": payload.get("error"),
                            "reply_action": "error",
                            "quoted_price": None,
                        }
                    )

    direct_count = sum(1 for item in results if item.get("reply_action") == "auto_quote_preview")
    handoff_count = sum(1 for item in results if item.get("reply_action") != "auto_quote_preview")
    return {
        "ok": True,
        "override_row_count": len(rows),
        "direct_quote_count": direct_count,
        "handoff_count": handoff_count,
        "results": results,
    }


def write_outputs(result: dict, output_json: Path, output_csv: Path) -> None:
    output_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "normalized_part_number",
                "requested_qty",
                "override_price",
                "pricing_policy_source",
                "quote_strategy",
                "auto_reply_allowed",
                "handoff_reason",
                "reply_action",
                "quoted_price",
            ],
        )
        writer.writeheader()
        writer.writerows(result.get("results", []))


def main() -> int:
    args = parse_args()
    result = run_smoke_check(args.db_path, args.soq_db_path, args.overrides_path)
    write_outputs(result, Path(args.output_json), Path(args.output_csv))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
