from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.response import error_response
from app.models import Job, JobRun, Rule, RuleVersion, Sample
from app.schemas.domain import SampleCreate
from app.services.audit_service import write_audit_log
from app.services.dedupe_service import apply_dedupe_v1, build_dedupe_key
from app.services.trace_service import build_sample_trace_payload

EXTRACTOR_NAME = "crawler"
EXTRACTOR_VERSION = "v0.2"


def _get_rule_version_id(db: Session, rule_id: int | None, rule_version_id: int | None) -> int | None:
    if rule_version_id is not None:
        return rule_version_id
    if rule_id is None:
        return None
    stmt = select(RuleVersion.id).where(RuleVersion.rule_id == rule_id).order_by(RuleVersion.version_no.desc())
    return db.execute(stmt).scalars().first()


def create_sample(db: Session, payload: SampleCreate, *, operator: str = "system") -> Sample:
    if payload.job_id is not None and db.get(Job, payload.job_id) is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=error_response("job_not_found", "job not found"))
    if payload.run_id is not None and db.get(JobRun, payload.run_id) is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=error_response("run_not_found", "run not found"))
    if payload.rule_id is not None and db.get(Rule, payload.rule_id) is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=error_response("rule_not_found", "rule not found"))

    sample = Sample(**payload.model_dump())
    sample.rule_version_id = _get_rule_version_id(db, sample.rule_id, sample.rule_version_id)
    sample.extractor_name = payload.extractor_name or EXTRACTOR_NAME
    sample.extractor_version = payload.extractor_version or EXTRACTOR_VERSION
    sample.dedupe_version = "v1"
    sample.dedupe_key, sample.duplicate_reason = build_dedupe_key(
        website=(sample.normalized_payload.get("website") if isinstance(sample.normalized_payload, dict) else "") or sample.source_url,
        email=(sample.normalized_payload.get("email") if isinstance(sample.normalized_payload, dict) else "") or "",
        company_name=(sample.normalized_payload.get("company_name") if isinstance(sample.normalized_payload, dict) else "") or sample.source_name,
        title=(sample.normalized_payload.get("title") if isinstance(sample.normalized_payload, dict) else "") or sample.title,
        source_url=(sample.normalized_payload.get("source_url") if isinstance(sample.normalized_payload, dict) else "") or sample.source_url,
    )
    db.add(sample)
    db.flush()
    apply_dedupe_v1(db, sample, operator=operator, source="auto")
    write_audit_log(
        db,
        object_type="sample",
        object_id=str(sample.id),
        action="create",
        status=sample.status,
        summary="sample created",
        operator=operator,
        sample_id=sample.id,
        rule_version_id=sample.rule_version_id,
        dedupe_key=sample.dedupe_key,
        detail_json={
            "sample_id": sample.id,
            "rule_id": sample.rule_id,
            "rule_version_id": sample.rule_version_id,
            "dedupe_key": sample.dedupe_key,
        },
    )
    db.commit()
    db.refresh(sample)
    return sample


def mark_duplicate_sample(
    db: Session,
    sample_id: int,
    *,
    duplicate_of_sample_id: int,
    dedupe_key: str = "",
    duplicate_reason: str = "",
    operator: str = "system",
    source: str = "manual",
) -> Sample:
    from app.services.dedupe_service import mark_duplicate

    sample = mark_duplicate(
        db,
        sample_id,
        duplicate_of_sample_id=duplicate_of_sample_id,
        dedupe_key=dedupe_key,
        duplicate_reason=duplicate_reason,
        operator=operator,
        source=source,
    )
    db.commit()
    db.refresh(sample)
    return sample


def get_sample_trace(db: Session, sample_id: int):
    return build_sample_trace_payload(db, sample_id)
