import argparse
import csv
import json
import sqlite3
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.generate_quote_handoff_guardrails import DEFAULT_OUTPUT as DEFAULT_GUARDRAIL_OUTPUT
from scripts.generate_quote_handoff_guardrails import build_guardrail_rows, summarize as summarize_guardrails
from scripts.generate_quote_handoff_guardrails import write_rows as write_guardrail_rows
from scripts.quote_orchestrator import FIRST_ROUND_OVERRIDE_PATH
from scripts.run_quote_override_smoke_check import run_smoke_check, write_outputs as write_smoke_outputs

DEFAULT_SMOKE_JSON = Path(r"F:/Jay_ic_tw/data/quote_override_smoke_check_latest.json")
DEFAULT_SMOKE_CSV = Path(r"F:/Jay_ic_tw/data/quote_override_smoke_check_latest.csv")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate first-round quote overrides from ERP inventory.")
    parser.add_argument("--db-path", default=r"F:/Jay_ic_tw/sol.db", help="SQLite database path.")
    parser.add_argument("--soq-db-path", default=r"F:/Jay_ic_tw/qq/agent-harness/soq.db", help="QQ SOQ database path.")
    parser.add_argument("--output", default=str(FIRST_ROUND_OVERRIDE_PATH), help="Output CSV path.")
    parser.add_argument("--refresh-guardrails", action="store_true", help="Run smoke check and rebuild handoff guardrails after override generation.")
    parser.add_argument("--smoke-json-output", default=str(DEFAULT_SMOKE_JSON), help="Smoke check JSON output path.")
    parser.add_argument("--smoke-csv-output", default=str(DEFAULT_SMOKE_CSV), help="Smoke check CSV output path.")
    parser.add_argument("--guardrail-output", default=str(DEFAULT_GUARDRAIL_OUTPUT), help="Guardrail CSV output path.")
    return parser.parse_args()


def connect_db(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def read_existing_overrides(csv_path: Path) -> list[dict[str, str]]:
    if not csv_path.exists():
        return []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_erp_rows(conn: sqlite3.Connection) -> list[dict[str, str]]:
    rows = conn.execute(
        """
        SELECT
          model,
          taxed_sale_price,
          standard_sale_price,
          floor_sale_price,
          supply_status,
          MAX(stock_qty) AS stock_qty
        FROM erp_inventory
        WHERE model IS NOT NULL
          AND TRIM(model) <> ''
          AND taxed_sale_price IS NOT NULL
        GROUP BY model, taxed_sale_price, standard_sale_price, floor_sale_price, supply_status
        ORDER BY model ASC
        """
    ).fetchall()
    return [dict(row) for row in rows]


def generate_rows(existing_rows: list[dict[str, str]], erp_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    output_rows: list[dict[str, str]] = []

    for row in existing_rows:
        note = str(row.get("note") or "").strip()
        if note.startswith("Generated from ERP taxed_sale_price"):
            continue
        output_rows.append(
            {
                "normalized_part_number": str(row.get("normalized_part_number") or "").strip().upper(),
                "inquiry_type": str(row.get("inquiry_type") or "general").strip() or "general",
                "qty_min": str(row.get("qty_min") or "").strip(),
                "qty_max": str(row.get("qty_max") or "").strip(),
                "first_quote_price": str(row.get("first_quote_price") or "").strip(),
                "currency": str(row.get("currency") or "CNY").strip() or "CNY",
                "note": note,
            }
        )

    manual_keys = {
        (
            str(row.get("normalized_part_number") or "").strip().upper(),
            str(row.get("qty_min") or "").strip(),
            str(row.get("qty_max") or "").strip(),
        )
        for row in output_rows
    }
    for row in erp_rows:
        model = str(row.get("model") or "").strip().upper()
        if not model:
            continue
        stock_qty = row.get("stock_qty")
        qty_text = ""
        if stock_qty not in (None, ""):
            qty_float = float(stock_qty)
            qty_text = str(int(qty_float)) if qty_float.is_integer() else str(qty_float)
        key = (model, qty_text, qty_text)
        if key in manual_keys:
            continue
        output_rows.append(
            {
                "normalized_part_number": model,
                "inquiry_type": "general",
                "qty_min": qty_text,
                "qty_max": qty_text,
                "first_quote_price": str(row.get("taxed_sale_price") or "").strip(),
                "currency": "CNY",
                "note": (
                    f"Generated from ERP taxed_sale_price; stock_qty={row.get('stock_qty')}; "
                    f"supply_status={str(row.get('supply_status') or '').strip()}"
                ),
            }
        )
    return output_rows


def write_rows(csv_path: Path, rows: list[dict[str, str]]) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "normalized_part_number",
                "inquiry_type",
                "qty_min",
                "qty_max",
                "first_quote_price",
                "currency",
                "note",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def refresh_guardrails(
    db_path: Path,
    soq_db_path: str,
    override_output_path: Path,
    smoke_json_output: Path,
    smoke_csv_output: Path,
    guardrail_output: Path,
) -> dict[str, object]:
    smoke_result = run_smoke_check(str(db_path), str(soq_db_path), str(override_output_path))
    write_smoke_outputs(smoke_result, smoke_json_output, smoke_csv_output)
    guardrails = build_guardrail_rows(smoke_result.get("results", []))
    write_guardrail_rows(guardrail_output, guardrails)
    return {
        "smoke_result": smoke_result,
        "guardrail_result": summarize_guardrails(smoke_result.get("results", []), guardrails),
        "smoke_json_output": str(smoke_json_output),
        "smoke_csv_output": str(smoke_csv_output),
        "guardrail_output": str(guardrail_output),
    }


def main() -> int:
    args = parse_args()
    output_path = Path(args.output)
    existing_rows = read_existing_overrides(output_path)
    db_path = Path(args.db_path)
    with connect_db(db_path) as conn:
        erp_rows = load_erp_rows(conn)
    rows = generate_rows(existing_rows, erp_rows)
    write_rows(output_path, rows)
    result: dict[str, object] = {
        "ok": True,
        "output": str(output_path),
        "existing_rows": len(existing_rows),
        "erp_rows": len(erp_rows),
        "written_rows": len(rows),
    }
    if args.refresh_guardrails:
        result["guardrail_refresh"] = refresh_guardrails(
            db_path=db_path,
            soq_db_path=str(args.soq_db_path),
            override_output_path=output_path,
            smoke_json_output=Path(args.smoke_json_output),
            smoke_csv_output=Path(args.smoke_csv_output),
            guardrail_output=Path(args.guardrail_output),
        )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
