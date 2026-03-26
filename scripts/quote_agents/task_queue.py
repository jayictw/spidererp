import json
import sqlite3
from datetime import datetime
from typing import Any


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def ensure_quote_tasks_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS quote_tasks (
          task_id INTEGER PRIMARY KEY AUTOINCREMENT,
          source TEXT NOT NULL,
          part_number TEXT NOT NULL,
          requested_qty REAL,
          batch_id TEXT,
          customer_id TEXT,
          qq_conversation_id TEXT,
          status TEXT NOT NULL,
          stage TEXT NOT NULL,
          assigned_worker TEXT,
          created_at TEXT NOT NULL,
          started_at TEXT,
          completed_at TEXT,
          decision_id INTEGER,
          error_text TEXT,
          payload_json TEXT,
          evidence_json TEXT,
          result_json TEXT
        )
        """
    )
    columns = {row[1] for row in conn.execute("PRAGMA table_info(quote_tasks)").fetchall()}
    if "stage" not in columns:
        conn.execute("ALTER TABLE quote_tasks ADD COLUMN stage TEXT NOT NULL DEFAULT 'queued'")
    if "evidence_json" not in columns:
        conn.execute("ALTER TABLE quote_tasks ADD COLUMN evidence_json TEXT")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS quote_task_events (
          event_id INTEGER PRIMARY KEY AUTOINCREMENT,
          task_id INTEGER NOT NULL,
          event_type TEXT NOT NULL,
          from_stage TEXT,
          to_stage TEXT,
          worker TEXT,
          status TEXT,
          note TEXT,
          created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()


def append_task_event(
    conn: sqlite3.Connection,
    task_id: int,
    event_type: str,
    from_stage: str = "",
    to_stage: str = "",
    worker: str = "",
    status: str = "",
    note: str = "",
) -> int:
    ensure_quote_tasks_table(conn)
    cur = conn.execute(
        """
        INSERT INTO quote_task_events(
          task_id, event_type, from_stage, to_stage, worker, status, note, created_at
        ) VALUES(?,?,?,?,?,?,?,?)
        """,
        (
            task_id,
            event_type,
            from_stage or None,
            to_stage or None,
            worker or None,
            status or None,
            note or None,
            _now(),
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def enqueue_quote_task(
    conn: sqlite3.Connection,
    source: str,
    part_number: str,
    requested_qty: int = 0,
    batch_id: str = "",
    customer_id: str = "",
    qq_conversation_id: str = "",
    payload_json: str = "",
) -> int:
    ensure_quote_tasks_table(conn)
    cur = conn.execute(
        """
        INSERT INTO quote_tasks(
          source, part_number, requested_qty, batch_id, customer_id, qq_conversation_id,
          status, stage, assigned_worker, created_at, payload_json
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            source,
            str(part_number).strip().upper(),
            requested_qty or None,
            batch_id or None,
            customer_id or None,
            qq_conversation_id or None,
            "queued",
            "queued",
            None,
            _now(),
            payload_json or None,
        ),
    )
    conn.commit()
    task_id = int(cur.lastrowid)
    append_task_event(
        conn,
        task_id,
        event_type="enqueue",
        from_stage="",
        to_stage="queued",
        worker="",
        status="queued",
        note=source,
    )
    return task_id


def fetch_next_task_by_stage(conn: sqlite3.Connection, stage: str) -> dict[str, Any] | None:
    ensure_quote_tasks_table(conn)
    row = conn.execute(
        """
        SELECT * FROM quote_tasks
        WHERE stage=? AND status IN ('queued','running')
        ORDER BY task_id ASC
        LIMIT 1
        """,
        (stage,),
    ).fetchone()
    return dict(row) if row else None


def get_task_by_id(conn: sqlite3.Connection, task_id: int) -> dict[str, Any] | None:
    ensure_quote_tasks_table(conn)
    row = conn.execute(
        "SELECT * FROM quote_tasks WHERE task_id=?",
        (task_id,),
    ).fetchone()
    return dict(row) if row else None


def mark_task_running(conn: sqlite3.Connection, task_id: int, assigned_worker: str, stage: str) -> None:
    task = get_task_by_id(conn, task_id) or {}
    conn.execute(
        """
        UPDATE quote_tasks
        SET status='running', stage=?, assigned_worker=?, started_at=COALESCE(started_at, ?), error_text=NULL
        WHERE task_id=?
        """,
        (stage, assigned_worker, _now(), task_id),
    )
    conn.commit()
    append_task_event(
        conn,
        task_id,
        event_type="claim",
        from_stage=str(task.get("stage") or ""),
        to_stage=stage,
        worker=assigned_worker,
        status="running",
    )


def mark_task_stage(
    conn: sqlite3.Connection,
    task_id: int,
    next_stage: str,
    status: str = "queued",
    evidence: dict[str, Any] | None = None,
    result: dict[str, Any] | None = None,
    decision_id: int | None = None,
) -> None:
    task = get_task_by_id(conn, task_id) or {}
    conn.execute(
        """
        UPDATE quote_tasks
        SET status=?, stage=?, decision_id=COALESCE(?, decision_id), evidence_json=COALESCE(?, evidence_json), result_json=COALESCE(?, result_json)
        WHERE task_id=?
        """,
        (
            status,
            next_stage,
            decision_id,
            json.dumps(evidence, ensure_ascii=False, indent=2) if evidence else None,
            json.dumps(result, ensure_ascii=False, indent=2) if result else None,
            task_id,
        ),
    )
    conn.commit()
    append_task_event(
        conn,
        task_id,
        event_type="stage_advance",
        from_stage=str(task.get("stage") or ""),
        to_stage=next_stage,
        worker=str(task.get("assigned_worker") or ""),
        status=status,
    )


def mark_task_completed(conn: sqlite3.Connection, task_id: int, result: dict[str, Any]) -> None:
    task = get_task_by_id(conn, task_id) or {}
    conn.execute(
        """
        UPDATE quote_tasks
        SET status='completed', stage='completed', completed_at=?, decision_id=?, result_json=?, error_text=NULL
        WHERE task_id=?
        """,
        (
            _now(),
            result.get("decision_id"),
            json.dumps(result, ensure_ascii=False, indent=2),
            task_id,
        ),
    )
    conn.commit()
    append_task_event(
        conn,
        task_id,
        event_type="completed",
        from_stage=str(task.get("stage") or ""),
        to_stage="completed",
        worker=str(task.get("assigned_worker") or ""),
        status="completed",
        note=str(result.get("decision_id") or ""),
    )


def mark_task_failed(conn: sqlite3.Connection, task_id: int, error_text: str, result: dict[str, Any] | None = None) -> None:
    task = get_task_by_id(conn, task_id) or {}
    conn.execute(
        """
        UPDATE quote_tasks
        SET status='failed', stage='failed', completed_at=?, error_text=?, result_json=?
        WHERE task_id=?
        """,
        (
            _now(),
            error_text,
            json.dumps(result, ensure_ascii=False, indent=2) if result else None,
            task_id,
        ),
    )
    conn.commit()
    append_task_event(
        conn,
        task_id,
        event_type="failed",
        from_stage=str(task.get("stage") or ""),
        to_stage="failed",
        worker=str(task.get("assigned_worker") or ""),
        status="failed",
        note=error_text,
    )
