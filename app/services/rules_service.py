from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.response import error_response
from app.models import Rule, RuleVersion, Sample, TrainingQueueItem
from app.schemas.rules_actions import (
    SampleApproveAction,
    SampleRejectAction,
    SampleReviewAction,
    SampleSendTrainingAction,
)
from app.schemas.statuses import ALLOWED_DOMAIN_STATUSES
from app.services.audit_service import write_audit_log

ALLOWED_SAMPLE_SOURCES_FOR_REVIEW = {"pending", "running", "parsed", "failed"}
ALLOWED_SAMPLE_SOURCES_FOR_APPROVE = {"review"}
ALLOWED_SAMPLE_SOURCES_FOR_REJECT = {"review"}
ALLOWED_SAMPLE_SOURCES_FOR_SEND_TRAINING = {"approved"}


@dataclass
class RuleSnapshot:
    rule_name: str
    hit_hint: str
    explanation_rule: str
    sample_input: str
    expected_output: str
    version_note: str
    enabled: bool
    auto_approve_on_hit: bool


def _ensure_allowed_status(value: str) -> str:
    if value not in ALLOWED_DOMAIN_STATUSES:
        raise HTTPException(status_code=400, detail=error_response("invalid_status", f"unsupported status: {value}"))
    return value


def _ensure_sample_source_status(sample: Sample, *, allowed_sources: set[str], action: str) -> None:
    current_status = _ensure_allowed_status(sample.status)
    if current_status not in allowed_sources:
        raise HTTPException(
            status_code=409,
            detail=error_response(
                "invalid_transition",
                f"{action} not allowed from status: {current_status}",
            ),
        )


def _resolve_linked_rule_id(db: Session, sample: Sample, linked_rule_id: int | None) -> int | None:
    candidate_rule_id = linked_rule_id if linked_rule_id is not None else sample.linked_rule_id
    if candidate_rule_id is None:
        return None
    rule = get_rule_or_404(db, candidate_rule_id)
    return rule.id


def build_rule_snapshot(rule: Rule) -> dict[str, Any]:
    snapshot = RuleSnapshot(
        rule_name=rule.rule_name,
        hit_hint=rule.hit_hint,
        explanation_rule=rule.explanation_rule,
        sample_input=rule.sample_input,
        expected_output=rule.expected_output,
        version_note=rule.version_note,
        enabled=rule.enabled,
        auto_approve_on_hit=rule.auto_approve_on_hit,
    )
    return asdict(snapshot)


def create_rule(db: Session, payload: dict[str, Any], *, created_by: str = "system") -> Rule:
    rule = Rule(**payload)
    db.add(rule)
    db.flush()
    create_rule_version(
        db,
        rule,
        change_summary="initial",
        created_by=created_by,
        rule_snapshot=payload,
    )
    write_audit_log(
        db,
        object_type="rule",
        object_id=str(rule.id),
        action="create",
        status="approved",
        summary=f"rule created: {rule.rule_name}",
        operator=created_by,
        detail_json={"rule_id": rule.id, "rule_name": rule.rule_name},
    )
    db.commit()
    db.refresh(rule)
    return rule


def create_rule_version(
    db: Session,
    rule: Rule,
    *,
    change_summary: str = "",
    created_by: str = "system",
    rule_snapshot: dict[str, Any] | None = None,
) -> RuleVersion:
    latest_version = db.execute(
        select(RuleVersion.version_no).where(RuleVersion.rule_id == rule.id).order_by(RuleVersion.version_no.desc())
    ).scalars().first()
    version_no = 1 if latest_version is None else int(latest_version) + 1
    item = RuleVersion(
        rule_id=rule.id,
        version_no=version_no,
        rule_snapshot=rule_snapshot or build_rule_snapshot(rule),
        change_summary=change_summary,
        created_by=created_by,
    )
    db.add(item)
    db.flush()
    return item


def get_rule_or_404(db: Session, rule_id: int) -> Rule:
    rule = db.get(Rule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail=error_response("rule_not_found", "rule not found"))
    return rule


def get_sample_or_404(db: Session, sample_id: int) -> Sample:
    sample = db.get(Sample, sample_id)
    if sample is None:
        raise HTTPException(status_code=404, detail=error_response("sample_not_found", "sample not found"))
    return sample


def list_rules(db: Session, *, enabled: bool | None = None, limit: int = 50) -> list[Rule]:
    stmt = select(Rule).order_by(Rule.id.desc()).limit(limit)
    if enabled is not None:
        stmt = stmt.where(Rule.enabled == enabled)
    return list(db.execute(stmt).scalars().all())


def list_rule_versions(db: Session, rule_id: int, *, limit: int = 50) -> list[RuleVersion]:
    stmt = (
        select(RuleVersion)
        .where(RuleVersion.rule_id == rule_id)
        .order_by(RuleVersion.version_no.desc())
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())


