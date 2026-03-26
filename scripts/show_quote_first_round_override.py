import argparse
import csv
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.quote_orchestrator import FIRST_ROUND_OVERRIDE_PATH, get_first_round_override


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Show first-round quote overrides.")
    parser.add_argument("--part-number", default="", help="Optional part number filter.")
    parser.add_argument("--requested-qty", type=float, default=0, help="Optional qty to evaluate effective override.")
    return parser.parse_args()


def _read_all_rows(csv_path: Path) -> list[dict]:
    if not csv_path.exists():
        return []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main() -> int:
    args = parse_args()
    rows = _read_all_rows(FIRST_ROUND_OVERRIDE_PATH)
    result: dict[str, object] = {
        "ok": True,
        "csv_path": str(FIRST_ROUND_OVERRIDE_PATH),
        "row_count": len(rows),
        "rows": rows,
    }
    if str(args.part_number).strip():
        normalized_part_number = str(args.part_number).strip().upper()
        filtered = [row for row in rows if str(row.get("normalized_part_number") or "").strip().upper() == normalized_part_number]
        result["rows"] = filtered
        result["row_count"] = len(filtered)
        if args.requested_qty:
            result["matched_override"] = get_first_round_override(normalized_part_number, args.requested_qty)
            result["requested_qty"] = args.requested_qty
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
