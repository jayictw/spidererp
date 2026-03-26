from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditLog
from app.models.base import utc_now


def write_audit_log(
    db: Session,
    *,
    object_type: str,
    object_id: str,
    action: str,
    status: str,
    summary: str,
    source: str = "rules",
    operator: str = "system",
    detail_json: dict[str, Any] | None = None,
    sample_id: int | None = None,
    rule_version_id: int | None = None,
    dedupe_key: str = "",
    trace_version: str = "v0.2",
    event_time: datetime | None = None,
) -> AuditLog:
    item = AuditLog(
        event_time=event_time or utc_now(),
        object_type=object_type,
        object_id=str(object_id),
        source=source,
        action=action,
        status=status,
        operator=operator,
        summary=summary,
        detail_json=detail_json or {},
        sample_id=sample_id,
        rule_version_id=rule_version_id,
        dedupe_key=dedupe_key,
        trace_version=trace_version,
    )
    db.add(item)
    db.flush()
    return item