def list_samples(db: Session, *, status: str | None = None, rule_name: str | None = None, limit: int = 50) -> list[Sample]:
    stmt = select(Sample).order_by(Sample.id.desc()).limit(limit)
    if status is not None:
        stmt = stmt.where(Sample.status == status)
    if rule_name is not None:
        stmt = stmt.where(Sample.rule_name == rule_name)
    return list(db.execute(stmt).scalars().all())


def review_sample(db: Session, sample_id: int, payload: SampleReviewAction, *, operator: str = "system") -> Sample:
    sample = get_sample_or_404(db, sample_id)
    _ensure_sample_source_status(sample, allowed_sources=ALLOWED_SAMPLE_SOURCES_FOR_REVIEW, action="review")
    sample.status = _ensure_allowed_status("review")
    write_audit_log(
        db,
        object_type="sample",
        object_id=str(sample.id),
        action="review",
        status=sample.status,
        summary=payload.note or "sample marked for review",
        operator=operator,
        detail_json={"sample_id": sample.id, "note": payload.note},
    )
    db.commit()
    db.refresh(sample)
    return sample


def approve_sample(db: Session, sample_id: int, payload: SampleApproveAction, *, operator: str = "system") -> Sample:
    sample = get_sample_or_404(db, sample_id)
    _ensure_sample_source_status(sample, allowed_sources=ALLOWED_SAMPLE_SOURCES_FOR_APPROVE, action="approve")
    if payload.linked_rule_id is not None:
        rule = get_rule_or_404(db, payload.linked_rule_id)
        sample.linked_rule_id = rule.id
        sample.rule_name = rule.rule_name
    sample.status = _ensure_allowed_status("approved")
    write_audit_log(
        db,
        object_type="sample",
        object_id=str(sample.id),
        action="approve",
        status=sample.status,
        summary=payload.note or "sample approved",
        operator=operator,
        detail_json={"sample_id": sample.id, "linked_rule_id": sample.linked_rule_id, "note": payload.note},
    )
    db.commit()
    db.refresh(sample)
    return sample


def reject_sample(db: Session, sample_id: int, payload: SampleRejectAction, *, operator: str = "system") -> Sample:
    sample = get_sample_or_404(db, sample_id)
    _ensure_sample_source_status(sample, allowed_sources=ALLOWED_SAMPLE_SOURCES_FOR_REJECT, action="reject")
    sample.status = _ensure_allowed_status("failed")
    write_audit_log(
        db,
        object_type="sample",
        object_id=str(sample.id),
        action="reject",
        status=sample.status,
        summary=payload.reason or "sample rejected",
        operator=operator,
        detail_json={"sample_id": sample.id, "reason": payload.reason},
    )
    db.commit()
    db.refresh(sample)
    return sample


def send_sample_to_training(
    db: Session,
    sample_id: int,
    payload: SampleSendTrainingAction,
    *,
    operator: str = "system",
) -> tuple[Sample, TrainingQueueItem]:
    sample = get_sample_or_404(db, sample_id)
    _ensure_sample_source_status(sample, allowed_sources=ALLOWED_SAMPLE_SOURCES_FOR_SEND_TRAINING, action="send_training")
    if payload.linked_rule_id is not None:
        get_rule_or_404(db, payload.linked_rule_id)
    resolved_linked_rule_id = _resolve_linked_rule_id(db, sample, payload.linked_rule_id)

    existing_item = db.execute(select(TrainingQueueItem).where(TrainingQueueItem.sample_id == sample.id)).scalar_one_or_none()
    if existing_item is None:
        existing_item = TrainingQueueItem(
            sample_id=sample.id,
            priority=payload.priority,
            queue_status="pending",
            linked_rule_id=resolved_linked_rule_id,
            note=payload.note,
        )
        db.add(existing_item)
    else:
        existing_item.priority = payload.priority
        existing_item.queue_status = "pending"
        existing_item.linked_rule_id = resolved_linked_rule_id
        existing_item.note = payload.note

    sample.status = _ensure_allowed_status("approved")
    write_audit_log(
        db,
        object_type="sample",
        object_id=str(sample.id),
        action="send_training",
        status=sample.status,
        summary=payload.note or "sample sent to training queue",
        operator=operator,
        detail_json={
            "sample_id": sample.id,
            "priority": payload.priority,
            "linked_rule_id": resolved_linked_rule_id,
            "note": payload.note,
        },
    )
    db.commit()
    db.refresh(sample)
    db.refresh(existing_item)
    return sample, existing_item


def create_rule_version_from_rule(
    db: Session,
    rule_id: int,
    *,
    change_summary: str = "",
    created_by: str = "system",
) -> RuleVersion:
    rule = get_rule_or_404(db, rule_id)
    item = create_rule_version(db, rule, change_summary=change_summary, created_by=created_by)
    write_audit_log(
        db,
        object_type="rule_version",
        object_id=str(item.id),
        action="create",
        status="approved",
        summary=f"rule version created for {rule.rule_name}",
        operator=created_by,
        detail_json={"rule_id": rule.id, "version_no": item.version_no, "change_summary": change_summary},
    )
    db.commit()
    db.refresh(item)
    return item
