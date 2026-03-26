import argparse
import csv
import json
from pathlib import Path


DEFAULT_INPUT = Path(r"F:/Jay_ic_tw/data/quote_override_smoke_check_latest.csv")
DEFAULT_OUTPUT = Path(r"F:/Jay_ic_tw/data/quote_first_round_handoff_guardrails.csv")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate first-round handoff guardrails from smoke check output.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Smoke check CSV path.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Guardrail CSV output path.")
    return parser.parse_args()


def read_rows(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def build_guardrail_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    guardrails: list[dict[str, str]] = []
    for row in rows:
        if str(row.get("auto_reply_allowed") or "").strip().lower() == "true":
            continue
        pricing_policy_source = str(row.get("pricing_policy_source") or "").strip()
        handoff_reason = str(row.get("handoff_reason") or "").strip()
        handoff_tokens = {token.strip() for token in handoff_reason.split("|") if token.strip()}
        if pricing_policy_source == "general_inquiry_override" and handoff_tokens == {"erp_missing"}:
            continue
        guardrails.append(
            {
                "normalized_part_number": str(row.get("normalized_part_number") or "").strip().upper(),
                "requested_qty": str(row.get("requested_qty") or "").strip(),
                "override_price": str(row.get("override_price") or "").strip(),
                "handoff_reason": handoff_reason,
                "reply_action": str(row.get("reply_action") or "").strip(),
                "guardrail_action": "manual_handoff_required",
            }
        )
    return guardrails


def write_rows(csv_path: Path, rows: list[dict[str, str]]) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "normalized_part_number",
                "requested_qty",
                "override_price",
                "handoff_reason",
                "reply_action",
                "guardrail_action",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def summarize(rows: list[dict[str, str]], guardrails: list[dict[str, str]]) -> dict[str, object]:
    reason_counts: dict[str, int] = {}
    for row in guardrails:
        reason = row.get("handoff_reason") or "unknown"
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
    return {
        "ok": True,
        "input_row_count": len(rows),
        "guardrail_count": len(guardrails),
        "reason_counts": reason_counts,
    }


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    rows = read_rows(input_path)
    guardrails = build_guardrail_rows(rows)
    write_rows(output_path, guardrails)
    print(json.dumps(summarize(rows, guardrails), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
