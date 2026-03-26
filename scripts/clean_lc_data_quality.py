import csv
import sqlite3
from pathlib import Path
from datetime import datetime


BASE = Path(__file__).resolve().parents[1]
DB = BASE / "sol.db"
OVERRIDES = BASE / "data" / "recent_orders_manual_overrides.csv"
REPORT = BASE / "data" / "lc_cleaning_report_latest.md"


def load_overrides(path: Path) -> dict[str, int]:
    out: dict[str, int] = {}
    if not path.exists():
        return out
    with path.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            model = (row.get("model") or "").strip().upper()
            raw = (row.get("recent_orders") or "").strip()
            if not model or not raw:
                continue
            try:
                value = int(float(raw))
            except ValueError:
                continue
            out[model] = max(0, min(100, value))
    return out


def main() -> None:
    overrides = load_overrides(OVERRIDES)
    con = sqlite3.connect(DB)
    cur = con.cursor()

    cur.execute("SELECT COUNT(*) FROM parts_pricing WHERE lc_recent_orders_extracted > 100")
    before_gt100_extracted = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM parts_pricing WHERE recent_orders > 100")
    before_gt100_recent = cur.fetchone()[0]

    cur.execute(
        """
        UPDATE parts_pricing
        SET lc_recent_orders_extracted = CASE
          WHEN lc_recent_orders_extracted IS NULL THEN NULL
          WHEN lc_recent_orders_extracted < 0 THEN 0
          WHEN lc_recent_orders_extracted > 100 THEN 100
          ELSE CAST(ROUND(lc_recent_orders_extracted) AS INTEGER)
        END
        WHERE lc_recent_orders_extracted IS NOT NULL
        """
    )
    updated_extracted = cur.rowcount

    cur.execute(
        """
        UPDATE parts_pricing
        SET recent_orders = CASE
          WHEN recent_orders IS NULL THEN NULL
          WHEN recent_orders < 0 THEN 0
          WHEN recent_orders > 100 THEN 100
          ELSE CAST(ROUND(recent_orders) AS INTEGER)
        END
        WHERE recent_orders IS NOT NULL
        """
    )
    updated_recent = cur.rowcount

    applied_overrides = 0
    for model, value in overrides.items():
        cur.execute(
            "UPDATE parts_pricing SET recent_orders=?, lc_recent_orders_extracted=? WHERE UPPER(TRIM(model))=?",
            (value, value, model),
        )
        applied_overrides += cur.rowcount

    con.commit()

    cur.execute("SELECT COUNT(*) FROM parts_pricing WHERE lc_recent_orders_extracted > 100")
    after_gt100_extracted = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM parts_pricing WHERE recent_orders > 100")
    after_gt100_recent = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM parts_pricing")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM parts_pricing WHERE lc_recent_orders_extracted IS NULL")
    null_extracted = cur.fetchone()[0]

    report = f"""# LC Cleaning Report

- Generated at: {datetime.now().isoformat(timespec="seconds")}
- Total rows: {total}
- recent_orders > 100 before: {before_gt100_recent}
- lc_recent_orders_extracted > 100 before: {before_gt100_extracted}
- recent_orders normalized rows: {updated_recent}
- lc_recent_orders_extracted normalized rows: {updated_extracted}
- Manual overrides loaded: {len(overrides)}
- Manual override updates applied: {applied_overrides}
- recent_orders > 100 after: {after_gt100_recent}
- lc_recent_orders_extracted > 100 after: {after_gt100_extracted}
- lc_recent_orders_extracted NULL rows: {null_extracted}

## Cleaning Rules
1. Clamp recent orders into 0..100 range.
2. Round non-integer recent orders to nearest integer.
3. Apply manual overrides from `data/recent_orders_manual_overrides.csv`.
4. Keep both `recent_orders` and `lc_recent_orders_extracted` synchronized.
"""
    REPORT.write_text(report, encoding="utf-8")
    con.close()
    print(report)
    print(f"saved_report={REPORT}")


if __name__ == "__main__":
    main()

