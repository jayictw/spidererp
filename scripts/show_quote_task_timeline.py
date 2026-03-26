import argparse
import json
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.quote_agents.task_queue import ensure_quote_tasks_table, get_task_by_id


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Show task timeline for a quote task.")
    parser.add_argument("--db-path", default=r"F:/Jay_ic_tw/sol.db", help="SQLite database path.")
    parser.add_argument("--task-id", type=int, required=True, help="Quote task id.")
    return parser.parse_args()


def _connect_db(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def build_task_timeline(conn: sqlite3.Connection, task_id: int) -> dict:
    ensure_quote_tasks_table(conn)
    task = get_task_by_id(conn, task_id)
    if task is None:
        return {"ok": False, "error": "task_not_found", "task_id": task_id}

    events = [
        dict(row)
        for row in conn.execute(
            """
            SELECT event_id, event_type, from_stage, to_stage, worker, status, note, created_at
            FROM quote_task_events
            WHERE task_id=?
            ORDER BY event_id ASC
            """,
            (task_id,),
        ).fetchall()
    ]

    return {
        "ok": True,
        "task_id": task_id,
        "task": task,
        "timeline_summary": {
            "part_number": task.get("part_number"),
            "status": task.get("status"),
            "stage": task.get("stage"),
            "assigned_worker": task.get("assigned_worker"),
            "event_count": len(events),
            "decision_id": task.get("decision_id"),
        },
        "events": events,
    }


def main() -> int:
    args = parse_args()
    with closing(_connect_db(Path(args.db_path))) as conn:
        result = build_task_timeline(conn, args.task_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
