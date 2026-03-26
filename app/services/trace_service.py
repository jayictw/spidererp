from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog, RuleVersion, Sample
from app.schemas.domain import (
    SampleTraceExtractorRead,
    SampleTracePrimarySampleRead,
    SampleTraceRuleRead,
    SampleTraceTimelineItemRead,
    SampleRead,
    SampleTraceDedupeRead,
    SampleTraceResponse,
)


def build_sample_trace_payload(db: Session, sample_id: int) -> dict:
    sample = db.get(Sample, sample_id)
    if sample is None:
        from fastapi import HTTPException
        from app.core.response import error_response

        raise HTTPException(status_code=404, detail=error_response("sample_not_found", "sample not found"))

    rule_version = db.get(RuleVersion, sample.rule_version_id) if sample.rule_version_id is not None else None
    primary_sample = db.get(Sample, sample.duplicate_of_sample_id) if sample.duplicate_of_sample_id is not None else None
    audit_stmt = (
        select(AuditLog)
        .where(
            (AuditLog.sample_id == sample.id)
            | ((AuditLog.object_type == "sample") & (AuditLog.object_id == str(sample.id)))
        )
        .order_by(AuditLog.event_time.desc(), AuditLog.id.desc())
    )
    audit_logs = db.execute(audit_stmt).scalars().all()
    payload = SampleTraceResponse(
        sample=SampleRead.model_validate(sample),
        dedupe=SampleTraceDedupeRead(
            dedupe_version=sample.dedupe_version,
            dedupe_key=sample.dedupe_key,
            is_duplicate=sample.is_duplicate,
            duplicate_of_sample_id=sample.duplicate_of_sample_id,
            duplicate_reason=sample.duplicate_reason,
            marked_duplicate_at=sample.marked_duplicate_at,
        ),
        extractor=SampleTraceExtractorRead(
            extractor_name=sample.extractor_name,
            extractor_version=sample.extractor_version,
        ),
        rule=SampleTraceRuleRead(
            rule_id=sample.rule_id if rule_version is None else rule_version.rule_id,
            rule_version_id=sample.rule_version_id,
        ),
        primary_sample=(
            SampleTracePrimarySampleRead(
                id=primary_sample.id,
                title=primary_sample.title,
                source_name=primary_sample.source_name,
                source_url=primary_sample.source_url,
                status=primary_sample.status,
            )
            if primary_sample is not None
            else None
        ),
        audit_timeline=[
            SampleTraceTimelineItemRead(
                event_time=item.event_time,
                action=item.action,
                status=item.status,
                operator=item.operator,
                summary=item.summary,
                dedupe_key=item.dedupe_key,
                trace_version=item.trace_version or "v0.2",
            )
            for item in audit_logs
        ],
    )
    return payload.model_dump(mode="json")
